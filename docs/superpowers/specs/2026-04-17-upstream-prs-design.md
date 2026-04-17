# Upstream PRs to speed47/dvdisaster — Design

**Date:** 2026-04-17
**Status:** Approved (pending spec review)
**Target upstream:** `speed47/dvdisaster` (GitHub) — the active maintained fork that `mezinster/dvdisaster` is built on.

## Goal

Land mezinster/dvdisaster's accumulated work back into speed47/dvdisaster as a coordinated set of focused PRs. The work consists of three subsystems plus miscellaneous fixes, totaling 46 commits ahead / 0 behind upstream.

## Context

- Local divergence: 46 commits ahead of `speed47/master`, 0 behind. Clean linear history; no rebase or merge resolution against upstream needed.
- Net diff: +14,497 / −21,978 lines across 63 files. The deletions are concentrated in `regtest/database/` golden files that the new pytest framework no longer references.
- Internal artifacts that must NOT go upstream: `docs/superpowers/**`, `CLAUDE.md`, `.claude/`, `tests/__pycache__/`.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Number of PRs | Four | Each PR has a single coherent purpose; speed47 maintainer prefers focused review. |
| Branch base | PR #1, #2, #3 stacked in dependency order; PR #4 branched directly off `speed47/master` | PR #2 depends on PR #1 (recognize tests would fail otherwise); PR #3 depends on PR #2 (CI invokes pytest). PR #4 is independent and can merge any time. |
| PR cadence | Open all four simultaneously | User chose simultaneous opening over sequential to surface the full picture at once. Each PR description states the merge order. |
| Cherry-pick vs rebase | Explicit `git cherry-pick` per branch | Better audit trail than interactive rebase; easier conflict recovery. |
| Where branches live | `mezinster/dvdisaster` fork only | Standard fork→upstream PR flow; no push permission to upstream. |
| Doc strategy | Per-PR docs only; no new top-level CONTRIBUTING.md | Each PR is reviewable on its own merits. Avoid arguing about doc conventions across multiple subsystems. |
| Workflow README location | `docs/workflow_readme.md` (new top-level `docs/` directory) | User-specified. Establishes a new directory in upstream — flag this explicitly in PR #3 description. |

## PR Layout

### PR #1 — `fix: RS03 recognize tries all known medium sizes as candidates`

**Branch:** `upstream/rs03-recognize-fix` based on `speed47/master`.

**Source commits (cherry-picked in order):**
- `f8d747f` — fix: RS03 recognize tries all known medium sizes as candidates
- `e8d34fd` — fix: suppress verbose noise from RS03 candidate loop *(drop deb-build hunk if mixed in)*
- `cc00e5e` — fix: wire CreateECC output/ecc_size fields, fix path stripping fidelity *(confirmed in scope)*
- `ab4b11d` — fix: update regtest golden files for multi-candidate RS03 recognize *(only bash-test golden file changes)*

**Files touched:** `src/rs03-recognize.c`, `src/rs03-common.c`, `src/dvdisaster.c`, `src/dvdisaster.h`, selected `regtest/database/RS03i_*` golden files.

**Docs:** PR description only. Explains the bug (single-medium-size recognition fails when image is augmented to a different size), the fix (try all known sizes as candidates), and backward-compat (existing single-size images still recognized).

### PR #2 — `enh: add Python pytest framework and migrate regression tests`

**Branch:** `upstream/pytest-framework` based on `upstream/rs03-recognize-fix`.

**Source commits (~20):** From `2e2dd60` (initial pytest framework) through `d42a840` (final tests/README + CLAUDE.md update). The CLAUDE.md hunk must be stripped from the cherry-pick.

**Files touched:** New `tests/` directory (framework.py, conftest.py, test_rs01.py, test_rs02.py, test_rs03f.py, test_rs03i.py, test_rs03_recognize.py, test_multipass_read.py, test_framework.py, README.md). `regtest/config.txt` edits to disable bash tests. Deletion of large bash-only golden files no longer referenced.

**Docs in this PR:** `tests/README.md` (already exists in fork, ports as-is). PR description explains: motivation (declarative tests, parallelism, IDE discovery), preserved compatibility (golden file format unchanged), removed (bash test machinery), the `/var/tmp/regtest` cache, and how to run tests locally.

### PR #3 — `enh: integrate pytest into CI and add slow-test gating`

