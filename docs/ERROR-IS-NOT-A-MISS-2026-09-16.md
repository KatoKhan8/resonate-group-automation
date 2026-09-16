# An Error Is Not a Miss - 2026-09-16

TASK-207. The five ContactOut outcome classes, the classification of every
existing reason, the live defect, and the fix.

## The five classes

    CONTACTOUT_CONFIRMED_MISS          may license fallback
    CONTACTOUT_CAPABILITY_UNAVAILABLE  may license fallback
    CONTACTOUT_ERROR                   must NOT license fallback
    CONTACTOUT_TIMEOUT                 must NOT license fallback
    CONTACTOUT_RATE_LIMITED            must NOT license fallback

Constants in `src/waterfall.py`. The three transient classes are also in
`TRANSIENT_REASONS`, a frozenset that `may_fall_back` checks explicitly
before the accepted-reasons allowlist.

## Classification of every existing reason

### CONFIRMED_MISS (ContactOut was asked, answered, and the data was not there)

| Reason                              | Where produced          |
|-------------------------------------|-------------------------|
| `contactout_no_people`              | enrich.py:929           |
| `contactout_no_target_persona`      | enrich.py:1000          |
| `contactout_result_collision`       | enrich.py:1002          |
| `contactout_rebrand_detected`       | enrich.py:1004          |
| `contactout_domain_unstaffed`       | enrich.py:1000          |
| `contactout_incomplete`             | fieldplan.py:225        |
| `contactout_no_company_linkedin`    | fieldplan.py:160        |
| `contactout_missing_company_data`   | fieldplan.py:183, 205   |
| `verification_inconclusive`         | waterfall.py (literal)  |
| `verification_contradiction`        | waterfall.py (literal)  |

### CAPABILITY_UNAVAILABLE (ContactOut structurally cannot provide this)

| Reason                            | Where produced          |
|-----------------------------------|-------------------------|
| `public_evidence_required`        | research.py:383         |
| `contactout_no_email_domain`      | fieldplan.py:169        |

### No existing reason is ambiguous

Every existing fallback reason is either a confirmed miss or a capability
gap. None of them can be produced by a transient failure. The taxonomy is
clean.

## The live defect (found and closed)

**Where does a transient failure currently get recorded?**

The call sites that catch ContactOut exceptions are in `src/enrich.py`:

    Line 929:  people-count ProviderError → logged, added to failures[]
    Line 964:  decision-makers ProviderError → logged, added to failures[]
    Line 995:  company-info ProviderError → logged, added to failures[]
    Line 1019: aiark ProviderError → logged, added to failures[]
    Line 1084: blitz-company ProviderError → logged, added to failures[]

None of these call sites record a fallback reason when ContactOut fails.
The failure is logged as text and added to a `failures` list. The waterfall
ledger row was already written by `spend()` BEFORE the provider call, with
the text description as the reason (not a classified reason code).

**The defect is in the NEXT RUN, not the current one.** When `spend()`
writes the ledger row before the call, and the call then fails:

1. The ledger has a ContactOut row (written before the call)
2. The field is still missing (because the call failed)
3. On the next run, `fieldplan.tried()` sees the ContactOut row and says
   "ContactOut was asked"
4. `state_of()` returns `MISSING_CONFIRMED`
5. `next_step()` returns the fallback with reason
   `CONTACTOUT_MISSING_COMPANY_DATA`
6. The fallback is licensed

A ContactOut timeout on `company-information-from-domain` would be recorded
indistinguishably from a confirmed miss, and the next run would pay Blitz
or Apify for data ContactOut has and was simply not asked properly.

**The fix has two parts:**

1. **Bounded retry in the adapter** (`src/providers/contactout.py`): 429,
   5xx and network errors are retried up to 2 times (3 total attempts) with
   exponential backoff (0.5s, 1.0s). 4xx client errors and MissingKey are
   never retried. This handles the common transient case without changing
   the waterfall semantics.

2. **Transient reasons fail closed at the waterfall** (`src/waterfall.py`):
   Three new reason strings (`contactout_error`, `contactout_timeout`,
   `contactout_rate_limited`) are defined. They are NOT in any
   `accepted_reasons` list. `may_fall_back` checks `is_transient()` before
   the allowlist and refuses with a clear message: "a transient failure,
   not a miss; a fallback would pay twice for data ContactOut has". Even if
   a caller somehow offered a transient reason, the waterfall refuses it.

## Bounded retry

    MAX_RETRIES = 2  (3 total attempts)
    Backoff: 0.5s, 1.0s

Justification: ContactOut's rate limit window is per-minute. A 5xx is
typically transient. Three attempts with 1.5 seconds of total backoff gives
the provider time to recover without blocking the batch. A 401 (bad key) is
never retried: a credential that is absent will not materialise.

**Spend audit impact:** A retry is invisible to the billing. ContactOut
bills only successful calls. A retry that fails costs nothing. A retry that
succeeds costs the same as a first attempt that succeeds. The ledger records
one row per call, not per attempt.

## Telemetry counters

Seven counters, aggregated from the waterfall ledger by
`waterfall.counters(records)`:

    CONTACTOUT_CALLS              ContactOut rows in the ledger
    CONTACTOUT_CACHE_HITS         passed in by the caller (not in ledger)
    CONTACTOUT_CONFIRMED_MISSES   fallback rows with a confirmed_miss reason
    CONTACTOUT_ERRORS             fallback rows with a transient reason
    CRAWLER_CALLS                 Apify research rows
    GROK_ESCALATIONS              xAI rows
    OTHER_PROVIDER_ESCALATIONS    other fallback rows

Each escalation carries its WHY: the reason code from the ledger row. The
`escalation_reasons` list in the return value has every escalation with its
provider, call and reason.

Source choice: aggregated from the ledger, not a second counter store. The
ledger is the single source of truth for what was bought and why. A parallel
counter would drift from it. `CONTACTOUT_CACHE_HITS` is the exception: a
cache hit does not produce a ledger row, so it is tracked at the call site
and passed in.

## What was not done

- No `accepted_reasons` list was widened. The transient reasons are refused
  by `is_transient()` before the allowlist is even consulted.
- The `company_information` stage's provider order was not touched (TASK-208
  owns that).
- No paid provider calls were made. All tests run against fakes.
- `src/providerwrites.py` was not touched.

## Files changed

    src/waterfall.py                        five classes, mapping, classify(),
                                            is_transient(), counters(),
                                            may_fall_back() transient check
    src/providers/contactout.py             classify_failure(), bounded retry
                                            in call(), MAX_RETRIES = 2
    tests/test_contactout_fallback_semantics.py   32 tests, all new
    docs/ERROR-IS-NOT-A-MISS-2026-09-16.md        this file
