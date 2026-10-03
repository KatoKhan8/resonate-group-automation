# TASK-484 — GLM independent verification of TASK-328

**Review target:** TASK-328, "the approval hash is recorded and never checked"
**Branch reviewed:** `origin/qwen-worker-12-r9`
**Target SHA (named in task file):** `83a91e9fda36b6eb510b38d3e652e98b2ffb43c1`
**Actual branch HEAD at review time:** `34bf792bebc52d35ef218096a42616b333b9cce5` (branch has moved)
**Reviewed SHA:** `83a91e9fda36b6eb510b38d3e652e98b2ffb43c1` (per task instruction)
**Review date:** 2026-10-04
**Worktree:** `.qwen/worktrees/glm-484` (detached HEAD at target SHA, now removed)

---

## Summary

**DISPOSITION: REWORK**

The core work is correct: `review_hash=None` is threaded through three production functions and forwarded to `reviewapproval.require`. The 14 new tests pass and are connected to the implementation. However:

1. **ZERO production callers pass `review_hash`**, so the mismatch branch in `require` is STILL unreachable in production. The gate was unreachable before TASK-328 and remains unreachable after it. The parameter exists but is never consumed.
2. **Significant scope drift**: the branch carries work from TASK-427, TASK-395, and TASK-449 beyond TASK-328's scope.
3. **One test has a quality issue**: the mutation test for `resume_campaign` does not mock the transport layer, so it fails for the wrong reason when the wiring is broken.

The task acknowledges finding #1 in its result block and frames it as a deliberate scoping decision requiring an operator decision. The GLM protocol is explicit: "Zero production callers means DISCONNECTED, which is a rework and not a merge."

---

## Finding 1: The artifact exists and the tests pass

**Status:** VERIFIED

The test file `tests/test_an_approval_does_not_survive_a_re_render.py` exists on the target SHA and is not on master. All 14 tests pass:

```
Ran 14 tests in 0.249s
OK
```

The code changes are minimal and surgical:
- `src/providers/bison.py`: 3 functions gain `review_hash=None`, 3 call sites forward it
- `src/providers/heyreach.py`: 1 function gains `review_hash=None`, 1 call site forwards it
- `src/reviewapproval.py`: NOT modified (correctly, per task instruction)

**Evidence:**
```bash
git show 83a91e9fda36b6eb510b38d3e652e98b2ffb43c1:tests/test_an_approval_does_not_survive_a_re_render.py | wc -l
# 178 lines

cd .qwen/worktrees/glm-484 && py -3 -m unittest tests.test_an_approval_does_not_survive_a_re_render -v
# 14 tests, all pass
```

---

## Finding 2: ZERO production callers pass `review_hash` — DISCONNECTED

**Status:** VERIFIED, CRITICAL

Every occurrence of `review_hash` in `src/` (outside `reviewapproval.py`) is either:
- A function definition parameter (`def resume_campaign(..., review_hash=None)`)
- An internal forwarding to `reviewapproval.require(campaign_id, review_hash=review_hash)`

**No production caller passes a value.** The actual callers:

```
src/orchestrator.py:667    bison.resume_campaign(...)           # no review_hash
src/orchestrator.py:672    heyreach.resume_campaign(pid)        # no review_hash
src/bisonfactory.py:1926   bison.attach_leads(provider_id, ids) # no review_hash
src/web/app.py:1631        api.resume_campaign                  # no review_hash
```

**Consequence:** The mismatch branch in `reviewapproval.require` (line 149: `if review_hash is not None and ...`) can STILL never fire in production. The gate was unreachable before TASK-328 and remains unreachable after it. The parameter exists but is never consumed.

The task's result block acknowledges this: "No existing caller passes `review_hash` yet, so behaviour is identical until a caller is updated to thread the hash from the review file." The task frames this as a deliberate scoping decision requiring an operator decision about whether to make `review_hash` mandatory.

The GLM protocol is explicit: **"Existence is not function... Zero production callers means DISCONNECTED, which is a rework and not a merge."**

**Evidence:**
```bash
cd .qwen/worktrees/glm-484 && grep -rn "review_hash" src/ --include="*.py" | grep -v "def " | grep -v "reviewapproval.py" | grep -v "#"
# Only internal forwarding, no callers

cd .qwen/worktrees/glm-484 && grep -n "resume_campaign\|activate_campaign\|attach_leads" src/orchestrator.py src/bisonfactory.py src/web/app.py | grep -v "def "
# All callers, none pass review_hash
```

---

## Finding 3: Mutation test detects broken wiring but fails for the wrong reason

**Status:** VERIFIED, test quality issue

I performed the mutation: removed `review_hash=review_hash` from `bison.resume_campaign` line 1911, changing it to `reviewapproval.require(campaign_id)`. The test `test_resume_campaign_refuses_on_hash_mismatch` FAILED, but not for the intended reason:

**Expected:** `reviewapproval.NotApproved` (gate refused)
**Actual:** `src.providers.MissingKey: no BISON_KEY in config/.env` (transport layer)

The test does not mock the transport layer (`_post`), so when the gate passes (because no hash is forwarded), the code continues and tries to make a real API call, which fails because there's no BISON_KEY.

**This is a valid falsification** (the test DID detect the broken wiring), but it reveals a test quality issue: the test can fail for reasons other than the gate. A better test would mock the transport so that the only way to fail is through the gate.

**Note:** The `NoProviderCallIsMade` tests DO mock the transport correctly and would catch this mutation for the right reason.

