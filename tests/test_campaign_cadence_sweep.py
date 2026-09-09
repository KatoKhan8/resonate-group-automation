"""The rest of the readers, and the one that could not be launched.

`tests/test_campaign_cadence_wiring.py` covers the send-and-approve path.
This covers everything else that builds a timeline for a campaign: the
plan, the QA report, the funnel, the preview, the replay, the touch
history, and - the one with teeth - drafting approval.

`approve.approvable_steps` enumerates every step a human could be asked to
approve, and `fully_approved` requires all of them. Built against the
module constant, a four-step campaign's records list seven, two of which
nobody will ever draft, so the record can never reach `approved` and the
campaign can never be launched. A cadence experiment comparing four steps
against seven would have had one arm that could not run.
"""
import ast
import inspect
import unittest

from src import approve, cadence, store
from tests.campaignbase import CampaignTest
from tests.test_campaign_cadence_wiring import DROPPED, FOUR


class AFourStepRecord(CampaignTest):
    """Drafted and approved against a campaign of four steps."""

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        self.draft_everything(recs)
        store.save(recs)
        self.recs = store.load()
        self.campaign = self.make_campaign(self.recs)
        self.campaign[cadence.CADENCE_KEY] = list(FOUR)
        self.save_campaign(self.campaign)
        self.rec = self.recs[0]


class WhatAHumanIsAskedToApprove(AFourStepRecord):

    def keys(self, campaign):
        return sorted({step_key for _, step_key, _ in
                       approve.approvable_steps(self.rec, self.config,
                                                campaign=campaign)})

    def test_it_asks_for_the_campaigns_steps(self):
        asked = self.keys(self.campaign)
        self.assertTrue(asked)
        for key in DROPPED:
            self.assertNotIn(key, asked)

    def test_without_the_campaign_it_asks_for_the_constants(self):
        """The defect, stated as a difference."""
        self.assertTrue(set(self.keys(None)) - set(self.keys(self.campaign)))

    def test_a_record_can_reach_approved(self):
        """The one with teeth. Two steps nobody will ever draft stayed
        outstanding for ever, so the record never left `drafted` and the
        campaign's own launch gate never opened."""
        for contact_key, step_key, step in approve.approvable_steps(
                self.rec, self.config, campaign=self.campaign):
            approve.approve_step(self.rec, contact_key, step_key, by="zb",
                                 config=self.config, step=step, sync=False,
                                 campaign=self.campaign)
        self.assertTrue(approve.fully_approved(self.rec, self.config,
                                               campaign=self.campaign))
        self.assertEqual(
            approve.sync_state(self.rec, self.config, self.campaign),
            "approved")

    def test_and_could_not_before(self):
        """Same approvals, judged against the constant: still not done."""
        for contact_key, step_key, step in approve.approvable_steps(
                self.rec, self.config, campaign=self.campaign):
            approve.approve_step(self.rec, contact_key, step_key, by="zb",
                                 config=self.config, step=step, sync=False,
                                 campaign=self.campaign)
        self.assertFalse(approve.fully_approved(self.rec, self.config))

    def test_a_record_in_no_campaign_is_judged_as_it_always_was(self):
        self.assertEqual(self.keys(None),
                         sorted({step_key for _, step_key, _ in
                                 approve.approvable_steps(self.rec,
                                                          self.config)}))


class TheApprovalQueueAsksForTheCampaignsSteps(AFourStepRecord):
    """`approve.pending` is the operator's queue. Built against the
    constant it asks a human to approve steps that will never be sent, and
    the two they will never see are the ones that keep the record out of
    `approved`."""

    def steps_in_queue(self, rows=None):
        found = approve.pending(self.recs, campaign_rows=rows)
        return sorted({row["step"]
                       for row in found["waiting"] + found["blocked"]
                       if row["id"] == self.rec["id"]})

    def test_the_queue_holds_only_the_campaigns_steps(self):
        """`campaign_rows` is left to default, so this also covers the
        lookup reading the campaign from where it is stored."""
        queued = self.steps_in_queue()
        self.assertTrue(queued)
        for key in DROPPED:
            self.assertNotIn(key, queued)

    def test_with_no_campaigns_in_play_it_asks_for_the_constants(self):
        self.assertTrue(set(self.steps_in_queue(rows=[]))
                        - set(self.steps_in_queue()))


