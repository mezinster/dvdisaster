# Hybrid Test Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a declarative Python test framework and migrate all 144 RS01 bash tests to it.

**Architecture:** A `GoldenTestSuite` base class converts declarative `GoldenTest` dataclass entries into parametrized pytest cases. Each test describes damage operations, dvdisaster action, and golden file to compare against. The runner handles image setup, damage application, execution, output cleaning, and golden file comparison. Complex tests use plain methods with semantic assertions.

**Tech Stack:** Python 3.8+, pytest, dataclasses

---

### Task 1: Core Damage Operations

**Files:**
- Create: `tests/framework.py`
- Test: `tests/test_framework.py`

- [ ] **Step 1: Write tests for damage operation CLI argument generation**

```python
# tests/test_framework.py
"""Tests for the test framework's damage operations."""

from framework import Erase, Byteset, Truncate, PadBytes, PadSectors


class TestDamageOps:
    def test_erase_range(self):
        op = Erase("1000-1049")
        assert op.cli_args() == ["--erase", "1000-1049"]

    def test_erase_single(self):
        op = Erase("766")
        assert op.cli_args() == ["--erase", "766"]

    def test_erase_with_fill_unreadable(self):
        op = Erase("15900-16099", fill_unreadable=64)
        assert op.cli_args() == ["--erase", "15900-16099", "--fill-unreadable=64"]

    def test_erase_with_label(self):
        op = Erase("15900-16099:readable in pass 3")
        assert op.cli_args() == ["--erase", "15900-16099:readable in pass 3"]

    def test_byteset(self):
        op = Byteset(4096, 100, 17)
        assert op.cli_args() == ["--byteset", "4096,100,17"]

    def test_truncate(self):
        op = Truncate(20500)
        assert op.cli_args() == ["--truncate=20500"]

    def test_pad_bytes(self):
        op = PadBytes(56)
        assert op.pad_size == 56

    def test_pad_sectors(self):
        op = PadSectors(17)
        assert op.pad_size == 17 * 2048
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_framework.py -v`
Expected: FAIL — `framework` module doesn't exist yet

- [ ] **Step 3: Implement damage operations**

```python
# tests/framework.py
"""
Declarative test framework for dvdisaster regression tests.

Provides a DSL for defining tests as dataclasses and a base class
(GoldenTestSuite) that converts them into parametrized pytest cases.
"""

import hashlib
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Union


# ---------------------------------------------------------------------------
# Damage operations
# ---------------------------------------------------------------------------

@dataclass
class Erase:
    """Erase sectors: --erase <spec>. Spec can include labels like
    '15900-16099:readable in pass 3'."""
    spec: str
    fill_unreadable: Optional[int] = None

    def cli_args(self) -> List[str]:
        args = ["--erase", self.spec]
        if self.fill_unreadable is not None:
            args.append(f"--fill-unreadable={self.fill_unreadable}")
        return args


@dataclass
class Byteset:
    """Set a byte in a sector: --byteset sector,offset,value."""
    sector: int
    offset: int
    value: int

    def cli_args(self) -> List[str]:
        return ["--byteset", f"{self.sector},{self.offset},{self.value}"]


@dataclass
class Truncate:
    """Truncate image to N sectors: --truncate=N."""
    sectors: int

    def cli_args(self) -> List[str]:
        return [f"--truncate={self.sectors}"]


@dataclass
class PadBytes:
    """Append N zero bytes to the image (done via Python, not CLI)."""
    count: int

    @property
    def pad_size(self) -> int:
        return self.count


@dataclass
class PadSectors:
    """Append N zero sectors (N * 2048 bytes) to the image."""
    count: int

    @property
    def pad_size(self) -> int:
        return self.count * 2048
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_framework.py::TestDamageOps -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/framework.py tests/test_framework.py
git commit -m "test: add damage operation dataclasses for test framework"
```

---

### Task 2: Golden File Parser

**Files:**
- Modify: `tests/framework.py`
- Modify: `tests/test_framework.py`

- [ ] **Step 1: Write tests for golden file parsing**

```python
# append to tests/test_framework.py
import os
import tempfile

from framework import GoldenFile, parse_golden_file


class TestGoldenFileParsing:
    def test_parse_with_both_checksums(self, tmp_path):
        golden = tmp_path / "RS01_good"
        golden.write_text(
            "9503f278d4550a9507a317664481adf8\n"
            "4be4dcc0f6b88965334ccf1050dfa5fa\n"
            "This software comes with  ABSOLUTELY NO WARRANTY.  This\n"
            "is free software and you are welcome to redistribute it\n"
            "under the conditions of the GNU GENERAL PUBLIC LICENSE.\n"
            "See the file \"COPYING\" for further information.\n"
            "\n"
            "Opening rs01-master.iso: 21000 medium sectors.\n"
            "Encoding with Method RS01: 32 roots, 14.3% redundancy.\n"
        )
        gf = parse_golden_file(str(golden))
        assert gf.image_md5 == "9503f278d4550a9507a317664481adf8"
        assert gf.ecc_md5 == "4be4dcc0f6b88965334ccf1050dfa5fa"
        assert "Opening rs01-master.iso" in gf.expected_output
        assert "ABSOLUTELY NO WARRANTY" not in gf.expected_output

    def test_parse_with_ignore_checksums(self, tmp_path):
        golden = tmp_path / "RS01_no_image"
        golden.write_text(
            "ignore\n"
            "ignore\n"
            "This software comes with  ABSOLUTELY NO WARRANTY.  This\n"
            "is free software and you are welcome to redistribute it\n"
            "under the conditions of the GNU GENERAL PUBLIC LICENSE.\n"
            "See the file \"COPYING\" for further information.\n"
            "\n"
            "Some output line.\n"
        )
        gf = parse_golden_file(str(golden))
        assert gf.image_md5 is None
        assert gf.ecc_md5 is None
        assert gf.expected_output == "Some output line.\n"

    def test_parse_platform_variant_preferred(self, tmp_path):
        base = tmp_path / "RS01_test"
        base.write_text("ignore\nignore\nheader\n\n\n\n\nbase output\n")
        darwin = tmp_path / "RS01_test.darwin"
        darwin.write_text("ignore\nignore\nheader\n\n\n\n\ndarwin output\n")

        # The resolve function should pick the right variant
        from framework import resolve_golden_path
        # On non-Darwin, should return base; on Darwin, should return .darwin
        result = resolve_golden_path(str(base))
        if platform.system() == "Darwin":
            assert result == str(darwin)
        else:
            assert result == str(base)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_framework.py::TestGoldenFileParsing -v`