**Branch:** `upstream/ci-pytest-integration` based on `upstream/pytest-framework`.

**Source commits (~12):** From `4478ac3` (pytest in macOS/Windows CI) through `5371514` (bionic apt sources fix in AppImage build).

**Files touched:** `.github/workflows/tests.yml`, `.github/workflows/release.yml`, plus pytest `slow` marker additions in `tests/test_rs02.py`, `tests/test_rs03i.py`, `tests/conftest.py`. New file `docs/workflow_readme.md`.

**Docs in this PR:**
- `docs/workflow_readme.md` (~50 lines): each workflow's purpose, the slow-test schedule (PR/push runs fast tests; cron / release-tag / manual-dispatch runs full suite), the `/var/tmp/regtest` cache strategy, the bionic-EOL apt-rewrite rationale.
- Inline YAML comments on the non-obvious bits (already present from prior commits).
- PR description flags the new `docs/` directory as an intentional convention.

### PR #4 — `enh: misc improvements (--medium-size flag, deb build, Windows GUI changelog)`

**Branch:** `upstream/misc-improvements` based on `speed47/master` (independent of #1, #2, #3).

**Source commits (split / partial cherry-picks):**
- `6fbeb0d` — keep `--medium-size` CLI flag and dist-duplicate fix; drop deb-build-speedup hunk (covered by `7e96fa1`).
- `7e96fa1` — keep deb build pdflatex fix and regtest image creation optimization; drop `regtest/` hunk (covered by PR #2's full bash-test removal).
- `8202182` — keep Windows GUI changelog visibility fix; drop CHANGELOG hunk (mezinster-specific).
- `ef0c847` — split: keep the `src/` macro-precedence half; drop "CI/CD improvements for fork" half.

**Files touched:** `src/` files (macro fix, --medium-size flag, Windows GUI fix), packaging files (deb build).

**Docs:** PR description only — itemized list of what's bundled and why each item is small enough to share a PR.

## Verification (per branch, before push)

1. `./configure --with-gui=no && make -j$(nproc)` — CLI build succeeds.
2. `./configure && make -j$(nproc)` — GUI build succeeds (skip if local GTK3 unavailable; rely on CI).
3. PR #2 onward: `python3 -m pytest tests/ -v` (fast tests only) passes.
4. `git log --stat speed47/master..HEAD` — diff matches expectations.
5. `git diff speed47/master..HEAD -- '*.c' '*.h'` — eyeball C-code changes per branch to catch unrelated drift.
6. Confirm `docs/superpowers/`, `CLAUDE.md`, `.claude/`, `tests/__pycache__/` are absent from every branch.

## Cherry-pick Conflict Handling

- If a cherry-pick fails, **stop and surface the conflict** rather than guessing a resolution. Original commits assumed mezinster's accumulated state; upstream may have moved things.
- Likely conflict point: `regtest/database/` golden files if upstream has touched them.
- Likely-clean: pure-additive files (`tests/*.py`, new workflows) — net new, no conflict expected.

## PR Opening

- Push all four branches to `mezinster/dvdisaster` via `git push origin upstream/<branch>`. No force-push.
- Open four PRs against `speed47/dvdisaster:master` via `gh pr create --repo speed47/dvdisaster --head mezinster:upstream/<branch>`.
- Each PR description includes a merge-order block:
  > This PR is part of a coordinated set:
  > 1. PR #1 (RS03 recognize fix) — merge first
  > 2. PR #2 (pytest framework) — depends on #1 for recognize-related tests to pass
  > 3. PR #3 (CI integration) — depends on #2 for pytest to exist
  > 4. PR #4 (misc improvements) — independent, can merge any time
- PR descriptions cross-link to the other three.

## Confirmation Gates

User explicitly confirms before any push:
- The list of files / diff per branch.
- The PR title and body for each (drafts before opening).

## Out of Scope

- Modifications to `documentation/` (the upstream PDFs).
- Any changes to upstream repo settings, labels, or CI beyond what the four PRs introduce.
- Mezinster-specific CI/CD improvements that aren't relevant to upstream's build matrix.
- A 5th PR for `ef0c847`'s "CI/CD improvements for fork" half — those are fork-specific.

## Open Questions

None at design time. Any cherry-pick conflict that arises will be surfaced to the user for resolution rather than guessed.
