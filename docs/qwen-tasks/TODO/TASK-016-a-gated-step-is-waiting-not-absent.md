# TASK-016 - A gated step is waiting, not absent

## GOAL

`cadence.build` should surface a step whose precondition has not been met
with a status saying so, instead of leaving it out of the timeline entirely.

## WHY IT MATTERS - IT IS BLOCKING THE HEYREACH CAMPAIGN

Measured 2026-09-14 on `ogpartner-dk`:

    LinkedIn notes STORED on the record:  li1 li2 li3 li4 li5 li6
    of those, APPROVED:                   li1
    steps the TIMELINE surfaces:          li1

All six notes are written. Five of them can never be approved, because
`approve.approve_record` walks the TIMELINE and the timeline does not contain
them - li2..li6 all carry `requires: CONNECTED` and the contact is not
connected, so `cadence.build` omits them.

`heyreachfactory` then refuses, correctly:

    approved LinkedIn copy is missing for: contact 'brooke-baron', step 'li2'
    -> role 'connected_1'; step 'li3' -> role 'message_3'; ...

**This is a deadlock, and it is the whole reason no HeyReach campaign can be
built.** The provider graph is written ONCE, before anybody is in it, and it
must contain every message including the post-connection ones. The approval
model gates those messages on a connection that cannot happen until the graph
exists and the campaign runs.

It is also the same defect reported hours earlier from the other direction:
`test_the_cadence_reacts_to_what_the_prospect_did` expects `li2` present with
status `waiting` and gets `KeyError: 'li2'`. Two independent paths found the
same hole.

## THE DISTINCTION THAT MATTERS

Omitted and waiting are different answers to a reviewer.

- **Waiting** says: this step exists, here are its words, it will run when the
  connection lands, and you may approve the words now.
- **Omitted** says nothing at all, and a cadence that quietly drops five of
  six steps reports eleven touches and sends one. `cadencelibrary.py`'s own
  docstring warns about exactly this.

Approving words is not the same act as executing a step. A human can read and
bless "the first message after they accept" today; whether it ever runs is
decided at execution time by `linkedinstate` and `eligibility`, which already
do that job and must keep doing it.

## SCOPE

1. `cadence.build` includes a step whose `requires` is unmet, with a status
   that names the unmet precondition. Do not invent a new vocabulary if one
   exists - `cadencesafety.HELD`, the existing `status` values and
   `linkedinstate`'s hold codes are the words already in use.
2. `approve.approve_record` and `approve.pending` may then offer it. Decide
   whether approving a gated step is allowed and say why. The argument for:
   the words are the thing being approved and the gate still runs at
   execution. The argument against: a reviewer might read "approved" as
   "will be sent".
3. **Nothing may become executable that was not executable before.**
   `eligibility.decide` and `executionguard` must still refuse a message
   step for an unconnected contact. Prove that with a test, because this
   change makes a previously invisible step visible and the whole risk is
   that visible gets mistaken for allowed.
4. Check what else walks the timeline and would now see more steps -
   `push.run`, `nextaction`, the reports, `cadenceexposure`. A step counted
   as a touch because it appeared in a timeline would be a fabricated
   exposure.

## FILES ALLOWED

`src/cadence.py`, `src/approve.py`, `tests/**`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/linkedinstate.py` and `src/eligibility.py` - the execution gates do not
change. `src/executionguard.py`. `work/**`. `config/**`.

## PRODUCTION CONSTRAINTS

Offline. No provider calls. HeyReach 599020 and 594061 are off limits;
EmailBison 481 holds fourteen live leads and 451 has a scheduled send.

## TESTS REQUIRED

- `cadence.build` surfaces `li2`..`li6` for an unconnected contact, with a
  status naming the unmet requirement. This also fixes
  `test_the_cadence_reacts_to_what_the_prospect_did`'s `KeyError: 'li2'`.
- A connected contact's `li1` is still `skipped` - already-connected people
  do not get a connection request.
- **`eligibility.decide` still refuses a message step for an unconnected
  contact, and `executionguard` still refuses to authorize it.** This is the
  test that matters most; write it first.
- Counting: the number of steps reported as CONFIRMED TOUCHES does not
  change. A waiting step is not an exposure.
- Break the change and confirm the intended tests fail for the intended
  reasons.

## EXPECTED OUTPUT

The change, the tests, your answer to (2), and a list of every timeline
consumer you checked under (4) with what you found.

## DONE CONDITION

`heyreachfactory.stage` can assemble a full six-step LinkedIn graph from a
record whose contact has not connected yet, and nothing that could not be
sent before can be sent now.

## RESULT

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
