# GLM Independent Verification: TASK-358

**Review target**: TASK-358 - CheapVerifier exists on a branch and is not in the waterfall  
**Branch**: origin/qwen-worker-3-r9-task285  
**Branch HEAD SHA**: c8a62f4109f47eb5338f1ef334d68f44dcb989ef  
**Review worktree**: C:\Users\Zvonimir\Desktop\resonate-qwen-5\.qwen\worktrees\glm-497 (detached at c8a62f410)  
**Verified by**: GLM independent review, 2026-10-03  

---

## Verdict: REWORK

**Reason**: The artifact exists and is correctly registered, but has **zero production callers**. This is the exact defect CLAUDE.md and QWEN.md warn against: "Existence is not function... trace the chain and prove every link is consumed. Zero production callers means DISCONNECTED, which is a rework and not a merge."

The task's own result block admits this: "CheapVerifier is registered but NOT wired into any caller in src/. The module exists, the waterfall knows it, but no production code path calls verify_single() through the waterfall. This is the same state as the other verifiers before they were wired - the registration is necessary but not sufficient."

**Necessary but not sufficient is not done.** A provider that cannot be reached from production is a disconnected component, and merging it would add 1,141 lines of code that nothing consumes.

---

## Findings

### 1. Artifact exists and imports correctly ✓ VERIFIED

**File**: `src/providers/cheapverifier.py` (1,141 lines, 47,161 bytes)  
**Import test**:
```
python -c "from src.providers import cheapverifier as cv; print([x for x in dir(cv) if not x.startswith('_')][:12])"
```
**Result**: `['BASE_DEFAULT', 'BASE_VAR', 'BULK_POLL_ATTEMPTS', 'BULK_POLL_INTERVAL', 'BulkNotSettled', 'CALL_BULK', 'CALL_SINGLE', 'CATCH_ALL', 'CHARGEABLE_OUTCOMES', 'HEADER_NAME', 'HttpTransportError', 'INVALID']`

The module loads without error and exposes the expected API surface.

### 2. Waterfall registration is correct ✓ VERIFIED

**File**: `src/waterfall.py` lines 100, 242-267, 328  
**Changes**:
- Line 100: `CHEAPVERIFIER = "cheapverifier"` constant added
- Lines 242-267: CheapVerifier inserted SECOND in `EMAIL_VERIFICATION["providers"]` tuple, after ContactOut, before Deliverable
- Line 328: `COST_UNITS[CHEAPVERIFIER]` entry added

**Runtime verification**:
```
python -c "from src import waterfall as W; d=W.describe(); provs=[p['provider'] for p in d[W.EMAIL_VERIFICATION]['providers']]; print('email_verification order:',provs)"
```
**Result**: `email_verification order: ['contactout', 'cheapverifier', 'deliverable', 'reoon']`

ContactOut is first (product policy preserved ✓). CheapVerifier is second (registration correct ✓).

### 3. Enrich COSTS and CALL_STAGE entries are correct ✓ VERIFIED

**File**: `src/enrich.py` lines 48, 93  
**Changes**:
- Line 48: `COSTS["cheapverifier-verify"] = 1` (one credit per call)
- Line 93: `CALL_STAGE["cheapverifier-verify"] = "email_verification"` (correct stage routing)

These are the two lines the result block says were missing from the original cherry-pick and were added in commit 5f6d83d7. They are present and correct.

### 4. Tests pass ✓ VERIFIED (with minor discrepancy)

**File**: `tests/test_cheapverifier_is_part_of_the_waterfall.py` (95 lines)  
**Test count**: 10 tests (result block claims 12, but file contains 10)  
**Test run**:
```
python -m unittest tests.test_cheapverifier_is_part_of_the_waterfall -v
```
**Result**: `Ran 10 tests in 0.001s OK`

**What the tests prove**:
- CheapVerifier is in the email_verification providers list
- `describe()` includes CheapVerifier
- ContactOut is still before CheapVerifier (product policy)
- ContactOut is first in email_verification
- CheapVerifier has a cost_unit entry
- CheapVerifier step is not a fallback (is_fallback=False)
- `record_step` does not raise WaterfallViolation for CheapVerifier
- `record_step` writes a cost_unit
- `spend()` sees the CheapVerifier row
- `may_fall_back` accepts CheapVerifier as primary