**Evidence:**
```bash
# Mutation applied: line 1911 changed to reviewapproval.require(campaign_id)
cd .qwen/worktrees/glm-484 && py -3 -m unittest tests.test_an_approval_does_not_survive_a_re_render.EveryCallSiteForwardsTheHash.test_resume_campaign_refuses_on_hash_mismatch -v
# FAILED with MissingKey, not NotApproved
```

---

## Finding 4: Scope drift — branch carries work from three other tasks

**Status:** VERIFIED

The branch carries changes beyond TASK-328's scope:

**TASK-427 (offer selection validation):**
- `src/generate_campaign.py` — 145 lines changed, offer validation scoped to selected offer
- `tests/test_only_the_selected_offer_is_validated.py` — 417 lines, new test file

**TASK-395 (spend ledger client name):**
- `scripts/glm_verify_branch.py` — 9 lines changed, `_read_spend` looks for "unattributed" instead of "_model"
- `tests/test_glm_verify_branch_read_spend_uses_unattributed.py` — 65 lines, new test file

**TASK-449 (order-dependent suite failures):**
- `tests/test_the_readback_cache_cannot_lie_about_its_age.py` — 12 lines changed, cleanup refactored

**Other changes:**
- `tests/offline.py` — `NetworkBlocked` now inherits from `OSError` as well as `RuntimeError`
- `tests/test_e2e.py` — file handle properly closed with `with` statement

**Consequence:** Merging this branch would bring in work from at least three other tasks. The task file says "Merging pollution to save time is forbidden here." These changes should be cherry-picked separately or the branch should be rebased to carry only TASK-328's work.

**Evidence:**
```bash
git diff master...83a91e9fda36b6eb510b38d3e652e98b2ffb43c1 --stat
# 24 files changed, 2314 insertions(+), 46 deletions(-)

git log --oneline 83a91e9fda36b6eb510b38d3e652e98b2ffb43c1 ^master -- src/generate_campaign.py
# c84654273 TASK-427 tests: the fixture domain moves to a reserved one
# 6b494b16c Finding: rec["research"] has two shapes and neither lets the new path write copy
# 9017c6a68 TASK-427: _check_offers validates the SELECTED offer, not the library
```

---

## Finding 5: No deletion risk

**Status:** VERIFIED

```bash
git diff master...83a91e9fda36b6eb510b38d3e652e98b2ffb43c1 --diff-filter=D --name-only
# (empty)
```

No files would be deleted by merging this branch.

---

## Finding 6: The task's scope decision is correct but incomplete

**Status:** VERIFIED

The task explicitly says: "Making `review_hash` mandatory would refuse every campaign whose approval row predates this change — including 493, which is ACTIVE and sending right now. That is an operator decision about existing approvals, not yours."

This is correct: making it mandatory would break campaign 493. But the task also says: "Thread the hash from the review file to the gate." The hash is threaded to the functions, but not from the review file to the callers. The chain is incomplete:

```
review file → ??? → caller function → require(campaign_id, review_hash=...)
                ^^^
                MISSING
```

The task's result block says: "RECOMMENDED CLAUDE ACTION: Review and integrate. The operator decision on whether to make `review_hash` mandatory is separate and needs the count of existing approval rows with vs. without a hash (live-state access owed from Claude's worktree)."

This is the right next step, but it does not satisfy the GLM protocol's requirement that the parameter be consumed by at least one production caller.

---

## Recommended Claude action

**REWORK**, with the following steps:

1. **Update at least one production caller to pass `review_hash`.** The minimum viable change is to update `bisonfactory.py:1926` (`bison.attach_leads(provider_id, ids)`) to read the hash from the review file and pass it. This proves the chain is connected end-to-end.

2. **Clean up scope drift.** Either:
   - Rebase the branch to carry only TASK-328's work, or
   - Cherry-pick TASK-328's commits onto a clean branch from master

3. **Fix the test quality issue.** Mock the transport layer in `test_resume_campaign_refuses_on_hash_mismatch` so it fails for the right reason.

4. **Operator decision:** After #1 is done, the operator can decide whether to make `review_hash` mandatory. This requires reading `work/review-approvals.jsonl` to count existing approval rows with vs. without a hash (live-state access, Claude's worktree only).

---

## What this review did NOT verify

- **Runtime proof:** I did not run a live campaign activation with a mismatched hash. This would require provider credentials and would violate the production freeze. The tests are sufficient proof at the code level.
- **Full suite:** I did not run the full test suite. The task's result block claims "12,563 passed, 0 failures, 0 errors" but I did not verify this. The TASK-328-specific tests pass.
- **TASK-427, TASK-395, TASK-449 work:** I did not review the correctness of the other work on the branch. That work should be reviewed separately.

---

## Disposition summary

| Finding | Status | Severity |
|---------|--------|----------|
| Artifact exists, tests pass | VERIFIED | — |
| ZERO production callers pass `review_hash` | VERIFIED | CRITICAL |
| Mutation test fails for wrong reason | VERIFIED | Suggestion |
| Scope drift (3 other tasks) | VERIFIED | Critical |
| No deletion risk | VERIFIED | — |
| Task's scope decision correct but incomplete | VERIFIED | Critical |

**RECOMMENDATION: REWORK**

The core work is correct and the tests are good, but the gate is still unreachable in production and the branch carries significant scope drift. The minimum rework is to update at least one production caller to pass `review_hash` and to clean up the scope drift.
