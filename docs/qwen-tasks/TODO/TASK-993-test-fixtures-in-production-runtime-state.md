# TASK-993 — test fixture strings are sitting in production runtime state

STAGE: QUEUED
PRIORITY: P2

## Measured 2026-10-12

`work/replywatch.json`, live production state, contains:

    "digest":  {"healthy": false, "last_error": "RuntimeError: no"}
    "watcher": {"healthy": false, "last_error": "RuntimeError: still on fire"}

"still on fire" and "no" are test fixture strings. A test wrote into the
operator's real runtime state, and two components have reported unhealthy ever
since on the strength of it.

The `emailbison` and `heyreach` entries in the same file are genuine and
healthy, checkpointed to 2026-10-11T00:33:16Z.

## Why it matters

`replywatch.healthy()` and `replywatch.problems()` read this file. Two
permanently unhealthy components are two alarms nobody can act on, which is
exactly how a real alarm comes to be ignored.

## Acceptance

- Find the test that writes the production path and isolate it. `store` has
  `refuse_production_write` and `use_directory` for precisely this, so a test
  reaching production state means one of them was bypassed.
- Clear the two fixture rows, or prove they are genuine.
- A test proving a test cannot write that file. The pattern already exists:
  `tests/test_tests_cannot_write_client_state.py`.
