PRIORITY: P0
DEPENDS:

# TASK-214 - the free crawl is in the routing table and not in the execution path

## WHERE THIS SITS

This is the throughput defect, and it is the shape `CLAUDE.md` warns about by
name: "Existence is not function... a thing computed correctly that nothing
downstream reads."

TASK-208 put `webfetch-crawl` into the `company_information` waterfall as a
PRIMARY step, free, ahead of every paid fallback. Claude then ran the free legs
over the estate from the production worktree:

    enrich   records=330, spent=0
    states   verified 65, held 32, dropped 126, queued 315, drafted 12
             - IDENTICAL to before the run. Nothing moved.

And the ledger says why. Across all 550 records:

    waterfall rows by provider
      contactout   1056
      apify         298      <- apify-research is where research came from
      blitz         221
      deliverable   103
      reoon         102
      aiark          34
      webfetch        0      <- ZERO. Not one row, ever.

394 of 550 records have `research`, and it was bought from Apify. So the free
crawl has never produced a ledger row, the paid crawler has done the work all
along, and when Apify is refused by `--cap 0` nothing substitutes for it - the
run gathers no evidence at all. Which is exactly why 330 records processed and
nothing changed.

`src/research.py` does reference `webfetch.research(domain, config)`. So this
is not a missing integration so much as a leg that is present in two places
and executes in neither.

## THE QUESTION

1. **Establish which it is.** Three candidates, and they are different bugs:
     (a) `webfetch.research` is never called - find the branch that skips it
     (b) it is called and returns nothing usable - find why, on a real domain
     (c) it is called, works, and records no waterfall step - so it is
         invisible to the ledger and to every cost measurement we have made
   Prove which with the code path plus one real free crawl on one domain.
2. **If (c), the cost conclusions of the whole day are affected.** Every
   measurement that read the ledger to say what evidence cost would be wrong
   about the free leg. Say so explicitly and say which documents are affected;
   do not edit them.
3. **Trace the whole chain, input to consumer.** `CLAUDE.md` requires it for
   anything execution-critical: does the crawl write `research` rows in the
   shape `check_evidence` accepts, with `source_url` and `retrieved_at`, and
   does `icpstructural` read what it produces for company_type? A crawl whose
   output nothing consumes is the same defect one layer along.
4. **Fix the smallest root cause** and prove it with a run over TEN records
   that currently have no research. Report per record: crawl attempted, pages
   fetched, research rows written, whether a criterion moved from UNKNOWN, and
   the waterfall row that now exists.
5. **Then the number that matters.** TASK-211 measured 53 queued records that
   would benefit from a free crawl, and 33 missing all three of
   industry/offices/employees. With the leg working, how many of those reach a
   verdict for zero credits?

## THE TRAP

`webfetch` is free but it is not costless: it makes real HTTP requests to real
prospect websites, and `src/webfetch.py` is documented as bounded - pages,
bytes and redirects. Do not raise a bound to get more evidence. Ten records in
item 4, and respect every existing limit.

Second trap: do not reach for Apify because it already works. The order is
settled by `PROVIDER-ROUTING-POLICY.md` - ContactOut, then its cache, then the
FREE crawler, then Grok, then other paid providers - and Apify is last for a
reason. Making the free leg work is the task; falling back to the paid one is
the thing that has been happening silently and is why nobody noticed.

## WHAT YOU MAY NOT DO

- No paid provider calls. No Apify, no ContactOut credits, no xAI. The free
  crawl only, on at most ten records.
- No provider writes to HeyReach or EmailBison.
- Do not change the waterfall ORDER, a criterion, a threshold or a gate.
- Do not raise a webfetch bound - pages, bytes, redirects or timeout.
- Do not move a record to `dropped`.
- Check for another live writer to `work/` before you start and say what you
  found. A canary path and two approval scripts are live against these files
  today.
- Never commit PII. Hash record ids and domains.

## FILES ALLOWED

    src/research.py   src/webfetch.py   (the smallest root-cause fix)
    tests/test_webfetch_leg.py   (new)
    docs/FREE-CRAWL-NEVER-RAN-2026-09-16.md   (new)
    scripts/task214_*.py

## FILES FORBIDDEN

    src/icp.py   src/icpstructural.py   src/waterfall.py   config/

## DELIVERABLE

Which of (a), (b) or (c) it is with the code path proven; the affected cost
conclusions named if (c); the full chain from crawl to consumer; the
smallest fix with a ten-record run reporting per record; and how many of
TASK-211's 53 reach a verdict for zero credits.

## PRIOR WORK RECOVERED — 2026-09-21, read this before starting

An earlier round already did the ANALYSIS half of this task and it was never
integrated. Do not repeat it. It is on `origin/qwen-worker-r45` (commit
`23200fbb` touched these paths), and none of these files exist on master:

    docs/FREE-CRAWL-NEVER-RAN-2026-09-16.md   the written finding
    docs/TASK-214-FINAL-REPORT.md
    scripts/task214_free_crawl_proof.py       the proof harness
    scripts/task214_find_success.py
    scripts/task214_analyze_53.py             TASK-211's 53 records
    scripts/task214_verify_sample.py
    tests/test_webfetch_leg.py                8 tests, 4 of which FAIL on master

Recover them with `git show origin/qwen-worker-r45:<path>` rather than
rewriting them.

**THE FIX HALF WAS NEVER DONE, AND THAT IS WHY THIS TASK IS STILL OPEN.**
`src/research.py` on master carries a 27-line change from that branch's
lineage, but the free leg still produces nothing. Verified on master at
2026-09-21T09:5xZ by running the branch's own test file: four failures, the
load-bearing one being

    test_the_row_has_the_right_stage_and_provider
    AssertionError: 0 != 1        # zero webfetch rows in the waterfall

That assertion IS the deliverable restated: the crawl is in the table and not
in the path. The test is a correct statement of intended behaviour that master
does not implement, so it must NOT be merged as-is to make the suite green -
make the leg produce the row, then the test passes on its own terms.

Do not re-derive which of (a)/(b)/(c) it is until you have read
`FREE-CRAWL-NEVER-RAN-2026-09-16.md` off that branch.
