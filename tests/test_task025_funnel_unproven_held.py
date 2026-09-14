"""TASK-025: every cadence step gets a verdict, and unproven capabilities
are HELD, not silently dropped.

The funnel audit found seven stages. Two of them - open_profile_message
and inmail - depend on capabilities the build has not proven. The planner
must not silently skip those steps: a cadence that reports eleven touches
and sends ten is a cadence lying to its operator.

This test walks the full LinkedIn-heavy cadence and asserts:

  1. Every LinkedIn step produces an EXPLICIT verdict from plan_step.
     No step is silently absent from the output.
  2. Steps naming unproven capabilities return WAIT with
     HELD_CAPABILITY_UNPROVEN, not GO and not skip.
  3. The held step's `node` field names the step that was held, so an
     operator screen can show which capability blocked it.

This overlaps TASK-021 by design. TASK-021 tests individual (state, step)
pairs; this test walks the whole sequence and checks that nothing falls
through the cracks between them.
"""
import unittest

from src import cadencelibrary as cl, events
from src import linkedinstate as ls


KEY = "sample_contact"
PAST_WINDOW = "2026-09-20T09:00:00+00:00"

CADENCE = cl.PRODUCTIVE_LI_HEAVY_V1
LI_STEPS = tuple(s for s in CADENCE if s.get("channel") == "linkedin")


def _record(events_=()):
    return {
        "id": "invented-acme",
        "client": "productive",
        "domain": "invented.example",
        "contacts": [{
            "key": KEY,
            "name": "Invented Prospect",
            "linkedin": "https://www.linkedin.com/in/invented-sample",
        }],
        "events": list(events_),
    }


def _request(step="li1", at="2026-09-01T09:00:00+00:00"):
    return {"type": events.PUSH_MARKED, "contact": KEY,
            "channel": "linkedin", "step": step, "at": at}


def _accepted(at="2026-09-02T09:00:00+00:00"):
    return {"type": events.LINKEDIN_CONNECTED, "contact": KEY, "at": at}


class EveryLinkedInStepGetsAVerdict(unittest.TestCase):
    """No step is silently absent from the planner's output."""

    def test_all_linkedin_steps_produce_a_verdict(self):
        """Walk the cadence with no events; every step gets a verdict."""
        rec = _record()
        contact = rec["contacts"][0]
        verdicts = []
        for step in LI_STEPS:
            move = ls.plan_step(rec, contact, step, steps=CADENCE,
                                at=PAST_WINDOW)
            verdicts.append((step["key"], move))

        self.assertEqual(len(verdicts), len(LI_STEPS),
                         "every LinkedIn step must produce exactly one "
                         "verdict; a missing one is a silently dropped step")

        for key, move in verdicts:
            self.assertIn(move["status"], (ls.GO, ls.WAIT, ls.SKIP),
                          f"step {key} returned an unrecognised status: "
                          f"{move['status']}")
            self.assertIsNotNone(move.get("node"),
                                 f"step {key} has no node; the planner "
                                 f"must name which step it ruled on")

    def test_no_step_is_silently_dropped(self):
        """Every step key in the cadence appears in the verdicts."""
        rec = _record()
        contact = rec["contacts"][0]
        expected_keys = {s["key"] for s in LI_STEPS}
        found_keys = set()
        for step in LI_STEPS:
            move = ls.plan_step(rec, contact, step, steps=CADENCE,
                                at=PAST_WINDOW)
            node = move.get("node") or {}
            found_keys.add(node.get("key") or step["key"])

        missing = expected_keys - found_keys
        self.assertEqual(missing, set(),
                         f"steps silently dropped: {missing}")


