# TASK-983: Two authorities disagree on the revival cooling window: 90 and 30

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

`revival.DEFAULTS['cooling_days']` is **90**. CLAUDE.md rule 2 says a revival needs a *minimum 30 days since our last touch*. Both are current, both are authoritative in their own place, and they differ by a factor of three.

This is the defect class this repository has already paid for twice: two authorities for one number. The last time, the writer contract and a thread-reply range intersected to exactly ONE legal word count. Here the consequence is a whole cohort either released 60 days early or held 60 days late. Scenarios S06 and S23 report it and cannot resolve it.

## Scenarios that surfaced it

reported across the run rather than by one scenario

## Proposal

ONE authority. Proposal: `revival.DEFAULTS['cooling_days']` is the authority, because it is the value code actually reads, and CLAUDE.md is corrected to match it rather than the reverse - a document that disagrees with the code is the thing to fix. If the operator wants 30, the config changes and CLAUDE.md stays; either way the number exists in ONE place afterwards and `revival` reads it. Add a test that fails if any document under `docs/` or `CLAUDE.md` states a cooling figure that differs from the config.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
