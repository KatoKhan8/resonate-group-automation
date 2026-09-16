PRIORITY: P0
DEPENDS:

# TASK-211 - run the estate through the new provider order

## WHERE THIS SITS

The waterfall changed this morning and nothing has been processed through it
yet. `company_information` now reads:

    contactout  company-information-from-domain   1 credit   PRIMARY
    webfetch    webfetch-crawl                    FREE       PRIMARY
    xai         xai-research                      fallback   needs a reason
    blitz       blitz-domain-to-linkedin          fallback   needs a reason
    blitz       blitz-linkedin-to-domain          fallback
    blitz       blitz-company                     fallback
    apify       apify-research                    fallback   LAST

That is `PROVIDER-ROUTING-POLICY.md`'s order: ContactOut first whenever
capable, its cache next, the free crawler third, Grok fourth, other paid
providers fifth. Progressive spend is unchanged - the point is not to call
every ContactOut endpoint on every domain.

The estate as it stands: 315 queued, 65 verified, 32 held, 126 dropped, 12
drafted. The last full free-path run processed 373 records for ZERO credits,
and left 314 of 316 in `review` because two criteria - geography and
company_type - had no evidence behind them.

TASK-190 measured what free sources can do for those two: 12 of 66 review
records reach `qualified` from wired free sources, 20 if the
medium-reliability ones are trusted, and only 2 of 250 from a TLD because 90%
are `.com`.

## THE QUESTION

1. **Run the free legs of the new order over the queued records** and report
   what changed. Free means: ContactOut CACHE hits and existing evidence,
   plus the `webfetch` crawl, which is now a PRIMARY step rather than sitting
   behind paid Apify. No new ContactOut credits, no Grok, no Apify, no Blitz.
2. **Report the per-leg yield.** How many records the ContactOut cache
   answered, how many the free crawl answered, how many criteria moved from
   UNKNOWN to a value, and how many records changed `icp_status`. The
   telemetry counters TASK-207 added - `CONTACTOUT_CACHE_HITS`,
   `CRAWLER_CALLS` and the rest - are the right source; say whether you read
   them or counted independently, and reconcile if the two disagree.
3. **Then the ordering question that matters for money.** For the records the
   free legs could NOT resolve, say what the next step in the order would cost
   and what it would be asked for. Do not make the call. Group them by the
   REASON they are unresolved, because a record missing a vertical and a record
   missing a country need different things and only one of them is a
   ContactOut capability.
4. **Prove no paid leg fired.** Read the spend ledger, not the run summary.
   `spent=0` in a summary line is the runner's claim about itself, and this
   repository has a documented incident of fabricated spend rows written by
   test runs that reached a paid call without isolating the store.
5. **Confirm the crawl is cached per company.** TASK-208 wired a company-level
   cache; a run over a multi-contact record should crawl once. Report the
   crawl count against the multi-contact record count.

## THE TRAP

`--limit` bounds the SCAN WINDOW rather than the work done, and `--lane` does
not scope the enrich or qualify stages at all - both measured in TASK-181, and
TASK-181 may have changed one or both since. Read what those flags do NOW
before bounding a run with them, and say what you relied on. A run bounded by a
flag that does not bound is an unbounded run.

Second trap: this writes to `work/`. Check for another live writer before
starting and say what you found - a second concurrent writer to the queue is
how state gets corrupted, and the approval scripts and the canary path are
both live against the same files today.

## WHAT YOU MAY NOT DO

- ZERO credits. No ContactOut paid call, no Apify, no Blitz, no xAI. Cache and
  free crawl only. If the runner will not restrict itself to the free legs,
  stop and report that rather than spending to find out.
- No provider writes to HeyReach or EmailBison.
- Do not move a record to `dropped`.
- Do not change the waterfall order, a criterion, a threshold or a gate.
- Never commit PII. Hash record ids and domains.

## FILES ALLOWED

    docs/NEW-ORDER-RUN-2026-09-16.md   (new)
    scripts/task211_*.py
    work/   (the run writes evidence onto records - that is the task)

## FILES FORBIDDEN

    src/   config/

## DELIVERABLE

The free-leg run with per-leg yield, the criteria and verdict movement, the
unresolved records grouped by reason with the next step's cost per group, the
spend proven zero from the ledger, and the company-level crawl count against
the multi-contact record count.
