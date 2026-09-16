PRIORITY: P0
DEPENDS:

# TASK-187 - is `icp_pass` reachable at all, for any record in this estate?

## WHERE THIS SITS

This is the throughput question underneath every other throughput question, and
TASK-180's measurement raised it without answering it.

    tracks_time     UNKNOWN on 544 of 550 records
                    resolved by billing phrases in website text
                    only 6 records in the whole estate carry one

If `icp_pass` requires all five structural criteria to PASS, then at most 6
records in 550 can ever reach it, and no purchase changes that - not
company-info at a credit a record, not Grok at twenty cents a domain, not a
full Apify crawl. The money would buy geography, employees, company_type and
services_business, and `tracks_time` would still be UNKNOWN, and the verdict
would still be `review`.

That would mean the estate is not bottlenecked on evidence. It would mean the
qualification bar, as written, is unsatisfiable by the data this pipeline can
obtain - and every measurement of the funnel since has been measuring the wrong
thing.

It would also mean the 32 records that DID reach campaign-ready got there by
some route this reading does not explain. That contradiction is the most
important thing in this task.

## THE QUESTION

1. **Read `icpstructural.verdict_of` and state the rule exactly.** Does
   `icp_pass` require all five to PASS? Does it tolerate UNKNOWN on some? Is
   there a count threshold, a weighting, a required subset? Quote the code.
   TASK-180 mentioned an `icp_pass_with_uncertainty` outcome - establish where
   that sits and whether it is a qualifying state downstream or another holding
   state.
2. **Resolve the contradiction.** 32 records reached CAMPAIGN_READY and 91 were
   enriched, so something qualified them. Take five records that got through
   and trace their actual verdict and the criteria that produced it. Did they
   PASS `tracks_time`, or did the rule tolerate it, or were they qualified by a
   different path entirely - a human review, an override, an older rule?
3. **Then answer the question in the title**, with a number: how many of the
   550 can reach `icp_pass` if every purchasable fact were bought, and how many
   can reach whatever state actually gates PERSON_DISCOVERY downstream.
4. **If the two differ, say which one matters.** The pipeline objective names
   QUALIFIED as the gate to person discovery. Find what `personas` and `enrich`
   actually test before they spend a person credit - the name of the state or
   the predicate - because that, not the word "qualified", is the real bar.
5. **If the bar is unsatisfiable as written**, describe the options without
   choosing: a different criterion for `tracks_time`, a different source for
   it, a required-subset rule, or human review at a defined volume. Give each
   the number of records it would unblock.

## THE TRAP

The whole value of this task is that it might prove the criterion set cannot be
satisfied. If it does, the answer is NOT to relax `tracks_time` - it is to
report to the operator that the bar and the obtainable evidence do not meet,
with the numbers, and let them decide. **Do not change ICP, a threshold, a
weighting or a criterion in this task.** Do not add a default. Do not introduce
a "provisional" state. Measure and report.

Second trap: `tracks_time` asks whether a prospect tracks time, and Productive
sells time tracking, so it is plausibly the single most load-bearing criterion
in the whole ICP. Do not treat it as noise because it is inconvenient. If it
cannot be evidenced from a website, the honest finding may be that it needs a
different kind of source, and naming that source is worth more than any
threshold change.

## WHAT YOU MAY NOT DO

- No paid provider calls. No credits, no Apify, no xAI. This is a code read and
  a measurement over records that already exist.
- No provider writes.
- Do not change `icp.py`, `icpstructural.py`, a threshold, a weighting or a
  criterion. Not one line.
- Do not move any record between states.
- Read live state, name the file, quote its record count - the snapshot is
  stale and reports `icp_status` NONE for everything.
- Never commit PII.

## FILES ALLOWED

    docs/IS-THE-BAR-REACHABLE-2026-09-16.md   (new)
    scripts/task187_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The exact `verdict_of` rule quoted from the code, the traced verdicts of five
records that reached campaign-ready and how they passed, the number that can
reach `icp_pass` with every purchasable fact bought, the real predicate that
gates person-credit spend, and - if the bar is unsatisfiable - the options with
a record count against each.
