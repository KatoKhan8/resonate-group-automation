"""Red-team the LinkedIn cross-channel state machine.

TASK-003. Eight adversarial cases designed to break `src/linkedinstate.py`
on paper. For each: if the machine already handles it, the test locks it in.
If it does not, the test is an expected-failure with a clear name and the
defect is recorded under FINDINGS.

No src/** changes. No real prospect data. Synthetic fixtures only.
"""
import unittest

from src import cadence, cadencelibrary as cl, events
from src import linkedinstate as ls

KEY = "brooke"
REQUEST_AT = "2026-09-01T09:00:00+00:00"
PAST_WINDOW = "2026-09-20T09:00:00+00:00"
INSIDE_WINDOW = "2026-09-03T09:00:00+00:00"
LI_STEPS = cl.PRODUCTIVE_LI_HEAVY_V1
REQUEST_STEP = next(s for s in LI_STEPS if ls.action_of(s) == ls.CONNECT)
MESSAGE_STEP = next(s for s in LI_STEPS if s["key"] == "li2")
FORK_STEP = next(s for s in LI_STEPS if s["key"] == "li3")


def _record(events_=(), contact_key=KEY):
    return {"id": "acme", "client": "productive", "domain": "acme.test",
            "contacts": [{"key": contact_key, "name": "Brooke Baron",
                          "linkedin": f"https://www.linkedin.com/in/{contact_key}"}],
            "events": list(events_)}


def _request(step="li1", at=REQUEST_AT, contact=KEY):
    return {"type": events.PUSH_MARKED, "contact": contact,
            "channel": "linkedin", "step": step, "at": at}


def _accepted(at="2026-09-02T09:00:00+00:00", contact=KEY):
    return {"type": events.LINKEDIN_CONNECTED, "contact": contact, "at": at}


def _replied(channel="email", at="2026-09-02T09:00:00+00:00", contact=KEY):
    return {"type": events.REPLY_RECEIVED, "contact": contact,
            "channel": channel, "at": at}


def _state(rec, observed=None, at=PAST_WINDOW):
    return ls.connection(rec, rec["contacts"][0], observed=observed,
                         steps=LI_STEPS, at=at)


def _move(rec, spec, observed=None, at=PAST_WINDOW, config=None):
    return ls.plan_step(rec, rec["contacts"][0], spec, observed=observed,
                        steps=LI_STEPS, config=config, at=at)


# ----------------------------------------------------------------------- 1
# A connection request that has neither been accepted nor declined, and a
# week has passed. Must NOT become connection_not_accepted on the strength
# of elapsed time alone.

class ElapsedTimeIsNotEvidence(unittest.TestCase):

    def test_a_week_of_silence_does_not_become_a_refusal(self):
        rec = _record([_request()])
        result = _state(rec, at=PAST_WINDOW)
        self.assertNotEqual(result["state"], ls.CONNECTION_NOT_ACCEPTED,
                            "elapsed time alone must not produce a refusal")
        self.assertEqual(result["state"], ls.UNKNOWN_ACCEPTANCE)

    def test_the_inmail_fallback_does_not_fire_on_elapsed_time(self):
        rec = _record([_request()])
        move = _move(rec, FORK_STEP, at=PAST_WINDOW)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_ACCEPTANCE_UNREAD)
        self.assertNotEqual(move["action"], ls.INMAIL,
                            "an InMail must not fire on elapsed time alone")

    def test_the_counterfactual_a_provider_reading_is_a_refusal(self):
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent", source="test")
        result = _state(rec, observed=observed, at=PAST_WINDOW)
        self.assertEqual(result["state"], ls.CONNECTION_NOT_ACCEPTED)


# ----------------------------------------------------------------------- 2
# Accepted, then the connection is removed. What does the machine say?

