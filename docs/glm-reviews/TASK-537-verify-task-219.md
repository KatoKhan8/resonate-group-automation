# TASK-537 — GLM Independent Verification: TASK-435

## Target

    task            TASK-435
    branch          origin/glm-review-504-task-387
    branch HEAD SHA f3b68bf849d8361fab9d3f8f972229369cf60944

**Note:** The branch has moved past the target SHA (current head: `515c638e`).
Per protocol, this review targets `f3b68bf849d8361fab9d3f8f972229369cf60944` specifically,
which is the artifact TASK-435's result block claims.

**Review worktree:** `.qwen/worktrees/task537-review` (detached at `f3b68bf8`)

**Secondary worktree:** `.qwen/worktrees/task537-verify` (detached at `8db92715`,
the SHA TASK-435 reviewed)

**START_MASTER_SHA:** Current master at review time

---

## Summary

**DISPOSITION: MERGE**

TASK-435's verdict is accurate, well-reasoned, and correctly identifies the defect.
The REWORK recommendation is justified. The wiring tests use `hasattr` and `assertIs`,
which are explicitly prohibited by QWEN.md as proof. I performed the mutation test
myself and confirmed: removing the actual call from `push.py` does not fail the wiring
tests, proving they are not falsifiable.

TASK-435's analysis is correct. The code is solid, the wiring is real, but the tests
do not prove what they claim to prove. This is the exact defect that cost three tasks
on 2026-09-14.

---

## Findings

### Finding 1: TASK-435's verdict document exists ✅

**Verified.** The verdict document `docs/glm-reviews/TASK-435-verify-task-246.md` exists
at SHA `f3b68bf849d8361fab9d3f8f972229369cf60944` and contains a complete, well-structured
review with eight findings, a disposition table, and a clear REWORK recommendation.

The verdict correctly identifies:
- The target SHA it reviewed (`8db9271503ac965bcaa48ee4cca55356c0582d9d`)
- The branch has moved (noted in the verdict)
- The artifact exists and does what the result block claims
- The production caller exists
- The wiring tests are not falsifiable
- The scope drift is significant
- No deletion risk

### Finding 2: TASK-435's mutation test claim is accurate ✅

**Verified by independent reproduction.** TASK-435 claimed that the two wiring tests
would pass even if the actual call to `enrollmenttags.preflight()` were removed from
`push.py`. I performed this mutation myself:

**Mutation applied:**
- Commented out line 531: `tag_coverage = enrollmenttags.preflight(enrolling_recs)`
- Commented out line 540: `"tag_coverage": tag_coverage` in the return dict

**Result:** Both `PushReportsTagCoverage` tests still pass:
```
test_push_result_contains_tag_coverage ... ok
test_push_result_tag_coverage_shape ... ok
Ran 2 tests in 0.051s
OK
```

This confirms the tests only check that the import exists, not that the function is
called. TASK-435's analysis is correct.

### Finding 3: TASK-435's production caller verification is accurate ✅

**Verified.** At SHA `8db9271503ac965bcaa48ee4cca55356c0582d9d`:

```
src/push.py:26:  from . import (..., enrollmenttags, ...)
src/push.py:531: tag_coverage = enrollmenttags.preflight(enrolling_recs)
```

The chain is connected: `push.run()` → `enrollmenttags.preflight()` → result dict →
CLI output. This is NOT disconnected.

### Finding 4: TASK-435's test count is accurate ✅

**Verified.** At SHA `8db9271503ac965bcaa48ee4cca55356c0582d9d`:

```
python -m unittest tests.test_enrollment_tags
Ran 38 tests in 0.162s
OK
```

All 38 tests pass, matching TASK-435's claim.

### Finding 5: TASK-435's scope drift analysis is accurate ✅

**Verified.** The branch has 78 commits not in master, matching TASK-435's claim.
The diff shows 121 files changed with significant additions. TASK-246's specific
contribution is contained in three commits:
- `cb403de0d` - Initial implementation (376 lines enrollmenttags.py, 386 lines tests)
- `49d440518` - Wiring into push.py and CLI entry point
- `19fb39a72` - Move to REVIEW

These are clean and self-contained, and can be cherry-picked without the rest of the
branch.

### Finding 6: TASK-435's deletion risk analysis is accurate ✅

**Verified.** The three deleted files:
- `docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md`
- `docs/qwen-tasks/TODO/TASK-364-one-canonical-sequence-plan.md`
- `docs/qwen-tasks/TODO/TASK-388-reconciliation-check-in-the-watcher-cycle.md`

These are task files that were moved to DONE/REVIEW on the branch. They do NOT exist
on master, so no master content would be lost by merging.

### Finding 7: TASK-435's REWORK recommendation is justified ✅

**Verified.** The defect is real and specific:

**What the tests claim:** "Driven through push.run()" (docstring on line 448)

