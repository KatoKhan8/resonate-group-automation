# TASK-537 — GLM Independent Verification of TASK-435's Verdict on TASK-246

## Target

    meta-review task   TASK-537
    reviewed verdict   TASK-435 (docs/glm-reviews/TASK-435-verify-task-246.md)
    original task      TASK-246 (enrollment tags preflight + nightly report)
    review branch      origin/glm-review-504-task-387
    branch HEAD SHA    f3b68bf849d8361fab9d3f8f972229369cf60944 (as named by TASK-537)
    actual HEAD SHA    515c638e14423a203e56f3ed3525af8569f72c07 (branch has moved)
    TASK-246 SHA       8db9271503ac965bcaa48ee4cca55356c0582d9d (what TASK-435 reviewed)

**Branch movement note:** The branch `origin/glm-review-504-task-387` has moved past
the SHA named in TASK-537 (`f3b68bf8`). Per protocol, this review targets
`f3b68bf849d8361fab9d3f8f972229369cf60944` — the artifact the verdict was dispatched against.

**Review worktrees:**
- `.qwen/worktrees/task537-review` (detached at `f3b68bf8`)
- `.qwen/worktrees/task537-mutation` (detached at `8db92715`, for mutation test)

---

## Summary

**DISPOSITION: MERGE (the verdict), with two corrections**

TASK-435's verdict is sound in its core finding and recommendation. The REWORK
conclusion is correct: the wiring tests use `hasattr` and `assertIs`, which are
explicitly prohibited by QWEN.md as proof, and a mutation test confirms they
pass even after the production call is removed.

However, TASK-435 contains two factual errors that must be corrected before the
verdict is acted on:

1. **Deletion risk is UNDERSTATED.** TASK-310 and TASK-388 exist on master and
   would be deleted by merging the branch. TASK-435 claimed they "do NOT exist
   on master." This is wrong.

2. **Commit count is understated.** 324 commits separate the branch from master,
   not 78. The file count (121) is correct.

Neither error changes the REWORK recommendation for TASK-246's code, but the
deletion-risk error is material: a cherry-pick of the three TASK-246 commits is
the correct integration path, and the verdict must be clear about why.

---

## Findings

### Finding 1: TASK-435's artifact-existence claim — VERIFIED ✅

TASK-435 claimed `src/enrollmenttags.py` exists at `8db92715` with `preflight()`,
`_cli_main()`, and a `__main__` guard. Confirmed:

    Line 387: def preflight(records, vocabularies=None):
    Line 440: def _cli_main(argv=None):
    Line 543: if __name__ == "__main__":

TASK-435 also claimed `src/push.py` imports `enrollmenttags` (line 26) and calls
`enrollmenttags.preflight(enrolling_recs)` (line 531). Confirmed at `8db92715`:

    Line 26:  from . import (cadence, clients, enrollmenttags, events, killswitch, lint,
    Line 531: tag_coverage = enrollmenttags.preflight(enrolling_recs)

**Minor numerical error:** TASK-435 said enrollmenttags.py has 587 lines; it has
544. Function start lines are off by 2-6 lines. Not material to the verdict.

### Finding 2: TASK-435's production-caller claim — VERIFIED ✅

TASK-435 correctly identified the chain: `push.run()` → `enrollmenttags.preflight()`
→ result dict → CLI output. The import and call are both present at the reviewed SHA.
This is NOT disconnected.

### Finding 3: TASK-435's wiring-test defect claim — CONFIRMED BY MUTATION TEST ✅

This is the core of TASK-435's verdict and the reason for the REWORK recommendation.
I performed the mutation independently.

**Before mutation:** Both `PushReportsTagCoverage` tests pass (2/2, 0.497s).

**Mutation applied:** Commented out line 531 (`tag_coverage = enrollmenttags.preflight(enrolling_recs)`)
and removed `"tag_coverage": tag_coverage` from the return dict in `src/push.py`.

**After mutation:** Both `PushReportsTagCoverage` tests STILL PASS (2/2, 0.024s).

This confirms TASK-435's claim: the tests check only that the import exists and the
function reference matches, not that `push.run()` actually calls the function. The
docstring says "Driven through push.run()" but neither test calls `push.run()`.

**Full test suite after mutation:** All 38 tests pass. No test in the file detects
the removal of the production call. This is the exact defect QWEN.md names:

> "Not accepted as proof: hasattr, assertions on source text, a token appearing in
> a file, proving a function exists, a JSON shape, or a fake cassette returning
> fake data."

Test 1 uses `hasattr`. Test 2 uses `assertIs`. Both are in the prohibited list.

### Finding 4: TASK-435's CLI-test weakness claim — VERIFIED ✅

The two `CLIReportsNightlyRates` tests:
- `test_cli_main_is_callable`: checks `callable(enrollmenttags._cli_main)` — proves
  existence, not execution.
- `test_module_has_main_guard`: checks `importlib.util.find_spec("src.enrollmenttags")`
  — proves importability, not that a `__main__` guard exists.

TASK-435 correctly identified these as weak. The second test's docstring says "The
module has an __name__ == '__main__' guard for CLI use" but the test checks no such
thing.

### Finding 5: TASK-435's deletion-risk claim — WRONG ❌

**This is the material error in the verdict.** TASK-435 claimed:

> "The branch 'deletes' three TODO task files [...] These do NOT exist on master."

I checked all three against current master:

| File | On master? | Branch deletes it? |
|------|-----------|-------------------|
| TASK-310-every-approved-file-feeds-the-training-set.md | **YES** | **YES** |
| TASK-364-one-canonical-sequence-plan.md | No | Yes (but not on master) |
| TASK-388-reconciliation-check-in-the-watcher-cycle.md | **YES** | **YES** |

`git diff master...8db9271503ac965bcaa48ee4cca55356c0582d9d` confirms:

    deleted file mode 100644
    --- a/docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md
    +++ /dev/null
    @@ -1,60 +0,0 @@

    deleted file mode 100644
    --- a/docs/qwen-tasks/TODO/TASK-388-reconciliation-check-in-the-watcher-cycle.md
    +++ /dev/null
    @@ -1,56 +0,0 @@

**TASK-310 and TASK-388 would be LOST if the branch were merged.** This is the exact
defect the protocol asks reviewers to catch: "one branch's files were byte-identical
to master's and merging would have deleted 12,487 lines."

TASK-435's error does not change the REWORK recommendation (the branch should be
cherry-picked, not merged), but the verdict's statement that "No master content
would be lost by merging" is factually wrong.