Expected: FAIL — `GoldenFile`, `parse_golden_file` not defined

- [ ] **Step 3: Implement golden file parsing**

```python
# append to tests/framework.py

@dataclass
class GoldenFile:
    """Parsed golden reference file."""
    image_md5: Optional[str]  # None if "ignore"
    ecc_md5: Optional[str]    # None if "ignore"
    expected_output: str      # everything after the license header


def resolve_golden_path(base_path: str) -> str:
    """Pick platform-specific golden file if available."""
    system = platform.system()
    if system == "Darwin":
        darwin_path = base_path + ".darwin"
        if os.path.isfile(darwin_path):
            return darwin_path
    elif system == "Windows" or os.environ.get("OS", "").startswith("Windows"):
        win_path = base_path + ".win"
        if os.path.isfile(win_path):
            return win_path
    return base_path


def parse_golden_file(path: str) -> GoldenFile:
    """Parse a golden reference file from regtest/database/.

    Format:
      Line 1: image MD5 or "ignore"
      Line 2: ecc MD5 or "ignore"
      Lines 3-6: license header (4 lines)
      Line 7: blank
      Lines 8+: expected output
    """
    path = resolve_golden_path(path)
    with open(path, "r") as f:
        lines = f.readlines()

    image_md5 = lines[0].strip() if lines[0].strip() != "ignore" else None
    ecc_md5 = lines[1].strip() if lines[1].strip() != "ignore" else None

    # Skip header: lines 2-5 are license, line 6 is blank → output starts at line 7
    # (0-indexed: lines[2:6] are license, lines[6] is blank, lines[7:] are output)
    # But the bash code does `tail -n +3` on the reflog (skipping lines 1-2 = the MD5 lines)
    # then compares against newlog which already had the header stripped by `tail -n +4`
    # on dvdisaster output. So the golden file lines 3+ include the license header,
    # and the actual dvdisaster output has it stripped (tail -n +4 removes first 3 lines).
    # We need to strip lines 0-1 (MD5s) from golden and match the rest against
    # dvdisaster output that's had its first 3 lines (version/license) removed.
    expected_output = "".join(lines[2:])

    return GoldenFile(
        image_md5=image_md5,
        ecc_md5=ecc_md5,
        expected_output=expected_output,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_framework.py::TestGoldenFileParsing -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/framework.py tests/test_framework.py
git commit -m "test: add golden file parser for regtest database files"
```

---

### Task 3: Output Cleaning

**Files:**
- Modify: `tests/framework.py`
- Modify: `tests/test_framework.py`

- [ ] **Step 1: Write tests for output cleaning**

The bash `run_regtest` strips:
- `dvdisaster: No memory leaks found.` lines
- Windows drive-letter paths (`C:/Users/.../`)
- Temp directory paths (`/dev/shm/`, `/var/tmp/regtest/`, `regtest/`)
- GitHub Actions temp paths
- The first 3 lines of dvdisaster output (version/license) via `tail -n +4`

```python
# append to tests/test_framework.py
from framework import clean_output


class TestOutputCleaning:
    def test_strips_memory_leak_line(self):
        raw = "some output\ndvdisaster: No memory leaks found.\nmore output\n"
        assert clean_output(raw) == "some output\nmore output\n"

    def test_strips_temp_paths(self):
        raw = "Opening /dev/shm/rs01-tmp.iso: 21000 sectors.\n"
        assert clean_output(raw, tmp_dirs=["/dev/shm"]) == "Opening rs01-tmp.iso: 21000 sectors.\n"

    def test_strips_isodir_paths(self):
        raw = "Opening /var/tmp/regtest/rs01-master.iso: 21000 sectors.\n"
        assert clean_output(raw, tmp_dirs=["/var/tmp/regtest"]) == "Opening rs01-master.iso: 21000 sectors.\n"

    def test_strips_regtest_prefix(self):
        raw = "Opening regtest/no.iso: file not found.\n"
        assert clean_output(raw) == "Opening no.iso: file not found.\n"

    def test_strips_windows_paths(self):
        raw = "Opening C:/Users/runner/AppData/Local/Temp/rs01-tmp.iso\n"
        assert clean_output(raw) == "Opening rs01-tmp.iso\n"

    def test_strips_version_header(self):
        raw = (
            "dvdisaster-0.79.10 (development)\n"
            "Copyright blah\n"
            "More copyright\n"
            "This software comes with  ABSOLUTELY NO WARRANTY.\n"
            "Actual output starts here.\n"
        )
        # First 3 lines are stripped (tail -n +4)
        result = clean_output(raw, strip_header=True)
        assert "dvdisaster-0.79.10" not in result
        assert "This software comes with" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_framework.py::TestOutputCleaning -v`
Expected: FAIL — `clean_output` not defined

- [ ] **Step 3: Implement output cleaning**

```python
# append to tests/framework.py

def clean_output(text: str, tmp_dirs: Optional[List[str]] = None,
                 strip_header: bool = False) -> str:
    """Clean dvdisaster output to match golden file format.

    Mirrors the filtering in regtest/common.bash run_regtest().
    """
    lines = text.splitlines(keepends=True)

    # Strip first 3 lines (version/copyright header) — bash does `tail -n +4`
    if strip_header and len(lines) >= 3:
        lines = lines[3:]

    text = "".join(lines)

    # Remove memory leak line
    text = re.sub(r'^dvdisaster: No memory leaks found\.\n', '', text, flags=re.MULTILINE)

    # Strip Windows drive-letter paths: C:/foo/bar/ → empty
    text = re.sub(r'[A-Z]:/[A-Za-z0-9_/-]+/', '', text)

    # Strip GitHub Actions temp paths
    text = re.sub(r'[-A-Za-z0-9_~]+/AppData/Local/Temp/', '', text)

    # Strip specific temp directories
    if tmp_dirs:
        for d in tmp_dirs:
            # Normalize: ensure trailing slash is handled
            d_escaped = re.escape(d.rstrip("/"))
            text = re.sub(d_escaped + r'/*', '', text)

    # Strip regtest/ prefix
    text = re.sub(r'regtest/', '', text)

    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_framework.py::TestOutputCleaning -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/framework.py tests/test_framework.py
git commit -m "test: add output cleaning for golden file comparison"
```

---

### Task 4: GoldenTest and SimCD Dataclasses

**Files:**
- Modify: `tests/framework.py`
- Modify: `tests/test_framework.py`

- [ ] **Step 1: Write tests for GoldenTest construction**

