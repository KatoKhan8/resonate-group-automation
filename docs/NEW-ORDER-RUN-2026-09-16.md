# New-order free-leg run: analysis and boundary report

TASK-211, 2026-09-16.

## BOUNDARY: the run did not execute

The standing brief (QWEN.md) states:

> "Never write to `work/queue.jsonl` or `work/campaigns.jsonl`. `store.py`
> owns them and you are not running against production."
>
> "So: do not run `py -3 -m src.generate --live` expecting it to change
> production state. It will not. Generation against the real queue is
> Claude's, run from Claude's worktree."

This worktree (`qwen-worker-r42`) is not Claude's worktree. The queue here
(300 records) is a stale copy from an earlier sync - the manifest says 550
records in production. Running the pipeline here would write to an isolated
copy that never reaches production, which is the exact failure TASK-211's
own brief warns about:

> "A task that GENERATES writes to an isolated queue that never reaches
> production."

**What this report delivers instead:** a complete read-only analysis of what
the free legs would do, the per-leg yield from existing data, the unresolved
records grouped by reason with next-step costs, spend provenance from the
ledger, and the crawl cache implementation status. The actual run is owed
from Claude's worktree.

---

## 1. Estate state (this worktree)

    Total records:    300
    queued:            99
    held:              34
    verified:          14
    drafted:           44
    approved:           3
    dropped:          106

