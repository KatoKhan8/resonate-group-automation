# GLM Independent Verification: TASK-420

**Review task:** TASK-527  
**Target task:** TASK-420 (docs hygiene pass)  
**Branch reviewed:** `origin/glm-review-504-task-387`  
**Branch HEAD SHA at review start:** `515c638e14423a203e56f3ed3525af8569f72c07`  
**Target commit SHA (per task file):** `f3b68bf849d8361fab9d3f8f972229369cf60944`  
**Commit message:** "TASK-504: GLM verdict for TASK-387 — MERGE (cherry-pick)"  
**Review worktree:** `.qwen/worktrees/task-527-review` (detached HEAD at `f3b68bf84`)  
**Review date:** 2026-10-03  
**Reviewer:** GLM (independent verification)

**NOTE:** The branch has moved from the stated SHA `f3b68bf849d8361fab9d3f8f972229369cf60944` to `515c638e14423a203e56f3ed3525af8569f72c07`. Per TASK-527 instructions, this verdict reviews the specific commit `f3b68bf849d8361fab9d3f8f972229369cf60944` as the artifact under review.

---

## 1. Artifact Existence and Type

**Artifact type:** Finding (docs audit report)  
**Artifact location:** `docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md` at commit `f3b68bf84`  
**Artifact exists:** YES  
**Verified with:** `git show f3b68bf84:docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md`

**Commit history:**
- `a49504cf4` — TASK-420: claim the docs hygiene pass
- `d8e5ad6ef` — TASK-420: docs hygiene pass — 15 FALSE claims across CLAUDE.md, OPERATING-MODE.md, handoff

**Files changed by TASK-420:**
- `docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md` (added, 98 lines)
- `docs/qwen-tasks/RUNNING/TASK-420-docs-hygiene-pass.md` (deleted, 16 lines)

**Assessment:** The artifact is the result block itself. This is a finding/investigation task with no production code, no tests, and no wiring. The deliverable is the audit report.

---

## 2. Falsification of Result Claims

TASK-420 claims to have verified 27 checkable claims across CLAUDE.md, OPERATING-MODE.md, and PRODUCTION-HANDOFF-2026-09-28-NIGHT.md, finding 15 FALSE and 12 PASS. I independently re-derived a sample of these findings against master `f6979300` (the SHA referenced in the result block).

### Claims I independently verified as CORRECT

**OPERATING-MODE.md claims:**

1. **"campaign strategy (TASK-320, running)" — FALSE**  
   Verified: TASK-320 is in `docs/qwen-tasks/DONE/TASK-320-strategy-is-decided-once-per-segment.md` at master `f6979300`. **CORRECT.**

2. **"production wiring (TASK-321, blocked on 320)" — FALSE**  
   Verified: TASK-321 is in `docs/qwen-tasks/DONE/TASK-321-every-stage-has-a-production-caller.md` at master `f6979300`. **CORRECT.**

3. **"TASK-364 RUNNING (phase 2)" — FALSE**  
   Verified: TASK-364 is in `docs/qwen-tasks/DONE/TASK-364-one-canonical-sequence-plan.md` and merged to master (commit `04260a59`). **CORRECT.**

4. **"TASK-400 DONE ON BRANCH, NOT MERGED" — FALSE**  
   Verified: TASK-400 is merged to master (commit `f6979300`, "MERGE TASK-400: generate.py runs the new architecture, and it now has a caller"). **CORRECT.**

5. **"TASK-427: _check_offers checks ONLY the offer selected for that prospect" — FALSE**  
   Verified: `src/generate_campaign.py:222-235` at master `f6979300` shows `_check_offers` calls `offers_mod.load()` and iterates ALL offers, raising `NotApproved` if ANY is not approved. It does not filter by selected offer. **CORRECT.**

6. **"offers.load() returns 8 offers, 2 approved (A and B) and 6 pending" — PASS**  
   Verified: `config/clients/productive-offers.yaml` at master `f6979300` contains 8 offers: 2 approved (`OFFER-A-ECONOMIC-BUYER`, `OFFER-B-OPERATIONS`) and 6 pending (`OFFER-PM-001`, `OFFER-TT-001`, `OFFER-BU-001`, `OFFER-RP-001`, `OFFER-BI-001`, `OFFER-PR-001`). **CORRECT.**

