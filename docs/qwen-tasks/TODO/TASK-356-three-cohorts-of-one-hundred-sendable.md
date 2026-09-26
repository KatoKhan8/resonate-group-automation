PRIORITY: P0
SIZE: L
DEPENDS: TASK-347

# TASK-356 - three cohorts of one hundred SENDABLE leads

**Operator decision, 2026-09-26, and it settles the question the launch package
raised:** 100 per cohort means **100 SENDABLE - through BOTH gates.** 300 total.

> If Monday's supply falls short of 300, launch with what passes and report the
> number.

So the target is 300 leads that pass `copylint` **and** `sequencegate`, and a
shortfall is an acceptable, reportable outcome - **not** something to reach by
loosening a gate.

## What that costs, measured on the fifty

    50 processed -> 31 written -> 13 passed both gates    (42% of written)
    cost per written lead                                 10.15c

    300 SENDABLE therefore needs ~715 written             ~$72.61
    300 written would yield only ~126 sendable

**Generate in batches and stop to report.** Do not generate 715 in one run. After
the first 100 written, report: how many passed both gates, which rules fired on
the rest, and the real spend from the ledger. The 42% rate is measured on 50
leads from one segment and may not hold; if it is 20%, 300 sendable needs 1,500
written and $152, and that is a number the operator must see before it is spent.

**BUDGET: stop at $80 and report**, whatever has been produced. Do not continue
past it without the operator.

## Depends on TASK-347

The inventory does not exist yet: 237 usable contacts against 300 sendable, and
their freshness is unestablished because the queue records no send events.
TASK-347 is running the client file (35,043 rows) through qualification, MX,
CheapVerifier, packs and facts. **Do not start until it has produced inventory**,
and read its measured qualification rate rather than the 21% estimate.

## The three cohorts must differ

`PRODUCTION-SCALE-POLICY.md`: a campaign is a COHORT and never a person, grouped
by a real signal backed by evidence that exists.

**Three cohorts on one segment measure the same thing three times.** Each needs a
different persona, capability or angle, so a week of replies is a comparison. Take
the grouping from `TASK-320`'s per-segment strategy if it has landed; if it has
not, group by the segment data already on the records and **say in the result
block that the grouping is data-derived rather than strategy-derived.**

## Unchanged, and any deviation is a failure of this task

- Five email steps, days 1/4/8/12/21, threading em1 new/A, em2 reply A, em3 new/B,
  em4 reply B, em5 new/C.
- Five LinkedIn steps, `PRODUCTIVE_LI_HEAVY_V1`, days 1/3/6/10/15.
- Every gate in force: `copylint`, `sequencegate`, `emptyrender`, suppression, DNC.
- The 76 recipients suppressed after the 09-23 incident stay suppressed.

## Deliverable: a review file per cohort, in the ten's shape

Three `.html` + `.xlsx` pairs. Each must carry, per lead: ICP verdict with
evidence, facts with first-party sources, the hypothesis marked AS a hypothesis,
capability and why, five emails with threading and both P.S. lines, the signature
block, the LinkedIn messages, and **the per-gate result per lead with the rule
that fired.**

The fifty looked like 31 usable leads and was 13. **A review file that does not
make the sendable count obvious on its own has failed**, so print the three
figures at the top of each: processed, written, sendable.

## Acceptance - RUN, paste real output

1. Per cohort: processed / written / **sendable**, and the rule-by-rule breakdown
   of everything that did not pass.
2. Real spend from the ledger, per model, per cohort. Not a projection.
3. Threading verified programmatically on every written lead: 5 steps, days
   1/4/8/12/21, threads A/A-reply/B/B-reply/C. Report any deviation as a failure.
4. **No suppressed or DNC address anywhere in any cohort.** Assert it and report
   the count skipped.
5. **Nothing staged, attached, enrolled, activated or sent.** Assert the queue
   carries no campaign id and no staged flag for these records.
6. The three review files exist, and the approval hash
   (`reviewapproval.file_hash`) of each is reported so the operator can quote it.

## What this task may NOT do

- **Do not activate, stage, attach, enrol or send.** The production freeze in
  `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md` is in force; the operator will
  grant a freeze exception with APPROVED, and until those words exist this
  produces review files and nothing else.
- **Do not loosen, widen or skip a gate to reach 300.** A shortfall is an
  acceptable reported outcome. Widening a lint rule to make a draft pass is
  forbidden by CLAUDE.md in as many words.
- Do not shorten the cadence or alter the threading.
- Do not exceed $80. Do not modify the fifty's posted, hashed files.