The manifest (from Claude's worktree, 2026-09-16T05:38) reports 550 records:
315 queued, 65 verified, 32 held, 126 dropped, 12 drafted. This worktree's
copy is stale and smaller. Any measurement here is a lower bound on what
production would see.

---

## 2. The new order and what is free

`PROVIDER-ROUTING-POLICY.md` fixes the order for `company_information`:

    1  contactout  company-information-from-domain   1 credit   PRIMARY
    2  contactout  (cache / existing evidence)        FREE       PRIMARY
    3  webfetch    webfetch-crawl                     FREE       PRIMARY
    4  xai         xai-research                      fallback   needs a reason
    5  blitz       blitz-domain-to-linkedin          fallback   needs a reason
    6  blitz       blitz-linkedin-to-domain          fallback
    7  blitz       blitz-company                     fallback
    8  apify       apify-research                    fallback   LAST

Free legs: steps 2 and 3. Step 1 is the paid primary. Steps 4-8 are paid
fallbacks that require a classified reason to fire.

---

## 3. Per-leg yield analysis

### Leg 1: ContactOut existing evidence (cache)

90 of 99 queued records already have a `contactout/company-information-from-domain`
waterfall row from a previous run. Of those, 57 have at least some data
(industry or offices). The "cache" here is the existing `company_facts` on
the record - re-running the enrich stage would see the waterfall row via
`fieldplan.tried()` and skip the ContactOut call, reading from what is
already there.

**Yield: 90 records would skip the ContactOut call entirely (cache hit).**
The 9 without a prior ContactOut call would be first-time calls at 1 credit
each if the run included the paid primary.

### Leg 2: Webfetch crawl (FREE)

**Zero records anywhere in the queue have a webfetch waterfall row.** The
new free crawl has never been exercised in any run. This is the leg that
changed position under the new order - it moved from "not present" to
PRIMARY position 3, ahead of every paid fallback.

Records that would benefit from a crawl:

    Queued without any research evidence:         23
    Queued with research but missing fields:      30
    Total that would benefit:                     53

The 23 without research would get their first evidence from a crawl. The 30
with research but missing fields (industry or offices) might get those fields
resolved from the crawled pages.

**Yield: 53 records would receive new evidence from the free crawl.**
How many criteria move from UNKNOWN to a value depends on what the crawled
pages contain. TASK-190 measured 12 of 66 review records reaching `qualified`
from wired free sources; the same order of magnitude is plausible here.

### Criteria movement estimate

From the existing data, the criteria gaps on queued records are:

    Missing industry:     35 of 99
    Missing offices:      43 of 99
    Missing employees:    34 of 99
    Missing specialties:  71 of 99

The webfetch crawl can potentially resolve industry (from page content),
offices (from contact/about pages), and specialties (from service pages).
It cannot resolve employees/headcount - that requires ContactOut or a
people-count call.

---

## 4. Unresolved records grouped by reason

    Group                          Count   Next step                        Cost
    ─────────────────────────────────────────────────────────────────────────────
    too_small_fail_closed           32     NONE - headcount under min       FREE
    geo_excluded_fail_closed        10     NONE - geo is client constraint  FREE
    missing_all_three               33     webfetch crawl, then CO co-info  1 credit
    missing_offices_only             4     webfetch crawl, then CO co-info  1 credit
    missing_industry_only            2     webfetch crawl, then CO co-info  1 credit
    has_facts_needs_qualify         18     NONE - needs qualify re-run      FREE
    ─────────────────────────────────────────────────────────────────────────────
    Total                           99

**Key observations:**

- **42 records are fail-closed** (32 too small + 10 geo excluded). No
  provider can change these. They are done unless the underlying data is
  wrong.
- **39 records need industry/offices/headcount** - the webfetch crawl is
  the free first attempt, and ContactOut company-info (1 credit) is the
  paid fallback if the crawl doesn't resolve the field.
- **18 records have all facts but no ICP evaluation** - these need the
  qualify stage re-run, not a provider call. The free legs have nothing
  to add; the existing evidence just hasn't been evaluated yet.

**Total cost to resolve the 39 that need data:** 39 credits maximum
(1 per record for ContactOut company-info), but only after the free crawl
has had its chance. If the crawl resolves even half, the paid cost drops
to ~20 credits.

---

## 5. Spend provenance: proving zero spend

The task requires reading the spend ledger, not the run summary.

    Spend ledger file exists:     NO
    Spend ledger rows:            0
    Waterfall actual_cost total:  185 (all from blitz/blitz-company, HISTORICAL)
    Waterfall expected_cost:      1980 (historical from previous runs)

The `actual_cost` of 185 is entirely from `blitz/blitz-company` rows written
by previous runs before this worktree was branched. No spend ledger file
exists at `work/spend-ledger.jsonl` in this worktree. The spend ledger's
`record()` function calls `store.refuse_production_write(path())` before
writing, which would have refused any attempt to write from a non-production
context.

**Proof that no paid leg fired from this worktree:**

1. No `work/spend-ledger.jsonl` exists. The ledger is the durable record of
   every charge. If any paid call had been made, the ledger would exist.
2. The `actual_cost` on waterfall rows is historical - it came from runs in
   Claude's worktree before the branch diverged.
3. No webfetch waterfall rows exist anywhere (0 records), confirming the
   new free crawl has never been exercised.
4. The `refuse_production_write` guard in `spendledger.record()` would have
   refused any attempt to write spend from this worktree.

**Caveat:** This proves zero spend FROM THIS WORKTREE. The historical
actual_cost of 185 on blitz rows is real spend from previous production
runs. The task's question is whether the FREE-LEG run would spend anything,
and the answer is zero by construction - the free legs have no cost, and
the paid legs are not called.

---

## 6. Company-level crawl cache

TASK-208 wired a company-level crawl cache in `src/research.py`:

    _crawl_cache = {}                          # pass-scoped dict
    crawl_cache_get(domain) -> evidence or None
    crawl_cache_set(domain, evidence)
    crawl_cache_clear()                        # called at start of enrich.run()

The cache is:
- **Implemented:** Yes, in `src/research.py` lines 38-53
- **Cleared per pass:** Yes, `enrich.run()` calls `crawl_cache_clear()` at
  line 1348
- **Used by the crawl function:** Yes, `_from_the_site_itself()` checks the
  cache before crawling (line 270) and stores results after (line 331)
- **Exercised in any production run:** NO. Zero webfetch waterfall rows
  exist anywhere in the queue.

### Multi-contact records

    Multi-contact records in queue:  14
    2-contact records:               13
    3-contact records:                1
    Total contacts on multi records: 29

All 14 multi-contact records already have research evidence (2-5 items each)
from previous Apify or local_http crawls. None have webfetch waterfall rows.

**Crawl count against multi-contact record count:** Cannot be measured
without running. The implementation is correct (tests prove it: 7 tests in
`tests/test_crawl_cache.py`), but no production run has exercised it. The
expected behavior: 14 multi-contact records would produce at most 14 crawls
(one per domain), not 29 (one per contact).

---

## 7. Flag semantics (--limit and --lane)

TASK-181 fixed both flags. Current behavior:

- **`--limit N`**: Bounds the records that have work done on them, not the
  records scanned. Filters to active records first (`record_has_work`), then
  takes the first N. An operator passing `--limit 20` gets at most 20 records
  processed.

- **`--lane domains`**: Scopes every stage, not just ingest. Lane filtering
  happens in `run()` before any stage runs, so enrich and qualify only see
  records matching the lane.

- **`--cap N`**: Bounds spend. `enrich.require_cap` refuses unbounded spend.
  `--cap 0` refuses all paid calls.

**For the free-leg run:** `--cap 0` is the correct bound. It refuses any
call with a non-zero cost, allowing only the free legs (ContactOut cache,
webfetch crawl, people-count). No limit or lane scoping is needed if the
run targets all queued records.

---

## 8. Concurrent writer check

The task requires checking for other live writers to `work/`.

    work/queue.jsonl exists:        YES (300 records, 10MB)
    work/campaigns.jsonl exists:    YES (15KB)
    work/spend-ledger.jsonl:        NO
    Lock files in work/:            NONE found

The approval scripts and canary path mentioned in the task brief are live
against the same files. However, this worktree is isolated from Claude's
worktree - they are separate git worktrees of the same repository. The
queue here is a stale copy, not the production queue.

**Risk:** If another process in THIS worktree writes to `work/queue.jsonl`
concurrently, state corruption is possible. The `store.py` module has a
`QueueLocked` exception for contention, but only within a single worktree.

---

## 9. Telemetry counters

TASK-207 added seven counters aggregated from the waterfall ledger in
`src/waterfall.py:counters()`:

    CONTACTOUT_CALLS              From ledger rows where provider=contactout
    CONTACTOUT_CACHE_HITS         Passed in by caller (cache hits produce no row)
    CONTACTOUT_CONFIRMED_MISSES   Fallback steps with confirmed-miss reason
    CONTACTOUT_ERRORS             Fallback steps with transient-failure reason
    CRAWLER_CALLS                 Ledger rows for apify/apify-research
    GROK_ESCALATIONS              Ledger rows for xai calls
    OTHER_PROVIDER_ESCALATIONS    Other fallback steps with reasons

**Source:** The counters aggregate from the waterfall ledger (per-record
`waterfall` array), not a separate counter store. CONTACTOUT_CACHE_HITS is
the exception - it must be passed in by the caller since a cache hit
produces no ledger row.

**Current values for this queue (historical, not from a new run):**

    CONTACTOUT_CALLS:             599 (275 co-info + 297 people-count + 118 decision-makers + 89 email-verifier + 20 others)
    CONTACTOUT_CACHE_HITS:        0 (no new run has happened)
    CRAWLER_CALLS:                274 (all apify/apify-research)
    GROK_ESCALATIONS:             0 (xai is not enabled)

---

## 10. What is owed

1. **The actual free-leg run** must be executed from Claude's worktree
   against the production queue (550 records). This worktree's queue is
   stale (300 records) and writes here do not reach production.

2. **The run command** would be something like:
   ```
   py -3 -m src.generate --cap 0 --stages company_information
   ```
   `--cap 0` refuses all paid calls. `--stages company_information` limits
   to the stage where the free legs operate. Verify these flags still work
   as documented before running.

3. **After the run**, re-run the analysis script (`scripts/task211_analyze_free_legs.py`)
   against the production queue to measure actual yield.

4. **The webfetch crawl** has never been exercised. The first run is the
   moment to discover whether it works end-to-end, what it returns, and
   how many criteria it resolves. Expect teething issues.

---

## Files created

    scripts/task211_analyze_free_legs.py   Read-only analysis script
    docs/NEW-ORDER-RUN-2026-09-16.md       This report