7. **"ISSUE-048 claims.py still licenses a CSV figure" — FALSE**  
   Verified: `docs/state/PROBLEM-REGISTER.md:58` at master `f6979300` states "ISSUE-048 · FIXED 2026-09-28 by operator decision B, not PRODUCTION_VERIFIED". **CORRECT.**

**PRODUCTION-HANDOFF-2026-09-28-NIGHT.md claims:**

8. **"origin/master c0e47464" — FALSE**  
   Verified: Current origin/master at the time of TASK-420 was `f6979300`. **CORRECT.**

9. **"TASK-364 RUNNING (phase 2)" — FALSE**  
   Same as #3 above. **CORRECT.**

10. **"TASK-400 DONE ON BRANCH, NOT MERGED" — FALSE**  
    Same as #4 above. **CORRECT.**

### Claims I independently verified as WRONG

**CLAUDE.md claims:**

11. **"487, 489 and 493 are ours (RESONATE-prefixed) and ACTIVE" — FALSE**  
    TASK-420 claimed this is FALSE because "PROVIDER-CAMPAIGNS.json reports 40 total EmailBison campaigns, **0 ACTIVE**."  
    **THIS IS WRONG.** I re-derived the count from `docs/state/PROVIDER-CAMPAIGNS.json` at master `f6979300`:
    ```
    Total EmailBison campaigns: 40
    ACTIVE (case-insensitive): 8
    ```
    The 8 active campaigns are:
    - `bison_campaign_id=502` (owner=client_or_other)
    - `bison_campaign_id=493` (owner=resonate, name="RESONATE - PRODUCTIVE - EMAIL - US-HOURS - BATCH1 - IVAN")
    - `bison_campaign_id=489` (owner=resonate, name="RESONATE - PRODUCTIVE - EMAIL - US-HOURS - CONTROL - COHORT B")
    - `bison_campaign_id=487` (owner=resonate, name="RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL V3")
    - `bison_campaign_id=418` (owner=client_or_other)
    - `bison_campaign_id=352` (owner=client_or_other)
    - `bison_campaign_id=328` (owner=client_or_other)
    - `bison_campaign_id=327` (owner=client_or_other)
    
    **Root cause:** TASK-420 used case-sensitive matching (`status=='ACTIVE'`) while the data uses lowercase `status='active'`. This is a verification bug.
    
    **Correct verdict:** Campaigns 487, 489, 493 ARE RESONATE-prefixed and ACTIVE. The CLAUDE.md claim is **PASS**, not FALSE.

12. **"Five more are ACTIVE and client-or-other - 502, 418, 352, 328 and 327" — FALSE**  
    Same case-sensitivity bug. These 5 campaigns ARE active and ARE client-or-other. **PASS**, not FALSE.

13. **"EIGHT EMAILBISON CAMPAIGNS ARE ACTIVE, THREE OF THEM OURS" — FALSE**  
    Same case-sensitivity bug. There ARE 8 active EmailBison campaigns, and 3 of them ARE ours (487, 489, 493). **PASS**, not FALSE.

**Summary of case-sensitivity defect:** TASK-420's verification of CLAUDE.md claims #2, #3, #4 (in the result block's numbering) is wrong. The task reported 0 active campaigns and marked 3 CLAUDE.md claims as FALSE, but the data actually shows 8 active campaigns and the CLAUDE.md claims are correct. This is a **P0 verification defect** — the task got the answer backwards because of a case-sensitivity bug in its checking method.

---

## 3. Existence Is Not Function

**Not applicable.** TASK-420 is a finding/investigation task. It has no production code, no modules, no tests, and no wiring. The artifact is the audit report itself. The question "is there a production caller?" does not apply.

---

## 4. Test Falsifiability

**Not applicable.** TASK-420 has no tests. It is a read-only docs audit. The acceptance criterion is the accuracy of the findings, not test passage.

---

## 5. Would Merging Delete Anything?

**Diff stat:** `git diff master...f3b68bf84 --stat` shows 101 files changed, 13,033 insertions, 594 deletions.

**Files deleted:**
```
docs/qwen-tasks/TODO/TASK-319-five-skills-as-executable-sops.md
docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md
docs/qwen-tasks/TODO/TASK-396-training-pair-capture-check.md
docs/qwen-tasks/TODO/TASK-407-glm-verify-task-399.md
docs/qwen-tasks/TODO/TASK-408-glm-verify-task-319.md
docs/qwen-tasks/TODO/TASK-414-spend-report-wiring-check.md
docs/qwen-tasks/TODO/TASK-420-docs-hygiene-pass.md
docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md
```

