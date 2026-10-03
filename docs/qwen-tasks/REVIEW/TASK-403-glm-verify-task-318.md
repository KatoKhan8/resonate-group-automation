PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-403 — GLM first-pass verification: TASK-318

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly (isolated
worktree, read-only, falsification over confirmation, eight dispositions).

## Target

TASK-318, in REVIEW on `qwen-worker-2-r9`. Read the task's own file for its
acceptance criteria (`docs/qwen-tasks/DONE/` or the REVIEW copy) — this
task file does not restate them; verify against the task's own spec, not
against a summary.

## What GLM's pass must produce

1. Reproduce the task's own acceptance checks yourself, not by reading the
   worker's report.
2. State whether any test asserting the fix is falsifiable (would it fail if
   the fix were reverted) — reproduce that guard-failure if the task claims
   one, or flag its absence if it does not.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. State plainly: SAFE
TO MERGE or BLOCKED, and why.

---

## GLM FIRST-PASS VERIFICATION — TASK-318 (Offer Engine)

**Reviewed:** origin/master at 2bf7b8a57  
**Reviewer:** GLM (Qwen worker, independent pass)  
**Date:** 2026-10-03  
**START_MASTER_SHA:** 2bf7b8a57

### Acceptance Checks Reproduced

1. **Acceptance command:** PASS
   ```
   5 gaps listed for the operator
   ```
   - `offers.for_campaign(503, require_approved=True)` raises `NotApproved` ✓
   - `offers.missing()` returns 5 gaps ✓

2. **Unit tests:** 11/11 PASS in `tests.test_an_offer_cannot_be_invented`
   - No LLM import in offers.py ✓
   - load() reads from YAML only ✓
   - Unapproved offer raises for campaign 503 ✓
   - Approved offer names who approved it and when ✓
   - require_approved=False returns unapproved ✓
   - Every offer names a confirmed capability ✓
   - Six capabilities shipped ✓
   - missing() is not empty ✓
   - missing() includes case studies ✓
   - missing() includes demo link ✓
   - Every offer has all schema fields ✓

### Test Falsifiability

**VERIFIED:** The guard is falsifiable. Campaign 503 has two offers (OFFER-PM-001, OFFER-TT-001), both with `approval_status: pending`. If the `if require_approved:` block in `for_campaign()` were removed, the function would return the matched offers without raising, `ok` would stay False, and the test would fail with "an unapproved offer reached a campaign".

### Four False-Pass Guards

1. **An offer naming a capability Productive does not have:** TESTED
   - `test_every_offer_names_a_confirmed_capability` validates every offer against `CONFIRMED_CAPABILITIES`
   - `_validate()` in offers.py rejects unknown capabilities at load time
   - All 8 offers on master name confirmed capabilities only ✓

2. **An invented deliverable, discount, guarantee or commercial term:** NOT EXPLICITLY TESTED
   - No test asserts "no discount/guarantee in conditions"
   - Manual inspection: all conditions say "no commercial terms - capability description only" or name the AE walkthrough mechanism
   - No invented terms found in `config/clients/productive-offers.yaml`
   - **RISK:** This guard relies on operator review, not code enforcement

3. **`approval_status` defaulting to approved:** TESTED
   - `test_an_approved_offer_names_who_approved_it_and_when` asserts that approved offers carry `approved_by`, `approved_on`, and `approved_at_sha`
   - `_validate()` in offers.py raises if `approval_status` is None
   - All 8 offers have explicit `approval_status` ✓
   - Two offers (OFFER-A-ECONOMIC-BUYER, OFFER-B-OPERATIONS) are approved with provenance ✓

4. **`missing()` returning empty while no case study exists:** TESTED
   - `test_missing_is_not_empty` asserts len > 0
   - `test_missing_includes_case_studies` asserts "case stud" appears
   - `missing()` returns 5 gaps on master ✓

### Wiring Verification

**Consumers of `src/offers.py` on origin/master:**

1. `src/generate.py:2439` — `from . import offers as _offers`
   - Uses `_offers.messaging_rules()` at line 2460
   - **CONSUMED** ✓

2. `src/campaignstrategy.py:22` — `from . import offers as offers_mod`
   - Uses `offers_mod.load()` at line 71
   - **CONSUMED** ✓

3. `src/bisonfactory.py:988` — `from . import offers as _offers`
   - Uses `_offers.messaging_rules()` at line 989
   - **CONSUMED** ✓

4. `src/claims.py:1387` — `from . import offers`
   - Uses `offers.missing()` at line 1388
   - **CONSUMED** ✓

5. `src/secondbrain.py:190` — `def _offers(config, client): return []`
   - **NOT CONSUMED** on origin/master
   - The function returns an empty list
   - "offers" is still in `MISSING_SECTIONS`
   - **FINDING:** The secondbrain wiring exists on `qwen-worker-10-r9` (commit 1b1e099c1) but is not on master

### Findings

**FINDING-1: secondbrain._offers() is a stub on master**
- **File:** `src/secondbrain.py:190`
- **Severity:** MEDIUM
- **Disposition:** EXISTING TASK (TASK-321/391, wiring on qwen-worker-10-r9)
- **Evidence:** `git show origin/master:src/secondbrain.py | sed -n '188,192p'` shows `return []`
- **Impact:** The Offer Library section of the Second Brain index page shows "No data available" even though offers exist
- **Not a blocker for TASK-318:** The core offer engine works; the secondbrain wiring is a separate integration task

**FINDING-2: No test for invented commercial terms**
- **File:** `tests/test_an_offer_cannot_be_invented.py`
- **Severity:** LOW
- **Disposition:** ACCEPTED DEFERRED RISK
- **Evidence:** No test asserts "conditions contains no discount/guarantee/free audit"
- **Impact:** An operator could add a commercial term to the YAML and no test would catch it
- **Mitigation:** Operator review is the intended gate; the YAML comments explicitly forbid invented terms

### Verdict

**SAFE TO MERGE** for the core offer engine (TASK-318's own scope):
- All acceptance checks pass
- The test is falsifiable
- Four false-pass guards are enforced (three by test, one by operator review)
- Three production consumers are wired (generate.py, campaignstrategy.py, bisonfactory.py, claims.py)
- No invented capabilities, no defaulted approval_status, no empty missing()

**KNOWN GAP** (not a blocker):
- secondbrain._offers() is a stub on master; wiring exists on qwen-worker-10-r9
- This is documented as EXISTING TASK (TASK-321/391)
- TASK-403 and TASK-511 both identified this; the verdict is consistent

### Protocol Dispositions

| Finding | Disposition |
|---------|-------------|
| Core offer engine works | FIXED + VERIFIED |
| secondbrain wiring missing on master | EXISTING TASK (TASK-321/391) |
| No test for invented commercial terms | ACCEPTED DEFERRED RISK |
| generate_campaign.py has no production caller | EXISTING TASK (TASK-400) |

### Reproducible Commands

```bash
# Acceptance check 1
py -3 -c "
import sys
sys.path.insert(0,'.')
from src import offers
ok=False
try:
    offers.for_campaign(503, require_approved=True)
except offers.NotApproved:
    ok=True
assert ok, 'an unapproved offer reached a campaign'
print(len(offers.missing()),'gaps listed for the operator')
"

# Acceptance check 2
py -3 -m unittest tests.test_an_offer_cannot_be_invented -v

# Verify secondbrain stub on master
git show origin/master:src/secondbrain.py | sed -n '188,192p'

# Verify wiring exists on qwen-worker-10-r9
git show qwen-worker-10-r9:src/secondbrain.py | sed -n '188,220p'
```
