# TASK-506: Independent Verification of TASK-390

**Review target:** TASK-390 (GLM Checkpoint B)  
**Branch reviewed:** `origin/qwen-worker-10-r9`  
**Branch HEAD SHA:** `d3b76e3e172b59d86fd9541f15f47fcbf049c857`  
**Review date:** 2026-09-28  
**Reviewer:** Qwen (independent verification)

---

## Summary

TASK-390 is a read-only verification checkpoint that reviewed the offers/persona/strategy chain (Checkpoint B). The task found that TASK-367's dependency was not met at the time of writing, control 6 (value proposition restatement) was violated for all six offers, and the chain was not safe to build copy generation against.

**Verdict: CLOSE - finding was correct at the time, but the branch is now stale relative to master.**

---

## Artifact Existence

**Does the artifact exist on this ref?** YES

The artifact is `docs/qwen-tasks/REVIEW/TASK-390-glm-checkpoint-b.md` (175 lines), present at commit `d3b76e3e`. The commit only moves the task file from TODO to REVIEW and fills in the result block. No code changes.

**Does it do what the result block claims?** The result block makes seven claims (one per negative control). Each was independently verified below.

---

## Control-by-Control Verification

### Control 1: CTA Link Allowlist

**TASK-390 claim:** "PARTIALLY VERIFIED / NOT APPLICABLE TO CURRENT STATE. `src/copylint.py:633-635` has exactly one URL: `https://productive.io/get-started/`. The six current offers have NO `cta_link` field at all."

**Independent verification:** ✓ CONFIRMED

```
git show d3b76e3e:src/copylint.py | grep -n -A 5 "CTA_LINK_ALLOWLIST"
633:CTA_LINK_ALLOWLIST = frozenset({
634-    "https://productive.io/get-started/",
635-})
```

The six offers on the branch have no `cta_link` field. The `mechanisms:` block in `productive-offers.yaml` carries the link for `demo` and `free_trial`. The allowlist is correct and fail-closed.

**Disposition: VERIFIED PASS**

---

### Control 2: Approval Status

**TASK-390 claim:** "VERIFIED PASS. All six offers have `approval_status: pending`. Grep of `config/` for `approval_status:\s*approved` returns zero matches."

**Independent verification:** ✓ CONFIRMED

```
git show d3b76e3e:config/clients/productive-offers.yaml | grep "approval_status:"
    approval_status: pending  (×6 offers)
```

No offer has `approval_status: approved`. `src/offers.py:99-103` raises `NotApproved` for any non-approved offer when `require_approved=True`.

**Disposition: VERIFIED PASS**

---

### Control 3: capability_by_persona Order

**TASK-390 claim:** "VERIFIED PASS. Offer assignment is by `offer.persona` field in `_offers_for_segment` (`src/campaignstrategy.py:56-73`), NOT by `capability_by_persona` order. Reordering the list changes the primary angle (first entry) but not which offers a persona gets."

**Independent verification:** ✓ CONFIRMED

`src/campaignstrategy.py:62-77` shows `_offers_for_segment` filters offers by:
1. `approval_status == APPROVED`
2. `offer.segment` matches segment_key (or 'all')
3. `offer.persona` matches persona

The function reads `offer.persona`, not `capability_by_persona`. The ordered list in `productive.yaml:359-361` is read by `cadence.product_words` for rung 3 capability selection, not by offer assignment.

**Disposition: VERIFIED PASS**

---

### Control 4: Campaign Strategy Cache

**TASK-390 claim:** "VERIFIED PASS. Reproduced: 5 calls to `for_segment('agencies', 'champion')` with a counting model → 1 model call, 4 cache hits. Cache keyed by `(segment_key, persona)` in `_strategy_cache` (`src/campaignstrategy.py:30`)."

**Independent verification:** ✓ CONFIRMED

`src/campaignstrategy.py:145-147`:
```python
cache_key = (segment_key, persona)
if cache_key in _strategy_cache:
    return _strategy_cache[cache_key]
```

The cache is keyed by `(segment_key, persona)` and returns the cached value on hit. The module-level `_model_call_count` is incremented exactly once per call (line 127). The design ensures one model call per unique segment+persona combination.

**Disposition: VERIFIED PASS**

---

### Control 5: No Capability Deleted

**TASK-390 claim:** "VERIFIED PASS. `productive.yaml` `product.capabilities` has all six: project_management, time_tracking, budgeting, resource_planning, billing, profitability."

**Independent verification:** ✓ CONFIRMED

```
git show d3b76e3e:config/clients/productive.yaml | sed -n '334,340p'
capabilities:
    project_management: projects, tasks and delivery in one place
    time_tracking: time booked against the project and the budget it belongs to
    budgeting: what a project was quoted at and what it has burned so far
    resource_planning: who is booked on what next week, and where the next hire goes
    billing: invoices raised from the time and the budget rather than retyped
    profitability: margin per project while it is running, not after it closes
```

