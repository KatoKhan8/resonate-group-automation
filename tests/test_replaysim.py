"""The reply-to-pause loop, run rather than asserted.

Every test here feeds a real inbound event through the real inbound path and
then reads the record. The distinction matters: checking that `paused` is set
proves a field was written, while checking that a step which was eligible
before is not eligible now proves the reply actually changed what happens next.
"""
import inspect
import unittest

from src import (campaigns, eligibility, events, replaysim, replies, store)
from tests.campaignbase import CampaignTest


class ReplayTest(CampaignTest):
    def approved(self):
        campaign, _, _ = self.approved_campaign()
        recs = store.load()
        rec = recs[0]
        return rec, recs, campaign, rec["contacts"][0]["key"]

    def run_one(self, scenario="positive_email"):
        rec, recs, campaign, key = self.approved()
        result = replaysim.simulate(rec, key, scenario, recs=recs,
                                    config=self.config, campaign=campaign)
        return result, rec, recs, campaign


class TestTheScenarios(ReplayTest):
    def test_the_four_shapes_the_brief_asks_for_exist(self):
        self.assertEqual(sorted(replaysim.SCENARIOS),
                         ["linkedin_reply", "negative_email",
                          "positive_email", "unclassifiable_inbound"])

    def test_each_one_classifies_as_documented(self):
        rec, recs, campaign, key = self.approved()
        # run_all copies the record per scenario, which is the point: after the
        # first reply the company is paused and every later run would be
        # testing the pause instead of the classifier.
        for name, result in replaysim.run_all(rec, key, recs=recs,
                                              config=self.config,
                                              campaign=campaign).items():
            self.assertTrue(result["classification_matches_expectation"],
                            f"{name}: got {result['classification']}, "
                            f"expected {result['expected_classification']}")

    def test_an_unknown_scenario_raises(self):
        rec, recs, campaign, key = self.approved()
        with self.assertRaises(KeyError):
            replaysim.simulate(rec, key, "wishful_thinking", recs=recs)

    def test_every_scenario_says_what_it_is_testing(self):
        for name, spec in replaysim.SCENARIOS.items():
            self.assertIn("expect", spec, name)
            self.assertTrue(spec["text"], name)


class TestThePositiveChain(ReplayTest):
    def test_every_link_moves(self):
        result, rec, recs, campaign = self.run_one()
        for link, ok in result["chain"].items():
            self.assertTrue(ok, f"{link} did not happen")

    def test_the_event_was_ingested_and_the_identity_resolved(self):
        result, *_ = self.run_one()
        self.assertTrue(result["chain"]["event_received"])
        self.assertTrue(result["chain"]["identity_resolved"])

    def test_the_company_is_paused_afterwards(self):
        result, rec, *_ = self.run_one()
        self.assertTrue(rec.get("paused"))
        # The pause reason is the outcome (positive, neutral, unsubscribe),
        # not a generic "reply_received". The outcome is what we made of the
        # reply, which is what matters for the audit.
        self.assertEqual(result["pause_reason"], "positive")

    def test_suppression_is_observed_rather_than_assumed(self):
        """A step that could have gone out before cannot go out now."""
        result, *_ = self.run_one()
        self.assertEqual(result["suppression_evidence"], "observed")
        self.assertGreater(result["steps_eligible_before"], 0)
        self.assertEqual(result["steps_eligible_after"], 0)
        self.assertTrue(result["steps_suppressed"])

    def test_it_does_not_claim_to_have_observed_what_it_could_not(self):
        """The mutation this catches: always reporting "observed".

        A record with nothing eligible to begin with has nothing to suppress,
        so the honest answer is that the pause is in place and no effect was
        demonstrated. Asserting only the positive case would pass against code
        that hard-coded the claim.
        """
        campaign, _, _ = self.approved_campaign()
        recs = store.load()
        rec = recs[0]
        key = rec["contacts"][0]["key"]
        # Nothing can go out: the campaign approval is not what is stale here,
        # the record itself is unshippable.
        rec["state"] = "dropped"
        rec["drop_reason"] = "no_website"
        result = replaysim.simulate(rec, key, "positive_email", recs=recs,
                                    config=self.config, campaign=campaign)
        self.assertEqual(result["steps_eligible_before"], 0)
        self.assertEqual(result["suppression_evidence"], "pause_only")
        self.assertEqual(result["steps_suppressed"], [])

    def test_the_remaining_steps_are_blocked_with_a_reason(self):
        result, rec, recs, campaign = self.run_one()
        for contact in rec["contacts"]:
            decision = eligibility.decide(rec, contact, "day5", "email",
                                          campaign=campaign, recs=recs,
                                          config=self.config)
            self.assertEqual(decision["verdict"], eligibility.BLOCKED)
            self.assertTrue(decision["reasons"])

    def test_the_reporting_events_a_report_would_count_are_recorded(self):
        result, *_ = self.run_one()
        self.assertIn(events.REPLY_RECEIVED, result["events_recorded"])
        self.assertIn(events.REPLY_CLASSIFIED, result["events_recorded"])

    def test_a_slack_alert_is_planned(self):
        result, *_ = self.run_one()
        self.assertTrue(result["chain"]["slack_planned"])
        self.assertIsNotNone(result["slack_payload"])


