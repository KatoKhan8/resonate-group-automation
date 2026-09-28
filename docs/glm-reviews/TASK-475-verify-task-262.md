# TASK-475 — GLM Independent Verification of TASK-262

**Target task:** TASK-262 — verification roles, attempt 2: private fixtures, shared ones untouched  
**Branch:** origin/qwen-worker-10-r59  
**Branch HEAD SHA:** 1c8377bd4dcc398b0e9536ccbda3df05295b3903  
**Verified SHA:** 1c8377bd4dcc398b0e9536ccbda3df05295b3903 (confirmed via `git rev-parse`)  
**Review date:** 2026-09-28  
**Reviewer:** GLM (TASK-475)  

---

## 1. Artifact Existence

**VERIFIED.** The artifact exists on the exact ref `1c8377bd4dcc398b0e9536ccbda3df05295b3903`.

Files changed (from merge-base `e4dc021c`):
- `tests/base.py` — 5 lines added (verification role pin in `fixture_config`)
- `tests/test_e2e.py` — 6 lines changed (removed `confirm_deliverable_contract()` from setUp)
- `tests/test_enrich.py` — 8 lines changed (replaced `confirm_deliverable_contract()` with `pin_client_config(self)`)
- Task file moved from TODO to DONE

**Shared fixtures NOT edited:** `git diff master...1c8377bd -- tests/fixtures/phase2.jsonl tests/fixtures/phase5.jsonl tests/fixtures/phase6.jsonl tests/fixtures/phase7.jsonl` returns empty. ✓

**No source/config/scripts changes:** `git diff master...1c8377bd --stat -- src/ config/ scripts/` returns empty. ✓

---

## 2. Existence Is Function — Consumption Chain Verified

The verification pin in `fixture_config` is consumed by every test that calls `pin_client_config`:

```
fixture_config() → pins verification roles to (contactout, deliverable, reoon)
    ↑
pin_client_config() → calls fixture_config(), patches clients.load
    ↑
40+ test methods across 15+ modules call pin_client_config()
```

**Callers verified:**
- `tests/test_e2e.py:137` — `pin_client_config(self)` in EndToEnd.setUp
- `tests/test_enrich.py:32` — `pin_client_config(self)` in EnrichTest.setUp
- `tests/test_approve.py:49` — `pin_client_config(self)`
- `tests/test_push.py:24` — `pin_client_config(self)`
- `tests/test_preproduction.py:129` — `pin_client_config(self)`
- `tests/test_double_verification.py:309,442,514` — three call sites
- `tests/test_generate.py:73,641,701` — three call sites
- Plus 8 more modules (test_company_evidence_cache, test_ladder_propagation, test_linkedin_note, etc.)

**The chain is real.** `verification.policy_for(config)` reads `config.get("verification")` at `src/verification.py:102`. When `clients.load("productive")` is patched to return the pinned config, every downstream verification decision uses (contactout, deliverable, reoon) regardless of what `productive.yaml` says.

**Live config confirmed:** `config/clients/productive.yaml` has `primary: deliverable, secondary: reoon, catch_all: reoon`. The fixtures were built for (contactout, deliverable, reoon). Without the pin, records with only contactout evidence are correctly held — which is the defect TASK-262 fixes.

---

## 3. Falsification — Mutation Test Performed

**Method:** Removed the verification pin from `fixture_config` (5 lines deleted), then ran `test_enrich.TestTheAcceptanceTest.test_the_verified_record_still_ships`.

**Result:**
```
FAIL: test_the_verified_record_still_ships
AssertionError: 'held' != 'verified'
```

**The test fails for the intended reason.** Without the pin, `clients.load("productive")` returns the live config with `primary: deliverable`, the fixture has no deliverable evidence, `verification.policy_for` computes "no verification evidence", and the record is held.

**A different guard did not fire first.** The failure is specifically `'held' != 'verified'`, not a cadence error, not an approval error, not a spend cap error. The verification path is the one that broke.

**Separation confirmed:** `test_productive_verification_roles.py` (7/7) passes BOTH with and without the pin, because it calls `clients.load` directly and tests the LIVE roles. The pin only affects tests that go through `fixture_config`/`pin_client_config`.

---

## 4. Test Falsifiability Assessment

**Are the tests falsifiable? YES.**

The tests assert on record state (`verified`, `approved`, `held`, `sendable`) after running the full pipeline through `enrich.run()`, `approve.pending()`, and `push.run()`. These are behavioral assertions, not source text checks.

**What could make these pass while the implementation is wrong?**
- If `fixture_config` pinned the wrong roles, the tests would fail (verified above).
- If `pin_client_config` did not actually patch `clients.load`, the tests would fail because `approve.pending()` and `push.run()` load the config themselves.
- If the verification module ignored the config's roles, the tests would fail because the waterfall order and acceptance logic depend on them.

**Not accepted as proof:** None of the forbidden patterns (hasattr, source text assertions, token checks) are present. The tests exercise the real entry points.

---

## 5. Would Merging Delete Anything?

**NO.** The only "deleted" file is `docs/qwen-tasks/TODO/TASK-262-*.md`, which is the task file moving to DONE. No source files, no config files, no test fixtures would be deleted.

**Blob comparison:** The branch modifies 3 test files and adds 1 task file in DONE. No other files are touched.

---

