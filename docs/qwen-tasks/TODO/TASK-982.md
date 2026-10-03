# TASK-982: The COLD LEAD recontact gap rule 2 requires does not exist

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

CLAUDE.md rule 2 makes a COLD LEAD contactable *subject to a configured gap since the last manual or internal touch*. There is no such configuration and no reader for one. Measured: `gap_days`, `min_days_since`, `min_gap` and `recontact_days` appear nowhere in `src/` outside reporting buckets in `src/outcomes.py`. `config/recontact-suppression.json`, which the phase-2 brief refers to, has NEVER existed in git on any branch.

This gate decides whether a lead with manual history is contacted or held, so its absence is a send-path gap and not a reporting one. Scenario S25 exists to make it visible.

## Scenarios that surfaced it

reported across the run rather than by one scenario

## Proposal

This one needs the OPERATOR before any code: the number is a business decision and guessing it would build the wrong product. Proposal - the operator sets `recontact.manual_touch_gap_days`, and `eligibility.must_not_contact` gains a seventh check reading it, fail-closed: an ABSENT config value refuses rather than defaulting to zero, because a default of zero is the same as no gate and would look like one. Suggested starting value 30 days, matching the revival minimum CLAUDE.md already states, but the operator decides.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
