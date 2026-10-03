# TASK-535 — GLM Independent Verification of TASK-433

## Review target

    task            TASK-433
    branch          origin/glm-review-504-task-387
    branch HEAD SHA f3b68bf849d8361fab9d3f8f972229369cf60944 (current)
    branch HEAD SHA 515c638e14423a203e56f3ed3525af8569f72c07 (moved)
    verified SHA    f3b68bf849d8361fab9d3f8f972229369cf60944
    worktree        .qwen/worktrees/task535-review (detached HEAD at f3b68bf8)

**The branch HEAD has MOVED since the task file named it.** The task file said `f3b68bf849d8361fab9d3f8f972229369cf60944` and `git rev-parse origin/glm-review-504-task-387` now returns `515c638e14423a203e56f3ed3525af8569f72c07`. Per the task instructions, I reviewed `f3b68bf849d8361fab9d3f8f972229369cf60944` anyway, because that is the artifact this verdict is about.

TASK-433 is itself a GLM verdict for TASK-231. TASK-433 reviewed SHA `36a4ce61b454187772e78daac49b08282380193e` (qwen-worker-8-r28). I independently verified TASK-433's claims by checking out `36a4ce61` in a separate worktree and running the tests and falsifications myself.

## What TASK-433 claims

TASK-433's verdict for TASK-231 claims:
1. The artifact exists on the exact ref (`36a4ce61`)
2. Existence is function — every link consumed
3. All five TASK-231 claims are falsified and pass
4. Tests are falsifiable
5. Merging would not delete anything
6. Scope drift present (TASK-226), cherry-pick required
7. Recommendation: MERGE (cherry-pick TASK-231 files only)

## Findings

### F1: Artifact exists on the ref — VERIFIED

At `36a4ce61`, the TASK-231 changes are present:
- `src/providers/__init__.py`: `HttpTimeout(TimeoutError)`, `HttpTransportError(ProviderError)`, refined exception handling in `_urllib_transport`
- `src/gather.py`: removed `timeout` parameter from `gather()` and `prefetch_headcount()`, catches `TimeoutError` directly
- `tests/test_http_timeout_aborts_at_socket_layer.py`: new, 19 tests
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`: updated timeout tests
- `tests/test_prefetch_headcount.py`: updated timeout tests

**VERIFIED.** The files exist and contain the claimed changes.

### F2: Existence is function — PARTIALLY VERIFIED, one consumption gap missed

**TASK-433's claim:** "The new exceptions are consumed through their parent classes by every existing handler."

**Independent verification:**

**`HttpTimeout` consumption at `36a4ce61`:**
- `HttpTimeout(TimeoutError)` — inherits from `TimeoutError` only, NOT from `ProviderError`
- `issubclass(HttpTimeout, ProviderError)` → **False** (independently confirmed)
- Caught by `gather()` at `src/gather.py:247` as `except TimeoutError` ✓
- **NOT caught by the 27+ `except ProviderError` handlers in `src/enrich.py`, `src/bisonfactory.py`, `src/campaigns.py`, etc.**

**Falsification performed:**
```python
from src.providers import HttpTimeout, ProviderError
try:
    raise HttpTimeout('test')
except ProviderError:
    print('CAUGHT')
except TimeoutError:
    print('ESCAPED except ProviderError')
