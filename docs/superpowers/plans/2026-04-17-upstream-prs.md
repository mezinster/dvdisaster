# Upstream PRs to speed47/dvdisaster — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare four cherry-picked branches off `speed47/master`, push them to `mezinster/dvdisaster`, and open four PRs against `speed47/dvdisaster:master` per the design spec at `docs/superpowers/specs/2026-04-17-upstream-prs-design.md`.

**Architecture:** Sequential branch construction via `git cherry-pick` (sometimes partial, via `git cherry-pick -n` followed by selective `git restore`). Build + test verification per branch. User confirmation gate before any push. PRs opened cross-repo via `gh pr create`.

**Tech Stack:** git, gh CLI, GNU make, pytest. No application code is being authored — this is git/PR plumbing only.

**Working directory:** `/home/mezinster/dvdisaster`. Master branch must be clean (no uncommitted changes) before starting.

---

## Task 1: Pre-flight verification

**Files:** None modified. Read-only inspection.

- [ ] **Step 1: Confirm working tree is clean of in-progress edits.**

```bash
git status --porcelain | grep -v '^??' || echo "clean"
```

Expected: `clean` (untracked files like `.claude/`, `tests/__pycache__/` are fine; only modified-tracked files would block us).

- [ ] **Step 2: Confirm `speed47` remote exists and is fetched.**

```bash
git remote get-url speed47 && git fetch speed47 --quiet && echo OK
```

Expected: `https://github.com/speed47/dvdisaster.git` followed by `OK`.

- [ ] **Step 3: Confirm divergence is what we expect (46 ahead, 0 behind).**

```bash
echo "ahead: $(git rev-list --count speed47/master..master)"
echo "behind: $(git rev-list --count master..speed47/master)"
```

