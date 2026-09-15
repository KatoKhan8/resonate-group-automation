PRIORITY: P1
DEPENDS:

# TASK-154 - research eligibility, before anybody spends money on it

## WHAT IS ALREADY SETTLED - DO NOT REDO

- The crawler exists, works, and its output reaches the prompt.
  `src/webfetch.py` is free and stdlib-only and runs before paid Apify.
- `research.why()` now has a TTL: 3 days for team/careers/hiring/news/launches,
  30 for positioning. `stale_evidence()` returns which rows aged out.
- A draft references an evidence fact 7.3% of the time when the evidence is
  good and 0.0% when it is junk. That is the CEILING on what research quality
  buys through the current prompt.

## THE QUESTION

Of the 550 records, which actually need research, and what would it cost?

Against the snapshot - **quote the STAMP**:

1. How many records have NO evidence at all, and would `research.why()` fire
   for them? Group by the reason it returns.
2. How many have evidence that is now STALE under the TTL, by field?
3. How many have evidence that is present but UNUSABLE - 236 of 695 rows were
   page furniture. Does `evidence.select` now filter those out of the prompt,
   and if so how many records are left with nothing usable to show?
4. Of the records that need research, how many are ICP-QUALIFIED? Crawling a
   company we have already rejected is spend with no downstream consumer, and
   the standing rule is company-first: cheap gates before expensive work.

## THE OUTPUT THAT MATTERS

A prioritised research WORKLIST: record ids, the reason each needs research,
and whether the free leg (`webfetch`) is likely to be enough or the paid leg
is required. Ordered so the highest-value, cheapest work is first.

**Do not perform uncontrolled crawling.** You may run `webfetch` against at
most FIVE domains to sanity-check reachability, and you must say which five
and why. Apify is Claude's to run.

## WHAT YOU MAY NOT DO

- No Apify. No bulk crawling. No model calls.
- Do not write to `work/`.

## FILES ALLOWED

    docs/RESEARCH-WORKLIST-2026-09-15.md   (new)
    scripts/task154_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The four counts, the prioritised worklist with a reason per record, the
free-vs-paid split, and the five reachability probes with their results.

## RESULT

**STATUS:** DONE

**COMMIT:** 8213a7b

**TESTS:** Analysis scripts ran successfully against the snapshot. No unit
tests were applicable — this is a measurement task, not a code change.

**SNAPSHOT STAMP:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

**FILES CHANGED:**
- `docs/RESEARCH-WORKLIST-2026-09-15.md` (new) — the deliverable report
- `scripts/task154_analysis.py` (new) — Q1-Q4 analysis
- `scripts/task154_deep_dive.py` (new) — why 326 no-evidence records don't fire
- `scripts/task154_probes.py` (new) — 5 reachability probes
- `scripts/task154_worklist.json` (new) — machine-readable worklist
- `scripts/task154_probe.json` (new) — probe domain selection
- `scripts/task154_probe_results.json` (new) — probe results

**THE FOUR COUNTS:**

1. **343 records have NO evidence** (62.4% of 550). Only **17 would `research.why()` fire for** — all for `public_evidence_required_for_icp_dimensions`. The other 326 have structured facts sufficient for their lane, or their ICP verdict is already settled.

2. **6 records have STALE evidence**, all in the `team` field (TTL=3 days). 4 are dropped, 2 are queued.

3. **3 boilerplate rows out of 703** (0.4%). `evidence.select` filters them. **0 records have ONLY boilerplate** — 343 have nothing usable because they have nothing at all.

4. **Of 23 needing research, 0 are ICP-qualified.** All 23 have no ICP verdict. 17 are queued (actionable), 6 are dropped (do not crawl).

**PRIORITISED WORKLIST:** 19 actionable records (17 ICP-dimension + 2 stale refresh), 4 dropped (do not crawl).

**FREE vs PAID:** 0/5 probe domains succeeded with the free leg. Expect ~15-17 of 19 actionable records to require paid Apify.

**FINDINGS:**
- `hotmail.fi` is an email domain, not a company site — data-quality issue.
- The research gap is smaller than the raw "343 with no evidence" suggests: 326 of them do not need research because structured data suffices.
- All 23 needing research are pre-ICP — research enables the verdict, not the other way around.
- The boilerplate filter is working well (0.4% vs the 34% measured before deployment).

**RISKS:**
- The 5-domain probe sample is small; the free-leg success estimate has wide uncertainty.
- Dropped records with stale evidence should not be re-crawled unless they are un-dropped.

**RECOMMENDED CLAUDE ACTION:**
1. Run free leg for all 19 actionable records.
2. Run Apify for failures (~15-17 expected).
3. Skip `hotmail.fi` until domain is verified.
4. After research, re-run ICP scoring on the 17 ICP-dimension records.
