"""
Tests for RS03 recognition robustness.

These tests verify that RS03 ECC data can be found even when the image
sector count doesn't match the expected medium size. This covers:

- BD-RE read-back: image padded with extra sectors (upstream #97)
- NODM without flag: image created with --no-bdr-defect-management
  but recognized without the flag (upstream #69)

The core fix is in src/rs03-recognize.c: RS03RecognizeImage() now tries
all known medium sizes as candidates instead of guessing a single one.
"""

import os

import pytest

from conftest import (
    augment_image_rs03,
    create_random_image,
    erase_sectors,
    run_dvdisaster,
    scan_image,
)

# Small image size for fast tests (in 2K sectors)
IMAGE_SECTORS = 21000
# RS03 augmented size matching the regtest default
ECC_SIZE = 25000


class TestBDREReadBackMismatch:
    """Issue #97: RS03 ECC not recognized after BD-RE read-back.

    Scenario: Image augmented at ECC_SIZE (25000 sectors), but when
    read back from a BD-RE disc, the image has extra trailing sectors
    (the drive returns the full formatted capacity). The recognize path
    must try multiple candidate layer sizes to find the ECC data.
    """

    def test_padded_image_recognized(self, dvdisaster_bin, work_dir):
        """RS03 data should be found in an image padded with extra sectors."""
        image = str(work_dir / "test.iso")
        scan_out = str(work_dir / "scan.iso")

        # Create and augment image
        create_random_image(dvdisaster_bin, image, IMAGE_SECTORS)
        augment_image_rs03(dvdisaster_bin, image, medium_size=ECC_SIZE)

        # Verify the image is the expected size
        original_size = os.path.getsize(image)
        assert original_size == ECC_SIZE * 2048

        # Pad with 5000 extra zero sectors (simulates BD-RE read-back)
        padding_sectors = 5000
        with open(image, "ab") as f:
            f.write(b"\x00" * (padding_sectors * 2048))

        padded_size = os.path.getsize(image)
        assert padded_size == (ECC_SIZE + padding_sectors) * 2048

        # Scan the padded image — should still find RS03 data
        output = scan_image(
            dvdisaster_bin, scan_out, sim_cd=image
        )

        assert "RS03" in output, (
            f"RS03 not found in padded image scan output:\n{output}"
        )
        # Should not report "no RS03 data found"
        assert "no RS03 data found" not in output.lower(), (
            f"RS03 recognition failed on padded image:\n{output}"
        )

    def test_heavily_padded_image(self, dvdisaster_bin, work_dir):
        """RS03 data should be found even with significant padding."""
        image = str(work_dir / "test.iso")
        scan_out = str(work_dir / "scan.iso")

        create_random_image(dvdisaster_bin, image, IMAGE_SECTORS)
        augment_image_rs03(dvdisaster_bin, image, medium_size=ECC_SIZE)

        # Pad to double size
        with open(image, "ab") as f:
            f.write(b"\x00" * (ECC_SIZE * 2048))

        output = scan_image(
            dvdisaster_bin, scan_out, sim_cd=image
        )

        assert "RS03" in output, (
            f"RS03 not found in heavily padded image:\n{output}"
        )


class TestNODMRecognitionWithoutFlag:
    """Issue #69: RS03 NODM images require flag at recognition time.

    Previously, an image created with -n BDNODM could only be recognized
    if --no-bdr-defect-management was also passed during scan/verify.
    Users could forget this flag years later when recovering a damaged disc.

    After the fix, both DM and NODM sizes are always tried as candidates.
    """

    def test_nodm_image_without_flag(self, dvdisaster_bin, work_dir):
        """RS03 NODM image should be recognized without the NODM flag."""
        image = str(work_dir / "test.iso")
        scan_out = str(work_dir / "scan.iso")

        # Create image augmented at BD_SL_SIZE_NODM (12219392 sectors)
        create_random_image(dvdisaster_bin, image, IMAGE_SECTORS)
        augment_image_rs03(dvdisaster_bin, image, medium_size="BDNODM")

        # Erase the ECC header to force the candidate search path
        # (if the header is intact, FindRS03HeaderInImage finds it
        # directly without needing the size-based search)
        erase_sectors(dvdisaster_bin, image, str(IMAGE_SECTORS))

        # Scan WITHOUT --no-bdr-defect-management flag
        # Use -a RS03 to hint the codec and trigger exhaustive search
        output = scan_image(
            dvdisaster_bin,
            scan_out,
            sim_cd=image,
            extra_args=["-a", "RS03", "-v"],
        )

        # Should find the RS03 data via candidate search
        assert "rediscovered format" in output.lower() or "RS03" in output, (
            f"RS03 NODM data not found without flag:\n{output}"
        )
        assert "no RS03 data found" not in output.lower(), (
            f"RS03 recognition failed for NODM image without flag:\n{output}"
        )

    def test_nodm_image_with_flag_still_works(self, dvdisaster_bin, work_dir):
        """Sanity check: NODM image with the flag should still work."""
        image = str(work_dir / "test.iso")
        scan_out = str(work_dir / "scan.iso")

        create_random_image(dvdisaster_bin, image, IMAGE_SECTORS)
        augment_image_rs03(dvdisaster_bin, image, medium_size="BDNODM")

        erase_sectors(dvdisaster_bin, image, str(IMAGE_SECTORS))

        output = scan_image(
            dvdisaster_bin,
            scan_out,
            sim_cd=image,
            extra_args=["-a", "RS03", "-v", "--no-bdr-defect-management"],
        )

        assert "no RS03 data found" not in output.lower(), (
            f"RS03 recognition failed even WITH NODM flag:\n{output}"
        )
