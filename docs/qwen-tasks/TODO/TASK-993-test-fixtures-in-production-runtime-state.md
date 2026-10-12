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

## Constraints on this assignment — operator, 2026-10-12

Work in YOUR OWN worktree only. These are not negotiable:

- **No provider call, no network, no send.** Nothing in this task needs one.
- **Do not read or touch old campaigns** (274/327/328/352 or any live campaign).
- **Do not change the order or the behaviour of the existing production flow.**
  This is an isolation bug in a TEST, not a flow change. If a fix seems to
  require altering production behaviour, stop and write that in REPORT.md.
- **Do not merge, and do not push to master.** Commit on your own worker branch.
- **One suite at a time on this machine.** Other lanes are live. Run only the
  specific test modules you touch with
  `py -3 -m unittest tests.test_<name> -v`. Never `unittest discover`, never
  `scripts/run_suite.py`.
- **Never `git stash`.** Worktrees share one stash and it has already stolen
  another agent's uncommitted work. Use a WIP commit.

## What a finished result looks like

1. The patch.
2. The test modules you ran, with their actual output pasted in `REPORT.md`.
3. **A positive control proving the check would FAIL if the rule were broken.**
   Concretely: write a test that a test cannot write
   `work/replywatch.json`, then deliberately make a test write it and show your
   new test goes red. A guard that has never been shown to fire is not a guard.
4. If you cannot find the offending test, say so and list exactly where you
   looked. A measured "not found" is a result; a guess is not.
