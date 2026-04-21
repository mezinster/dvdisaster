# Multilingual Translation Fanout — Design Spec

**Date:** 2026-04-21
**Status:** Approved, ready for implementation planning
**Target languages:** Georgian (ka), Belarusian (be), Turkish (tr), Ukrainian (uk), Polish (pl)

## Context

dvdisaster has existing translations for Czech (cs), German (de), Italian (it), Brazilian Portuguese (pt_BR), Russian (ru), and Swedish (sv). The i18n pipeline (`locale/create-makefile` + `gettext`) auto-detects any new `*.po` file — no source-code registration required.

Current state (as of master `d6730d9`):
- Scaffolds exist: `locale/ka.po`, `locale/be.po` (1,097 entries each, 38 translated)
- Remaining targets: `locale/tr.po`, `locale/uk.po`, `locale/pl.po` (not yet scaffolded)
- Tooling: `scripts/apply-translations.py` (merges dict-based translations into PO files, strips `fuzzy` flag from translated entries)
- `gettext` 0.19.8.1 installed (`msgfmt`, `msgmerge`, `xgettext` available)

Source of truth for msgid list: `locale/ru.po` (1,097 entries, most recently msgmerged against the current source).

## Goal

Populate all 5 target PO files with **complete, fuzzy-cleared translations** as fast as possible. Users should see their native language immediately after the next `./configure && make locale && make install`.

## Non-Goals

- Not adding a UI language-picker dropdown (dvdisaster uses env-var `LC_MESSAGES` selection; nothing to change in the source)
- Not regenerating `messages.pot` from current source (existing ru.po string set is the source of truth; diverging from it would require re-translating anyway)
- Not translating HTML help files or README (only `.po`-tracked strings)

## Approach: Parallel Subagent Fanout

### Architecture

```
main Claude Code session
    │
    ├── dispatches 5 Agent tool calls in one message (parallel execution)
    │
    ├── Agent #1 (ka) ──▶ /tmp/translations_ka.json
    ├── Agent #2 (be) ──▶ /tmp/translations_be.json
    ├── Agent #3 (tr) ──▶ /tmp/translations_tr.json
    ├── Agent #4 (uk) ──▶ /tmp/translations_uk.json
    └── Agent #5 (pl) ──▶ /tmp/translations_pl.json
              │
              ▼ (all complete in ~10–15 min wall time)
    scripts/apply-translations.py (extended: load dicts from JSON)
              │
              ▼
    locale/{ka,be,tr,uk,pl}.po  (fuzzy-cleared)
              │
              ▼
    msgfmt -c validation (fails commit if format specifiers don't match)
              │
              ▼
    5 commits (one per language) + push
```

### Why parallel subagents and not a single large session

- Each subagent has its own context window. All 5 can process ~1,097 msgids simultaneously without exhausting the main session's context.
- Each subagent uses Claude Pro-subscription tokens (overage-covered), not API credits.
- Wall clock: ~10–15 min total (vs many hours for sequential me-in-session translation).

### Subagent prompt contract (identical for all 5; only target language varies)

**Input supplied in prompt:**
- Complete list of 1,097 msgids, extracted from `locale/ru.po` into a JSON array at `/tmp/msgids.json`
- Path hint: `/home/mezinster/dvdisaster/.worktrees/upstream-prs/locale/ru.po` (for context lookup if needed)
- Target language name and ISO code
- Glossary (see below)