```python
# append to tests/test_framework.py
from framework import GoldenTest, SimCD, CreateECC


class TestGoldenTestDataclass:
    def test_simple_verify_test(self):
        t = GoldenTest("good", action="-t", use_master=True)
        assert t.name == "good"
        assert t.action == "-t"
        assert t.use_master is True
        assert t.damage is None
        assert t.sim_cd is None

    def test_test_with_damage(self):
        t = GoldenTest("data_bad_byte", action="-t",
                       damage=[Byteset(4096, 100, 17)])
        assert len(t.damage) == 1
        assert t.damage[0].cli_args() == ["--byteset", "4096,100,17"]

    def test_reading_test_with_sim_cd(self):
        t = GoldenTest("read_good", action="-r",
                       sim_cd=SimCD(damage=[Erase("100-200")]))
        assert t.sim_cd is not None
        assert len(t.sim_cd.damage) == 1

    def test_creation_test(self):
        t = GoldenTest("ecc_create", action="-c",
                       create_ecc=CreateECC(redundancy="normal"))
        assert t.create_ecc.redundancy == "normal"

    def test_sim_cd_defaults(self):
        s = SimCD()
        assert s.source == "master"
        assert s.damage is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_framework.py::TestGoldenTestDataclass -v`
Expected: FAIL — `GoldenTest`, `SimCD`, `CreateECC` not defined

- [ ] **Step 3: Implement the dataclasses**

```python
# append to tests/framework.py

@dataclass
class SimCD:
    """Configuration for simulated CD reading."""
    source: str = "master"  # base image to copy ("master" or a path)
    damage: Optional[List] = None  # damage ops to apply to sim image


@dataclass
class CreateECC:
    """Configuration for ECC creation."""
    method: Optional[str] = None       # e.g., "RS03"
    redundancy: Optional[str] = None   # e.g., "normal", "20r"
    output: Optional[str] = None       # e.g., "file"
    ecc_size: Optional[int] = None     # -n <sectors>


@dataclass
class GoldenTest:
    """Declarative definition of a single regression test."""
    name: str
    action: str                                  # dvdisaster flags: "-t", "-r", "-c", "-f"
    damage: Optional[List] = None                # damage ops on the test image
    use_master: bool = False                     # use master image directly (read-only)
    image: Optional[str] = None                  # override image path (e.g., "no.iso")
    ecc: Optional[str] = None                    # ecc file ("master_ecc", path, or None)
    sim_cd: Optional[SimCD] = None               # sim-cd config for reading tests
    create_ecc: Optional[CreateECC] = None       # ecc creation config
    extra_args: Optional[List[str]] = None       # additional CLI args
    ecc_damage: Optional[List] = None            # damage ops on the ecc file
    chmod_image: Optional[int] = None            # chmod on image (e.g., 0o000)
    chmod_ecc: Optional[int] = None              # chmod on ecc file (e.g., 0o000)
    skip_on_windows: bool = False                # skip on Windows (chmod tests)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_framework.py::TestGoldenTestDataclass -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/framework.py tests/test_framework.py
git commit -m "test: add GoldenTest, SimCD, CreateECC dataclasses"
```

---

### Task 5: GoldenTestSuite Runner

This is the core: the base class that converts `GoldenTest` entries into parametrized pytest methods and runs them.

**Files:**
- Modify: `tests/framework.py`
- Create: `tests/test_rs01_verify_smoke.py` (small smoke test with 3 real tests)

- [ ] **Step 1: Write a smoke test using 3 real RS01 verify tests**

These tests use real golden files from `regtest/database/` and the real dvdisaster binary.

```python
# tests/test_rs01_verify_smoke.py
"""Smoke test: verify the framework works with real golden files."""

from framework import GoldenTest, GoldenTestSuite, Erase, Byteset


class TestRS01VerifySmoke(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    tests = [
        # Simplest test: verify good image + ecc
        GoldenTest("good", action="-t", use_master=True, ecc="master_ecc"),
        # Verify with missing image
        GoldenTest("no_image", action="-t",
                   image="no.iso", ecc="master_ecc"),
        # Verify with CRC error
        GoldenTest("crc_errors_with_ecc", action="-t",
                   damage=[Byteset(13444, 0, 154)], ecc="master_ecc"),
    ]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_rs01_verify_smoke.py -v`
Expected: FAIL — `GoldenTestSuite` not implemented

- [ ] **Step 3: Implement GoldenTestSuite**

