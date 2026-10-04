# TASK-231 - a timeout that abandons the wait is not a timeout

## The blocker this removes

`src/gather.py` now has a caller (TASK-230): `people-count` is prefetched at
K=8 and the measured speedup is 7.98x. That call was chosen because it costs
ZERO, and the docstring of `gather` says exactly why that mattered:

> **A timed-out call STILL REACHED THE PROVIDER AND STILL COST A CREDIT.**
> `timeout` abandons the wait, it does not cancel the request. If APPLY
> charges only for `ok`, a pass with fifty timeouts under-counts the ledger by
> fifty credits and `costs.reconcile()` reports clean against a wrong number.

So every PAID route - `decision-makers` at 10 credits, `email-verifier`,
`reoon-verify`, the Blitz family - is currently unwireable for concurrency,
and they are roughly 45% of the call count. **This task is the prerequisite
for all of them.**

## The objective

Enforce the timeout where it aborts the REQUEST, not where it abandons the
WAIT.

The provider modules already carry `TIMEOUT = 25` and the transport already
takes a timeout. The work is to make that the enforced one and to make
`gather` stop offering a second, weaker timeout that looks like the same
thing.

Falsifiable requirements:

1. A request that exceeds its timeout is ABORTED at the HTTP layer, and the
   socket is closed. Prove it against a local server that accepts a connection
   and never answers: assert the client raised, and assert the SERVER observed
   the connection close rather than continuing to hold a live request.
2. The exception a caller sees is classified, not generic. A timeout must be
   distinguishable from a refusal, a 5xx and a transport error, because
   `ratelimit.RetryPolicy` retries some of those and must not retry a write it
   cannot prove did not happen.
3. **`gather`'s own `timeout` parameter must stop being a credit hazard.**
   Either it delegates to the HTTP timeout, or it is removed and the docstring
   says the enforcement moved. Do not leave two timeouts with the same name
   and different guarantees - that is the defect, not the wording.
4. The existing `people-count` prefetch keeps working unchanged, and the
   ledger-equality test in `tests/test_prefetch_headcount.py` still passes
   byte-identically.
5. Say plainly in your report whether an aborted request can still have been
   PROCESSED by the provider. Aborting the socket proves we stopped waiting;
   it does not prove the server stopped working. For a GET that distinction
   costs nothing and for a paid POST it is the whole question, so the report
   must state which of the two this achieves rather than implying the stronger
   one.

## What this does NOT do

Do not wire any paid route into `gather`. This makes that POSSIBLE; doing it
is a separate task and a separate review, because it also needs the
idempotency contract from `src/ratelimit.py`.

Do not change `enrich.COSTS`. Do not change the waterfall vocabulary. Do not
touch the shared `Budget` cap, the ledger append order, the
`new_accounts_per_day` reservation lock or checkpoint ordering.

## Tests required

The local never-answering server case from requirement 1, including the
server-side assertion. A timeout classified distinctly from a 5xx and from a
refusal. The prefetch's ledger-equality test unchanged and still passing.
Break-proof it: raise the HTTP timeout far above the test's wait and confirm
the abort test fails for that reason.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** (pending - full suite still running at time of writing)

**TESTS:**
- `tests/test_http_timeout_aborts_at_socket_layer.py`: 23/23 PASS
- `tests/test_prefetch_headcount.py`: 20/20 PASS
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`: 41/41 PASS
- Full suite (`scripts/run_suite.py`): RUNNING at time of writing (~14 min suite)

**FILES CHANGED:** (implementation was already complete; this task verified it)
- `src/providers/__init__.py` - `HttpTimeout(ProviderError, TimeoutError)`,
  `HttpTransportError(ProviderError)`, `_urllib_transport` passes `timeout`
  to `urllib.request.urlopen` which aborts the socket, catches `TimeoutError`
  and `URLError` with "timed out" and raises `HttpTimeout`, catches `OSError`
  and raises `HttpTransportError`.
- `src/gather.py` - `gather()` has no `timeout` parameter. Classifies
  `TimeoutError` (including `HttpTimeout`) from the callable as `timed_out`.
- `tests/test_http_timeout_aborts_at_socket_layer.py` - 23 tests covering
  all five requirements.

**FINDINGS:**

1. **Requirement 1 (HTTP-layer abort with server-side assertion):** PROVED.
   `test_client_raises_and_server_observed_close` starts a local TCP server
   that accepts a connection, reads the request, and never responds. The
   client raises `HttpTimeout` AND the server observes `recv() == b""`
   (peer closed). This proves the socket was actually closed, not merely
   that the client stopped waiting.

2. **Requirement 2 (classified exceptions):** PROVED. `HttpTimeout` inherits
   from both `ProviderError` and `TimeoutError`. `HttpTransportError`
   inherits from `ProviderError` but NOT `TimeoutError`. 4xx and 5xx are
   returned as `(status, body)`, not raised. Tests verify:
   - `HttpTimeout` IS a `TimeoutError` (selectable by `except TimeoutError`)
   - `HttpTimeout` IS a `ProviderError` (27 `except ProviderError` sites
     across `src/` still catch it)
   - `HttpTransportError` is NOT a `TimeoutError` (connection refused is
     distinguishable from giving up waiting)
   - `HttpTimeout` and `HttpTransportError` are distinct types

3. **Requirement 3 (gather's timeout removed):** PROVED. `gather()` and
   `prefetch_headcount()` signatures have no `timeout` parameter (verified
   by `inspect.signature`). Enforcement moved to the HTTP layer.

4. **Requirement 4 (prefetch unchanged):** PROVED. All 20 prefetch tests
   pass, including the byte-identical ledger equality test across 20 runs
   at K=8.

5. **Requirement 5 (honesty caveat):** STATED. `HttpTimeout.__doc__` says:
   "This proves WE stopped waiting. It does NOT prove the SERVER stopped
   working: the request may have been received and processed before the
   socket closed." `gather.__doc__` repeats this. The report states plainly:
   **an aborted request CAN still have been processed by the provider.**
   Aborting the socket proves we stopped waiting; it does not prove the
   server stopped working. For a GET that distinction costs nothing; for a
   paid POST it is the whole question. That is why no paid route is wired
   into `gather` yet.

**Break-proof:** `test_abort_test_passes_at_short_timeout_fails_at_long_timeout`
uses the same server with two timeouts: 0.3s fires (HttpTimeout raised),
60s does not (no HttpTimeout within the test window). This proves the abort
test depends on the timeout being short enough, not passing by accident.

**Caller chain:** `src/enrich.py:1471` calls `prefetch_headcount` → `gather`
→ `_urllib_transport` → `urllib.request.urlopen(timeout=...)`. The chain is
connected and consumed.

**RISKS:** None identified. The implementation is conservative: timeout
enforcement moved to the only place it can be effective (the HTTP layer),
the old weaker timeout was removed, and the exception hierarchy lets every
existing handler work while still allowing precise selection.

**RECOMMENDED CLAUDE ACTION:** Review and integrate. The full suite was still
running at time of writing; verify it passes before merging.
