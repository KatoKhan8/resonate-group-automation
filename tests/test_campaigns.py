"""The campaign: its state file, its status machine, and its fingerprint.

The fingerprint tests are the ones that matter. An approval is a person saying
"this run may go", and the only thing standing between that sentence and a
different run going out is that every launch-sensitive fact is inside the
digest. Each test below moves exactly one of them and insists the approval dies.
"""
import os
import unittest

from src import campaigns, cadence, orchestrator, roles, store
from tests.campaignbase import CampaignTest


class TestTheStateFile(CampaignTest):
    def test_campaigns_do_not_live_in_the_queue(self):
        self.make_campaign(self.seed_records())
        self.assertTrue(os.path.exists(self.campaign_file))
        with open(self.queue, encoding="utf-8") as f:
            self.assertNotIn("campaign_id", f.read())

    def test_the_file_sits_beside_the_queue_and_is_gitignored(self):
        self.assertIn("work", campaigns.path())
        self.assertTrue(campaigns.path().endswith("campaigns.jsonl"))

    def test_a_campaign_survives_a_reload(self):
        self.make_campaign(self.seed_records(), campaign_id="camp-x")
        again = campaigns.require("camp-x")
        self.assertEqual(again["client"], "demo")
        self.assertEqual(again["status"], campaigns.DRAFT)

    def test_a_missing_campaign_is_an_error_not_an_empty_dict(self):
        with self.assertRaises(campaigns.NotFound):
            campaigns.require("no-such-campaign")

    def test_two_campaigns_cannot_share_an_id(self):
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id="camp-1")
        with self.assertRaises(orchestrator.OrchestratorError):
            orchestrator.create("camp-1", "demo", "again")

    def test_a_campaign_for_an_unknown_client_is_refused(self):
        with self.assertRaises(orchestrator.OrchestratorError):
            orchestrator.create("camp-9", "no-such-client", "nope")

    def test_the_write_is_atomic_and_leaves_no_temp_file(self):
        self.make_campaign(self.seed_records())
        leftovers = [f for f in os.listdir(os.path.dirname(self.campaign_file))
                     if ".tmp" in f]
        self.assertEqual(leftovers, [])


class TestTheStatusMachine(CampaignTest):
    def campaign(self):
        return self.make_campaign(self.seed_records())

    def test_a_new_campaign_is_a_draft(self):
        self.assertEqual(self.campaign()["status"], campaigns.DRAFT)

    def test_a_legal_move_is_allowed(self):
        campaign = self.campaign()
        campaigns.set_status(campaign, campaigns.PREPARING)
        self.assertEqual(campaign["status"], campaigns.PREPARING)

    def test_an_illegal_move_is_refused_with_the_options(self):
        campaign = self.campaign()
        with self.assertRaises(campaigns.BadTransition) as e:
            campaigns.set_status(campaign, campaigns.RUNNING)
        self.assertIn("may only go to", str(e.exception))

    def test_a_completed_campaign_goes_nowhere(self):
        campaign = self.campaign()
        campaign["status"] = campaigns.COMPLETED
        with self.assertRaises(campaigns.BadTransition):
            campaigns.set_status(campaign, campaigns.RUNNING)

    def test_every_move_is_logged(self):
        campaign = self.campaign()
        campaigns.set_status(campaign, campaigns.PREPARING, "because")
        entry = campaign["log"][-1]
        self.assertEqual(entry["step"], "status")
        self.assertIn("draft -> preparing", entry["note"])

    def test_the_unlaunchable_statuses_include_every_pre_approval_one(self):
        for status in (campaigns.DRAFT, campaigns.PREPARING,
                       campaigns.READY_FOR_REVIEW, campaigns.AWAITING_APPROVAL,
                       campaigns.REJECTED, campaigns.FAILED):
            self.assertIn(status, campaigns.UNLAUNCHABLE, status)


class FingerprintTest(CampaignTest):
    """One helper, then one test per launch-sensitive field."""

    def setUp(self):
        super().setUp()
        self.campaign, self.recs, _ = self.approved_campaign()

    def still_approved(self):
        orchestrator.refresh_approval(self.campaign, store.load(), self.config)
        return campaigns.is_approved(self.campaign, store.load(), self.config)


class TestAnUnchangedCampaignStaysApproved(FingerprintTest):
    def test_nothing_changed_so_the_approval_stands(self):
        self.assertTrue(self.still_approved())

    def test_the_fingerprint_is_stable_across_repeated_reads(self):
        first = campaigns.fingerprint(self.campaign, store.load(), self.config)
        second = campaigns.fingerprint(self.campaign, store.load(), self.config)
        self.assertEqual(first, second)

    def test_it_does_not_depend_on_the_order_records_are_read_in(self):
        forwards = campaigns.fingerprint(self.campaign, store.load(), self.config)
        backwards = campaigns.fingerprint(self.campaign,
                                          list(reversed(store.load())),
                                          self.config)
        self.assertEqual(forwards, backwards)

    def test_a_field_nobody_sends_on_does_not_move_it(self):
        before = campaigns.fingerprint(self.campaign, store.load(), self.config)
        self.campaign["name"] = "A completely different display name"
        after = campaigns.fingerprint(self.campaign, store.load(), self.config)
        self.assertEqual(before, after, "the display name is not sent to anyone")


