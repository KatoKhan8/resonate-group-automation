# TASK-433 — GLM Independent Verification of TASK-231

## Review target

    task            TASK-231
    branch          qwen-worker-8-r28
    branch HEAD SHA 36a4ce61b454187772e78daac49b08282380193e
    verified SHA    36a4ce61b454187772e78daac49b08282380193e (unchanged)
    worktree        .qwen/worktrees/task433-review (detached HEAD at 36a4ce61)

**The branch HEAD has NOT moved since the task file named it.**

## What TASK-231 claims

1. The HTTP timeout now aborts the REQUEST at the socket layer, not merely abandons the wait.
2. Exceptions are classified: `HttpTimeout` (TimeoutError) vs `HttpTransportError` (ProviderError) vs 4xx/5xx returned as status.
3. `gather`'s own `timeout` parameter is removed — no more dual-timeout credit hazard.
4. The people-count prefetch keeps working unchanged; ledger-equality tests pass byte-identically.
5. Honest caveat: aborting the socket proves WE stopped waiting, NOT that the SERVER stopped working.

## Findings

### F1: Artifact exists on the ref — VERIFIED

Files changed (TASK-231 scope only):
- `src/providers/__init__.py`: +25 lines — `HttpTimeout(TimeoutError)`, `HttpTransportError(ProviderError)`, refined exception handling in `_urllib_transport`
- `src/gather.py`: -30/+20 lines — removed `timeout` parameter from `gather()` and `prefetch_headcount()`, removed `_CallableTimeoutError`, catches `TimeoutError` directly
- `tests/test_http_timeout_aborts_at_socket_layer.py`: new, 451 lines, 19 tests
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`: updated timeout tests
- `tests/test_prefetch_headcount.py`: updated timeout tests

### F2: Existence is function — VERIFIED, every link consumed

**`HttpTimeout` consumption chain:**
- Raised by `_urllib_transport` at `src/providers/__init__.py:215,221` when `TimeoutError` or `URLError` with "timed out" fires
- `HttpTimeout` inherits from `TimeoutError` (not `ProviderError`)
- Caught by `gather()` at `src/gather.py:247` as `except TimeoutError` → classified as `Outcome.timed_out()`
- `gather()` is called by `prefetch_headcount()` at `src/gather.py:353`
- `prefetch_headcount()` is the first caller, used by `enrich.run()`

**`HttpTransportError` consumption chain:**
- Raised by `_urllib_transport` at `src/providers/__init__.py:224,230,234`
- `HttpTransportError` inherits from `ProviderError`
- Caught by 30+ existing `except ProviderError` handlers throughout `src/` (enrich.py, bisonfactory.py, campaigns.py, leadstop.py, mapping.py, generate.py, all provider modules, validate.py, verification.py, research.py, webfetch.py)

**`_urllib_transport` is the production transport:**
- Assigned to `_transport` at `src/providers/__init__.py:239`
- Called by `providers.request()` at line 255
- Every provider module calls `providers.request()` — this IS the production path

**Zero production callers means DISCONNECTED: NOT APPLICABLE.** The new exceptions are consumed through their parent classes by every existing handler.

### F3: Falsification of claims — ALL PASS

**Claim 1: Socket abort, not wait abandonment**
- Independent reproduction: started a TCP server that accepts, reads the request, never responds
- Client raised `HttpTimeout: HTTP GET timed out after 0.3s` ✓
- Server observed `recv() == b''` (peer closed) ✓
- **The socket was actually closed, not merely abandoned.**

**Claim 2: Exception classification**
- `issubclass(HttpTimeout, TimeoutError)` → True ✓
- `issubclass(HttpTimeout, ProviderError)` → False ✓
- `issubclass(HttpTransportError, ProviderError)` → True ✓
- `issubclass(HttpTransportError, TimeoutError)` → False ✓
- `issubclass(HttpTimeout, HttpTransportError)` → False ✓
- 4xx returned as `(status=403, body)`, not raised ✓
- 5xx returned as `(status=500, body)`, not raised ✓

**Claim 3: gather has no timeout parameter**
- `inspect.signature(gather).parameters` → `['items', 'call', 'k', 'min_interval']` ✓
- `inspect.signature(prefetch_headcount).parameters` → `['records', 'people_count', 'spend', 'k', 'on_applied']` ✓
- No `timeout` in either ✓

**Claim 4: Prefetch still works**
- `tests/test_prefetch_headcount.py`: 20 tests, all pass ✓
- Ledger equality across 20 runs at K=8: byte-identical ✓
- `tests/test_enrich.py`: 49 tests, all pass ✓

**Claim 5: Honesty caveat**
- `HttpTimeout.__doc__` contains "WE stopped waiting", "does NOT prove", "SERVER" ✓
- `gather.__doc__` contains "HTTP layer", "TimeoutError" ✓

**Break-proof:**
- 0.3s timeout → `HttpTimeout` raised ✓
- 60s timeout → no `HttpTimeout` within test window ✓
- Same server, different deadlines: the abort test depends on the timeout being short enough ✓

### F4: Tests are falsifiable — VERIFIED

The tests are NOT:
- `hasattr` checks
- Assertions on source text
- Token-in-file checks
- JSON shape assertions
- Fake cassettes returning fake data

The tests ARE:
- Real TCP servers that accept connections and never respond
- Server-side assertions that the client closed the socket
- Real exception hierarchy checks with `issubclass`
- Real `gather()` calls with callables that raise `TimeoutError`
- Break-proof: same server, two timeouts, different outcomes

**How could these pass while the implementation is wrong?**
- If the server-side close assertion were fake: but it uses `recv() == b''`, which is the POSIX definition of peer close
- If `HttpTimeout` were not actually raised by the transport: but the test starts a real server and measures real socket behavior
- If `gather` still had a timeout parameter: but `inspect.signature` proves it does not

I cannot produce a path where these tests pass but the implementation is wrong.

### F5: Merging would NOT delete anything — VERIFIED

`git diff master...36a4ce61 --diff-filter=D --name-only` returns:
- `docs/qwen-tasks/TODO/TASK-231-a-timeout-that-abandons-is-not-a-timeout.md` (moved to REVIEW, expected)

No production files, no test files, no documentation files would be deleted.

### F6: Scope drift — PRESENT, cherry-pick required

The branch carries TASK-226 changes (queuejournal offset index, journal tests, benchmark scripts):
- `src/queuejournal.py`: +174 lines
- `tests/test_the_journal_index.py`: +256 lines (new)
- `scripts/journal_benchmark_report.py`: +218 lines (new)
- `scripts/journal_read_benchmark.py`: +314 lines (new)
- `scripts/journal_replay_cost.py`: +204 lines (new)

Total scope drift: 1,156 lines across 5 files, unrelated to TASK-231.

**Cherry-pick scope for TASK-231 only:**
- `src/providers/__init__.py`
- `src/gather.py`
- `tests/test_http_timeout_aborts_at_socket_layer.py`
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`
- `tests/test_prefetch_headcount.py`