Expected: `ahead: 46+` (may have grown since spec was written; that's fine if the new commits are also for upstream), `behind: 0`.

- [ ] **Step 4: Confirm all source commits referenced in the spec exist locally.**

```bash
for sha in f8d747f e8d34fd ab4b11d 2e2dd60 05ff5be cc00e5e ffcdc34 cc90a4e 1ab7f60 a66eb97 72f4a4a 3052f8b 8eb1b9b 9e1c113 143f642 7f02366 dad70d8 74286d5 3791e5a 0c5164b 4945835 dedff60 40ee9e6 d42a840 f1ebd28 4478ac3 4420263 30fa639 d422707 7afcf87 0b33244 8368930 091a68d f99e1ec 373d20e 5371514 6fbeb0d ef0c847; do
  git cat-file -e "$sha^{commit}" 2>/dev/null && echo "OK $sha" || echo "MISSING $sha"
done
```

Expected: All `OK`. If any `MISSING`, stop and reconcile against the spec before proceeding.

- [ ] **Step 5: Confirm `gh` is authenticated against GitHub with permission to open PRs against speed47/dvdisaster.**

```bash
gh auth status && gh repo view speed47/dvdisaster --json name,defaultBranchRef -q '.name + " / " + .defaultBranchRef.name'
```

Expected: auth status prints user; second command prints `dvdisaster / master`.

---

## Task 2: Build PR #1 branch (`upstream/rs03-recognize-fix`)

**Files:** Cherry-picks land in `src/rs03-recognize.c`, `regtest/database/*`, `debian/rules`.

**Goal commit count on this branch (above speed47/master):** 3.

- [ ] **Step 1: Create the branch off `speed47/master`.**

```bash
git checkout -B upstream/rs03-recognize-fix speed47/master
```

Expected: `Switched to a new branch 'upstream/rs03-recognize-fix'`. HEAD is at speed47/master tip.

- [ ] **Step 2: Cherry-pick `f8d747f` (the actual fix).**

```bash
git cherry-pick f8d747f
```

Expected: clean pick, single commit added. Touches only `src/rs03-recognize.c`. If conflict, **stop and surface to user**.

- [ ] **Step 3: Cherry-pick `e8d34fd` with `-n` (no-commit) to allow dropping the deb-build hunk.**

```bash
git cherry-pick -n e8d34fd
git status
```

Expected: staged changes in both `src/rs03-recognize.c` and `debian/rules`.

- [ ] **Step 4: Drop the `debian/rules` hunk from the staged cherry-pick.**

```bash
git restore --staged --worktree debian/rules
git status
```

Expected: only `src/rs03-recognize.c` remains staged. `debian/rules` shows no changes.

- [ ] **Step 5: Commit the partial pick using the original message but noting the modification.**

```bash
git commit -C e8d34fd
```

Expected: commit lands with original message. Verify only src/ touched:

```bash
git show --stat HEAD | head -5
```

Should show only `src/rs03-recognize.c`.

- [ ] **Step 6: Cherry-pick `ab4b11d` (golden file updates).**

```bash
git cherry-pick ab4b11d
```

Expected: clean pick. Touches many `regtest/database/*` files and a small `debian/rules` hunk. If conflict, **stop and surface to user**.

- [ ] **Step 7: Verify branch has exactly 3 commits ahead of speed47/master.**

```bash
git log --oneline speed47/master..HEAD
```

Expected: 3 lines, in order: `f8d747f` clone, `e8d34fd` clone (modified), `ab4b11d` clone.

- [ ] **Step 8: Verify no forbidden files are present.**

```bash
git diff --name-only speed47/master..HEAD | grep -E '^(docs/superpowers|CLAUDE\.md|\.claude/|tests/__pycache__/)' && echo "FORBIDDEN FILES PRESENT" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 9: Build CLI to verify code compiles.**

```bash
./configure --with-gui=no && make -j$(nproc) 2>&1 | tail -20
```

Expected: build succeeds, binary `./dvdisaster` exists. If failure, **stop and surface**.

- [ ] **Step 10: Snapshot the diff for the user-confirmation gate (Task 6).**

```bash
git diff --stat speed47/master..HEAD > /tmp/pr1-diffstat.txt
git log --oneline speed47/master..HEAD > /tmp/pr1-log.txt
echo "PR #1 ready"
```

---

## Task 3: Build PR #2 branch (`upstream/pytest-framework`)

**Files:** New `tests/` directory tree, `regtest/config.txt` edits, deletions of bash-only golden files.

**Goal commit count on this branch (above speed47/master):** ~22 (includes PR #1's 3 + ~19 test framework commits + 1 split commit).

- [ ] **Step 1: Create the branch off PR #1.**

```bash
git checkout -B upstream/pytest-framework upstream/rs03-recognize-fix
```

Expected: `Switched to a new branch 'upstream/pytest-framework'`.

- [ ] **Step 2: Cherry-pick the test framework + RS01/RS02 migration commits in chronological order.**

```bash
git cherry-pick 2e2dd60 05ff5be ffcdc34 cc90a4e 1ab7f60
```

Expected: 5 clean picks. If any fails, **stop and surface to user with the conflict diff**.

- [ ] **Step 3: Cherry-pick `cc00e5e` (the framework wiring fix relocated from PR #1).**

```bash
git cherry-pick cc00e5e
```

Expected: clean pick. Touches only `tests/framework.py` (7 lines).

- [ ] **Step 4: Cherry-pick the RS03f migration commits.**

```bash
git cherry-pick a66eb97 72f4a4a 3052f8b 8eb1b9b 9e1c113 143f642
```

Expected: 6 clean picks.

- [ ] **Step 5: Cherry-pick the RS03i migration commits.**

```bash
git cherry-pick 7f02366 dad70d8 74286d5 3791e5a 0c5164b 4945835
```

Expected: 6 clean picks.

- [ ] **Step 6: Cherry-pick the bash-test disablement and final docs commit.**

```bash
git cherry-pick dedff60 40ee9e6
```

Expected: 2 clean picks.

- [ ] **Step 7: Cherry-pick `d42a840` with `-n` to strip the CLAUDE.md hunk.**

```bash
git cherry-pick -n d42a840
git restore --staged --worktree CLAUDE.md
git status
```

Expected: only `tests/README.md` staged. `CLAUDE.md` reverted.

- [ ] **Step 8: Commit the partial pick.**

```bash
git commit -C d42a840
git show --stat HEAD | head -5
```

Expected: commit lands with original message; only `tests/README.md` touched.

- [ ] **Step 9: Cherry-pick `f1ebd28` with `-n` to keep only the `tests/test_rs03_recognize.py` hunk.**

```bash
git cherry-pick -n f1ebd28
git restore --staged --worktree debian/
git status
```

Expected: only `tests/test_rs03_recognize.py` staged. `debian/` files reverted.

- [ ] **Step 10: Commit the partial pick.**

```bash
git commit -C f1ebd28
git show --stat HEAD | head -5
```

Expected: only `tests/test_rs03_recognize.py` touched.

- [ ] **Step 11: Verify no forbidden files.**

```bash
git diff --name-only speed47/master..HEAD | grep -E '^(docs/superpowers|CLAUDE\.md|\.claude/|tests/__pycache__/)' && echo "FORBIDDEN" || echo "clean"
```

Expected: `clean`. If `CLAUDE.md` shows up here, the strip in Steps 7 or 9 didn't take — investigate.

- [ ] **Step 12: Build CLI.**

```bash
make distclean && ./configure --with-gui=no && make -j$(nproc) 2>&1 | tail -20
```

Expected: build succeeds.

- [ ] **Step 13: Run pytest (fast tests only, all codecs).**

```bash
pip install --user --quiet pytest 2>/dev/null || true
python3 -m pytest tests/ -v --ignore=tests/__pycache__ 2>&1 | tail -30
```

Expected: all fast tests pass (slow tests not yet marked at this point in history — that's PR #3). First run will be slow (~3GB image creation in `/var/tmp/regtest/`).

- [ ] **Step 14: Snapshot diff.**

```bash
git diff --stat speed47/master..HEAD > /tmp/pr2-diffstat.txt
git log --oneline speed47/master..HEAD > /tmp/pr2-log.txt
echo "PR #2 ready"
```

---

## Task 4: Build PR #3 branch (`upstream/ci-pytest-integration`)

**Files:** `.github/workflows/tests.yml`, `.github/workflows/release.yml`, slow markers in `tests/test_rs02.py` / `tests/test_rs03i.py` / `tests/conftest.py`, new `docs/workflow_readme.md`.

**Goal commit count on this branch (above speed47/master):** ~34 (PR #2's commits + ~12 CI commits + 1 doc commit).

- [ ] **Step 1: Create the branch off PR #2.**

```bash
git checkout -B upstream/ci-pytest-integration upstream/pytest-framework
```

- [ ] **Step 2: Cherry-pick the CI integration commits in chronological order.**

```bash
git cherry-pick 4478ac3 4420263 30fa639 d422707 7afcf87 0b33244 8368930 091a68d f99e1ec 373d20e 5371514
```

Expected: 11 clean picks.

- [ ] **Step 3: Create the new `docs/workflow_readme.md` file.**

```bash
mkdir -p docs
```

Then write the file content:

```markdown
# CI Workflow Reference

This document describes the GitHub Actions workflows in `.github/workflows/`. Each workflow has a single coherent purpose; this file explains the orchestration that's not obvious from the YAML alone.

## tests.yml — Regression tests

Triggered on push and pull_request. Runs the pytest suite (`tests/`) on Linux, macOS (x86_64 + arm64), and Windows (MSYS2/MINGW64), for both CLI and GUI build variants. The full pytest suite is gated:

- **PR / push events**: fast tests only. Runs in ~5–10 minutes per platform.
- **Scheduled cron, release tags (`v*`), and manual `workflow_dispatch`**: full suite including slow tests (large-image RS02 / RS03i tests).

Slow tests are marked with `@pytest.mark.slow` in `tests/test_rs02.py` and `tests/test_rs03i.py`. The `--run-slow` pytest option (defined in `tests/conftest.py`) opts them in; CI passes it conditionally.

The first test run on any host creates ~3GB of master images in `/var/tmp/regtest/` and reuses them on subsequent runs. CI caches this directory between runs to save startup time.

## release.yml — Multi-platform release builds

Triggered on push to master/dev and on `v*` tags. Produces:

- `linux64-cli` — static CLI binary
- `linux64-deb` — Debian package
- `linux64-appimage` — AppImage built inside `ubuntu:18.04` Docker container
- `win (cli)` / `win (gui)` — Windows binaries via MSYS2/MINGW64
- `mac (cli, x86_64 / arm64)` / `mac (gui, x86_64 / arm64)` — macOS binaries

A `prepare-tag` job runs first to avoid tag race conditions between parallel platform builds.

### AppImage build note

The AppImage job intentionally builds inside `ubuntu:18.04` (Bionic) to keep the resulting AppImage's glibc dependency at 2.27 — the lowest common denominator across modern Linux distros, which maximizes downstream compatibility.

Bionic reached end-of-standard-support on 2023-04-30. The main, updates, and backports apt pockets were moved off `archive.ubuntu.com` to `old-releases.ubuntu.com`. The "install prerequisites in docker" step rewrites `/etc/apt/sources.list` to point at `old-releases.ubuntu.com` before `apt update` so package installation succeeds. The `bionic-security` pocket on `security.ubuntu.com` is also rewritten for consistency.

## codeql.yml — Static analysis

Triggered on push, pull_request, and weekly cron. Runs CodeQL static analysis. No special configuration.

## stale.yml — Issue housekeeping

Triggered on daily cron. Auto-closes issues labeled `needs-more-info` or `answered` after a quiet period.
```

Save this content to `docs/workflow_readme.md` using your editor / Write tool. Then:

```bash
ls -l docs/workflow_readme.md
```

Expected: file exists, ~50 lines.

- [ ] **Step 4: Commit the workflow README.**

```bash
git add docs/workflow_readme.md
git commit -m "$(cat <<'EOF'
docs: add CI workflow reference at docs/workflow_readme.md

Documents each workflow's purpose, the slow-test gating strategy, and
the AppImage / bionic-EOL apt-rewrite rationale. Establishes a new
docs/ directory in the upstream tree.

EOF
)"
```

- [ ] **Step 5: Verify no forbidden files.**

```bash
git diff --name-only speed47/master..HEAD | grep -E '^(docs/superpowers|CLAUDE\.md|\.claude/|tests/__pycache__/)' && echo "FORBIDDEN" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 6: Build CLI.**

