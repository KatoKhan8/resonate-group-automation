# TASK-985: No positive rate may be published until 100 classifier-positives are reviewed

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

The operator's condition, recorded 2026-10-03: every positive rate carries the label *classifier unaudited* until 100 classifier-positive replies have been reviewed by a person. The reason is on the record - a reply whose entire human content was the word "Stop" was classified `positive 0.75` before TASK-939, and commit d307e019 measured that of 23 replies a human flagged interested, five classify positive and FOUR classify as a refusal.

The input rate is thin: 20 positives in the 899-reply corpus, 2.2%. A simulated funnel's entire meeting count rests on it.

## Scenarios that surfaced it

`S09`, `S15`

## Proposal

Two parts. (1) A review artefact: `scripts/audit_positives.py` walks the provider for replies the current rules classify `positive`, `meeting_intent`, `question` or `interested`, writes them to a review file with the verdict and the evidence, and records the operator's agree/disagree per row. It is a provider READ and within policy. (2) A gate: any report or digest rendering a positive rate reads an `audited_positives` count and appends "classifier unaudited" whenever it is under 100. Make the label a property of the renderer, not of the author's memory - this run had to add it by hand in four places, which is three too many.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
