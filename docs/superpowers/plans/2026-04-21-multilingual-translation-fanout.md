# Multilingual Translation Fanout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate `locale/{ka,be,tr,uk,pl}.po` with 1,097 fuzzy-cleared translations each by dispatching 5 parallel Agent subagents and merging their output via `scripts/apply-translations.py`.

**Architecture:** Main session extracts msgids from `locale/ru.po` → fans out one `Agent` call per target language in a single message → each subagent writes `/tmp/translations_<lang>.json` → main session validates (count check, format-specifier integrity, `msgfmt -c`) → runs `apply-translations.py` to drop translations into PO files with `fuzzy` stripped → commits per-language → pushes.

**Tech Stack:** Python 3 (for scaffolding/merge tooling), `gettext` 0.19.8.1 (`msgfmt -c` validation), Claude Code `Agent` tool (parallel subagent dispatch via Pro subscription), existing `scripts/apply-translations.py` (extended with JSON-input mode).

**Spec:** `docs/superpowers/specs/2026-04-21-multilingual-translation-fanout-design.md`

---

## File Structure

**Files to create:**
- `locale/tr.po` — Turkish PO scaffold (1,097 empty + fuzzy entries)
- `locale/uk.po` — Ukrainian PO scaffold
- `locale/pl.po` — Polish PO scaffold
- `scripts/gen-po-skeleton.py` — formalized skeleton generator (upstream the /tmp script)
- `/tmp/msgids.json` — array of 1,097 msgids extracted from ru.po (tmp, not committed)
- `/tmp/translations_{ka,be,tr,uk,pl}.json` — subagent outputs (tmp, not committed)

**Files to modify:**
- `scripts/apply-translations.py` — add `--lang <code>` and `--json <path>` flags; load dict from JSON; replace in-file TRANSLATIONS_* dicts with on-demand loading
- `locale/ka.po` — subagent output replaces existing 38-entry partial translation
- `locale/be.po` — subagent output replaces existing 38-entry partial translation

**Files unchanged but verified:**
- `locale/create-makefile` — already globs `*.po`, no edits needed
- `src/dvdisaster.c` — already calls `bindtextdomain/textdomain`, no edits needed

---

## Task 1: Formalize skeleton generator and scaffold tr/uk/pl

**Files:**
- Create: `scripts/gen-po-skeleton.py`
- Create: `locale/tr.po`, `locale/uk.po`, `locale/pl.po`

- [ ] **Step 1: Create `scripts/gen-po-skeleton.py` with Plural-Forms entries for all 5 target languages**