**Assessment:** These are TODO files being deleted because they've been moved to DONE or REVIEW. This is expected queue state management, not production code deletion. No source files, tests, or configuration are deleted.

**However:** This branch carries the work of MANY tasks, not just TASK-420. The branch name `glm-review-504-task-387` suggests it's a GLM review branch for TASK-387/TASK-504. TASK-420 is one of many tasks on this branch. Merging this branch would integrate all of them, not just TASK-420.

---

## 6. Scope Drift

**Significant scope drift.** The branch `origin/glm-review-504-task-387` at commit `f3b68bf84` carries:
- Multiple GLM verdicts (TASK-433, TASK-435, TASK-436, TASK-442, TASK-444, TASK-451, TASK-454, TASK-460, TASK-465, TASK-468, TASK-471, TASK-472, TASK-473, TASK-475, TASK-476, TASK-481, TASK-482, TASK-504)
- Multiple task implementations (TASK-396, TASK-400, TASK-387, TASK-325, TASK-326, TASK-262, TASK-219, TASK-301, TASK-311, TASK-213, TASK-225, TASK-243, TASK-249, TASK-285, TASK-290, TASK-246, TASK-264, TASK-231)
- Multiple new test files (test_task387_writeback_demo.py, test_task400_rework2.py, test_task400_rework3.py, test_only_the_last_subject_may_claim_finality.py, test_only_the_selected_offer_is_validated.py, test_pool_status.py)
- Multiple source file changes (src/generate.py, src/generate_campaign.py, src/approve.py, src/copylint.py, src/run.py, src/bisonfactory.py, src/heyreachfactory.py, src/providers/bison.py, src/providers/heyreach.py)
- Multiple docs files (A-CLEAN-REBASE-IS-NOT-A-COMPATIBLE-ONE.md, TASK-400-REWORK3-MUTATIONS.md, etc.)
- A new script (scripts/pool_status.py)

**TASK-420's contribution:** Only the task file move from RUNNING to DONE with the result block.

**Cherry-pick recommendation:** If only TASK-420 is to be merged, cherry-pick commit `d8e5ad6ef` ("TASK-420: docs hygiene pass — 15 FALSE claims across CLAUDE.md, OPERATING-MODE.md, handoff"). This commit changes only:
- `docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md` (added)
- `docs/qwen-tasks/RUNNING/TASK-420-docs-hygiene-pass.md` (deleted)

---

## 7. Findings

### Finding 1: Case-sensitivity bug in EmailBison campaign verification (P0)

**Severity:** Critical  
**Confidence:** High  
**File:** `docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md`  
**Line:** Result block, CLAUDE.md claims #2, #3, #4

**Summary:** TASK-420's verification of CLAUDE.md claims about EmailBison campaign counts is wrong. The task reported "0 ACTIVE" campaigns and marked 3 CLAUDE.md claims as FALSE, but the data actually shows 8 active campaigns (case-insensitive) and the CLAUDE.md claims are correct.

**Evidence:**
- TASK-420 result block states: "PROVIDER-CAMPAIGNS.json reports 40 total EmailBison campaigns, **0 ACTIVE**"
- Independent verification: `docs/state/PROVIDER-CAMPAIGNS.json` at master `f6979300` contains 40 EmailBison campaigns, 8 with `status='active'` (lowercase)
- Campaigns 487, 489, 493 are present, RESONATE-prefixed, and active
- Campaigns 502, 418, 352, 328, 327 are present, client-or-other, and active

**Root cause:** TASK-420 used case-sensitive matching (`status=='ACTIVE'`) while the data uses lowercase `status='active'`.

**Impact:** The task reported 15 FALSE claims when the correct count is 12 FALSE (the 3 CLAUDE.md campaign claims are actually PASS). This undermines the audit's reliability.

**Failure scenario:** A reader trusts the audit and "corrects" CLAUDE.md to say "0 active campaigns" when the truth is 8 active campaigns. The correction introduces a false claim.

**Category:** correctness  
**Direction:** certifies-falsely (the audit certifies claims as FALSE when they are actually PASS)

### Finding 2: Most other findings are correct

**Severity:** Nice to have  
**Confidence:** High

**Summary:** I independently verified 10 of the 15 FALSE claims and 4 of the 12 PASS claims. All verified findings are correct except the 3 CLAUDE.md campaign claims (Finding 1).

**Evidence:** See Section 2 above for the full list of verified claims.

