#!/usr/bin/env python3
"""Apply translations to locale/ka.po and locale/be.po.

Reads the current .po files, replaces msgstr for any msgid found in the
TRANSLATIONS_KA / TRANSLATIONS_BE dicts, and removes the `#, fuzzy` flag
from successfully-translated entries so gettext will actually use them.

Designed to be run repeatedly as translations are added to the dicts.
"""
import re
import sys
from pathlib import Path

# --- Translations: single-line msgids only for the first pass ---
# Keys are exact msgid strings as they appear in ru.po.
# Values are the translated msgstr. Any entry NOT in the dict stays empty
# + fuzzy (English fallback at runtime).

TRANSLATIONS_KA = {
    # Common UI — buttons, menu items, labels
    "OK": "კარგი",
    "Cancel": "გაუქმება",
    "Close": "დახურვა",
    "Help": "დახმარება",
    "Apply": "გადატარება",
    "Quit": "გასვლა",
    "Yes": "დიახ",
    "No": "არა",
    "Save": "შენახვა",
    "Open": "გახსნა",
    "Error": "შეცდომა",
    "Warning": "გაფრთხილება",
    "Info": "ინფორმაცია",
    "Preferences": "პარამეტრები",
    "File": "ფაილი",
    "Edit": "რედაქტირება",
    "View": "ხედი",
    "Tools": "ხელსაწყოები",
    "About": "პროგრამის შესახებ",

    # Core actions
    "Create": "შექმნა",
    "Read": "წაკითხვა",
    "Scan": "სკანირება",
    "Verify": "შემოწმება",
    "Fix": "შეკეთება",
    "Repair": "შეკეთება",
    "Test": "ტესტირება",
    "Strip": "გაწმენდა",

    # Status / progress
    "Progress: %3d%%": "პროგრესი: %3d%%",
    "Aborted by user.": "გაუქმებულია მომხმარებლის მიერ.",
    "Aborted by user request!": "გაუქმებულია მომხმარებლის მოთხოვნით!",
    "Finished.": "დასრულდა.",
    "Done.": "შესრულდა.",
    "Success": "წარმატება",
    "Failed": "ვერ განხორციელდა",
    "Unknown": "უცნობი",

    # Media / hardware
    "CD": "CD",
    "DVD": "DVD",
    "BD": "BD",
    "Blu-Ray": "Blu-Ray",
    "Drive": "წამყვანი",
    "Device": "მოწყობილობა",
    "Image": "ასლი",
    "ECC": "ECC",
    "Sector": "სექტორი",
    "Sectors": "სექტორები",
    "Sector size": "სექტორის ზომა",
    "File size": "ფაილის ზომა",
    "Medium": "მედია",
    "Medium type": "მედიის ტიპი",
    "Medium size": "მედიის ზომა",

    # File names / placeholders
    "medium.iso": "medium.iso",
    "medium.ecc": "medium.ecc",
    "sector-": "სექტორი-",

    # Common error categories
    "Out of memory": "მეხსიერება ამოიწურა",
    "Out of memory.": "მეხსიერება ამოიწურა.",
    "File not found": "ფაილი ვერ მოიძებნა",
    "Permission denied": "წვდომა აკრძალულია",
    "Invalid argument": "არასწორი არგუმენტი",
    "Unknown error": "უცნობი შეცდომა",
    "I/O error": "I/O შეცდომა",

    # Frequent sentence fragments
    "Stop reporting these errors": "ამ შეცდომების გამოცხადების შეწყვეტა",
    "Continue reporting": "გამოცხადების გაგრძელება",
    "Raw reading only possible on CD media\n": "პირდაპირი წაკითხვა შესაძლებელია მხოლოდ CD მედიაზე\n",
    "2nd argument is missing": "მე-2 არგუმენტი აკლია",
    "3rd argument is missing": "მე-3 არგუმენტი აკლია",
    "4th argument is missing": "მე-4 არგუმენტი აკლია",
    "test phrase for verifying the locale installation": "ტესტის ფრაზა ლოკალის ინსტალაციის შესამოწმებლად",

    # Format-string errors (keep format specifiers intact!)
    "Number of erasures must be > 0 and <= %d\n": "წაშლების რაოდენობა უნდა იყოს > 0 და <= %d\n",
    "Failed seeking to sector %<PRId64> in image: %s": "ასლში სექტორ %<PRId64>-ზე გადასვლა ვერ მოხერხდა: %s",
    "Failed writing to sector %<PRId64> in image: %s": "ასლში სექტორ %<PRId64>-ში ჩაწერა ვერ მოხერხდა: %s",
    "Failed reading sector %<PRId64> in image: %s": "ასლში სექტორ %<PRId64>-ის წაკითხვა ვერ მოხერხდა: %s",
    "Failed reading sector %<PRId64>: %s": "სექტორ %<PRId64>-ის წაკითხვა ვერ მოხერხდა: %s",
    "Sector must be in range [0..%<PRId64>]\n": "სექტორი უნდა იყოს [0..%<PRId64>] დიაპაზონში\n",
    "Byte position must be in range [0..2047]": "ბაიტის პოზიცია უნდა იყოს [0..2047] დიაპაზონში",
    "Byte value must be in range [0..255]": "ბაიტის მნიშვნელობა უნდა იყოს [0..255] დიაპაზონში",
    "Sectors must be in range [0..%<PRId64>].\n": "სექტორები უნდა იყოს [0..%<PRId64>] დიაპაზონში.\n",
    "Erasing sectors [%<PRId64>,%<PRId64>]\n": "სექტორების წაშლა [%<PRId64>,%<PRId64>]\n",
    "New length must be in range [0..%<PRId64>].\n": "ახალი სიგრძე უნდა იყოს [0..%<PRId64>] დიაპაზონში.\n",
    "Truncating image to %<PRId64> sectors.\n": "ასლი იკვეცება %<PRId64> სექტორამდე.\n",
    "Could not truncate %s: %s\n": "ვერ შემცირდა %s: %s\n",
    "Setting byte %d in sector %<PRId64> to value %d.\n": "სექტორ %<PRId64>-ში ბაიტი %d ყენდება მნიშვნელობაზე %d.\n",
    "Failed seeking to start of image: %s\n": "ასლის დასაწყისზე გადასვლა ვერ მოხერხდა: %s\n",
    "Could not write the new byte value": "ახალი ბაიტის მნიშვნელობა ვერ ჩაიწერა",
    "Source sector must be in range [0..%<PRId64>]\n": "წყარო სექტორი უნდა იყოს [0..%<PRId64>] დიაპაზონში\n",
    "Destination sector must be in range [0..%<PRId64>]\n": "დანიშნულების სექტორი უნდა იყოს [0..%<PRId64>] დიაპაზონში\n",
    "Generating at most %d random correctable erasures.\n": "არაუმეტეს %d შემთხვევითი აღდგენადი წაშლის გენერაცია.\n",
}

