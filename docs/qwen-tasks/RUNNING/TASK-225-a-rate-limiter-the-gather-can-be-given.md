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
- COMMIT SHA: (pending)
- TESTS: (pending)
- FILES CHANGED: src/ratelimit.py, tests/test_ratelimit.py
- FINDINGS: (pending)
- RISKS: (pending)
- RECOMMENDED CLAUDE ACTION: (pending)
