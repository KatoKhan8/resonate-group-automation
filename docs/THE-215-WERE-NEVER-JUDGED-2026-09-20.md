# The 215 are not a backlog of rejected companies. Nothing has judged them yet.

2026-09-20. Written to settle a question three handoffs have carried forward
as an action item for a human, and to stop the next session spending a day on
the wrong fix - including the fix that was already built and is sitting on a
branch.

Every number here is recomputed from `work/queue.jsonl` today.

## The claim being tested

The previous session's preliminary finding was that the 215 records in
`ICP_REVIEW` are there because their criteria are UNKNOWN - the records were
never enriched - rather than because they failed qualification.

**Confirmed, and it is stronger than that.**

## The measurement

    review records                                     215
    records with ANY criterion at `fail`                 0
    records carrying any contact                         0
    records still in state `queued`                    215

**Not one of the 215 has failed a single criterion.** There is no rejected
pool here. `review` is the verdict this system returns when it has not been
given enough to decide, and that is exactly what it is saying.

Per criterion, across the 215:

    tracks_time         unknown 215
    geography           unknown 208   pass   7
    services_business   unknown 167   pass  48
    company_type        unknown 144   pass  71
    employees           unknown  59   pass 147   pass_with_tolerance 9

The two that decide a verdict are `geography` and `company_type`
(`verdict_of` returns qualified when both PASS, and
`icp_pass_with_uncertainty` when both PASS with other criteria unknown):

    geography unknown, company_type unknown    137
    geography unknown, company_type pass        71   <- one field away
    geography pass,    company_type unknown      7

## So the bottleneck is geography, and it is not a parsing problem

208 of 215 are blocked on geography. That makes it the single highest-value
field in the estate, and the obvious next question is whether the evidence is
already on the record and simply unread - the recurring defect in this
repository.

It is not, for the overwhelming majority:

    carry company enrichment beyond a headcount signal      31 of 215
    carry any `company_facts.offices`                       22 of 215
    carry only `headcount_signal`, or nothing              184 of 215

**184 of the 215 hold no company evidence at all.** They were received,
given a preliminary ICP pass over whatever the intake carried, and never
enriched. Nothing downstream is broken. The pipeline is correct and the
records are empty.

## The fix that already exists does not fix this, and that is the point

`origin/geo-iso-resolution-2026-09-17` carries TASK-227, commit `9194b06c`,
titled *"The offices string ends in an ISO code and geo never read it"*. It
is a real defect and a real fix: `geo.resolve` matched free text against city
and country NAMES while the evidence held is a two-letter CODE, so
`offices: ["Buenos Aires, Buenos Aires, AR"]` resolved to
`no usable location evidence`. The branch adds ISO-code resolution, trailing
extraction from the offices string, a comma-separated city fallback, and it
keeps the US/CA/AU timezone refusal intact at MEDIUM rather than HIGH
confidence. 27 new tests, no regressions.

It was found independently today by walking the 215, and it is worth
integrating on its own merits.

**It moves at most 8 of the 215, and 1 of the 71.** Measured, not estimated,
by extracting the trailing ISO from every office string on a review record
and testing it against the client's own include and exclude lists:

    review records carrying a parseable trailing ISO        22
      -> would reach geography PASS                          8
      -> would reach geography FAIL                          0
      -> still UNKNOWN: on neither the include nor the
         exclude list                                       14

    of the 71 that are one field away                       13 carry an ISO
      -> would reach PASS                                    1

Two separate reasons it is small, and both matter:

1. **Only 22 of 215 carry an offices string at all.** A better parser over
   evidence that does not exist resolves nothing.
2. **The codes that do appear are mostly outside the client's stated
   market.** Productive's include list is UK, Ireland, Netherlands, Germany,
   France, the Nordics, Belgium, Austria, Switzerland, Spain, Italy,
   Portugal, Poland, Australia, New Zealand, the US and Canada. The codes
   actually present on review records are largely CEE, the Balkans, the
   former USSR, the Middle East, Africa and Latin America. Resolving those
   correctly turns `unknown` into a *better-evidenced* `unknown` - "on
   neither list, so it is unestablished rather than excluded" - which is the
   right answer and is not inventory.

So the branch should be integrated for correctness and for the scheduler,
and **it must not be integrated as the answer to the 215.** Reporting it as
cohort growth would be the same error as the credential audit on the 19th:
a confident number pointed at the wrong bottleneck.

## What this does and does not license

**It does NOT license reclassifying any UNKNOWN as READY.** An unknown
geography is an unanswered question, not a pass, and the standing rule holds
without exception: missing evidence is never positive evidence. Nothing in
this document moves a single record's verdict.

What it settles is the *shape* of the work:

- **The 215 are not waiting on a human ICP verdict.** Three handoffs list
  "215 records await a human ICP verdict" as an operator action. A person
  looking at a record holding a domain and a headcount signal has nothing to
  judge either; they would be guessing from the same void. Remove it from the
  operator's list - it is an ENRICHMENT task, and it was always an
  enrichment task.
- **The limiting stage is company enrichment, not qualification, not
  approval, not copy and not sender capacity.** 184 records need a first
  unit of company evidence before any other stage can have an opinion.
- **The cheapest measured lever is unproven for this pool.** The 09-16
  measurement stands and is discouraging: ContactOut `company-information-
  from-domain` over 50 records cost 25 credits and moved ZERO verdicts and
  ZERO criteria. Whatever buys geography for these 184, that call is not yet
  known to be it, and the next spend on this pool should be a bounded
  measurement of verdict movement per credit - not a batch.

## The falsifiable next step

Before any batch: take a bounded sample of the 71 that are one field away,
buy company evidence through the routing policy's order, and measure
**criteria resolved and verdicts moved per credit** - the same measurement
that saved roughly 300 credits on the 16th. If geography does not move, the
provider is wrong for this question and the answer is sourcing accounts that
arrive with a location, not enriching accounts that do not.

The 71 are the right sample because they are one field from a verdict, so
the measurement is unambiguous: geography resolves to an include-list country
and the record qualifies, or it does not and nothing was hidden behind a
second unknown.