**What the tests do NOT prove**: That any production code path reaches CheapVerifier. The tests verify registration, order, and ledger mechanics, but they do not verify that `verify_single()` or `stored_lookup()` is called from anywhere in src/.

### 5. ZERO production callers ✗ DISCONNECTED

**Search**: `grep -rn "from src.providers.cheapverifier|from src.providers import cheapverifier|import cheapverifier|cheapverifier\.verify|cheapverifier\.stored_lookup|cheapverifier\.verify_single" src/`  
**Result**: No matches (except within cheapverifier.py itself)

**Comparison with other verifiers**: ContactOut, Deliverable, and Reoon are called from:
- `src/validate.py` (lines 290, 295-303, 400-435, 510-512)
- `src/enrich.py` (lines 960, 990, 1020, 1450)
- `src/generate.py` (line 1733)
- `src/check.py` (lines 33, 36-37)
- `src/verification.py` (lines 167-173, 620)

CheapVerifier is called from **nowhere** in src/ except its own module definition.

**This is the defect.** The module exists, the waterfall knows it, enrich has cost/stage entries, but no production code path reaches it. Merging this would add 1,141 lines of code that nothing consumes.

### 6. Scope drift: branch carries multiple other tasks ⚠ POLLUTION

**Commits on branch not in master**: 21 commits  
**Other tasks on this branch**:
- TASK-267: LLM tiebreaker for FLAGGED domains (script + 23 tests)
- TASK-285: Collision walk over 200 domains (script + 15 tests)
- TASK-387: Provider event write-back (tests)
- TASK-412: Suppression list audit (docs + tests)
- TASK-426: Bison staging qualification pass (src/bisonfactory.py + tests)
- TASK-432: GLM verdict for TASK-226 (docs)
- TASK-410: GLM verification of TASK-400 (docs)

**Files changed beyond TASK-358**:
- `src/bisonfactory.py` (TASK-426: qualification pass-through)
- `scripts/claim_task.py` (TASK-267/285 changes)
- `scripts/collision_walk_report.py` (TASK-285: new script)
- `scripts/stage_s3_llm_tiebreaker.py` (TASK-267: new script)
- `tests/test_a_refused_domain_is_never_clear.py` (TASK-285: 257 lines)
- `tests/test_claim_task.py` (TASK-267: 52 lines changed)
- `tests/test_claim_task_readiness_is_not_inferred.py` (TASK-267: 412 lines)
- `tests/test_llm_tiebreaker.py` (TASK-267: 436 lines)
- `tests/test_staging_a_campaign_twice_builds_one.py` (TASK-426: 1 line)
- `tests/test_staging_refuses_colliding_contacts.py` (TASK-426: 1 line)
- `tests/test_task387_provider_event_writeback.py` (TASK-387: 216 lines)
- Multiple docs/ files (GLM reviews, task files, collision walk report)

**Cherry-pick required**: To merge TASK-358 cleanly, only these files should be taken:
- `src/providers/cheapverifier.py`
- `src/waterfall.py` (only the CheapVerifier registration)
- `src/enrich.py` (only the two lines: COSTS and CALL_STAGE)
- `tests/test_cheapverifier_is_part_of_the_waterfall.py`
- `tests/cassettes/cheapverifier/*` (9 fixture files)

Everything else on this branch belongs to other tasks and must not be merged as part of TASK-358.

### 7. Merging would not delete production files ✓ SAFE

**Deleted files**: Only task files moved from TODO/ to REVIEW/ (expected lifecycle)
- `docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md`
- `docs/qwen-tasks/TODO/TASK-410-glm-verify-task-400-critical-path.md`
- `docs/qwen-tasks/TODO/TASK-412-suppression-list-audit.md`

No production code, tests, or configuration deleted.

---

## Falsification attempts

### Claim: "The WaterfallViolation is gone"
**Test**: Call `waterfall.record_step(rec, EMAIL_VERIFICATION, CHEAPVERIFIER, "cheapverifier-verify", result="valid")`  
**Result**: No exception raised ✓  
**Verdict**: Claim verified.

### Claim: "ContactOut is still first"
**Test**: `waterfall.describe()[EMAIL_VERIFICATION]["providers"][0]["provider"]`  
**Result**: `"contactout"` ✓  
**Verdict**: Claim verified.

