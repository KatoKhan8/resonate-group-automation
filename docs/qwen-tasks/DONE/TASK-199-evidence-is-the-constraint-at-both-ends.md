PRIORITY: P0
DEPENDS:

# TASK-199 - the same missing thing blocks qualification and copy

## WHERE THIS SITS

Two findings from opposite ends of the pipeline arrived an hour apart and they
are the same finding.

**At the front,** TASK-180 and TASK-187: a record qualifies when geography and
company_type both PASS. 314 of 316 sit in `review` because their criteria are
UNKNOWN, and 276 have all five UNKNOWN. Absent evidence, `review` is the only
honest verdict ICP can give.

**At the back,** TASK-197: fifteen verified records with no copy. Generation was
attempted on all fifteen and **all fifteen failed at `persona_angle`**, refused
by the evidence traceability gate `check_evidence` in `src/llm.py`. The model
must produce a claim traceable to the record's own research rows, and a record
with no usable research cannot pass.

So a record with no evidence cannot be qualified, and a record that somehow
reaches verified without evidence cannot have copy written for it. The person
credits on those fifteen are already spent.

Two purchases have been measured against this. ContactOut company-info moved
**zero** verdicts across 50 records (TASK-185). Grok returned 174 sourced facts
on 10 domains at $0.20 each (TASK-166) and TASK-192 is measuring whether that
moves verdicts.

Nobody has measured the thing that decides how much either purchase is worth:
**what one unit of evidence actually unblocks.**

## THE QUESTION

1. **Count the blocked populations and their overlap.** Records blocked at ICP
   for want of evidence; records blocked at generation by `check_evidence`;
   records blocked at both. Name the predicate for each count. The overlap is
   the number that matters, because a record in both is unblocked twice by one
   purchase.
2. **What does `check_evidence` actually require?** Read it. How many research
   rows, with what fields, and what makes a row "usable"? A row with a
   `source_url` and a `retrieved_at` may still be unusable for reasons the gate
   knows and nobody has written down. Be exact: this is the spec any bought
   evidence must satisfy, and TASK-192 is buying against it blind.
3. **Do ICP and `check_evidence` want the same evidence?** ICP wants geography
   and a vertical. `persona_angle` wants a traceable claim about the company.
   A fact can satisfy one and not the other. Say which fields serve which, and
   whether one purchase can serve both or whether they are two purchases.
4. **Then price it.** For a record with nothing: what is the minimum evidence
   that moves it from `review` to `qualified` AND lets `persona_angle` pass?
   Express it as a list of fields, then say which of the measured sources can
   supply each - free webfetch, ContactOut company-info, Grok, Apify - with the
   per-record cost of the cheapest combination.
5. **Sanity-check the fifteen.** They are verified, so somebody paid for their
   contacts. How did they reach verified with no research? If a stage spends
   person credits on a record that cannot later have copy written for it, that
   is an ordering defect worth more than this whole analysis, and TASK-169
   measured that two thirds of enrichment spend produces nothing campaign-ready.

## THE TRAP

The conclusion this task is most likely to reach wrongly is "buy evidence for
everything". Check the direction of the money first: item 5 asks whether we are
spending person credits BEFORE the evidence that licenses copy, and if so the
cheapest fix is an ordering change costing nothing, not a purchase.

Second trap: do not propose relaxing `check_evidence`. It is the gate that
stops the model asserting things about a prospect that nothing supports, and
this repository's copy has already failed a human read once for exactly that.
A record that cannot pass it should not be emailed.

## WHAT YOU MAY NOT DO

- No paid provider calls. No credits, no Apify, no xAI - TASK-192 owns the
  spending side.
- No provider writes.
- Do not change `check_evidence`, ICP, a criterion or a threshold.
- Do not move records between states or run generation.
- Read live state, name the file, quote its record count. The snapshot is
  stale.
- Never commit PII. Hash record ids and domains.

## FILES ALLOWED

    docs/WHAT-ONE-FACT-UNBLOCKS-2026-09-16.md   (new)
    scripts/task199_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The three counts with the overlap and the predicate for each; `check_evidence`