TASK-226 should be reviewed and merged separately.

## Test results

All TASK-231 tests pass on the exact ref:
- `tests/test_http_timeout_aborts_at_socket_layer.py`: 19/19 pass
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`: 41/41 pass
- `tests/test_prefetch_headcount.py`: 20/20 pass
- `tests/test_enrich.py`: 49/49 pass
- `tests/test_invariants.py`: 83 tests, 1 FAIL + 1 ERROR (both pre-existing, unrelated to TASK-231)
  - FAIL: `test_emailbison_posts_only_to_routes_it_declares` — the task file mentions this
  - ERROR: `test_nothing_was_written_by_that` — `work/` directory does not exist in worktree (gitignored)

## Disposition

**MERGE** (with cherry-pick of TASK-231 files only)

**Reason:**
1. The artifact exists on the exact ref named.
2. Every new exception type is consumed by production code through its parent class.
3. All five claims are independently falsified and pass.
4. The tests are falsifiable — they use real sockets, real servers, real exception types.
5. Merging would not delete anything.
6. The scope drift (TASK-226) is isolated and can be cherry-picked around.

**The honesty caveat is the strongest part of this task.** The result explicitly states what was NOT achieved (server may still have processed the request) rather than implying the stronger claim. This is the right level of honesty for a prerequisite task that has not yet wired a paid route.

**Next step:** Wire a paid route into `gather`, which needs the idempotency contract from `src/ratelimit.py` as a separate task.

## Boundaries observed

- Provider writes = 0
- No real provider called
- No campaign touched
- Read-only review in isolated worktree
- Verdict is the deliverable, Claude merges