**Glossary — translate literally or keep English:**
- Keep English (proper nouns / tech acronyms): `RS01`, `RS02`, `RS03`, `RS03f`, `RS03i`, `ECC`, `CRC`, `MD5`, `CD`, `DVD`, `BD`, `Blu-Ray`, `TAO`, `DAO`, `ISO`, `UDF`, `SSE2`, `AltiVec`, `mmap`, `sg`, `cdrom`
- Preserve exactly: format specifiers `%s %d %<PRId64> %3d%% %c`, escape sequences `\n \t \\ \"`, leading/trailing whitespace, HTML-like tags `<b>`, CLI flag names `--read-medium` etc.
- Register: technical, concise, disk-recovery tool (not chatty or marketing)
- Consistency: the same English term should translate the same way every occurrence (subagent's job)

**Output contract:**
- File: `/tmp/translations_<lang>.json`
- Format: `{"msgid_string": "msgstr_string", ...}` — plain JSON object, UTF-8
- Must contain all 1,097 msgids as keys (no missing)
- Values must be non-empty (empty string means skip and is a bug)

### Merge & commit pipeline

1. Extend `scripts/apply-translations.py`: add `--lang <code>` and `--json <path>` flags. When given a JSON file, load it as the translation dict and apply to `locale/<lang>.po`.
2. For each language, run: `python3 scripts/apply-translations.py --lang ka --json /tmp/translations_ka.json`
3. Validate: `msgfmt -c -o /tmp/check.mo locale/<lang>.po` — must exit 0
4. Sanity check: count non-empty msgstrs, confirm ≥ 1,097
5. Commit: `git commit -m "i18n: add <Language> translations (ka/be/tr/uk/pl)"`
6. Push after all 5 languages complete (single push, 5 commits)

### Scaffolding for tr/uk/pl

ka.po and be.po already scaffolded. Need to create analogous scaffolds for tr, uk, pl before subagent dispatch:

- Extend `/tmp/gen_po_skeleton.py` (or inline equivalent) with Plural-Forms rules:
  - `tr`: `nplurals=2; plural=(n != 1);`
  - `uk`: `nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);`
  - `pl`: `nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);`
- Generate `locale/tr.po`, `locale/uk.po`, `locale/pl.po` from ru.po with all msgstrs empty + `#, fuzzy` marker

### Error handling

| Failure mode | Detection | Response |
|---|---|---|
| Subagent returns <1,097 entries | Count check after JSON load | Respawn that one subagent with the missing msgid subset |
| Format specifiers mangled | Regex compares `%s\|%d\|%<PRId64>` counts in msgid vs msgstr | Respawn for affected entries only, supplying the originals as context |
| Subagent fails entirely (exception, timeout) | No JSON file at expected path | Respawn just that language; other 4 proceed |
| `msgfmt -c` rejects a file | Exit code ≠ 0 | Print error, abort commit for that language, dump offending lines |
| All entries pass but text is nonsense | Not detectable automatically | Out of scope — fuzzy-cleared means we trust subagent output; contributors can still fix later |

### Testing

Per-language post-translation checks (in this order):

1. **Count check** (Python): `len(translations) == 1097` and all msgstr values non-empty
2. **Format specifier integrity** (Python regex): for each entry, count of `%s|%d|%<PRId64>|%c|%3d` in msgid equals count in msgstr
3. **`msgfmt -c`** (shell): formal PO syntax + format-specifier validation — must produce a `.mo` without errors
4. **Runtime smoke test** (manual, optional): `LC_MESSAGES=ka_GE.UTF-8 ./dvdisaster --version` — expects Georgian version string

If steps 1–3 all pass, commit. Step 4 is a manual verification the user runs after the PR merges.

### Rollback

If a language's translations turn out poorly in practice, revert just that language's commit (`git revert <sha>`). Other languages unaffected. Scaffold remains (English fallback via fuzzy).

## Risks

- **Subagent context truncation**: 1,097 msgids ≈ 60KB input + 60KB output. Well within Sonnet's 200K context. Low risk.
- **Format-specifier mistakes**: mitigated by automated regex check before commit.
- **Glossary inconsistency across subagents**: each subagent self-consistent; cross-language variation acceptable since users see only one language.
- **Georgian script rendering**: dvdisaster uses Pango (via GTK3) in GUI; CLI uses raw UTF-8 to terminal. Georgian Mkhedruli is well-supported in both; no special font configuration needed.
- **Belarusian orthography**: two orthographies exist (Taraškievica vs Narkamaŭka); subagent defaults to Narkamaŭka (standard/official) — matches ru.po register.

## Success Criteria

- All 5 `locale/<lang>.po` files exist with ≥ 1,097 non-fuzzy msgstr entries
- All pass `msgfmt -c`
- `configure && make locale` generates 5 new `.mo` files without error
- User can set `LC_MESSAGES=ka_GE.UTF-8` (or other) and see translated CLI output
- Work committed and pushed in ≤ 20 min wall time from plan start