### Claim: "A fixture call records a waterfall step without raising, and writes a ledger row through enrich's spend()"
**Test**: `test_record_step_does_not_raise_for_cheapverifier` and `test_spend_sees_the_cheapverifier_row`  
**Result**: Both pass ✓  
**Verdict**: Claim verified, but this only proves the ledger works IF something calls it. It does not prove anything DOES call it.

### Claim: "The module imports and its entry point is callable"
**Test**: `from src.providers import cheapverifier as cv; print([x for x in dir(cv) if not x.startswith('_')][:12])`  
**Result**: Module loads, entry points visible ✓  
**Verdict**: Claim verified.

### Implicit claim: "This is ready to merge"
**Test**: `grep -rn "cheapverifier\.verify\|cheapverifier\.stored_lookup" src/`  
**Result**: Zero matches outside cheapverifier.py itself ✗  
**Verdict**: Claim falsified. The module is disconnected.

---

## What is owed

TASK-358 completed the **registration** half correctly:
1. ✓ Cherry-picked cheapverifier.py by path
2. ✓ Registered it in the waterfall (second, after ContactOut)
3. ✓ Added COSTS and CALL_STAGE entries to enrich.py
4. ✓ Wrote 10 tests proving registration and ledger mechanics

But it did NOT complete the **wiring** half:
1. ✗ No production caller in src/ reaches cheapverifier.verify_single() or cheapverifier.stored_lookup()
2. ✗ No code path in validate.py, enrich.py, generate.py, or verification.py calls CheapVerifier
3. ✗ The module is unreachable from the production generation entrypoint

**The result block admits this**: "CheapVerifier is registered but NOT wired into any caller in src/. The module exists, the waterfall knows it, but no production code path calls verify_single() through the waterfall. This is the same state as the other verifiers before they were wired - the registration is necessary but not sufficient."

**Necessary but not sufficient is not done.** The other verifiers (ContactOut, Deliverable, Reoon) are called from validate.py, enrich.py, generate.py, check.py, and verification.py. CheapVerifier is called from nowhere.

**What must be added**:
1. A call site in `src/validate.py` or `src/enrich.py` that routes to `cheapverifier.verify_single()` when the workspace config names CheapVerifier as primary
2. Tests that prove the call site is reached from the production entrypoint (not just that the module exists)
3. A mutation test: delete the call site, confirm the intended test fails for the intended reason

Until that wiring exists, CheapVerifier is a disconnected component, and merging it would add 1,141 lines of code that nothing consumes.

---

## Disposition

**MERGE**: No  
**REWORK**: Yes  
**CLOSE**: No (the registration work is correct and worth keeping, but the wiring is missing)

**Recommended action**: 
1. Cherry-pick ONLY the TASK-358 files (cheapverifier.py, waterfall.py registration, enrich.py COSTS/CALL_STAGE, test file, cassettes) - do NOT merge the entire branch
2. Create a follow-up task to wire CheapVerifier into the production call path (validate.py or enrich.py)
3. The follow-up task must prove the wiring with a test that fails when the call site is deleted

**Scope**: The branch carries 21 commits from 7 other tasks (TASK-267, TASK-285, TASK-387, TASK-412, TASK-426, TASK-432, TASK-410). Merging the entire branch would introduce unrelated changes. Cherry-pick by path, as TASK-358's own instructions say.

**Risk**: Low. The registration is correct and does not break anything. But merging a disconnected component sets a bad precedent and adds dead code.

---

## Evidence

**Worktree**: C:\Users\Zvonimir\Desktop\resonate-qwen-5\.qwen\worktrees\glm-497  
**HEAD SHA**: c8a62f4109f47eb5338f1ef334d68f44dcb989ef  
**Test run**: `python -m unittest tests.test_cheapverifier_is_part_of_the_waterfall -v` → 10 tests, all green  
**Caller search**: `grep -rn "cheapverifier\.verify\|cheapverifier\.stored_lookup" src/` → zero matches outside cheapverifier.py  
**Waterfall order**: `['contactout', 'cheapverifier', 'deliverable', 'reoon']`  
**Diff vs master**: 39 files changed, 7,167 insertions, 223 deletions (but only 5 files belong to TASK-358)

---

**Verdict written**: 2026-10-03  
**Reviewer**: GLM independent review (TASK-497)  
**Status**: REWORK - registration correct, wiring missing