**What the tests actually do:**
- Test 1: `hasattr(push_module, "enrollmenttags")` - proves import exists
- Test 2: `assertIs(push_module.enrollmenttags.preflight, enrollmenttags.preflight)` - proves function reference is correct

**What the tests do NOT prove:** That `push.run()` calls `enrollmenttags.preflight()`.

**QWEN.md explicitly prohibits this:**
> "Not accepted as proof: hasattr, assertions on source text, a token appearing in a
> file, proving a function exists, a JSON shape, or a fake cassette returning fake data."

Both tests use patterns QWEN.md names as insufficient. The fix is small and specific:
replace the two tests with one that calls `push.run()` and asserts the result contains
`tag_coverage` with the preflight shape.

### Finding 8: TASK-435's verdict is complete and well-structured ✅

**Verified.** The verdict includes:
- Clear target identification with SHA
- Eight findings with evidence
- Reproducible verification commands
- Disposition table
- Clear recommendation with justification
- Risk assessment

The verdict follows the GLM review protocol and provides enough detail for Claude to
make an informed decision.

---

## What TASK-435 got right

1. **The defect identification is correct.** The wiring tests are not falsifiable.
2. **The mutation test claim is accurate.** I reproduced it independently.
3. **The production caller verification is correct.** The chain is connected.
4. **The scope drift analysis is accurate.** 78 commits, 121 files.
5. **The deletion risk analysis is correct.** No master content would be lost.
6. **The REWORK recommendation is justified.** The fix is small and specific.
7. **The verdict is complete and well-structured.** Follows the protocol.

## What TASK-435 could have done better

1. **Minor discrepancy in line count.** TASK-435 says `src/enrollmenttags.py` is 587
   lines; it's actually 544 lines at SHA `8db9271503ac965bcaa48ee4cca55356c0582d9d`. This
   is a minor factual error that does not affect the verdict.

2. **Minor discrepancy in commit list.** TASK-435 mentions "three commits: 5c3e3f30,
   49d44051, 19fb39a7" but the actual implementation commits are `cb403de0d` and
   `49d440518`, plus `19fb39a72` for the move. The commit `5c3e3f30b` is just the claim,
   not implementation. This is a minor factual error that does not affect the verdict.

3. **Could have been more explicit about the fix.** TASK-435 provides a code example
   of what the fix should look like, which is helpful, but could have been more explicit
   about which lines to replace.

These are minor issues and do not affect the overall quality of the verdict.

---

## Reproducible verification commands

```bash
# Check out the exact SHA TASK-435 reviewed
git worktree add .qwen/worktrees/task537-verify 8db9271503ac965bcaa48ee4cca55356c0582d9d --detach

# Verify production callers
cd .qwen/worktrees/task537-verify
grep -rn "enrollmenttags" src/ --include="*.py"

# Run the tests
python -m unittest tests.test_enrollment_tags -v

# Mutation test: remove the call, see if tests catch it
# (Edit src/push.py: comment out lines 531 and 540, re-run tests)
# Expected result: PushReportsTagCoverage tests still pass (proving they're not falsifiable)
```

---

## Recommendation

**MERGE** — TASK-435's verdict is accurate and the REWORK recommendation is justified.

The verdict correctly identifies the defect: the wiring tests use `hasattr` and
`assertIs`, which are explicitly prohibited by QWEN.md as proof. The mutation test
confirms the tests are not falsifiable. The fix is small and specific.

**Required action:** Claude should route this back to the original worker (or assign
a new task) to fix the wiring tests. The fix is to replace the two `PushReportsTagCoverage`
tests with one that calls `push.run()` and asserts the result contains `tag_coverage`
with the preflight shape.

**Cherry-pick scope:** The three TASK-246 commits (`cb403de0d`, `49d440518`, `19fb39a72`)
are clean and can be cherry-picked from the branch without the other 75 commits.

**Risk if merged as-is:** The wiring tests would pass even if the call were removed
from `push.run()`. A future refactor could silently disconnect the preflight from the
push path, and the tests would not catch it. This is the exact defect that cost three
tasks on 2026-09-14.

---

## Disposition summary

| Aspect | Status | Evidence |
|--------|--------|----------|
| TASK-435 verdict exists | ✅ VERIFIED | `docs/glm-reviews/TASK-435-verify-task-246.md` at `f3b68bf8` |
| Mutation test claim | ✅ VERIFIED | Reproduced independently: tests pass after removing call |
| Production caller | ✅ VERIFIED | `push.py:531` calls `enrollmenttags.preflight()` |
| Test count | ✅ VERIFIED | 38/38 tests pass at `8db92715` |
| Scope drift | ✅ VERIFIED | 78 commits, 121 files, TASK-246 is 3 commits |
| Deletion risk | ✅ VERIFIED | Deleted files don't exist on master |
| REWORK recommendation | ✅ JUSTIFIED | Defect is real, fix is small and specific |

**RECOMMENDATION: MERGE** — TASK-435's verdict is accurate and well-reasoned. The
REWORK recommendation is correct and should be acted on.