```bash
make distclean && ./configure --with-gui=no && make -j$(nproc) 2>&1 | tail -20
```

Expected: build succeeds.

- [ ] **Step 7: Run pytest with slow tests excluded (default).**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -30
```

Expected: passes; slow tests are skipped.

- [ ] **Step 8: Snapshot diff.**

```bash
git diff --stat speed47/master..HEAD > /tmp/pr3-diffstat.txt
git log --oneline speed47/master..HEAD > /tmp/pr3-log.txt
echo "PR #3 ready"
```

---

## Task 5: Build PR #4 branch (`upstream/misc-improvements`)

**Files:** Only `src/dvdisaster.c`, `src/rs03-common.c`, `src/dvdisaster.h`. Optionally `debian/control`.

**Goal commit count on this branch (above speed47/master):** 2.

- [ ] **Step 1: Create the branch off `speed47/master` (independent of #1, #2, #3).**

```bash
git checkout -B upstream/misc-improvements speed47/master
```

- [ ] **Step 2: Cherry-pick `6fbeb0d` with `-n` to keep only the src/ hunks (`--medium-size` flag).**

```bash
git cherry-pick -n 6fbeb0d
git restore --staged --worktree .github/workflows/
git status
```

Expected: only `src/dvdisaster.c` and `src/rs03-common.c` staged.

- [ ] **Step 3: Commit the partial pick.**

```bash
git commit -C 6fbeb0d
git show --stat HEAD | head -5
```

Expected: only the two src/ files touched.

- [ ] **Step 4: Cherry-pick `ef0c847` with `-n` to keep only `src/dvdisaster.h` (and optionally `debian/control`).**

```bash
git cherry-pick -n ef0c847
git restore --staged --worktree .github/workflows/ CLAUDE.md
git status
```

Expected: `src/dvdisaster.h` and `debian/control` staged. (Decide on debian/control inclusion below.)

- [ ] **Step 5: Decide on `debian/control` inclusion.**

Look at the diff:

```bash
git diff --staged debian/control
```

If the change is generic packaging metadata that benefits upstream's debian build, keep it. If it's mezinster-specific (e.g., maintainer field changes, fork-specific dependencies), drop it:

```bash
git restore --staged --worktree debian/control
```

- [ ] **Step 6: Commit the partial pick.**

```bash
git commit -C ef0c847
git show --stat HEAD | head -5
```

Expected: only `src/dvdisaster.h` (and optionally `debian/control`).

- [ ] **Step 7: Verify branch has exactly 2 commits ahead of speed47/master.**

```bash
git log --oneline speed47/master..HEAD
```

Expected: 2 lines.

- [ ] **Step 8: Verify no forbidden files.**

```bash
git diff --name-only speed47/master..HEAD | grep -E '^(\.github/|docs/superpowers|CLAUDE\.md|\.claude/|tests/|regtest/|CHANGELOG)' && echo "FORBIDDEN" || echo "clean"
```

Expected: `clean`. PR #4 should touch only `src/` and possibly `debian/control` — nothing else.

- [ ] **Step 9: Build CLI.**

```bash
make distclean && ./configure --with-gui=no && make -j$(nproc) 2>&1 | tail -20
```

Expected: build succeeds.

- [ ] **Step 10: Snapshot diff.**

```bash
git diff --stat speed47/master..HEAD > /tmp/pr4-diffstat.txt
git log --oneline speed47/master..HEAD > /tmp/pr4-log.txt
echo "PR #4 ready"
```

---

## Task 6: User confirmation gate (CHECKPOINT — DO NOT PROCEED WITHOUT APPROVAL)

**Files:** None modified. Display only.

- [ ] **Step 1: Display the diff summaries for all four branches to the user.**

```bash
echo "=== PR #1 (rs03-recognize-fix) ==="; cat /tmp/pr1-log.txt; echo; cat /tmp/pr1-diffstat.txt
echo; echo "=== PR #2 (pytest-framework) ==="; cat /tmp/pr2-log.txt; echo; cat /tmp/pr2-diffstat.txt
echo; echo "=== PR #3 (ci-pytest-integration) ==="; cat /tmp/pr3-log.txt; echo; cat /tmp/pr3-diffstat.txt
echo; echo "=== PR #4 (misc-improvements) ==="; cat /tmp/pr4-log.txt; echo; cat /tmp/pr4-diffstat.txt
```

- [ ] **Step 2: Display the proposed PR titles and ask the user to approve push + open.**

Show the user:
- PR #1 title: `fix: RS03 recognize tries all known medium sizes as candidates`
- PR #2 title: `enh: add Python pytest framework and migrate regression tests`
- PR #3 title: `enh: integrate pytest into CI and add slow-test gating`
- PR #4 title: `enh: --medium-size CLI flag and macro precedence fix`

**Wait for explicit user approval before proceeding to Task 7.** If the user requests changes, return to the relevant task and re-build that branch.

---

## Task 7: Push branches and open PRs

**Files:** None modified locally. Network operations only.

- [ ] **Step 1: Push all four branches to mezinster's fork.**

```bash
git push origin upstream/rs03-recognize-fix upstream/pytest-framework upstream/ci-pytest-integration upstream/misc-improvements
```

Expected: 4 branches pushed. No force-push. If any push is rejected (e.g., remote already has the branch), **stop and surface to user**.

- [ ] **Step 2: Open PR #1.**

```bash
gh pr create --repo speed47/dvdisaster \
  --base master \
  --head mezinster:upstream/rs03-recognize-fix \
  --title "fix: RS03 recognize tries all known medium sizes as candidates" \
  --body "$(cat <<'EOF'
