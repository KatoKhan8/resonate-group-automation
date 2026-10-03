# TASK-988: A question with no question mark, and a past-failure objection, both fall to unknown

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

MEASURED, 3 of 3 firings each.

**S15** - `how would this work with the tooling we already run` - classifies **`unknown 0.00`**. The `question` rule's leading pattern requires a literal `?`. People do not reliably punctuate, and the same sentence WITH a question mark classifies `question 0.75` - verified by probe.

**S16** - `we tried something like this before and it did not work for us` - classifies **`unknown 0.00`**. The `objection` patterns cover price, budget, time, resources, headcount, an incumbent vendor and priority. They do not cover a PAST FAILURE, which is one of the commonest objections there is.

Both land in `unknown`, already the largest real class at 278 of 899, and per TASK-941 not one of those 278 reaches a human. Under the operator's metric of 2026-10-03 a question about the offer IS a positive, so S15 is the headline metric going into a bucket nobody reads.

## Scenarios that surfaced it

reported across the run rather than by one scenario

## Proposal

Two narrow additions, each with its own test, and NEITHER widens `unknown`:

1. Make the question mark OPTIONAL in the question rule's leading pattern but require the interrogative to START the first non-empty line - anchored, so a mid-sentence "what we do" does not match. The anchor is the guard, exactly as `BARE_REMOVAL_LINE_PATTERNS` uses the first non-empty line rather than the whole body.
2. Add past-failure patterns to `objection`: `tried (?:this|that|something like)`, `did ?n.?t work`, `was ?n.?t a success`, `burned by` - at `objection`'s existing position AFTER every refusal, so a refusal is never softened into an objection.

Sweep the 899-reply corpus before and after and report the verdict delta as a NAMED SET, not a count: three finished suites here once reported exactly 231 failing names and one of them was a different 231.

Acceptance: S15 reports `question` and reaches a human, S16 reports `objection`, and NO row loses a verdict into `unknown`.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
