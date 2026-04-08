# RS03 Recognition Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RS03 recognition find ECC data regardless of image size mismatch (BD-RE read-back, DM/NODM mismatch, custom -n values) by trying all known medium sizes as candidates.

**Architecture:** Replace the single-guess layer size selection in `RS03RecognizeImage()` with a multi-candidate search loop. Add three small helper functions in the same file. Both DM and NODM BD sizes are always tried, removing the `noBdrDefectManagement` flag dependency from the recognize path.

**Tech Stack:** C (gcc/clang), bash regression tests, GNU make

**Spec:** `docs/superpowers/specs/2026-04-08-rs03-recognize-robustness-design.md`

---

### Task 1: Add helper functions to rs03-recognize.c

**Files:**
- Modify: `src/rs03-recognize.c` (insert before `RS03RecognizeImage` function, around line 635)

- [ ] **Step 1: Add the `add_candidate` helper function**

Insert the following code before the `RS03RecognizeImage` function (before line 641):

```c
/*
 * Multi-candidate layer size search helpers.
 * Instead of guessing a single layer size from the image sector count,
 * we try all known medium sizes (DM and NODM) plus image-derived sizes.
 * search_crc_blocks_for_layer_size() validates each candidate via CRC,
 * so wrong guesses fail fast and cheaply.
 */

#define MAX_CANDIDATES 16

static void add_candidate(guint64 *candidates, int *n, guint64 layer_size)
{  int i;

   if(layer_size == 0 || *n >= MAX_CANDIDATES)
      return;

   /* Deduplicate: skip if already present */
   for(i = 0; i < *n; i++)
      if(candidates[i] == layer_size)
         return;

   candidates[(*n)++] = layer_size;
}
```

- [ ] **Step 2: Add the `heuristic_layer_size` helper function**

Insert immediately after `add_candidate`:

```c
/*
 * Original heuristic: pick layer size from total image sectors using
 * strict-less-than thresholds. This is the best first guess for optical
 * media where READ CAPACITY matches the medium type.
 */
static guint64 heuristic_layer_size(guint64 image_sectors)
{
   if(image_sectors < CDR_SIZE)         return CDR_SIZE/GF_FIELDMAX;
   else if(image_sectors < DVD_SL_SIZE) return DVD_SL_SIZE/GF_FIELDMAX;
   else if(image_sectors < DVD_DL_SIZE) return DVD_DL_SIZE/GF_FIELDMAX;
   else if(image_sectors < BD_SL_SIZE)  return BD_SL_SIZE/GF_FIELDMAX;
   else if(image_sectors < BD_DL_SIZE)  return BD_DL_SIZE/GF_FIELDMAX;
   else if(image_sectors < BDXL_TL_SIZE) return BDXL_TL_SIZE/GF_FIELDMAX;
   else                                  return BDXL_QL_SIZE/GF_FIELDMAX;
}
```

- [ ] **Step 3: Verify the project builds**

