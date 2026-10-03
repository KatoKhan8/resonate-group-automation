# TASK-984: The operator's positive metric collapses into `unknown` in CLASSIFIER_OUTCOME

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

The operator's metric from 2026-10-03 is the POSITIVE REPLY: explicit interest or a request for more - `positive`, a meeting, or a question about the offer.

`accountpolicy.CLASSIFIER_OUTCOME` maps:

- `question` -> `unknown`
- `meeting_intent` -> `unknown`
- `interested` -> `unknown`
- `objection` -> `unknown`
- `send_info` -> `unknown`

So TWO of the three things the operator calls a positive produce NO account outcome, and per TASK-941 an `unknown` reaches no human at all. The system's headline metric is partly invisible to the system. Scenario S15 asserts that a question counts as a positive and the classifier agrees - `replies.classify` returns `question` - but the outcome map discards it one step later.

## Scenarios that surfaced it

reported across the run rather than by one scenario

## Proposal

Do NOT widen `unknown`. Add the mapping the metric needs: `question`, `meeting_intent` and `interested` map to a new `accountpolicy.INTERESTED` outcome whose plan HOLDS the account and routes to a human, which is what a positive already does. Keep `objection` and `send_info` where they are - the operator said in terms that "send me information and I will see" is not positive. Then `notify.positive_reply` fires for the whole metric and not for a third of it. The acceptance test is S09 and S15 together: both must reach a human, and `send_info` and `referral` must not.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
