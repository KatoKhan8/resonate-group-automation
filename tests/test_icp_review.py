"""The human decision on a company that did not qualify on evidence.

PLAYBOOK section 1 is a table: `qualified` gets person credits up to the tier
cap, and `review`, `rejected` and `unknown` get zero - `review` and `unknown`
"until a human decides". Until this existed there was no way to record that a
human had decided anything, and `dmplan.may_enrich` said as much in a string
about a field that did not exist.

What is tested here is mostly what a review may *not* do. A reviewer clicking
a button in a browser must not be able to spend money the client never agreed
to spend, and a review recorded against facts that have since changed must not
keep authorising anything.
"""
import unittest

from src import dmplan, icp, qualify
from tests.campaignbase import CampaignTest
from tests.test_icp import AGENCY_TEXT, rec as make_rec


def agency(rid="reviewme", **kw):
    """A company the engine will actually reach a verdict on."""
    return make_rec(rid=rid, industry="Marketing", employees=90,
                    specialties=["digital marketing", "content marketing"],
                    country="United Kingdom", city="London",
                    description=AGENCY_TEXT, **kw)


class RecordingAReview(CampaignTest):

    def qualified_record(self, **kw):
        record = agency(**kw)
        qualify.company(record)
        return record

    def test_a_review_needs_a_verdict_to_be_about(self):
        rec = agency(rid="unqualified")
        with self.assertRaises(qualify.BadDecision):
            qualify.record_review(rec, qualify.ACCEPT, by="operator")

    def test_only_the_two_decisions_there_are_may_be_recorded(self):
        rec = self.qualified_record()
        with self.assertRaises(qualify.BadDecision):
            qualify.record_review(rec, "maybe", by="operator")
        with self.assertRaises(qualify.BadDecision):
            qualify.record_review(rec, "approve", by="operator")

    def test_a_review_changes_no_verdict(self):
        """The score is what the evidence earned. A person is a second fact."""
        rec = self.qualified_record()
        before = dict(rec["qualification"]["verdict"])
        qualify.record_review(rec, qualify.REJECT, by="operator",
                              note="they are a client already")
        self.assertEqual(rec["qualification"]["verdict"], before)

    def test_the_review_records_who_when_and_what_they_were_looking_at(self):
        rec = self.qualified_record()
        review = qualify.record_review(rec, qualify.ACCEPT, by="ops@x.test",
                                       note="checked their site")
        self.assertEqual(review["by"], "ops@x.test")
        self.assertEqual(review["decision"], qualify.ACCEPT)
        self.assertEqual(review["reviewed_status"],
                         rec["qualification"]["verdict"]["icp_status"])
        self.assertTrue(review["at"])
        self.assertEqual(review["note"], "checked their site")

    def test_a_note_cannot_be_used_as_storage(self):
        rec = self.qualified_record()
        review = qualify.record_review(rec, qualify.ACCEPT, by="x",
                                       note="n" * 5000)
        self.assertLessEqual(len(review["note"]), 500)


class AReviewGoesStaleWhenTheFactsMove(CampaignTest):
    """The same rule the campaign and enrichment approvals already use.

    An approval that outlives the thing it approved is not an approval, and
    this one authorises spending money on a company that did not qualify.
    """

    def reviewed(self):
        record = agency(rid="moving")
        qualify.company(record)
        qualify.record_review(record, qualify.ACCEPT, by="operator")
        return record

    def test_a_fresh_review_is_returned(self):
        rec = self.reviewed()
        self.assertIsNotNone(qualify.review_of(rec))
        self.assertIsNone(qualify.stale_review_of(rec))

    def test_changing_the_company_facts_retires_the_review(self):
        rec = self.reviewed()
        rec["company_facts"]["employees"] = 900
        qualify.company(rec)
        self.assertIsNone(qualify.review_of(rec),
                          "a review of the old facts still counted")
        self.assertIsNotNone(qualify.stale_review_of(rec),
                             "the stale review was lost rather than reported")

    def test_the_spend_gate_uses_the_same_staleness_rule(self):
        rec = self.reviewed()
        rec["company_facts"]["employees"] = 900
        qualify.company(rec)
        self.assertIsNone(dmplan.human_review(rec))


