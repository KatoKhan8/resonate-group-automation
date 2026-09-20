# Two thirds of all spend is one call, and the model lane is not on the ledger

Measured 2026-09-20 from `work/spend-ledger.jsonl` — 1,320 rows, every paid
call this system has made. Not modelled, not projected.

## The whole bill

    contactout   decision-makers                   1320 credits   64.7%
    blitz        blitz-company                      232 credits   11.4%
    contactout   company-information-from-domain    145 credits    7.1%
    contactout   email-verifier                      97 credits    4.8%
    reoon        reoon-verify                        97 credits    4.8%
    deliverable  deliverable-verify                  79 credits    3.9%
    aiark        aiark-people-search                 70 credits    3.4%
    ------------------------------------------------------------------
    TOTAL                                          2040 credits
    over 1,320 calls, of which 503 (38%) were free

## Cost per outcome

    accounts in the queue              550
    COST_PER_PROCESSED_ACCOUNT        3.71 credits
    ALREADY_LIVE contact-channel        18
    COST_PER_LIVE_LEAD               113.3 credits
    READY_NOW                            0
    COST_PER_READY_LEAD              UNDEFINED, and that is the real answer

`COST_PER_READY_LEAD` has no denominator because READY_NOW is zero on both
channels. Reporting a number here would require inventing one. The honest
statement is that **2,040 credits have produced 18 live contact-channel pairs
and 7 more that a human approval would convert**, and everything else is
blocked at the account gate by the client's own campaigns
(`WRITING-THE-MISSING-COPY-WOULD-UNLOCK-NOBODY-2026-09-20.md`).

## The one lever worth pulling

**`decision-makers` is 132 calls and 1,320 credits — 65% of everything
spent.** At 10 credits a call it is two orders of magnitude more expensive
than anything else on the list, and `people-count`, which is FREE, was called
250 times.

That is where a cost programme starts, and the shape of the fix is already
in `PROVIDER-ROUTING-POLICY.md`: existing evidence before a paid call, and
the cheapest capable provider first. What is NOT yet measured is the YIELD -
how many of those 132 calls returned a decision-maker this system went on to
use. Cost per call is on the ledger; cost per USEFUL result is not, because
the ledger records the call and not its outcome.

**That is the next measurement, and it should come before any optimisation.**
A cheaper provider that halves the yield is more expensive per useful result,
and this ledger cannot currently tell the difference.

## Two holes in the ledger itself

**The model lane spends real money and writes no row.** `src/llm.py`'s
`OpenAICompatibleModel` bills per record; `src/aispendledger.py` was designed
and never built. CLAUDE.md states "every paid call goes through enrich's
`spend()`, which writes the waterfall ledger" — that has an undocumented
exception, and it is the lane whose usage grows fastest as cohorts scale.
So the 2,040 credits above are PROVIDER credits and the true bill is higher
by an unmeasured amount.

**Apify records 253 calls at zero expected cost.** Apify bills in compute
units rather than credits, so `expected_cost: 0` is the ledger saying "this
is not denominated in credits" rather than "this was free". 253 calls is 19%
of all traffic and its cost is currently invisible.

## Cross-checked against the audit

`spendledger.check` re-reads the whole ledger on every paid call - O(n²)
over a run. The Buggie panel MEASURED it rather than assuming: 4.6ms at
today's 1,320 rows, ~0.1% of run time, break-even around 9,000 domains and
12.2 hours at 30,000. **A scaling boundary for the 100k phase, not a present
defect**, and it is recorded here so it is not "fixed" ahead of the 65% item.

`spendledger.record` appends with a bare `open(path, "a")` and no lock, on a
platform where this repository has now measured twice that concurrent appends
LOSE LINES - 2,400 expected / 2,193 parsed, and 240 expected / 193 present in
`watchsink`'s own test. The live file already has mixed CRLF and LF, which is
two different writers. **So the 2,040 figure is a floor, not a count.**

## Classification

    2040 credits over 1320 calls                MEASURED, from the ledger
    decision-makers is 64.7% of spend           MEASURED
    3.71 credits per processed account          MEASURED
    113.3 credits per live lead                 MEASURED
    cost per READY lead                         UNDEFINED - no denominator
    yield per decision-makers call              UNMEASURED - the ledger
                                                records calls, not outcomes
    model-lane spend                            UNMEASURED - no ledger exists
    apify spend                                 UNMEASURED - not in credits
    the ledger under-counts concurrent appends  MEASURED twice, on this
                                                platform, in this repository
