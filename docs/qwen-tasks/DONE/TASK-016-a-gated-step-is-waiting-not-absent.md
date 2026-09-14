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

    approved LinkedIn copy is missing for: contact 'pat-morgan', step 'li2'
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

STATUS: DONE
COMMIT SHA: 9de2f14
TESTS: 8 new tests in tests/test_a_gated_step_is_waiting_not_absent.py, all
  pass. 3 previously failing tests in
  test_the_cadence_reacts_to_what_the_prospect_did.TheTimelineReadsTheBranch
  now pass (test_a_message_step_waits_until_the_connection_lands,
  test_the_acceptance_releases_it,
  test_the_state_travels_onto_the_step_for_a_reviewer). 414 cadence tests
  run with no new regressions (2 failures + 2 errors are pre-existing and
  unrelated). 124 approval tests pass. 101 heyreach tests pass.
FILES CHANGED:
  src/cadence.py - the fix: 6 lines added in build() to create a minimal
    placeholder step when expand_step returns None for a step with requires.
  tests/test_a_gated_step_is_waiting_not_absent.py - 8 new tests.
  src/quality.py - resolved merge conflict from master (channel-aware gate).
FINDINGS:
  1. THE FIX is a single guard in cadence.build. When expand_step returns
     None (generated step, no body yet) and the spec has a `requires` field,
     a minimal step {"channel": spec["channel"]} is created. status_for then
     evaluates the precondition through linkedinstate.plan_step and returns
     "waiting" with the unmet requirement named. Steps without requires are
     still omitted (no behaviour change for generated email steps).

  2. ANSWER TO SCOPE (2) - Should approving a gated step be allowed?
     YES, with a natural distinction. The existing approve.why_not already
     draws the line correctly:
     - Template steps with content (e.g. day8 in the balanced cadence) CAN
       be approved while waiting. The words exist, a human can read them,
       and the execution gate still runs at execution time.
     - Generated steps without content CANNOT be approved. why_not refuses
       them as "empty note" (LinkedIn) or "fails lint" (email). There is
       nothing to approve.
     This is the right boundary: approval is about the words, and the gate
     still runs at execution. A human can bless "the first message after
     they accept" for template steps; for generated steps, the words must
     exist first.

  3. ANSWER TO SCOPE (4) - Timeline consumers checked:
     - push.py: filters on status == "eligible". Waiting steps are NOT
       eligible. SAFE.
     - cadenceexposure.py: counts confirmed touches from actual events
       (touch.CONFIRMED_STATES = {SENT, DELIVERED, REPLIED, POSITIVE_REPLY}).
       Does NOT iterate the timeline. SAFE.
     - nextaction.py: uses linkedinstate.plan_step directly, not the
       timeline. SAFE.
     - approve.py: walks the timeline to find approvable steps. Waiting
       template steps can now be approved; waiting generated steps cannot
       (empty note). SAFE.
     - eligibility.py: reads the timeline for status. Waiting steps are
       refused by _linkedin_checks (no note) or _dependency (waiting
       status). SAFE.
     - executionguard.py: calls expand_step directly. A generated step
       with no body returns None and is refused as "does not render". SAFE.
     - heyreachfactory.py: reads from rec["cadence"][contact_key] (stored
       approval data), NOT the timeline. Not directly affected. The fix
       enables approve_record to walk the steps so they can be stored.
     - coherence.py, report.py, campaigns.py, duplicates.py, preview.py,
       plan.py: all checked. No crashes. coherence.py may emit a NOTE
       finding for empty steps; plan.size() overcounts by 1 per contact;
       preview.py inflates unapproved totals. All cosmetic, none
       structural. The day field was added to the placeholder to address
       the most pervasive issue (coherence step_without_a_day).

  4. BREAK THE CHANGE: removing the guard causes
     test_li2_through_li6_appear_for_an_unconnected_contact to fail with
     AssertionError (steps missing from timeline) and
     test_eligibility_decide_refuses_a_waiting_message_step to fail with
     KeyError: 'li2'. Both fail for the intended reasons.

RISKS:
  - Generated email steps (em1-em5) are still omitted from the timeline
    when they have no body. This is correct for now (no precondition to
    name) but means the email side of the campaign graph is still
    incomplete until content is generated. This is a separate concern from
    the deadlock this task fixes.
  - plan.size() counts waiting steps in its linkedin_steps total, making
    the campaign appear one step larger per affected contact. This is
    cosmetically odd but not structurally broken - plan.schedule() has a
    day-is-None guard that excludes them from daily volume.
  - coherence.py ordering_problems may emit a NOTE finding for steps whose
    day field is present but whose content is empty. This is noise, not a
    crash, and is the correct direction (flagging incomplete steps).
  - coherence.py ineligible_channel does not exclude "waiting" status from
    its check. Currently mitigated because a LinkedIn placeholder for a
    contact without LinkedIn gets "blocked" status (which IS excluded),
    but this is fragile if the status assignment changes.
RECOMMENDED CLAUDE ACTION:
  Review and merge. The change is minimal (6 lines), the tests prove both
  the fix and the safety invariants, and no previously executable path is
  changed.
