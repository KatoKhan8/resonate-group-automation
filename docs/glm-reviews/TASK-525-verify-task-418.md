# GLM Independent Verification: TASK-418

**Review Date:** 2026-10-04  
**Reviewer:** GLM (independent verification layer)  
**Task:** TASK-418 — Offer Config Consistency Check  
**Branch:** origin/qwen-worker-r9-t391  
**Branch HEAD SHA:** d4effa8d82c50fc4166fd6e6780f069d728eda00  
**Verified SHA:** d4effa8d82c50fc4166fd6e6780f069d728eda00 (confirmed via `git rev-parse`)  
**Worktree:** .qwen/worktrees/glm-525 (isolated, detached HEAD at target SHA)

---

## 1. Artifact Existence

**Status:** EXISTS, but the artifact is a finding, not code.

TASK-418's result block states:
- **ARTIFACT KIND:** finding (read-only audit, no code or test changes)
- **FILES CHANGED:** none (task file only)
- **STATUS:** DONE

The task file moved from `docs/qwen-tasks/TODO/TASK-418-offer-config-consistency-check.md` to `docs/qwen-tasks/DONE/TASK-418-offer-config-consistency-check.md` on the branch. This is a queue move, not a code change. The result block itself is the artifact.

**Verification:**
```bash
git ls-tree -r --name-only d4effa8d8 -- docs/qwen-tasks/ | grep TASK-418
# Output: docs/qwen-tasks/DONE/TASK-418-offer-config-consistency-check.md
```

The file `config/clients/productive-offers.yaml` is identical to master (0 lines changed in `git diff master...d4effa8d8 -- config/clients/productive-offers.yaml`), confirming the audit was read-only.

---

## 2. Existence Is Not Function

**Status:** NOT APPLICABLE — no code was produced.

TASK-418 was a read-only audit task. The result block claims no code changes, no tests, and no production callers. This is consistent with the task description: "Read `config/clients/productive-offers.yaml` end to end and check for internal contradictions."

There is no chain to trace because no chain was built. The artifact is the finding itself.

---

## 3. Falsification of Result Claims

**Status:** ONE CLAIM FALSIFIED.

The result block claims 12 checks were performed and "none found" contradictions. I independently re-derived the file's state at SHA d4effa8d8 and found one inconsistency the audit missed.

### Check #9 Falsification: No-Dash Rule

**Audit claim:** "No dashes in any business_problem, value_proposition, concrete_deliverable or cta"

**Actual state:**
- Line 107 (OFFER-RP-001, `concrete_deliverable`): `a forward-looking view of who is booked where and where the next hire goes` — contains "forward-looking" with a dash.
- Line 249 (OFFER-B-OPERATIONS, `concrete_deliverable`): `a single view of every project and its delivery status, time entries linked to the project and budget they belong to, and a forward looking view of who is booked where` — contains "forward looking" with NO dash.

**Inconsistency:** OFFER-B composes OFFER-RP-001 (among others), and the file's own comment at line 162 states: "No dashes in any prospect facing field, per the standing rule. `14 day` rather than the hyphenated form is deliberate, not a typo."

OFFER-B correctly removed the dash ("forward looking"), but OFFER-RP-001 still has it ("forward-looking"). This is an internal contradiction: the component offer violates the rule the composed offer enforces, and the two are not consistent.

**Reproduction command:**
```bash
git show d4effa8d8:config/clients/productive-offers.yaml | grep -n "forward"
# Output:
# 107:    concrete_deliverable: a forward-looking view of who is booked where and where the next hire goes
# 249:    concrete_deliverable: ... and a forward looking view of who is booked where
```

### Other Checks Verified

