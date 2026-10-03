# TASK-986: channels.email_verdict allows writing to a STOPPED contact

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

MEASURED over 90 firings. `channels.email_verdict` and `channels.linkedin_verdict` BOTH return ALLOWED for a contact whose `stopped` block is set.

The verdict functions check `operator_excluded`, `unsubscribed`, `suppressed`, `no_address` and `bounced`. They do NOT check `stopped` - the block `accountpolicy.apply_reply` writes when it honours a negative reply, an out-of-office or a not-now.

Two scenarios land on it:

- **S29**: a negative email reply (`no thanks, not for us`, classified `negative 0.80`) leaves BOTH channels reporting allowed, so `cross_channel_stop` is False.
- **S24**: an out-of-office stops the contact - `stopped.reason` is `not_now`, which this run confirms matched - and the email channel still reports allowed.

The stop IS enforced: `eligibility.must_not_contact` returns `blocked:contact_stopped`, channel-agnostically, and that is what makes this a severity question rather than an open door. But it means the cross-channel stop rests on ONE authority, and any caller that asks `channels` instead of `eligibility` - which is the question `channels` exists to answer - gets the wrong answer.

## Scenarios that surfaced it

reported across the run rather than by one scenario

## Proposal

Add a `_stopped(rec, contact)` check to the shared preamble in `channels`, returning a new `channels.STOPPED` reason, positioned AFTER `unsubscribed` and `suppressed` so a removal request is still reported as itself rather than as a generic stop.

Do NOT re-derive the stop from event text - read the `stopped` block that `accountpolicy.apply_reply` wrote. That is the discipline `eligibility._replied` already follows, and for the reason its docstring gives: a gate that classified the text again would be a second implementation of the one rule that must not have two.

Then enumerate the callers of `email_verdict` and `linkedin_verdict` and check each for whether it also asks `eligibility`. Acceptance: after the fix S24 and S29 both report `cross_channel_stop: true` from `channels` alone, and S01's removal request still reports `unsubscribed` rather than `stopped`.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