class TheDuplicateScanComparesTheCampaignsSteps(CampaignTest):
    """Two bodies are only duplicates of each other if both steps are in
    the sequence that will run. Judged against the constant the scan both
    misses pairs and invents them."""

    # day8 and day12 are the same template, so they render the same body
    # for the same contact. Neither pair exists in the constant.
    DUPLICATING = FOUR + [{"key": "day12", "day": 12, "channel": "email",
                           "template": "breakup"}]

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        self.draft_everything(recs)
        store.save(recs)
        self.recs = store.load()
        self.campaign = self.make_campaign(self.recs)
        self.campaign[cadence.CADENCE_KEY] = list(self.DUPLICATING)
        self.save_campaign(self.campaign)

    def bodies(self, campaign):
        from src import duplicates

        return [f for f in duplicates.find(self.recs, self.config,
                                           campaign=campaign)
                if f["code"] == duplicates.DUPLICATE_BODY]

    def test_it_finds_the_pair_the_campaign_actually_contains(self):
        found = self.bodies(self.campaign)
        self.assertTrue(found, "the fixture produced no duplicate at all")
        pairs = [sorted(row.get("steps") or []) for row in found]
        self.assertIn(["day12", "day8"], pairs, pairs)

    def test_it_does_not_find_it_against_the_constant(self):
        """The same records, the same config, judged against a sequence
        that contains neither step."""
        self.assertEqual(self.bodies(None), [])


class TheTouchHistoryFollowsTheCampaign(AFourStepRecord):
    """What a later message may claim about an earlier one. Built against
    the constant it can describe a step the campaign does not contain."""

    def steps_in(self, campaign):
        from src import touch

        found = touch.history(self.rec, self.rec["contacts"][0]["key"],
                              config=self.config, campaign=campaign)
        rows = found if isinstance(found, list) else found.get("steps") or []
        return sorted({row.get("step") for row in rows if row.get("step")})

    def test_it_describes_only_the_campaigns_steps(self):
        described = self.steps_in(self.campaign)
        self.assertEqual(described, sorted(s["key"] for s in FOUR))
        for key in DROPPED:
            self.assertNotIn(key, described)

    def test_without_the_campaign_it_describes_the_constants(self):
        """Stated as a difference so the test above cannot pass by
        describing nothing at all."""
        self.assertTrue(set(self.steps_in(None))
                        - set(self.steps_in(self.campaign)))


class EveryRemainingTimelineIsGivenItsCampaign(unittest.TestCase):
    """The regression guard, extended to the modules swept here.

    Structural because the failure is an omitted keyword argument at a call
    site.

    `benchmark`, `simulator` and `demo_outreach` are deliberately absent.
    They are measurement and demo surfaces: nothing in their call paths has
    a campaign, and giving them a parameter nobody passes would be a wire
    that looks connected. That remainder is recorded in PRODUCT-GAPS.
    """

    MODULES = ("approve", "plan", "qa", "report", "preview", "replaysim",
               "touch", "duplicates", "coherence", "campaigns",
               "eligibility", "push")

    def test_every_swept_module_passes_the_campaign(self):
        import importlib

        for name in self.MODULES:
            module = importlib.import_module(f"src.{name}")
            calls = [
                node for node in ast.walk(
                    ast.parse(inspect.getsource(module)))
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "build"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "cadence"]
            self.assertTrue(calls, f"src/{name}.py builds no timeline")
            for node in calls:
                self.assertIn(
                    "campaign", [kw.arg for kw in node.keywords],
                    f"cadence.build at src/{name}.py line {node.lineno} does "
                    "not pass a campaign")


if __name__ == "__main__":
    unittest.main()
