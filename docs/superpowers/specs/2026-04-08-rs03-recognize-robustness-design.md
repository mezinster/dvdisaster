# RS03 Recognition Robustness: Unified Candidate Search

## Problem

RS03 recognition fails in two real-world scenarios:

1. **BD-RE read-back mismatch (upstream #97):** An RS03 augmented image created for DVD_DL_SIZE (~8 GB) is burned to a BD-RE 25 GB disc. Reading back produces an image with ~12M sectors (BD capacity). The recognize path uses `image_sectors < BD_SL_SIZE` to guess the layer size, yielding `BD_SL_SIZE / 255` — but the actual ECC data was laid out for `DVD_DL_SIZE / 255`. Recognition fails, and the ECC data becomes inaccessible despite being physically present.

2. **DM/NODM flag dependency (upstream #69):** An image created with `BD_SL_SIZE_NODM` (via `--no-bdr-defect-management`) cannot be recognized unless the same flag is passed at recognition time. The recognize path gates BD sizes behind `Closure->noBdrDefectManagement`, trying only one variant per BD tier. If the flag is forgotten — possibly years later when trying to recover a damaged disc — the ECC data is invisible.

Both issues share a root cause: the recognize path tries a **single** layer size guess based on the total image sector count, instead of searching across all plausible layer sizes.

## Solution

Replace the single-guess layer size selection in `RS03RecognizeImage()` with a multi-candidate search loop. Each candidate layer size is validated by `search_crc_blocks_for_layer_size()`, which reads 1-3 sectors and checks CRC signatures. Wrong guesses fail fast and cheaply.

### Candidate List

All candidates are expressed as `medium_capacity / GF_FIELDMAX` (i.e., `/ 255`):

| Priority | Candidate | Rationale |
|----------|-----------|-----------|
| 0 | `Closure->mediumSize` | User override via `-n`, already handled separately |
| 1 | `image_sectors / 255` (+/- 1) | Exact match for complete, unpadded images |
| 2 | `DVD_DL_SIZE` | Most common "wrong" medium for mid-size images |
| 3 | `BD_SL_SIZE` | Standard BD 25 GB |
| 4 | `BD_SL_SIZE_NODM` | BD 25 GB without defect management |
| 5 | `DVD_SL_SIZE` | Standard DVD |
| 6 | `BD_DL_SIZE` | BD 50 GB |
| 7 | `BD_DL_SIZE_NODM` | BD 50 GB without defect management |
| 8 | `CDR_SIZE` | CD-R |
| 9 | `BDXL_TL_SIZE` | BDXL 100 GB |
| 10 | `BDXL_TL_SIZE_NODM` | BDXL 100 GB without defect management |
| 11 | `BDXL_QL_SIZE` | BDXL 128 GB |
| 12 | `BDXL_QL_SIZE_NODM` | BDXL 128 GB without defect management |

Deduplication: skip any candidate whose computed `layer_size` matches one already tried.

### Quick Search vs Exhaustive Search

The current code has two modes:
- **Quick** (`maxtries = 3`): Optical media without `--examine-rs03`. Limits sector reads.
- **Exhaustive** (`maxtries = -1`): File images or when `--examine-rs03` is set.

Design for each mode:

**Quick mode (optical media):**
- First, try the current heuristic (`image_sectors < X`) as candidate 0 — this is usually correct since the drive's READ CAPACITY matches the medium type.
- If that fails, try the DM/NODM counterpart of the same tier (e.g., if `BD_SL_SIZE` failed, try `BD_SL_SIZE_NODM`).
- If that fails, try the image-derived size (`image_sectors / 255`).
- Stop after these 3 candidates. This keeps optical drive reads under ~10 sectors total.

**Exhaustive mode (file images):**
- Try all candidates in the full priority list above.
- Then fall through to bruteforce scan if enabled (unchanged).

### Changes to `noBdrDefectManagement` in Recognize

The `Closure->noBdrDefectManagement` flag is **removed from the recognize path entirely**. Both DM and NODM sizes are always candidates. The flag retains its meaning only in:
- `rs03-common.c` `CalcRS03Layout()` — creation-time size selection
- `rs03-create.c` — NODM warning dialog
- `dvdisaster.c` — CLI flag parsing

## Files Modified

### `src/rs03-recognize.c` — `RS03RecognizeImage()`

**Lines 718-737** (Phase 0 single-guess): Replace with candidate loop.

Before:
```c
const guint64 bd_sl_sz = (Closure->noBdrDefectManagement ? BD_SL_SIZE_NODM : BD_SL_SIZE);
// ... single if/else chain picking one layer_size ...
if(search_crc_blocks_for_layer_size(...))
   return TRUE;
```

After (pseudocode):
```c
/* Build candidate list of layer sizes to try */
guint64 candidates[16];
int n_candidates = 0;

/* Image-derived (strong heuristic for complete images) */
add_candidate(candidates, &n_candidates, image_sectors / GF_FIELDMAX);

/* All known medium sizes — both DM and NODM variants */
add_candidate(candidates, &n_candidates, DVD_DL_SIZE / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, BD_SL_SIZE / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, BD_SL_SIZE_NODM / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, DVD_SL_SIZE / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, BD_DL_SIZE / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, BD_DL_SIZE_NODM / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, CDR_SIZE / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, BDXL_TL_SIZE / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, BDXL_TL_SIZE_NODM / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, BDXL_QL_SIZE / GF_FIELDMAX);
add_candidate(candidates, &n_candidates, BDXL_QL_SIZE_NODM / GF_FIELDMAX);

/* For quick mode (optical media), limit to first 3 candidates */
int max_candidates = (maxtries < 0) ? n_candidates : 3;

for(int i = 0; i < max_candidates; i++)
{  trynumber = 0;  /* reset per candidate */
   if(search_crc_blocks_for_layer_size(image, image_sectors, candidates[i], maxtries, &trynumber))
      return TRUE;
}
```

The `add_candidate()` helper deduplicates (skips if `layer_size` already in the array) and skips zero.

For quick mode on optical media, the candidate list is reordered to put the heuristic guess first:
```c
if(image->type == IMAGE_MEDIUM)
{  /* Put the READ CAPACITY-based guess first for optical media */
   guint64 heuristic = heuristic_layer_size(image_sectors);
   add_candidate(candidates, &n_candidates, heuristic);
   add_candidate(candidates, &n_candidates, nodm_counterpart(heuristic));
   add_candidate(candidates, &n_candidates, image_sectors / GF_FIELDMAX);
}
```

**Lines 745-760** (Phase 1 image-derived): Removed — subsumed into the candidate list above.

**Lines 767-771** (Phase 2 bruteforce): Unchanged.

### `src/rs03-recognize.c` — new helper functions

```c
/* Add a layer_size candidate if not zero and not already present */
static void add_candidate(guint64 *candidates, int *n, guint64 layer_size);

/* Current heuristic: pick layer size from image_sectors using < thresholds */
static guint64 heuristic_layer_size(guint64 image_sectors);

/* Return the DM/NODM counterpart of a layer_size, or 0 if none */
static guint64 nodm_counterpart(guint64 layer_size);
```

### No changes to

- `rs03-common.c` — creation logic unchanged
- `rs03-create.c` — creation warnings unchanged
- `rs03-verify.c` — uses recognized header
- `rs03-preferences.c` — GUI unchanged
- `dvdisaster.h` — constants unchanged
- `closure.c` — defaults unchanged

## Test Plan

### Existing tests

All existing RS03 regtests must pass unchanged. The new candidate loop tries the same sizes as before (just more of them), and the first valid match wins.

### New regression tests

Add to `regtest/rs03i.bash`:

1. **BD-RE read-back mismatch:** Create RS03 augmented image at `DVD_DL_SIZE`, pad image file with zero sectors to `BD_SL_SIZE` total, verify `--scan` recognizes the ECC data.

2. **NODM without flag:** Create RS03 augmented image with `-n BDNODM`, then verify/scan **without** `--no-bdr-defect-management` flag. Must succeed.

3. **DM image at NODM size:** Create RS03 augmented image at `BD_SL_SIZE` (standard), pad to `BD_SL_SIZE_NODM`, verify recognition.

4. **Custom -n value:** Create RS03 augmented image with `-n 5000000`, verify recognition works without specifying `-n` at scan time.

All tests use `--sim-cd` and `--debug` for simulated optical media, following existing regtest patterns.

## Risk Assessment

**Low risk.** The `search_crc_blocks_for_layer_size()` function validates candidates via CRC — wrong guesses are rejected definitively. The change cannot cause false positives (accepting wrong ECC data) because the CRC check is authoritative. The only behavioral change is that images which previously failed to recognize will now succeed.

**Performance:** Worst case (no RS03 data at all, exhaustive mode) adds ~12 candidates x 2-3 sector reads = ~30 extra reads. For file images on SSD this is sub-millisecond. For optical media, quick mode limits to 3 candidates.

**Backwards compatibility:** Fully backwards compatible. Images created by any version of dvdisaster (upstream or fork) will be recognized. No on-disc format changes.