```python
# append to tests/framework.py
import shutil
import pytest

# Project root: two levels up if framework.py is in tests/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DVDISASTER = os.path.join(_PROJECT_ROOT, "dvdisaster")
_GOLDEN_DB = os.path.join(_PROJECT_ROOT, "regtest", "database")
_ISODIR = "/var/tmp/regtest"


def _find_binary():
    """Find the dvdisaster binary."""
    for candidate in [_DVDISASTER, _DVDISASTER + ".exe"]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _run_dvdisaster(binary, *args):
    """Run dvdisaster, return (returncode, output_text)."""
    cmd = [binary] + list(args)
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300,
    )
    text = result.stdout.decode("utf-8", errors="replace")
    return result.returncode, text


def _md5_file(path):
    """Compute MD5 hex digest of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _apply_damage(binary, image_path, ops):
    """Apply a list of damage operations to an image."""
    for op in ops:
        if isinstance(op, (Erase, Byteset, Truncate)):
            _run_dvdisaster(binary, "--debug", f"-i{image_path}", *op.cli_args())
        elif isinstance(op, PadBytes):
            with open(image_path, "ab") as f:
                f.write(b"\x00" * op.pad_size)
        elif isinstance(op, PadSectors):
            with open(image_path, "ab") as f:
                f.write(b"\x00" * op.pad_size)
        else:
            raise ValueError(f"Unknown damage op: {op}")


class GoldenTestSuite:
    """Base class for declarative golden-file test suites.

    Subclasses define class-level attributes:
      codec, codec_prefix, master, master_ecc, image_size, redundancy, tests

    The __init_subclass__ hook converts each GoldenTest in `tests` into a
    parametrized test_golden() method.
    """

    codec: str = ""
    codec_prefix: str = ""
    master: str = ""
    master_ecc: Optional[str] = None
    image_size: int = 21000
    redundancy: Optional[str] = None
    tests: List[GoldenTest] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.tests:
            return

        # Build parametrize IDs and argvalues
        test_entries = list(cls.tests)

        @pytest.fixture
        def dvdisaster_bin(self):
            binary = _find_binary()
            if binary is None:
                pytest.skip("dvdisaster binary not found")
            return binary

        # We use pytest_generate_tests instead of parametrize decorator
        # because we need the test list from the class
        cls._golden_tests = test_entries

    @pytest.fixture(autouse=True)
    def _setup_binary(self):
        binary = _find_binary()
        if binary is None:
            pytest.skip("dvdisaster binary not found")
        self._binary = binary

    @pytest.fixture(autouse=True)
    def _setup_workdir(self, tmp_path):
        self._work_dir = tmp_path

    def _ensure_master(self):
        """Ensure master image exists in ISODIR (created once, cached)."""
        master_path = os.path.join(_ISODIR, self.master)
        if not os.path.isfile(master_path):
            os.makedirs(_ISODIR, exist_ok=True)
            _run_dvdisaster(
                self._binary, "--regtest", "--debug",
                f"-i{master_path}", "--random-image", str(self.image_size),
            )
        return master_path

    def _ensure_master_ecc(self):
        """Ensure master ECC file exists in ISODIR."""
        if not self.master_ecc:
            return None
        ecc_path = os.path.join(_ISODIR, self.master_ecc)
        if not os.path.isfile(ecc_path):
            master_path = self._ensure_master()
            args = [
                "--regtest", "--debug", "--set-version", "0.80",
                f"-i{master_path}", f"-e{ecc_path}", "-c",
            ]
            if self.redundancy:
                args.extend(["-n", self.redundancy])
            _run_dvdisaster(self._binary, *args)
        return ecc_path

    def _resolve_image(self, test: GoldenTest):
        """Resolve the image path for a test. Returns (path, is_temp)."""
        if test.image:
            # Literal path like "no.iso" — use ISODIR
            return os.path.join(_ISODIR, test.image), False
        if test.use_master:
            return self._ensure_master(), False
        # Copy master to work dir
        master = self._ensure_master()
        tmp_iso = os.path.join(str(self._work_dir), os.path.basename(self.master).replace("master", "tmp"))
        shutil.copy2(master, tmp_iso)
        return tmp_iso, True

    def _resolve_ecc(self, test: GoldenTest):
        """Resolve the ECC file path for a test."""
        if test.ecc == "master_ecc":
            return self._ensure_master_ecc()
        if test.ecc:
            # Check if it's a literal path that should exist (like "no.ecc")
            ecc_path = os.path.join(_ISODIR, test.ecc)
            return ecc_path
        return None

    def _run_golden_test(self, test: GoldenTest):
        """Execute a single GoldenTest and assert results."""
        # Skip chmod tests on Windows (chmod doesn't work properly)
        if (test.chmod_image is not None or test.chmod_ecc is not None):
            if os.name == "nt" or os.environ.get("OS", "").startswith("Windows"):
                pytest.skip("chmod tests not supported on Windows")

        image_path, is_temp = self._resolve_image(test)
        ecc_path = self._resolve_ecc(test)

        # Apply damage to image
        if test.damage and is_temp:
            _apply_damage(self._binary, image_path, test.damage)

        # Apply damage to ECC file (copy first if needed)
        if test.ecc_damage:
            if ecc_path and os.path.isfile(ecc_path):
                tmp_ecc = os.path.join(str(self._work_dir), "tmp.ecc")
                shutil.copy2(ecc_path, tmp_ecc)
                ecc_path = tmp_ecc
                _apply_damage(self._binary, ecc_path, test.ecc_damage)

        # Apply chmod
        if test.chmod_image is not None and is_temp:
            os.chmod(image_path, test.chmod_image)
        if test.chmod_ecc is not None and ecc_path:
            # May need to copy ecc first
            if ecc_path == self._ensure_master_ecc():
                tmp_ecc = os.path.join(str(self._work_dir), "tmp.ecc")
                shutil.copy2(ecc_path, tmp_ecc)
                ecc_path = tmp_ecc
            os.chmod(ecc_path, test.chmod_ecc)

        # Handle ECC creation tests
        if test.create_ecc:
            ecc_path = os.path.join(str(self._work_dir), "tmp.ecc")
            # create_ecc args are part of the action

        # Build command
        args = ["--regtest", "--no-progress"]
        args.append(f"-i{image_path}")
        if ecc_path:
            args.append(f"-e{ecc_path}")

        # Handle sim-cd
        sim_iso = None
        if test.sim_cd:
            if test.sim_cd.source == "master":
                src = self._ensure_master()
            else:
                src = os.path.join(_ISODIR, test.sim_cd.source)
            sim_iso = os.path.join(str(self._work_dir), "sim.iso")
            shutil.copy2(src, sim_iso)
            if test.sim_cd.damage:
                _apply_damage(self._binary, sim_iso, test.sim_cd.damage)
            args.extend([
                "--debug",
                f"--sim-cd={sim_iso}",
                "--fixed-speed-values",
                "--spinup-delay=0",
            ])

        # Handle create_ecc
        if test.create_ecc:
            ce = test.create_ecc
            args.extend(["--debug", "--set-version", "0.80"])
            if ce.method:
                args.append(f"-m{ce.method}")
            if ce.redundancy:
                args.extend(["-n", ce.redundancy])
            if ce.output:
                args.extend(["-o", ce.output])
            if ce.ecc_size:
                args.extend(["-n", str(ce.ecc_size)])

        # Add action
        args.extend(test.action.split())

        # Add extra args
        if test.extra_args:
            args.extend(test.extra_args)

        # Run dvdisaster
        returncode, output = _run_dvdisaster(self._binary, *args)

        # Clean output
        tmp_dirs = [str(self._work_dir), _ISODIR, "/dev/shm", "/var/tmp"]
        cleaned = clean_output(output, tmp_dirs=tmp_dirs, strip_header=True)

        # Load golden file
        golden_base = os.path.join(_GOLDEN_DB, f"{self.codec_prefix}_{test.name}")
        if not os.path.isfile(golden_base):
            # Check without platform suffix
            pytest.fail(f"Golden file not found: {golden_base}")

        golden = parse_golden_file(golden_base)

        # Compare output
        # The golden file includes the license header (lines 3+),
        # while our cleaned output has the first 3 lines stripped.
        # So we need to compare cleaned output against golden.expected_output
        # which starts at line 3 of the golden file (after MD5 lines).
        assert cleaned == golden.expected_output, (
            f"Output mismatch for {self.codec_prefix}_{test.name}:\n"
            f"--- expected\n+++ actual\n"
            + _unified_diff(golden.expected_output, cleaned)
        )

        # Check MD5 sums
        if golden.image_md5 and os.path.isfile(image_path):
            actual_md5 = _md5_file(image_path)
            assert actual_md5 == golden.image_md5, (
                f"Image MD5 mismatch: expected {golden.image_md5}, got {actual_md5}"
            )
        if golden.ecc_md5 and ecc_path and os.path.isfile(ecc_path):
            actual_md5 = _md5_file(ecc_path)
            assert actual_md5 == golden.ecc_md5, (
                f"ECC MD5 mismatch: expected {golden.ecc_md5}, got {actual_md5}"
            )

        # Clean up chmod'd files so pytest can remove tmp_path
        if test.chmod_image is not None and is_temp:
            try:
                os.chmod(image_path, 0o644)
            except OSError:
                pass
        if test.chmod_ecc is not None and ecc_path:
            try:
                os.chmod(ecc_path, 0o644)
            except OSError:
                pass


def _unified_diff(expected: str, actual: str) -> str:
    """Generate a unified diff between two strings."""
    import difflib
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    diff = difflib.unified_diff(expected_lines, actual_lines,
                                fromfile="expected", tofile="actual",
                                lineterm="")
    return "".join(diff)


def pytest_generate_tests(metafunc):
    """Hook: parametrize test_golden from the class's tests list."""
    if metafunc.function.__name__ == "test_golden":
        cls = metafunc.cls
        if cls and hasattr(cls, "_golden_tests") and cls._golden_tests:
            ids = [t.name for t in cls._golden_tests]
            metafunc.parametrize("golden_test", cls._golden_tests, ids=ids)
```

