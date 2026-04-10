"""
RS01 verify tests -- all 28 verify tests from regtest/rs01.bash.

Tests are grouped into:
  - Declarative GoldenTest entries for tests using master/master_ecc directly
  - Session fixture for plus56 setup images
  - Plain test methods for plus56-dependent and truncated_by_bytes tests
"""

import os
import shutil

import pytest

from framework import (
    Byteset,
    Erase,
    GoldenTest,
    GoldenTestSuite,
    PadBytes,
    PadSectors,
    Truncate,
    _ISODIR,
    _find_binary,
    _run_dvdisaster,
)


# ---------------------------------------------------------------------------
# Session fixture: create plus56 setup images (shared across all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def plus56_images():
    """Create rs01-plus56_bytes.iso and .ecc in ISODIR if they don't exist.

    These mirror the bash preamble that creates ISO_PLUS56 and ECC_PLUS56.
    Requires the master image and is idempotent.
    """
    os.makedirs(_ISODIR, exist_ok=True)
    master_iso = os.path.join(_ISODIR, "rs01-master.iso")
    iso_plus56 = os.path.join(_ISODIR, "rs01-plus56_bytes.iso")
    ecc_plus56 = os.path.join(_ISODIR, "rs01-plus56_bytes.ecc")

    # Ensure master exists (the suite's _ensure_master would do this,
    # but we need it before the suite runs for the fixture).
    if not os.path.isfile(master_iso):
        _run_dvdisaster(
            "--regtest", "--debug",
            "-i{}".format(master_iso),
            "--random-image", "21000",
            check=True,
        )

    # Create plus56 ISO: master + 56 zero bytes
    if not os.path.isfile(iso_plus56):
        shutil.copy2(master_iso, iso_plus56)
        with open(iso_plus56, "ab") as f:
            f.write(b"\x00" * 56)

    # Create plus56 ECC
    if not os.path.isfile(ecc_plus56):
        # Ensure master ECC exists too (needed for the suite)
        master_ecc = os.path.join(_ISODIR, "rs01-master.ecc")
        if not os.path.isfile(master_ecc):
            _run_dvdisaster(
                "--regtest", "--debug", "--set-version", "0.80",
                "-i{}".format(master_iso),
                "-e{}".format(master_ecc),
                "-c", "-n", "normal",
                check=True,
            )
        _run_dvdisaster(
            "--regtest", "--debug", "--set-version", "0.80",
            "-i{}".format(iso_plus56),
            "-e{}".format(ecc_plus56),
            "-c", "-n", "normal",
            check=True,
        )

    return iso_plus56, ecc_plus56


# ---------------------------------------------------------------------------
# Common damage patterns (reused by multiple tests)
# ---------------------------------------------------------------------------

_DAMAGE_DEFECTIVE = [
    Erase("1000-1049"),
    Erase("11230"),
    Erase("12450-12457"),
    Byteset(13444, 0, 154),
]

_DAMAGE_MISSING_SECTORS = [
    Erase("1000-1049"),
    Erase("11230"),
    Erase("12450-12457"),
]

_DAMAGE_DSM1 = [
    Erase("3030"),
    Byteset(3030, 353, 49),
    Erase("4400"),
    Byteset(4400, 353, 53),
    Erase("4411"),
    Byteset(4411, 353, 53),
]