## Summary

Fix for RS03 recognition failing on augmented images whose medium size differs from the default. Previously the recognize routine tried only one candidate medium size; now it iterates through all known sizes.

## Changes

- `src/rs03-recognize.c`: candidate-loop implementation, with verbose-output suppression so single-image scans don't get noisier
- `regtest/database/*`: golden file updates (the candidate loop changes verbose output across many bash test scenarios)
- `debian/rules`: small companion change

## Backward compatibility

Existing single-size augmented images continue to be recognized identically. The change is additive — new candidate sizes are tried only when the original lookup fails.

## Coordinated PR set

This PR is part of a coordinated set of four PRs from mezinster/dvdisaster. **Recommended merge order:**

1. **#1 (this PR) — RS03 recognize fix** — merge first
2. **#2 — pytest framework + test migration** — depends on #1 for recognize-related tests to pass
3. **#3 — CI pytest integration + workflow docs** — depends on #2 for pytest to exist
4. **#4 — `--medium-size` flag + macro precedence fix** — independent, can merge any time

Cross-reference: PRs #2, #3, #4 will be linked here once opened.
EOF
)"
```

Capture the PR URL from the output and save it to `/tmp/pr1-url.txt`.

- [ ] **Step 3: Open PR #2.**

```bash
gh pr create --repo speed47/dvdisaster \
  --base master \
  --head mezinster:upstream/pytest-framework \
  --title "enh: add Python pytest framework and migrate regression tests" \
  --body "$(cat <<'EOF'
