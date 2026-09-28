# TASK-537 — GLM Independent Verification: TASK-435

## Target

    task            TASK-435
    branch          origin/glm-review-504-task-387
    branch HEAD SHA f3b68bf849d8361fab9d3f8f972229369cf60944

TASK-435 reviewed TASK-246 (enrollment tag coverage preflight wired into
`push.run()`). TASK-435's verdict was **REWORK**: the code and wiring are
correct, but the two `PushReportsTagCoverage` wiring tests use `hasattr` and
`assertIs` — patterns QWEN.md explicitly prohibits as proof. This verdict
independently verifies every finding TASK-435 made.

**Review worktree:** `.qwen/worktrees/task537-review` (detached at `f3b68bf8`)
**Code verification worktree:** was `.qwen/worktrees/task537-code` (detached at `8db92715`, now removed)
**START_MASTER_SHA:** `1d9b8f6c` (current master at review time)

---

## Summary

**DISPOSITION: TASK-435's REWORK verdict is CORRECT.**

Every material finding in TASK-435's review is independently confirmed. The
central claim — that the two wiring tests are not falsifiable — was verified
by performing the mutation TASK-435 described: removing the
`enrollmenttags.preflight()` call and `tag_coverage` return key from
`push.py`. Both wiring tests still passed. The tests prove the import exists,
not that the function is called.

One minor inaccuracy was found in TASK-435's Finding 7 (deletion risk): two
of the three "deleted" TODO files DO exist on master in TODO/ and are moved
to REVIEW/ on the branch. The conclusion (no meaningful content loss) is
correct — the files were expanded during the move — but the premise was
wrong.

---

## Findings

### Finding 1: TASK-435's Finding 1 (artifact exists) — ✅ CORRECT

**Independently verified.** At SHA `8db92715`:

- `src/enrollmenttags.py` exists (545 lines)
  - `preflight()` at lines 384-432
  - `_cli_main()` at lines 438-533
  - `__main__` guard at lines 536-545
  - `import json` and `from . import store` at lines 36-38

- `src/push.py` at lines 26, 531, 540:
  - `from . import (..., enrollmenttags, ...)` (line 26)
  - `tag_coverage = enrollmenttags.preflight(enrolling_recs)` (line 531)
  - `"tag_coverage": tag_coverage` in return dict (line 540)

- `tests/test_enrollment_tags.py` has 38 tests, all passing in 0.235s

TASK-435's file locations and line numbers are accurate.

### Finding 2: TASK-435's Finding 2 (production caller) — ✅ CORRECT

**Independently verified.** `grep -rn enrollmenttags src/` returns:

```
src/enrollmenttags.py:444-452:  (CLI help text, self-references)
src/push.py:26:                 from . import (..., enrollmenttags, ...)
src/push.py:531:                tag_coverage = enrollmenttags.preflight(enrolling_recs)
```

Two hits outside the module itself: the import and the call. The chain is:
`push.run()` → `enrollmenttags.preflight()` → result dict → CLI output.
This is NOT disconnected.

### Finding 3: TASK-435's Finding 3 (wiring tests not falsifiable) — ✅ CORRECT

**Independently verified by performing the mutation.**

The two `PushReportsTagCoverage` tests at lines 436-462:

```python
# Test 1 (line 454): checks hasattr(push_module, "enrollmenttags")
# Test 2 (line 461-462): checks push_module.enrollmenttags.preflight is enrollmenttags.preflight
```

**Mutation performed:** Removed line 531 (`tag_coverage = enrollmenttags.preflight(enrolling_recs)`)
and the `"tag_coverage": tag_coverage` key from the return dict in `push.py`.

**Result after mutation:**

```
test_push_result_contains_tag_coverage ... ok
test_push_result_tag_coverage_shape ... ok

Ran 2 tests in 0.045s
OK
```

**Both tests pass with the call completely removed.** This conclusively proves
they test only the import's existence, not the function's invocation.

**Additional observation TASK-435 did not make:** The docstring on
`test_push_result_contains_tag_coverage` says "Driven through push.run(),
which imports enrollmenttags and calls preflight on the enrolling records. If
the import is removed or the call is cut, this test fails — which is the
point." The test does NOT call `push.run()`. The docstring describes what the
test should prove but does not. This is the third face of the 2026-09-14
defect: the test describes what it should prove but actually proves something
weaker.

