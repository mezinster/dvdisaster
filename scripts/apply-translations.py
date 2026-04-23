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

Context-marker hygiene: dvdisaster uses sgettext()-style msgids like
"button|Read" where the "button|" prefix is a translator-hint that the
sgettext() wrapper in src/misc.c strips on the untranslated fallback
path. Machine translators tend to translate the prefix verbatim,
producing msgstrs like "button|Чытаць" -- which sgettext() returns
as-is, leaking into the UI. apply() strips such leaked prefixes from
incoming translations before writing them (see _strip_context_prefix).
"""
import argparse
import json
import re
import sys
from pathlib import Path


# dvdisaster msgids use a short ASCII identifier as a context marker,
# e.g. "button|Read", "tooltip|...", "windowtitle|...", "menu|...".
# Detects that prefix so we can scrub it from translations that
# accidentally include a translated copy of it.
_CTX_PREFIX_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,29}\|')


def _strip_context_prefix(msgid, translation):
    """If msgid has a 'CTX|' context marker and the translation also
    starts with '<anything>|', strip everything up to and including
    the first '|' in the translation.

    Machine translators often translate the context marker verbatim
    (e.g. 'button|Read' -> 'button|Чытаць' or 'ფანჯარა სათავე|...')
    which the runtime sgettext() does not un-prefix on the translated
    path. We cap the prefix length at 60 chars so a legitimate '|' in
    the translation body is never eaten.
    """
    if not _CTX_PREFIX_RE.match(msgid):
        return translation
    # Look for a leaked prefix in the translation: up to 60 chars with
    # no embedded quote/pipe, followed by '|'.
    m = re.match(r'^([^"|]{1,60})\|(.*)$', translation, re.DOTALL)
    if not m:
        return translation
    return m.group(2)


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
        translation = _strip_context_prefix(msgid, translation)
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
