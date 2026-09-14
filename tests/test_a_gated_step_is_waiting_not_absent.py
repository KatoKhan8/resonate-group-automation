"""TASK-016: a gated step is waiting, not absent.

`cadence.build` used to omit a step whose `requires` precondition was
unmet when the step was generated and had no body yet. Five of six
LinkedIn steps in the heavy sequence were invisible to approval and to
the campaign graph, which is the deadlock that blocked HeyReach staging.

The fix: a step with a `requires` appears in the timeline even when its
content has not been generated, and `status_for` names the unmet
precondition. Nothing that was unexecutable before becomes executable:
`eligibility.decide` and `executionguard.authorize` still refuse.
"""
import unittest

from src import (cadence, cadenceexposure, clients, eligibility, events,
                 executionguard, linkedinstate as ls, store, touch)
from tests.campaignbase import CampaignTest


WS = "productive"
KEY = "pat"


class GatedStepsAppearInTheTimeline(CampaignTest):
    """`cadence.build` surfaces every step whose requires is unmet."""

    def setUp(self):
        super().setUp()
        self.config = clients.load(WS)

    def record(self):
        self.reset_estate()
        rec = store.new_record("acme", "domains", WS, "Acme Ltd", "acme.test")
        rec["state"] = "verified"
        rec["hook"] = "resourcing visibility"
        rec["company_facts"] = {"name": "Acme Ltd", "industry": "agency"}
        rec["contacts"] = [{
            "key": KEY, "name": "Pat Morgan",
            "email": f"{KEY}@acme.test",
            "linkedin": f"https://www.linkedin.com/in/{KEY}",
            "title": "Head of Production",
            "angle": "operations",
        }]
        rec["cadence"] = {}
        rec["events"] = []
        store.save([rec])
        return rec

    def steps(self, rec):
        return cadence.build(rec, self.config)["contacts"][KEY]

    def test_li2_through_li6_appear_for_an_unconnected_contact(self):
        """The whole point. Five steps that were invisible are now waiting."""
        rec = self.record()
        timeline = self.steps(rec)
        for step_key in ("li2", "li3", "li4", "li5", "li6"):
            self.assertIn(step_key, timeline,
                          f"{step_key} is missing from the timeline")

    def test_each_gated_step_names_the_unmet_requirement(self):
        rec = self.record()
        timeline = self.steps(rec)
        for step_key in ("li2", "li3", "li4", "li5", "li6"):
            step = timeline[step_key]
            self.assertEqual(step["status"], "waiting",
                             f"{step_key} status is {step['status']!r}, "
                             f"expected 'waiting'")

    def test_an_already_connected_person_skips_the_request(self):
        """li1 for a connected contact: the connection request is skipped."""
        rec = self.record()
        events.record(rec, events.LINKEDIN_CONNECTED, contact_key=KEY,
                      at="2026-09-02T09:00:00+00:00")
        store.save([rec])
        step = self.steps(rec)["li1"]
        self.assertEqual(step["status"], "skipped")
        self.assertIn("connection request is skipped", step["skipped_reason"])

    def test_the_acceptance_releases_the_waiting_steps(self):
        """Once connected, li2..li6 are no longer waiting."""
        rec = self.record()
        events.record(rec, events.LINKEDIN_CONNECTED, contact_key=KEY,
                      at="2026-09-02T09:00:00+00:00")
        store.save([rec])
        timeline = self.steps(rec)
        for step_key in ("li2", "li3", "li4", "li5", "li6"):
            self.assertNotEqual(timeline[step_key]["status"], "waiting",
                                f"{step_key} is still waiting after acceptance")


class EligibilityStillRefusesWaitingSteps(CampaignTest):
    """TASK-016 scope (3): eligibility.decide still refuses a message step
    for an unconnected contact, even though the step is now visible."""

    def setUp(self):
        super().setUp()
        self.config = clients.load(WS)

    def record(self):
        self.reset_estate()
        rec = store.new_record("acme", "domains", WS, "Acme Ltd", "acme.test")
        rec["state"] = "verified"
        rec["company_facts"] = {"name": "Acme Ltd", "industry": "agency"}
        rec["contacts"] = [{
            "key": KEY, "name": "Pat Morgan",
            "email": f"{KEY}@acme.test",
            "linkedin": f"https://www.linkedin.com/in/{KEY}",
            "title": "Head of Production",
            "angle": "operations",
        }]
        rec["cadence"] = {}
        rec["events"] = []
        store.save([rec])
        return rec

    def test_eligibility_decide_refuses_a_waiting_message_step(self):
        """The test that matters most. li2 is now visible in the timeline
        with status 'waiting', but eligibility.decide must still refuse it
        for an unconnected contact. Visible must not mean allowed.

        The refusal reason depends on check order: a generated step with
        no body has no note, so _linkedin_checks refuses it as
        HELD_APPROVAL_MISSING before _dependency reads the waiting status.
        Either way, the step is HELD and cannot execute."""
        rec = self.record()
        timeline = cadence.build(rec, self.config)
        step = timeline["contacts"][KEY]["li2"]
        self.assertEqual(step["status"], "waiting")

        contact = rec["contacts"][0]
        decision = eligibility.decide(
            rec, contact, "li2", channel="linkedin",
            config=self.config, timeline=timeline["contacts"])
        self.assertEqual(decision["verdict"], eligibility.HELD)
        self.assertTrue(len(decision["reasons"]) > 0,
                        "eligibility.decide returned no refusal reason")

    def test_dependency_check_reads_waiting_status(self):
        """Prove that eligibility._dependency catches a waiting step
        directly, even if other checks were to pass. This is the guard
        that makes visible != allowed."""
        from src.eligibility import _dependency, HELD_AWAITING_DEPENDENCY

        rec = self.record()
        timeline = cadence.build(rec, self.config)
        contact = rec["contacts"][0]
        step = timeline["contacts"][KEY]["li2"]
        self.assertEqual(step["status"], "waiting")

        result = _dependency(rec, contact, "li2", step,
                             timeline["contacts"])
        self.assertEqual(result, HELD_AWAITING_DEPENDENCY)


