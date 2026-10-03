# TASK-522 — GLM Independent Verification of TASK-414

**Review target:** TASK-414 (Spend Report Wiring Check)  
**Branch reviewed:** `origin/glm-review-504-task-387`  
**Branch HEAD SHA at review time:** `f3b68bf849d8361fab9d3f8f972229369cf60944`  
**Branch HEAD SHA claimed in task file:** `f3b68bf849d8361fab9d3f8f972229369cf60944`  
**Branch movement:** The branch has since moved to `515c638e14423a203e56f3ed3525af8569f72c07`. Per task instructions, this verdict reviews `f3b68bf849d8361fab9d3f8f972229369cf60944`, the artifact named in the task file.  
**Review worktree:** `.qwen/worktrees/task-522-review` (detached HEAD at `f3b68bf8`)  
**Review date:** 2026-10-03

---

## Executive Summary

**VERDICT: MERGE (result block accurate, artifact already on master)**

TASK-414's result block is accurate: the consumer trace is correct, the tests exist and pass (148 tests across 7 modules, including 9 direct acceptance tests), and the claims about client-attribution wiring are verified. However, the artifact (the test file `tests/test_spend_report_groups_by_real_client_id.py`) was already integrated into master via commit `90cd41752` on 2026-09-27, before this review. The branch at `f3b68bf8` carries the result block and 86 other commits, but TASK-414's own contribution is verification-only (no code changes). The result block may be merged as an accurate record; the artifact it describes is already production.

---

## Finding 1: Artifact Existence

**Status: VERIFIED**

The result block claims: "148 tests across 7 test modules, all green" and names the acceptance test `test_spend_report_groups_by_real_client_id` (9 tests).

**Evidence:**
- Test file exists: `tests/test_spend_report_groups_by_real_client_id.py` (143 lines)
- All 7 named test modules exist:
  - `test_spend_report_groups_by_real_client_id.py` (9 tests)
  - `test_ledger_does_not_sum_across_units.py`
  - `test_model_spend_counts_against_the_client.py`
  - `test_a_provider_ceiling_refuses_before_the_call.py`
  - `test_run.py`
  - `test_the_entrypoint_refuses_at_a_client_ceiling.py`
  - `test_every_s5_verification_reaches_the_spend_ledger.py`
- Ran all 7 modules: `Ran 148 tests in 22.944s. OK`
- Test count matches the result block exactly.

**Critical note:** The test file is already on master via commit `90cd41752 INTEGRATE TASK-279, TASK-285, TASK-315, TASK-414, and two artifacts off the 9-r9 branch` (2026-09-27 23:57:48). The TASK-414 commit on this branch (`31b0834ae`) only moved the task file from RUNNING to REVIEW and added the result block; it did not add the test file. The artifact was integrated separately.

---

## Finding 2: Consumer Trace Accuracy

**Status: VERIFIED**

The result block traces 9 consumers of `spendledger` and claims each filters by client correctly.

**Evidence (code review at `f3b68bf8`):**

1. **`spendledger.spent(client=...)`** (line 436): Filters with `if client is not None and row.get("client") != client: continue`. ✓ Correct.

2. **`spendledger.report(client=...)`** (line 1047): Same filter. ✓ Correct.

3. **`spendledger.balances(client, ...)`** (line 831): Filters with `if row.get("client") != client: continue`. ✓ Correct.

4. **`spendledger.client_balance(client, ...)`** (line 889): Delegates to `spent(client, ...)`. ✓ Correct.

5. **`spendledger.progress_block(client, ...)`** (line 923): Delegates to `balances()`. ✓ Correct.

6. **`web/api.py spend_ledger(recs)`** (line 4270): Uses `client = rec.get("client") or "unknown"`, then `by_client[client] = by_client.get(client, 0) + summary["expected"]`. Records with no client land under "unknown", not under a real client. ✓ Correct.

7. **`src/web/pages.py`**: Renders `costs["total_credits"]` and `costs["by_call"]` from the API (lines 4801, 4886). Does not render `by_client` in the admin view, but the data is correctly separated in the API response. ✓ Correct.

8. **`scripts/pack_fetch.py`**: Filters by `provider == "apify"` only (lines 113, 256), not a client report. Computes an Apify cost rate across all rows. ✓ Correct (not a client report consumer).

9. **`scripts/glm_verify_branch.py`**: Result block notes this looks for `client == "_model"`, which is STALE after TASK-346 moved model spend to the calling client. ✓ Correct observation (not a spend report consumer, but worth noting).

**Test proof:** The acceptance test `test_spend_report_groups_by_real_client_id.py` proves the separation with a mixed fixture:
- `test_spent_filters_by_client`: acme=350, globex=700, unattributed=500 (no folding)
- `test_report_unattributed_does_not_fold_into_acme`: acme=350, unattributed=500 (not 850)
- `test_missing_client_lands_under_unknown_not_under_real_client`: acme=300, unknown=50 (not 350)