| # | Check | Independent Verification | Result |
|---|-------|--------------------------|--------|
| 1 | CTA links vs "THE ONLY allowed CTA link" | All 6 `cta_link` and `link` fields in mechanisms/offers are `https://productive.io/get-started/` (lines 210, 284, 481, 488, 496). Comment at line 481 matches. | ✓ CONSISTENT |
| 2 | `composes:` references resolve | OFFER-A → [OFFER-PR-001, OFFER-BU-001] (line 170); OFFER-B → [OFFER-PM-001, OFFER-TT-001, OFFER-RP-001] (line 244). All exist. | ✓ CONSISTENT |
| 3 | `mechanism:` references resolve | Both composed offers → `ae_walkthrough_premium_trial` (lines 206, 276). Key exists at line 483. | ✓ CONSISTENT |
| 4 | AI page_texts match verbatim | All 7 AI feature `page_text` values in offers match `evidence.productive_ai.page_text` word-for-word (lines 192-202, 262-274 vs 446-453). | ✓ CONSISTENT |
| 5 | `traces_to:` keys resolve | All AI capabilities trace to `productive_ai` (lines 194, 196, 264, 266, 268, 270, 272). Key exists at line 444. | ✓ CONSISTENT |
| 6 | Approval statuses match header | Header (line 23): "Offers A v2 and B v2 stay approved". Lines 212, 286: `approval_status: approved`. Lines 69, 83, 97, 111, 125, 139: `approval_status: pending` (6 simple offers). | ✓ CONSISTENT |
| 7 | `approved_at_sha` matches `approval_history.v2.at_sha` | Lines 215, 289: `approved_at_sha: a04574be`. Lines 234, 307: `at_sha: a04574be` in v2 blocks. | ✓ CONSISTENT |
| 8 | Persona consistency | OFFER-A: `persona: economic_buyer` (line 172); composes OFFER-PR-001 (economic_buyer, line 90) and OFFER-BU-001 (economic_buyer, line 76). OFFER-B: `persona: champion` (line 246); composes OFFER-PM-001 (champion, line 62), OFFER-TT-001 (champion, line 69), OFFER-RP-001 (champion, line 104). | ✓ CONSISTENT |
| 9 | No-dash rule | **FALSIFIED** — line 107 has "forward-looking" with a dash. | ✗ INCONSISTENT |
| 10 | `missing.demo_link` vs `mechanisms.demo` | `missing.demo_link` (line 333): "no live demo environment or recorded demo available". `mechanisms.demo` (line 478): "Productive demo or walkthrough with a Productive AE". These are different things: self-service demo link vs AE-led walkthrough. | ✓ NOT A CONTRADICTION |
| 11 | `enforced_by` vs `enforcement_status` | `enforced_by` (line 55): "sequencegate checks step_objectives". `enforcement_status` (line 58): "DATA_ONLY_NOT_YET_ENFORCED". Inline comment (line 56): "ENFORCEMENT IS NOT YET BUILT". The tension is documented, not hidden. | ✓ NOT A HIDDEN CONTRADICTION |
| 12 | `permitted_chains` vs offer ai_capabilities | `permitted_chains` (lines 47-50) name primary AI angle per persona. Offers list all available AI capabilities. These are different scopes (per-message selection vs full inventory). | ✓ NOT A CONTRADICTION |

---

## 4. Test Falsifiability

**Status:** NOT APPLICABLE — no tests were produced.

TASK-418 was a read-only audit. There are no tests to falsify.

---

## 5. Deletion Check

**Status:** NO DELETIONS of production code.

```bash
git diff master...d4effa8d8 --diff-filter=D --name-only
# Output:
# docs/qwen-tasks/TODO/TASK-302-re-render-504-and-build-the-review-file.md
# docs/qwen-tasks/TODO/TASK-418-offer-config-consistency-check.md
```

Two task files were deleted from TODO, but they were moved to BLOCKED and DONE respectively:
```bash
git ls-tree -r --name-only d4effa8d8 -- docs/qwen-tasks/ | grep -E "TASK-302|TASK-418"
# Output:
# docs/qwen-tasks/BLOCKED/TASK-302-re-render-504-and-build-the-review-file.md
# docs/qwen-tasks/DONE/TASK-418-offer-config-consistency-check.md
```

These are queue moves, not content deletions. No production code, tests, or configuration files were deleted.

---

## 6. Scope Drift

**Status:** SIGNIFICANT SCOPE DRIFT.

The branch `qwen-worker-r9-t391` carries 46 files changed (+5285, -212) across multiple tasks:
- TASK-391: wire cold_email_writing and linkedin_writing into generate.py (primary task)
- TASK-311: ingest carries LinkedIn column
- TASK-418: offer config consistency check (this task)
- TASK-464: qualify.company RAISES on ingest-written record
- TASK-302: moved to BLOCKED
- Multiple GLM verification tasks (TASK-465 through TASK-477)
- COMPLIANCE.md, PROBLEM-REGISTER.md, and other documentation updates

**Cherry-pick requirement:** TASK-418's artifact is the task file move from TODO to DONE. This is a single file move and can be cherry-picked cleanly. However, the branch carries substantial other work that is unrelated to TASK-418.

**Recommendation:** Do not merge the branch to integrate TASK-418. Cherry-pick the task file move:
```bash
git cherry-pick d4effa8d8 -- docs/qwen-tasks/DONE/TASK-418-offer-config-consistency-check.md
```

Or, more simply, move the file on master directly since the audit itself produced no code.

---

## Findings

### Finding 1: Missed Dash Inconsistency

**Severity:** Suggestion  
**Confidence:** High  
**File:** config/clients/productive-offers.yaml  
**Lines:** 107, 249  
**Category:** correctness  

