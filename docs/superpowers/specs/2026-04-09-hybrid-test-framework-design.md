# Hybrid Test Framework Design

**Date:** 2026-04-09
**Status:** Approved

## Goal

Replace the bash-based regression test suite (568 tests across 4 codecs) with a Python/pytest framework that uses a declarative DSL for test definitions. The framework supports both golden-file comparison and semantic assertions (hybrid approach).

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Assertion style | Hybrid (golden + semantic) | Golden for deterministic output, semantic for timing-sensitive tests |
| Golden file management | Reuse existing, then migrate | Avoids duplicating 500+ files during transition |
| Test declaration | Declarative test classes (DSL) | Compact, scannable, hides boilerplate |
| Codec organization | Separate file per codec | Codecs differ in parameters; enables one-at-a-time migration |
| Reading test pattern | Optional `sim_cd` field on `GoldenTest` | Single class, presence/absence makes test type clear |
| Initial scope | RS01 (simplest, 144 tests) | Prove framework on easiest case first |

## Damage Operations DSL

Atomic operations applied to images before running dvdisaster:

```python
Erase("15800-16199")                          # --erase range
Erase("15900-16099", fill_unreadable=64)      # --erase with --fill-unreadable
Erase("15900-16099:readable in pass 3")       # --erase with sim label
Byteset(4096, 100, 17)                        # --byteset sector,offset,value
Truncate(20500)                               # --truncate=N
```

Each is a dataclass that knows how to produce CLI arguments for dvdisaster.

## Test Declaration DSL

### GoldenTest dataclass

```python
@dataclass
class GoldenTest:
    name: str                          # test name, maps to golden file
    action: str                        # dvdisaster action flags (e.g., "-t", "-r", "-c", "-f")
    damage: list = None                # list of Erase/Byteset/Truncate to apply to image
    use_master: bool = False           # run directly on master (read-only test)
    image: str = None                  # override image path (e.g., "no.iso")
    ecc: str = None                    # ecc file to use ("master_ecc" or path)
    sim_cd: SimCD = None               # sim-cd reading configuration
    create_ecc: CreateECC = None       # ecc creation configuration
    extra_args: list = None            # additional CLI arguments
    skip_output_compare: bool = False  # skip golden output diff (MD5 only)
```

### SimCD dataclass

```python
@dataclass
class SimCD:
    source: str = "master"             # base image ("master" or "raw")
    damage: list = None                # damage to apply to sim image
```

### CreateECC dataclass

```python
@dataclass
class CreateECC:
    method: str = None                 # e.g., "RS03"
    redundancy: str = None             # e.g., "normal", "20r"
    output: str = None                 # e.g., "file"
    ecc_size: int = None               # -n <sectors> for augmented image codecs
```

### GoldenTestSuite base class

```python
class GoldenTestSuite:
    codec: str                         # e.g., "RS01"
    codec_prefix: str                  # for golden file lookup (e.g., "RS01")
    master: str                        # master image filename
    ecc_master: str = None             # pre-built ecc file (if needed)
    tests: list                        # list of GoldenTest instances
```

The base class uses `__init_subclass__` (or a pytest plugin hook) to convert each `GoldenTest` in the `tests` list into a parametrized `test_golden()` method at collection time.

## Test Suite Example

```python
class TestRS01Verify(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    ecc_master = "rs01-master.ecc"

    tests = [
        GoldenTest("good", action="-t", use_master=True, ecc="master_ecc"),
        GoldenTest("good_quick", action="-tq", use_master=True, ecc="master_ecc"),
        GoldenTest("no_image", action="-t", image="no.iso", ecc="no.ecc"),
        GoldenTest("data_bad_byte", action="-t",
                   damage=[Byteset(4096, 100, 17)], ecc="master_ecc"),
        GoldenTest("missing_sectors", action="-t",
                   damage=[Erase("1500-1673"), Erase("13420-14109")],
                   ecc="master_ecc"),
    ]
```

### Reading tests with sim-cd

