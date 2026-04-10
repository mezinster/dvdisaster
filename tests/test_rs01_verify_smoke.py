"""
Smoke tests for the golden-test framework using real RS01 verify tests.

These verify the full pipeline: master image creation, damage application,
dvdisaster invocation, output cleaning, and golden-file comparison.
"""

from framework import Byteset, GoldenTest, GoldenTestSuite


class TestRS01VerifySmoke(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    master_ecc = "rs01-master.ecc"
    image_size = 21000
    redundancy = "normal"

    tests = [
        # Test good image + ecc (uses master directly, no copy)
        GoldenTest("good", action="-t", use_master=True, ecc="master_ecc"),

        # Test with missing image file (nonexistent path)
        GoldenTest("ecc_missing_image", action="-c -n normal",
                   image="none.iso", ecc="rs01-tmp.ecc"),

        # Test with CRC errors in image (byteset damage, verify with ecc)
        GoldenTest("crc_errors_with_ecc", action="-t",
                   damage=[Byteset(13444, 0, 154)], ecc="master_ecc"),
    ]