class TestNothingIsPosted(ReplayTest):
    def test_slack_was_not_delivered(self):
        result, *_ = self.run_one()
        self.assertFalse(result["slack_delivered"])

    def test_the_collector_reports_that_it_delivered_nothing(self):
        collector = replaysim.Collector()
        answer = collector({"text": "x"})
        self.assertFalse(answer["delivered"])
        self.assertEqual(len(collector.posted), 1)

    def test_no_provider_was_called(self):
        self.run_one()
        self.assertEqual(self.cassette.calls, [])

    def test_the_module_has_no_path_to_a_real_post(self):
        source = inspect.getsource(replaysim)
        for banned in ("slack.post", "providers.request", "push.run",
                       "live=True"):
            self.assertNotIn(banned, source, banned)


class TestTheOtherShapes(ReplayTest):
    def test_an_unsubscribe_pauses_the_company_too(self):
        result, rec, *_ = self.run_one("negative_email")
        self.assertEqual(result["classification"], replies.UNSUBSCRIBE)
        self.assertTrue(rec.get("paused"))

    def test_an_unsubscribe_raises_no_positive_alert(self):
        result, *_ = self.run_one("negative_email")
        self.assertFalse(result["chain"]["slack_planned"])

    def test_a_linkedin_reply_pauses_the_company_as_well(self):
        result, rec, *_ = self.run_one("linkedin_reply")
        self.assertTrue(rec.get("paused"))
        self.assertEqual(result["suppression_evidence"], "observed")

    def test_an_unclassifiable_inbound_still_stops_the_sequence(self):
        """Not knowing what somebody meant is a reason to stop, not to carry on."""
        result, rec, *_ = self.run_one("unclassifiable_inbound")
        self.assertTrue(rec.get("paused"))
        self.assertEqual(result["steps_eligible_after"], 0)


class TestRunningThemAll(ReplayTest):
    def test_each_scenario_gets_a_fresh_record(self):
        """Otherwise the first pause makes every later scenario a no-op."""
        rec, recs, campaign, key = self.approved()
        results = replaysim.run_all(rec, key, recs=recs, config=self.config,
                                    campaign=campaign)
        self.assertEqual(len(results), len(replaysim.SCENARIOS))
        for name, result in results.items():
            self.assertGreater(result["steps_eligible_before"], 0, name)

    def test_the_original_record_is_left_alone(self):
        rec, recs, campaign, key = self.approved()
        replaysim.run_all(rec, key, recs=recs, config=self.config,
                          campaign=campaign)
        self.assertFalse(rec.get("paused"),
                         "run_all must not pause the caller's record")

    def test_nothing_is_saved_to_the_queue(self):
        import json
        rec, recs, campaign, key = self.approved()
        before = json.dumps(store.load(), sort_keys=True)
        replaysim.run_all(rec, key, recs=recs, config=self.config,
                          campaign=campaign)
        self.assertEqual(json.dumps(store.load(), sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()
