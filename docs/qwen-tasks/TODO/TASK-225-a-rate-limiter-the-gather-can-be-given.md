# TASK-225 - a rate limiter the bounded gather can be given

## Why now

`docs/PERF-LATENCY-MODEL-2026-09-18.md` puts provider wait at 98.2-99.7% of a
real 5,000-record pass. Measured 2026-09-18, ContactOut `people-count` p50 is
**0.425s** against the model's assumed MID of 0.2s - the dominant call by
count is 112% slower than assumed, so the case for concurrency got stronger,
not weaker. `src/gather.py` already provides bounded concurrency with serial
decide / concurrent fetch / serial apply IN INPUT ORDER.

What it has no answer for is the provider's own limit. Raising K without one
converts latency into 429s.

## The objective

A rate limiter primitive, with NO caller, that `gather` can later be given.

    src/ratelimit.py

Falsifiable requirements:

1. A token-bucket or equivalent admitting at most N operations per window,
   shared across threads, with a `wait()` that blocks rather than rejects.
2. **Classified limits, never assumed.** The limiter takes its rate from a
   caller-supplied policy. Where a provider's limit is UNKNOWN the policy
   must say UNKNOWN and the limiter must fall back to the conservative
   configured default - it may NOT treat unknown as unlimited. The enrichment
   providers that dominate the call count have UNKNOWN limits, and
   EmailBison's 3,000 rpm is MARKETING (a features page, not the API
   reference); encode both facts as data, with the classification beside
   each number.
3. Retry with exponential backoff and jitter on 429 and on 5xx, bounded
   attempts, and **honour `Retry-After` when the response carries it**.
4. **IDEMPOTENCY IS THE CALLER'S PROBLEM AND THE MODULE MUST SAY SO.** A
   retried POST is a second write. The module refuses to retry a
   non-idempotent verb unless the caller passes an explicit idempotency
   assertion.
5. Thread-safe. Prove it: a test with 8 threads and a limit of 5/second must
   observe no window exceeding 5, and must FAIL if the lock is removed.

## What this must NOT do

- No caller. Do not wire it into `gather`, `enrich` or any provider module.
- Do not touch the shared `Budget` cap, the waterfall ledger append order,
  the `new_accounts_per_day` reservation lock, or checkpoint ordering.
  Section 7 of `docs/PRODUCTION-HANDOFF-2026-09-18.md` names these as the
  things that cannot be parallelised; this task does not attempt them.
- No provider write. No credit spend. Tests use fakes.

## Tests required

Rate held under concurrency; backoff honours Retry-After; unknown-limit falls
back conservatively; non-idempotent verb refuses retry without the assertion;
break-proof the lock and confirm the concurrency test fails for the intended
reason.