```python
#!/usr/bin/env python3
"""Generate a new .po skeleton from locale/ru.po for a target language.

Usage: python3 scripts/gen-po-skeleton.py <lang_code> <output_path>

Copies every msgid block verbatim from ru.po, blanks msgstr, marks every
translated entry `#, fuzzy`. The PO header is rewritten with
language-appropriate Plural-Forms and a machine-translated-seed note.
"""
import sys
import re
from pathlib import Path

HEADERS = {
    "ka": {
        "title_comment": "# Georgian translations for dvdisaster package\n# ქართული თარგმანი dvdisaster პაკეტისთვის.\n",
        "language": "Georgian",
        "language_code": "ka",
        "plural_forms": "nplurals=2; plural=(n!=1);",
    },
    "be": {
        "title_comment": "# Belarusian translations for dvdisaster package\n# Беларускі пераклад для пакета dvdisaster.\n",
        "language": "Belarusian",
        "language_code": "be",
        "plural_forms": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
    },
    "tr": {
        "title_comment": "# Turkish translations for dvdisaster package\n# dvdisaster paketi için Türkçe çeviriler.\n",
        "language": "Turkish",
        "language_code": "tr",
        "plural_forms": "nplurals=2; plural=(n != 1);",
    },
    "uk": {
        "title_comment": "# Ukrainian translations for dvdisaster package\n# Українські переклади для пакета dvdisaster.\n",
        "language": "Ukrainian",
        "language_code": "uk",
        "plural_forms": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
    },
    "pl": {
        "title_comment": "# Polish translations for dvdisaster package\n# Polskie tłumaczenia dla pakietu dvdisaster.\n",
        "language": "Polish",
        "language_code": "pl",
        "plural_forms": "nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
    },
}


def parse_entries(path):
    text = Path(path).read_text(encoding="utf-8")
    blocks = re.split(r"\n\n+", text)
    for idx, block in enumerate(blocks):
        block = block.rstrip()
        if not block:
            continue
        lines = block.split("\n")
        comment_lines = []
        i = 0
        while i < len(lines) and (lines[i].startswith("#") or lines[i].startswith("#~")):
            comment_lines.append(lines[i])
            i += 1
        body = lines[i:]
        msgstr_start = None
        for j, l in enumerate(body):
            if l.startswith("msgstr"):
                msgstr_start = j
                break
        if msgstr_start is None:
            yield ("\n".join(comment_lines), "\n".join(body), "", idx == 0)
            continue
        msgid_block = "\n".join(body[:msgstr_start])
        msgstr_block = "\n".join(body[msgstr_start:])
        yield ("\n".join(comment_lines), msgid_block, msgstr_block, idx == 0)


def build(lang_code, out_path):
    if lang_code not in HEADERS:
        raise SystemExit(f"Unknown language code: {lang_code}. Known: {list(HEADERS)}")
    meta = HEADERS[lang_code]
    entries = list(parse_entries("locale/ru.po"))
    out = []

    header_comment = (
        meta["title_comment"]
        + "# Copyright (C) 2026 THE dvdisaster'S COPYRIGHT HOLDER\n"
        + "# This file is distributed under the same license as the dvdisaster package.\n"
        + "# Machine-translated seed — contributors welcome to refine.\n"
        + "#\n"
    )
    header_body = (
        'msgid ""\n'
        'msgstr ""\n'
        '"Project-Id-Version: dvdisaster 0.79.10\\n"\n'
        '"Report-Msgid-Bugs-To: \\n"\n'
        '"POT-Creation-Date: 2026-04-06 16:01+0200\\n"\n'
        '"PO-Revision-Date: 2026-04-21 00:00+0000\\n"\n'
        '"Last-Translator: Machine-translated seed <noreply@example.com>\\n"\n'
        f'"Language-Team: {meta["language"]}\\n"\n'
        f'"Language: {meta["language_code"]}\\n"\n'
        '"MIME-Version: 1.0\\n"\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Content-Transfer-Encoding: 8bit\\n"\n'
        f'"Plural-Forms: {meta["plural_forms"]}\\n"\n'
    )
    out.append(header_comment + header_body)

    for comments, msgid_block, msgstr_block, is_header in entries[1:]:
        if not msgid_block.startswith("msgid"):
            continue
        comment_lines = [l for l in comments.split("\n") if l]
        has_flags = any(l.startswith("#,") for l in comment_lines)
        if has_flags:
            comment_lines = [
                (l.replace("#,", "#, fuzzy,", 1) if (l.startswith("#,") and "fuzzy" not in l) else l)
                for l in comment_lines
            ]
        else:
            comment_lines.append("#, fuzzy")
        if "msgid_plural" in msgid_block:
            n_plurals = len(re.findall(r"^msgstr\[\d+\]", msgstr_block, re.MULTILINE)) or 2
            blank_msgstr = "\n".join(f'msgstr[{i}] ""' for i in range(n_plurals))
        else:
            blank_msgstr = 'msgstr ""'
        entry = ""
        if comment_lines:
            entry += "\n".join(comment_lines) + "\n"
        entry += msgid_block + "\n" + blank_msgstr
        out.append(entry)

    Path(out_path).write_text("\n\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} with {len(out)} entries (1 header + {len(out)-1} msgids)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: gen-po-skeleton.py <lang_code> <output_path>")
    build(sys.argv[1], sys.argv[2])
```

- [ ] **Step 2: Make it executable and scaffold tr/uk/pl**

Run:
```bash
chmod +x scripts/gen-po-skeleton.py
python3 scripts/gen-po-skeleton.py tr locale/tr.po
python3 scripts/gen-po-skeleton.py uk locale/uk.po
python3 scripts/gen-po-skeleton.py pl locale/pl.po
```

Expected output (three times, varying only the language):
```
Wrote locale/tr.po with 1097 entries (1 header + 1096 msgids)
Wrote locale/uk.po with 1097 entries (1 header + 1096 msgids)
Wrote locale/pl.po with 1097 entries (1 header + 1096 msgids)
```

- [ ] **Step 3: Validate scaffolds with msgfmt**

Run:
```bash
for lang in tr uk pl; do
  msgfmt -c -o /tmp/check_${lang}.mo locale/${lang}.po && echo "${lang}: OK" || echo "${lang}: FAIL"
done
```
Expected: `tr: OK`, `uk: OK`, `pl: OK` (all three on separate lines).

- [ ] **Step 4: Verify each scaffold has 1097 msgid entries and 1096 `#, fuzzy` markers**

Run:
```bash
python3 -c "
import re
for lang in ['tr', 'uk', 'pl']:
    t = open(f'locale/{lang}.po', encoding='utf-8').read()
    n_msgid = len(re.findall(r'^msgid \"', t, re.MULTILINE))
    n_fuzzy = len(re.findall(r'^#, fuzzy', t, re.MULTILINE))
    print(f'{lang}: msgids={n_msgid}, fuzzy={n_fuzzy}')
"
```
Expected: `tr: msgids=1097, fuzzy=1096`, `uk: msgids=1097, fuzzy=1096`, `pl: msgids=1097, fuzzy=1096`.

- [ ] **Step 5: Commit**

```bash
git add scripts/gen-po-skeleton.py locale/tr.po locale/uk.po locale/pl.po
git commit -m "$(cat <<'EOF'
i18n: scaffold tr/uk/pl locale files and formalize skeleton generator

Adds scripts/gen-po-skeleton.py (upstreamed from /tmp helper). It reads
locale/ru.po and emits a new .po with identical msgid structure, empty
msgstrs, and #, fuzzy markers so gettext falls back to English until each
entry is reviewed. Plural-Forms rules encoded per language:
  - tr: nplurals=2 (Turkish)
  - uk: nplurals=3 (Ukrainian, Russian-style)
  - pl: nplurals=3 (Polish, distinct rule)

All three scaffolds validated with msgfmt -c.
EOF
)"
```

---

## Task 2: Extend `scripts/apply-translations.py` to load translations from JSON

**Files:**
- Modify: `scripts/apply-translations.py` (add argparse, add `--lang` + `--json` flags, load dict from JSON)

- [ ] **Step 1: Rewrite `scripts/apply-translations.py` with CLI interface**

Replace entire file contents with:

```python
#!/usr/bin/env python3
"""Apply translations to a locale/<lang>.po file.

