"""The watcher reconciles: it reports drift rather than assuming agreement.

TASK-350. Every drift this project has hit was found by hand, days late:
campaigns believed active that were paused, 44 of 46 blank leads already in
a client campaign, a ledger whose silence was read as absence.

The reconciliation check compares what we believe against what the provider
says, per bound campaign, and reports three verdicts:

  AGREED               both sides say the same thing
  DRIFTED              they disagree
  COULD_NOT_ESTABLISH  the provider call failed or returned nothing

A zero on both sides is AGREED only when both sides genuinely returned zero.
A provider that returned nothing is COULD_NOT_ESTABLISH, not AGREED. This is
the assertion that closes the task.

Nothing here writes to a provider, pauses a campaign, or changes local state.
"""
import os
import unittest

from tests.campaignbase import CampaignTest
from src import campaigns as campaigns_state, replywatch, store


class ReconcileDriftDetected(CampaignTest):
    """Acceptance 1: drift is detected and named."""

    def setUp(self):
        super().setUp()
        self.recs = self.seed_records()

    def test_drift_is_reported_naming_campaign_field_and_both_values(self):
        """A fixture where our count and the provider's disagree."""
        campaign = campaigns_state.new_campaign(
            "camp-drift", "demo", "Drift campaign")
        campaign["heyreach_campaign_id"] = "5001"
        campaign["record_ids"] = ["acme", "borealis"]
        campaign["status"] = "running"
        campaigns_state.save([campaign])

        def fake_read(cid):
            return {"id": cid, "status": "PAUSED", "name": "Drift campaign"}

        def fake_stats(cid):
            return {"connectionsSent": 10, "connectionsAccepted": 5,
                    "totalMessageReplies": 3, "uniqueLeadsContacted": 50}

        findings = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=fake_stats,
            bison_read=lambda cid: {}, bison_lead_count=lambda cid: 0)

        status_finding = next(
            f for f in findings if f["field"] == "status")
        self.assertEqual(status_finding["verdict"], replywatch.DRIFTED)
        self.assertEqual(status_finding["campaign_id"], "camp-drift")
        self.assertEqual(status_finding["provider_id"], "5001")
        self.assertEqual(status_finding["provider"], "heyreach")
        self.assertEqual(status_finding["local"], "running")
        self.assertEqual(status_finding["provider_value"], "PAUSED")

        lead_finding = next(
            f for f in findings if f["field"] == "lead_count")
        self.assertEqual(lead_finding["verdict"], replywatch.DRIFTED)
        self.assertEqual(lead_finding["local"], 2)
        self.assertEqual(lead_finding["provider_value"], 50)

    def test_sent_count_drift_is_detected(self):
        campaign = campaigns_state.new_campaign(
            "camp-sent", "demo", "Sent drift")
        campaign["heyreach_campaign_id"] = "5002"
        campaign["record_ids"] = ["acme"]
        campaign["events"] = [
            {"type": "sent"}, {"type": "sent"}, {"type": "sent"},
        ]
        campaign["status"] = "running"
        campaigns_state.save([campaign])

        def fake_read(cid):
            return {"id": cid, "status": "IN_PROGRESS"}

        def fake_stats(cid):
            return {"connectionsSent": 100, "connectionsAccepted": 0,
                    "totalMessageReplies": 0, "uniqueLeadsContacted": 1}

        findings = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=fake_stats)

        sent_finding = next(
            f for f in findings if f["field"] == "sent_count")
        self.assertEqual(sent_finding["verdict"], replywatch.DRIFTED)
        self.assertEqual(sent_finding["local"], 3)
        self.assertEqual(sent_finding["provider_value"], 100)

    def test_reply_count_drift_is_detected(self):
        campaign = campaigns_state.new_campaign(
            "camp-reply", "demo", "Reply drift")
        campaign["heyreach_campaign_id"] = "5003"
        campaign["record_ids"] = ["acme"]
        campaign["events"] = [{"type": "reply"}]
        campaign["status"] = "running"
        campaigns_state.save([campaign])

        def fake_read(cid):
            return {"id": cid, "status": "IN_PROGRESS"}

        def fake_stats(cid):
            return {"connectionsSent": 1, "connectionsAccepted": 1,
                    "totalMessageReplies": 7, "uniqueLeadsContacted": 1}

        findings = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=fake_stats)

        reply_finding = next(
            f for f in findings if f["field"] == "reply_count")
        self.assertEqual(reply_finding["verdict"], replywatch.DRIFTED)
        self.assertEqual(reply_finding["local"], 1)
        self.assertEqual(reply_finding["provider_value"], 7)