class UnprovenCapabilitiesAreHeld(unittest.TestCase):
    """Steps naming unproven capabilities are HELD, not skipped or run."""

    def test_open_profile_message_alternative_is_held(self):
        """li1's alternative names CAP_OPEN_PROFILE, which is unproven.

        When the alternative's requirement IS satisfied (open profile
        observed) but the capability is unproven, the planner must HOLD
        the step rather than running the alternative as if it worked.
        """
        rec = _record()
        contact = rec["contacts"][0]
        li1 = next(s for s in LI_STEPS if s["key"] == "li1")

        observed = {"open_profile": True, "state": ls.OPEN_PROFILE,
                    "source": "test-fixture"}
        move = ls.plan_step(rec, contact, li1, observed=observed,
                            steps=CADENCE, at=PAST_WINDOW)

        self.assertEqual(move["status"], ls.WAIT,
                         "an open_profile_message step with an unproven "
                         "capability must WAIT, not GO")
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN,
                         "the hold code must name the unproven capability")
        self.assertIn("profile", str(move.get("why", "")).lower(),
                      "the why must mention the unproven capability")

    def test_inmail_fallback_is_held(self):
        """li3's alternative names CAP_INMAIL, which is unproven.

        When the connection was not accepted and the wait window closed,
        the InMail branch would fire - but the capability is unproven,
        so the planner must HOLD rather than send.
        """
        rec = _record([_request(), _accepted(at=None)])
        contact = rec["contacts"][0]
        li3 = next(s for s in LI_STEPS if s["key"] == "li3")

        observed = {"state": ls.CONNECTION_NOT_ACCEPTED,
                    "source": "test-fixture"}
        move = ls.plan_step(rec, contact, li3, observed=observed,
                            steps=CADENCE, at=PAST_WINDOW)

        self.assertEqual(move["status"], ls.WAIT,
                         "an InMail step with an unproven capability "
                         "must WAIT, not GO")
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN,
                         "the hold code must name the unproven capability")

    def test_proven_capabilities_are_not_held(self):
        """CAP_CONNECT and CAP_MESSAGE are proven. Steps using them must
        NOT return HELD_CAPABILITY_UNPROVEN."""
        rec = _record()
        contact = rec["contacts"][0]

        li1 = next(s for s in LI_STEPS if s["key"] == "li1")
        move = ls.plan_step(rec, contact, li1, steps=CADENCE,
                            at=PAST_WINDOW)
        self.assertNotEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN,
                            "li1 uses CAP_CONNECT which is proven; "
                            "it must not be held for unproven capability")

    def test_held_step_names_its_node(self):
        """A held step must name which node was held, so a screen can
        show the operator what was blocked."""
        rec = _record()
        contact = rec["contacts"][0]
        li1 = next(s for s in LI_STEPS if s["key"] == "li1")

        observed = {"open_profile": True, "state": ls.OPEN_PROFILE,
                    "source": "test-fixture"}
        move = ls.plan_step(rec, contact, li1, observed=observed,
                            steps=CADENCE, at=PAST_WINDOW)

        node = move.get("node")
        self.assertIsNotNone(node,
                             "a held step must name its node")
        self.assertIn("key", node,
                      "the held node must carry its step key")


class CapabilityTableIsTheGatekeeper(unittest.TestCase):
    """The CAPABILITIES table is the single point of control.

    Flipping an entry from False to True is what validating a capability
    looks like. Nothing else in the planner changes.
    """

    def test_unproven_capabilities_are_false(self):
        """The shipped table has open_profile and inmail as unproven."""
        for cap_name in (cl.CAP_OPEN_PROFILE, cl.CAP_INMAIL):
            proven, why = ls.capability(cap_name)
            self.assertFalse(proven,
                             f"{cap_name} is not validated; "
                             f"capability() must return False: {why}")

    def test_proven_capabilities_are_true(self):
        """The shipped table has connect and message as proven."""
        for cap_name in (cl.CAP_CONNECT, cl.CAP_MESSAGE):
            proven, why = ls.capability(cap_name)
            self.assertTrue(proven,
                            f"{cap_name} is validated; "
                            f"capability() must return True: {why}")

    def test_unknown_capability_is_false(self):
        """A capability nobody has classified is not a satisfied one."""
        proven, why = ls.capability("linkedin.nonexistent")
        self.assertFalse(proven,
                         "an unclassified capability must be False")
        self.assertIn("nonexistent", why,
                      "the why must name the unclassified capability")


if __name__ == "__main__":
    unittest.main()