And add `test_golden` as a method on `GoldenTestSuite`:

```python
# Add this method to GoldenTestSuite class:

    def test_golden(self, golden_test):
        """Parametrized test method — one call per GoldenTest entry."""
        self._run_golden_test(golden_test)
```

- [ ] **Step 4: Run smoke tests to verify they pass**

Run: `python3 -m pytest tests/test_rs01_verify_smoke.py -v`
Expected: 3 tests PASS (good, no_image, crc_errors_with_ecc)

- [ ] **Step 5: Debug and fix output comparison issues**

The golden file format needs careful alignment with output cleaning. The bash framework:
1. Runs dvdisaster with `tail -n +4` equivalent (strips 3-line version header)
2. Removes `dvdisaster: No memory leaks found.`
3. Strips temp paths
4. Compares against golden file lines 3+ (after the 2 MD5 lines)

Iterate on `clean_output` and `parse_golden_file` until the smoke tests pass. Adjust path stripping, header line counts, and trailing newlines.

- [ ] **Step 6: Commit**

```bash
git add tests/framework.py tests/test_rs01_verify_smoke.py
git commit -m "test: implement GoldenTestSuite runner with parametrized tests"
```

---

### Task 6: Conftest Integration

The `pytest_generate_tests` hook in `framework.py` won't be auto-discovered by pytest. It needs to be in `conftest.py` or a plugin.

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add the hook import to conftest.py**

```python
# append to tests/conftest.py

# Import the pytest_generate_tests hook so pytest discovers it
from framework import pytest_generate_tests  # noqa: F401
```

- [ ] **Step 2: Verify the smoke test still passes with the hook in conftest**

Run: `python3 -m pytest tests/test_rs01_verify_smoke.py -v`
Expected: 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: wire up pytest_generate_tests hook in conftest"
```

---

### Task 7: Migrate RS01 Verify Tests

Migrate all 28 verify tests from `regtest/rs01.bash` to the framework.

**Files:**
- Create: `tests/test_rs01.py`
- Delete: `tests/test_rs01_verify_smoke.py` (merged into test_rs01.py)

**Notes on special cases:**
- `plus56_bytes` / `image_plus56_bytes` / `ecc_plus56_bytes` / etc. need a pre-built `rs01-plus56_bytes.iso` and `.ecc`. These are setup images created in the bash preamble. The Python framework should create them in a session-scoped fixture.
- `image_few_bytes_shorter` / `image_few_bytes_longer` use `dd` to add padding — use `PadBytes`.
- `truncated_by_bytes` uses `dd` to create a partial copy — use a custom `TruncateToBytes` damage op or handle inline.
- `uncorrectable_dsm_in_image*` tests have complex multi-step erase+byteset sequences.

- [ ] **Step 1: Add session-scoped fixtures for plus56 images**

```python
# tests/test_rs01.py
"""RS01 regression tests — migrated from regtest/rs01.bash."""

import os
import shutil

import pytest

from framework import (
    Byteset,
    CreateECC,
    Erase,
    GoldenTest,
    GoldenTestSuite,
    PadBytes,
    PadSectors,
    SimCD,
    Truncate,
    _ISODIR,
    _find_binary,
    _run_dvdisaster,
)


@pytest.fixture(scope="session")
def rs01_plus56_images():
    """Create the plus-56-bytes image and its ECC file (cached in ISODIR)."""
    binary = _find_binary()
    if binary is None:
        pytest.skip("dvdisaster binary not found")

    iso_path = os.path.join(_ISODIR, "rs01-plus56_bytes.iso")
    ecc_path = os.path.join(_ISODIR, "rs01-plus56_bytes.ecc")
    master_path = os.path.join(_ISODIR, "rs01-master.iso")

    if not os.path.isfile(iso_path):
        # Ensure master exists
        if not os.path.isfile(master_path):
            os.makedirs(_ISODIR, exist_ok=True)
            _run_dvdisaster(binary, "--regtest", "--debug",
                            f"-i{master_path}", "--random-image", "21000")
        shutil.copy2(master_path, iso_path)
        with open(iso_path, "ab") as f:
            f.write(b"\x00" * 56)

    if not os.path.isfile(ecc_path):
        _run_dvdisaster(binary, "--regtest", "--debug", "--set-version", "0.80",
                        f"-i{iso_path}", f"-e{ecc_path}", "-c", "-n", "normal")

    return iso_path, ecc_path
