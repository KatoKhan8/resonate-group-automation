# TASK-987: A referral is classified not_relevant and becomes BLOCKED FOREVER

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

MEASURED, 3 of 3 firings of S13. The reply

> wrong person, speak to our head of operations instead

classifies **`not_relevant 0.80`**, which `accountpolicy.CLASSIFIER_OUTCOME` maps to **`not_icp`** - a terminal refusal. A warm introduction to the right person inside a qualified account becomes a permanent block on that account.

Two measured causes, and both matter:

1. **RULES ORDER.** `not_relevant` sits at position 4 of 13 and `referral` at position 12, so a reply matching both is read as the refusal.
2. **`_points_at_somebody`.** `classify_rules` discards a referral hit unless `referral.evidence` finds a name, an email or a profile. That guard is CORRECT - a hand-off cue alone is the half that produces false positives - but it means a ROLE-based referral ("our head of operations", "whoever owns billing") names nobody and falls through. Probed separately: with a name present the same sentence classifies `referral 0.80` as intended, so the guard is doing exactly what it says.

The defect is therefore NOT the guard. It is that a sentence which is unmistakably a hand-off, but names a role rather than a person, is read as "you are not relevant to us".

## Scenarios that surfaced it

reported across the run rather than by one scenario

## Proposal

Do NOT widen `referral` and do NOT weaken `_points_at_somebody`. Add a third state.

When a referral CUE matches and `_points_at_somebody` finds nobody, return a new `replies.REFERRAL_UNNAMED` classification at low confidence, mapped to an `accountpolicy` outcome that HOLDS and routes to a human rather than refusing - because a person can read "speak to our head of operations" and find them, and no regex can.

That also requires the `not_relevant` rule to stop claiming "wrong person": `wrong_person` is already its own `accountpolicy` outcome and a distinct thing from "not relevant".

Acceptance: S13 reports a hold and a route rather than `not_icp`, and every existing not-relevant test passes unchanged. Sweep the 899-reply corpus and report the verdict delta as a NAMED SET.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