Two modes of operation:

  1. In-file dicts (legacy, backward-compatible):
       python3 scripts/apply-translations.py
     Applies TRANSLATIONS_KA and TRANSLATIONS_BE dicts defined in this
     file to locale/ka.po and locale/be.po respectively. Used only for
     small manual fixups.

  2. JSON input (preferred for bulk translation):
       python3 scripts/apply-translations.py --lang ka --json /tmp/translations_ka.json
     Loads the JSON dict {msgid: msgstr} and applies it to locale/ka.po.
     Removes the `#, fuzzy` flag from each successfully-translated entry.

In both modes, entries not present in the translation dict are left
untouched (msgstr stays empty, fuzzy flag preserved) so gettext falls
back to English for them.

The escape logic is critical: `\\n` inside translations must survive as
the escape sequence in the PO file, not as a literal newline. This is
achieved by using a lambda in re.sub() for the msgstr replacement, so
re.sub does NOT interpret backslash escapes in the replacement string.
"""
import argparse
import json
import re
import sys
from pathlib import Path


# Legacy in-file dicts — kept for the 38 manual translations. Will be
# overridden by JSON input when --json is provided.
TRANSLATIONS_KA = {}
TRANSLATIONS_BE = {}


def _escape_for_po(s):
    """Escape a Python string for embedding inside a .po msgstr value."""
    return (s.replace("\\", "\\\\")
             .replace('"', '\\"')
             .replace("\n", "\\n")
             .replace("\t", "\\t"))


def _unescape_from_po(s):
    """Reverse of _escape_for_po."""
    return s.encode().decode("unicode_escape")


def _extract_msgid(entry):
    """Return the concatenated msgid string (unescaped) from a PO entry."""
    m = re.search(r'^msgid (.*?)(?=^msgid_plural |^msgstr)',
                  entry, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    parts = re.findall(r'"((?:\\.|[^"\\])*)"', raw)
    joined = "".join(parts)
    try:
        return _unescape_from_po(joined)
    except Exception:
        return joined


def apply(po_path, translations):
    """Apply translations dict to po_path; returns (applied, total)."""
    text = Path(po_path).read_text(encoding="utf-8")
    entries = re.split(r"\n\n+", text)
    out_entries = []
    applied = 0
    for i, entry in enumerate(entries):
        entry = entry.rstrip()
        if not entry:
            continue
        if i == 0:
            out_entries.append(entry)
            continue
        msgid = _extract_msgid(entry)
        if msgid is None or msgid not in translations:
            out_entries.append(entry)
            continue
        translation = translations[msgid]
        if not translation:
            # Empty translation means "don't translate" — skip rather than
            # produce an empty msgstr that would look translated.
            out_entries.append(entry)
            continue
        escaped = _escape_for_po(translation)
        new_msgstr = f'msgstr "{escaped}"'
        # Lambda replacement sidesteps backslash-escape interpretation.
        new_entry = re.sub(
            r'^msgstr.*(?:\n"[^"\n]*")*\s*$',
            lambda _m: new_msgstr,
            entry,
            flags=re.MULTILINE | re.DOTALL,
        )
        def _strip_fuzzy(m):
            flags = [f.strip() for f in m.group(1).split(",")
                     if f.strip() and f.strip() != "fuzzy"]
            if not flags:
                return ""
            return "#, " + ", ".join(flags) + "\n"
        new_entry = re.sub(r'^#,\s*([^\n]+)\n', _strip_fuzzy,
                           new_entry, count=1, flags=re.MULTILINE)
        out_entries.append(new_entry.rstrip())
        applied += 1
    Path(po_path).write_text("\n\n".join(out_entries) + "\n", encoding="utf-8")
    return applied, len(entries) - 1  # minus header


def main():
    parser = argparse.ArgumentParser(description="Apply translations to a PO file.")
    parser.add_argument("--lang", help="Target language code (e.g. ka, be, tr, uk, pl)")
    parser.add_argument("--json", dest="json_path",
                        help="Path to JSON file with {msgid: msgstr} dict")
    args = parser.parse_args()

    if args.lang and args.json_path:
        translations = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
        po_path = f"locale/{args.lang}.po"
        applied, total = apply(po_path, translations)
        print(f"{po_path}: applied {applied}/{total} translations "
              f"({len(translations)} supplied in JSON)")
    elif args.lang or args.json_path:
        parser.error("--lang and --json must be used together")
    else:
        # Legacy mode: apply in-file dicts
        if TRANSLATIONS_KA:
            applied, total = apply("locale/ka.po", TRANSLATIONS_KA)
            print(f"locale/ka.po: applied {applied}/{total} from in-file dict")
        if TRANSLATIONS_BE:
            applied, total = apply("locale/be.po", TRANSLATIONS_BE)
            print(f"locale/be.po: applied {applied}/{total} from in-file dict")
        if not TRANSLATIONS_KA and not TRANSLATIONS_BE:
            print("No translations to apply. Use --lang + --json for JSON input.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test JSON mode with a minimal 1-entry dict**

Run:
```bash
echo '{"medium.iso": "TEST_TRANSLATION"}' > /tmp/test_translations.json
# Backup ka.po first
cp locale/ka.po /tmp/ka.po.backup
python3 scripts/apply-translations.py --lang ka --json /tmp/test_translations.json
grep -A1 '^msgid "medium.iso"' locale/ka.po | head -2
```
Expected output (last two lines):
```
msgid "medium.iso"
msgstr "TEST_TRANSLATION"
```

- [ ] **Step 3: Restore ka.po and verify apply is idempotent**

Run:
```bash
cp /tmp/ka.po.backup locale/ka.po
# Re-apply the minimal translation, should succeed the same way
python3 scripts/apply-translations.py --lang ka --json /tmp/test_translations.json
# Revert again so we start clean for the real subagent run
cp /tmp/ka.po.backup locale/ka.po
rm /tmp/ka.po.backup /tmp/test_translations.json
```
Expected: no errors; `locale/ka.po` matches the previously-committed `ka.po`.

- [ ] **Step 4: Commit**

```bash
git add scripts/apply-translations.py
git commit -m "$(cat <<'EOF'
i18n: extend apply-translations.py with --lang/--json flags

Enables bulk translation loading from JSON files produced by the parallel
subagent fanout (docs/superpowers/specs/2026-04-21-multilingual-translation-fanout-design.md).

Usage:
  python3 scripts/apply-translations.py --lang ka --json /tmp/translations_ka.json

The legacy in-file dict mode is preserved for small manual fixups but
is no longer the primary workflow.
EOF
)"
```

---

## Task 3: Extract msgids from ru.po to /tmp/msgids.json

**Files:**
- Create: `/tmp/msgids.json` (tmp, not committed)

- [ ] **Step 1: Write extraction script inline and run it**

Run:
```bash
python3 << 'EOF'
import re
import json
from pathlib import Path

text = Path("locale/ru.po").read_text(encoding="utf-8")
entries = re.split(r"\n\n+", text)

def _unescape(s):
    return s.encode().decode("unicode_escape")

def _extract_msgid(entry):
    m = re.search(r'^msgid (.*?)(?=^msgid_plural |^msgstr)',
                  entry, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    parts = re.findall(r'"((?:\\.|[^"\\])*)"', raw)
    joined = "".join(parts)
    try:
        return _unescape(joined)
    except Exception:
        return joined

msgids = []
for i, entry in enumerate(entries):
    if i == 0:
        continue
    entry = entry.rstrip()
    if not entry:
        continue
    mid = _extract_msgid(entry)
    if mid:
        msgids.append(mid)

Path("/tmp/msgids.json").write_text(
    json.dumps(msgids, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"Wrote /tmp/msgids.json with {len(msgids)} msgids")
EOF
```
Expected: `Wrote /tmp/msgids.json with 1097 msgids`.

- [ ] **Step 2: Sanity-check the JSON**

Run:
```bash
python3 -c "
import json
m = json.load(open('/tmp/msgids.json', encoding='utf-8'))
assert len(m) == 1097, f'expected 1097, got {len(m)}'
assert 'medium.iso' in m, 'missing known msgid medium.iso'
assert any('Failed seeking to sector' in s for s in m), 'missing format-specifier msgid'
print('msgids.json looks good: 1097 entries, contains expected samples')
"
```
Expected: `msgids.json looks good: 1097 entries, contains expected samples`.

- [ ] **Step 3: No commit — /tmp/msgids.json is workspace-local**

(Skip commit; this file is only consumed by the subagent dispatch.)

---

## Task 4: Dispatch 5 parallel subagents (one per language)

**Files:**
- Input: `/tmp/msgids.json`
- Output: `/tmp/translations_{ka,be,tr,uk,pl}.json`

- [ ] **Step 1: Issue 5 `Agent` tool calls in a single message, all run in parallel**

Each subagent uses `subagent_type: "general-purpose"`. The prompt template is identical for all 5, differing only in `<LANG_CODE>`, `<LANG_NAME>`, and a language-specific register note.

**Prompt template (substitute placeholders per language):**

````
You are translating 1,097 UI and error-message strings from English to <LANG_NAME> for the dvdisaster disc-recovery tool.

## Input
Read the msgid list from /tmp/msgids.json (a JSON array of 1097 strings).

Path to existing translations for reference context: /home/mezinster/dvdisaster/.worktrees/upstream-prs/locale/ru.po (Russian — use as style reference for register and terminology).

## Output
Write a JSON object mapping each msgid to its <LANG_NAME> translation at:
  /tmp/translations_<LANG_CODE>.json

Format: {"msgid_string": "translated_string", ...}

## Rules (read carefully — format violations cause build failures)

### Glossary — keep these English, do NOT translate:
RS01, RS02, RS03, RS03f, RS03i, ECC, CRC, MD5, CD, DVD, BD, Blu-Ray, TAO, DAO, ISO, UDF, SSE2, AltiVec, mmap, sg, cdrom, dvdisaster

### Preserve exactly (must appear the same count in translation as in msgid):
- Format specifiers: `%s`, `%d`, `%c`, `%<PRId64>`, `%3d`, `%%`
- Escape sequences: `\n`, `\t`, `\\`, `\"`
- Leading/trailing whitespace (if msgid starts/ends with spaces, so must msgstr)
- CLI flag names: `--read-medium`, `--no-progress`, `--erase`, etc.

### Style
- Technical, concise, matching a disk-recovery tool's register
- Not marketing-speak, not chatty
- Match the level of formality used in other technical tools in <LANG_NAME>
- <LANGUAGE_SPECIFIC_NOTE>

### Completeness
- Every msgid MUST have a non-empty translation in the output JSON
- If a msgid is just a technical term that stays in English (e.g. "RS01"), set msgstr to the same English string

## Verification before writing output
1. Count entries — must be exactly 1097
2. For each entry, verify format-specifier count matches the msgid
3. For each entry, verify escape-sequence count matches the msgid

## Deliverable
ONE file: /tmp/translations_<LANG_CODE>.json
Report back: entry count, any entries you had to leave as English per glossary rule, and any concerns about the translation quality.
````

**Language-specific notes to substitute into `<LANGUAGE_SPECIFIC_NOTE>`:**

- **ka (Georgian)**: "Use Mkhedruli script (UTF-8). Georgian has no grammatical gender and no definite/indefinite articles. Keep sentences direct."
- **be (Belarusian)**: "Use Narkamaŭka (official) orthography, not Taraškievica. Cyrillic script."
- **tr (Turkish)**: "Turkish uses agglutination; keep compound nouns concise. Use Turkish apostrophes where appropriate (e.g. `CD'de`)."
- **uk (Ukrainian)**: "Ukrainian Cyrillic, modern orthography. Use 'і' not 'и' in Ukrainian-specific contexts."
- **pl (Polish)**: "Formal register (use impersonal forms or 2nd-person-plural; avoid 2nd-person singular). Use Polish diacritics (ą, ć, ę, ł, ń, ó, ś, ź, ż)."

The 5 `Agent` calls go in one message for parallel dispatch:

```
Agent(description="Translate UI strings to Georgian", subagent_type="general-purpose",
      prompt="<full prompt with ka substitutions>", run_in_background=true)
Agent(description="Translate UI strings to Belarusian", subagent_type="general-purpose",
      prompt="<full prompt with be substitutions>", run_in_background=true)
Agent(description="Translate UI strings to Turkish", subagent_type="general-purpose",
      prompt="<full prompt with tr substitutions>", run_in_background=true)
Agent(description="Translate UI strings to Ukrainian", subagent_type="general-purpose",
      prompt="<full prompt with uk substitutions>", run_in_background=true)
Agent(description="Translate UI strings to Polish", subagent_type="general-purpose",
      prompt="<full prompt with pl substitutions>", run_in_background=true)
```

Expected: 5 subagent IDs returned; all run in background; console reports completion notifications.

- [ ] **Step 2: Wait for all 5 subagents to complete (notifications come in asynchronously)**

Do not poll. The harness will deliver completion notifications automatically. When all 5 have reported done, proceed to validation.

- [ ] **Step 3: Verify all 5 JSON outputs exist**

Run:
```bash
ls -la /tmp/translations_*.json
```
Expected: 5 files, each > 20KB.

---

## Task 5: Validate each subagent's output

**Files:**
- Read: `/tmp/translations_{ka,be,tr,uk,pl}.json`

- [ ] **Step 1: Validate entry count + format-specifier integrity for all 5 languages**

Run:
```bash
python3 << 'EOF'
import json
import re
from pathlib import Path

msgids = json.load(open("/tmp/msgids.json", encoding="utf-8"))
assert len(msgids) == 1097, f"msgids.json has {len(msgids)}, expected 1097"

SPEC_RE = re.compile(r"%(?:<PRId64>|[0-9]*[dscxXoufeg%c])")
ESC_RE = re.compile(r"\\(?:n|t|\\|\"|r|0)")

all_ok = True
for lang in ["ka", "be", "tr", "uk", "pl"]:
    path = f"/tmp/translations_{lang}.json"
    if not Path(path).exists():
        print(f"{lang}: MISSING output file")
        all_ok = False
        continue
    trans = json.load(open(path, encoding="utf-8"))
    errs = []
    missing = [m for m in msgids if m not in trans]
    if missing:
        errs.append(f"missing {len(missing)} msgids (first 3: {missing[:3]})")
    empty = [m for m, v in trans.items() if not v]
    if empty:
        errs.append(f"empty msgstr for {len(empty)} entries")
    spec_mismatches = []
    esc_mismatches = []
    for m in msgids:
        if m not in trans:
            continue
        v = trans[m]
        if len(SPEC_RE.findall(m)) != len(SPEC_RE.findall(v)):
            spec_mismatches.append(m[:50])
        if len(ESC_RE.findall(m)) != len(ESC_RE.findall(v)):
            esc_mismatches.append(m[:50])
    if spec_mismatches:
        errs.append(f"format-specifier mismatch in {len(spec_mismatches)} entries: {spec_mismatches[:3]}")
    if esc_mismatches:
        errs.append(f"escape-sequence mismatch in {len(esc_mismatches)} entries: {esc_mismatches[:3]}")
    if errs:
        print(f"{lang}: FAIL — {'; '.join(errs)}")
        all_ok = False
    else:
        print(f"{lang}: OK ({len(trans)} entries)")

if not all_ok:
    raise SystemExit(1)
print("All 5 languages passed validation.")
EOF
```
Expected: 5 lines `<lang>: OK (N entries)` then `All 5 languages passed validation.`

- [ ] **Step 2: If any language fails, respawn just that one subagent with the failures highlighted**

If validation in Step 1 reports FAIL for language `<LANG>`:

1. Note the list of broken msgids from the error output (up to 3 shown; extract all via Python if needed)
2. Dispatch ONE more `Agent` call with this prompt:

```
You previously translated msgids to <LANG_NAME> and wrote /tmp/translations_<LANG_CODE>.json.
Validation found problems with these specific entries: <LIST_FROM_STEP_1>.

Please reload /tmp/msgids.json and /tmp/translations_<LANG_CODE>.json.
Re-translate only the failing entries, updating the JSON file in place.
Preserve all other entries unchanged.

Rules (reminder):
- Format specifiers (%s, %d, %<PRId64>, %%) must appear the same count in msgstr as in msgid
- Escape sequences (\n, \t, \\) must be preserved exactly as they appear in msgid
- Output is /tmp/translations_<LANG_CODE>.json (same path, rewritten in place)
```

3. When the respawned subagent finishes, re-run Step 1 until all 5 pass.

---

## Task 6: Apply translations to PO files and validate with msgfmt

**Files:**
- Modify: `locale/{ka,be,tr,uk,pl}.po`

- [ ] **Step 1: Apply translations for all 5 languages**

Run:
```bash
for lang in ka be tr uk pl; do
  python3 scripts/apply-translations.py --lang $lang --json /tmp/translations_${lang}.json
done
```
Expected (5 lines, one per language):
```
locale/ka.po: applied 1097/1096 translations (1097 supplied in JSON)
locale/be.po: applied 1097/1096 translations (1097 supplied in JSON)
locale/tr.po: applied 1097/1096 translations (1097 supplied in JSON)
locale/uk.po: applied 1097/1096 translations (1097 supplied in JSON)
locale/pl.po: applied 1097/1096 translations (1097 supplied in JSON)
```

(The "1097/1096" is because apply() counts 1096 non-header entries but ~1097 distinct msgid strings may exist due to duplicates; exact equality is acceptable.)

- [ ] **Step 2: Verify no `#, fuzzy` markers remain in any of the 5 files**

Run:
```bash
for lang in ka be tr uk pl; do
  n=$(grep -c "^#, fuzzy" locale/${lang}.po || echo 0)
  echo "${lang}: ${n} fuzzy markers remaining"
done
```
Expected: `ka: 0`, `be: 0`, `tr: 0`, `uk: 0`, `pl: 0` (all zero).

If any file shows a non-zero count, it means the JSON was missing those msgids — go back to Task 5 Step 2 to respawn the subagent for that language.

- [ ] **Step 3: Validate all 5 files with `msgfmt -c`**

Run:
```bash
for lang in ka be tr uk pl; do
  msgfmt -c -o /tmp/check_${lang}.mo locale/${lang}.po 2>&1 | head -5
  if [ -f /tmp/check_${lang}.mo ]; then
    echo "${lang}: msgfmt OK"
  else
    echo "${lang}: msgfmt FAILED — see errors above"
  fi
done
```
Expected: 5 lines `<lang>: msgfmt OK`.

If a language fails, `msgfmt` will print the specific line numbers with problems. Diagnose, fix the JSON (or manual edit of the PO), and retry.

- [ ] **Step 4: Verify non-empty msgstr count**

Run:
```bash
python3 << 'EOF'
import re
for lang in ["ka", "be", "tr", "uk", "pl"]:
    t = open(f"locale/{lang}.po", encoding="utf-8").read()
    n_empty = len(re.findall(r'^msgstr ""\s*$', t, re.MULTILINE))
    n_nonempty = len(re.findall(r'^msgstr "[^"]', t, re.MULTILINE))
    print(f"{lang}: empty={n_empty} non-empty={n_nonempty}")
EOF
```
Expected: `empty=1` (the header msgstr is a multi-line block, but `""` alone appears on the header line only), `non-empty≈1096` for each language.

If `non-empty` is significantly less than 1096, the JSON was incomplete — go back to Task 5.

---

## Task 7: Commit per-language translations

**Files:**
- `locale/{ka,be,tr,uk,pl}.po` (already modified)

- [ ] **Step 1: Commit Georgian**

```bash
git add locale/ka.po
git commit -m "$(cat <<'EOF'
i18n: complete Georgian (ka) translation — 1097 strings

Machine-translated via Claude parallel subagent fanout. All entries
fuzzy-cleared so translations ship to users immediately. Validated with
msgfmt -c.

Contributors: review and refine any awkward phrasing by editing
locale/ka.po directly. See docs/superpowers/specs/2026-04-21-multilingual-translation-fanout-design.md
for the glossary and translation conventions used.
EOF
)"
```

- [ ] **Step 2: Commit Belarusian**

```bash
git add locale/be.po
git commit -m "$(cat <<'EOF'
i18n: complete Belarusian (be) translation — 1097 strings

Machine-translated via Claude parallel subagent fanout (Narkamaŭka
orthography). All entries fuzzy-cleared. Validated with msgfmt -c.
EOF
)"
```

- [ ] **Step 3: Commit Turkish**

```bash
git add locale/tr.po
git commit -m "$(cat <<'EOF'
i18n: add Turkish (tr) translation — 1097 strings

Machine-translated via Claude parallel subagent fanout. All entries
fuzzy-cleared. Validated with msgfmt -c.
EOF
)"
```

- [ ] **Step 4: Commit Ukrainian**

```bash
git add locale/uk.po
git commit -m "$(cat <<'EOF'
i18n: add Ukrainian (uk) translation — 1097 strings

Machine-translated via Claude parallel subagent fanout. All entries
fuzzy-cleared. Validated with msgfmt -c.
EOF
)"
```

- [ ] **Step 5: Commit Polish**

```bash
git add locale/pl.po
git commit -m "$(cat <<'EOF'
i18n: add Polish (pl) translation — 1097 strings

Machine-translated via Claude parallel subagent fanout (formal register,
impersonal forms). All entries fuzzy-cleared. Validated with msgfmt -c.
EOF
)"
```

- [ ] **Step 6: Push all 5 commits at once**

```bash
git push origin master
```

Expected: output like `5 new commits pushed`, ending with the SHA of the Polish commit.

---

## Task 8: End-to-end smoke test

**Files:** none modified in this task

- [ ] **Step 1: Reconfigure and rebuild the locale files**

Run:
```bash
./configure --with-gui=no
(cd locale && make clean && make)
```
Expected: output ending with (one line per language):
```
Updating ka.mo
Updating be.mo
Updating tr.mo
Updating uk.mo
Updating pl.mo
```

- [ ] **Step 2: Confirm `.mo` files were generated for all 5 new languages**

Run:
```bash
ls -la locale/{ka,be,tr,uk,pl}/LC_MESSAGES/dvdisaster.mo
```
Expected: 5 files, each non-empty.

- [ ] **Step 3: Rebuild the binary (picks up new localedir contents)**

Run:
```bash
make -j$(nproc)
```
Expected: build succeeds without errors; `./dvdisaster` executable exists.

- [ ] **Step 4: Smoke-test each locale via LANGUAGE env var**

Run:
```bash
for lang in ka be tr uk pl; do
  echo "=== $lang ==="
  LANGUAGE=$lang LC_ALL=en_US.UTF-8 ./dvdisaster --version 2>&1 | head -3
done
```
Expected: each block prints the dvdisaster version line, with the "Copyright..." or other follow-up text rendered in the target language (or English fallback for strings the new locale doesn't uniquely translate — e.g., "dvdisaster" itself).

If a locale doesn't show translated output, check that `locale/<lang>/LC_MESSAGES/dvdisaster.mo` exists and that the binary was rebuilt after `make locale`.

- [ ] **Step 5: No commit — this is verification only**

Record any observations (e.g. "Georgian renders correctly in terminal", "Polish shows diacritics properly") in the final PR/summary message.

---

## Self-Review

Spec coverage check (against `docs/superpowers/specs/2026-04-21-multilingual-translation-fanout-design.md`):

- **Parallel subagent fanout** → Task 4
- **Glossary (RS01/ECC/etc. English)** → Task 4 Step 1 prompt template
- **Format specifiers preserved** → Task 4 rules + Task 5 Step 1 validator
- **JSON dict output** → Task 4 deliverable + Task 2 `--json` flag
- **apply-translations.py merge** → Task 6 Step 1
- **msgfmt -c validation** → Task 6 Step 3
- **Per-language commits** → Task 7
- **Scaffold tr/uk/pl** → Task 1
- **Plural-Forms per language** → Task 1 Step 1 HEADERS dict
- **Error handling / respawn** → Task 5 Step 2
- **End-to-end smoke test** → Task 8

All spec requirements mapped to tasks. No gaps.
