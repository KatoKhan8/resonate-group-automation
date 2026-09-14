# TASK-086: The tenancy tests are red

## STATUS: REVIEW

## DESCRIPTION

Three ERRORs in the tenancy test files:
- `test_workspace_isolation_attacks.py` (2 errors)
- `test_the_second_client_runs_on_the_same_engine.py` (1 error)

All three are stale tests where production code got stricter, not real leaks.
The question is whether the TEST is stale or the GUARANTEE is gone.

## INSTRUCTIONS

- START WITH THE THREE TENANCY FAILURES.
- If any is a REAL LEAK rather than a stale test, STOP immediately.
- Six of the seven are ERRORS rather than failures - check broken fixture/import first.
- NEVER delete, skip, expectedFailure or weaken any of these tests.
- READS ONLY at every provider.

## FILES ALLOWED
- tests/test_workspace_isolation_attacks.py
- tests/test_the_second_client_runs_on_the_same_engine.py

## FILES FORBIDDEN
- src/* (no production changes - these are test fixes only)

## RESULT BLOCK

### STATUS: COMPLETE

### COMMIT SHA
241ab6e

### TESTS RUN
`py -3 -m unittest tests.test_workspace_isolation_attacks tests.test_the_second_client_runs_on_the_same_engine -v`

### TEST RESULTS
103 tests, 0 failures, 0 errors. 1 skipped (intentional), 3 expected failures (intentional).

### FILES CHANGED
- `tests/test_workspace_isolation_attacks.py` - 2 tests fixed
- `tests/test_the_second_client_runs_on_the_same_engine.py` - 1 test fixed

### FINDINGS

**None of the three were real leaks.** All three were stale tests where production
code got stricter and the tests were not updated.

#### Error 1: test_LEAK_the_sanctioned_write_path_accepts_a_null_client
- **Root cause:** `store.append` now validates that `client` must be a non-empty
  lowercase slug (src/store.py:808). The test expected `client=None` to be accepted.
- **Verdict:** The leak is FIXED. `store.append` now refuses null clients at the
  ingestion boundary.
- **Fix:** Renamed to `test_the_sanctioned_write_path_refuses_a_null_client`.
  Asserts `ValueError` on `store.append` with null client.

#### Error 2: test_the_unscoped_default_reads_the_whole_estate
- **Root cause:** `approve.pending()` now requires `recs` as a positional argument
  (src/approve.py:221). The test called it with no arguments.
- **Verdict:** The unscoped path is GONE. The function can no longer be called
  without an explicit record list.
- **Fix:** Renamed to `test_the_unscoped_default_is_gone`. Asserts `TypeError`
  on no-arg call, then verifies the scoped path still works correctly.

#### Error 3: test_an_unowned_record_belongs_to_nobody_rather_than_to_everybody
- **Root cause:** Same as Error 1 - `store.append` refuses null client.
- **Verdict:** Not a leak. The test's purpose is to assert Repo scope, not
  ingestion. The orphan just needs to exist in the store.
- **Fix:** Uses `store.transaction()` (the lower-level path) to create the orphan,
  matching the pattern used by the `orphan()` helper in the first test file.

### CLASSIFICATION
All three were **stale tests** (broken fixtures), not broken guarantees. The
production code became stricter in two places:
1. `store.append` validates client slug (prevents orphan records)
2. `approve.pending` requires explicit `recs` (prevents unscoped reads)

Both changes CLOSE former risks rather than opening new ones.

### RISKS
None. No production code was changed. No tests were weakened, skipped, or removed.
All assertions now match the stricter production behavior.

### RECOMMENDED CLAUDE ACTION
Review and merge. The tenancy boundary is intact and the tests now document the
current (stricter) state correctly.