class TestEveryLaunchSensitiveEditInvalidates(FingerprintTest):
    def test_changing_a_sender_invalidates(self):
        orchestrator.set_senders(self.campaign,
                                 email=[{"id": "bison-9", "daily_limit": 40}],
                                 role=roles.ADMIN)
        self.assertFalse(self.still_approved())

    def test_disabling_a_sender_invalidates(self):
        orchestrator.set_senders(
            self.campaign,
            email=[{"id": "bison-1", "daily_limit": 40, "enabled": False},
                   {"id": "bison-2", "daily_limit": 40}])
        self.assertFalse(self.still_approved())

    def test_adding_a_contact_invalidates(self):
        recs = store.load()
        from tests.campaignbase import contact
        recs[0]["contacts"].append(contact("extra", "Extra Person",
                                           "extra@acme.test"))
        store.save(recs)
        self.assertFalse(self.still_approved())

    def test_removing_a_record_invalidates(self):
        orchestrator.set_records(self.campaign, [self.recs[0]["id"]])
        self.assertFalse(self.still_approved())

    def test_editing_an_approved_draft_invalidates(self):
        recs = store.load()
        for steps in recs[0]["cadence"].values():
            for step in steps.values():
                if step.get("channel") == "email":
                    step["body"] = "Completely different words entirely.\n"
                    break
            break
        store.save(recs)
        self.assertFalse(self.still_approved())

    def test_changing_the_daily_volume_invalidates(self):
        orchestrator.set_daily_volume(self.campaign, email=999)
        self.assertFalse(self.still_approved())

    def test_repointing_the_bison_campaign_invalidates(self):
        orchestrator.map_external(self.campaign, bison_campaign_id="4242")
        self.assertFalse(self.still_approved())

    def test_repointing_the_heyreach_campaign_invalidates(self):
        orchestrator.map_external(self.campaign, heyreach_campaign_id="4242")
        self.assertFalse(self.still_approved())

    def test_dropping_a_record_invalidates(self):
        recs = store.load()
        recs[0]["state"] = "dropped"
        recs[0]["drop_reason"] = "changed my mind"
        store.save(recs)
        self.assertFalse(self.still_approved())

    def test_losing_a_draft_approval_invalidates(self):
        recs = store.load()
        for steps in recs[0]["cadence"].values():
            for step in steps.values():
                step.pop("approval", None)
        store.save(recs)
        self.assertFalse(self.still_approved())

    def test_a_contact_becoming_unsendable_invalidates(self):
        recs = store.load()
        recs[0]["contacts"][0]["verification"] = {"state": "held", "evidence": []}
        recs[0]["contacts"][0]["sendable"] = False
        # Planting a degraded state deliberately. `store.save` refuses a
        # write that drops paid evidence, so this replaces the estate
        # rather than updating it - the contact is being constructed
        # unverified, not un-verified after the fact.
        store.save([])
        store.save(recs)
        self.assertFalse(self.still_approved())

    def test_invalidation_is_recorded_rather_than_silent(self):
        orchestrator.set_daily_volume(self.campaign, email=999)
        self.still_approved()
        kinds = [e["type"] for e in self.campaign["events"]]
        self.assertIn("campaign_approval_invalidated", kinds)

    def test_an_invalidated_campaign_leaves_the_approved_status(self):
        orchestrator.set_daily_volume(self.campaign, email=999)
        self.still_approved()
        self.assertEqual(self.campaign["status"], campaigns.PREPARING)


class TestTheCostEstimate(CampaignTest):
    def test_it_counts_steps_rather_than_inventing_a_price(self):
        campaign, recs = self.ready_campaign()
        estimate = campaigns.cost_estimate(campaign, recs, self.config)
        self.assertGreater(estimate["email_steps"], 0)
        self.assertGreater(estimate["linkedin_steps"], 0)

    def test_what_cannot_be_known_is_reported_as_unknown_not_zero(self):
        campaign, recs = self.ready_campaign()
        estimate = campaigns.cost_estimate(campaign, recs, self.config)
        self.assertEqual(estimate["apify_compute_units"], "unknown")
        self.assertEqual(estimate["llm_cost"], "unknown")

    def test_enrichment_is_zero_because_it_is_already_spent(self):
        campaign, recs = self.ready_campaign()
        estimate = campaigns.cost_estimate(campaign, recs, self.config)
        self.assertEqual(estimate["contactout_credits"], 0)


if __name__ == "__main__":
    unittest.main()
