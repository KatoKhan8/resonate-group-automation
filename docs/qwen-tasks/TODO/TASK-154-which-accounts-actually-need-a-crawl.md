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