**Summary:** OFFER-RP-001's `concrete_deliverable` (line 107) contains "forward-looking" with a dash, but OFFER-B-OPERATIONS (which composes OFFER-RP-001) correctly removed the dash to "forward looking" (line 249). The file's own comment at line 162 states the no-dash rule is a "standing rule" and that "`14 day` rather than the hyphenated form is deliberate, not a typo."

**Failure Scenario:** A future audit or lint check enforcing the no-dash rule would flag OFFER-RP-001 but not OFFER-B, creating an inconsistency where the component offer violates a rule the composed offer follows. The audit's check #9 claimed "No dashes in any business_problem, value_proposition, concrete_deliverable or cta" but this is false.

**Direction:** fails-closed (the audit reported a clean pass when one contradiction exists)

**Baseline:** regression (the audit should have caught this)

---

## Disposition

**FINDING 1:** EXISTING TASK (the dash inconsistency is a minor data quality issue that can be fixed in place; no separate task is needed)

**Overall Assessment:** TASK-418's audit was thorough but missed one internal inconsistency. The result block's claim of "none found" is incorrect — there is one contradiction between OFFER-RP-001 and OFFER-B regarding the no-dash rule.

The audit correctly identified 11 of 12 checks as consistent, and correctly identified that checks #10, #11, and #12 are not contradictions. The missed dash inconsistency is a minor data quality issue, not a safety or architectural defect.

---

## Recommendation

**REWORK**

**Reason:** The result block claims "No dashes in any business_problem, value_proposition, concrete_deliverable or cta" but line 107 has "forward-looking" with a dash. The audit should have caught this and reported it, even if the finding was "one minor inconsistency found" rather than "none found."

**Required action:**
1. Fix OFFER-RP-001's `concrete_deliverable` to remove the dash: "a forward looking view of who is booked where and where the next hire goes"
2. Update TASK-418's result block to report the finding: "One minor inconsistency found: OFFER-RP-001 has 'forward-looking' (dashed) while OFFER-B correctly removed the dash."
3. Alternatively, accept the finding as-is and fix the dash in a separate commit, updating the task file to note the post-audit fix.

**Merge impact:** TASK-418 produced no code, so there is nothing to merge. The task file move from TODO to DONE can be cherry-picked or replicated on master. The branch carries substantial other work (TASK-391, TASK-311, TASK-464, etc.) that is unrelated to TASK-418 and should be reviewed separately.

**Scope:** The branch has significant scope drift. TASK-418's artifact is a single task file move and can be integrated without merging the branch.

---

## Reproducible Commands

All verification was performed in an isolated worktree at the exact SHA:

```bash
# Create worktree
git worktree add .qwen/worktrees/glm-525 d4effa8d82c50fc4166fd6e6780f069d728eda00 --detach

# Verify SHA
git rev-parse HEAD
# d4effa8d82c50fc4166fd6e6780f069d728eda00

# Check file identity with master
git diff master...d4effa8d8 -- config/clients/productive-offers.yaml
# (empty - file unchanged)

# Find the dash inconsistency
git show d4effa8d8:config/clients/productive-offers.yaml | grep -n "forward"
# 107:    concrete_deliverable: a forward-looking view of who is booked where and where the next hire goes
# 249:    concrete_deliverable: ... and a forward looking view of who is booked where

# Verify task file location
git ls-tree -r --name-only d4effa8d8 -- docs/qwen-tasks/ | grep TASK-418
# docs/qwen-tasks/DONE/TASK-418-offer-config-consistency-check.md

# Check deletions
git diff master...d4effa8d8 --diff-filter=D --name-only
# docs/qwen-tasks/TODO/TASK-302-re-render-504-and-build-the-review-file.md
# docs/qwen-tasks/TODO/TASK-418-offer-config-consistency-check.md
```

---

## Static vs Runtime Proof

**Static proof:** All verification was static (file content analysis). No runtime execution was performed, consistent with the read-only nature of the task.

**Runtime proof:** Not applicable — TASK-418 was a read-only audit with no code or tests.

---

## Summary

TASK-418's audit was mostly correct but missed one internal inconsistency: OFFER-RP-001 has "forward-looking" (dashed) while OFFER-B (which composes it) has "forward looking" (no dash). The file's own comment states the no-dash rule is a "standing rule," making this a real contradiction the audit should have reported.

The result block's claim of "none found" is incorrect. The task should be reworked to either fix the dash and report the fix, or report the inconsistency as a finding.

**Disposition:** REWORK  
**Reason:** One missed contradiction in the audit's check #9.  
**Merge recommendation:** Do not merge the branch; cherry-pick or replicate the task file move on master.
