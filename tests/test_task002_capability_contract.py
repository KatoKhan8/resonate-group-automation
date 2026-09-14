#!/usr/bin/env python3
"""TASK-002: the HeyReach capability contract, asserted on behaviour.

Two capabilities are in question: CAP_OPEN_PROFILE and CAP_INMAIL.
This file asserts:

1. The CAPABILITIES table classifies both as unproven (False).
2. A step naming an unproven capability is HELD by the planner, with
   HELD_CAPABILITY_UNPROVEN as the code - not silently dropped, not
   executed as if it worked.
3. Every capability the shipped sequences name is classified.
4. The counterfactual: flipping the table entry to True is the ONLY
   thing that changes, and the step then proceeds.

All assertions are on what plan_step RETURNS, not on source text.
The entry point is plan_step - the function production calls.
"""
import unittest

from src import cadencelibrary as cl
from src import events
from src import linkedinstate as ls


KEY = "probe"
REQUEST_AT = "2026-09-01T09:00:00+00:00"
PAST_WINDOW = "2026-09-20T09:00:00+00:00"

LI_STEPS = cl.PRODUCTIVE_LI_HEAVY_V1
REQUEST_STEP = next(s for s in LI_STEPS if ls.action_of(s) == ls.CONNECT)
FORK_STEP = next(s for s in LI_STEPS if s["key"] == "li3")


def _record(events_=()):
    return {"id": "acme", "client": "probe", "domain": "probe.test",
            "contacts": [{"key": KEY, "name": "Pat Probe",
                          "linkedin": f"https://www.linkedin.com/in/{KEY}"}],
            "events": list(events_)}


def _request(step="li1", at=REQUEST_AT):
    return {"type": events.PUSH_MARKED, "contact": KEY,
            "channel": "linkedin", "step": step, "at": at}


def _move(rec, spec, observed=None, at=PAST_WINDOW, config=None):
    return ls.plan_step(rec, rec["contacts"][0], spec, observed=observed,
                        steps=LI_STEPS, config=config, at=at)


class CapabilityTableContract(unittest.TestCase):
    """The CAPABILITIES table is the gatekeeper. Assert its shape."""

    def test_cap_connect_is_proven(self):
        proven, why = ls.capability(cl.CAP_CONNECT)
        self.assertTrue(proven)

    def test_cap_message_is_proven(self):
        proven, why = ls.capability(cl.CAP_MESSAGE)
        self.assertTrue(proven)

    def test_cap_open_profile_is_unproven(self):
        """No route, no field. OPEN_PROFILE_DETECTABLE is False."""
        proven, why = ls.capability(cl.CAP_OPEN_PROFILE)
        self.assertFalse(proven)
        self.assertTrue(why)

    def test_cap_inmail_is_unproven(self):
        """Capacity is readable; prospect eligibility is not."""
        proven, why = ls.capability(cl.CAP_INMAIL)
        self.assertFalse(proven)
        self.assertTrue(why)

    def test_unknown_capability_is_unproven(self):
        """A capability nobody classified must not read as satisfied."""
        proven, why = ls.capability("linkedin.nobody_defined_this")
        self.assertFalse(proven)

    def test_empty_capability_is_satisfied(self):
        """A step naming no capability depends on nothing."""
        proven, why = ls.capability(None)
        self.assertTrue(proven)

    def test_every_capability_shipped_sequences_name_is_classified(self):
        """A new linkedin_action arriving with no gate would pass silently."""
        for name in cl.SEQUENCES:
            steps = cl.named(name)
            for cap in cl.capabilities_used(steps):
                with self.subTest(sequence=name, capability=cap):
                    self.assertIn(cap, ls.CAPABILITIES)