class ConnectionRemovedAfterAcceptance(unittest.TestCase):

    def test_a_removed_connection_should_not_be_reported_as_accepted(self):
        """A provider-reported removal overrides the event-log acceptance.
        The state is NOT_CONNECTED - not CONNECTION_NOT_ACCEPTED, because
        the latter would fire the InMail fallback, and InMail is for a
        refused request, not a removed connection."""
        rec = _record([_request(), _accepted()])
        observed = ls.observation(state=ls.NOT_CONNECTED, source="test")
        result = _state(rec, observed=observed)
        self.assertNotEqual(result["state"], ls.CONNECTION_ACCEPTED,
                            "a provider-reported removal should override "
                            "the event-log acceptance")
        self.assertEqual(result["state"], ls.NOT_CONNECTED)

    def test_a_message_step_should_not_go_after_removal(self):
        """The operational consequence: a message is NOT planned for a
        person who is no longer connected. Proved at the planner, not
        merely at the state string. The code is HELD_REQUIRES_UNMET
        because the requirement check fires before the action-specific
        message branch - the step requires CONNECTION_ACCEPTED and the
        state NOT_CONNECTED does not satisfy it."""
        rec = _record([_request(), _accepted()])
        observed = ls.observation(state=ls.NOT_CONNECTED, source="test")
        move = _move(rec, MESSAGE_STEP, observed=observed)
        self.assertNotEqual(move["status"], ls.GO,
                            "a message should not go to a removed connection")
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REQUIRES_UNMET)


# ----------------------------------------------------------------------- 3
# Two connection requests attempted for one person in one sequence.

class TwoConnectionRequestsInOneSequence(unittest.TestCase):

    def test_authoring_refuses_two_requests(self):
        doubled = list(LI_STEPS[:2]) + [
            {"key": "li_extra", "day": 5, "channel": "linkedin",
             "linkedin_action": "connect", "capability": cl.CAP_CONNECT,
             "template": "linkedin_intro"}]
        with self.assertRaises(cadence.BadCadence):
            cadence.validate_steps(doubled)

    def test_execution_refuses_a_second_request_while_one_is_pending(self):
        rec = _record([_request()])
        move = _move(rec, REQUEST_STEP, at=INSIDE_WINDOW)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REQUEST_OUTSTANDING)

    def test_execution_refuses_a_second_request_after_refusal(self):
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent", source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["status"], ls.WAIT)


# ----------------------------------------------------------------------- 4
# An open_profile prospect who is ALSO already connected.

class OpenProfileAndAlreadyConnected(unittest.TestCase):

    def test_the_open_profile_observation_wins_over_the_event_log(self):
        """The observation is provider truth and outranks the plan. An open
        profile observation returns OPEN_PROFILE even when the event log
        has an acceptance. The state label loses the acceptance fact, but
        the person IS reachable so the decision is not unsafe."""
        rec = _record([_request(), _accepted()])
        observed = ls.observation(open_profile=True, source="test")
        result = _state(rec, observed=observed)
        self.assertEqual(result["state"], ls.OPEN_PROFILE)

    def test_the_message_step_still_goes(self):
        rec = _record([_request(), _accepted()])
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, MESSAGE_STEP, observed=observed)
        self.assertEqual(move["status"], ls.GO)

    @unittest.expectedFailure
    def test_the_connection_request_should_skip_when_already_connected(self):
        """DEFECT: When the state is OPEN_PROFILE and the step is li1
        (connect, alternative: open_profile_message), the alternative
        branch is chosen because OPEN_PROFILE satisfies its requires.
        But the alternative's capability (CAP_OPEN_PROFILE) is unproven,
        so the step returns WAIT/HELD_CAPABILITY_UNPROVEN instead of SKIP.

        The person is already connected (event log has acceptance). The
        connection request is pointless and should SKIP. Instead the
        alternative branch is chosen and held, blocking the lane.

        Without the open_profile observation, the state would be
        CONNECTION_ACCEPTED, the request would SKIP, and the sequence
        would advance to li2. With the observation, the lane is blocked.

        The correct behavior: when the person is already connected, the
        connection request should SKIP regardless of the open profile
        observation, and the sequence should advance."""
        rec = _record([_request(), _accepted()])
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["status"], ls.SKIP,
                         "a connection request to an already-connected "
                         "person should skip, not wait")


# ----------------------------------------------------------------------- 5
# Events arriving out of order (accept timestamped before the request).

class EventsOutOfOrder(unittest.TestCase):

    def test_an_acceptance_before_the_request_still_resolves(self):
        """The evidence function scans the event log in order and takes the
        first timestamp for each fact. If the acceptance event appears
        first in the log but both exist, the state is CONNECTION_ACCEPTED.
        The machine does not compare timestamps for ordering."""
        rec = _record([_accepted(at="2026-08-30T09:00:00+00:00"),
                       _request(at=REQUEST_AT)])
        result = _state(rec)
        self.assertEqual(result["state"], ls.CONNECTION_ACCEPTED)

    def test_the_message_goes_regardless_of_event_order(self):
        rec = _record([_accepted(at="2026-08-30T09:00:00+00:00"),
                       _request(at=REQUEST_AT)])
        move = _move(rec, MESSAGE_STEP)
        self.assertEqual(move["status"], ls.GO)