### Finding 4: TASK-435's Finding 4 (CLI tests weak) — ✅ CORRECT

**Independently verified.** The two `CLIReportsNightlyRates` tests:

- `test_cli_main_is_callable`: asserts `callable(enrollmenttags._cli_main)` —
  proves the function exists, not that it works.
- `test_module_has_main_guard`: asserts `find_spec("src.enrollmenttags") is
  not None` — proves the module is importable, not that a `__main__` guard
  exists.

Neither test invokes the CLI or checks output. Less critical than the wiring
tests (CLI is not the production path), but still not falsifiable for the
claims they imply.

### Finding 5: TASK-435's Finding 5 (core module solid) — ✅ CORRECT

**Independently verified.** The 29 original tests (classes
`UnknownValuesAreRefused`, `ReportStructure`, `RateNamesItsDenominator`,
`UnderThirtyRefusesPercentage`, `BackTaggingFromEnrollmentArtifact`,
`PreflightChecksTagCoverage`) drive through the actual functions (`validate`,
`backfill`, `nightly_report`, `preflight`) and assert on their output. They
are well-designed and falsifiable. Examples:

- `test_unknown_angle_is_refused`: calls `validate()` with an unknown angle,
  expects `UnknownTagValue` exception. If validation were removed, this fails.
- `test_below_30_sends_refuses_rate`: calls `nightly_report()` with 5 sends,
  checks `refused: True`. If the under-30 guard were removed, this fails.
- `test_backfill_refuses_unknown_values`: calls `backfill()` with invalid
  data, expects refusal. If backfill accepted anything, this fails.

### Finding 6: TASK-435's Finding 6 (scope drift) — ✅ CORRECT

**Independently verified.**

```
git log --oneline 8db92715 --not master | wc -l  →  78
git diff master...8db92715 --stat | tail -1       →  121 files changed, 13485 insertions(+), 541 deletions(-)
```

TASK-246's specific contribution is 3 commits (`5c3e3f30`, `49d44051`,
`19fb39a7`), with the code change in `49d44051` (3 files, +282/-12). The
rest is work from many other tasks. The branch cannot be merged as a whole.

The three TASK-246 commits are clean and self-contained and can be
cherry-picked independently.

### Finding 7: TASK-435's Finding 7 (no deletion risk) — ⚠️ PARTIALLY INACCURATE

TASK-435 claimed: "These do NOT exist on master (they were created on the
branch and moved to DONE/REVIEW). No master content would be lost by merging."

**This is wrong for two of the three files:**

| File | On master? | On branch? |
|------|-----------|-----------|
| TASK-310 | ✅ YES, in `TODO/` (60 lines) | In `REVIEW/` (171 lines, expanded) |
| TASK-364 | ❌ Not on master | Not on branch |
| TASK-388 | ✅ YES, in `TODO/` | In `REVIEW/` (expanded) |

TASK-310 and TASK-388 exist on master in `TODO/`. The branch moved them to
`REVIEW/` with expanded content (result blocks, findings). A merge would
delete the `TODO/` versions and add the `REVIEW/` versions. This is
legitimate task progression, not data loss — the content was expanded, not
reduced — but TASK-435's premise that the files "do NOT exist on master" is
factually wrong.

**The conclusion (no meaningful content loss) is correct**, but the reasoning
was inaccurate.

### Finding 8: TASK-435's Finding 8 (preflight is report, not gate) — ✅ CORRECT

**Independently verified.** `preflight()` (lines 384-432) returns a dict with
`total`, `tagged`, `untagged`, `partial`, `untagged_ids`, `problems`. It
never raises, never blocks, never refuses enrollment. The comment in
`push.py` line 527 says explicitly: "Reported, not enforced: a lead without
tags is not a reason to stop the batch, but it is a reason to know."

---

## What TASK-435 got right

