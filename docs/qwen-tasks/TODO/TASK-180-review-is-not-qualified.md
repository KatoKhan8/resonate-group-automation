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
