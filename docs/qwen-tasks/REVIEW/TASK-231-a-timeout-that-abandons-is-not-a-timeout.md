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

**STATUS: DONE**

**COMMIT SHA:** ed070c63 (claim) + this commit

**TESTS:**
- `tests/test_http_timeout_aborts_at_socket_layer.py` — 23 tests, all pass
- `tests/test_prefetch_headcount.py` — 20 tests, all pass (ledger equality byte-identical)
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py` — 41 tests, all pass
- `tests/test_ratelimit.py`, `tests/test_providers.py`, `tests/test_failure_injection.py` — 144 tests, all pass
- Combined run of all six modules: 228 tests, 0 failures

**FILES CHANGED:** None by this task. The implementation and tests were already in place in `src/gather.py`, `src/providers/__init__.py`, and `tests/test_http_timeout_aborts_at_socket_layer.py`. This task verified the implementation meets all five requirements and reports the findings.

**Artifact kind:** finding (verification report). The code and tests already existed; this task's deliverable is the RESULT BLOCK confirming correctness and stating the honesty caveat.

**FINDINGS:**

### Requirement 1: HTTP-level abort — MET

`src/providers/_urllib_transport` passes `timeout` to `urllib.request.urlopen`, which aborts the socket when the deadline expires. The test `test_client_raises_and_server_observed_close` proves this with a local server that accepts a connection and never responds:
- The client raises `HttpTimeout` ✓
- The server observes `recv` returning `b""` (peer closed) ✓

This is not merely "the client stopped waiting" — the server saw the connection close.

### Requirement 2: Classified exceptions — MET

Four distinct exception types, each distinguishable by `isinstance`:
- `HttpTimeout(ProviderError, TimeoutError)` — the HTTP request was aborted at the socket layer
- `HttpTransportError(ProviderError)` — DNS, connection refused, unreachable host (request demonstrably did not arrive)
- 4xx responses are returned as `(status, body)`, not raised
- 5xx responses are returned as `(status, body)`, not raised

`HttpTimeout` inherits from BOTH `ProviderError` (so 27 existing `except ProviderError` sites still catch it) and `TimeoutError` (so `except TimeoutError` recognises it as a timeout). This was measured: with `HttpTimeout(TimeoutError)` alone, the exception escaped every `except ProviderError` handler.

### Requirement 3: gather has no timeout parameter — MET

`inspect.signature(gather)` has no `timeout` parameter. `inspect.signature(prefetch_headcount)` has no `timeout` parameter. The docstrings state enforcement moved to the HTTP layer. A callable that raises `TimeoutError` (including `HttpTimeout`) is classified as `timed_out` in the Outcome.

### Requirement 4: Prefetch unchanged — MET

All 20 tests in `test_prefetch_headcount.py` pass, including:
- `test_ledger_is_byte_identical_serial_vs_k8` — serial vs K=8, byte-identical waterfall
- `test_ledger_equality_holds_across_twenty_runs` — 20 concurrent runs, every one matches
- `test_a_timeout_leaves_neighbours_intact` — timeout on one record, others succeed

### Requirement 5: Honesty caveat — STATED

**This achieves the WEAKER claim: we stopped waiting. It does NOT prove the server stopped working.**

Aborting the socket proves the client closed the connection. For a GET (like `people-count`), this distinction costs nothing — a GET that was partially processed can be retried idempotently. For a paid POST, this is the whole question: the server may have received the request, processed it, and charged the credit before the socket closed. The client raising `HttpTimeout` does not prove the credit was not spent.

**That is why no paid route is wired into `gather` yet.** The people-count call costs zero, so the honesty caveat has no value to be wrong about. Wiring a paid route needs the idempotency contract from `src/ratelimit.py` as a separate task.

### Break-proof — MET

`test_abort_test_fails_when_timeout_is_raised_far_above_wait`: with a 60s timeout and a 1.5s test window, no `HttpTimeout` is raised. `test_abort_test_passes_at_short_timeout_fails_at_long_timeout`: 0.3s fires, 60s does not. The abort test depends on the timeout being short enough — if it passed at 60s, the short-timeout pass would not be testing the deadline.

**RISKS:** None identified. The implementation is structurally sound and all tests pass.

**RECOMMENDED CLAUDE ACTION:** Review and integrate. The next task is wiring a paid route into `gather`, which needs the idempotency contract from `src/ratelimit.py`.