```

- [ ] **Step 2: Define all 28 verify tests**

```python
class TestRS01Verify(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    tests = [
        GoldenTest("good", action="-t", use_master=True, ecc="master_ecc"),
        GoldenTest("good_quick", action="-tq", use_master=True, ecc="master_ecc"),
        GoldenTest("no_files", action="-t", image="no.iso", ecc="no.ecc"),
        GoldenTest("no_image", action="-t", image="no.iso", ecc="master_ecc"),
        GoldenTest("no_ecc", action="-t", use_master=True, ecc="no.ecc"),
        GoldenTest("defective_image_no_ecc", action="-t",
                   damage=[Erase("1000-1049"), Erase("11230"), Erase("12450-12457"),
                           Byteset(13444, 0, 154)],
                   ecc="no.ecc"),
        # plus56 tests need special image — handled via extra_args or custom fixture
        # These will be added as plain methods below
        GoldenTest("defective_with_ecc", action="-t",
                   damage=[Erase("1000-1049"), Erase("11230"), Erase("12450-12457"),
                           Byteset(13444, 0, 154)],
                   ecc="master_ecc"),
        GoldenTest("missing_sectors_with_ecc", action="-t",
                   damage=[Erase("1000-1049"), Erase("11230"), Erase("12450-12457")],
                   ecc="master_ecc"),
        GoldenTest("crc_errors_with_ecc", action="-t",
                   damage=[Byteset(13444, 0, 154)],
                   ecc="master_ecc"),
        GoldenTest("crc_in_fingerprint", action="-t",
                   damage=[Byteset(16, 201, 55)],
                   ecc="master_ecc"),
        GoldenTest("missing_fingerprint", action="-t",
                   damage=[Erase("16")],
                   ecc="master_ecc"),
        GoldenTest("missing_ecc_header", action="-t",
                   use_master=True,
                   ecc="master_ecc",
                   ecc_damage=[Erase("0")]),
        GoldenTest("ecc_header_crc_error", action="-t",
                   use_master=True,
                   ecc="master_ecc",
                   ecc_damage=[Byteset(0, 22, 107)]),
        GoldenTest("truncated", action="-t",
                   damage=[Truncate(21000 - 5)],
                   ecc="master_ecc"),
        GoldenTest("uncorrectable_dsm_in_image", action="-t",
                   damage=[Erase("3030"), Byteset(3030, 353, 49),
                           Erase("4400"), Byteset(4400, 353, 53),
                           Erase("4411"), Byteset(4411, 353, 53)],
                   ecc="master_ecc"),
        GoldenTest("uncorrectable_dsm_in_image_verbose", action="-t -v",
                   damage=[Erase("3030"), Byteset(3030, 353, 49),
                           Erase("4400"), Byteset(4400, 353, 53),
                           Erase("4411"), Byteset(4411, 353, 53)],
                   ecc="master_ecc"),
        GoldenTest("uncorrectable_dsm_in_image2", action="-t",
                   damage=[Erase("3030"), Byteset(3030, 416, 55),
                           Byteset(3030, 556, 32), Byteset(3030, 557, 50),
                           Erase("4400"), Byteset(4400, 416, 53),
                           Byteset(4400, 556, 32), Byteset(4400, 557, 50),
                           Erase("4411"), Byteset(4411, 416, 53),
                           Byteset(4411, 556, 32), Byteset(4411, 557, 50)],
                   ecc="master_ecc"),
        GoldenTest("uncorrectable_dsm_in_image2_verbose", action="-t -v",
                   damage=[Erase("3030"), Byteset(3030, 416, 55),
                           Byteset(3030, 556, 32), Byteset(3030, 557, 50),
                           Erase("4400"), Byteset(4400, 416, 53),
                           Byteset(4400, 556, 32), Byteset(4400, 557, 50),
                           Erase("4411"), Byteset(4411, 416, 53),
                           Byteset(4411, 556, 32), Byteset(4411, 557, 50)],
                   ecc="master_ecc"),
    ]
```

- [ ] **Step 3: Add plus56 and padding tests as plain methods**

These tests use pre-built images that differ from master. They are better expressed as methods with the `rs01_plus56_images` fixture.

```python
    # Plain methods for tests needing the plus56 image
    def test_plus56_bytes(self, rs01_plus56_images):
        iso, ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "plus56_bytes", action="-t", image=iso, ecc=ecc,
            use_master=False,
        ))

    def test_image_plus56_bytes(self, rs01_plus56_images):
        iso, _ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "image_plus56_bytes", action="-t", image=iso, ecc="no.ecc",
            use_master=False,
        ))

    def test_ecc_plus56_bytes(self, rs01_plus56_images):
        _iso, ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "ecc_plus56_bytes", action="-t", image="no.iso", ecc=ecc,
            use_master=False,
        ))

    def test_normal_image_ecc_plus56b(self, rs01_plus56_images):
        _iso, ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "normal_image_ecc_plus56b", action="-t",
            use_master=True, ecc=ecc,
        ))

    def test_image_plus56b_normal_ecc(self, rs01_plus56_images):
        iso, _ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "image_plus56b_normal_ecc", action="-t",
            image=iso, ecc="master_ecc",
        ))

    def test_image_few_bytes_shorter(self, rs01_plus56_images):
        _iso, ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "image_few_bytes_shorter", action="-t",
            damage=[PadBytes(55)], ecc=ecc,
        ))

    def test_image_few_bytes_longer(self, rs01_plus56_images):
        _iso, ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "image_few_bytes_longer", action="-t",
            damage=[PadBytes(57)], ecc=ecc,
        ))

    def test_truncated_by_bytes(self):
        """Image truncated by 7 bytes (not sector-aligned)."""
        # This test uses dd to create a partial copy — handle inline
        master = self._ensure_master()
        tmp_iso = os.path.join(str(self._work_dir), "rs01-tmp.iso")
        # Copy all but last 7 bytes
        total = 2048 * 21000 - 7
        with open(master, "rb") as src, open(tmp_iso, "wb") as dst:
            dst.write(src.read(total))
        ecc = self._ensure_master_ecc()
        self._run_golden_test(GoldenTest(
            "truncated_by_bytes", action="-t", image=tmp_iso, ecc=ecc,
            use_master=False,
        ))

    def test_plus1(self):
        self._run_golden_test(GoldenTest(
            "plus1", action="-t",
            damage=[PadSectors(1)], ecc="master_ecc",
        ))

    def test_plus17(self):
        self._run_golden_test(GoldenTest(
            "plus17", action="-t",
            damage=[PadSectors(17)], ecc="master_ecc",
        ))
