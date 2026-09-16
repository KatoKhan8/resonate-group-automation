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
