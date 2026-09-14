# TASK-021 - The LinkedIn hold code nothing produces

Operator backlog: QWEN-13. Carried as OPEN P1 in the context-reset checkpoint.

## GOAL

Make the LinkedIn state machine answer the SPECIFIC hold reason for each
branch a prospect can be in, and prove each branch with a test.

## WHY IT MATTERS

Four tests in `tests/test_the_cadence_reacts_to_what_the_prospect_did.py`
fail, and they are behavioural rather than fixture: the state machine answers
a generic `linkedin:step_requirement_unmet` where `linkedinstate.
HELD_REQUEST_OUTSTANDING` exists and NOTHING PRODUCES IT.

A constant defined and never returned is the exact shape of defect this
repository keeps finding - `PRODUCT-GAPS.md` records an evaluator that
reported INSUFFICIENT_DATA forever because nothing wrote the field it read.
Here the cost is operational: "this step cannot run" and "this step is
waiting for an invitation they have not answered" are different situations,
and an operator cannot tell them apart from the report.

It also blocks the branching the operator asked for by name:

    open profile / already connected / not connected /
    accepted / not accepted / InMail-capable / not InMail-capable

## CURRENT CONTEXT

- `src/linkedinstate.py` holds the states and the hold codes.
- `src/cadencelibrary.py` HOLDS any step naming `CAP_OPEN_PROFILE` or
  `CAP_INMAIL` because neither capability is established. A held step is
  CORRECT; a held step reported with the wrong reason is not.
- One expected failure in `tests/test_linkedinstate_redteam.py`: an
  already-connected person's `li1` returns WAIT instead of SKIP, because the
  Open Profile alternative names an unproven capability. Decide whether that
  is right and say why; do not silently flip it.
- The graph the factory now builds has two real branches - already-connected
  and not-yet-connected - and since 2026-09-14 they carry DIFFERENT cadence
  steps (`connected_1..4` against `message_2..4`). The state machine and the
  graph must agree about which branch a person is on.

## SCOPE

1. Enumerate every state a prospect can be in and, for each, the single hold
   or skip code the planner should answer. Write that table down first.
2. Make the machine produce them. `HELD_REQUEST_OUTSTANDING` is the known
   missing one; there may be others - find them by asking which constants are
   never returned.
3. A test per branch, asserting on WHAT THE PLANNER RETURNS. Not on source
   text, and not on the constant existing - the constant already exists and
   that is the bug.
4. Fix the four failing tests, or establish that the tests are wrong and say
   why. Do not weaken them.

## THE DISTINCTION THAT DECIDES THIS TASK

"We cannot do this step" / "we are waiting for them" / "this no longer
applies" are three answers. Collapsing them into one generic code is what
this task removes, so do not introduce a new generic code to replace it.
Unknown must be explicit and must never look like a decision.

## FILES ALLOWED

`src/linkedinstate.py`, `src/cadencelibrary.py`, `tests/`,
`docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/providers/**`, `src/providerwrites.py`, `src/executionguard.py`,
`src/killswitch.py`, `src/heyreachfactory.py`, `work/**`.

## PRODUCTION CONSTRAINTS

ZERO network. ZERO credentials. Capability constants stay UNPROVEN - this
task does not establish Open Profile or InMail and must not mark either as
available. If a branch needs a capability we do not have, it HOLDS with a
reason that says so.

## TESTS REQUIRED

One per branch, behavioural. Then break each one deliberately and confirm the
intended test fails for the intended reason and that no other guard fired
first.