class ReconcileAgreement(CampaignTest):
    """Acceptance 2: agreement is reported as agreement, not as silence."""

    def setUp(self):
        super().setUp()
        self.recs = self.seed_records()

    def test_agreement_when_both_sides_match(self):
        campaign = campaigns_state.new_campaign(
            "camp-ok", "demo", "Good campaign")
        campaign["heyreach_campaign_id"] = "6001"
        campaign["record_ids"] = ["acme", "borealis"]
        campaign["status"] = "running"
        campaign["events"] = [{"type": "sent"}, {"type": "reply"}]
        campaigns_state.save([campaign])

        def fake_read(cid):
            return {"id": cid, "status": "IN_PROGRESS"}

        def fake_stats(cid):
            return {"connectionsSent": 1, "connectionsAccepted": 0,
                    "totalMessageReplies": 1, "uniqueLeadsContacted": 2}

        findings = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=fake_stats)

        for f in findings:
            self.assertEqual(f["verdict"], replywatch.AGREED,
                             f"field {f['field']} should be AGREED but was "
                             f"{f['verdict']}")

    def test_bison_agreement(self):
        campaign = campaigns_state.new_campaign(
            "camp-bison-ok", "demo", "Bison good")
        campaign["bison_campaign_id"] = "9001"
        campaign["record_ids"] = ["acme"]
        campaign["status"] = "running"
        campaigns_state.save([campaign])

        def fake_read(cid):
            return {"status": "active"}

        def fake_leads(cid):
            return 1

        findings = replywatch.reconcile_campaigns(
            bison_read=fake_read, bison_lead_count=fake_leads)

        for f in findings:
            self.assertEqual(f["verdict"], replywatch.AGREED,
                             f"field {f['field']} should be AGREED")

    def test_both_zeros_from_real_data_is_agreed_not_silence(self):
        """A zero on both sides is AGREED when both sides returned it.

        This is the distinction: both sides genuinely returned zero is
        agreement. One side returning nothing is COULD_NOT_ESTABLISH.
        """
        campaign = campaigns_state.new_campaign(
            "camp-zero", "demo", "Zero campaign")
        campaign["heyreach_campaign_id"] = "6002"
        campaign["record_ids"] = []
        campaign["status"] = "draft"
        campaign["events"] = []
        campaigns_state.save([campaign])

        def fake_read(cid):
            return {"id": cid, "status": "DRAFT"}

        def fake_stats(cid):
            return {"connectionsSent": 0, "connectionsAccepted": 0,
                    "totalMessageReplies": 0, "uniqueLeadsContacted": 0}

        findings = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=fake_stats)

        for f in findings:
            self.assertEqual(f["verdict"], replywatch.AGREED,
                             f"field {f['field']} should be AGREED when "
                             f"both sides genuinely return zero")


