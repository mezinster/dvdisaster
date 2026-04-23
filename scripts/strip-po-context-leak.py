#!/usr/bin/env python3
"""
Strip leaked context-marker prefixes from .po msgstr values.

dvdisaster uses the "CTX|English text" convention in msgids, where sgettext()
(src/misc.c) strips the "CTX|" part at runtime. Translators are supposed to
provide *only the translation* in msgstr (no prefix). Machine-translated seeds
sometimes translate the prefix verbatim too, leaving msgstrs like
  msgstr "button|Чытаць"
which sgettext() returns as-is (it only strips the prefix on the untranslated
fallback path), so users see "button|Чытаць" in the UI.

This script fixes that: for each entry whose msgid matches CTX|... and whose
msgstr matches ANY|<rest> (with a | in the first ~40 chars), it rewrites
msgstr to <rest>. Only runs the fix when msgid itself had a | prefix -- never
touches entries where | is legitimate content.

Usage:  strip-po-context-leak.py path/to/xx.po [path/to/yy.po ...]
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Matches a context-marker msgid prefix: "<no | or quotes>{1..30}|..."
# (the prefix in msgids never contains whitespace -- it's always a short
# ASCII identifier like "menu", "button", "windowtitle").
_MSGID_CTX_RE = re.compile(r'^"([^"|]{1,30})\|')

# When we KNOW the msgid had a context marker, the msgstr prefix may be
# a translated version of it (can contain spaces: e.g. ka translates
# "windowtitle" as "ფანჯარა სათავე"). Strip everything up to the first |,
# but cap the prefix length so we don't eat legitimate content.
_MSGSTR_LEAK_RE = re.compile(r'^"([^"|]{1,60})\|(.*)"$')


def msgid_has_context(msgid_lines: list[str]) -> bool:
    """True if msgid starts with 'XXX|' (ASCII identifier, no spaces)."""
    if not msgid_lines:
        return False
    return _MSGID_CTX_RE.match(msgid_lines[0]) is not None


def fix_msgstr_line(msgstr_line: str) -> tuple[str, bool]:
    """If msgstr starts with 'Y|rest', rewrite to 'rest'. Returns (new, changed)."""
    m = _MSGSTR_LEAK_RE.match(msgstr_line.rstrip())
    if not m:
        return msgstr_line, False
    rest = m.group(2)
    return f'"{rest}"\n', True


def process_file(path: Path) -> int:
    """Returns number of msgstr entries rewritten."""
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)

    out: list[str] = []
    i = 0
    fixes = 0

    while i < len(lines):
        line = lines[i]

        # Collect multi-line msgid block
        if line.startswith('msgid "'):
            msgid_block_first = line[len('msgid '):]  # "..."
            msgid_lines = [msgid_block_first]
            out.append(line)
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                msgid_lines.append(lines[i])
                out.append(lines[i])
                i += 1

            has_ctx = msgid_has_context(msgid_lines)

            # Now the following block should be msgstr
            if i < len(lines) and lines[i].startswith('msgstr "'):
                msgstr_first = lines[i][len('msgstr '):]
                if has_ctx:
                    new_first, changed = fix_msgstr_line(msgstr_first)
                    if changed:
                        fixes += 1
                        out.append(f'msgstr {new_first}')
                    else:
                        out.append(lines[i])
                else:
                    out.append(lines[i])
                i += 1
                # Copy any msgstr continuation lines untouched
                while i < len(lines) and lines[i].startswith('"'):
                    out.append(lines[i])
                    i += 1
            continue

        out.append(line)
        i += 1

    if fixes:
        path.write_text(''.join(out), encoding='utf-8')
    return fixes


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    total = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        n = process_file(p)
        total += n
        print(f'{p}: stripped {n} leaked context prefix(es)')
    print(f'Total: {total} msgstr(s) rewritten')
    return 0


if __name__ == '__main__':
    sys.exit(main())