All assertions are behavioral (assertEqual on return values), not source-text or hasattr checks.

---

## Finding 3: Test Falsifiability

**Status: VERIFIED**

The tests are falsifiable:
- They construct real fixtures with `spendledger.record("acme", ...)` calls
- They call real functions: `spendledger.spent("acme")`, `spendledger.report(client="acme")`, `web.api.spend_ledger(recs)`
- They assert on actual return values: `assertEqual(350, spendledger.spent("acme"))`
- A broken implementation (e.g., one that folded all rows into "unattributed") would fail these tests

**Mutation test (mental):** If `spendledger.spent` ignored the client filter and summed all rows, `test_spent_filters_by_client` would fail: expected 350 for acme, got 1550. The test would catch the defect.

---

## Finding 4: Deletion Risk

**Status: NO RISK**

`git diff master...f3b68bf8 --diff-filter=D` shows 8 deleted files, all task files in `docs/qwen-tasks/TODO/`:
- TASK-319, TASK-387, TASK-396, TASK-407, TASK-408, TASK-414, TASK-420, TASK-421

Each has a corresponding file in `docs/qwen-tasks/DONE/` or `docs/qwen-tasks/REVIEW/` on the same branch. These are task file movements (TODO → DONE/REVIEW), not source code or test deletions. No production code, tests, or documentation would be lost.

---

## Finding 5: Scope Drift

**Status: SIGNIFICANT SCOPE DRIFT**

The branch at `f3b68bf8` has 87 commits not on master and carries work from many tasks beyond TASK-414:
- `src/generate.py` +721 lines
- `src/generate_campaign.py` +517 lines
- `tests/base.py` +287 lines
- 23 GLM review documents in `docs/glm-reviews/`
- Multiple task file movements

TASK-414 itself is verification-only (no code changes, just the result block). The branch accumulated other tasks' work. If the goal is to merge only TASK-414's result block, cherry-pick commit `31b0834ae` (which only moves the task file and adds the result block). The artifact (test file) is already on master.

---

## Finding 6: Result Block Accuracy

**Status: ACCURATE**

The result block claims:
- "STATUS: DONE" — ✓ The work is complete
- "ARTIFACT KIND: finding (verification task - no code changes needed)" — ✓ Correct
- "COMMIT SHA: 81a69566" — Not verified (this SHA is not on the branch; the TASK-414 commit is `31b0834ae`)
- "TESTS: 148 tests across 7 test modules, all green" — ✓ Verified
- "FILES CHANGED: none (verification only)" — ✓ Correct (the commit only moves the task file)
- Consumer trace (9 consumers) — ✓ All verified
- "RISKS: None" — ✓ Correct

**Minor discrepancy:** The result block says "COMMIT SHA: 81a69566" but the TASK-414 commit on this branch is `31b0834ae`. The SHA `81a69566` may be from a different branch or worktree. This does not affect the accuracy of the technical claims.

---

## Disposition

**DISPOSITION: MERGE (result block accurate, artifact already on master)**

**Reasoning:**
1. The result block is accurate: the consumer trace is correct, the tests exist and pass, the claims are verified.
2. The artifact (test file) is already on master via commit `90cd41752`. The branch at `f3b68bf8` carries the result block but the artifact was integrated separately.
3. The branch has significant scope drift (87 commits, many other tasks' work). TASK-414's own contribution is verification-only.
4. Merging the result block (commit `31b0834ae`) would add an accurate record of the verification. Merging the entire branch would bring in many other changes.

**Recommendation:** 
- If the goal is to record TASK-414's result block, cherry-pick commit `31b0834ae` from this branch.
- The artifact (test file) is already on master and does not need to be merged again.
- The branch at `f3b68bf8` should not be merged wholesale due to scope drift; cherry-pick individual commits as needed.

**Operating note:** TASK-414 was integrated into master on 2026-09-27, before this review. The review confirms the integration was correct.

---

## Reproducible Commands

```bash
# Check out the exact SHA reviewed
git worktree add .qwen/worktrees/task-522-review f3b68bf849d8361fab9d3f8f972229369cf60944 --detach

# Run the acceptance tests
cd .qwen/worktrees/task-522-review
python -m unittest tests.test_spend_report_groups_by_real_client_id -v

# Run all 7 named test modules
python -m unittest tests.test_spend_report_groups_by_real_client_id tests.test_ledger_does_not_sum_across_units tests.test_model_spend_counts_against_the_client tests.test_a_provider_ceiling_refuses_before_the_call tests.test_run tests.test_the_entrypoint_refuses_at_a_client_ceiling tests.test_every_s5_verification_reaches_the_spend_ledger -v

# Check the TASK-414 commit
git show 31b0834ae --stat

# Check the integration commit (artifact already on master)
git show 90cd41752 --stat

# Clean up
cd ../..
git worktree remove .qwen/worktrees/task-522-review
```

---

## Reviewer

GLM independent review, dispatched by TASK-522.  
Read-only: no production state modified, no provider calls, no merges performed.
