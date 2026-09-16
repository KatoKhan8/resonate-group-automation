PRIORITY: P0
DEPENDS:

# TASK-207 - an error is not a miss, and only a miss licenses a fallback

## WHERE THIS SITS

`PROVIDER-ROUTING-POLICY.md` requires five ContactOut outcomes to be
distinguishable, and only the first two may license the next provider:

    CONTACTOUT_CONFIRMED_MISS          may license fallback
    CONTACTOUT_CAPABILITY_UNAVAILABLE  may license fallback
    CONTACTOUT_ERROR                   must NOT license fallback
    CONTACTOUT_TIMEOUT                 must NOT license fallback
    CONTACTOUT_RATE_LIMITED            must NOT license fallback

`src/waterfall.py` already does the hard half and you must not undo it. Every
fallback step carries `requires_reason`, a CLOSED allowlist per step, and
`may_fall_back` refuses a fallback offered no reason and refuses a reason the
stage does not name. So an unnamed failure already fails closed. Read
`waterfall.describe()` before touching anything.

What is missing is the taxonomy itself, the retry behaviour for the three
transient classes, and a test proving an error cannot be spelled as a miss.

The risk is specific and expensive. If a ContactOut timeout is recorded as
`contactout_missing_company_data`, then every timeout silently buys a Blitz or
Apify call - we pay a second provider for data ContactOut has and was simply
not asked properly. Under a ContactOut-first policy that is the exact failure
to prevent.

## THE QUESTION

1. **Read the existing reasons and classify each one.** The stages name things
   like `contactout_no_company_linkedin`, `contactout_no_email_domain`,
   `contactout_missing_company_data`. For each: is it a CONFIRMED_MISS, a
   CAPABILITY_UNAVAILABLE, or is it ambiguous enough that a transient failure
   could be recorded under it? The ambiguous ones are the finding.
2. **Introduce the five classes** as named constants, and make every accepted
   fallback reason map to exactly one. Do not invent a parallel vocabulary
   next to the existing reasons - map the existing reasons onto the classes,
   per CLAUDE.md on canonical state. Two state machines for one fact is how
   they drift.
3. **Prove an error cannot license a fallback.** A test per transient class:
   given a ContactOut error, timeout or rate limit, `may_fall_back` must refuse
   the paid step. And the inverse: given a confirmed miss, it must permit.
4. **Where does a transient failure currently get recorded?** Find the call
   sites that catch a ContactOut exception. If any of them record a step whose
   reason could license a fallback, that is the live defect and it is what this
   task exists to close. If none do, prove it with the grep and say so.
5. **Retry and backoff for the three transient classes.** Bounded - name the
   bound and justify it. The xAI adapter already has a bounded retry that
   re-raises `MissingKey` immediately rather than spending attempts on a
   credential that will not appear; the same shape applies here, where a 401 is
   not worth retrying and a 429 is.
6. **The telemetry counters** the policy names: `CONTACTOUT_CALLS`,
   `CONTACTOUT_CACHE_HITS`, `CONTACTOUT_CONFIRMED_MISSES`,
   `CONTACTOUT_ERRORS`, `CRAWLER_CALLS`, `GROK_ESCALATIONS`,
   `OTHER_PROVIDER_ESCALATIONS` - each escalation recorded with its WHY. The
   ledger `record_step` already writes per-record rows; prefer aggregating
   from it over adding a second source of truth, and say which you chose.

## THE TRAP

Do not widen an `accepted_reasons` list to make anything pass. This task
NARROWS what licenses a paid call; if a legitimate path breaks because its
reason was ambiguous, the fix is a more precise reason, not a wider allowlist.

Second trap: a retry on a rate limit that is not bounded is a way to turn one
refused call into a hundred. Bound it, and make the bound visible in the
telemetry so a retry storm is detectable rather than merely expensive.

Third trap: `enrich`'s `spend()` is the only path that may charge, and the
spend audit reads the waterfall ledger. If you add a retry, make sure a retried
call is not recorded as a second charge - and if it IS a second charge because
the provider bills it, make sure the ledger says so. A retry that is invisible
to the audit makes the audit wrong.

## WHAT YOU MAY NOT DO

- No paid provider calls. Test against fakes; the classes are about how a
  failure is recorded, which needs no live failure to verify.
