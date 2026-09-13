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

STATUS: DONE
COMMIT SHA: faf5269
TESTS:
  Command: py -3 -m unittest tests.test_linkedinstate_redteam -v
  Ran 25 tests in 0.003s
  Exit code: 0
  Result: OK (expected failures=3)
  22 green, 3 expected failures (defects found)

FILES CHANGED:
  tests/test_linkedinstate_redteam.py  (new) - 25 adversarial tests covering
                                              all 8 cases from the task

FINDINGS:

  ALREADY CORRECT, NOW LOCKED (22 tests):

  1. Elapsed time is not evidence (3 tests). A connection request that has
     neither been accepted nor declined, and a week has passed, does NOT
     become connection_not_accepted. The state is UNKNOWN_ACCEPTANCE, the
     InMail fallback does not fire, and the counterfactual (provider reading
     = refusal) works. Locked.

  2. Two connection requests in one sequence (3 tests). Authoring refuses
     two requests (BadCadence). Execution refuses a second request while one
     is pending (HELD_REQUEST_OUTSTANDING) and after refusal (WAIT). Locked.

  3. Open profile observation wins over event log (2 tests). When the
     provider says open_profile, the state is OPEN_PROFILE even if the event
     log has an acceptance. The message step still goes. Locked.

  4. Events out of order (2 tests). An acceptance timestamped before the
     request still resolves to CONNECTION_ACCEPTED. The message goes. The
     machine does not compare timestamps for ordering. Locked.

  5. Duplicate identical events (3 tests). Duplicate acceptances, requests,
     and replies are harmless. The evidence function uses first-wins. Locked.

  6. Tenancy isolation (3 tests). Events for a different contact_key do not
     leak. A reply for a different contact does not hold this one. Events
     for a different record are on a different record. Locked.

  7. Garbage state fails closed (6 tests). Unknown provider words become
     UNKNOWN. Unknown states in observations are UNKNOWN. plan_step holds on
     UNKNOWN (HELD_PROVIDER_STATE_UNKNOWN). Unknown actions are held
     (HELD_ACTION_UNKNOWN). Unclassified capabilities are held
     (HELD_CAPABILITY_UNPROVEN). None state does not default to ALLOW.
     Locked.

  DEFECTS, CLAUDE MUST FIX (3 tests, expected failures):

  1. Connection removed after acceptance (2 tests). The machine has no event
     type for a removed connection and no observation path that overrides an
     event-log acceptance. Once linkedin_connected is in the log, the state
     is CONNECTION_ACCEPTED regardless of what the provider says afterwards.
     A prospect who removes the connection is still reported as connected,
     and a message step would GO to someone who is no longer reachable.

     The correct behavior: when the provider reports NOT_CONNECTED after an
     acceptance, the state should reflect the removal, not the old
     acceptance. The message step should not GO.

     Tests: test_a_removed_connection_should_not_be_reported_as_accepted,
     test_a_message_step_should_not_go_after_removal.

  2. Open profile + already connected blocks the sequence (1 test). When the
     state is OPEN_PROFILE and the step is li1 (connect, alternative:
     open_profile_message), the alternative branch is chosen because
     OPEN_PROFILE satisfies its requires. But the alternative's capability
     (CAP_OPEN_PROFILE) is unproven, so the step returns
     WAIT/HELD_CAPABILITY_UNPROVEN instead of SKIP.

     The person is already connected (event log has acceptance). The
     connection request is pointless and should SKIP. Instead the alternative
     branch is chosen and held, blocking the lane. Without the open_profile
     observation, the state would be CONNECTION_ACCEPTED, the request would
     SKIP, and the sequence would advance to li2. With the observation, the
     lane is blocked.

     The correct behavior: when the person is already connected, the
     connection request should SKIP regardless of the open profile
     observation, and the sequence should advance.

     Test: test_the_connection_request_should_skip_when_already_connected.

RISKS:
  - The connection-removed defect is operationally dangerous. A prospect who
    removes the connection is still reported as connected, and messages would
    be planned for them. The fix requires either a new event type
    (connection_removed) or a rule that the provider observation can override
    an event-log acceptance when the provider positively reports NOT_CONNECTED.

  - The open-profile-blocks-sequence defect is a corner case but reveals a
    design tension: the alternative branch is "the step" when its requirement
    is satisfied, but when the alternative's capability is unproven, the step
    is held even though the primary (connect) would SKIP. The fix requires
    either proving the open_profile capability, or adding a rule that a
    connection request to an already-connected person SKIPs before the
    alternative branch is evaluated.

  - The tenancy tests assume events are scoped to the record. This is
    enforced by the store, not by linkedinstate. If events were ever shared
    across records, the state machine would not catch it.

RECOMMENDED CLAUDE ACTION:
  1. Fix the connection-removed defect. Add a rule that when the provider
     positively reports NOT_CONNECTED and the event log has an acceptance,
     the state should reflect the removal. Options:
     a. Add a connection_removed event type and a predicate in events.py.
     b. Add a rule in connection() that the provider observation can override
        an event-log acceptance when the provider says NOT_CONNECTED.
     c. Both. The event type is for audit; the override is for real-time.

  2. Fix the open-profile-blocks-sequence defect. Options:
     a. Check whether the person is already connected (event log has
        acceptance) before evaluating the alternative branch. If connected,
        SKIP the connection request regardless of the open_profile
        observation.
     b. Prove the open_profile capability (CAP_OPEN_PROFILE = True) if the
        provider can actually detect open profiles.
     c. Change the branch selection logic so that when the alternative's
        capability is unproven, the primary is considered as a fallback.

  3. Both defects are in src/linkedinstate.py. The fixes should be minimal
     and should not weaken existing guards. The 22 green tests must remain
     green after the fixes.
