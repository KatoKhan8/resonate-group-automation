# GLM Verdict: TASK-328 — the approval hash is recorded and never checked

## Review metadata

| Field | Value |
|---|---|
| Task | TASK-328 |
| Branch | origin/qwen-worker-12-r9 |
| Nominated HEAD SHA | 83a91e9fda36b6eb510b38d3e652e98b2ffb43c1 |
| Actual HEAD SHA at review time | 34bf792bebc52d35ef218096a42616b333b9cce5 (branch has moved) |
| Reviewed SHA | 83a91e9fda36b6eb510b38d3e652e98b2ffb43c1 (as instructed) |
| Master at review time | 53dc50c8 |
| Isolated worktree | .qwen/worktrees/glm-484 (detached at 83a91e9f) |
| Verdict date | 2026-09-29 |
| Reviewer | GLM (independent, via TASK-484) |

**Branch has moved.** The branch `origin/qwen-worker-12-r9` now points at `34bf792b`, not `83a91e9f`. Per the task instruction, the verdict reviews `83a91e9f` anyway — that is the artifact TASK-328 was submitted against.

---

## 1. Does the artifact exist on this ref?

**YES.** All three files named in the result block exist at the reviewed SHA:

| File | Status | Evidence |
|---|---|---|
| `src/providers/bison.py` | Modified | `_require_approval_for_topup`, `attach_leads`, `resume_campaign` each gain `review_hash=None` and forward it |
| `src/providers/heyreach.py` | Modified | `activate_campaign` gains `review_hash=None` and forwards it |
| `tests/test_an_approval_does_not_survive_a_re_render.py` | New, 178 lines | 14 tests in 3 classes |

TASK-328's own commits are `f4b9a681` (code + test) and `f298ad87` (task file to REVIEW). They touch exactly 3 source/test files plus the task file. No other files are part of this task's work.

---

## 2. Existence is not function — is the chain consumed?

**YES.** The hash now flows from every production call site to the gate:

```
bison.resume_campaign(campaign_id, ..., review_hash=None)
  → reviewapproval.require(campaign_id, review_hash=review_hash)    ✅

bison.attach_leads(campaign_id, lead_ids, review_hash=None)
  → _require_approval_for_topup(campaign_id, review_hash=review_hash)
    → reviewapproval.require(campaign_id, review_hash=review_hash)  ✅

heyreach.activate_campaign(campaign_id, ..., review_hash=None)
  → reviewapproval.require(campaign_id, review_hash=review_hash)    ✅
```

`reviewapproval.require` (unchanged by this task) already had the correct comparison logic:

```python
if review_hash is not None and str(given.get("review_hash")) != str(review_hash):
    raise NotApproved(...)
```

Before this task: all three call sites called `require(campaign_id)` with no `review_hash`, so the mismatch branch was unreachable. After: all three forward the hash.

**Verified by direct execution** in the isolated worktree:
- `reviewapproval.require(CAMPAIGN_ID, rows=[row])` → passes (permissive default)
- `reviewapproval.require(CAMPAIGN_ID, review_hash=HASH_A, rows=[row])` → passes (match)
- `reviewapproval.require(CAMPAIGN_ID, review_hash=HASH_B, rows=[row])` → refuses with message naming campaign and both hashes

**No upstream caller passes `review_hash` yet.** Confirmed by `grep -rn "review_hash" src/orchestrator.py src/bisonfactory.py` — empty. The threading is structurally correct but has no runtime effect until a caller is updated to pass the hash from the review file. This is acknowledged in the result block and is not a defect in this task — the task was to thread the parameter, not to update callers.

**One additional function noted:** `heyreach.resume_campaign` (line 1630) does NOT call `reviewapproval.require` and does NOT gain `review_hash`. This is correct — it is a sealed transport (`LINKEDIN_ACTIVATE`, not in `SUPPORTED`) that is never called directly. The three call sites TASK-328 modified are the only production paths that gate on approval.

---

## 3. Falsification — would the tests pass if the implementation were wrong?

**YES, the tests would fail.** The key falsification path:

The behavioral tests (e.g., `test_resume_campaign_refuses_on_hash_mismatch`) mock `reviewapproval.load` to return a row with `HASH_A`, then call `bison.resume_campaign(CAMPAIGN_ID, review_hash=HASH_B)` through the real entry point, and assert `NotApproved` is raised.

If `resume_campaign` did NOT forward `review_hash` (the pre-fix bug), `require` would receive `review_hash=None`, the permissive default would apply, and no exception would be raised. The test's `assertRaises(NotApproved)` would FAIL.

**Verified by direct test execution:** All 14 tests pass in 0.382s.

**Three signature-only tests are weak but not misleading:** `test_resume_campaign_accepts_review_hash`, `test_activate_campaign_accepts_review_hash`, and `test_attach_leads_accepts_review_hash` only check `inspect.signature` — they prove the parameter exists but not that it is forwarded. However, the behavioral tests in the same class DO prove forwarding, so the weak tests are redundant rather than deceptive.

