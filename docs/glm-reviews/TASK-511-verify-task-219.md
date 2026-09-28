# TASK-511 — Independent verification of TASK-403's verdict on TASK-318

**REVIEW MODEL**: Qwen-7, independent, falsification-oriented
**START_BRANCH_SHA**: f03c74fc01a40df45419742e122268d11c8395a1
**BRANCH**: origin/qwen-worker-2-r9
**SHA VERIFIED**: `git rev-parse origin/qwen-worker-2-r9` = `f03c74fc01a40df45419742e122268d11c8395a1` ✓
**WORKTREE**: `.qwen/worktrees/task511-verify` (detached HEAD at f03c74fc)
**MASTER_SHA**: ccaa48d6 (HEAD of master at review time)
**MERGE_BASE**: 26f942ac896f1c5d318b4414235b19e31874a409

---

## What TASK-403 claimed

TASK-403 reviewed TASK-318 (the Offer Engine) and returned verdict **SAFE TO MERGE**:

1. Acceptance one-liner passes: `5 gaps listed for the operator`
2. 11 tests all pass in `test_an_offer_cannot_be_invented`
3. All 6 offers have `approval_status: pending`
4. Two production consumers (`generate_campaign.py`, `campaignstrategy.py`) wired
5. FINDING-1: `secondbrain._offers()` is a stub returning `[]`, not wired to offers module
6. All four false-pass guards are falsifiable

---

## Independent reproduction

### 1. Acceptance one-liner

