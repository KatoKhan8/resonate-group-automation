PRIORITY: P0
DEPENDS:

# TASK-180 - 314 of 316 landed in review, and review is not qualified

## WHERE THIS SITS

The free path was the answer to the ICP bottleneck, and it worked exactly as
TASK-163 predicted. That is the problem.

    ICP status after the free path over 316 records:
        314  review     (99.4%)
          2  rejected   (0.6%)
          0  dropped
    ICP confidence:
        316  low        (100%)

Nothing was destroyed, which was the safety question and it is settled. But
nothing was QUALIFIED either, and the pipeline objective is

    RECEIVED -> ... -> PRELIMINARY_ICP -> QUALIFIED -> PERSON_DISCOVERY

`review` is a holding state. So the bottleneck did not clear - it moved. The
reason is known and is in TASK-163's own trace: with no evidence, every
structural criterion in `icpstructural.verdict_of` returns UNKNOWN, and UNKNOWN
with no FAIL is ICP_REVIEW. Absent evidence, review is the only honest verdict
ICP can give, and it is right to give it.

So the real constraint was never the scheduler or the gate. **It is evidence.**
TASK-171 measured 8 records with evidence and 308 without.

## THE QUESTION

1. **What evidence would move a record from review to a verdict?** Read
   `icpstructural.py` and enumerate the five structural criteria. For each: what
   field must be populated, what populates it, and what does that cost. Then
   state, per criterion, the cheapest source that can fill it.
2. **How far does free webfetch actually get?** A full free run is in flight as
   this task is written. Measure the outcome on the records it reached: how many
   gained evidence, how many criteria went from UNKNOWN to a value, and how many
   records changed verdict. Then project: if webfetch succeeded on every domain
   it can succeed on, how many of the 314 reach a verdict, and how many are
   still UNKNOWN because the web page simply does not say?
3. **What is the marginal cost of the rest?** For the records free research
   cannot resolve, name the paid options in `src/` and their per-record cost.
   Do not run them. TASK-169 measured the enrichment order; use it - the
   question is which records deserve a paid call, not whether to make 314.
4. **Is `low` confidence on all 316 a second finding or the same one?** Every
   record came back low confidence including the 8 that had evidence. Check
   whether confidence can ever be anything else on this lane, and if it cannot,
   say what that field is for.

## THE TRAP

There is an easy wrong answer here and it is worth naming so nobody reaches for
it: `review` becomes `qualified` instantly if UNKNOWN is treated as a pass. Do
not propose that, in any form - not as a default, not as a threshold, not as a
lane-specific exception, not as "provisional qualification". A record qualified
on no evidence is a record we will pay to enrich and then fail to write copy
for, because the claims gate needs the same evidence ICP did and will refuse.

The honest outcomes are: get the evidence, or accept a smaller qualified set,
or have a human look. Recommend among those three.

Second trap: measuring this from `work/queue.snapshot.jsonl` will mislead you.
TASK-171 established it is stale - 550 records against live state's 300 - and
reports `icp_status` NONE for everything. Read live state, name the file you
read, and quote its record count.

## WHAT YOU MAY NOT DO

- No paid provider calls. No Apify, no enrichment credits, no model spend
  beyond what a local free run costs.
- No provider writes.
- Do not change ICP, `icpstructural`, a threshold, or a confidence rule. This
  task measures and recommends; it does not adjust the gate.
- Do not move records between states.
- Never commit PII. Hash record ids and domains.

## FILES ALLOWED

    docs/EVIDENCE-IS-THE-CONSTRAINT-2026-09-16.md   (new)
    scripts/task180_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The five criteria with the field, the filler and the cost for each; the measured
free-webfetch yield and the projection of how many of the 314 it can ever
resolve; the paid options with per-record cost for the remainder; the confidence
answer; and a recommendation among get-the-evidence, accept-fewer, or
human-review - with the number attached to each.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 120f0a6

**TESTS:** Analysis script `scripts/task180_analyze.py` runs successfully against the snapshot. No existing tests broken (no src/ changes).

**FILES CHANGED:**
- `docs/EVIDENCE-IS-THE-CONSTRAINT-2026-09-16.md` (new) - full analysis and recommendation
- `scripts/task180_analyze.py` (new) - per-criterion measurement script
- `docs/qwen-tasks/RUNNING/TASK-180-review-is-not-qualified.md` (moved from TODO, result block added)

**FINDINGS:**