class ReconcileUnestablished(CampaignTest):
    """Acceptance 3: an unestablished comparison is its own verdict.

    This is the assertion that closes the task. A provider call that fails
    or returns nothing must produce COULD_NOT_ESTABLISH, not AGREED.
    """

    def setUp(self):
        super().setUp()
        self.recs = self.seed_records()

    def test_provider_failure_is_not_agreed(self):
        """The provider call raises. The verdict is COULD_NOT_ESTABLISH."""
        campaign = campaigns_state.new_campaign(
            "camp-fail", "demo", "Failed read")
        campaign["heyreach_campaign_id"] = "7001"
        campaign["record_ids"] = ["acme"]
        campaign["status"] = "running"
        campaigns_state.save([campaign])

        def exploding_read(cid):
            raise ConnectionError("provider unreachable")

        def exploding_stats(cid):
            raise ConnectionError("provider unreachable")

        findings = replywatch.reconcile_campaigns(
            heyreach_read=exploding_read, heyreach_stats=exploding_stats)

        self.assertTrue(len(findings) > 0,
                        "should have findings even when provider fails")
        for f in findings:
            self.assertEqual(f["verdict"], replywatch.COULD_NOT_ESTABLISH,
                             f"field {f['field']} must be COULD_NOT_ESTABLISH "
                             f"when the provider call fails, not AGREED")

    def test_provider_returns_none_is_not_agreed(self):
        """The provider returns None. The verdict is COULD_NOT_ESTABLISH."""
        campaign = campaigns_state.new_campaign(
            "camp-none", "demo", "None read")
        campaign["heyreach_campaign_id"] = "7002"
        campaign["record_ids"] = ["acme"]
        campaign["status"] = "running"
        campaigns_state.save([campaign])

        def none_read(cid):
            return None

        def none_stats(cid):
            return None

        findings = replywatch.reconcile_campaigns(
            heyreach_read=none_read, heyreach_stats=none_stats)

        self.assertTrue(len(findings) > 0)
        for f in findings:
            self.assertEqual(f["verdict"], replywatch.COULD_NOT_ESTABLISH,
                             f"field {f['field']} must be COULD_NOT_ESTABLISH "
                             f"when provider returns None, not AGREED")

    def test_bison_provider_failure_is_not_agreed(self):
        campaign = campaigns_state.new_campaign(
            "camp-bison-fail", "demo", "Bison fail")
        campaign["bison_campaign_id"] = "9999"
        campaign["record_ids"] = ["acme"]
        campaign["status"] = "running"
        campaigns_state.save([campaign])

        def exploding_read(cid):
            raise RuntimeError("bison down")

        def exploding_leads(cid):
            raise RuntimeError("bison down")

        findings = replywatch.reconcile_campaigns(
            bison_read=exploding_read, bison_lead_count=exploding_leads)

        self.assertTrue(len(findings) > 0)
        for f in findings:
            self.assertEqual(f["verdict"], replywatch.COULD_NOT_ESTABLISH)

    def test_partial_provider_failure_is_still_unestablished_for_that_field(
            self):
        """One call succeeds, the other fails. The failed field is
        COULD_NOT_ESTABLISH, the succeeded one is compared normally."""
        campaign = campaigns_state.new_campaign(
            "camp-partial", "demo", "Partial")
        campaign["heyreach_campaign_id"] = "7003"
        campaign["record_ids"] = ["acme"]
        campaign["status"] = "running"
        campaigns_state.save([campaign])

        def fake_read(cid):
            return {"id": cid, "status": "IN_PROGRESS"}

        def exploding_stats(cid):
            raise ConnectionError("stats endpoint down")

        findings = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=exploding_stats)

        status_finding = next(
            f for f in findings if f["field"] == "status")
        self.assertEqual(status_finding["verdict"], replywatch.AGREED)

        for f in findings:
            if f["field"] != "status":
                self.assertEqual(
                    f["verdict"], replywatch.COULD_NOT_ESTABLISH,
                    f"field {f['field']} should be COULD_NOT_ESTABLISH "
                    f"when stats call fails")


class ReconcileGuardFails(CampaignTest):
    """Acceptance 4: the guard is seen to fail.

    Break the comparison so drift is missed, confirm the test fails, restore.
    """

    def setUp(self):
        super().setUp()
        self.recs = self.seed_records()

    def test_breaking_the_comparison_makes_the_drift_test_fail(self):
        """If _compare_field always returned AGREED, drift tests would fail.

        This is the guard-fail assertion: monkey-patch the comparison to
        always say AGREED, run the drift test, confirm it fails, then
        restore.
        """
        campaign = campaigns_state.new_campaign(
            "camp-guard", "demo", "Guard test")
        campaign["heyreach_campaign_id"] = "8001"
        campaign["record_ids"] = ["acme", "borealis"]
        campaign["status"] = "running"
        campaign["events"] = [{"type": "sent"}]
        campaigns_state.save([campaign])

        def fake_read(cid):
            return {"id": cid, "status": "PAUSED"}

        def fake_stats(cid):
            return {"connectionsSent": 100, "connectionsAccepted": 0,
                    "totalMessageReplies": 50, "uniqueLeadsContacted": 99}

        # First, confirm drift IS detected with the real comparison.
        findings = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=fake_stats)
        drifted = [f for f in findings if f["verdict"] == replywatch.DRIFTED]
        self.assertTrue(len(drifted) > 0,
                        "drift should be detected with real comparison")

        # Now break the comparison to always return AGREED.
        original = replywatch._compare_field

        def broken_compare(field, local_value, provider_value):
            return replywatch.AGREED

        replywatch._compare_field = broken_compare
        try:
            findings_broken = replywatch.reconcile_campaigns(
                heyreach_read=fake_read, heyreach_stats=fake_stats)
            drifted_broken = [f for f in findings_broken
                              if f["verdict"] == replywatch.DRIFTED]
            # With the broken comparison, no drift should be found.
            self.assertEqual(len(drifted_broken), 0,
                             "broken comparison should miss all drift")
        finally:
            replywatch._compare_field = original

        # After restore, drift is detected again.
        findings_restored = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=fake_stats)
        drifted_restored = [f for f in findings_restored
                            if f["verdict"] == replywatch.DRIFTED]
        self.assertTrue(len(drifted_restored) > 0,
                        "drift should be detected again after restore")