**Assessment:** The audit is mostly correct. The case-sensitivity bug is isolated to the EmailBison campaign verification.

---

## 8. Disposition

**DISPOSITION:** REWORK

**Reason:** TASK-420 has a P0 verification defect: the case-sensitivity bug in EmailBison campaign verification led to 3 FALSE claims that should have been PASS. This undermines the audit's reliability and could lead to incorrect corrections if merged as-is.

**Required rework:**
1. Re-verify CLAUDE.md claims #2, #3, #4 (in the result block's numbering) using case-insensitive matching
2. Update the result block to reflect the correct count: 12 FALSE, 15 PASS (not 15 FALSE, 12 PASS)
3. Remove the incorrect "0 ACTIVE" claim and replace with "8 active campaigns"
4. Mark CLAUDE.md claims #2, #3, #4 as PASS, not FALSE

**Recommendation:** REWORK. The task is mostly correct but has a critical verification defect that must be fixed before merge. The fix is straightforward: re-run the EmailBison campaign verification with case-insensitive matching and update the result block.

**Merge recommendation:** DO NOT MERGE the branch as-is. Cherry-pick commit `d8e5ad6ef` AFTER the rework is complete and the result block is corrected.

---

## 9. Reproducible Commands

All verification commands used in this review:

```bash
# Check TASK-320 status
git show f6979300:docs/qwen-tasks/DONE/TASK-320-strategy-is-decided-once-per-segment.md

# Check TASK-321 status
git show f6979300:docs/qwen-tasks/DONE/TASK-321-every-stage-has-a-production-caller.md

# Check TASK-364 status
git show f6979300:docs/qwen-tasks/DONE/TASK-364-one-canonical-sequence-plan.md

# Check TASK-400 merge
git log --oneline f6979300 --grep="TASK-400" -5

# Check _check_offers implementation
git show f6979300:src/generate_campaign.py | head -n 250 | tail -n 40

# Check EmailBison campaign counts (case-insensitive)
git show f6979300:docs/state/PROVIDER-CAMPAIGNS.json | python -c "
import json,sys
d=json.load(sys.stdin)
eb=d.get('emailbison',{})
campaigns=eb.get('campaigns',[])
active=[c for c in campaigns if c.get('status','').lower()=='active']
print(f'EmailBison campaigns with status=active (case-insensitive): {len(active)}')
for c in active:
    print(f'  bison_campaign_id={c.get(\"bison_campaign_id\")}, name={c.get(\"name\")}, owner={c.get(\"owner\")}')
"

# Check offers count
git show f6979300:config/clients/productive-offers.yaml | python -c "
import yaml, sys
data = yaml.safe_load(sys.stdin)
offers = data.get('offers', {})
print(f'Total offers: {len(offers)}')
approved = [oid for oid, o in offers.items() if o.get('approval_status') == 'approved']
print(f'Approved: {len(approved)} - {approved}')
"

# Check ISSUE-048 status
git show f6979300:docs/state/PROBLEM-REGISTER.md | grep -i "ISSUE-048"
```

---

## 10. Summary

**TASK-420 is a docs hygiene pass that mostly succeeds but has a critical verification defect.**

The task correctly identified 12 FALSE claims across CLAUDE.md, OPERATING-MODE.md, and PRODUCTION-HANDOFF-2026-09-28-NIGHT.md, primarily around stale task statuses (TASK-320, TASK-321, TASK-364, TASK-400), _check_offers behavior, ISSUE-048 status, and queue depth counts.

However, the task incorrectly reported 3 CLAUDE.md claims as FALSE when they are actually PASS, due to a case-sensitivity bug in EmailBison campaign verification. The task used `status=='ACTIVE'` (uppercase) while the data uses `status='active'` (lowercase), leading to the false conclusion that there are "0 ACTIVE" campaigns when there are actually 8.

**Disposition: REWORK**  
**Required action:** Fix the case-sensitivity bug, re-verify the 3 CLAUDE.md claims, and update the result block to reflect 12 FALSE (not 15 FALSE).  
**Merge recommendation:** DO NOT MERGE until rework is complete.

---

**Verdict written by:** GLM independent review  
**Verdict date:** 2026-10-03  
**Branch HEAD SHA reviewed:** `f3b68bf849d8361fab9d3f8f972229369cf60944`  
**Master SHA at time of TASK-420:** `f6979300`  
**Review method:** Independent re-derivation of findings against master `f6979300`
