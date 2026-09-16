# Lead Variable Stale Clearing, 2026-09-16

## The defect

Campaign 485 had ten leads at EmailBison carrying `subject_4`,
`subject_5`, `body_4` and `body_5` from a five-step era while the
campaign's sequence had been reduced to three steps. The activation
was stopped because the corrected comparator found the leads held the
OLD model-generated copy, not the approved CONTROL copy.

## Root cause

`_variables_for(lead, campaign)` in `src/bisonfactory.py` builds the
wanted variable set by enumerating the lead's copy and numbering it
from 1. A three-step campaign therefore names `subject_1..3` and
`body_1..3` and nothing else.

`_ensure_leads` then computes stale variables as:

    stale = [v for v in wanted_vars if held.get(v["name"]) != v["value"]]

`subject_4`, `subject_5`, `body_4` and `body_5` are not in
`wanted_vars`, are never compared, and are never cleared. They survive
from the five-step era indefinitely.

## The fix

`_stale_clearances(sequence)` returns explicit empty-valued entries
for every numbered position above the sequence length up to
`MAX_SEQUENCE_STEPS` (currently 6). `_ensure_leads` merges them into
the wanted set before the stale comparison, so the reconciliation
writes `""` for each one.

The provider PATCH merges custom variables rather than replacing the
set, so an empty value is stored and the template never reads a
variable its sequence does not declare.

## Mechanism

The clearing is done via `bison.update_lead` with `custom_variables`
entries carrying `value: ""`. The provider has no delete route for
individual custom variables on a lead; an empty value that the
template never reads is the correct clearance.

## What was NOT changed

- `_variables_for` still drops empty values via `bison._variables`.
  The clearances are computed separately and merged only in the
  reconciliation path, not in the create path.
- `_ensure_leads`' empty-copy refusal is unchanged. A lead whose
  approved copy is missing for a step the sequence reads is still
  refused. The distinction is between a variable the sequence reads
  (must be approved and non-empty) and one it does not (must be empty).
- No approval was set, cleared or re-taken.
- No campaign, lead, sequence, cap, schedule or sender was created or
  modified.

## Regression test

`tests/test_lead_variables.py` drives `stage()` through the real
entry point with leads pre-populated at the fake provider with
five-step variables, then stages a three-step campaign and asserts
positions 4 through `MAX_SEQUENCE_STEPS` are empty. Breaking the
wiring (removing the `_stale_clearances` call) makes the test fail
with the exact defect.

## Verification

The fix was verified by:

1. Running the regression test: 10/10 pass
2. Running the broader bisonfactory test suite: 45/45 pass
3. Running the render_preview tests (which exercise `_variables_for`):
   29/29 pass
4. Breaking the wiring and confirming the regression test fails with
   the exact defect message

## Live-state access owed

The provider readback (30/30 exact matches, zero non-empty
out-of-range variables) requires live-state access to campaign 485's
ten leads. This worktree does not hold `work/queue.jsonl` and the
readback is Claude's to run from Claude's worktree after reviewing
this change.