**Reproduced with correct Python syntax** (TASK-403's one-liner had a try/except on a single line which is a SyntaxError):

```
py -3 -c "import sys; sys.path.insert(0,'.'); from src import offers;
offers.for_campaign(503, require_approved=True)"
```

**Result**: `NotApproved: offer OFFER-PM-001 has approval_status='pending'` — the fail-closed guard works. Campaign 503's offers are all pending, so the exception fires correctly.

`offers.missing()` returns 5 gaps. **PASS** (matches TASK-403's claim).

### 2. Unit tests

```
py -3 -m unittest tests.test_an_offer_cannot_be_invented -v
```

**Result**: 10 pass, **1 FAILS**:

```
FAIL: test_approval_status_is_not_defaulted_to_approved
AssertionError: 'approved' == 'approved' : offer OFFER-A-ECONOMIC-BUYER
has approval_status='approved' - production does not approve its own offers
```

**Root cause**: The YAML now has 8 offers (6 capability + 2 composed). The composed offers `OFFER-A-ECONOMIC-BUYER` and `OFFER-B-OPERATIONS` have `approval_status: approved` (operator-approved 2026-09-27). The test asserts NO offer is approved, which was true when TASK-403 reviewed but is no longer true.

**Critical: this test also fails on master** (ccaa48d6). The branch did NOT introduce this failure. Both master and the branch have the same operator-approved composed offers. The test needs updating to accommodate operator-approved offers alongside pending ones.

### 3. Consumer wiring — VERIFIED, all three consumers connected

| Consumer | File:Line | What it does | Verified |
|----------|-----------|--------------|----------|
| `generate_campaign._check_offers()` | `src/generate_campaign.py:114` | Calls `offers_mod.load()`, raises `NotApproved` if any offer is not approved. Called at line 62 before generation. | YES |
| `generate_campaign._offer_summary()` | `src/generate_campaign.py:189` | Returns `offers_mod.load()` for plan metadata. | YES |
| `campaignstrategy._offers_for_segment()` | `src/campaignstrategy.py:69` | Calls `offers_mod.load()`, filters by approval_status, segment, persona. Called at line 152 during strategy generation. | YES |
| `secondbrain._offers()` | `src/secondbrain.py:157-174` | Calls `_offers_mod.load()` and `_offers_mod.missing()`, returns facts. Registered in dispatch table at line 216. | YES |

### 4. FINDING-1 re-evaluated: TASK-403 was WRONG

TASK-403 claimed `secondbrain._offers()` at line 157-158 "returns `[]` (stub)" and "never calls `offers.load()` or `offers.missing()`".

**This is factually incorrect at the branch HEAD.** The diff `master...HEAD -- src/secondbrain.py` shows the change clearly:

```diff
 def _offers(config, client):
-    return []
+    from . import offers as _offers_mod
+    facts = []
+    for offer_id, offer in _offers_mod.load().items():
+        ...
+    for gap in _offers_mod.missing():
+        ...
+    return facts
```

The function IS wired. It imports the offers module, iterates all offers, and lists all gaps. TASK-403's FINDING-1 is a **FALSE POSITIVE** — the wiring was done by TASK-318's own commit and is visible in the diff.

### 5. Falsifiability of each guard

| Guard | Test | Falsifiable? | Current status |
|-------|------|-------------|----------------|
| Unapproved offer blocked | `test_unapproved_offer_raises_for_campaign_503` | YES | PASS — campaign 503's offers are pending |
| No invented capability | `test_every_offer_names_a_confirmed_capability` + `test_six_capabilities_shipped` | YES | PASS for 6 capability offers; `test_six_capabilities_shipped` asserts exact set equality which the 2 composed offers bypass (they reuse existing capabilities) |
| No LLM in offers path | `test_offers_module_has_no_llm_import` | YES | PASS — AST walk rejects forbidden imports |
| approval_status not defaulted | `test_approval_status_is_not_defaulted_to_approved` | YES | **FAIL** — operator-approved composed offers break the assertion |
| missing() non-empty | `test_missing_is_not_empty` + `test_missing_includes_case_studies` | YES | PASS |

### 6. Deletion check

`git diff master...HEAD --diff-filter=D` reports **one file** would be deleted:

```
docs/qwen-tasks/TODO/TASK-372-the-suite-baseline-is-73-failures-short.md
```

This is a task file that exists in TODO/ on master but was removed on the branch. It is a queue management file, not production code. Cherry-picking TASK-318's changes would need to exclude this deletion.

### 7. Scope drift

The branch `qwen-worker-2-r9` carries **93 changed files** (+10,615 / -315 lines) vs master. TASK-318's specific changes are:

- `config/clients/productive-offers.yaml` (+245 lines: composed offers, messaging rules, evidence, mechanisms)
- `src/secondbrain.py` (+30/-7: offer wiring, missing-section removal, index text update)
- `src/offers.py` — already on master, no diff
- `tests/test_an_offer_cannot_be_invented.py` — already on master, no diff

TASK-318's delta is ~275 lines across 2 files. The remaining ~10,340 lines belong to other tasks (TASK-364, TASK-372, TASK-397, TASK-400, TASK-410, etc.). Cherry-pick is required; bulk merge would bring everything.

---

## Findings

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | `test_approval_status_is_not_defaulted_to_approved` FAILS at branch HEAD and on master. The test asserts no offer is approved, but operator-approved composed offers exist. | Medium — broken test, pre-existing on both refs | EXISTING TASK (test needs updating to distinguish "defaulted to approved" from "operator-approved") |
| 2 | TASK-403's FINDING-1 (secondbrain._offers is a stub) is a FALSE POSITIVE. The function is fully wired at the branch HEAD. | Low — TASK-403's error, not TASK-318's defect | FALSE POSITIVE |
| 3 | TASK-403 claimed "11 tests, all pass" — only 10 pass at the branch HEAD. The 11th was broken by later operator-approved offers, not by TASK-318. | Medium — incorrect claim in the verdict | SUPERSEDED (the test was green when TASK-403 ran; later commits broke it) |
| 4 | Merge would delete `docs/qwen-tasks/TODO/TASK-372-the-suite-baseline-is-73-failures-short.md` | Low — task queue file, not production code | ACCEPTED DEFERRED RISK (cherry-pick avoids this) |
| 5 | `messaging_rules.enforcement_status: DATA_ONLY_NOT_YET_ENFORCED` — the messaging rules block in the YAML is explicitly not enforced by any gate. | Low — documented intent, not a false claim | OPERATOR DECISION REQUIRED (when to build sequencegate enforcement) |

---

## Verdict

**REVISED: REWORK (minor, targeted)**

TASK-403's core verdict — that TASK-318's offer engine is real, wired, and fail-closed — is **substantively correct**. The three production consumers (`generate_campaign`, `campaignstrategy`, `secondbrain`) all drive through `offers.load()`. The fail-closed guard works: campaign 503's pending offers correctly raise `NotApproved`.

However, at the branch HEAD `f03c74fc`:

1. **One test fails** (`test_approval_status_is_not_defaulted_to_approved`). This is pre-existing on master and was not introduced by the branch, but it means the test suite is not green. The test needs to be updated to accommodate operator-approved offers — the original guard (no offer silently defaults to approved) is still valid, but the assertion needs to exclude explicitly approved offers.

2. **TASK-403's FINDING-1 was wrong** — `secondbrain._offers()` IS wired. This does not affect TASK-318's correctness (the wiring is real), but it means TASK-403's verdict carried a false finding that should be retired.

3. **The branch carries work from many tasks** (93 files). TASK-318's delta is 2 files, ~275 lines. Cherry-pick is the correct integration path.

**What needs rework**: Update `test_approval_status_is_not_defaulted_to_approved` to assert that no offer has `approval_status` defaulting silently to approved (e.g., check that approved offers carry explicit `approved_by`, `approved_on`, and `approved_at_sha` fields), rather than asserting no offer is approved at all. This is a test fix, not an implementation fix.

**RECOMMENDED CLAUDE ACTION**: Cherry-pick TASK-318's two files (`config/clients/productive-offers.yaml`, `src/secondbrain.py`). Fix the test separately. Retire TASK-403's FINDING-1 as a false positive.