## Summary

Adds a Python/pytest regression test framework and migrates all 424 tests from the legacy bash-based `regtest/` framework. Bash tests are disabled in `regtest/config.txt` but the directory and golden files are kept for reference.

## Why

- **Declarative test definitions**: the new framework uses `GoldenTest` / `SimCD` / `CreateECC` dataclasses to express tests compactly
- **IDE / pytest discoverable**: per-test execution via standard pytest selectors
- **Parallelism-friendly**: `pytest -n auto` works out of the box
- **Golden-file format unchanged**: existing `regtest/database/*` files are reused as-is

## What's preserved

- Existing golden files in `regtest/database/` are still authoritative
- The bash framework code stays in `regtest/` for reference
- All 424 regression scenarios are migrated 1:1

## What's new

- `tests/framework.py` — the GoldenTest DSL and runner
- `tests/conftest.py` — pytest fixtures (master image cache, build location)
- `tests/test_rs01.py`, `test_rs02.py`, `test_rs03f.py`, `test_rs03i.py`, `test_rs03_recognize.py`, `test_multipass_read.py` — codec-specific tests
- `tests/test_framework.py` — unit tests for the DSL itself
- `tests/README.md` — developer documentation

## Cache

Master images are created in `/var/tmp/regtest/` on first run (~3GB) and reused thereafter. CI caches this directory between runs.

