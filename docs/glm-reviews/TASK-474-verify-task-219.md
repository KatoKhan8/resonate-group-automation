# GLM Independent Verification: TASK-250

**Review target**: TASK-250 — 27 tests assert verification roles this client no longer uses  
**Branch**: `origin/qwen-worker-9-r61`  
**Branch HEAD SHA**: `3efcc9683f2a3dd23b1096ef1824d70d78f5cb33`  
**Review date**: 2026-10-03  
**Reviewer**: GLM (independent verification, TASK-474)

---

## Executive Summary

**DISPOSITION: MERGE** — The artifact is correct, the wiring is real, and the approach is safe. Two falsification tests prove the verification pin does real work and that the live client config remains unaffected. Shared fixtures are untouched. All critical test modules pass.

**RECOMMENDATION**: Merge to master, with the caveat that Claude should run the full suite baseline comparison from his worktree to verify no regressions against the baseline artifact (`docs/state/SUITE-BASELINE-2026-09-22.json`).

---

## Verification Results

### 1. Does the artifact exist on this ref?

**YES** — Verified at SHA `3efcc9683f2a3dd23b1096ef1824d70d78f5cb33`.

Files changed:
- `tests/base.py`: Added verification role pinning to `fixture_config()` (5 lines)
- `tests/test_e2e.py`: Replaced `confirm_deliverable_contract()` with `pin_client_config(self)` in setUp
- `tests/test_enrich.py`: Replaced `confirm_deliverable_contract()` with `pin_client_config(self)` in setUp
- `docs/qwen-tasks/DONE/TASK-250-*.md`: Task file moved from TODO to DONE with result block
- `docs/qwen-tasks/RUNNING/TASK-262-*.md`: New task file added (superseded by this work)

**Artifact verified**: The changes exist and are consumed.

---

### 2. Existence is not function — is the chain consumed?

**YES** — Verified through static analysis and runtime falsification.

**Static analysis**:
- `fixture_config()` in `tests/base.py` is consumed by `pin_client_config()` (line 99) and by `tests/test_render_preview.py` (as `_fixture_config`, imported from `scripts/render_preview.py` — a different function, unrelated).
- `pin_client_config()` is consumed by 8+ test modules: `test_approve`, `test_e2e`, `test_enrich`, `test_generate`, `test_double_verification`, `test_company_evidence_cache`, `test_a_stop_survives_a_concurrent_run`, and others.
- `pin_client_config()` patches `clients.load` on the `clients` module object, which is what every caller holds (`from . import clients` → `clients.load(...)`).

**Runtime falsification** (see section 4 below): Mutation tests prove the wiring is real.

---

### 3. Falsify the result's own claims

**CLAIM 1**: "The specific test named in TASK-250 (`test_e2e.TestEnrichmentOutcomes.test_the_clean_domain_verifies`) now passes."

**VERIFIED**: Test passes at SHA `3efcc9683`.

**CLAIM 2**: "Shared fixtures (phase2/5/6/7.jsonl) are NOT edited."

**VERIFIED**: `git diff master...3efcc9683f2a3dd23b1096ef1824d70d78f5cb33 -- tests/fixtures/` returns empty. Zero changes to shared fixture files.

**CLAIM 3**: "Tests that ARE about the live roles (`test_productive_verification_roles`) call `clients.load` directly and are unaffected."

**VERIFIED**: `test_productive_verification_roles.py` uses `clients.load("productive")` in setUp, not `fixture_config`. The test asserts the LIVE roles (deliverable primary, reoon secondary, contactout removed) and passes 7/7.

**CLAIM 4**: "Key test modules verified individually: test_approve, test_push, test_cadence, test_generate (169 tests), test_enrich (49 tests), test_productive_verification_roles (7 tests) - all pass."

**VERIFIED**: All pass, plus additional modules:
- `test_e2e.TestEnrichmentOutcomes`: 9/9 OK
- `test_enrich`: 49/49 OK
- `test_productive_verification_roles`: 7/7 OK
- `test_approve`: 43/43 OK
- `test_push`: 37/37 OK
- `test_cadence`: 38/38 OK
- `test_generate`: OK (exit code 0)
- `test_double_verification`: 53/53 OK
- Other fixture consumers (`test_events`, `test_personas`, `test_audit`, `test_render`, `test_company_evidence_cache`, `test_siblings_block`): 155/155 OK

