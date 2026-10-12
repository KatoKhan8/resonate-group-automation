# TASK-993 REPORT — test fixture strings in production runtime state

## STATUS: DONE

## FINDINGS

### 1. The offending test

`tests/test_replywatch.py::TheLoop::test_a_sweep_that_raises_does_not_kill_the_watcher`
(line 305 in the original file).

The class `TheLoop` inherited from bare `unittest.TestCase` with no store
isolation. When the test's custom sweeper raised `RuntimeError("still on fire")`,
the `Watcher._tick()` method caught it and called `_record_failure("watcher", exc)`,
which called `_write_status("watcher", {"last_error": "RuntimeError: still on fire", ...})`.

`_write_status` writes to `work/replywatch.json` via a temp-file-and-replace
pattern. Before the barrier existed, this wrote directly to the production path.

A second fixture, `RuntimeError: no`, came from the same test class via the
`digest` after-job path: `Watcher._tick()` iterates `self.after` and catches
exceptions from each job, calling `_record_failure(name, exc)` with the same
`_write_status` path.

### 2. The barrier is already in place

`store.refuse_production_write(path)` is called by `_write_status` before any
filesystem mutation. `REPLY_WATCH_STATUS` is in `STATE_OVERRIDES`, so
`store.use_directory()` moves it alongside the queue. The barrier covers the
file in two independent ways:

- **Barrier 1**: `ProviderTest.setUp` calls `store.use_directory(tmp)`, which
  pops `REPLY_WATCH_STATUS` from the environment, so `status_path()` resolves
  into the temp directory.
- **Barrier 2**: `refuse_production_write` checks `under_test()` and refuses
  any write to `PRODUCTION_WORK` or the main checkout's `work/`.

The existing test
`test_the_reply_watcher_cannot_report_health_into_real_state` in
`tests/test_tests_cannot_write_client_state.py` proves barrier 2 fires for
`replywatch._write_status`.

### 3. The fix: isolate TheLoop

`TheLoop` was the only class in `test_replywatch.py` that used bare
`unittest.TestCase` AND triggered a write to `work/`. The other bare class,
`Gating`, only reads environment variables and never writes.

Added `setUp`/`tearDown` to `TheLoop`:

```python
def setUp(self):
    self._tmp = tempfile.mkdtemp(prefix="rga-loop-")
    store.use_directory(os.path.join(self._tmp, "work"))

def tearDown(self):
    shutil.rmtree(self._tmp, ignore_errors=True)
```

This is barrier 1: the write goes to the temp directory, and the barrier 2
check never fires because the path is not in `PRODUCTION_WORK`.

### 4. The contamination registry

`src/contamination.py` already tracks `replywatch.json` as contaminated with
marker `"still on fire"`, registered since `"2026-09-02"`. The registry says:

> do NOT conclude anything about reply-watcher health from this file.

Clearing the file is a destructive write to client state and requires a human
decision. The registry entry stays until the file is actually cleared.

### 5. Positive control

The guard is proven to fire by 23 tests in
`tests/test_tests_cannot_write_client_state.py`, all passing:

- `test_the_reply_watcher_cannot_report_health_into_real_state` — directly
  calls `replywatch._write_status` with the production path unresolved and
  asserts `ProductionStateUnderTest`.
- `test_barrier_two_still_fires_if_barrier_one_is_undone` — pops all
  `STATE_OVERRIDES` and proves the refusal still fires.
- `test_every_state_override_names_a_file_the_guard_would_refuse` — iterates
  every entry in `STATE_OVERRIDES` including `REPLY_WATCH_STATUS`.

## TESTS RUN

### tests.test_replywatch

```
Ran 26 tests in 22.229s
OK
```

### tests.test_tests_cannot_write_client_state

```
Ran 23 tests in 0.443s
OK
```

## FILES CHANGED

- `tests/test_replywatch.py` — added `import shutil`, `import tempfile`;
  added `setUp`/`tearDown` to `TheLoop` class isolating the store.

## RISKS

- The contamination in the main checkout's `work/replywatch.json` is NOT
  cleared by this patch. Clearing it is a human decision per
  `src/contamination.py`. The barrier prevents new contamination; the old
  fixture strings remain until manually cleared.

## RECOMMENDED CLAUDE ACTION

1. Review the isolation fix in `tests/test_replywatch.py`.
2. Clear `work/replywatch.json` in the main checkout (or rebuild it from a
   real poll). The contamination registry entry can then be removed.
3. Promote to DONE.