class WhatAReviewMayNotDo(CampaignTest):
    """Accepting is weaker than rejecting, on purpose."""

    def entries(self, status, rec=None):
        rec = rec if rec is not None else {"id": "a", "domain": "a.test"}
        return [{
            "record": rec,
            "verdict": {"icp_status": status,
                        "icp_tier": icp.TIER_REVIEW if status != icp.QUALIFIED
                        else icp.TIER_A},
            "persona_plan": {"max_contacts_to_enrich": 2,
                             "target_titles": ["CEO"], "cap_reason": "tier A"},
        }]

    def reviewed_record(self, decision, status=icp.REVIEW):
        rec = {"id": "a", "domain": "a.test",
               "qualification": {"inputs_fingerprint": "fixed",
                                 "verdict": {"icp_status": status,
                                             "icp_tier": icp.TIER_REVIEW}}}
        qualify.record_review(rec, decision, by="operator")
        return rec

    def test_accepting_does_not_by_itself_unlock_a_review_company(self):
        """The default config has not opted in, so the answer is still no."""
        rec = self.reviewed_record(qualify.ACCEPT)
        entries = self.entries(icp.REVIEW, rec)
        batch = {}
        dmplan.approve(batch, self.entries(icp.QUALIFIED), by="operator")
        allowed, why = dmplan.may_enrich(batch, entries, rec,
                                         entries[0]["verdict"])
        self.assertFalse(allowed)
        self.assertIn("allow_review_enrichment", why)

    def test_the_client_policy_plus_a_review_is_what_unlocks_it(self):
        rec = self.reviewed_record(qualify.ACCEPT)
        entries = self.entries(icp.REVIEW, rec)
        batch = {}
        dmplan.approve(batch, entries, by="operator")
        config = {"dm_plan": {"allow_review_enrichment": True}}
        allowed, why = dmplan.may_enrich(batch, entries, rec,
                                         entries[0]["verdict"], config)
        self.assertTrue(allowed, why)
        self.assertIn("operator", why)

    def test_the_policy_alone_is_not_enough_without_a_review(self):
        rec = {"id": "a", "domain": "a.test"}
        entries = self.entries(icp.REVIEW, rec)
        batch = {}
        dmplan.approve(batch, entries, by="operator")
        config = {"dm_plan": {"allow_review_enrichment": True}}
        allowed, why = dmplan.may_enrich(batch, entries, rec,
                                         entries[0]["verdict"], config)
        self.assertFalse(allowed)
        self.assertIn("no review has been recorded", why)

    def test_an_unlocked_review_company_still_needs_a_current_batch_approval(self):
        """A human decision is one gate. It does not replace the cost cap."""
        rec = self.reviewed_record(qualify.ACCEPT)
        entries = self.entries(icp.REVIEW, rec)
        config = {"dm_plan": {"allow_review_enrichment": True}}
        allowed, why = dmplan.may_enrich({}, entries, rec,
                                         entries[0]["verdict"], config)
        self.assertFalse(allowed)
        self.assertIn("no person-enrichment approval", why)

    def test_rejecting_needs_no_policy_and_outranks_a_qualified_verdict(self):
        """Refusing to spend is never the dangerous direction."""
        rec = self.reviewed_record(qualify.REJECT, status=icp.QUALIFIED)
        entries = self.entries(icp.QUALIFIED, rec)
        batch = {}
        dmplan.approve(batch, entries, by="operator")
        allowed, why = dmplan.may_enrich(batch, entries, rec,
                                         {"icp_status": icp.QUALIFIED,
                                          "icp_tier": icp.TIER_A})
        self.assertFalse(allowed)
        self.assertIn("rejected it", why)

    def test_a_rejected_company_is_still_refused_whatever_a_review_says(self):
        rec = self.reviewed_record(qualify.ACCEPT, status=icp.REJECTED)
        entries = self.entries(icp.QUALIFIED)
        batch = {}
        dmplan.approve(batch, entries, by="operator")
        config = {"dm_plan": {"allow_review_enrichment": True}}
        allowed, why = dmplan.may_enrich(
            batch, entries, rec,
            {"icp_status": icp.REJECTED, "icp_tier": icp.TIER_NOT_ICP}, config)
        self.assertFalse(allowed)
        self.assertIn("ever", why)

    def test_a_stale_acceptance_stops_unlocking_anything(self):
        rec = self.reviewed_record(qualify.ACCEPT)
        rec["qualification"]["inputs_fingerprint"] = "moved"
        entries = self.entries(icp.REVIEW, rec)
        batch = {}
        dmplan.approve(batch, entries, by="operator")
        config = {"dm_plan": {"allow_review_enrichment": True}}
        allowed, why = dmplan.may_enrich(batch, entries, rec,
                                         entries[0]["verdict"], config)
        self.assertFalse(allowed)
        self.assertIn("no review has been recorded", why)


class TheQueueDoesNotHandBackFinishedWork(CampaignTest):

    def test_a_rejected_review_leaves_the_review_state(self):
        rec = {"id": "a", "domain": "a.test",
               "qualification": {"inputs_fingerprint": "fixed",
                                 "verdict": {"icp_status": icp.REVIEW,
                                             "icp_tier": icp.TIER_REVIEW}}}
        self.assertEqual(qualify.state_of(rec), dmplan.REVIEW_REQUIRED)
        qualify.record_review(rec, qualify.REJECT, by="operator")
        self.assertEqual(qualify.state_of(rec), dmplan.REJECTED)

    def test_an_accepted_review_stays_visible_as_review_required(self):
        """Accepted is not the same as enriched, and the screen must not lie."""
        rec = {"id": "a", "domain": "a.test",
               "qualification": {"inputs_fingerprint": "fixed",
                                 "verdict": {"icp_status": icp.REVIEW,
                                             "icp_tier": icp.TIER_REVIEW}}}
        qualify.record_review(rec, qualify.ACCEPT, by="operator")
        self.assertEqual(qualify.state_of(rec), dmplan.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