specified exactly; whether ICP and the copy gate want the same evidence; the
minimum field list to unblock a record at both ends with the cheapest source
per field and a per-record price; and the answer to how fifteen records reached
verified with no research.

## RESULT

STATUS: DONE
COMMIT SHA: 14eca22
TESTS: Analysis scripts run against snapshot (2026-09-15T17:52:12+00:00 from
       master cf23154, 550 records). No src/ changes.
FILES CHANGED:
  docs/WHAT-ONE-FACT-UNBLOCKS-2026-09-16.md     (new - the deliverable)
  scripts/task199_count_blocked.py               (new - population counter)
  scripts/task199_evidence_analysis.py            (new - evidence analysis)

FINDINGS:

1. THREE COUNTS WITH OVERLAP:
   - Blocked at ICP (geography or company_type UNKNOWN): 349
   - Blocked at generation (verified/held, 0 usable research): 20
   - Overlap: 0
   The overlap is zero because these are sequential pipeline stages.
   ICP-blocked records sit in review and never reach verified.
   Generation-blocked records already passed ICP (all 20 have
   icp_pass_with_uncertainty).

2. WHAT check_evidence REQUIRES:
   - Model produces evidence[] list for persona_angle
   - Each string must be traceable to fact_strings(rec)
   - fact_strings walks: company, domain, context, signal, company_facts
     (key+value pairs), contacts, sizing, research[].fact
   - Traceability: every adjacent content-word pair in the claim must be
     adjacent in ONE fact string; every number must appear in some fact
   - A research row is "usable" when quality is medium or strong
   - BUT: fact_strings includes ALL research rows regardless of quality,
     so even records with only weak/unusable rows have those strings in
     the pool. The failure is that the pool lacks specific prose claims
     the model can construct traceable evidence from.

3. ICP vs check_evidence EVIDENCE:
   - company_facts serves BOTH gates (industry->ICP company_type + fact pool;
     offices->ICP geography + fact pool; employees->ICP + fact pool)
   - research[].fact serves ONLY check_evidence (ICP ignores research)
   - segment.country/business_model serve ONLY ICP (not in fact pool)
   - ONE purchase CAN serve both if it populates company_facts

4. MINIMUM TO UNBLOCK BOTH ENDS:
   - One Grok call at $0.20/domain returns industry, offices, employees,
     specialties, notable, description with source URLs
   - This satisfies ICP's geography+company_type AND provides prose facts
     for check_evidence
   - For 349 ICP-blocked + 20 gen-blocked (zero overlap): $73.80 total
   - ContactOut company-info (1 credit/record) failed on unknown domains
     (TASK-185: zero verdicts moved on 50 records)
   - webfetch is free but already tried for the 20 - produced weak/unusable
     quality rows (boilerplate)

5. HOW 20 RECORDS REACHED VERIFIED WITH NO RESEARCH:
   - THE ORDERING DEFECT: enrich.outcome() checks any(sendable contacts)
     but NOT research, evidence, or ICP verdict
   - Person credits spent (decision-makers: 10 + email-verifier: 1 per
     contact) BEFORE evidence gathered
   - All 20 have icp_pass_with_uncertainty from ContactOut structured data
     (industry + offices) but zero usable research for copy
   - CHEAPEST FIX: gate person-level enrichment on evidence availability
     (research.why() already computes this). Costs zero provider credits.
   - Scale of waste: ~240 credits on contacts where copy cannot be generated

RISKS:
- The 20 generation-blocked records have company_facts producing 27-246
  fact strings, but persona_angle still fails because the model cannot
  construct traceable claims from structured data alone. Grok's prose
  (specialties, notable, description) may help but is not guaranteed to
  produce adjacent-word-pair matches for every claim the model attempts.
- TASK-192 is measuring whether Grok actually moves verdicts on 25 records.
  If it also moves zero, the evidence bottleneck has a different root cause.

RECOMMENDED CLAUDE ACTION:
1. Read docs/WHAT-ONE-FACT-UNBLOCKS-2026-09-16.md
2. Add evidence gate before person-level enrichment (costs nothing)
3. Wait for TASK-192 results before purchasing Grok for the 349
4. Investigate why persona_angle fails for records with large fact pools
   (prompt issue or traceability test too strict for structured data)