# ----------------------------------------------------------------------- 6
# Duplicate identical events.

class DuplicateIdenticalEvents(unittest.TestCase):

    def test_duplicate_acceptances_are_harmless(self):
        rec = _record([_request(), _accepted(), _accepted()])
        result = _state(rec)
        self.assertEqual(result["state"], ls.CONNECTION_ACCEPTED)

    def test_duplicate_requests_do_not_start_two_windows(self):
        rec = _record([_request(), _request(at="2026-09-02T09:00:00+00:00")])
        result = _state(rec, at=INSIDE_WINDOW)
        self.assertEqual(result["state"], ls.REQUEST_PENDING)

    def test_duplicate_replies_are_harmless(self):
        rec = _record([_request(), _accepted(), _replied(), _replied()])
        result = _state(rec)
        self.assertEqual(result["state"], ls.REPLIED)


# ----------------------------------------------------------------------- 7
# An event for a person who belongs to a different client (tenancy).

class TenancyIsolation(unittest.TestCase):

    def test_events_for_a_different_contact_key_do_not_leak(self):
        """The evidence function filters by contact_key. Events for a
        different contact on the same record do not affect this person's
        state. Tenancy is enforced at the record level: events live on
        the record, and the record belongs to one client."""
        other_key = "other_person"
        rec = _record([
            _request(contact=other_key),
            _accepted(contact=other_key),
        ])
        result = _state(rec)
        self.assertEqual(result["state"], ls.NO_EVIDENCE)

    def test_a_reply_for_a_different_contact_does_not_hold_this_one(self):
        other_key = "other_person"
        rec = _record([_replied(contact=other_key)])
        result = _state(rec)
        self.assertNotEqual(result["state"], ls.REPLIED)

    def test_events_for_a_different_record_are_on_a_different_record(self):
        """Events are stored on the record. A different record has its own
        event log. This is enforced by the store, not by linkedinstate,
        but the state machine reads only the record it is given."""
        rec = _record()
        result = _state(rec)
        self.assertEqual(result["state"], ls.NO_EVIDENCE)


# ----------------------------------------------------------------------- 8
# Unknown/garbage state string - must fail closed, never default to ALLOW.

class GarbageStateFailsClosed(unittest.TestCase):

    def test_an_unknown_provider_word_becomes_UNKNOWN(self):
        state, why = ls.from_provider_lifecycle("banana")
        self.assertEqual(state, ls.UNKNOWN)
        self.assertIn("banana", why)

    def test_an_unknown_state_in_observation_is_UNKNOWN(self):
        observed = ls.observation(state="completely_made_up")
        self.assertEqual(observed["state"], ls.UNKNOWN)

    def test_plan_step_holds_on_UNKNOWN_and_never_returns_GO(self):
        rec = _record()
        observed = ls.observation(state="completely_made_up")
        move = _move(rec, MESSAGE_STEP, observed=observed)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_PROVIDER_STATE_UNKNOWN)

    def test_an_unknown_action_is_held(self):
        rec = _record()
        bogus_step = {"key": "li_bogus", "day": 1, "channel": "linkedin",
                      "linkedin_action": "telepathy",
                      "capability": cl.CAP_CONNECT}
        move = _move(rec, bogus_step)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_ACTION_UNKNOWN)

    def test_an_unclassified_capability_is_held(self):
        rec = _record()
        step = {"key": "li_x", "day": 1, "channel": "linkedin",
                "linkedin_action": "message",
                "capability": "linkedin.telepathy"}
        move = _move(rec, step)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)

    def test_none_state_does_not_default_to_ALLOW(self):
        rec = _record()
        result = _state(rec)
        self.assertEqual(result["state"], ls.NO_EVIDENCE)
        move = _move(rec, MESSAGE_STEP)
        self.assertNotEqual(move["status"], ls.GO,
                            "a message to a cold prospect must not go")


if __name__ == "__main__":
    unittest.main()