## Coordinated PR set

Part of a four-PR series. **Recommended merge order:**

1. #1 — RS03 recognize fix — merge first (link to be added)
2. **#2 (this PR) — pytest framework** — depends on #1 for recognize tests to pass
3. #3 — CI pytest integration — depends on this PR
4. #4 — `--medium-size` flag + macro precedence fix — independent
EOF
)"
```

Capture the PR URL to `/tmp/pr2-url.txt`.

- [ ] **Step 4: Open PR #3.**

```bash
gh pr create --repo speed47/dvdisaster \
  --base master \
  --head mezinster:upstream/ci-pytest-integration \
  --title "enh: integrate pytest into CI and add slow-test gating" \
  --body "$(cat <<'EOF'
## Summary

Wires the new pytest framework (PR #2) into GitHub Actions, adds a `@pytest.mark.slow` gate for large-image tests, and documents the workflow design in a new `docs/workflow_readme.md` file.

## Changes

- `.github/workflows/tests.yml`: pytest now runs on Linux/macOS/Windows for CLI builds. Slow tests opt-in via `--run-slow`.
- `.github/workflows/release.yml`: AppImage build's bionic apt sources rewritten to `old-releases.ubuntu.com` (Bionic reached EOL 2023-04-30 and was relocated; previously the docker `apt update` step failed with connection timeouts).
- `tests/conftest.py`: registers the `--run-slow` option and the `slow` marker.
- `tests/test_rs02.py`, `tests/test_rs03i.py`: ~40 large-image tests marked slow.
- `docs/workflow_readme.md`: **new file**, documents each workflow's purpose, the slow-test schedule, the test-image cache, and the bionic-EOL rationale.

## New convention

This PR establishes a new top-level `docs/` directory. Currently upstream uses `documentation/` for PDFs but has no markdown documentation tree. The new file lives at `docs/workflow_readme.md` rather than `.github/workflows/README.md` to keep contributor-facing docs in a discoverable location.

## Slow-test schedule

- **PR / push events**: fast tests only (~5–10 min per platform)
- **Scheduled cron, release tags (`v*`), manual workflow_dispatch**: full suite including slow tests

## Coordinated PR set

Part of a four-PR series. **Recommended merge order:**

1. #1 — RS03 recognize fix — merge first
2. #2 — pytest framework — depends on #1
3. **#3 (this PR) — CI integration** — depends on #2 for pytest to exist
4. #4 — `--medium-size` + macro precedence — independent
EOF
)"
```

Capture URL to `/tmp/pr3-url.txt`.

- [ ] **Step 5: Open PR #4.**

```bash
gh pr create --repo speed47/dvdisaster \
  --base master \
  --head mezinster:upstream/misc-improvements \
  --title "enh: --medium-size CLI flag and macro precedence fix" \
  --body "$(cat <<'EOF'
