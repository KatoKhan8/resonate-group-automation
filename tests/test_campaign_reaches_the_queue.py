"""A campaign built in the product never reached the screen that lists work.

`orchestrator.prepare` is the only thing that sets `ready_for_review`, and
it is the only caller of `assign_cadence_arms`. It had no web caller at
all. `api.create_campaign` created a draft, saved it, and stopped there;
the approval handler transitions from `ready_for_review` and `decide` then
forces `approved`, so a campaign went draft straight to approved without
passing through either status.

`src/tasks.py` files its rows for exactly those two statuses. So `/tasks` -
the screen the product presents as everything waiting - never showed a
campaign awaiting approval, for any campaign built in the product. The jobs
screen said the opposite in as many words, telling the operator that
`PREPARE_CAMPAIGN` "is the campaign builder, which is its own screen".

The quieter half is the cadence experiment. `assign_cadence_arms` is
reached only from `prepare`, and explains in its own docstring that
assignment happens before the approval fingerprint is taken, "so what a
reviewer approves already includes which arm each contact is in". With
`prepare` unreachable, that ran only from a test.

It is a no-op today for a separate reason, recorded in `PRODUCT-GAPS.md`
rather than fixed here: `orchestrator.set_cadence_experiment` - the only
thing that attaches an experiment to a campaign - has no caller anywhere
outside the test suite, so no real campaign has one to assign arms from.
Its own docstring names that as "the failure this repository keeps
producing". Wiring the call path is this change; giving somebody a way to
author an experiment is a feature, and not one to invent while clearing
defects.

This is the third orphaned path found in a day - after the import's missing
Commit button and the approval's missing Reject - and the largest: not a
control nobody rendered, but a lifecycle step nobody called.
"""
import unittest

from src import campaigns as campaign_store
from src import store, tasks
from src.repo import Repo
from src.web import api
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
WORKSPACE = "productive"


class ABuiltCampaignIsPrepared(WebTest):

    def setUp(self):
        self._campaigns = [dict(c) for c in campaign_store.load()]
        self._records = [dict(r) for r in store.load()]
        self.repo = Repo.for_user(OPERATOR, WORKSPACE)

    def tearDown(self):
        campaign_store.save(self._campaigns)
        store.save(self._records)

    def free_segment(self):
        """A segment whose companies are not already in a campaign."""
        taken = set()
        for campaign in self.repo.campaigns():
            taken.update(campaign.get("record_ids") or [])
        for rec in self.repo.records():
            key = (rec.get("qualification") or {}).get("segment_key")
            if key and rec["id"] not in taken:
                return key
        return None

    def built(self):
        segment = self.free_segment()
        if not segment:
            self.skipTest("every segment in the estate is already in a "
                          "campaign")
        return api.create_campaign(self.repo, segment, "Walkthrough campaign",
                                   by=OPERATOR)

    # --------------------------------------------------------- the defect

    def test_it_is_ready_for_review_rather_than_a_draft(self):
        self.assertEqual(self.built()["status"],
                         campaign_store.READY_FOR_REVIEW)

    def test_the_work_queue_lists_it(self):
        """The screen the product calls everything waiting."""
        campaign = self.built()
        rows = tasks.collect(WORKSPACE)
        mine = [r for r in rows
                if r.get("object_id") == campaign["campaign_id"]]
        self.assertTrue(
            mine,
            "the work queue does not mention a campaign built in the "
            f"product: {[r['kind'] for r in rows]}")

    def test_arm_assignment_is_reached(self):
        """`assign_cadence_arms` had exactly one caller - `prepare` - and
        `prepare` had none, so the whole path ran only from a test.

        A campaign with no experiment gets no arm, and that is correct
        rather than a defect: `assign_cadence_arms` returns 0 immediately
        when the campaign carries no experiment. So what this asserts is
        that the *call happens* - the summary reports the count - which is
        the link that was missing.
        """
        from src import orchestrator

        campaign = self.built()
        mine = [r for r in store.load()
                if r["id"] in set(campaign.get("record_ids") or [])]
        summary = orchestrator.prepare(campaign, mine, self.repo.config())
        self.assertIn("cadence_arms_assigned", summary)

    def test_it_is_still_saved_and_findable(self):
        campaign = self.built()
        self.assertIsNotNone(self.repo.campaign(campaign["campaign_id"]))

    def test_it_is_not_approved_by_being_prepared(self):
        """Preparing is not deciding. Nothing here may approve."""
        campaign = self.built()
        self.assertIsNone(campaign.get("approval"))
        self.assertNotEqual(campaign["status"], campaign_store.APPROVED)


if __name__ == "__main__":
    unittest.main()
