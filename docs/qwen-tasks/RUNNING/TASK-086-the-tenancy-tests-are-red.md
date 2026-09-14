# TASK-086: The tenancy tests are red

## STATUS: RUNNING

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