TRANSLATIONS_BE = {
    # Common UI
    "OK": "OK",
    "Cancel": "Скасаваць",
    "Close": "Закрыць",
    "Help": "Даведка",
    "Apply": "Ужыць",
    "Quit": "Выйсці",
    "Yes": "Так",
    "No": "Не",
    "Save": "Захаваць",
    "Open": "Адкрыць",
    "Error": "Памылка",
    "Warning": "Папярэджанне",
    "Info": "Інфармацыя",
    "Preferences": "Налады",
    "File": "Файл",
    "Edit": "Праўка",
    "View": "Выгляд",
    "Tools": "Інструменты",
    "About": "Пра праграму",

    # Core actions
    "Create": "Стварыць",
    "Read": "Чытаць",
    "Scan": "Сканаваць",
    "Verify": "Праверыць",
    "Fix": "Выправіць",
    "Repair": "Адрамантаваць",
    "Test": "Тэст",
    "Strip": "Ачысціць",

    # Status / progress
    "Progress: %3d%%": "Прагрэс: %3d%%",
    "Aborted by user.": "Перарвана карыстальнікам.",
    "Aborted by user request!": "Перарвана па запыце карыстальніка!",
    "Finished.": "Скончана.",
    "Done.": "Гатова.",
    "Success": "Поспех",
    "Failed": "Не ўдалося",
    "Unknown": "Невядома",

    # Media / hardware
    "CD": "CD",
    "DVD": "DVD",
    "BD": "BD",
    "Blu-Ray": "Blu-Ray",
    "Drive": "Прывад",
    "Device": "Прылада",
    "Image": "Вобраз",
    "ECC": "ECC",
    "Sector": "Сектар",
    "Sectors": "Сектары",
    "Sector size": "Памер сектара",
    "File size": "Памер файла",
    "Medium": "Носьбіт",
    "Medium type": "Тып носьбіта",
    "Medium size": "Памер носьбіта",

    # File names / placeholders
    "medium.iso": "medium.iso",
    "medium.ecc": "medium.ecc",
    "sector-": "сектар-",

    # Common error categories
    "Out of memory": "Не хапае памяці",
    "Out of memory.": "Не хапае памяці.",
    "File not found": "Файл не знойдзены",
    "Permission denied": "Доступ забаронены",
    "Invalid argument": "Няправільны аргумент",
    "Unknown error": "Невядомая памылка",
    "I/O error": "Памылка ўводу/вываду",

    # Frequent sentence fragments
    "Stop reporting these errors": "Спыніць паведамленні пра гэтыя памылкі",
    "Continue reporting": "Працягваць паведамленні",
    "Raw reading only possible on CD media\n": "Сырое чытанне магчымае толькі для носьбітаў CD\n",
    "2nd argument is missing": "Адсутнічае 2-гі аргумент",
    "3rd argument is missing": "Адсутнічае 3-ці аргумент",
    "4th argument is missing": "Адсутнічае 4-ты аргумент",
    "test phrase for verifying the locale installation": "тэставая фраза для праверкі ўстаноўкі лакалі",

    # Format-string errors
    "Number of erasures must be > 0 and <= %d\n": "Колькасць сціранняў павінна быць > 0 і <= %d\n",
    "Failed seeking to sector %<PRId64> in image: %s": "Не ўдалося перайсці да сектара %<PRId64> у вобразе: %s",
    "Failed writing to sector %<PRId64> in image: %s": "Не ўдалося запісаць у сектар %<PRId64> у вобразе: %s",
    "Failed reading sector %<PRId64> in image: %s": "Не ўдалося прачытаць сектар %<PRId64> у вобразе: %s",
    "Failed reading sector %<PRId64>: %s": "Не ўдалося прачытаць сектар %<PRId64>: %s",
    "Sector must be in range [0..%<PRId64>]\n": "Сектар павінен быць у дыяпазоне [0..%<PRId64>]\n",
    "Byte position must be in range [0..2047]": "Пазіцыя байта павінна быць у дыяпазоне [0..2047]",
    "Byte value must be in range [0..255]": "Значэнне байта павінна быць у дыяпазоне [0..255]",
    "Sectors must be in range [0..%<PRId64>].\n": "Сектары павінны быць у дыяпазоне [0..%<PRId64>].\n",
    "Erasing sectors [%<PRId64>,%<PRId64>]\n": "Сціранне сектараў [%<PRId64>,%<PRId64>]\n",
    "New length must be in range [0..%<PRId64>].\n": "Новая даўжыня павінна быць у дыяпазоне [0..%<PRId64>].\n",
    "Truncating image to %<PRId64> sectors.\n": "Абразанне вобраза да %<PRId64> сектараў.\n",
    "Could not truncate %s: %s\n": "Не ўдалося абрэзаць %s: %s\n",
    "Setting byte %d in sector %<PRId64> to value %d.\n": "Усталёўваецца байт %d у сектары %<PRId64> у значэнне %d.\n",
    "Failed seeking to start of image: %s\n": "Не ўдалося перайсці да пачатку вобраза: %s\n",
    "Could not write the new byte value": "Не ўдалося запісаць новае значэнне байта",
    "Source sector must be in range [0..%<PRId64>]\n": "Зыходны сектар павінен быць у дыяпазоне [0..%<PRId64>]\n",
    "Destination sector must be in range [0..%<PRId64>]\n": "Мэтавы сектар павінен быць у дыяпазоне [0..%<PRId64>]\n",
    "Generating at most %d random correctable erasures.\n": "Генерацыя не больш за %d выпадковых папраўных сціранняў.\n",
}


