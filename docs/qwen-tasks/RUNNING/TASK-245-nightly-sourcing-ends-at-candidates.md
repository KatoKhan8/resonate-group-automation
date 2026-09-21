# TASK-245 — nightly sourcing, and it ENDS AT CANDIDATES

OPERATOR DECISION, 2026-09-21, Zvonimir, which REPLACES the earlier
"nightly sourcing into S3 -> MX -> collision -> S4 -> S5 -> S7" instruction:

> Nightly sourcing stays, but ends at CANDIDATES: sourced -> S3 ICP ->
> S4b MX -> local collision -> candidate list. Candidates accumulate and are
> exported weekly (Monday 07:00 Zagreb) for Productive: domain, company,
> headcount, industry, country, website, why it matched, prior-touch status.
> Nothing else is spent on them.

**"NOTHING ELSE IS SPENT ON THEM" IS THE POINT OF THIS TASK.** A candidate
that reaches S4 persona discovery or S5 verification before Productive has
approved its account costs credits on an account the client may reject. The
pipeline STOPS at the candidate list. If you find yourself calling a people
endpoint or a verifier, you have built the wrong thing.

## WHAT RUNS NIGHTLY — 02:00 Europe/Zagreb

    1  AI-ARK company search on the Productive ICP
       headcount >= 20 AND the geos APPLIED AT THE SOURCE, not filtered
       after. Filtering after is paid-for rows thrown away.
       Walk to last=true. DIFF against what we hold; NEVER delete.
    2  S3 ICP verdict
    3  S4b MX classification
       known_allowed and unknown_provider survive. known_blocked, no_mx and
       dns_failure do not - dns_failure is HELD, we could not ask, which is
       not the same fact as no mail.
    4  LOCAL collision only - work/stage/last-touch.json and the store.
       No provider walk. The index is persisted and must be KEPT CURRENT,
       never re-walked: scheduled_emails(352) is 96,045 rows over 6,403
       pages and the adapter correctly refuses to return a partial.
    5  append to the candidate list. Accumulating, de-duplicated by domain,
       and it records WHEN and WHY each row arrived.

## THE WEEKLY EXPORT — Monday 07:00 Europe/Zagreb

Columns, exactly these, in this order:

    domain · company · headcount · industry · country · website ·
    why it matched · prior-touch status

"why it matched" is the ICP evidence that produced the IN verdict, in words a
client can read. "prior-touch status" comes from the local collision walk:
never touched / touched <date> / has_reply / bounced / unsubscribed.

The export is the input to TASK-244's approval intake. Write it so that task's
sheet writer and Slack poster can both consume it without reshaping it.

## DST, AND IT BITES IN FIVE WEEKS

DIGEST_HOUR moves 5 -> 6 UTC on 2026-10-25 when Zagreb leaves DST. Both
schedules here are stated in Zagreb time and both must move with it. Do not
hardcode a UTC hour: ask geo for the window. senderheadroom counted weekdays
from 0 in an ISO repo and read Mon-Fri as Tue-Saturday (F-004).

## COST DISCIPLINE

Credit spend is REPORTED, NEVER GATED - no cap, no balance pause. A rate
limit means back off and continue, never halt. Report per run: rows sourced,
credits spent, credits per surviving candidate.

/domain/enrich costs nothing measurable - 24,404 domains moved the search
meter by zero - and returns ALL 30 domains per call. One call per domain is
6.8 hours; batched it is fourteen minutes. Do not re-derive this.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test name both directions. Every AI-ARK call faked in
tests. One test proves the pipeline REFUSES to advance a candidate past the
candidate list. One test proves a rejected-then-resourced domain does not
reappear as new.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