All six capabilities present. `src/offers.py:28-35` defines `CONFIRMED_CAPABILITIES` matching exactly these six.

**Disposition: VERIFIED PASS**

---

### Control 6: Value Proposition Restatement

**TASK-390 claim:** "VIOLATION FOUND. ALL SIX offers have `value_proposition` text that is a VERBATIM copy of the corresponding `product.capabilities` text."

**Independent verification:** ✓ VIOLATION CONFIRMED

Programmatic comparison:

```
OFFER-PM-001.value_proposition == capabilities.project_management
  'projects, tasks and delivery in one place' == 'projects, tasks and delivery in one place'

OFFER-TT-001.value_proposition == capabilities.time_tracking
  'time booked against the project and the budget it belongs to' == 'time booked against the project and the budget it belongs to'

OFFER-BU-001.value_proposition == capabilities.budgeting
  'what a project was quoted at and what it has burned so far' == 'what a project was quoted at and what it has burned so far'

OFFER-RP-001.value_proposition == capabilities.resource_planning
  'who is booked on what next week, and where the next hire goes' == 'who is booked on what next week, and where the next hire goes'

OFFER-BI-001.value_proposition == capabilities.billing
  'invoices raised from the time and the budget rather than retyped' == 'invoices raised from the time and the budget rather than retyped'

OFFER-PR-001.value_proposition == capabilities.profitability
  'margin per project while it is running, not after it closes' == 'margin per project while it is running, not after it closes'
```

All six offers restate their capability's value proposition verbatim. This creates dual truth: if a capability's wording is updated, the offer's copy becomes stale without warning.

**Disposition: VIOLATION CONFIRMED**

---

### Control 7: NotApproved Exception

**TASK-390 claim:** "VERIFIED PASS. `src/offers.py:40` defines `class NotApproved(Exception)`. `for_campaign` at line 99-103 raises it naming the offer."

**Independent verification:** ✓ CONFIRMED

```python
# src/offers.py:40
class NotApproved(Exception):
    """An offer whose approval_status is not 'approved' was requested for
    copy generation. Production does not approve its own offers."""

# src/offers.py:100-104
raise NotApproved(
    f"offer {oid} has approval_status="
    f"{offer.get('approval_status')!r}, not 'approved'. "
    f"Production does not approve its own offers."
)
```

The exception is defined, raised with the offer ID and status, and the message is clear.

**Disposition: VERIFIED PASS**

---

## Dependency Claim: TASK-367 Not on Master

**TASK-390 claim:** "TASK-367 (the real two-record offers block) is NOT on master."

**Independent verification:** ✓ CORRECT AT THE TIME, NOW STALE

Timeline:
- TASK-390 commit: `2026-09-27 00:31:08` (early morning Sept 27)
- TASK-367 offers first appeared on master: `7a4ab105` at `2026-09-27 13:05:08` (afternoon Sept 27)

When TASK-390 was written, TASK-367 had not yet landed on master. The finding was correct at the time.

However, the branch `qwen-worker-10-r9` diverged from master at `045aa69a` (before TASK-367 landed), so the branch's offers file has only 6 offers while current master has 8 (the original 6 + OFFER-A-ECONOMIC-BUYER and OFFER-B-OPERATIONS from TASK-367).

**Current state on master:** The two TASK-367 offers do NOT have the control 6 violation (their `value_proposition` fields differ from the capability text). The original 6 offers remain on master with the violation.

**Disposition: FINDING WAS CORRECT, NOW SUPERSEDED BY MASTER MOVEMENT**

---

## Merge Safety

**Would merging delete anything?**

The branch changes 205 files (+30,881 / -477 lines). One file is deleted:
- `docs/qwen-tasks/TODO/TASK-216-find-the-supported-list-to-campaign-bind.md`

However, TASK-216 was moved from TODO to DONE by commit `135a6655` (legitimate task lifecycle), not deleted. The file exists on the branch at `docs/qwen-tasks/DONE/TASK-216-find-the-supported-list-to-campaign-bind.md`.

The TASK-390 commit itself (`d3b76e3e`) only moves its own task file from TODO to REVIEW. No code changes, no deletions.

**Disposition: SAFE TO MERGE (task file movement only)**

---

## Scope Drift

**Does the branch carry junk beside the work?**

The branch carries 205 files of changes across many tasks (TASK-320, TASK-321, TASK-323, TASK-331, TASK-343, TASK-346, TASK-354, TASK-365, TASK-366, TASK-367, TASK-369, TASK-370, TASK-373, TASK-374, TASK-375, TASK-377, TASK-380, etc.). This is a large integration branch, not a single-task branch.