def _escape_for_po(s):
    """Escape a Python string for embedding inside a .po msgstr value."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def _unescape_from_po(s):
    """Reverse of _escape_for_po."""
    return s.encode().decode("unicode_escape")


def _extract_msgid(entry):
    """Given a full entry block, return the concatenated msgid string (unescaped)."""
    # msgid "..." possibly spanning multiple "..." continuation lines until msgstr/msgid_plural
    m = re.search(r'^msgid (.*?)(?=^msgid_plural |^msgstr)', entry, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    # Each line is like `"..."` — concatenate
    parts = re.findall(r'"((?:\\.|[^"\\])*)"', raw)
    joined = "".join(parts)
    try:
        return _unescape_from_po(joined)
    except Exception:
        return joined


def apply(po_path, translations):
    text = Path(po_path).read_text(encoding="utf-8")
    entries = re.split(r"\n\n+", text)
    out_entries = []
    applied = 0
    for i, entry in enumerate(entries):
        entry = entry.rstrip()
        if not entry:
            continue
        if i == 0:
            # header entry — leave as-is
            out_entries.append(entry)
            continue
        msgid = _extract_msgid(entry)
        if msgid is None or msgid not in translations:
            out_entries.append(entry)
            continue
        # Replace msgstr with the translation and drop fuzzy
        translation = translations[msgid]
        escaped = _escape_for_po(translation)
        new_msgstr = f'msgstr "{escaped}"'
        # Drop trailing msgstr block (plural or singular) and append our new one.
        # Use a lambda for the replacement so backslash escapes in `new_msgstr`
        # (e.g. \n inside translated strings) are NOT interpreted by re.sub.
        new_entry = re.sub(
            r'^msgstr.*(?:\n"[^"\n]*")*\s*$',
            lambda _m: new_msgstr,
            entry,
            flags=re.MULTILINE | re.DOTALL,
        )
        # Remove the `fuzzy` marker from the flags comment
        def _strip_fuzzy(m):
            flags = [f.strip() for f in m.group(1).split(",") if f.strip() and f.strip() != "fuzzy"]
            if not flags:
                return ""
            return "#, " + ", ".join(flags) + "\n"
        new_entry = re.sub(r'^#,\s*([^\n]+)\n', _strip_fuzzy, new_entry, count=1, flags=re.MULTILINE)
        out_entries.append(new_entry.rstrip())
        applied += 1
    Path(po_path).write_text("\n\n".join(out_entries) + "\n", encoding="utf-8")
    print(f"{po_path}: applied {applied} translations")


if __name__ == "__main__":
    apply("locale/ka.po", TRANSLATIONS_KA)
    apply("locale/be.po", TRANSLATIONS_BE)