_DAMAGE_DSM2 = [
    Erase("3030"),
    Byteset(3030, 416, 55),
    Byteset(3030, 556, 32),
    Byteset(3030, 557, 50),
    Erase("4400"),
    Byteset(4400, 416, 53),
    Byteset(4400, 556, 32),
    Byteset(4400, 557, 50),
    Erase("4411"),
    Byteset(4411, 416, 53),
    Byteset(4411, 556, 32),
    Byteset(4411, 557, 50),
]


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestRS01Verify(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    # ------------------------------------------------------------------
    # Declarative tests (auto-parametrized via test_golden)
    # ------------------------------------------------------------------
    tests = [
        # 1. good
        GoldenTest("good", action="-t", use_master=True, ecc="master_ecc"),
        # 2. good_quick
        GoldenTest("good_quick", action="-tq", use_master=True, ecc="master_ecc"),
        # 3. no_files
        GoldenTest("no_files", action="-t", image="no.iso", ecc="no.ecc"),
        # 4. no_image
        GoldenTest("no_image", action="-t", image="no.iso", ecc="master_ecc"),
        # 5. no_ecc
        GoldenTest("no_ecc", action="-t", use_master=True, ecc="no.ecc"),
        # 6. defective_image_no_ecc
        GoldenTest("defective_image_no_ecc", action="-t",
                   damage=_DAMAGE_DEFECTIVE, ecc="no.ecc"),
        # 15. truncated (by 5 sectors)
        GoldenTest("truncated", action="-t",
                   damage=[Truncate(20995)], ecc="master_ecc"),
        # 16. plus1 (1 extra sector)
        GoldenTest("plus1", action="-t",
                   damage=[PadSectors(1)], ecc="master_ecc"),
        # 17. plus17 (17 extra sectors)
        GoldenTest("plus17", action="-t",
                   damage=[PadSectors(17)], ecc="master_ecc"),
        # 18. defective_with_ecc
        GoldenTest("defective_with_ecc", action="-t",
                   damage=_DAMAGE_DEFECTIVE, ecc="master_ecc"),
        # 19. missing_sectors_with_ecc
        GoldenTest("missing_sectors_with_ecc", action="-t",
                   damage=_DAMAGE_MISSING_SECTORS, ecc="master_ecc"),
        # 20. crc_errors_with_ecc
        GoldenTest("crc_errors_with_ecc", action="-t",
                   damage=[Byteset(13444, 0, 154)], ecc="master_ecc"),
        # 21. crc_in_fingerprint
        GoldenTest("crc_in_fingerprint", action="-t",
                   damage=[Byteset(16, 201, 55)], ecc="master_ecc"),
        # 22. missing_fingerprint
        GoldenTest("missing_fingerprint", action="-t",
                   damage=[Erase("16")], ecc="master_ecc"),
        # 23. missing_ecc_header
        GoldenTest("missing_ecc_header", action="-t",
                   use_master=True, ecc="master_ecc",
                   ecc_damage=[Erase("0")]),
        # 24. ecc_header_crc_error
        GoldenTest("ecc_header_crc_error", action="-t",
                   use_master=True, ecc="master_ecc",
                   ecc_damage=[Byteset(0, 22, 107)]),
        # 25. uncorrectable_dsm_in_image
        GoldenTest("uncorrectable_dsm_in_image", action="-t",
                   damage=_DAMAGE_DSM1, ecc="master_ecc"),
        # 26. uncorrectable_dsm_in_image_verbose
        GoldenTest("uncorrectable_dsm_in_image_verbose", action="-t -v",
                   damage=_DAMAGE_DSM1, ecc="master_ecc"),
        # 27. uncorrectable_dsm_in_image2
        GoldenTest("uncorrectable_dsm_in_image2", action="-t",
                   damage=_DAMAGE_DSM2, ecc="master_ecc"),
        # 28. uncorrectable_dsm_in_image2_verbose
        GoldenTest("uncorrectable_dsm_in_image2_verbose", action="-t -v",
                   damage=_DAMAGE_DSM2, ecc="master_ecc"),
    ]

    # ------------------------------------------------------------------
    # Plus56 fixture-dependent tests (#7-#13)
    # ------------------------------------------------------------------

    def test_plus56_bytes(self, plus56_images, tmp_path):
        """#7: verify plus56 image with its own ecc."""
        iso_plus56, ecc_plus56 = plus56_images
        test = GoldenTest(
            "plus56_bytes", action="-t",
            image=os.path.basename(iso_plus56),
            ecc=os.path.basename(ecc_plus56),
        )
        self._run_golden_test(test, tmp_path)

    def test_image_plus56_bytes(self, plus56_images, tmp_path):
        """#8: verify plus56 image with no ecc."""
        iso_plus56, _ = plus56_images
        test = GoldenTest(
            "image_plus56_bytes", action="-t",
            image=os.path.basename(iso_plus56),
            ecc="no.ecc",
        )
        self._run_golden_test(test, tmp_path)

    def test_ecc_plus56_bytes(self, plus56_images, tmp_path):
        """#9: verify no image with plus56 ecc."""
        _, ecc_plus56 = plus56_images
        test = GoldenTest(
            "ecc_plus56_bytes", action="-t",
            image="no.iso",
            ecc=os.path.basename(ecc_plus56),
        )
        self._run_golden_test(test, tmp_path)

    def test_normal_image_ecc_plus56b(self, plus56_images, tmp_path):
        """#10: verify normal master image with plus56 ecc."""
        _, ecc_plus56 = plus56_images
        test = GoldenTest(
            "normal_image_ecc_plus56b", action="-t",
            use_master=True,
            ecc=os.path.basename(ecc_plus56),
        )
        self._run_golden_test(test, tmp_path)

    def test_image_plus56b_normal_ecc(self, plus56_images, tmp_path):
        """#11: verify plus56 image with normal master ecc."""
        iso_plus56, _ = plus56_images
        test = GoldenTest(
            "image_plus56b_normal_ecc", action="-t",
            image=os.path.basename(iso_plus56),
            ecc="master_ecc",
        )
        self._run_golden_test(test, tmp_path)

    def test_image_few_bytes_shorter(self, plus56_images, tmp_path):
        """#12: master + 55 bytes (1 byte shorter than plus56 ecc expects)."""
        _, ecc_plus56 = plus56_images
        test = GoldenTest(
            "image_few_bytes_shorter", action="-t",
            damage=[PadBytes(55)],
            ecc=os.path.basename(ecc_plus56),
        )
        self._run_golden_test(test, tmp_path)

    def test_image_few_bytes_longer(self, plus56_images, tmp_path):
        """#13: master + 57 bytes (1 byte longer than plus56 ecc expects)."""
        _, ecc_plus56 = plus56_images
        test = GoldenTest(
            "image_few_bytes_longer", action="-t",
            damage=[PadBytes(57)],
            ecc=os.path.basename(ecc_plus56),
        )
        self._run_golden_test(test, tmp_path)

    # ------------------------------------------------------------------
    # Truncated by bytes test (#14) -- needs dd-like truncation
    # ------------------------------------------------------------------

    def test_truncated_by_bytes(self, tmp_path):
        """#14: master truncated to (2048*21000 - 7) bytes."""
        master = self._ensure_master()
        master_ecc = self._ensure_master_ecc()
        truncated_size = 2048 * 21000 - 7

        tmp_iso = os.path.join(str(tmp_path), "rs01-tmp.iso")
        with open(master, "rb") as src, open(tmp_iso, "wb") as dst:
            dst.write(src.read(truncated_size))

        test = GoldenTest(
            "truncated_by_bytes", action="-t",
            ecc="master_ecc",
        )
        # Manually set up and run since we prepared the image ourselves
        self._run_golden_test_with_prepared_image(test, tmp_iso, tmp_path)

    def _run_golden_test_with_prepared_image(self, test, image_path, tmp_path):
        """Run a golden test with an already-prepared image file."""
        import difflib

        golden_base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "regtest", "database",
            "{}_{}".format(self.codec_prefix, test.name),
        )
        from framework import resolve_golden_path, parse_golden_file, clean_output, _md5_file, _ISODIR, _TMPDIR
        golden_path = resolve_golden_path(golden_base)
        if not os.path.isfile(golden_path):
            pytest.skip("Golden file not found: {}".format(golden_path))

        image_md5, ecc_md5, expected_output = parse_golden_file(golden_path)
        ecc_path = self._resolve_ecc(test)

        cmd_args = ["--regtest", "--no-progress"]
        cmd_args.append("-i{}".format(image_path))
        if ecc_path:
            cmd_args.append("-e{}".format(ecc_path))
        cmd_args.extend(test.action.split())

        _, raw_output = _run_dvdisaster(*cmd_args)

        work_dir = str(tmp_path)
        cleaned = clean_output(
            raw_output,
            tmp_dirs=[work_dir, _TMPDIR, _ISODIR],
            strip_header=True,
        )

        if cleaned != expected_output:
            diff = difflib.unified_diff(
                expected_output.splitlines(keepends=True),
                cleaned.splitlines(keepends=True),
                fromfile="expected (golden)",
                tofile="actual (cleaned)",
            )
            diff_text = "".join(diff)
            assert cleaned == expected_output, (
                "Output mismatch for test '{}':\n{}".format(test.name, diff_text)
            )

        if image_md5 is not None and os.path.isfile(image_path):
            actual_md5 = _md5_file(image_path)
            assert actual_md5 == image_md5, (
                "Image MD5 mismatch for '{}': expected {}, got {}".format(
                    test.name, image_md5, actual_md5
                )
            )