| Claim | Verified? | Method |
|-------|-----------|--------|
| Artifact exists at target SHA | ✅ | File read, line numbers match |
| Production caller exists | ✅ | grep confirms import + call |
| Wiring tests use hasattr/assertIs | ✅ | Source read, lines 454, 461-462 |
| Wiring tests not falsifiable | ✅ | **Mutation performed, tests still pass** |
| CLI tests weak | ✅ | Source read, assertions are existence checks |
| Core module tests solid | ✅ | 29 tests, all drive through real functions |
| Scope drift significant | ✅ | 78 commits, 121 files confirmed |
| Cherry-pick scope clean | ✅ | 3 commits, code in one |
| Preflight is report, not gate | ✅ | Function returns dict, never raises |

## What TASK-435 got wrong

| Claim | Issue |
|-------|-------|
| "Deleted files do NOT exist on master" | Wrong for TASK-310 and TASK-388; they exist in TODO/ on master |
| "No master content would be lost" | Technically the TODO versions would be deleted, but REVIEW versions contain expanded content — conclusion is correct, premise was not |

---

## Reproducible verification commands

```bash
# Check out the exact branch HEAD
git worktree add .qwen/worktrees/task537-review f3b68bf849d8361fab9d3f8f972229369cf60944 --detach

# Check out the code at TASK-246's target SHA
git worktree add .qwen/worktrees/task537-code 8db9271503ac965bcaa48ee4cca55356c0582d9d --detach

# Verify production callers
cd .qwen/worktrees/task537-code
grep -rn "enrollmenttags" src/ --include="*.py"

# Run the tests
python -m unittest tests.test_enrollment_tags -v

# Mutation test: remove the call, see if tests catch it
# Delete line 531 (tag_coverage = enrollmenttags.preflight(enrolling_recs))
# Delete "tag_coverage": tag_coverage from the return dict
# Re-run: python -m unittest tests.test_enrollment_tags.PushReportsTagCoverage -v
# Expected: both tests still pass (proving they are not falsifiable)

# Check deletion risk
git diff master...8db9271503ac965bcaa48ee4cca55356c0582d9d --diff-filter=D --name-only
# Then check each file against master
git show master:<path>
```

---

## Recommendation

**MERGE the TASK-435 verdict as-is.** The REWORK disposition is correct and
well-evidenced. The analysis is thorough, the mutation test is valid, and the
recommended fix (replace the two `PushReportsTagCoverage` tests with one that
calls `push.run()` and asserts on the result) is the right fix.

The only correction is to Finding 7: TASK-310 and TASK-388 DO exist on master
(in TODO/) and the branch moves them to REVIEW/ with expanded content. This
does not change the conclusion (no meaningful content loss) but corrects the
premise.

**Required fix for TASK-246 (same as TASK-435 recommended):**

Replace the two `PushReportsTagCoverage` tests with one that calls
`push.run()` and asserts the result contains `tag_coverage` with the
preflight shape. This is a ~10-line change.

**Optional fix:** Strengthen the `CLIReportsNightlyRates` tests to actually
invoke `_cli_main()` with `--preflight` and check the output.

**Cherry-pick scope:** The three TASK-246 commits (`5c3e3f30`, `49d44051`,
`19fb39a7`) are clean and self-contained.

---

## Disposition summary

| Aspect | TASK-435 claim | Independent verdict |
|--------|---------------|-------------------|
| Artifact exists | ✅ VERIFIED | ✅ CONFIRMED |
| Production caller | ✅ VERIFIED | ✅ CONFIRMED |
| Wiring tests falsifiable | ❌ FAILED | ✅ CONFIRMED FAILED (mutation performed) |
| Core module correct | ✅ VERIFIED | ✅ CONFIRMED |
| Scope drift | ⚠️ SIGNIFICANT | ✅ CONFIRMED (78 commits, 121 files) |
| Deletion risk | ✅ NONE | ⚠️ PARTIALLY WRONG PREMISE, correct conclusion |
| Tests pass | ✅ 38/38 | ✅ CONFIRMED (38/38 in 0.235s) |
| REWORK recommendation | Correct | ✅ CONFIRMED |

**RECOMMENDATION: MERGE** — TASK-435's REWORK verdict on TASK-246 is correct
and independently verified. The one minor inaccuracy in Finding 7 does not
affect the disposition.