```python
class TestRS01ReadLinear(GoldenTestSuite):
    codec = "RS01"
    codec_prefix = "RS01"
    master = "rs01-master.iso"
    ecc_master = "rs01-master.ecc"

    tests = [
        GoldenTest("read_good", action="-r",
                   sim_cd=SimCD(source="master"),
                   ecc="master_ecc"),
        GoldenTest("read_defective_no_ecc", action="-r",
                   sim_cd=SimCD(source="master",
                                damage=[Erase("15800-16199")])),
    ]
```

### Semantic tests (hybrid)

Complex tests that don't use golden comparison live as plain methods on the same suite class:

```python
class TestRS01ReadLinear(GoldenTestSuite):
    # ... declarative tests above ...

    def test_multipass_partial_success(self, dvdisaster_bin, work_dir):
        """Semantic test -- checks properties, not exact output."""
        # Custom setup and assertions (like test_multipass_read.py)
```

## Golden File Handling

### Lookup

For test name `foo` with codec prefix `RS01`:
1. Check `regtest/database/RS01_foo.darwin` (on macOS)
2. Check `regtest/database/RS01_foo.win` (on Windows)
3. Fall back to `regtest/database/RS01_foo`

### Parsing

Golden files have this format:
```
<image_md5 or "ignore">
<ecc_md5 or "ignore">
<license header (4 lines)>
<blank line>
<expected output...>
```

The runner:
1. Reads line 1 as expected image MD5 (`"ignore"` = skip)
2. Reads line 2 as expected ecc MD5 (`"ignore"` = skip)
3. Strips lines 3-6 (license header + blank) as expected output starts at line 7

### Output Cleaning

Same filtering as bash `run_regtest`:
- Remove "dvdisaster: No memory leaks found." lines
- Remove user-specified `IGNORE_LOG_LINE` patterns
- Strip temp directory paths for reproducibility
- Strip Windows drive letter paths

### Comparison

1. Diff cleaned actual output against expected output
2. If image MD5 is not "ignore", verify image file matches
3. If ecc MD5 is not "ignore", verify ecc file matches

## Execution Flow

For each `GoldenTest`:

```
1. Create temp work_dir (pytest tmp_path)
2. Resolve image:
   - use_master=True → use master directly (no copy)
   - image="no.iso" → use literal path (for error tests)
   - else → copy master to work_dir
3. Apply damage operations in order (erase, byteset, truncate)
4. If create_ecc: run dvdisaster to create ECC data
5. If sim_cd:
   a. Copy source image to work_dir as sim ISO
   b. Apply sim_cd.damage operations
   c. Add --sim-cd=<path> --fixed-speed-values --spinup-delay=0 to args
6. Run: dvdisaster --regtest --no-progress -i<image> [-e<ecc>] <action> [extra_args]
7. Clean and compare output against golden file
8. Verify MD5 checksums if specified
```

## File Structure

```
tests/
  conftest.py              # existing fixtures (dvdisaster_bin, work_dir)
  framework.py             # GoldenTestSuite, GoldenTest, damage ops, runner
  test_rs01.py             # RS01 tests (first migration target)
  test_rs02.py             # future
  test_rs03f.py            # future
  test_rs03i.py            # future
  test_multipass_read.py   # existing semantic tests (all codecs)
  test_rs03_recognize.py   # existing semantic tests
```

## Master Image Management

Master images are created once and cached in `/var/tmp/regtest/` (same as bash tests). The framework:
- Checks if master exists before creating
- Creates with `--random-image <size>` using default seed
- For RS01: also creates a master ECC file

This matches the bash setup phase and reuses the same cached files during the transition period.

## Migration Path

1. Build `framework.py` + migrate RS01 verify tests (prove it works)
2. Migrate remaining RS01 sections (creation, fixing, scanning, reading)
3. Migrate RS02, RS03f, RS03i (one codec at a time)
4. Once a codec is fully migrated, disable its bash tests in `regtest/config.txt`
5. Move golden files from `regtest/database/` to `tests/golden/` with simplified format (drop MD5 lines, just keep expected output; MD5 checks become inline assertions)
6. Eventually remove bash test files and `common.bash`

## CI Integration

The pytest tests already run in `.github/workflows/tests.yml`:
```yaml
- name: pytest integration tests
  run: |
    pip install pytest
    python3 -m pytest tests/ -v
```

New test files are picked up automatically. During migration, both bash and Python tests run. Once a codec is migrated, its bash tests are disabled to avoid double-running.
