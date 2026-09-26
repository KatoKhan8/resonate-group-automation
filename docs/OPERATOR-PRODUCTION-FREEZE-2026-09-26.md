# OPERATOR PRODUCTION FREEZE — 2026-09-26

Standing production-safety rule, given by the operator on 2026-09-26, verbatim
in substance and to be read alongside `OPERATOR-DIRECTIVES-2026-09-25.md`,
`OPERATOR-DIRECTIVES-2026-09-26-PHASE1.md` and the morning handoff.

## WHAT IS FROZEN, from this point forward

Prospect-facing production actions require the operator's explicit **APPROVED**:

- no new campaign launches
- no new campaign activations
- no new lead/cohort enrolments or provider attachments
- no new prospect-facing sends
- no pending 50 / 63 / 128 / 825 / US / re-engagement cohort pushes
- no active campaign or provider changes for testing

## WHAT IS EXPLICITLY NOT FROZEN

Development continues normally:

Phase 1 development, the Second Brain, the Offer Engine, the five skills,
research, the copy engine, QA and gates, tests, previews, dry runs, Qwen
implementation and GLM review.

Keep committing and pushing completed development work to GitHub, and verify
the remote SHA.

## WHAT MUST NOT BE DONE BECAUSE OF THIS RULE

- **Do not interrupt, cancel, restart or reprioritise anything already
  running.** All in-flight Phase 1 / Second Brain / Offer Engine / skills / QA
  / research / Qwen / GLM work continues from its current state.
- **Do not pause or modify campaigns that were already active.** They remain in
  their current state. 493 stays ACTIVE; 491-498 and 503-505 stay as the
  handoff records them. This rule is not an instruction to pause anything.
- **Do not pause development for cost optimisation.** The model cost breakdown
  is reviewed later; it does not block Phase 1.

## THE DISTINCTION THIS RULE DRAWS

The freeze is on **prospect-facing** action, not on work. A dry run, a preview,
a generated review file, a gate result and a test are all permitted and none of
them is a send. What is refused is anything that puts a message in front of a
prospect, attaches a lead to a provider campaign, or changes the state of a
live campaign.

`reviewapproval.require` already refuses `bison.resume_campaign`,
`heyreach.activate_campaign` and, since `c3fbc106`, `attach_leads` into any
campaign in a live state. This document is the operator-level statement of the
same boundary, and it extends it to cohort pushes and to provider changes made
"for testing".

New prospect-facing launches require the operator's explicit **APPROVED**.