```

- [ ] **Step 4: Run all verify tests**

Run: `python3 -m pytest tests/test_rs01.py::TestRS01Verify -v`
Expected: All 28 tests PASS

- [ ] **Step 5: Fix any output comparison issues**

Iterate on path stripping and golden file line alignment until all tests pass. Common issues:
- Trailing newline differences
- Path components not fully stripped
- `TEST_TMPDIR` subpath appearing in output

- [ ] **Step 6: Remove smoke test file**

```bash
rm tests/test_rs01_verify_smoke.py
```

- [ ] **Step 7: Commit**

```bash
git add tests/test_rs01.py
git rm tests/test_rs01_verify_smoke.py
git commit -m "test: migrate all 28 RS01 verify tests to Python framework"
```

---

### Task 8: Migrate RS01 Creation Tests

**Files:**
- Modify: `tests/test_rs01.py`

There are 12 creation tests. Several use `extra_args="--debug --set-version $SETVERSION"` and sim-cd for "read and create" tests.

- [ ] **Step 1: Define creation tests**

```python
class TestRS01Create(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    tests = [
        GoldenTest("ecc_create", action="-c -n normal",
                   use_master=True,
                   extra_args=["--debug", "--set-version", "0.80"],
                   ecc="tmp_ecc"),
        GoldenTest("ecc_missing_image", action="-c -n normal",
                   image="none.iso", ecc="tmp_ecc"),
        GoldenTest("ecc_no_read_perm", action="-c -n normal",
                   chmod_image=0o000, ecc="tmp_ecc"),
        GoldenTest("ecc_no_write_perm", action="-c -n normal",
                   use_master=True,
                   extra_args=["--debug", "--set-version", "0.80"],
                   ecc="tmp_ecc", chmod_ecc=0o400),
        GoldenTest("ecc_missing_sectors", action="-c -n normal",
                   damage=[Erase("1000-1049"), Erase("11230"), Erase("12450-12457")],
                   ecc="tmp_ecc"),
    ]
```

- [ ] **Step 2: Add plus56 creation and read-and-create tests as methods**

The `ecc_create_plus56` test needs the plus56 image. The `ecc_create_after_read` and `ecc_recreate_after_read_*` tests use sim-cd with `--set-version` — these are reading-then-creating tests.

```python
    def test_ecc_create_plus56(self, rs01_plus56_images):
        iso, _ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "ecc_create_plus56", action="-c -n normal",
            image=iso, ecc="tmp_ecc", use_master=False,
            extra_args=["--debug", "--set-version", "0.80"],
        ))

    def test_ecc_create_after_read(self):
        self._run_golden_test(GoldenTest(
            "ecc_create_after_read", action="-r -c -n normal --spinup-delay=0 -v",
            sim_cd=SimCD(source="master"),
            ecc="tmp_ecc",
            extra_args=["--debug", "--set-version", "0.80"],
        ))

    # ... similar for ecc_recreate_after_read_rs01, rs02, rs03i, rs03f,
    # ecc_create_after_partial_read — each with their specific setup
```

- [ ] **Step 3: Run creation tests**

Run: `python3 -m pytest tests/test_rs01.py::TestRS01Create -v`
Expected: All creation tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_rs01.py
git commit -m "test: migrate RS01 creation tests to Python framework"
```

---

### Task 9: Migrate RS01 Repair Tests

**Files:**
- Modify: `tests/test_rs01.py`

18 repair tests: fix_good, fix_no_read_perm, fix_missing_sectors, fix_crc_errors, fix_additional_sector, fix_plus17, fix_truncated, and the plus56 variants.

- [ ] **Step 1: Define repair tests**

```python
class TestRS01Repair(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    tests = [
        GoldenTest("fix_good", action="-f", ecc="master_ecc"),
        GoldenTest("fix_no_read_perm", action="-f",
                   chmod_image=0o000, ecc="master_ecc"),
        GoldenTest("fix_no_read_perm_ecc", action="-f",
                   ecc="master_ecc", chmod_ecc=0o000),
        GoldenTest("fix_no_write_perm", action="-f",
                   chmod_image=0o400, ecc="master_ecc"),
        GoldenTest("fix_missing_sectors", action="-f",
                   damage=[Erase("0"), Erase("190"), Erase("192"),
                           Erase("590-649"), Erase("2000-2139"),
                           Erase("2141-2176"), Erase("20999")],
                   ecc="master_ecc"),
        GoldenTest("fix_crc_errors", action="-f",
                   damage=[Byteset(0, 1, 1), Byteset(190, 200, 143),
                           Byteset(1200, 100, 1), Byteset(1201, 100, 1),
                           Byteset(20999, 500, 91)],
                   ecc="master_ecc"),
        GoldenTest("fix_additional_sector", action="-f",
                   damage=[PadSectors(1)], ecc="master_ecc"),
        GoldenTest("fix_plus17", action="-f",
                   damage=[PadSectors(17)], ecc="master_ecc"),
        GoldenTest("fix_plus17_truncate", action="-f --truncate",
                   damage=[PadSectors(17)], ecc="master_ecc"),
        GoldenTest("fix_truncated", action="-f",
                   damage=[Truncate(20731)], ecc="master_ecc"),
    ]
```

- [ ] **Step 2: Add plus56 repair tests as methods**

```python
    def test_fix_plus56_bytes(self, rs01_plus56_images):
        iso, ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "fix_plus56_bytes", action="-f", image=iso, ecc=ecc,
            use_master=False,
        ))

    def test_fix_plus56(self, rs01_plus56_images):
        iso, ecc = rs01_plus56_images
        self._run_golden_test(GoldenTest(
            "fix_plus56", action="-f",
            image=iso, ecc=ecc,
            damage=[Byteset(21000, 28, 90)],
            use_master=False,
        ))

    # ... similar for fix_plus56_plus17, fix_plus56_plus1s,
    # fix_plus56_plus2s, fix_plus56_plus17500,
    # fix_plus56_truncated, fix_plus56_little_truncated
```

- [ ] **Step 3: Run repair tests**

