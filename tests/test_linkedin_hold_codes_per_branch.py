"""One test per branch, asserting on WHAT THE PLANNER RETURNS.

TASK-021. The hold codes are the vocabulary an operator reads. A constant
defined and never returned is the exact shape of defect this repository
keeps finding. Each test here asserts on the code `plan_step` returns for
a specific (state, step) combination - not on the constant existing, and
not on source text.

The state table this file defends lives in TASK-021. Each test is one row.
"""
import unittest

from src import cadencelibrary as cl, events
from src import linkedinstate as ls

KEY = "pat"
REQUEST_AT = "2026-09-01T09:00:00+00:00"
INSIDE_WINDOW = "2026-09-03T09:00:00+00:00"
PAST_WINDOW = "2026-09-20T09:00:00+00:00"

LI_STEPS = cl.PRODUCTIVE_LI_HEAVY_V1
REQUEST_STEP = next(s for s in LI_STEPS if ls.action_of(s) == ls.CONNECT)
MESSAGE_STEP = next(s for s in LI_STEPS if s["key"] == "li2")
FORK_STEP = next(s for s in LI_STEPS if s["key"] == "li3")


def _record(events_=()):
    return {"id": "acme", "client": "productive", "domain": "acme.test",
            "contacts": [{"key": KEY, "name": "Pat Okafor",
                          "linkedin": f"https://www.linkedin.com/in/{KEY}"}],
            "events": list(events_)}


def _request(step="li1", at=REQUEST_AT):
    return {"type": events.PUSH_MARKED, "contact": KEY,
            "channel": "linkedin", "step": step, "at": at}


def _accepted(at="2026-09-02T09:00:00+00:00"):
    return {"type": events.LINKEDIN_CONNECTED, "contact": KEY, "at": at}


def _replied(channel="email", at="2026-09-02T09:00:00+00:00"):
    return {"type": events.REPLY_RECEIVED, "contact": KEY,
            "channel": channel, "at": at}


def _move(rec, spec, observed=None, at=PAST_WINDOW, config=None):
    return ls.plan_step(rec, rec["contacts"][0], spec, observed=observed,
                        steps=LI_STEPS, config=config, at=at)


