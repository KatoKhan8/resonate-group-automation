# TASK-239 · The 459 accounts that carry no contact

PRIORITY: P1
DEPENDS: TASK-238
OWNER: qwen
CHANNEL: enrichment

## THE NUMBER THAT MATTERS

Measured 2026-09-21 by `scripts/funnel_truth.py`:

    accounts in queue                550
    with an ICP verdict              550   (113 qualified, 222 rejected,
                                            215 review)
    with >= 1 contact                 91
    ACCOUNTS CARRYING NO CONTACT     459   - 83% of the estate
    contacts (decision makers)       277   (240 with an email, 68 SENDABLE,
                                            69 email-verified)

**83% of the estate has no decision maker attached.** That is the first big
drop in the funnel and it is the constraint on cohort size - not approval,
not sender capacity. `docs/THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED-2026-09-18.md`
says expansion is a sourcing problem; this task is the sourcing.

## SCOPE - and read this before choosing the input set

The 459 are not one population. Split them before spending a credit:

- **Accounts whose ICP verdict is `qualified`** are the ones worth a paid
  call. Enrich these FIRST.
- **The 215 at `review`** are an enrichment task, not a human backlog -
  REFUTED-002 in `docs/state/PROBLEM-REGISTER.md`, and it has been carried as
  an operator action in three consecutive handoffs while being nothing of the
  kind. Zero of the 215 have any criterion at `fail`, 184 hold no company
  evidence at all. They need evidence, then re-qualification. Enrich these
  SECOND and report how many reach a verdict.
- **The 222 `rejected`** are out of scope. Do not spend on them.

## PROVIDER ORDER - it is a standing policy, not your choice

`PROVIDER-ROUTING-POLICY.md`, set by the operator 2026-09-16, and
`src/waterfall.py` already encodes most of it. Read `waterfall.describe()`
before changing anything there.

    ContactOut first whenever capable
    -> its cache
    -> the free crawler
    -> Grok
    -> other paid providers (AI Ark, BlizAPI)
    -> Claude

**AI Ark and BlizAPI are for MISSING FIELDS ONLY.** They are not a second
opinion and not a fallback for a field ContactOut already answered. A record
that has an email does not get an AI Ark email.

**The free crawler now actually runs.** TASK-214 merged today (`e197f0b5`):
the free leg used to sit below `if not live: return []` and had zero callers,
so every cost measurement that read the waterfall ledger was wrong about it.
It is in the path now, it is free, and a site it reads never reaches the paid
leg. Do not re-derive this.

Budget: ContactOut had ~36,679 credits and ~117,419 searches remaining on
2026-09-20. The variable is `CONTACTOUT_TOKEN` - from `config.VARIABLES`,
never guessed. `docs/THE-CREDENTIAL-WAS-THERE-ALL-ALONG-2026-09-20.md` is why
that sentence is here.

## REQUIREMENTS

1. **Bounded concurrency.** `src/ratelimit.py` carries the measured limits,
   including `CONTACTOUT_PEOPLE_COUNT` at 1,038/min classified OBSERVED with
   its date. Operate the ContactOut route at **K=8**: scaling is 7.98x there
   and 8.23x at K=12, so the last four threads buy 3% and nearly double
   `max` latency. Do not raise a limit to go faster.
2. **PARTIAL RESULTS PERSISTED.** A crash at account 300 must not lose 299.
   Write incrementally; the pass must be resumable and must not re-spend on
   an account already enriched. This is the single most important requirement
   in this task - a 459-account run that loses its work is worse than no run.
3. **SPEND CAPPED AND REPORTED PER 100 ACCOUNTS.** Take an explicit `--cap`.
   There is precedent for refusing without one: an uncapped walk of the whole
   queue is hundreds of thousands of credits, and the suite already has a
   REFUSED message saying so. Report credits consumed, calls made and useful
   records produced per 100, so cost per useful lead is measurable rather
   than assumed.
4. **USE EXISTING EVIDENCE FIRST.** Do not pay for a field already held.
   Check the cache and the crawl cache before any paid call.
5. **NO PII IN GIT.** Hash record ids and domains in anything committed.
   The cohort itself stays in gitignored `work/`.
6. **NO PROVIDER WRITES.** Enrichment reads. No campaign, no lead add, no
   send, on either provider.
7. **NO GATE WEAKENED.** Not a criterion, not a threshold, not a verification
   rule, not a suppression check - to make a number look better.

## OUTPUT - the deliverable is a delta, not a report

    READY RESERVOIR DELTA, per channel

    email     before  68 sendable / 69 verified   after  ...
    linkedin  before  ...                          after  ...

    accounts processed        ...
    accounts gaining >=1 contact  ...
    contacts discovered       ...
    contacts with an email    ...
    contacts email-VERIFIED   ...   (verified is the gate, not found)
    of the 215 review: reaching a verdict  ...

    credits consumed          ...   per 100 accounts: ...
    cost per useful lead      ...
    wall clock                ...

A contact found is not a contact verified, and only verified reaches READY.
Report both and never conflate them.

## FILES ALLOWED

    scripts/task239_*.py      new
    src/enrich.py  src/waterfall.py   only if a change is REQUIRED, and say why
    tests/test_task239_*.py   new

## FILES FORBIDDEN

    src/icp.py   src/icpstructural.py   config/
    anything under `src/providerwrites.py` or `src/executionguard.py`

## ACCEPTANCE

Tests with the transport stubbed proving: resume after an interrupt re-spends
nothing; the cap is honoured exactly; a paid provider is not called for a
field already held; AI Ark/BlizAPI are not called for a field ContactOut
answered; and a provider error leaves the record resumable rather than
consumed.