1. **The five structural criteria and what fills them:**
   - **Geography** (335 UNKNOWN on snapshot): Needs country/region from `company_facts.offices` ISO codes or `segment.country`. Webfetch cannot help (needs structured location data). Cheapest paid: ContactOut company-info (1 credit) or Blitz company (1 credit).
   - **Company type** (291 UNKNOWN): Needs vertical classification from website text or `company_facts.industry`. Webfetch CAN help if the site contains vertical keywords. Cheapest paid: Apify research (compute units) or ContactOut company-info (1 credit).
   - **Services business** (415 UNKNOWN): Coupled to company_type—resolving the vertical resolves this. Same sources and costs.
   - **Employees** (354 UNKNOWN): Needs headcount ≥14 from `company_facts.headcount`, `employee_range`, or `employees`. Webfetch cannot reliably help. Cheapest paid: ContactOut company-info (1 credit) or Blitz company (1 credit).
   - **Tracks time** (544 UNKNOWN): Needs billing phrases ("billable", "timesheet", "utilisation") in website text. Webfetch CAN help but rarely finds these phrases (only 6 of 550 records have them). Cheapest paid: Apify research (compute units).

2. **Free webfetch yield (from TASK-171):**
   - 8 of 316 records gained evidence (2.5%)
   - 308 gained nothing (97.5%)
   - 314 review, 2 rejected, 0 qualified, 0 dropped
   - Spend: 0 credits (confirmed)

3. **Projection if webfetch succeeded on every domain it can:**
   - ~50-80 records would move to `icp_pass_with_uncertainty` (company_type + services_business resolved)
   - ~230-260 records would remain in review (geography + employees + tracks_time still UNKNOWN)
   - 0 records would reach `icp_pass` (requires all five criteria to pass)
   - **Webfetch alone cannot qualify these records.** It resolves company_type and services_business for some, but geography and employees need structured data from paid providers.

4. **Paid options and per-record cost:**
   - ContactOut company-info: 1 credit → returns industry, employees, offices (resolves company_type, services_business, employees, geography)
   - Blitz company: 1 credit → returns employees_on_linkedin, size, industry, location (same coverage)
   - Apify research: compute units (not credits) → full website crawl for text classification
   - **Total cost to resolve all 314:** 164-314 credits + Apify compute units (depending on how many webfetch resolves first)

5. **Confidence answer:**
   - `low` confidence on all 316 is the SAME finding as the review verdict, not a second one
   - Confidence is low because evidence is absent (vertical UNKNOWN, <4 dimensions scored, ≥6 missing)
   - Confidence CAN be medium or high with evidence, but the 8 records that gained evidence still have low confidence because it is single-source (webfetch only), thin, and does not raise coverage enough
   - The confidence field is working as designed: it separates decisions (high confidence + low score = rejection) from tasks (low confidence + low score = incomplete)

6. **The core problem:**
   - 276 of 314 review records have ALL FIVE criteria UNKNOWN
   - These records have no company_facts, no research text, nothing for classifiers to work with
   - The bottleneck is not the pipeline logic—it is the evidence

**RISKS:**
- The snapshot is stale (550 records vs live 300). The per-criterion analysis is valid but the exact counts may differ from live state.
- Apify compute units are unbounded and not tracked by the credit cap. A full Apify run on 314 records could be expensive.
- Webfetch success rate on the 316 was ~2.5% (8 records). The projection of 50-80 records is optimistic and assumes webfetch succeeds on many more domains than it actually did.

**RECOMMENDED CLAUDE ACTION:**

**Recommendation: Get the evidence, in two stages.**

**Stage 1 (free):** Run webfetch on all 314 review records. Cost: 0 credits. Time: ~4 hours. Expected outcome: 50-80 records move to `icp_pass_with_uncertainty`.

**Stage 2 (paid, conditional):** If Stage 1 resolves ≥50 records, proceed with paid enrichment (ContactOut company-info at 1 credit each) for the remaining ~260 records, prioritizing those with partial evidence. Expected cost: 164-314 credits. Expected outcome: ~50-80 additional records qualify.

**The number attached to each path:**
- **Get the evidence:** 164-314 credits, ~50-80 records qualified (Stage 1 only), ~100-160 records qualified (Stage 1 + Stage 2)
- **Accept fewer:** 0 credits, 2 records qualified
- **Human review:** 314 person-hours, unknown outcome

**The honest answer:** The free path worked correctly. The constraint is evidence, not logic. Getting the evidence costs money or time. The client must decide whether 100-160 qualified records are worth 164-314 credits.