class ReconcileOrdering(CampaignTest):
    """Campaigns are ordered by provider id, numerically."""

    def setUp(self):
        super().setUp()
        self.recs = self.seed_records()

    def test_findings_are_ordered_by_provider_id_numerically(self):
        """Provider ids 9, 10, 100 should sort as 9, 10, 100 - not 10, 100, 9.

        created_at is null on the campaigns that actually send, so ordering
        by it silently drops them.
        """
        all_campaigns = []
        for pid in ("100", "9", "10"):
            c = campaigns_state.new_campaign(
                f"camp-{pid}", "demo", f"Campaign {pid}")
            c["heyreach_campaign_id"] = pid
            c["record_ids"] = ["acme"]
            c["status"] = "running"
            all_campaigns.append(c)
        campaigns_state.save(all_campaigns)

        def fake_read(cid):
            return {"id": cid, "status": "PAUSED"}

        def fake_stats(cid):
            return {"connectionsSent": 0, "connectionsAccepted": 0,
                    "totalMessageReplies": 0, "uniqueLeadsContacted": 0}

        findings = replywatch.reconcile_campaigns(
            heyreach_read=fake_read, heyreach_stats=fake_stats)

        # Extract the provider ids in order.
        seen_ids = []
        for f in findings:
            pid = f["provider_id"]
            if not seen_ids or seen_ids[-1] != pid:
                seen_ids.append(pid)

        # Should be numerically ordered: 9, 10, 100.
        self.assertEqual(seen_ids, ["9", "10", "100"])


class ReconcileNoCampaigns(CampaignTest):
    """Edge cases: no campaigns, no bindings."""

    def setUp(self):
        super().setUp()
        self.recs = self.seed_records()

    def test_no_campaigns_produces_no_findings(self):
        campaigns_state.save([])
        findings = replywatch.reconcile_campaigns()
        self.assertEqual(findings, [])

    def test_campaign_without_provider_bindings_is_skipped(self):
        campaign = campaigns_state.new_campaign(
            "camp-nobind", "demo", "No binding")
        campaign["record_ids"] = ["acme"]
        campaigns_state.save([campaign])

        findings = replywatch.reconcile_campaigns()
        self.assertEqual(findings, [])


class DriftSummary(unittest.TestCase):
    """The summary renders the drift table correctly."""

    def test_summary_reports_drifted_and_unestablished(self):
        findings = [
            {"campaign_id": "c1", "provider_id": "1",
             "provider": "heyreach", "field": "status",
             "local": "running", "provider_value": "PAUSED",
             "verdict": replywatch.DRIFTED},
            {"campaign_id": "c2", "provider_id": "2",
             "provider": "heyreach", "field": "lead_count",
             "local": 5, "provider_value": None,
             "verdict": replywatch.COULD_NOT_ESTABLISH},
            {"campaign_id": "c3", "provider_id": "3",
             "provider": "heyreach", "field": "status",
             "local": "running", "provider_value": "IN_PROGRESS",
             "verdict": replywatch.AGREED},
        ]
        lines = []
        replywatch.drift_summary(findings, out=lines.append)
        output = "\n".join(lines)
        self.assertIn("DRIFT", output)
        self.assertIn("COULD NOT ESTABLISH", output)
        self.assertIn("1 drifted", output)
        self.assertIn("1 unestablished", output)
        self.assertIn("1 agreed", output)


if __name__ == "__main__":
    unittest.main()