# Output: ESCAPED except ProviderError
```

**The consumption gap:**
At `36a4ce61`, if a provider function is called directly (not through `gather()`), and that function raises `HttpTimeout`, the `except ProviderError` handlers in `enrich.py` and other modules will NOT catch it. The exception will propagate up uncaught.

**Example path:**
1. `enrich.run()` calls `bisonfactory.check()` directly (not through `gather()`)
2. `bisonfactory.check()` calls `providers.request()`
3. `providers.request()` calls `_transport()` which raises `HttpTimeout`
4. `HttpTimeout` propagates through `bisonfactory.check()` (no handler)
5. The `except ProviderError` in `enrich.run()` does NOT catch it
6. The exception propagates further, potentially ending the pass

**TASK-433's verdict missed this.** It correctly traced the `gather()` path but incorrectly claimed "every existing handler" consumes the new exceptions. The 27+ `except ProviderError` handlers do NOT consume `HttpTimeout` at `36a4ce61`.

**However:** This defect was caught and fixed during integration. Commit `b513879d1` on master ("Integrate TASK-231: the timeout aborts the socket, and it is still a ProviderError") changed `HttpTimeout(TimeoutError)` to `HttpTimeout(ProviderError, TimeoutError)`. The code at `f3b68bf8` (the branch I'm reviewing) reflects this fix. The docstring at `f3b68bf8` explains:

> "This was `HttpTimeout(TimeoutError)` alone, on the reasoning that inheriting from nothing else keeps it distinguishable from a transport error, a refusal and a 5xx. Distinguishable it was - and invisible to every existing handler, because before this change a timeout arrived as a plain `ProviderError` and **27 `except ProviderError` sites across `src/` catch exactly that**."

**The fix is correct and is already on master.** TASK-433's verdict was technically correct for the SHA it reviewed, but it missed the consumption gap and recommended MERGE without noting the defect.

**DISPOSITION: PARTIALLY VERIFIED.** The artifact exists and the tests pass, but the verdict's F2 claim "every link consumed" is incorrect for `HttpTimeout` at `36a4ce61`. The defect was later fixed during integration.

### F3: Falsification of TASK-231's claims — ALL PASS (with one caveat)

**Claim 1: Socket abort, not wait abandonment**
- Independent reproduction at `36a4ce61`: started a TCP server that accepts, reads the request, never responds
- Client raised `HttpTimeout: HTTP GET timed out after 0.3s` ✓
- Server observed `recv() == b''` (peer closed) ✓
- **VERIFIED.** The socket was actually closed.

**Claim 2: Exception classification**
- `issubclass(HttpTimeout, TimeoutError)` → True ✓
- `issubclass(HttpTimeout, ProviderError)` → **False** (at `36a4ce61`, this is the defect)
- `issubclass(HttpTransportError, ProviderError)` → True ✓
- `issubclass(HttpTransportError, TimeoutError)` → False ✓
- 4xx returned as `(status=403, body)`, not raised ✓
- 5xx returned as `(status=500, body)`, not raised ✓
- **VERIFIED for the SHA reviewed.** The classification is correct, but `HttpTimeout` not being a `ProviderError` is the consumption gap.

**Claim 3: gather has no timeout parameter**
- `inspect.signature(gather).parameters` → `['items', 'call', 'k', 'min_interval']` ✓
- `inspect.signature(prefetch_headcount).parameters` → `['records', 'people_count', 'spend', 'k', 'on_applied']` ✓
- **VERIFIED.** No `timeout` in either.

**Claim 4: Prefetch still works**
- `tests/test_prefetch_headcount.py`: 20 tests, all pass ✓
- `tests/test_enrich.py`: 49 tests, all pass ✓
- **VERIFIED.**

**Claim 5: Honesty caveat**
- `HttpTimeout.__doc__` contains "WE stopped waiting", "does NOT prove", "SERVER" ✓
- `gather.__doc__` contains "HTTP layer", "TimeoutError" ✓
- **VERIFIED.**

### F4: Tests are falsifiable — VERIFIED

The tests at `36a4ce61` are NOT:
- `hasattr` checks
- Assertions on source text
- Token-in-file checks
- JSON shape assertions
- Fake cassettes returning fake data

The tests ARE:
- Real TCP servers that accept connections and never respond
- Server-side assertions that the client closed the socket (`recv() == b''`)
- Real exception hierarchy checks with `issubclass`
- Real `gather()` calls with callables that raise `TimeoutError`
- Break-proof: same server, two timeouts, different outcomes

**How could these pass while the implementation is wrong?**
- If the server-side close assertion were fake: but it uses `recv() == b''`, which is the POSIX definition of peer close
- If `HttpTimeout` were not actually raised by the transport: but the test starts a real server and measures real socket behavior
- If `gather` still had a timeout parameter: but `inspect.signature` proves it does not

**One test is misleading:** `test_http_timeout_is_not_a_provider_error` asserts that `HttpTimeout` is NOT a `ProviderError`. This test PASSES at `36a4ce61`, but it's asserting a defect, not a feature. The test was later INVERTED at `f3b68bf8` to `test_http_timeout_IS_a_provider_error` after the fix.

**VERIFIED.** The tests are falsifiable and use real sockets, real servers, real exception types.

### F5: Merging would NOT delete anything — VERIFIED

`git diff master...36a4ce61 --diff-filter=D --name-only` returns:
- `docs/qwen-tasks/TODO/TASK-231-a-timeout-that-abandons-is-not-a-timeout.md` (moved to REVIEW, expected)

No production files, no test files, no documentation files would be deleted.

**VERIFIED.**

### F6: Scope drift — PRESENT, cherry-pick required

The branch at `36a4ce61` carries TASK-226 changes (queuejournal offset index, journal tests, benchmark scripts):
- `src/queuejournal.py`: +174 lines
- `tests/test_the_journal_index.py`: +256 lines (new)
- `scripts/journal_benchmark_report.py`: +218 lines (new)
- `scripts/journal_read_benchmark.py`: +314 lines (new)
- `scripts/journal_replay_cost.py`: +204 lines (new)

Total scope drift: 1,156 lines across 5 files, unrelated to TASK-231.

**VERIFIED.** TASK-433 correctly identified the scope drift.

**Cherry-pick scope for TASK-231 only:**
- `src/providers/__init__.py`
- `src/gather.py`
- `tests/test_http_timeout_aborts_at_socket_layer.py`
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`
- `tests/test_prefetch_headcount.py`

## Test results

All TASK-231 tests pass at `36a4ce61`:
- `tests/test_http_timeout_aborts_at_socket_layer.py`: 19/19 pass ✓
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`: 41/41 pass ✓
- `tests/test_prefetch_headcount.py`: 20/20 pass ✓
- `tests/test_enrich.py`: 49/49 pass ✓

## Disposition

**CLOSE** (work already integrated)

**Reason:**
1. TASK-433's verdict was technically correct for the SHA it reviewed (`36a4ce61`).
2. However, TASK-433 missed a critical consumption gap: `HttpTimeout(TimeoutError)` at `36a4ce61` escapes the 27+ `except ProviderError` handlers in direct provider call paths outside `gather()`.
3. This defect was caught and fixed during integration at commit `b513879d1` on master, which changed `HttpTimeout(TimeoutError)` to `HttpTimeout(ProviderError, TimeoutError)`.
4. TASK-231 is already on master with the fix. The verdict's MERGE recommendation is moot.
5. The verdict's F2 claim "every link consumed" is incorrect for the reviewed SHA, but the defect was fixed before merge, so the integrated code is correct.

**The verdict was good but not perfect.** It correctly verified the artifact, the tests, and the falsifiability. It missed one consumption gap, but that gap was caught during integration. The work is done and correct on master.

**No further action required.** TASK-231 is integrated, the fix is on master, and the verdict's recommendation (MERGE with cherry-pick) has been superseded by the actual integration.

## Boundaries observed

- Provider writes = 0
- No real provider called
- No campaign touched
- Read-only review in isolated worktrees
- Verdict is the deliverable, Claude merges
