PRIORITY: P1
DEPENDS:

# TASK-264 — find every environment leak, and make isolation the default

Tests that pass standalone and fail under full discovery. The infra session
already found and fixed two instances of this class today; this task finds the
rest and removes the class.

## The two already diagnosed, as the worked example

`test_invariants.TestTheBarrierCoversEveryWriter` and
`TestValidationCannotSpendByAccident` were green alone and red in the suite.
Cause, reproduced rather than inferred:

    clean environment        5/5 OK
    QUEUE=<tmp> ...          4 failures
    SPEND_LEDGER=<tmp> ...   1 failure, exactly the spendledger subtest

`spendledger`, `observability` and `validate.output_dir` resolve their own
path beside `store.queue_path()`. With `QUEUE` still pointing at an earlier
module's temp directory they write THERE, the barrier correctly does not fire,
and the test fails while the guard is in perfect health.

Fixed with a `PinsTheRealStatePaths` mixin. **That fix is a patch on two
classes. This task is the general case.**

## What leaks

Three kinds, and the task must look for all three:

1. **Environment variables.** 50 test modules call `store.use_directory`,
   which sets `QUEUE` and clears `STATE_OVERRIDES`. Any module that does not
   restore them leaks into the next. `QUEUE_BACKEND`, `QUEUE_JOURNAL`,
   `SHADOW_STRICT` and `QUEUE_DB` are newer and equally leaky.
2. **Cached modules.** A module that reads an env var AT IMPORT rather than
   per call is frozen at whatever the first importer set. `store.queue_path()`
   resolves per call precisely for this reason and says so in its docstring;
   find the ones that do not.
3. **Shared temp dirs.** A module that builds a fixture estate in a fixed
   path rather than `mkdtemp` shares it with everything after it.

## Do

1. **Measure first.** Run every test module STANDALONE, record pass/fail per
   module, then run the full suite and diff BY NAME. The set difference is
   the leak list. `docs/state/SUITE-BASELINE-2026-09-22.json` is the
   full-run baseline; regenerate the standalone side.
2. **Report which module leaked WHAT** - the operator asked for this
   explicitly. Not "test_x leaks" but "test_x leaves QUEUE set to a deleted
   temp dir".
3. **Make isolation the default**, in `tests/base.py`, so a module gets it
   without remembering: save and restore `QUEUE`, `QUEUE_BACKEND`,
   `QUEUE_JOURNAL`, `SHADOW_STRICT` and every `store.STATE_OVERRIDES` entry
   around each test. Clear rather than assert-clean - a test that skips on a
   dirty environment tests nothing on a dirty environment.
4. Bring the full-run baseline to the standalone number and report both.

## Falsifiable requirements

1. The leak list, per module, with what each leaked. This is the deliverable.
2. Isolation by default in `tests/base.py`, and a test that PROVES it: set a
   poisoned env var, run a test, assert it is restored afterwards.
3. Full-run failures equal standalone failures. If a residue remains, name it
   and say why rather than rounding it away.
4. **No test is deleted, skipped or weakened to close the gap.** A test that
   only passes in isolation because it depends on a leak is a finding, not a
   fix.
5. The existing `PinsTheRealStatePaths` mixin becomes redundant or is folded
   in - two mechanisms for one job is the drift this repo keeps naming.

## Do not

- Do not change what any test asserts.
- Do not touch `config/.env`, `src/providers/*`, `scripts/*_watch_loop.py` or
  `work/`.
- Do not run anything under `timeout`. Suites go to a file, detached.
