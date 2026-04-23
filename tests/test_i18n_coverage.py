"""CI gate: every locale/*.po must reach the translation threshold."""
import subprocess
import re
from pathlib import Path
import pytest

LOCALE_DIR = Path(__file__).parent.parent / "locale"
THRESHOLD_PCT = 90.0

def get_po_files():
    return sorted(LOCALE_DIR.glob("*.po"))

def parse_stats(po_path):
    result = subprocess.run(
        ["msgfmt", "--statistics", str(po_path), "-o", "/dev/null"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"msgfmt failed on {po_path}:\n{result.stderr}"
        )
    output = result.stderr + result.stdout
    translated = int(re.search(r'\b(\d+) translated\b', output).group(1)) if 'translated' in output else 0
    untranslated = int(re.search(r'\b(\d+) untranslated\b', output).group(1)) if 'untranslated' in output else 0
    fuzzy = int(re.search(r'\b(\d+) fuzzy\b', output).group(1)) if 'fuzzy' in output else 0
    total = translated + untranslated + fuzzy
    return translated, untranslated, fuzzy, total

@pytest.mark.parametrize("po_path", get_po_files(), ids=lambda p: p.stem)
def test_translation_coverage(po_path):
    translated, untranslated, fuzzy, total = parse_stats(po_path)
    assert total > 0, f"{po_path.name}: no strings found"
    pct = translated / total * 100
    assert pct >= THRESHOLD_PCT, (
        f"{po_path.name}: {pct:.1f}% translated ({translated}/{total}), "
        f"need {THRESHOLD_PCT}%"
    )