### Finding 6: TASK-435's scope-drift assessment — NUMERICALLY WRONG ⚠️

TASK-435 claimed "78 commits not in master, changing 121 files." The actual count:

    Commits:  324 (not 78 — off by a factor of 4)
    Files:    121 (correct)
    Lines:    +13,485 / -541 (correct)

The conclusion is the same — the branch carries work from many tasks and cannot be
merged wholesale — but the commit count error suggests TASK-435 did not actually
run `git log master...HEAD | wc -l`.

### Finding 7: TASK-435's cherry-pick identification — VERIFIED ✅

TASK-435 identified three commits for cherry-pick: `5c3e3f30`, `49d44051`, `19fb39a7`.
These are the correct TASK-246 commits:

    cb403de0  TASK-246: learning tags schema, validation, back-tagging and nightly rate report
    5c3e3f30  Claim TASK-246: learning tags and nightly rate report
    49d44051  Wire enrollmenttags into push and add CLI entry point
    19fb39a7  TASK-246 to REVIEW: learning tags wired and tested

Note: TASK-435 listed `49d44051` but not `cb403de0` (the initial schema commit). The
cherry-pick set should include all four commits, not three.

### Finding 8: TASK-435's REWORK recommendation — CORRECT ✅

Despite the factual errors above, the REWORK recommendation is correct. The wiring
tests are not falsifiable, the mutation test proves it, and the fix is small: replace
the two `PushReportsTagCoverage` tests with one that calls `push.run()` and asserts
on the result containing `tag_coverage`.

The cherry-pick path (rather than a full merge) is also correct, and is in fact
MORE important than TASK-435 realised, given that a full merge would delete TASK-310
and TASK-388 from master.

---

## What TASK-435 got right

1. The wiring tests use prohibited patterns (`hasattr`, `assertIs`). Confirmed by
   independent mutation test.
2. The production caller exists and is connected. Verified at the target SHA.
3. The core module (29 non-wiring tests) is solid and falsifiable. Verified.
4. The REWORK recommendation is correct.
5. The fix is small and specific (replace two tests with one that calls `push.run()`).
6. The cherry-pick path is the correct integration strategy.

## What TASK-435 got wrong

1. **Deletion risk:** TASK-310 and TASK-388 exist on master and would be deleted.
   The verdict says "No master content would be lost by merging." This is false.
2. **Commit count:** 324, not 78. The verdict significantly understated the branch's
   divergence from master.
3. **Line count:** enrollmenttags.py has 544 lines, not 587.
4. **Cherry-pick set:** Listed 3 commits but missed `cb403de0` (the initial schema
   commit). Should be 4 commits.

## Protocol compliance

| Requirement | Status |
|-------------|--------|
| Named the exact SHA reviewed | ✅ `8db9271503ac965bcaa48ee4cca55356c0582d9d` |
| Used an isolated worktree | ✅ `.qwen/worktrees/task435-review` (stated, now removed) |
| Falsification over confirmation | ✅ Mutation test performed |
| Eight dispositions per finding | ⚠️ Used emoji indicators, not the formal eight |
| Cited file:line evidence | ✅ Mostly accurate line numbers |
| Distinguished static from runtime proof | ✅ Noted the tests are static only |
| Marked unverified claims | ✅ Said "not verified" where appropriate |
| Checked deletion risk | ❌ Got it wrong — two master files would be deleted |
| Checked scope drift | ⚠️ Right conclusion, wrong numbers |

---

## Recommendation

**MERGE the verdict (with corrections).** TASK-435's REWORK recommendation for
TASK-246 is correct and well-evidenced. The mutation test independently confirms
the core finding. The factual errors (deletion risk, commit count) do not change
the recommendation but should be corrected in the record:

1. The verdict's "No deletion risk" finding must be amended: TASK-310 and TASK-388
   exist on master and would be deleted by a full merge. Cherry-pick is mandatory.
2. The commit count should be corrected from 78 to 324.
3. The cherry-pick set should include `cb403de0` (the initial schema commit).

**Next action for TASK-246:** Fix the two wiring tests to call `push.run()` and
assert on the result containing `tag_coverage`. Then cherry-pick the four TASK-246
commits (not a full merge) onto master.
