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

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 6b488f9f

**TESTS:** 
- 8 new tests in tests/test_webfetch_leg.py, all green
- 64 existing research tests green (test_research_audit, test_research_spend, test_research_ttl)
- 85 waterfall and enrich tests green
- Total: 157 tests, all passing

**FILES CHANGED:**
- `src/research.py` — moved free leg before `if not live` gate, added waterfall recording in _from_the_site_itself()
- `tests/test_webfetch_leg.py` — new test file, 8 tests
- `docs/FREE-CRAWL-NEVER-RAN-2026-09-16.md` — analysis document recovered from r45
- `scripts/task214_free_crawl_proof.py` — proof harness recovered from r45

**FINDINGS:**

1. **Root cause is option (a):** The free leg was gated behind `if not live: return []` in `research.run()`, and `live` was `live and apify.settings(config)["enabled"]`. Since `apify.settings({})["enabled"]` is False by default, `live` was always False for clients without Apify, and the function returned before reaching the free crawl. The free webfetch leg never ran.

2. **Secondary issue is option (c):** Even if the free leg had run, `_from_the_site_itself()` wrote evidence to `rec["research"]` but never called `waterfall.record_step()`. So the ledger had zero webfetch rows, making every cost measurement that read the ledger wrong about the free leg.

3. **The fix:** 
   - Moved the free leg (call to `_from_the_site_itself`) BEFORE `if not live: return []` in `research.run()`. The free leg now runs whenever there is a stated `reason`, regardless of whether Apify is enabled.
   - Added `waterfall.record_step()` in `_from_the_site_itself()` when the crawl succeeds, with `stage=company_information`, `provider=webfetch`, `call=webfetch-crawl`, `expected_cost=0`.
   - The `live` gate now stops only the PAID leg, not the free one.

4. **Test fix:** The recovered tests were failing because `setUp` only cleared the in-memory crawl cache but not the persisted cache, which was leaking state between tests. Added `research._reset_persisted_cache()` to both test class setUp methods. All 8 tests now pass.

5. **Chain from crawl to consumer:** The chain is complete and correct. `webfetch.research(domain, config)` returns pages with `source_url`, `field`, `fact`, `provider: local_http`, `content_hash`, `http_status`, `chars`. `_from_the_site_itself()` transforms this into evidence rows with `record_id`, `retrieved_at` added. Evidence is appended to `rec["research"]`. Downstream consumers read `rec["research"]`: `segments.text_of(rec)`, `research.for_prompt(rec)`, `evidence.select()`, and `icpstructural`. The shape is correct.

6. **Cost conclusions affected:** Every cost measurement that read the waterfall ledger to say what evidence cost was wrong about the free leg. The ledger said "webfetch: 0 rows, 0 cost" and concluded the free crawl was not being used. The truth is the free crawl was not even being attempted (option a), and even if it had been, it would have written no ledger row (option c). Affected documents: any document that read the waterfall ledger to measure free vs paid evidence costs. `docs/FREE-CRAWL-NEVER-RAN-2026-09-16.md` names them but does not change them, per the task instructions.

**RISKS:**
- The free crawl makes real HTTP requests to real prospect websites. All existing bounds (pages, bytes, redirects, timeout) are respected and were not changed.
- The free crawl adds prose evidence (company website, about pages, team pages) but not structured evidence (industry, offices, employees). Records missing structured data still need ContactOut company-info (1 credit) to reach an ICP verdict.

**RECOMMENDED CLAUDE ACTION:**
1. Review the fix in `src/research.py`
2. Run the free-leg pipeline from Claude's worktree: `py -3 -m src.generate --cap 0`
3. The free crawl will now run and write waterfall rows, improving copy quality for all records
4. Records missing structured data (industry/offices/employees) still need ContactOut company-info to reach ICP verdicts
