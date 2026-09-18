# TASK-225: A rate limiter the gather can be given

## FILES ALLOWED
- src/ratelimit.py (NEW)
- tests/test_ratelimit.py (NEW)

## FILES FORBIDDEN
- src/gather.py, src/enrich.py, any provider module
- src/enrich.py Budget class, spendledger, waterfall ledger

## TASK
Build src/ratelimit.py: a thread-safe token bucket with blocking wait(),
exponential backoff with jitter on 429 and 5xx, honouring Retry-After.

### FIRST priority: UNKNOWN provider limits
An UNKNOWN provider limit must fall back to the conservative configured
default and must NEVER be treated as unlimited. Most enrichment providers
here have UNKNOWN limits and EmailBison's 3000 rpm is a MARKETING page not
an API reference. Encode the classification as data next to each number.

### SECOND priority: non-idempotent retry refusal
A retried POST is a second write, so the module must REFUSE to retry a
non-idempotent verb unless the caller passes an explicit idempotency
assertion.

## VERIFICATION
- 8 threads against limit of 5/second
- Break-proof: remove the lock, confirm test fails for intended reason, restore
- No provider calls - tests use fakes

## RESULT
- STATUS: DONE
- COMMIT SHA: cf58aed
- TESTS: 52/52 pass in tests.test_ratelimit; 80/80 pass in tests.test_invariants
- FILES CHANGED: src/ratelimit.py (NEW), tests/test_ratelimit.py (NEW)
- FINDINGS:
  - UNKNOWN provider limits fall back to DEFAULT_LIMIT (5/min), never treated
    as unlimited. LimitClassification enum encodes provenance as data.
  - EmailBison 3000rpm encoded as MARKETING_PAGE, not CONFIRMED.
  - POST/PUT/PATCH refused on retry without explicit idempotency_key.
    NonIdempotentRetry raised with message naming "second write".
  - Thread safety proven: 8 threads vs 5/s bucket stays within bounds.
  - Break-proof: 1 token + 8 threads = exactly 1 succeeds with lock.
    Unsafe bucket (no lock, widened race window) allows >1 to succeed.
  - Retry-After header parsed (integer seconds and HTTP-date), honoured
    as floor on exponential backoff.
- RISKS:
  - No wiring to gather.py or any provider module (per task instructions).
    Claude must wire the bucket into the gather loop.
  - DEFAULT_LIMIT of 5/min is conservative; a provider with a real limit
    below 5/min would need a separate floor. None documented here is.
  - Break-proof race test depends on timing; the widened race window
    (10ms sleep between check and consume) makes it reliable on this
    machine but is not guaranteed on all hardware.
- RECOMMENDED CLAUDE ACTION:
  - Wire TokenBucket into src/gather.py's provider call loop.
  - Each provider gets its own bucket, constructed from its declared
    limit with classification. UNKNOWN limits get the floor.
  - POST calls to providers need idempotency_key from the caller.
  - Do NOT change the Budget cap or waterfall ledger append order.
