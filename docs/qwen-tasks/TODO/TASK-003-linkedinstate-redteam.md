# TASK-003 - Red-team the cross-channel state machine

## GOAL

Break `src/linkedinstate.py` on paper, then leave behind the tests that stop
it being broken again.

## WHY IT MATTERS

It decides whether a LinkedIn message step may run. A wrong ALLOW messages
somebody who never connected; a wrong HOLD silently shortens a cadence that
reports its full length. Both are invisible in a green suite that never asked.

## CURRENT CONTEXT

`src/linkedinstate.py` was committed at `8990225` and is wired into
`src/cadence.py` and `src/nextaction.py`. The states are in
`src/cadencelibrary.py`: `open_profile`, `connected`, `connection_accepted`,
`connection_not_accepted`.

CLAUDE.md: "time passing is not a decline". A clock never produces evidence.
"One connection request per person per sequence, enforced at execution time
as well as at authoring time."

## SCOPE

Adversarial cases, each as a test:

1. A connection request that has neither been accepted nor declined, and a
   week has passed. Assert this does NOT become `connection_not_accepted` on
   the strength of elapsed time alone.
2. Accepted, then the connection is removed. What does the machine say?
3. Two connection requests attempted for one person in one sequence.
4. An `open_profile` prospect who is ALSO already connected.
5. Events arriving out of order (accept timestamped before the request).
6. Duplicate identical events.
7. An event for a person who belongs to a different client (tenancy).
8. Unknown/garbage state string - must fail closed, never default to ALLOW.

For each: if the machine already handles it, the test locks it in. If it does
NOT, write the test as an expected-failure with a clear name and record it
under FINDINGS. Do not fix `src/**` in this task.

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/**`. Report defects; Claude fixes them. `work/**`.

## PRODUCTION CONSTRAINTS

Offline. Synthetic events only. No real prospect data - construct fixtures.

## TESTS REQUIRED

All eight above. Each must be shown to fail when the guard it covers is
removed, for the intended reason and not because a different guard fired
first.

## EXPECTED OUTPUT

One test module, plus a FINDINGS list separating "already correct, now
locked" from "defect, Claude must fix".

## DONE CONDITION

Every one of the eight has a named test and a recorded verdict.

## RESULT

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
