# TASK-008 - A removed connection is not a connection

## GOAL

Make `src/linkedinstate.py` stop reporting somebody as connected after they
have removed the connection, and turn the two expected failures that prove it
into passing tests.

## WHY IT MATTERS

This is the one real defect TASK-003 found, and it is on a send path. Once
`linkedin_connected` is in a record's event log the state is
`CONNECTION_ACCEPTED` regardless of what the provider says afterwards, because
there is no event type for a removal and no observation path that overrides
an event-log acceptance. So a message step would GO to somebody who is no
longer reachable, and the send would fail at the provider for a reason the
planner had already decided could not happen.

It is also the same shape as three other things found on 2026-09-13: a stale
local fact outranking live provider truth. `PLAYBOOK.md` is explicit that a
message may only claim what the event log supports, and the corollary is that
the event log may not outrank what the provider is saying now.

## CURRENT CONTEXT

`tests/test_linkedinstate_redteam.py` already carries the two failing cases
as expected failures:

    test_a_removed_connection_should_not_be_reported_as_accepted
    (and its sibling - read the file)

They are marked `expectedFailure` because TASK-003 forbade touching `src/`.
This task lifts that: you may change `src/linkedinstate.py`.

The module ALREADY does the right thing in the neighbouring case, and that is
the precedent to follow rather than invent from: when the provider reports
`open_profile`, the observation wins over an acceptance in the event log.
TASK-003 locked that with `test_open_profile_observation_wins_over_event_log`.
A removal is the same question with a different answer.

Read `docs/qwen-tasks/DONE/TASK-003-linkedinstate-redteam.md` first. It says
exactly what the machine does today and what it should do.

## SCOPE

1. Decide, and write down, what the machine should answer when the provider
   reports NOT_CONNECTED after an event-log acceptance. Consider at least:
   is it `CONNECTION_NOT_ACCEPTED`, or a distinct state? They are different
   facts - one person never accepted, the other accepted and left - and
   `CADENCE-MODEL.md` cares about that distinction because the InMail
   fallback fires on one of them.
2. Implement the smallest change that makes the observation override the
   stale acceptance, following the Open Profile precedent.
3. Remove the `expectedFailure` markers and make both tests pass.
4. Prove you have not broken the locked behaviours: all 22 must still pass,
   and `test_open_profile_observation_wins_over_event_log` in particular.
5. Prove the change is CONSUMED. A state the planner does not read is a
   state that changes nothing. Trace it to `plan_step` and add a test that
   the message step does NOT go for a removed connection.

## FILES ALLOWED

`src/linkedinstate.py`, `tests/test_linkedinstate_redteam.py`,
`docs/qwen-tasks/`.

## FILES FORBIDDEN

Every other `src/` file - if the fix appears to need one, that is a finding
and a design question, not a licence. `work/**`. `config/**`.

## PRODUCTION CONSTRAINTS

Offline. No provider calls. This module must keep importing no provider -
`test_it_imports_no_provider` asserts it and a state machine that fetched its
own evidence would spend on every screen refresh.

## TESTS REQUIRED

- The two expected failures, passing, with the markers gone.
- One test that the PLANNER refuses the message step, not merely that the
  state string changed. Existence is not function.
- All 25 in the red-team module still green.
- Break your own fix and confirm the intended test fails for the intended
  reason and that a different guard did not fire first.

## EXPECTED OUTPUT

The change, the tests, and a written answer to (1) - which state, and why
that one rather than `CONNECTION_NOT_ACCEPTED`.

## DONE CONDITION

A record whose provider reading says NOT_CONNECTED after an acceptance is not
planned a message, and a test proves it at the planner rather than at the
state string.

## RESULT

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