Run:
```bash
./configure --with-gui=no && make clean && make -j$(nproc)
```
Expected: Compiles without errors. The new functions are static and not yet called, so no warnings about unused functions with the current warning flags (unused functions don't warn, only unused variables do with `-Wno-unused-but-set-variable`).

- [ ] **Step 4: Commit**

```bash
git add src/rs03-recognize.c
git commit -m "refactor: add candidate search helpers for RS03 recognize"
```

---

### Task 2: Replace single-guess with candidate loop in RS03RecognizeImage

**Files:**
- Modify: `src/rs03-recognize.c:709-760` (the Phase 0 + Phase 1 block inside `RS03RecognizeImage`)

- [ ] **Step 1: Replace the single-guess block with candidate loop**

Replace lines 709-760 (from `/* Determine image size in augmented case */` through the end of the Phase 1 `if(maxtries < 0)` block) with:

```c
   /* Try all known medium sizes as candidates.
      For optical media in quick mode, we limit to a few likely candidates
      to avoid excessive reads on slow drives.
      For file images (exhaustive mode), we try all known sizes.
      search_crc_blocks_for_layer_size() validates via CRC, so wrong
      guesses are rejected definitively and cheaply. */

   if(Closure->mediumSize >= GF_FIELDMAX)
   {  /* User override via -n: try only this size */
      layer_size = Closure->mediumSize/GF_FIELDMAX;
      Verbose("Image size set to %" PRId64 " (layer size %" PRId64 ")\n",
	      Closure->mediumSize, layer_size);

      trynumber = 0;
      if(search_crc_blocks_for_layer_size(image, image_sectors, layer_size, maxtries, &trynumber))
	 return TRUE;
   }
   else
   {  guint64 candidates[MAX_CANDIDATES];
      int n_candidates = 0;
      int max_to_try;
      int i;

      if(image->type == IMAGE_MEDIUM && maxtries > 0)
      {  /* Quick mode for optical media: heuristic first, then alternatives */
	 guint64 heuristic = heuristic_layer_size(image_sectors);
	 add_candidate(candidates, &n_candidates, heuristic);
	 /* Try the NODM counterpart of the heuristic's BD tier */
	 add_candidate(candidates, &n_candidates, BD_SL_SIZE_NODM/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BD_DL_SIZE_NODM/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BDXL_TL_SIZE_NODM/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BDXL_QL_SIZE_NODM/GF_FIELDMAX);
	 /* Image-derived as fallback */
	 add_candidate(candidates, &n_candidates, image_sectors/GF_FIELDMAX);
	 max_to_try = 3; /* limit candidates in quick mode */
	 Verbose("RS03RecognizeImage: quick mode, %d candidates (trying up to %d)\n",
		 n_candidates, max_to_try);
      }
      else
      {  /* Exhaustive mode for file images: try all known sizes */
	 /* Image-derived is a strong heuristic for complete images */
	 add_candidate(candidates, &n_candidates, image_sectors/GF_FIELDMAX);
	 if(image_sectors > 0)
	 {  add_candidate(candidates, &n_candidates, image_sectors/GF_FIELDMAX - 1);
	    add_candidate(candidates, &n_candidates, image_sectors/GF_FIELDMAX + 1);
	 }
	 /* All standard medium sizes */
	 add_candidate(candidates, &n_candidates, DVD_DL_SIZE/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BD_SL_SIZE/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BD_SL_SIZE_NODM/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, DVD_SL_SIZE/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BD_DL_SIZE/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BD_DL_SIZE_NODM/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, CDR_SIZE/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BDXL_TL_SIZE/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BDXL_TL_SIZE_NODM/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BDXL_QL_SIZE/GF_FIELDMAX);
	 add_candidate(candidates, &n_candidates, BDXL_QL_SIZE_NODM/GF_FIELDMAX);
	 max_to_try = n_candidates; /* try all in exhaustive mode */
	 Verbose("RS03RecognizeImage: exhaustive mode, %d candidates\n", n_candidates);
      }

      for(i = 0; i < n_candidates && i < max_to_try; i++)
      {  trynumber = 0;
	 Verbose("RS03RecognizeImage: trying candidate %d/%d, layer size %" PRId64 "\n",
		 i+1, n_candidates < max_to_try ? n_candidates : max_to_try,
		 (gint64)candidates[i]);
	 if(search_crc_blocks_for_layer_size(image, image_sectors, candidates[i], maxtries, &trynumber))
	    return TRUE;
      }
   }
```

Note: This replaces everything from line 709 (`/* Determine image size */`) through line 760 (end of Phase 1 block). The variable declarations for `layer_size` and `trynumber` at the top of the function (lines 643-644) remain unchanged — `layer_size` is still used in the `Closure->mediumSize` path.

- [ ] **Step 2: Build and verify compilation**

Run:
```bash
make clean && make -j$(nproc)
```
Expected: Compiles without errors or warnings.

- [ ] **Step 3: Run existing regression tests**

Run:
```bash
mkdir -p /var/tmp/regtest
REGTEST_NO_UTF8=1 MAX_JOBS=4 ./regtest/runtests.sh
```
Expected: All existing tests pass. The new candidate loop tries the same sizes as before (the image-derived and heuristic paths cover all previous behavior), just more of them.

- [ ] **Step 4: Commit**

```bash
git add src/rs03-recognize.c
git commit -m "fix: RS03 recognize tries all known medium sizes as candidates

Replace single-guess layer size selection with multi-candidate search.
Both DM and NODM BD sizes are always tried, removing the need for
--no-bdr-defect-management at recognition time. Fixes recognition
of RS03 ECC data when image sector count doesn't match expected
medium size (BD-RE read-back, DM/NODM mismatch).

Addresses upstream issues speed47/dvdisaster#69, #97, #135."
```

---

### Task 3: Add regression test for BD-RE read-back mismatch (issue #97)

**Files:**
- Modify: `regtest/rs03i.bash` (append new test near the end, before the final `collect_results`)
- Modify: `regtest/config.txt` (add test toggle)
- Create: `regtest/database/RS03i_scan_recognize_padded_image` (generated by test run)

This test simulates the BD-RE scenario: create an RS03 augmented image at a small size (DVD_DL-like), then pad it to a larger size (simulating BD-RE read-back returning more sectors), and verify that scanning still finds the ECC data.

- [ ] **Step 1: Add test toggle to config.txt**

Append to the RS03i scan section in `regtest/config.txt` (after the last `RS03i_scan_*` line):

```
RS03i_scan_recognize_padded_image yes
```

- [ ] **Step 2: Add the test case to rs03i.bash**

Find the line `collect_results` near the end of `regtest/rs03i.bash` and insert the following test block before it:

```bash
# Recognize RS03 data in an image padded to a larger size.
# Simulates BD-RE read-back: image was augmented at ECCSIZE (25000 sectors)
# but read back with additional trailing sectors (30000 total).
# The recognize path must try multiple candidate layer sizes to find it.
# (Addresses upstream issues #69, #97)

REGTEST_SECTION="Recognition robustness"

if try "recognize RS03 in padded image (BD-RE scenario)" scan_recognize_padded_image; then (
  # Create a standard augmented image
  $NEWVER --debug -i$SIMISO --random-image $ISOSIZE >>$LOGFILE 2>&1
  $NEWVER --regtest --debug --set-version $SETVERSION -i$SIMISO -mRS03 -n$ECCSIZE -c >>$LOGFILE 2>&1

  # Pad the image with 5000 extra zero sectors to simulate BD-RE read-back
  dd if=/dev/zero bs=2048 count=5000 >>$SIMISO 2>/dev/null

  extra_args="--debug --sim-cd=$SIMISO --fixed-speed-values"
  run_regtest scan_recognize_padded_image "--spinup-delay=0 -s" $TMPISO $NO_FILE
) & limit_jobs; fi
```

- [ ] **Step 3: Run the new test to generate the reference database file**

Run:
```bash
cd regtest
REGTEST_NO_UTF8=1 ../dvdisaster --regtest --debug -i/dev/shm/regtest_RS03i/scan_recognize_padded_image/rs03i-sim.iso --random-image 21000 2>/dev/null
../dvdisaster --regtest --debug --set-version 0.80 -i/dev/shm/regtest_RS03i/scan_recognize_padded_image/rs03i-sim.iso -mRS03 -n25000 -c 2>/dev/null
dd if=/dev/zero bs=2048 count=5000 >>/dev/shm/regtest_RS03i/scan_recognize_padded_image/rs03i-sim.iso 2>/dev/null
../dvdisaster --regtest --debug --sim-cd=/dev/shm/regtest_RS03i/scan_recognize_padded_image/rs03i-sim.iso --fixed-speed-values --spinup-delay=0 -s -i/dev/shm/regtest_RS03i/scan_recognize_padded_image/rs03i-tmp.iso 2>&1 | tee /dev/shm/newlog.txt
```

Expected: The scan should succeed and find the RS03 ECC data despite the image being padded.

- [ ] **Step 4: Create the reference database file**

Copy the output from step 3, edit it following the `regtest/README` format:
- Line 1: md5sum of the image file or "ignore"
- Line 2: md5sum of the ecc file or "ignore"
- Remove directory path prefixes from .iso/.ecc file paths
- Save as `regtest/database/RS03i_scan_recognize_padded_image`

Since the exact output depends on the runtime, run the test once via the framework to generate it:

```bash
cd /home/mezinster/dvdisaster
mkdir -p /var/tmp/regtest
REGTEST_NO_UTF8=1 ./regtest/runtests.sh RS03i_scan_recognize_padded_image
```

The test will show a diff between actual and expected (since no database file exists yet). Copy the "new" log from the test output location to the database:

```bash
cp /dev/shm/regtest_RS03i/scan_recognize_padded_image/newlog.txt regtest/database/RS03i_scan_recognize_padded_image
```

Then edit the file per `regtest/README` conventions (remove path prefixes, set line 1/2 checksums).

- [ ] **Step 5: Verify the test passes**

```bash
REGTEST_NO_UTF8=1 ./regtest/runtests.sh RS03i_scan_recognize_padded_image
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add regtest/rs03i.bash regtest/config.txt regtest/database/RS03i_scan_recognize_padded_image
git commit -m "test: add regtest for RS03 recognition of padded image (BD-RE scenario)"
```

---

### Task 4: Add regression test for NODM recognition without flag (issue #69)

**Files:**
- Modify: `regtest/rs03i.bash` (append new test)
- Modify: `regtest/config.txt` (add test toggle)
- Create: `regtest/database/RS03i_scan_recognize_nodm_without_flag` (generated by test run)

This test creates an RS03 augmented image using a NODM medium size, then verifies recognition works without the `--no-bdr-defect-management` flag.

- [ ] **Step 1: Add test toggle to config.txt**

Append after the previous new entry:

```
RS03i_scan_recognize_nodm_without_flag yes
```

- [ ] **Step 2: Add the test case to rs03i.bash**

Insert after the previous new test block (before `collect_results`):

```bash
# Recognize RS03 data created with NODM size, without --no-bdr-defect-management.
# Previously, recognition required the flag to be set, which users could forget
# years later when trying to recover a damaged disc.
# (Addresses upstream issue #69)

if try "recognize NODM image without flag" scan_recognize_nodm_without_flag; then (
  # Create image augmented at BD_SL_SIZE_NODM (12219392 sectors)
  # We use a small image with -n to set the sector count explicitly.
  $NEWVER --debug -i$SIMISO --random-image $ISOSIZE >>$LOGFILE 2>&1
  $NEWVER --regtest --debug --set-version $SETVERSION -i$SIMISO -mRS03 -n BDNODM -c >>$LOGFILE 2>&1

  # Erase the ECC header to force exhaustive search
  # The header position is at dataSectors (right after data)
  $NEWVER --debug -i$SIMISO --erase $ISOSIZE >>$LOGFILE 2>&1

  # Scan WITHOUT --no-bdr-defect-management flag
  replace_config examine-rs03 1
  replace_config medium-size 0
  extra_args="--debug --sim-cd=$SIMISO --fixed-speed-values"
  run_regtest scan_recognize_nodm_without_flag "--spinup-delay=0 -a RS03 -s -v" $TMPISO $TMPECC
) & limit_jobs; fi
```

- [ ] **Step 3: Generate the reference database file**

Run the test once to generate the output:

```bash
REGTEST_NO_UTF8=1 ./regtest/runtests.sh RS03i_scan_recognize_nodm_without_flag
```

Copy the new log to the database directory:

```bash
cp /dev/shm/regtest_RS03i/scan_recognize_nodm_without_flag/newlog.txt regtest/database/RS03i_scan_recognize_nodm_without_flag
```

Edit per `regtest/README` conventions (remove path prefixes, set line 1/2 checksums).

- [ ] **Step 4: Verify the test passes**

```bash
REGTEST_NO_UTF8=1 ./regtest/runtests.sh RS03i_scan_recognize_nodm_without_flag
```

Expected: PASS — recognition finds the RS03 data laid out at BD_SL_SIZE_NODM layer size without requiring the flag.

- [ ] **Step 5: Commit**

```bash
git add regtest/rs03i.bash regtest/config.txt regtest/database/RS03i_scan_recognize_nodm_without_flag
git commit -m "test: add regtest for NODM image recognition without flag"
```

---

### Task 5: Run full test suite and final commit

**Files:**
- No new changes — validation only

- [ ] **Step 1: Run all regression tests**

```bash
mkdir -p /var/tmp/regtest
REGTEST_NO_UTF8=1 MAX_JOBS=4 ./regtest/runtests.sh
```

Expected: All tests pass, including the two new ones and all existing RS01/RS02/RS03f/RS03i tests.

- [ ] **Step 2: Build both GUI and CLI variants (if GTK3 is available)**

```bash
# CLI
make clean && ./configure --with-gui=no --with-werror && make -j$(nproc)
./dvdisaster --version

# GUI (only if GTK3 is installed)
make clean && ./configure --with-werror && make -j$(nproc)
./dvdisaster --version
```

Expected: Both variants compile without errors or warnings.

- [ ] **Step 3: Push**

```bash
git push origin master
```
