# TASK-981: collision.account_policy cannot be driven without a live provider

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

`collision.account_policy(account)` is the authority for the ON HOLD step of rule 2, and it takes a provider-truth `account` structure that only a live provider walk produces. A 120-day simulation therefore cannot exercise the one authority that answers the second of rule 2's five steps, and eight scenarios reported this key as unanswerable.

## Scenarios that surfaced it

`S04`, `S05`, `S06`, `S07`, `S08`

## Proposal

Give `collision` a pure constructor - `account_from_touches(rows)` - that builds the same structure from a list of touch rows, so a fixture or a simulation can produce one without a network call. `collision.touches_of(row)` already normalises a single row; this is the missing aggregate. Then `account_policy` is testable, and the REFUSED path - an incomplete walk must yield `unknown`, never `allow` - becomes assertable, which today it is not.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