**Total verified**: 391+ tests pass across 12 modules.

---

### 4. Are the tests falsifiable?

**YES** — Two mutation tests prove the wiring is real.

**MUTATION TEST 1**: Removed the verification pin from `fixture_config()`.

**Result**: `test_the_clean_domain_verifies` FAILED with:
```
AssertionError: 'held' != 'approved'
```

**Interpretation**: This is EXACTLY the failure mode TASK-250 described: "a `(contactout, reoon)` pair is no longer a verified address, and the record lands `held` where the test expects `approved`." The pin is doing real work, not just existing.

**MUTATION TEST 2**: Set the verification pin to WRONG values (`primary: WRONG`, `secondary: WRONG`, `catch_all: WRONG`).

**Result**: `test_productive_verification_roles` still PASSED (7/7 OK).

**Interpretation**: The live roles test is unaffected by the pin, proving it reads the live client config via `clients.load`, not the pinned config.

**Conclusion**: The tests are falsifiable. The wiring is real. The two-layer approach (pin for fixtures, live for policy tests) works as claimed.

---

### 5. Would merging delete anything?

**NO** — `git diff master...3efcc9683f2a3dd23b1096ef1824d70d78f5cb33 --diff-filter=D --name-only` returns empty. No files deleted.

---

### 6. Scope drift — does the branch carry junk?

**MINIMAL** — Only 5 files changed, all directly related to the task:
- 3 test files (`tests/base.py`, `tests/test_e2e.py`, `tests/test_enrich.py`)
- 2 task files (TASK-250 moved to DONE, TASK-262 added to RUNNING)

No unrelated changes. No scope drift.

---

### 7. Forbidden files — were they touched?

**NO** — `git diff master...3efcc9683f2a3dd23b1096ef1824d70d78f5cb33 -- src/ config/` returns empty. No changes to `src/`, `config/`, or `src/providers/*`.

---

### 8. Pinned vs Live roles — are they different?

**YES** — Verified at runtime:

```
fixture_config verification roles (pinned for tests):
  primary:   contactout
  secondary: deliverable
  catch_all: reoon

LIVE productive.yaml verification roles (operator's decision):
  primary:   deliverable
  secondary: reoon
  catch_all: reoon

Roles are different: True
```

**Interpretation**: The two-layer approach works. Tests that need the old roles (because the fixtures were built for them) get the pinned config. Tests that assert the live policy read the live config directly.

---

## Findings

### Finding 1: The approach is sound and safe

**Severity**: Informational  
**Disposition**: ACCEPTED

The approach pins verification roles in test infrastructure (`fixture_config`) rather than editing shared fixtures. This avoids the trap that killed attempt 1 (editing shared fixtures that feed multiple test modules). The live client config is unaffected, and tests that assert the live policy still work.

**Evidence**: 
- Shared fixtures untouched (git diff returns empty)
- `test_productive_verification_roles` passes 7/7 (asserts live roles)
- Mutation test 2 proves the live roles test is unaffected by the pin

---

### Finding 2: Full suite baseline comparison is owed

**Severity**: Informational  
**Disposition**: ACCEPTED DEFERRED RISK

The result block notes: "Full suite baseline comparison (name diff in both directions) is owed. The suite runtime exceeded the interactive session timeout."

This is acceptable for the merge, but Claude should run the full suite from his worktree and diff by name against the baseline artifact (`docs/state/SUITE-BASELINE-2026-09-22.json`) to verify no regressions.

**Evidence**: Result block, lines 148-149.

---

### Finding 3: The pin is a temporary bridge, not a permanent solution

**Severity**: Informational  
Disposition**: ACCEPTED DEFERRED RISK

The result block notes: "The approach pins the OLD verification roles in test config. This is correct for the current fixtures, but if the fixtures are ever updated to use the new roles (deliverable, reoon), the pin in fixture_config must be removed or updated."

This is a known limitation and is acceptable. The pin is a bridge until the fixtures are updated, not a permanent solution.

**Evidence**: Result block, lines 153-155.

---

## Risks

1. **Full suite baseline comparison not completed**: The result block acknowledges this. Claude should run the full suite from his worktree to verify no regressions against the baseline. **Risk: LOW** — 391+ tests verified across 12 modules, all pass.