class ExecutionGuardStillRefusesWaitingSteps(CampaignTest):
    """TASK-016 scope (3): executionguard still refuses to authorise a
    step whose precondition is unmet. Uses the default cadence's day8
    step (requires connection_accepted) because executionguard._spec_for
    reads cadence.STEPS."""

    def setUp(self):
        super().setUp()
        self.config = clients.load("demo")

    def record(self):
        self.reset_estate()
        rec = store.new_record("acme", "domains", "demo", "Acme Ltd",
                               "acme.test")
        rec["state"] = "verified"
        rec["company_facts"] = {"name": "Acme Ltd", "industry": "agency"}
        rec["contacts"] = [{
            "key": KEY, "name": "Pat Morgan",
            "email": f"{KEY}@acme.test",
            "linkedin": f"https://www.linkedin.com/in/{KEY}",
            "title": "Head of Production",
            "angle": "ops",
        }]
        rec["cadence"] = {}
        rec["events"] = []
        store.save([rec])
        return rec

    def test_authorize_refuses_a_step_with_unmet_precondition(self):
        """day8 requires connection_accepted. Without acceptance,
        executionguard must refuse even though the step is now visible
        in the timeline."""
        rec = self.record()
        contact = rec["contacts"][0]
        campaign = {
            "campaign_id": "test-campaign",
            "client": "demo",
            "org_unit": WS,
            "record_ids": [rec["id"]],
            "senders": {"email": ["anna07"], "linkedin": ["petar-li"]},
        }
        with self.assertRaises(executionguard.NotAuthorized):
            executionguard.authorize(
                operation="send", channel="linkedin",
                campaign=campaign, rec=rec, contact=contact,
                step_key="day8", workspace=WS, config=self.config,
                recs=[rec], readback=({}, "2026-09-14T09:00:00+00:00"))


class WaitingStepsAreNotExposures(CampaignTest):
    """TASK-016 scope (4): a waiting step is not a confirmed touch.
    Counting it as one would fabricate an exposure."""

    def setUp(self):
        super().setUp()
        self.config = clients.load(WS)

    def record(self):
        self.reset_estate()
        rec = store.new_record("acme", "domains", WS, "Acme Ltd", "acme.test")
        rec["state"] = "verified"
        rec["company_facts"] = {"name": "Acme Ltd", "industry": "agency"}
        rec["contacts"] = [{
            "key": KEY, "name": "Pat Morgan",
            "email": f"{KEY}@acme.test",
            "linkedin": f"https://www.linkedin.com/in/{KEY}",
            "title": "Head of Production",
            "angle": "operations",
        }]
        rec["cadence"] = {}
        rec["events"] = []
        store.save([rec])
        return rec

    def test_waiting_steps_are_not_confirmed_touches(self):
        """A waiting step has not reached anybody. Counting it would be
        a fabricated exposure."""
        rec = self.record()
        timeline = cadence.build(rec, self.config)
        steps = timeline["contacts"][KEY]
        for step_key in ("li2", "li3", "li4", "li5", "li6"):
            self.assertEqual(steps[step_key]["status"], "waiting")
            self.assertNotIn(steps[step_key]["status"],
                             touch.CONFIRMED_STATES)

    def test_push_does_not_pick_up_waiting_steps(self):
        """push.collect filters on status == 'eligible'. A waiting step
        is not eligible."""
        rec = self.record()
        timeline = cadence.build(rec, self.config)
        steps = timeline["contacts"][KEY]
        for step_key in ("li2", "li3", "li4", "li5", "li6"):
            self.assertNotEqual(steps[step_key]["status"], "eligible")


if __name__ == "__main__":
    unittest.main()
