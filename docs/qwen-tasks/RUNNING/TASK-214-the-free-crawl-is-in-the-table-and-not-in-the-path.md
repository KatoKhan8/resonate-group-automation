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
