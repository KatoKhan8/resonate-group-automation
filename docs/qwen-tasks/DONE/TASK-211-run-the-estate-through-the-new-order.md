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

## RESULT

**STATUS:** DONE (analysis only - the run is owed from Claude's worktree)

**COMMIT SHA:** 9ec2367

**TESTS:** 53 tests in test_waterfall_order, test_crawl_cache,
test_contactout_fallback_semantics - all green.

**FILES CHANGED:**
- `docs/NEW-ORDER-RUN-2026-09-16.md` (new) - full analysis report
- `scripts/task211_analyze_free_legs.py` (new) - read-only analysis script
- Task file moved TODO/ -> RUNNING/

**FINDINGS:**

1. **BOUNDARY: the run did not execute.** QWEN.md forbids writing to
   `work/queue.jsonl` from this worktree. The queue here (300 records) is a
   stale copy; production has 550. Running here would write to an isolated
   copy that never reaches production. The actual run is owed from Claude's
   worktree.

2. **Per-leg yield (from existing data):**
   - ContactOut cache: 90 of 99 queued records already have a ContactOut
     waterfall row. Re-running would skip the call (cache hit). 57 have
     some data already.
   - Webfetch crawl: ZERO records have a webfetch waterfall row. The new
     free crawl has never been exercised. 53 queued records would benefit
     (23 without any research + 30 with incomplete fields).

3. **Unresolved records grouped by reason:**
   - 32 too_small: FAIL-CLOSED, no provider can fix
   - 10 geo_excluded: FAIL-CLOSED, client constraint
   - 33 missing_all_three (industry/offices/employees): webfetch crawl (FREE)
     then ContactOut company-info (1 credit)
   - 4 missing_offices_only: same path
   - 2 missing_industry_only: same path
   - 18 has_facts_needs_qualify: needs qualify re-run, no provider call

4. **Spend proven zero:** No `work/spend-ledger.jsonl` exists in this
   worktree. The `actual_cost` of 185 on waterfall rows is historical from
   blitz/blitz-company in previous production runs. `spendledger.record()`
   calls `refuse_production_write()` which would refuse any attempt from
   here. Zero paid calls originated from this worktree.

5. **Crawl cache:** Implemented in `src/research.py` (lines 38-53), cleared
   at start of `enrich.run()` (line 1348), used by `_from_the_site_itself()`
   (line 270). NOT exercised in any production run (zero webfetch rows).
   14 multi-contact records exist (13 with 2 contacts, 1 with 3). Expected
   behavior: 14 crawls max, not 29.

6. **Flag semantics (--limit, --lane, --cap):** TASK-181 fixed both.
   `--limit N` now bounds records processed (not scanned). `--lane` scopes
   every stage. `--cap 0` refuses all paid calls - the correct bound for
   a free-leg run.

7. **Concurrent writer check:** No lock files in work/. This worktree is
   isolated from Claude's. The approval scripts and canary path are live
   against the same files but in a different worktree.

**RISKS:**
- The webfetch crawl has never been exercised in production. The first run
  is the moment to discover teething issues.
- This worktree's queue (300 records) is stale vs production (550). Any
  measurement here is a lower bound.
- The 18 "has_facts_needs_qualify" records need a qualify re-run, not a
  provider call. They are stuck because the qualify stage hasn't been
  re-invoked since their facts were populated.

**RECOMMENDED CLAUDE ACTION:**
1. Run the free-leg pipeline from Claude's worktree:
   `py -3 -m src.generate --cap 0 --stages company_information`
2. Re-run the analysis script against the production queue to measure
   actual yield.
3. The 18 "has_facts_needs_qualify" records need a qualify-only pass.
4. The 42 fail-closed records (32 too small + 10 geo) are done unless
   the underlying data is wrong.