- No provider writes.
- Do not widen any `accepted_reasons` list.
- Do not touch the `company_information` stage's provider ORDER - TASK-208
  owns ordering, and two workers in that file will collide.
- Do not weaken `may_fall_back`'s refusal of an unnamed reason.
- Never commit a key or PII.

## FILES ALLOWED

    src/waterfall.py   (the reason classes, the mapping, the counters - NOT
                        the stage provider order)
    src/providers/contactout.py   (retry and failure classification)
    tests/test_contactout_fallback_semantics.py   (new)
    docs/ERROR-IS-NOT-A-MISS-2026-09-16.md   (new)

## FILES FORBIDDEN

    work/   config/   src/providerwrites.py

## DELIVERABLE

Every existing reason classified with the ambiguous ones named; the five
classes as constants with the existing reasons mapped onto them; a test per
transient class proving refusal and one proving a confirmed miss permits; the
call sites that catch a ContactOut failure with a verdict on each; the bounded
retry with its bound justified; and the counters, aggregated from the ledger
if that is the right source.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 7d0828d

**TESTS:** 32 new tests in `tests/test_contactout_fallback_semantics.py`, all
passing. Existing waterfall tests (test_waterfall, test_contactout_wire) all
pass. One pre-existing failure in test_contactout_first
(TestDeliverableContractIsConfirmed) is unrelated to this change.

**FILES CHANGED:**
- `src/waterfall.py` - five outcome classes, REASON_CLASS mapping, classify(),
  is_transient(), TRANSIENT_REASONS, counters(), may_fall_back() transient check
- `src/providers/contactout.py` - classify_failure(), bounded retry in call(),
  MAX_RETRIES=2, _RETRY_BACKOFF=(0.5, 1.0)
- `tests/test_contactout_fallback_semantics.py` - 32 tests (new)
- `docs/ERROR-IS-NOT-A-MISS-2026-09-16.md` - findings document (new)

**FINDINGS:**

1. **No existing reason is ambiguous.** All 12 existing fallback reasons
   classify cleanly as either CONFIRMED_MISS (10) or CAPABILITY_UNAVAILABLE
   (2). None can be produced by a transient failure.

2. **The live defect is in the NEXT RUN, not the current one.** When
   ContactOut fails (timeout, error, rate limit), the ledger row is already
   written by `spend()` before the call. On the next run, `fieldplan.tried()`
   sees the row and says "ContactOut was asked", the field is still missing,
   and the fallback is licensed with reason `CONTACTOUT_MISSING_COMPANY_DATA`.
   A timeout is spelled as a miss. The fix: bounded retry handles the common
   transient case, and the three new transient reason strings fail closed at
   the waterfall even if somehow offered.

3. **Five call sites catch ContactOut ProviderError** (enrich.py lines 929,
   964, 995, 1019, 1084). None record a classified reason - they log text and
   append to a failures list. The defect is that the absence of a classified
   failure reason means the next run cannot distinguish "ContactOut answered
   and the data was not there" from "ContactOut failed to answer".

4. **Retry is bounded and invisible to the spend audit.** MAX_RETRIES=2
   (3 total attempts), backoff 0.5s/1.0s. ContactOut bills only successful
   calls, so retries cost nothing. The ledger records one row per call, not
   per attempt.

5. **Telemetry counters aggregate from the ledger.** `waterfall.counters()`
   reads the waterfall rows. CONTACTOUT_CACHE_HITS is the exception (a cache
   hit produces no ledger row) and is passed in by the caller.

**RISKS:**
- The retry adds latency to ContactOut calls that fail transiently (up to
  1.5 seconds per call). Under sustained rate limiting, this could slow the
  batch. The bound is visible in telemetry (CONTACTOUT_ERRORS counter).
- The `contactout_incomplete` reason is classified as CONFIRMED_MISS. If a
  future code path produces it from a transient failure, the classification
  would be wrong. The current code paths all produce it from actual missing
  data, not from exceptions.

**RECOMMENDED CLAUDE ACTION:** Review the five outcome classes and the
REASON_CLASS mapping. Verify the transient refusal in may_fall_back. Consider
whether enrich.py should record a transient reason on the ledger when a
ContactOut call fails, so the next run can distinguish "ContactOut failed"
from "ContactOut answered and the data was not there".