Run: `python3 -m pytest tests/test_rs01.py::TestRS01Repair -v`
Expected: All 18 tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_rs01.py
git commit -m "test: migrate RS01 repair tests to Python framework"
```

---

### Task 10: Migrate RS01 Scanning Tests

**Files:**
- Modify: `tests/test_rs01.py`

22 scanning tests. Most use `extra_args="--debug --sim-cd=... --fixed-speed-values"` and scan to `$ISODIR/no.iso` / `$ISODIR/no.ecc`.

- [ ] **Step 1: Define scanning tests**

The scanning tests use `sim_cd` for the disc simulation and write to a non-existent image path.

```python
class TestRS01Scan(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    tests = [
        GoldenTest("scan_no_ecc", action="-s",
                   sim_cd=SimCD(source="master"),
                   image="no.iso", ecc="no.ecc"),
        GoldenTest("scan_with_ecc", action="-s",
                   sim_cd=SimCD(source="master"),
                   image="no.iso", ecc="master_ecc"),
        GoldenTest("scan_defective_no_ecc", action="-s",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("100-200"), Erase("766"), Erase("2410")]),
                   image="no.iso", ecc="no.ecc"),
        GoldenTest("scan_defective_no_ecc_again", action="-s -j 1",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("100-200"), Erase("766"), Erase("2410")]),
                   image="no.iso", ecc="no.ecc"),
        GoldenTest("scan_defective_large_skip", action="-s -j 256",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("1600-1615"), Erase("6400-10000")]),
                   image="no.iso", ecc="no.ecc"),
        GoldenTest("scan_crc_errors_with_ecc", action="-s",
                   sim_cd=SimCD(source="master",
                                damage=[Byteset(0, 100, 255), Byteset(1, 180, 200),
                                        Byteset(7910, 23, 98), Byteset(20999, 55, 123)]),
                   image="no.iso", ecc="master_ecc"),
        GoldenTest("scan_with_hardware_failure", action="-s",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("5000:hardware failure"),
                                        Erase("6000:hardware failure")]),
                   image="no.iso", ecc="no.ecc"),
        GoldenTest("scan_with_ignored_hardware_failure", action="-s --ignore-fatal-sense",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("5000:hardware failure")]),
                   image="no.iso", ecc="no.ecc"),
        GoldenTest("scan_medium_with_dsm", action="-s",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("4999:pass as dead sector marker"),
                                        Erase("5799:pass as dead sector marker")]),
                   image="no.iso", ecc="no.ecc"),
        # ... remaining scan tests (shorter, longer, tao_tail, etc.)
    ]
```

- [ ] **Step 2: Add device-error and range scan tests as methods**

Tests like `scan_no_device`, `scan_no_device_access`, and `scan_new_with_range_no_ecc` use non-standard flags (`-d /dev/sdz`, `-s10000-15000`) that don't fit the sim_cd pattern cleanly.

```python
    def test_scan_no_device(self):
        """Scan from non-existent device."""
        non_existent = "/dev/sdz"
        if os.name == "nt":
            non_existent = "V:"
        # This test passes all args through extra_args
        self._run_golden_test(GoldenTest(
            "scan_no_device", action="-s",
            sim_cd=SimCD(source="master"),
            image="no.iso", ecc="no.ecc",
            extra_args=["-d", non_existent],
        ))
```

- [ ] **Step 3: Run scanning tests**

Run: `python3 -m pytest tests/test_rs01.py::TestRS01Scan -v`
Expected: All 22 tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_rs01.py
git commit -m "test: migrate RS01 scanning tests to Python framework"
```

---

### Task 11: Migrate RS01 Linear Reading Tests

**Files:**
- Modify: `tests/test_rs01.py`

39 linear reading tests. These all use sim-cd and write to a tmp image. Some have complex multi-step setups (multipass, DSM markers).

- [ ] **Step 1: Define linear reading tests**

```python
class TestRS01ReadLinear(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    tests = [
        GoldenTest("read_no_ecc", action="-r",
                   sim_cd=SimCD(source="master"),
                   ecc="no.ecc"),
        GoldenTest("read_with_ecc", action="-r",
                   sim_cd=SimCD(source="master"),
                   ecc="master_ecc"),
        GoldenTest("read_defective_no_ecc", action="-r",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("100-200"), Erase("766"), Erase("2410")]),
                   ecc="no.ecc"),
        # ... all other linear reading tests
    ]
```

- [ ] **Step 2: Add multipass and DSM tests as semantic methods**

The `read_multipass_ecc_partial_success` test is already in `test_multipass_read.py`. The DSM tests have complex setup but stable output — use `_run_golden_test` with inline damage lists.

- [ ] **Step 3: Run reading tests**

Run: `python3 -m pytest tests/test_rs01.py::TestRS01ReadLinear -v`
Expected: All 39 tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_rs01.py
git commit -m "test: migrate RS01 linear reading tests to Python framework"
```

---

### Task 12: Migrate RS01 Adaptive Reading Tests

**Files:**
- Modify: `tests/test_rs01.py`

25 adaptive reading tests. Similar to linear but with `--adaptive-read`.

- [ ] **Step 1: Define adaptive reading tests**

```python
class TestRS01ReadAdaptive(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    tests = [
        GoldenTest("adaptive_good", action="-r --adaptive-read",
                   sim_cd=SimCD(source="master"),
                   ecc="master_ecc"),
        GoldenTest("adaptive_no_ecc", action="-r --adaptive-read",
                   sim_cd=SimCD(source="master"),
                   ecc="no.ecc"),
        GoldenTest("adaptive_defective_no_ecc", action="-r --adaptive-read",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("100-200"), Erase("766"), Erase("2410")]),
                   ecc="no.ecc"),
        # ... all other adaptive tests
    ]
```

- [ ] **Step 2: Run adaptive tests**

Run: `python3 -m pytest tests/test_rs01.py::TestRS01ReadAdaptive -v`
Expected: All 25 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_rs01.py
git commit -m "test: migrate RS01 adaptive reading tests to Python framework"
```

---

### Task 13: Disable RS01 Bash Tests

Once all 144 RS01 tests pass in Python, disable the bash tests.

**Files:**
- Modify: `regtest/config.txt` — set all `RS01_*` entries to `no`

- [ ] **Step 1: Run the full Python test suite to confirm everything passes**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (RS01 + existing RS03 recognize + multipass)

- [ ] **Step 2: Disable RS01 bash tests in config**

Set all `RS01_*` lines in `regtest/config.txt` to `no`:

```bash
sed -i 's/^RS01_\(.*\) yes$/RS01_\1 no/' regtest/config.txt
```

- [ ] **Step 3: Verify bash tests skip RS01**

```bash
cd regtest && bash rs01.bash all 2>&1 | tail -5
```
Expected: All tests show SKIPPED

- [ ] **Step 4: Commit**

```bash
git add tests/test_rs01.py regtest/config.txt
git commit -m "test: complete RS01 migration to Python, disable bash tests"
```

---

### Task 14: Final Cleanup and CI Verification

**Files:**
- Remove: `tests/test_rs01_verify_smoke.py` (if not already removed)
- Verify: `.github/workflows/tests.yml` runs pytest

- [ ] **Step 1: Run full test suite one more time**

```bash
python3 -m pytest tests/ -v --tb=short
```

- [ ] **Step 2: Verify CI will pick up the new tests**

Check that `tests.yml` has the pytest step and doesn't need changes:
```bash
grep -A3 'pytest' .github/workflows/tests.yml
```

- [ ] **Step 3: Commit and push**

```bash
git push
```