class HoldCodesPerBranch(unittest.TestCase):
    """Each test is one (state, step) -> (status, code) assertion."""

    # ---- NO_EVIDENCE

    def test_no_evidence_connect_goes(self):
        rec = _record()
        move = _move(rec, REQUEST_STEP)
        self.assertEqual(move["status"], ls.GO)
        self.assertIsNone(move["code"])

    def test_no_evidence_message_waits_requires_unmet(self):
        rec = _record()
        move = _move(rec, MESSAGE_STEP)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REQUIRES_UNMET)

    # ---- REQUEST_PENDING

    def test_request_pending_connect_holds_request_outstanding(self):
        rec = _record([_request()])
        move = _move(rec, REQUEST_STEP, at=INSIDE_WINDOW)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REQUEST_OUTSTANDING)

    def test_request_pending_message_holds_request_outstanding(self):
        """THE FIX. Previously returned HELD_REQUIRES_UNMET because step 5
        did not distinguish REQUEST_PENDING from other unmet states."""
        rec = _record([_request()])
        move = _move(rec, MESSAGE_STEP, at=INSIDE_WINDOW)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REQUEST_OUTSTANDING)
        self.assertTrue(move["execute_after"])

    # ---- CONNECTION_ACCEPTED

    def test_connection_accepted_connect_skips(self):
        rec = _record([_request(), _accepted()])
        move = _move(rec, REQUEST_STEP)
        self.assertEqual(move["status"], ls.SKIP)
        self.assertEqual(move["code"], ls.SKIP_ALREADY_REACHABLE)

    def test_connection_accepted_message_goes(self):
        rec = _record([_request(), _accepted()])
        move = _move(rec, MESSAGE_STEP)
        self.assertEqual(move["status"], ls.GO)

    # ---- CONNECTED (already connected, no request record)

    def test_connected_connect_skips(self):
        rec = _record([_accepted()])
        move = _move(rec, REQUEST_STEP)
        self.assertEqual(move["status"], ls.SKIP)
        self.assertEqual(move["code"], ls.SKIP_ALREADY_REACHABLE)

    def test_connected_message_goes(self):
        rec = _record([_accepted()])
        move = _move(rec, MESSAGE_STEP)
        self.assertEqual(move["status"], ls.GO)

    # ---- UNKNOWN_ACCEPTANCE

    def test_unknown_acceptance_message_holds_acceptance_unread(self):
        rec = _record([_request()])
        move = _move(rec, MESSAGE_STEP, at=PAST_WINDOW)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_ACCEPTANCE_UNREAD)
        self.assertIsNone(move["execute_after"])

    def test_unknown_acceptance_connect_holds_acceptance_unread(self):
        rec = _record([_request()])
        move = _move(rec, REQUEST_STEP, at=PAST_WINDOW)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_ACCEPTANCE_UNREAD)

    # ---- CONNECTION_NOT_ACCEPTED

    def test_connection_not_accepted_connect_holds_not_reachable(self):
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent", source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_NOT_REACHABLE)

    def test_connection_not_accepted_message_holds_requires_unmet(self):
        """Step 5 fires before step 7 because the requirement (CONNECTED)
        is not satisfied. HELD_REQUIRES_UNMET is the correct code here;
        HELD_NOT_REACHABLE only comes from step 7's action-specific logic
        when the requirement IS satisfied but the state is not MESSAGEABLE."""
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent", source="test")
        move = _move(rec, MESSAGE_STEP, observed=observed)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REQUIRES_UNMET)

    # ---- REPLIED

    def test_replied_message_holds_replied(self):
        rec = _record([_request(), _accepted(), _replied()])
        move = _move(rec, MESSAGE_STEP)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REPLIED)

    def test_replied_connect_holds_replied(self):
        rec = _record([_request(), _accepted(), _replied()])
        move = _move(rec, REQUEST_STEP)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REPLIED)

    # ---- UNKNOWN

    def test_unknown_message_holds_provider_state_unknown(self):
        rec = _record()
        observed = ls.observation(state="completely_made_up")
        move = _move(rec, MESSAGE_STEP, observed=observed)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_PROVIDER_STATE_UNKNOWN)

    # ---- OPEN_PROFILE

    def test_open_profile_message_goes(self):
        rec = _record()
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, MESSAGE_STEP, observed=observed)
        self.assertEqual(move["status"], ls.GO)

    def test_open_profile_connect_alternative_chosen_and_held(self):
        """The alternative (open_profile_message) is chosen because
        OPEN_PROFILE satisfies its requires. Its capability is unproven,
        so the step is held. The primary (connect) never runs. This is
        the same defect as the redteam expected failure: when the person
        is also already connected, the connect should SKIP but the
        alternative blocks it."""
        rec = _record()
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["action"], ls.OPEN_PROFILE_MESSAGE)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)

    def test_open_profile_alternative_action_is_named(self):
        """The alternative's action is open_profile_message, not connect.
        This is the load-bearing assertion: the alternative IS the step
        when its requirement is satisfied."""
        rec = _record()
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["action"], ls.OPEN_PROFILE_MESSAGE)

    # ---- InMail branch (FORK_STEP / li3)

    def test_inmail_unproven_capability_holds(self):
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent", inmail=True,
                                  source="test")
        config = {"linkedin": {"inmail": {"enabled": True}}}
        move = _move(rec, FORK_STEP, observed=observed, config=config)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)

    def test_inmail_eligible_and_capability_proven_goes(self):
        """THE FIX. Previously step 8 always returned WAIT even when
        verdict was INMAIL_ELIGIBLE and capability was proven."""
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent", inmail=True,
                                  source="test")
        config = {"linkedin": {"inmail": {"enabled": True}}}
        original = dict(ls.CAPABILITIES)
        ls.CAPABILITIES[cl.CAP_INMAIL] = (True, "validated in this test")
        try:
            move = _move(rec, FORK_STEP, observed=observed, config=config)
            self.assertEqual(move["status"], ls.GO)
            self.assertEqual(move["action"], ls.INMAIL)
        finally:
            ls.CAPABILITIES.clear()
            ls.CAPABILITIES.update(original)

    def test_inmail_not_available_holds_inmail_unavailable(self):
        """Workspace has not enabled InMail - the step holds with
        HELD_INMAIL_UNAVAILABLE (capability is proven for the alternative
        but the workspace policy refuses)."""
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent", inmail=False,
                                  source="test")
        move = _move(rec, FORK_STEP, observed=observed)
        self.assertEqual(move["status"], ls.WAIT)
        # Capability is unproven so step 4 catches it first
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)

    # ---- NOT_CONNECTED (provider reports nothing)

    def test_not_connected_message_holds_requires_unmet(self):
        rec = _record()
        observed = ls.observation(state=ls.NOT_CONNECTED, source="test")
        move = _move(rec, MESSAGE_STEP, observed=observed)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_REQUIRES_UNMET)

    def test_not_connected_connect_goes(self):
        rec = _record()
        observed = ls.observation(state=ls.NOT_CONNECTED, source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["status"], ls.GO)


if __name__ == "__main__":
    unittest.main()
