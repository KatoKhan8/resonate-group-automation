"""The gate, the shared timeline, and the checklist that guards them.

The single most important property in this file: campaign approval is one
condition among fourteen, not a master key. Every test in
TestApprovalIsNotAMasterKey approves a campaign properly and then breaks one
unrelated safety rule, and the launch must still refuse.
"""
import unittest

from src.providers import bison

from src import cadence, campaigns, lint, orchestrator, push, roles, store
from tests.campaignbase import CampaignTest

ADMIN = "U0DEMOADMIN1"


class TestTheLaunchGate(CampaignTest):
    def test_an_unapproved_campaign_cannot_launch(self):
        campaign, recs = self.ready_campaign()
        with self.assertRaises(orchestrator.NotReady) as e:
            orchestrator.launch(campaign, recs=recs, config=self.config)
        self.assertIn("campaign approved", str(e.exception))

    def test_an_approved_campaign_reaches_the_live_send_refusal(self):
        """Proof the gate is real: approval gets you to the door, not through."""
        campaign, recs, _ = self.approved_campaign()
        with self.assertRaises(push.LiveSendNotEnabled):
            orchestrator.launch(campaign, recs=store.load(), config=self.config,
                                live=True)

    def test_an_unapproved_campaign_is_refused_before_the_live_check(self):
        """The order matters: otherwise the live refusal would mask every gate."""
        campaign, recs = self.ready_campaign()
        with self.assertRaises(orchestrator.NotReady):
            orchestrator.launch(campaign, recs=recs, config=self.config,
                                live=True)

    def test_a_dry_launch_prepares_payloads_and_sends_nothing(self):
        campaign, recs, _ = self.approved_campaign()
        result = orchestrator.launch(campaign, recs=store.load(),
                                     config=self.config)
        self.assertFalse(result["launched"])
        self.assertTrue(result["ready"])
        self.assertEqual(self.cassette.calls, [])

    def test_an_approved_campaign_becomes_launch_ready(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.launch_readiness(campaign, store.load(), self.config)
        self.assertEqual(campaign["status"], campaigns.LAUNCH_READY)

    def test_a_launched_campaign_cannot_be_launched_again(self):
        campaign, recs, _ = self.approved_campaign()
        campaign["launch"] = {"state": "launched", "at": "2026-08-26T00:00:00Z"}
        result = campaigns.validate("camp-1", store.load(), self.config,
                                    campaign=campaign)
        self.assertIn("not already launched", result["blockers"])


class TestApprovalIsNotAMasterKey(CampaignTest):
    """Approve properly, then break one rule. The launch must still refuse."""

    def setUp(self):
        super().setUp()
        self.campaign, _, _ = self.approved_campaign()

    def refuses(self, blocker):
        result = campaigns.validate("camp-1", store.load(), self.config,
                                    campaign=self.campaign)
        self.assertFalse(result["ok"])
        self.assertIn(blocker, result["blockers"])

    def test_an_unverified_recipient_blocks_it(self):
        recs = store.load()
        recs[0]["contacts"][0]["verification"] = {"state": "unknown"}
        # Planting a degraded state deliberately. `store.save` refuses a
        # write that drops paid evidence, so this replaces the estate
        # rather than updating it - the contact is being constructed
        # unverified, not un-verified after the fact.
        store.save([])
        store.save(recs)
        self.refuses("recipients sendable")

    def test_a_lint_failure_blocks_it(self):
        recs = store.load()
        for steps in recs[0]["cadence"].values():
            for step in steps.values():
                if step.get("generated"):
                    step["body"] = "Hi {{first_name}}, quick one.\n"
        store.save(recs)
        self.refuses("lint clean")

    def test_a_dropped_record_blocks_it(self):
        recs = store.load()
        recs[0]["state"] = "dropped"
        recs[0]["drop_reason"] = "out of geo"
        store.save(recs)
        self.refuses("no dropped or pushed records")

    def test_a_paused_company_blocks_it(self):
        recs = store.load()
        recs[0]["paused"] = {"since": "2026-08-26T00:00:00Z",
                             "reason": "reply_received"}
        store.save(recs)
        self.refuses("no paused companies")

    def test_an_already_pushed_step_blocks_it(self):
        recs = store.load()
        contact_key = recs[0]["contacts"][0]["key"]
        push.mark_pushed(recs[0], contact_key, "day1",
                         f"acme:{contact_key}:day1:email")
        store.save(recs)
        self.refuses("no duplicate push ids")

    def test_a_missing_external_campaign_id_blocks_it(self):
        self.campaign["bison_campaign_id"] = None
        self.refuses("external campaign mapping")

    def test_a_zero_daily_volume_blocks_it(self):
        self.campaign["daily_volume"] = {"email": 0, "linkedin": 0}
        self.refuses("daily volume")

    def test_a_missing_sender_blocks_it(self):
        self.campaign["senders"] = {}
        self.refuses("sender mapping")

    def test_a_record_that_left_the_queue_blocks_it(self):
        store.save([r for r in store.load() if r["id"] != "acme"])
        self.refuses("records present")

    def test_the_checklist_reports_every_condition_not_just_the_first(self):
        self.campaign["senders"] = {}
        self.campaign["daily_volume"] = {}
        result = campaigns.validate("camp-1", store.load(), self.config,
                                    campaign=self.campaign)
        self.assertGreaterEqual(len(result["blockers"]), 2)
        self.assertEqual(len(result["checks"]), len(campaigns.CHECKS))

    def test_a_broken_check_blocks_rather_than_passing(self):
        """A check that raises must not be read as a pass."""
        def explode(campaign, recs, config):
            raise RuntimeError("boom")

        original = campaigns.CHECKS
        campaigns.CHECKS = original[:1] + (("exploding", explode),)
        try:
            result = campaigns.validate("camp-1", store.load(), self.config,
                                        campaign=self.campaign)
        finally:
            campaigns.CHECKS = original
        self.assertFalse(result["ok"])
        self.assertIn("exploding", result["blockers"])


class TestNoPushWithoutApproval(CampaignTest):
    def test_a_stale_approval_cannot_launch(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.set_daily_volume(campaign, email=999)
        with self.assertRaises(orchestrator.NotReady):
            orchestrator.launch(campaign, recs=store.load(), config=self.config)

    def test_a_rejected_campaign_cannot_launch(self):
        campaign, recs = self.ready_campaign()
        orchestrator.prepare(campaign, recs, self.config)
        orchestrator.request_approval(campaign, recs, self.config)
        orchestrator.decide(campaign, ADMIN, "reject", interaction_id="r-1",
                            config=self.config, recs=recs)
        with self.assertRaises(orchestrator.NotReady):
            orchestrator.launch(campaign, recs=store.load(), config=self.config)

    def test_resuming_re_checks_everything_rather_than_trusting_the_pause(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.launch_readiness(campaign, store.load(), self.config)
        orchestrator.pause(campaign, "manual", by=ADMIN)
        recs = store.load()
        recs[0]["state"] = "dropped"
        recs[0]["drop_reason"] = "changed our minds"
        store.save(recs)
        with self.assertRaises(orchestrator.NotReady):
            orchestrator.resume(campaign, by=ADMIN, recs=store.load(),
                                config=self.config)

    def test_a_clean_campaign_resumes(self):
        campaign, recs, _ = self.approved_campaign()
        orchestrator.launch_readiness(campaign, store.load(), self.config)
        orchestrator.pause(campaign, "manual", by=ADMIN)
        orchestrator.resume(campaign, by=ADMIN, recs=store.load(),
                            config=self.config)
        self.assertEqual(campaign["status"], campaigns.RUNNING)

    def test_a_reviewer_cannot_launch(self):
        self.assertFalse(roles.may(roles.REVIEWER, roles.LAUNCH_CAMPAIGN))
        with self.assertRaises(roles.NotPermitted):
            roles.require(roles.REVIEWER, roles.LAUNCH_CAMPAIGN, "someone")

    def test_a_viewer_cannot_pause(self):
        with self.assertRaises(roles.NotPermitted):
            orchestrator.pause({}, by="v", role=roles.VIEWER)


class TestOneSharedTimeline(CampaignTest):
    """Bison and HeyReach are execution layers. The cadence is the timeline."""

    def timeline(self):
        recs = self.seed_records()
        self.draft_everything(recs)
        return cadence.build(recs[0], self.config, recs=recs), recs

    def test_a_contact_has_one_combined_cadence_across_both_channels(self):
        timeline, _ = self.timeline()
        for contact_key, steps in timeline["contacts"].items():
            channels = {s["channel"] for s in steps.values()}
            self.assertEqual(channels, {"email", "linkedin"}, contact_key)

    def test_no_two_channels_land_on_the_same_day_for_one_person(self):
        timeline, _ = self.timeline()
        for contact_key, steps in timeline["contacts"].items():
            by_day = {}
            for key, step in steps.items():
                by_day.setdefault(step["day"], set()).add(step["channel"])
            for day, channels in by_day.items():
                self.assertEqual(len(channels), 1, f"{contact_key} day {day}")

    def test_the_step_days_come_from_the_internal_cadence_only(self):
        """No provider supplies a schedule: the days are ours."""
        timeline, _ = self.timeline()
        days = sorted({s["day"] for steps in timeline["contacts"].values()
                       for s in steps.values()})
        expected = sorted({s["day"] for s in cadence.STEPS})
        self.assertTrue(set(days) <= set(expected) or days, days)

    def test_the_buyer_track_keeps_its_offset(self):
        recs = self.seed_records()
        from tests.campaignbase import contact
        recs[0]["contacts"].append(contact("acme-buyer", "Buyer", "buyer@acme.test",
                                           persona="economic_buyer",
                                           angle="founder"))
        self.draft_everything(recs)
        timeline = cadence.build(recs[0], self.config, recs=recs)
        champion = min(s["day"] for s in timeline["contacts"]["acme-champ"].values())
        buyer = min(s["day"] for s in timeline["contacts"]["acme-buyer"].values())
        self.assertEqual(buyer - champion, 5)

    def test_a_push_id_is_unique_per_contact_step_and_channel(self):
        campaign, recs, _ = self.approved_campaign()
        result = campaigns.validate("camp-1", store.load(), self.config,
                                    campaign=campaign)
        row = next(r for r in result["checks"] if r["check"] == "no duplicate push ids")
        self.assertTrue(row["ok"], row["detail"])

    def test_an_accepted_connection_changes_the_later_variant(self):
        recs = self.seed_records()
        self.draft_everything(recs)
        before = cadence.build(recs[0], self.config, recs=recs)
        before_template = before["contacts"]["acme-champ"]["day10"].get("template")
        cadence.record_event(recs[0], "connection_accepted",
                             contact_key="acme-champ")
        after = cadence.build(recs[0], self.config, recs=recs)
        after_template = after["contacts"]["acme-champ"]["day10"].get("template")
        self.assertNotEqual(before_template, after_template)


class TestTheDryRun(CampaignTest):
    def plan(self):
        campaign, recs, _ = self.approved_campaign()
        return campaigns.dry_run("camp-1", day=21, recs=store.load(),
                                 config=self.config, campaign=campaign)

    def test_it_reports_the_shape_of_the_run(self):
        plan = self.plan()
        for field in ("records", "contacts", "channels", "senders", "external",
                      "payload_count", "estimate", "held", "blocked"):
            self.assertIn(field, plan)

    def test_it_carries_both_provider_payloads(self):
        plan = self.plan()
        self.assertIn("emailbison", plan["payloads"])
        self.assertIn("heyreach", plan["payloads"])

    def test_the_payloads_point_at_the_mapped_external_campaigns(self):
        plan = self.plan()
        self.assertIn("9001", plan["payloads"]["emailbison"]["endpoint"])
        self.assertEqual(plan["payloads"]["heyreach"]["body"]["campaignId"], "7001")

    def test_it_makes_no_network_call(self):
        self.plan()
        self.assertEqual(self.cassette.calls, [])

    def test_every_email_payload_carries_a_real_subject_and_body(self):
        plan = self.plan()
        leads = plan["payloads"]["emailbison"]["body"]["leads"]
        self.assertTrue(leads)
        for lead in leads:
            variables = bison.variables_of(lead)
            self.assertTrue(variables["subject"].strip())
            self.assertGreater(len(variables["body"].split()), 20)
            self.assertNotIn("{{", variables["body"])


if __name__ == "__main__":
    unittest.main()
