# GLM independent verification: TASK-345

## Target

    task            TASK-345
    branch          origin/qwen-worker-r68
    branch HEAD SHA f95066072e12e6e0690408375d325657ac44d9

**Verified at:** `f95066072e12e6e0690408375d325657ac44d9` (confirmed via `git rev-parse` in isolated worktree `.qwen/worktrees/task490-review`).

**Note:** The task file says to write this verdict to `TASK-490-verify-task-219.md` — the "219" is a template error; this verdict reviews TASK-345.

## Branch composition

Four files, 927 insertions, 0 deletions (three-dot diff against master):

| File | Lines | Type |
|------|-------|------|
| `scripts/glm_verify_branch.py` | 569 | NEW — CLI verification tool |
| `docs/glm-reviews/branch-TASK-323.md` | 110 | NEW — GLM verdict output |
| `docs/glm-reviews/branch-TASK-324.md` | 104 | NEW — GLM verdict output |
| `docs/qwen-tasks/REVIEW/TASK-345-...md` | 144 | MOVED TODO→REVIEW |

No scratch files. No unrelated changes. No scope drift.

## Finding 1: Artifacts exist and do what the result block claims

**VERIFIED with caveats.**

The script runs. `--dry-run` produces a coherent prompt (7,828 chars), extracts acceptance commands from the task file, diffs the branch, and reports changed test files. The two GLM review outputs contain real model responses (glm-5.3, 8,061 and 5,976 tokens respectively) with specific, falsifiable findings that reference actual code defects.

The result block claims "DONE" and "The script works as designed." This is partially true:
- ✅ The script runs acceptance commands in a worktree
- ✅ The script calls GLM and parses verdicts
- ✅ The script detects scratch files and new test failures
- ❌ The baseline comparison is BROKEN (see Finding 3)
- ❌ The spend reporting has a latent bug (see Finding 4)

## Finding 2: Production caller — ACCEPTABLE for a tool

`grep -rn glm_verify_branch src/` returns zero hits. The script is a standalone CLI tool invoked by the operator, not a library imported by production code. This is the same pattern as `scripts/glm_review.py` which it extends, and is acceptable for a verification tool. It is not a bridge function masquerading as a module.

However, the script has no automated integration into any CI/CD or pre-merge gate. It must be manually invoked per branch. This limits its value as a "gate" — it is a tool, not a gate.

## Finding 3: Test name normalization bug — the script could never emit PASS for test failures

**CONFIRMED DEFECT, since fixed on master.**

The baseline file (`docs/state/SUITE-BASELINE-2026-09-26.txt`) stores failing test names as:
```
FAIL test_a_bounced_address_stops_being_sendable.TheSENDPathReads.test_decide_blocks_a_bounced_address
```

The script's `_run_tests_in_worktree` extracts from `unittest -v` output:
```
FAIL: test_decide_blocks_a_bounced_address (tests.test_a_bounced_address_stops_being_sendable.TheSENDPathReads.test_decide_blocks_a_bounced_address)
```

The script stores `parts[1]` verbatim after splitting on `FAIL: `, which is `test_decide_blocks_a_bounced_address (tests.test_a_bounced_address_stops_being_sendable.TheSENDPathReads.test_decide_blocks_a_bounced_address)`. This NEVER matches the baseline's `test_a_bounced_address_stops_being_sendable.TheSENDPathReads.test_decide_blocks_a_bounced_address`.

**Consequence:** Every failing test is reported as "new (not in baseline)" and the verdict is always FAIL when any test fails — including for branches whose failures are entirely baseline-known. The script cannot emit a valid PASS when tests fail.

**Fix on master:** Commit `cafa7ca5` ("The GLM verifier could never emit PASS: its two sides were shaped differently") introduced `normalise_test_name()` which strips the `tests.` prefix and extracts the parenthesised dotted path. This fix is on master but NOT on the branch.

**Falsification performed:** I loaded the baseline via the branch's `_load_baseline()` and confirmed it stores 128 names without the `tests.` prefix. I compared the format with `unittest -v` output format and confirmed the mismatch.

## Finding 4: Spend attribution bug — `_read_spend` looks for wrong client key