## Summary

Two unrelated but small src/-only improvements bundled for review economy:

1. **`--medium-size` CLI flag** (`src/dvdisaster.c`, `src/rs03-common.c`): explicit medium-size override on the command line. Useful when the auto-detected size needs to be forced (e.g., for testing or for unusual augmented images).
2. **Macro precedence fix** (`src/dvdisaster.h`): corrects parenthesization in a few macros that could expand incorrectly when used inside complex expressions.

## Independent of the other coordinated PRs

This PR has no test framework dependency and no CI dependency. It can merge any time, in any order relative to PRs #1, #2, #3.

## Coordinated PR set

This branch is one of four coordinated PRs from mezinster/dvdisaster. The others are #1 (RS03 recognize fix), #2 (pytest framework), #3 (CI integration). Merge order is flexible for this PR.
EOF
)"
```

Capture URL to `/tmp/pr4-url.txt`.

- [ ] **Step 6: Cross-link the PRs.**

For each of PR #1–#4, edit the PR description to replace `(link to be added)` placeholders with the actual URLs from the previous steps.

```bash
PR1=$(cat /tmp/pr1-url.txt | tr -d '\n')
PR2=$(cat /tmp/pr2-url.txt | tr -d '\n')
PR3=$(cat /tmp/pr3-url.txt | tr -d '\n')
PR4=$(cat /tmp/pr4-url.txt | tr -d '\n')

gh pr edit "$PR1" --repo speed47/dvdisaster --body "$(gh pr view "$PR1" --repo speed47/dvdisaster --json body -q .body | sed -e "s|(link to be added)|$PR2|" -e "s|will be linked here once opened|$PR2 $PR3 $PR4|")"
```

Repeat the equivalent edit for PRs #2, #3, #4 — substituting the relevant cross-links into each body.

(If `sed`-based body editing is fragile, a simpler manual approach is to open each PR in the browser via `gh pr view <url> --web` and edit the body directly. Document which approach was used.)

---

## Task 8: Post-push verification

**Files:** None. Reporting only.

- [ ] **Step 1: Confirm all 4 PRs are open and visible on speed47/dvdisaster.**

```bash
gh pr list --repo speed47/dvdisaster --author mezinster --limit 10
```

Expected: 4 open PRs.

- [ ] **Step 2: Report URLs to the user and stop.**

Per user preference, do NOT poll the PR conversations or watch CI runs. Just report the four URLs and stand by.

---

## Self-Review

**Spec coverage:** Each spec PR has at least one task: PR #1 → Task 2, PR #2 → Task 3, PR #3 → Task 4, PR #4 → Task 5. Verification is in Tasks 2–5 + 8. Confirmation gate is Task 6. Push/open is Task 7.

**Placeholder scan:** No "TBD" or "fill in" markers. The cross-link sed in Task 7 Step 6 is fragile — explicit fallback noted (browser edit). The `docs/workflow_readme.md` content is fully spelled out in Task 4 Step 3 (no "see spec" references).

**Type/identifier consistency:** Branch names `upstream/rs03-recognize-fix` / `upstream/pytest-framework` / `upstream/ci-pytest-integration` / `upstream/misc-improvements` used consistently in tasks and `gh pr create` head args. PR titles match between the user-facing approval gate (Task 6) and the actual `gh pr create` titles (Task 7).

**Risk reminders for the executing engineer:**
- If a cherry-pick conflicts, **stop and surface to user** — do not guess a resolution.
- If the AppImage workflow change in PR #3 introduces a path/identifier that upstream's CI doesn't have, the PR may not validate cleanly until upstream merges its half. That's expected; the code is still correct.
- The cross-link step (Task 7 Step 6) can be done after-the-fact if it fails.