---

## 4. Are the tests falsifiable?

**YES.** The tests assert on behavior, not source text:

- **Mismatch refuses** — drives through real entry points with mocked `load()`, asserts `NotApproved` with both hashes in the message
- **Match proceeds** — drives through real entry points, asserts no `NotApproved`
- **Omit proceeds** — documents the permissive default
- **No provider call on refusal** — asserts `_post` / `request` / `membership` are not called when the hash mismatches

The tests do NOT use `hasattr`, source text matching, or fake cassettes. They mock the approval store and drive through the real functions.

---

## 5. Would merging delete anything?

**NO.** `git diff master...83a91e9f --diff-filter=D --name-only` returns empty. No files would be deleted.

---

## 6. Scope drift

**SIGNIFICANT.** The branch has 198 commits ahead of master and 24 files changed. TASK-328's own commits (`f4b9a681`, `f298ad87`) touch only 4 files:

- `src/providers/bison.py`
- `src/providers/heyreach.py`
- `tests/test_an_approval_does_not_survive_a_re_render.py`
- `docs/qwen-tasks/REVIEW/TASK-328-*.md`

The other 20 files on the branch belong to other tasks (TASK-908, TASK-913, TASK-914, TASK-915, TASK-916, TASK-917, TASK-441, TASK-459, TASK-467, TASK-472, TASK-475, and others). **Cherry-pick is required** — the branch cannot be merged wholesale.

Files that would need separate cherry-pick or are already merged:
- `src/generate_campaign.py` (145 lines) — not TASK-328
- `tests/test_only_the_selected_offer_is_validated.py` (417 lines) — not TASK-328
- `tests/test_glm_verify_branch_read_spend_uses_unattributed.py` (65 lines) — not TASK-328
- `tests/offline.py`, `tests/test_e2e.py`, `tests/test_the_readback_cache_cannot_lie_about_its_age.py` — not TASK-328
- Multiple GLM review documents — not TASK-328
- Multiple task file stage moves — not TASK-328

---

## Findings

### Finding 1: The fix is correct and minimal
**Disposition: FIXED + VERIFIED**

The three call sites that called `reviewapproval.require(campaign_id)` without `review_hash` now forward it. The gate logic was already correct; the defect was that nobody used it. The fix threads the parameter without changing the default behavior.

### Finding 2: The permissive default is the right call
**Disposition: ACCEPTED DEFERRED RISK**

Making `review_hash` mandatory would refuse every campaign whose approval row predates this change, including campaign 493 which is ACTIVE and sending. The task correctly identifies this as an operator decision and leaves the default permissive. The risk is that the hash check remains ineffective until a caller is updated to pass it — but that is a separate task, not a defect in this one.

### Finding 3: No caller passes review_hash yet
**Disposition: EXISTING TASK (follow-up needed)**

`grep -rn "review_hash" src/orchestrator.py src/bisonfactory.py` returns empty. The threading is in place but no upstream caller reads the hash from the review file and passes it to `resume_campaign`, `activate_campaign`, or `attach_leads`. The fix is structurally correct but has no runtime effect until this follow-up is done. This is acknowledged in the result block.

### Finding 4: Scope drift requires cherry-pick
**Disposition: OPERATOR DECISION REQUIRED**

The branch carries 198 commits and 20 files unrelated to TASK-328. Merging the branch wholesale would bring in unreviewed work from multiple other tasks. The TASK-328 changes should be cherry-picked from commits `f4b9a681` and `f298ad87`.

### Finding 5: Three signature-only tests are weak but not misleading
**Disposition: FALSE POSITIVE**

`test_resume_campaign_accepts_review_hash`, `test_activate_campaign_accepts_review_hash`, and `test_attach_leads_accepts_review_hash` only check `inspect.signature`. They would pass on a comment containing the parameter name. However, the behavioral tests in the same class prove forwarding through real entry points, so the weak tests are redundant safety rather than the primary evidence.

### Finding 6: Live-state measurement not performed
**Disposition: RUNTIME VERIFICATION REQUIRED**

The task asks for the count of existing approval rows with vs. without a hash, so the operator can decide whether to make the hash mandatory. This requires reading `work/review-approvals.jsonl` which is live state in Claude's worktree only. **Not verified — live-state access is owed.**

---

## Recommendation

**MERGE** (via cherry-pick of commits `f4b9a681` and `f298ad87`).

The code change is correct, minimal, and well-tested. It fixes a real defect (the approval hash was unreachable) by threading the parameter through all three production call sites. The permissive default is the right call given the operator decision needed for existing approvals. The tests are falsifiable and drive through real entry points.

**Cherry-pick, not merge.** The branch carries significant scope drift from other tasks.

**Follow-up owed:**
1. An upstream caller (orchestrator or bisonfactory) must be updated to read the hash from the review file and pass it to the modified functions. Until then, the hash check has no runtime effect.
2. The operator decision on whether to make `review_hash` mandatory needs the count of existing approval rows with vs. without a hash (live-state access required).
