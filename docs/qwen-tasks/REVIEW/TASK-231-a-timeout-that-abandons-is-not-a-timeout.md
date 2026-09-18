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

**COMMIT SHA:** daf1c706

**TESTS:**
- `tests/test_http_timeout_aborts_at_socket_layer.py`: 19 tests, all pass
  - Server-side close assertion: the never-answering server observed the
    socket close (recv returned b''), proving the request was ABORTED, not
    merely abandoned.
  - Exception classification: HttpTimeout (TimeoutError), HttpTransportError
    (ProviderError), 4xx returned as status, 5xx returned as status.
  - gather recognizes TimeoutError from callable as timed_out.
  - Break-proof: 0.3s timeout fires, 60s timeout does not - same server.
  - gather and prefetch_headcount signatures have no timeout parameter.
  - Honesty caveat documented in HttpTimeout and gather docstrings.
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`:
  41 tests, all pass.
- `tests/test_prefetch_headcount.py`: 20 tests, all pass. Ledger-equality
  tests pass byte-identically.
- `tests/test_enrich.py`: 49 tests, all pass.
- `tests/test_invariants.py`: 83 tests, 1 pre-existing failure
  (test_emailbison_posts_only_to_routes_it_declares - unrelated to this task,
  confirmed by running against stashed state).

**FILES CHANGED:**
- `src/providers/__init__.py`: added HttpTimeout(TimeoutError) and
  HttpTransportError(ProviderError). Modified _urllib_transport to raise
  classified exceptions.
- `src/gather.py`: removed timeout parameter from gather() and
  prefetch_headcount(). Removed _CallableTimeoutError. TimeoutError from
  callable produces Outcome.timed_out(). Updated docstrings.
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`:
  updated Timeout tests to raise TimeoutError instead of sleeping.
- `tests/test_prefetch_headcount.py`: updated _run_serial and timeout tests.
- `tests/test_http_timeout_aborts_at_socket_layer.py`: new file, 19 tests.

**FINDINGS:**

1. **What was achieved: WE stopped waiting.** The HTTP layer aborts the
   socket when the timeout expires. The server-side test proves the server
   observed the connection close (recv returned b''). This is the honest
   achievement: we stopped waiting.

2. **What was NOT achieved: the server stopped working.** Aborting the
   socket does NOT prove the server stopped processing. For a GET, this
   distinction costs nothing. For a paid POST, it is the whole question:
   the request may have been received and processed before the socket
   closed. The report states this explicitly rather than implying the
   stronger claim.

3. **No paid route was wired into gather.** This was a prerequisite task.
   Wiring a paid route needs the idempotency contract from src/ratelimit.py
   as a separate task.

4. **The people-count prefetch keeps working unchanged.** The ledger-
   equality test passes byte-identically. The timeout behavior is now
   enforced at the HTTP layer, and the callable raises TimeoutError
   (including HttpTimeout from the transport) which gather classifies as
   timed_out.

5. **Break-proof confirmed.** Raising the HTTP timeout from 0.3s to 60s
   makes the abort test fail (no HttpTimeout raised), proving the abort
   test actually depends on the timeout deadline.

**RISKS:**
- On some platforms/ports, a recently-closed port may timeout instead of
  refusing connections. The exception hierarchy distinguishes HttpTimeout
  from HttpTransportError regardless of which one fires, so a retry policy
  can classify them correctly.
- The connection-refused test is platform-dependent and accepts either
  HttpTimeout or HttpTransportError/OSError, since the OS network stack
  behavior varies.

**RECOMMENDED CLAUDE ACTION:**
Review and integrate. The next task is to wire a paid route into gather,
which needs the idempotency contract from src/ratelimit.py.
