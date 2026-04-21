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