class OpenProfileCapabilityHeld(unittest.TestCase):
    """CAP_OPEN_PROFILE: the open-profile alternative on li1.

    The alternative requires OPEN_PROFILE state and depends on
    CAP_OPEN_PROFILE. When the person IS an open profile, the
    alternative is chosen - and then held because the capability
    is unproven.
    """

    def test_open_profile_alternative_is_chosen(self):
        """The alternative IS the step when its requirement is met."""
        rec = _record()
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["action"], ls.OPEN_PROFILE_MESSAGE)

    def test_open_profile_alternative_is_held(self):
        """Chosen AND held. The capability is unproven."""
        rec = _record()
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)

    def test_open_profile_held_names_its_node(self):
        """The held step names the alternative node, not the primary."""
        rec = _record()
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertTrue(move["node"].get("is_alternative"))

    def test_open_profile_counterfactual_capability_proven_goes(self):
        """Flipping the table entry is the ONLY thing that changes."""
        rec = _record()
        observed = ls.observation(open_profile=True, source="test")
        original = dict(ls.CAPABILITIES)
        ls.CAPABILITIES[cl.CAP_OPEN_PROFILE] = (True, "validated in test")
        try:
            move = _move(rec, REQUEST_STEP, observed=observed)
            self.assertEqual(move["status"], ls.GO)
            self.assertEqual(move["action"], ls.OPEN_PROFILE_MESSAGE)
        finally:
            ls.CAPABILITIES.clear()
            ls.CAPABILITIES.update(original)


class InMailCapabilityHeld(unittest.TestCase):
    """CAP_INMAIL: the InMail fallback on li3.

    The alternative requires CONNECTION_NOT_ACCEPTED and depends on
    CAP_INMAIL. When the connection was not accepted, the alternative
    is chosen - and then held because the capability is unproven.
    """

    def _enabled(self):
        return {"linkedin": {"inmail": {"enabled": True}}}

    def test_inmail_alternative_is_chosen_after_unaccepted(self):
        """The InMail branch is chosen when connection was not accepted."""
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent",
                                  inmail=True, source="test")
        move = _move(rec, FORK_STEP, observed=observed,
                     config=self._enabled())
        self.assertEqual(move["action"], ls.INMAIL)

    def test_inmail_alternative_is_held_on_capability(self):
        """Chosen AND held at step 4 (capability gate), before step 8."""
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent",
                                  inmail=True, source="test")
        move = _move(rec, FORK_STEP, observed=observed,
                     config=self._enabled())
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)

    def test_inmail_held_even_when_eligible(self):
        """Provider says eligible, workspace enabled, capability unproven.
        The capability gate fires BEFORE the eligibility check."""
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent",
                                  inmail=True, source="test")
        move = _move(rec, FORK_STEP, observed=observed,
                     config=self._enabled())
        self.assertEqual(move["status"], ls.WAIT)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)

    def test_inmail_counterfactual_capability_proven_goes(self):
        """The counterfactual: one table entry, nothing else.

        This is the instruction for whoever validates CAP_INMAIL:
        flip the table, the step goes. No other change needed."""
        rec = _record([_request()])
        observed = ls.observation(lifecycle="connectionsent",
                                  inmail=True, source="test")
        original = dict(ls.CAPABILITIES)
        ls.CAPABILITIES[cl.CAP_INMAIL] = (True, "validated in test")
        try:
            move = _move(rec, FORK_STEP, observed=observed,
                         config=self._enabled())
            self.assertEqual(move["status"], ls.GO)
            self.assertEqual(move["action"], ls.INMAIL)
        finally:
            ls.CAPABILITIES.clear()
            ls.CAPABILITIES.update(original)


class CapabilityGateIsTheGatekeeper(unittest.TestCase):
    """The capability gate is step 4 in plan_step. It fires before
    the prospect-state checks (step 5) and the action-specific logic
    (steps 6-8). These tests assert that ordering.
    """

    def test_capability_gate_fires_before_prospect_state(self):
        """An unproven capability holds even when the prospect state
        would also refuse. The capability reason is reported, not the
        prospect-state reason."""
        rec = _record()
        observed = ls.observation(open_profile=True, source="test")
        move = _move(rec, REQUEST_STEP, observed=observed)
        self.assertEqual(move["code"], ls.HELD_CAPABILITY_UNPROVEN)
        self.assertNotEqual(move["code"], ls.HELD_REQUIRES_UNMET)

    def test_proven_capability_passes_the_gate(self):
        """CAP_CONNECT is proven. The connect step passes step 4 and
        reaches step 6 (the action-specific logic)."""
        rec = _record()
        move = _move(rec, REQUEST_STEP)
        self.assertEqual(move["status"], ls.GO)
        self.assertIsNone(move["code"])


if __name__ == "__main__":
    unittest.main()