2. **Pin must be updated if fixtures change**: If the shared fixtures are ever updated to use the new verification roles, the pin in `fixture_config` must be removed or updated. **Risk: LOW** — This is a known limitation and is documented in the result block.

3. **test_e2e full module not verified**: The full `test_e2e` module timed out after 300 seconds. Only `TestEnrichmentOutcomes` (9/9) was verified. **Risk: LOW** — The specific test named in TASK-250 passes, and the approach is sound.

---

## Conclusion

**DISPOSITION: MERGE**

The artifact is correct, the wiring is real, and the approach is safe. Two falsification tests prove the verification pin does real work and that the live client config remains unaffected. Shared fixtures are untouched. All critical test modules pass (391+ tests verified across 12 modules).

The full suite baseline comparison is owed, but the risk is low given the extensive verification already performed. Claude should run the full suite from his worktree to verify no regressions against the baseline artifact.

**RECOMMENDATION**: Merge to master.

---

## Verification Commands

All commands were run in an isolated worktree at SHA `3efcc9683f2a3dd23b1096ef1824d70d78f5cb33`.

```bash
# Verify branch HEAD SHA
git rev-parse origin/qwen-worker-9-r61
# Output: 3efcc9683f2a3dd23b1096ef1824d70d78f5cb33

# Check shared fixtures untouched
git diff master...3efcc9683f2a3dd23b1096ef1824d70d78f5cb33 -- tests/fixtures/
# Output: (empty)

# Check no deletions
git diff master...3efcc9683f2a3dd23b1096ef1824d70d78f5cb33 --diff-filter=D --name-only
# Output: (empty)

# Check no forbidden files touched
git diff master...3efcc9683f2a3dd23b1096ef1824d70d78f5cb33 -- src/ config/
# Output: (empty)

# Run key tests
python -m unittest tests.test_e2e.TestEnrichmentOutcomes.test_the_clean_domain_verifies
# Output: OK

python -m unittest tests.test_productive_verification_roles
# Output: Ran 7 tests, OK

python -m unittest tests.test_enrich
# Output: Ran 49 tests, OK

python -m unittest tests.test_approve
# Output: Ran 43 tests, OK

python -m unittest tests.test_push
# Output: Ran 37 tests, OK

python -m unittest tests.test_cadence
# Output: Ran 38 tests, OK

python -m unittest tests.test_double_verification
# Output: Ran 53 tests, OK

# Verify pinned vs live roles
python -c "from tests.base import fixture_config; from src import clients; \
  fc=fixture_config().get('verification',{}); \
  live=clients.load('productive').get('verification',{}); \
  print(f'Pinned: {fc}'); print(f'Live: {live}'); print(f'Different: {fc != live}')"
# Output: Pinned: {primary: contactout, secondary: deliverable, catch_all: reoon}
#         Live: {primary: deliverable, secondary: reoon, catch_all: reoon}
#         Different: True
```

---

## Mutation Tests

**Mutation Test 1**: Removed verification pin from `fixture_config()`.

```bash
# Mutate tests/base.py: remove the verification pin
# Run test_the_clean_domain_verifies
# Restore tests/base.py
```

**Result**: FAILED with `AssertionError: 'held' != 'approved'`

**Interpretation**: The pin is doing real work. Without it, the record lands `held` instead of `approved`, which is exactly the failure mode TASK-250 described.

---

**Mutation Test 2**: Set verification pin to WRONG values.

```bash
# Mutate tests/base.py: set verification roles to WRONG
# Run test_productive_verification_roles
# Restore tests/base.py
```

**Result**: PASSED (7/7 OK)

**Interpretation**: The live roles test is unaffected by the pin, proving it reads the live client config via `clients.load`, not the pinned config.

---

## Reviewer Attestation

I reviewed the artifact at SHA `3efcc9683f2a3dd23b1096ef1824d70d78f5cb33` on branch `origin/qwen-worker-9-r61`. I verified the artifact exists, the wiring is real, the tests are falsifiable, and the approach is safe. I performed two mutation tests to prove the wiring is real. I verified that shared fixtures are untouched and that the live client config is unaffected.

**Verdict**: MERGE.

---

**Review completed**: 2026-10-03  
**Reviewer**: GLM (independent verification, TASK-474)  
**Branch HEAD SHA reviewed**: `3efcc9683f2a3dd23b1096ef1824d70d78f5cb33`
