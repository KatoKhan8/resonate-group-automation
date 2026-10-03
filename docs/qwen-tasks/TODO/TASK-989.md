# TASK-989: No rule decides which DM on an account is approached first, second or third

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

The brief predicted this and the run confirms it. 300 accounts x 3 DMs = 900 contacts, and NOTHING in the codebase decides the order in which an account's contacts are approached.

`collision.account_policy` answers whether the account may be touched at all - allow, hold, stop, unknown - which is a different question. `accountpolicy.account_state` answers whether the account is held. `assignment.describe` answers which sender a contact is bound to. None of them answers "of the three decision-makers at this account, who do we write to first, and what happens to the other two while we wait".

The simulation therefore works them in RECORD ORDER, which is an arbitrary choice made by the harness. That matters because the choice is not cosmetic: `ACCOUNT-OUTREACH.md` makes the account the unit of outreach, and a champion and an economic buyer are measurably different populations - `out_of_office` is 25.3% of a champion's replies against 6.2% of an economic buyer's, and `unsubscribe` runs 15.2% against 25.6%. Approaching the economic buyer first spends the account's goodwill on the persona most likely to unsubscribe.

## Scenarios that surfaced it

reported across the run rather than by one scenario

## Proposal

ONE function, and it decides order only - never permission. Proposal: `accountpolicy.contact_order(rec, config)` returns the account's contacts ranked, with the reason for the ranking, and it reads only canonical state: persona, verification confidence, and whether that contact already carries a touch. It must NOT re-answer eligibility - every contact it returns still goes through `must_not_contact` and `executionguard` unchanged, so the ranking can never widen what may be sent.

The second question needs the operator, not code: while DM #1 is mid-sequence, may DM #2 be approached in parallel, or does the account hold? `PRODUCTION-SCALE-POLICY.md` says a campaign is a cohort and never a person, which implies parallel, but the cross-channel stop and the fatigue check both reason per account. Guessing it would build the wrong product.

Acceptance: a test that two accounts with identical contacts in different record order produce the SAME ranking - because if record order still decides, nothing was fixed.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