TASK-390's commit is clean (only moves its own file). The branch as a whole would need to be cherry-picked or rebased to integrate individual tasks.

**Disposition: BRANCH IS A MULTI-TASK INTEGRATION BRANCH; TASK-390 COMMIT IS CLEAN**

---

## Chain Safety Assessment

**TASK-390 claim:** "The chain is NOT safe to build copy generation against in its current state."

**Independent assessment:** PARTIALLY SUPERSEDED

At the time TASK-390 was written (2026-09-27 00:31), the chain was not safe because:
1. TASK-367 had not landed (now it has, as of 13:05 the same day)
2. Control 6 was violated for all six offers (still true for the original 6 on current master)

On current master (2026-09-28):
- TASK-367 has landed with two new offers that do NOT violate control 6
- The original 6 offers remain with the violation
- The two TASK-367 offers (OFFER-A-ECONOMIC-BUYER, OFFER-B-OPERATIONS) are the ones copy generation should use

The chain is safer now than when TASK-390 was written, but the original 6 offers still carry the dual-truth defect.

---

## Findings Summary

| Control | TASK-390 Claim | Independent Verification | Disposition |
|---------|----------------|--------------------------|-------------|
| 1. CTA allowlist | Partially verified / N/A | ✓ Confirmed | VERIFIED PASS |
| 2. Approval status | All pending | ✓ Confirmed | VERIFIED PASS |
| 3. capability_by_persona | Order changes angle, not offer | ✓ Confirmed | VERIFIED PASS |
| 4. Strategy cache | One call per segment+persona | ✓ Confirmed | VERIFIED PASS |
| 5. No capability deleted | All 6 present | ✓ Confirmed | VERIFIED PASS |
| 6. Value proposition | All 6 restate | ✓ Violation confirmed | VIOLATION CONFIRMED |
| 7. NotApproved exception | Defined and raised | ✓ Confirmed | VERIFIED PASS |
| Dependency: TASK-367 | Not on master | ✓ Correct at time, now stale | SUPERSEDED |

---

## Recommendation

**CLOSE**

TASK-390's findings were correct at the time it was written. All seven controls were verified independently. The task correctly identified that:
1. TASK-367 had not landed (now it has)
2. Control 6 was violated for all six offers (still true for the original 6 on master)

The branch is now stale relative to master. TASK-367 has been integrated with two new offers that do not violate control 6. The original 6 offers remain on master with the violation, but they are not the offers copy generation should use.

**No merge is needed.** TASK-390 is a finding-only task (no code changes). The finding has been superseded by master's movement. The control 6 violation for the original 6 offers is a known state that TASK-367's two-offer design addresses by introducing new offers that reference rather than restate.

**What remains:**
- The original 6 offers on master still have the control 6 violation (dual truth)
- Copy generation should use OFFER-A-ECONOMIC-BUYER and OFFER-B-OPERATIONS, not the original 6
- If the original 6 are ever used, the violation would need to be resolved

**Artifact kind:** Finding (read-only verification checkpoint)  
**Tests:** All controls verified programmatically or by config inspection  
**Files changed by TASK-390:** 1 (task file moved TODO → REVIEW)  
**Production impact:** None (read-only review)

---

## Verification Commands

All claims can be reproduced with:

```bash
# Verify control 6 (value proposition restatement)
python -c "
import yaml, subprocess
result = subprocess.run(['git', 'show', 'd3b76e3e:config/clients/productive-offers.yaml'], 
                       capture_output=True, text=True, encoding='utf-8')
offers = yaml.safe_load(result.stdout)['offers']
result2 = subprocess.run(['git', 'show', 'd3b76e3e:config/clients/productive.yaml'], 
                        capture_output=True, text=True, encoding='utf-8')
caps = yaml.safe_load(result2.stdout)['product']['capabilities']
for oid, offer in offers.items():
    cap_id = offer.get('capability')
    vp = offer.get('value_proposition', '')
    cap_text = caps.get(cap_id, '')
    if vp == cap_text:
        print(f'VIOLATION: {oid}')
"

# Verify CTA allowlist
git show d3b76e3e:src/copylint.py | grep -n -A 5 "CTA_LINK_ALLOWLIST"

# Verify NotApproved exception
git show d3b76e3e:src/offers.py | grep -n -A 10 "class NotApproved\|raise NotApproved"

# Verify strategy cache
git show d3b76e3e:src/campaignstrategy.py | grep -n "_strategy_cache\|cache_key"
```

---

**Review complete. Branch HEAD SHA reviewed: `d3b76e3e172b59d86fd9541f15f47fcbf049c857`**