**CONFIRMED DEFECT, fix exists but is NOT on master.**

The branch's `_read_spend()` filters for `r.get("client") == "_model"`. After TASK-346, model spend rows use `client == "unattributed"` (or a different key). The function returns `(0, 0)` for any run after that change, making the spend report silently wrong.

**Status:** Commit `428c640d` fixes this but lives only on `qwen-worker-12-r9`, not on master. Master's version of the script still has `_model`. The review outputs' spend figures (10,168 and 8,011 micro-USD) were correct at the time of running (before TASK-346's change took effect) but the code is fragile.

## Finding 5: Would merging delete anything?

**NO — from the branch's own changes.** The three-dot diff shows 927 insertions, 0 deletions. All four files are new additions.

**But the branch is STALE.** The two-dot diff between master and the branch shows 561 files changed, 3175 insertions, 103,053 deletions — because master has moved far ahead (merge-base is `2e1e55a5`, master is at `50293a86`). A naive merge would be catastrophic. Cherry-picking is the only safe path.

**All artifacts are already integrated:**
- `docs/glm-reviews/branch-TASK-323.md` — byte-identical on master (blob `b2d42bf9`)
- `docs/glm-reviews/branch-TASK-324.md` — byte-identical on master (blob `57867765`)
- `scripts/glm_verify_branch.py` — integrated via commit `23ade722`, then fixed in `cafa7ca5`. The branch's version (`d6b69664`) differs from master's (`1382f8bc`).
- Task file — still in TODO on master; the branch moved it to REVIEW.

## Finding 6: Scope drift

**NONE.** All four files answer to the task. No scratch files. No unrelated edits.

## Finding 7: GLM review quality

Both GLM reviews are high quality:
- **TASK-323 review (FAIL):** Correctly identified that 2/4 acceptance commands exit=1 because `spendledger.rows()` does not exist. Correctly noted the task doc was empty and still in RUNNING. Correctly identified a latent defect: `test_an_unpriced_model_still_writes_a_row` enshrines cost=0 for unknown model IDs, which could make the ceiling test vacuous.
- **TASK-324 review (FAIL):** Correctly identified that the audit script never ran (missing `work/` directory). Correctly noted that "2124 table cells" is a false measurement (pipes ≠ cells). Correctly identified that the task doc was empty and still in RUNNING.

Both verdicts are concrete, cite file names, and name specific defeat mechanisms. The GLM layer worked as designed.

## Disposition

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | Artifacts exist and partially work | INFO | Dry-run succeeded; GLM reviews contain real findings |
| 2 | No production caller (acceptable for tool) | NONE | Same pattern as `scripts/glm_review.py` |
| 3 | Test name normalization broken — can never emit PASS for test failures | CRITICAL | Baseline format vs unittest output format mismatch; fixed on master in `cafa7ca5` |
| 4 | Spend attribution uses stale `_model` key | MEDIUM | `_read_spend` filters wrong client; fix `428c640d` not on master |
| 5 | Branch is stale; all artifacts already integrated | INFO | Blob hashes match; script has been fixed post-integration |
| 6 | No scope drift | NONE | All files on-topic |
| 7 | GLM review quality is high | POSITIVE | Both reviews caught real defects with specific evidence |

## Recommendation: CLOSE

**The branch is fully superseded.** All four artifacts were already integrated into master (commit `23ade722`). The script was subsequently fixed on master (commit `cafa7ca5` for the test name bug). The review outputs are byte-identical on master. The branch has nothing left to contribute.

Merging the branch would either:
- Fail (conflict on `scripts/glm_verify_branch.py` which already exists on master with fixes)
- Or, if force-applied, regress the script to the pre-fix version

The task file should be moved from TODO to DONE on master (it is still in TODO on both master and the branch). The two known defects in master's version of the script are:
1. Spend attribution (`_model` → `unattributed`) — fix exists on `qwen-worker-12-r9` but not master
2. File handle leak in `_load_baseline` — fixed in `cafa7ca5` on master

**CLOSE reason:** Work already integrated and superseded by post-integration fixes on master. No remaining delta worth cherry-picking.