## 6. Scope Drift

**NONE.** The branch has exactly 3 commits:
1. `fbf04944` — Task claimed and moved to RUNNING
2. `9848eaf2` — The actual code changes (5 lines in base.py, cleanup in 2 test files)
3. `1c8377bd` — Result block, moved to DONE

No junk, no unrelated changes, no scratch files. The diff is exactly what the result block claims.

---

## 7. Merge Conflict with Current Master

**CONFLICT DETECTED in `tests/test_e2e.py`.**

Master has moved since the branch diverged (merge-base `e4dc021c`, master HEAD `6ad72a43`). Master added `pin_approved_offer(self)` and campaign prompt handling to `test_e2e.py`, and **kept** `self.confirm_deliverable_contract()` in the setUp.

The branch removes `confirm_deliverable_contract()`. The conflict region:

```python
# Master has:
pin_client_config(self)
pin_approved_offer(self)  # ← added on master
self.confirm_deliverable_contract()  # ← branch removes this

# Branch wants:
pin_client_config(self)
# (confirm_deliverable_contract removed)
```

**Resolution:** Keep `pin_approved_offer(self)` from master, remove `confirm_deliverable_contract()` as the branch intends. With the verification pin, contactout is primary and deliverable's contract is not needed in setUp.

**`tests/base.py` has NO conflict** — master adds new functions after line 102, branch adds the verification pin at lines 68-75. Different areas, clean merge.

---

## 8. Test Results on Branch HEAD

| Test File | Result | Claimed | Verified |
|-----------|--------|---------|----------|
| test_productive_verification_roles.py | 7/7 pass | ✓ | ✓ |
| test_enrich.py | 49/49 pass | ✓ | ✓ |
| test_e2e.TestTheProviderWaterfall | 14/14 pass | ✓ | ✓ |
| test_e2e.TestEnrichmentOutcomes | 9/9 pass | ✓ | ✓ (note: result block says 5/5, but 9 tests exist) |
| test_e2e.TestGenerationAndLint | 5/5 pass | ✓ | ✓ |
| test_e2e.TestTheFinalShape | 8/9 pass | ✓ | ✓ (1 pre-existing failure: skyline held vs approved) |
| test_e2e.TestPushPreparationAndIdempotency | 4/4 pass | ✓ | ✓ |
| test_preproduction.py | 28/28 pass | ✓ | ✓ |
| test_approve.py | 43/43 pass | ✓ | ✓ |
| test_push.py | 37/37 pass | ✓ | ✓ |
| test_cadence + test_double_verification + test_events + test_personas + test_fixture_hygiene | 193/193 pass | ✓ | ✓ |

**Pre-existing failure documented:** `test_the_state_of_every_record` expects `skyline: approved` but gets `skyline: held`. The result block explicitly states this is unrelated to verification roles. **Verified: this failure exists on master too.**

---

## Findings

### Finding 1: Artifact exists and does what the result block claims
**Disposition: VERIFIED**  
The 5-line pin in `fixture_config` correctly addresses the defect. Shared fixtures are untouched. The consumption chain is real and traced.

### Finding 2: Tests are falsifiable and the mutation trips the live path
**Disposition: VERIFIED**  
Removing the pin causes the intended test to fail with the intended error (`'held' != 'verified'`). A different guard did not fire first.

### Finding 3: Merge conflict with current master
**Disposition: REQUIRES MANUAL RESOLUTION**  
`tests/test_e2e.py` has a conflict where master added `pin_approved_offer()` alongside `confirm_deliverable_contract()`, and the branch removes `confirm_deliverable_contract()`. Resolution is straightforward: keep `pin_approved_offer()`, remove `confirm_deliverable_contract()`.

### Finding 4: Result block has a minor count discrepancy
**Disposition: COSMETIC**  
The result block says "TestEnrichmentOutcomes: 5/5 pass" but the class has 9 tests. All 9 pass. This is likely because the result block was written when the class had fewer tests, and master has since added more. Not a defect in the work.

### Finding 5: No scope drift, no junk, no source changes
**Disposition: VERIFIED**  
The branch is clean. Only 3 test files and the task file are modified. No source code, no config, no scripts, no shared fixtures.

---

## Recommendation

**MERGE after resolving the conflict in `tests/test_e2e.py`.**

The work is correct, minimal, and well-scoped. The verification pin follows the established pattern (cadence pin was already there). The consumption chain is real. The mutation test proves the wiring.

**Cherry-pick is NOT needed** — the conflict is local to one setUp method and the resolution is obvious. A merge with manual conflict resolution is cleaner than a cherry-pick.

**Post-merge:** Regenerate the suite baseline JSON to record the new failure count (82 → 50, delta -32).

---

## Disposition Summary

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Artifact exists and does what claimed | VERIFIED |
| 2 | Tests are falsifiable, mutation trips live path | VERIFIED |
| 3 | Merge conflict with current master | REQUIRES MANUAL RESOLUTION |
| 4 | Minor count discrepancy in result block | COSMETIC |
| 5 | No scope drift, no junk, no source changes | VERIFIED |

**Final verdict: MERGE** (after resolving the `test_e2e.py` conflict)

---

*Review performed on isolated worktree at SHA 1c8377bd4dcc398b0e9536ccbda3df05295b3903. No production state was modified. No provider calls were made.*
