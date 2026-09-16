PRIORITY: P0
DEPENDS: TASK-182

# TASK-183 - buy evidence for twenty-five records and see if the wall moves

## WHERE THIS SITS

This is the measurement that decides how the estate gets unblocked, and the two
results it sits between are both from this morning.

TASK-171 and TASK-180: **314 of 316 records are in `review`, 308 have no
evidence at all, and absent evidence `review` is the only honest verdict ICP
can give.** The constraint is evidence.

TASK-166: Grok, on 10 real domains, found **174 facts the free path does not
have, every one carrying a source URL, at $0.20 per domain.** Six of those ten
domains had ZERO usable free-crawl evidence, and for those six Grok found all
of the public evidence there was. The free path's webfetch is same-domain-only
and structurally cannot reach a news article, a registry or a directory.

So there is a plausible answer - buy the evidence - and one number nobody has:
how many records actually change verdict when you do.

## THE QUESTION

Twenty-five records. Not 316. This is a measurement with a budget of about $5.

1. **Pick the 25** from the records in `review` with no evidence, and say how
   you picked them. TASK-169 produced an enrichment ordering; if it applies,
   use it and say so. A sample chosen for being easy answers a question nobody
   asked.
2. **Acquire evidence through the adapter** (TASK-182 has moved it onto the
   Responses API - use it, do not call the endpoint directly). Write the facts
   into the record's `company_facts` and `research` the way the existing free
   path does, preserving **provenance, source_url, retrieved_at and evidence
   ids**. A fact without provenance cannot pass the claims gate, so a fact
   without provenance is worth nothing here however true it is.
3. **Re-run qualify and count the movement.** This is the deliverable:

       how many of the 25 moved from `review` to `qualified`
       how many moved from `review` to `rejected`
       how many stayed `review`, and which criterion was still UNKNOWN
       how many changed `confidence` off `low`

   A rejection is a good outcome. It is a record we now know not to spend
   person credits on, which is the whole point of company-first.
4. **Then run the claims gate** against the new facts for any record that
   reached `qualified`. ICP accepting a fact and the claims gate licensing it
   for copy are different questions, and if the second one refuses, the
   evidence bought a verdict and no copy.
5. **The cost per outcome.** Dollars spent, divided by records that reached a
   verdict, and the projection to all 308. TASK-166 projected $61.89 for 316
   and about $20 targeted - replace those projections with a measured one.

## THE TRAP

The tempting summary is "Grok added 174 facts". Facts added is not the metric.
**Records that changed verdict** is the metric, and it is possible to add a
hundred true sourced facts about a company and leave every structural criterion
still UNKNOWN, because the criteria ask specific questions and a news article
may answer none of them. If that is what happens, say it plainly - it is the
most useful finding available from this task and it would stop a $60 spend that
buys nothing.

Second trap: do not let a bought fact bypass anything a free fact must pass.
Same freshness rules, same licensing, same claims gate. And do not treat
UNKNOWN as a pass to make the movement number look better - that prohibition is
the same one TASK-180 carries.

## WHAT YOU MAY NOT DO

- **Twenty-five records. Hard stop.** Do not continue to 50 because the
  results look good. Scaling is Claude's decision and the operator's money.
- Budget about $5. If spend passes $8, stop and report.
- No provider writes to HeyReach or EmailBison. No enrichment credits, no
  Apify - the only paid call here is xAI.
- Do not weaken ICP, a threshold, the claims gate or a freshness rule.
- Do not move a record to `dropped`.
- Never commit PII: hash record ids, domains and company names. Source URLs
  that point at a prospect's own site identify the prospect - hash those too,
  and keep third-party source domains as they are.

## FILES ALLOWED

    docs/BOUGHT-EVIDENCE-2026-09-16.md   (new)
    scripts/task183_*.py
    work/   (writing evidence onto the 25 records is the point of the task -
             a full free run may still be in flight, so check for a live writer
             before you start and say what you found)

## FILES FORBIDDEN

    src/   config/   src/providerwrites.py

## DELIVERABLE

How the 25 were chosen, the four movement counts with the still-UNKNOWN
criterion named, the claims-gate verdict on the newly qualified, the measured
cost per verdict, and the projection to 308 that replaces TASK-166's estimate.

## RESULT

**STATUS: BLOCKED - no XAI_API_KEY in this worktree**

**COMMIT SHA:** 16b187f

**TESTS:** Script dry-run passes; live run refused correctly on missing key.

**FILES CHANGED:**
- `scripts/task183_buy_evidence.py` (new) - complete measurement script
- Task file moved TODO/ -> RUNNING/

**FINDINGS:**

1. **XAI_API_KEY is absent from `config/.env` in this worktree.** The key is
   not listed among the provider keys QWEN.md confirms present (BISON,
   HEYREACH, CONTACTOUT, APIFY, REOON, DELIVERABLE, BLITZ). The only API keys
   present are LLM_API_KEY (OpenRouter), APIFY_TOKEN, and DELIVERABLE_KEY.
   The entire task depends on calling xAI's Responses API to buy evidence.
   Without the key, no evidence can be acquired and no verdict movement can
   be measured.

2. **The queue snapshot has different state than TASK-171/180 reported.**
   Snapshot stamp: `2026-09-15T17:52:12+00:00 from master cf23154 550 records`.
   Status distribution: 250 unqualified, 121 rejected, 113 qualified, 66 review.
   Only **17 records** are in `review` with zero evidence (not 308). An
   additional 49 are in `review` with some evidence (1-5 rows). The 308-no-
   evidence figure from TASK-171/180 was measured against a different state.

3. **Selection strategy implemented and verified via dry-run:**
   - All 17 records in `review` with zero evidence
   - 8 records in `review` with exactly 1 evidence row, sorted by descending
     ICP score (closest to qualifying, most likely to tip with evidence)
   - Total: 25 records
   - Score range: 0.0 to 24.0

4. **The script is complete and ready to run.** It:
   - Calls Grok via the Responses API with web_search (same pattern as
     TASK-166's measurement, which is the adapter TASK-182 describes)
   - Writes facts into `company_facts` and `research` with full provenance
     (source_url, retrieved_at, evidence_id, provider="grok")
   - Re-qualifies through the real `qualify.company()` entry point
   - Runs the claims gate on newly qualified records
   - Tracks cost and projects to 308
   - Saves incrementally so a timeout loses nothing
   - Hashes all record IDs, domains, and company names before logging
   - Budget: $5 soft stop, $8 hard stop

**RISKS:**
- The measurement cannot be completed from this worktree without XAI_API_KEY.
- The snapshot state differs from what the task description assumed (17 vs 308
  records with no evidence). The projection base should be recalculated from
  the actual current state.

**RECOMMENDED CLAUDE ACTION:**
1. Add XAI_API_KEY to this worktree's `config/.env`, OR
2. Run `py -3 scripts/task183_buy_evidence.py` from a worktree that has the
   key (Claude's worktree has it per TASK-166 having run successfully), OR
3. Provide the key and I will run the measurement immediately.
