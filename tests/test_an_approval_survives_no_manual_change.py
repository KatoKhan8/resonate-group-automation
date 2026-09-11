#!/usr/bin/env python3
"""What was approved is not edited to agree with what happened.

    APPROVED MATERIAL
      -> AN EXTERNAL OR MANUAL PROVIDER CHANGE
      -> THE EXPECTED MATERIAL STAYS AS APPROVED
      -> THE PROVIDER DIFF FAILS
      -> THE APPROVAL INVALIDATES
      -> NOTHING EXECUTES UNTIL A HUMAN RE-APPROVES

REPRODUCED ON 2026-09-11, AND BY THIS SYSTEM'S OWN OPERATOR LOOP.

Campaign 594061 was approved while PAUSED. An operator then unpaused it by
hand in the vendor UI, and the unpause was recorded into canonical state by
setting `provider_status_expected` to IN_PROGRESS. That is the one diff field
that would have flagged an unauthorized activation, and moving it made
`configdiff` report `status: match` - the provider agreeing with itself.

Setting the field back to PAUSED regenerates the recorded approval
fingerprint `037e5c328dad6bb29299` exactly, which is how we know what was
actually approved.

The only reason nothing could execute was luck of ordering:
`provider_status_expected` happens to be inside `campaigns.material()`, so the
fingerprint moved and `approval_is_current` answered False. Nothing asserted
that. This file asserts it, because the next field somebody edits to make a
diff pass may not be in `material()` at all.

The rule is not "the diff must pass". The rule is that a human approved a
specific state of the world, and if the world has moved, a human says so
again.
"""
import copy
import unittest

from src import campaigns
from tests.campaignbase import CampaignTest


APPROVED_STATUS = "PAUSED"
MANUAL_STATUS = "IN_PROGRESS"


class ApprovedMaterialIsNotEditable(CampaignTest):

    def approved(self, **over):
        """A campaign approved against a PAUSED provider campaign."""
        row = {
            "id": "canary-1", "client": "productive", "name": "CANARY",
            "status": campaigns.APPROVED,
            "heyreach_campaign_id": 594061, "heyreach_list_id": 926076,
            "provider_status_expected": APPROVED_STATUS,
            "senders": {"email": [],
                        "linkedin": [{"id": 116968, "daily_limit": 1}]},
            "record_ids": [],
        }
        row.update(over)
        row["approval"] = {"action": "approve", "by": "operator",
                           "at": "2026-09-10T07:20:50+00:00",
                           "fingerprint": campaigns.fingerprint(row, recs=[]),
                           "scope": "one prospect, one sender, one step"}
        return row

    def test_the_approval_is_current_while_nothing_moves(self):
        """A guard that invalidates every approval is an outage."""
        row = self.approved()
        self.assertTrue(campaigns.approval_is_current(row, recs=[]))

    def test_editing_the_expected_status_invalidates_the_approval(self):
        row = self.approved()
        moved = copy.deepcopy(row)
        moved["provider_status_expected"] = MANUAL_STATUS
        self.assertFalse(campaigns.approval_is_current(moved, recs=[]),
                         "the expected material was edited and the approval "
                         "still read as current")

    def test_the_approved_value_is_what_regenerates_the_fingerprint(self):
        """The test that told us what had actually been approved."""
        row = self.approved()
        recorded = row["approval"]["fingerprint"]
        moved = copy.deepcopy(row)
        moved["provider_status_expected"] = MANUAL_STATUS
        self.assertNotEqual(campaigns.fingerprint(moved, recs=[]), recorded)
        back = copy.deepcopy(moved)
        back["provider_status_expected"] = APPROVED_STATUS
        self.assertEqual(campaigns.fingerprint(back, recs=[]), recorded)

    def test_the_expected_status_is_inside_the_fingerprint_at_all(self):
        """Stated on its own, because the whole guard rests on it.

        If `provider_status_expected` ever leaves `campaigns.material()`, the
        approval would survive an edit to it and nothing else here would
        notice - every other test in this class would still pass.
        """
        row = self.approved()
        other = copy.deepcopy(row)
        other["provider_status_expected"] = MANUAL_STATUS
        self.assertNotEqual(campaigns.fingerprint(row, recs=[]),
                            campaigns.fingerprint(other, recs=[]))

    def test_a_stale_approval_is_not_an_approval(self):
        row = self.approved()
        row["provider_status_expected"] = MANUAL_STATUS
        self.assertFalse(campaigns.is_approved(row, recs=[]))

    def test_re_approving_the_moved_state_is_what_restores_it(self):
        """The remedy is a human approving the new material, not an edit."""
        row = self.approved()
        row["provider_status_expected"] = MANUAL_STATUS
        self.assertFalse(campaigns.approval_is_current(row, recs=[]))
        row["approval"] = {"action": "approve", "by": "operator",
                           "at": "2026-09-11T18:00:00+00:00",
                           "fingerprint": campaigns.fingerprint(row, recs=[])}
        self.assertTrue(campaigns.approval_is_current(row, recs=[]))

    def test_a_rejection_is_never_current(self):
        row = self.approved()
        row["approval"] = dict(row["approval"], action="reject")
        self.assertFalse(campaigns.approval_is_current(row, recs=[]))


class EveryApprovalFieldIsCovered(CampaignTest):
    """Each field a human weighs must move the fingerprint.

    A field inside the approval decision but outside `material()` can be
    changed after approval with no trace, which is exactly the shape of the
    defect above.
    """

    def base(self):
        return {"id": "canary-2", "client": "productive", "name": "CANARY",
                "status": campaigns.APPROVED,
                "heyreach_campaign_id": 594061, "heyreach_list_id": 926076,
                "provider_status_expected": APPROVED_STATUS,
                "senders": {"email": [],
                            "linkedin": [{"id": 116968, "daily_limit": 1}]},
                "record_ids": []}

    def test_each_one_moves_it(self):
        row = self.base()
        before = campaigns.fingerprint(row, recs=[])
        # THE REAL SCHEMA'S NAMES. The first version of this test invented
        # `sender_id` and `provider_campaign_id`, which this repo does not
        # use, and "failed" against fields no campaign carries - a fixture
        # error reported as a missing guard. The names below are the ones in
        # `work/campaigns.jsonl`.
        for field, value in (("provider_status_expected", MANUAL_STATUS),
                             ("heyreach_campaign_id", 594060),
                             ("heyreach_list_id", 926077),
                             ("senders", {"email": [], "linkedin": [
                                 {"id": 999999, "daily_limit": 1}]}),
                             ("daily_volume", {"linkedin": 50}),
                             ("record_ids", ["someone-else"])):
            with self.subTest(field=field):
                moved = copy.deepcopy(row)
                moved[field] = value
                self.assertNotEqual(
                    campaigns.fingerprint(moved, recs=[]), before,
                    f"{field} can be changed after approval without "
                    f"invalidating it")


class HoistingTheVerdictDoesNotWeakenTheGate(CampaignTest):
    """The approval verdict is computed once per batch. It is a FACT, not an
    authorization.

    `eligibility._campaign` asked `campaigns.approval_is_current` once per
    contact per step, and each call rebuilt the cadence for every record in
    the campaign. Measured 2026-09-11: 5.03 x K^2 `cadence.build` calls, K^2.27
    overall - 40.3s for a 160-record campaign, projecting 60 days at 30,000.
    Hoisted, the same loop is K^0.99 and 0.24s.

    The safety argument, asserted rather than assumed: a hoisted answer may
    HOLD a step and may never RELEASE one, because `executionguard` recomputes
    the same gate at send time on its own path and accepts nothing from here.
    """

    def campaign(self, recs):
        row = {"id": "c", "client": "productive", "name": "C",
               "status": campaigns.APPROVED, "record_ids": [r["id"] for r in recs],
               "heyreach_campaign_id": 1, "heyreach_list_id": 2,
               "provider_status_expected": APPROVED_STATUS,
               "senders": {"email": [],
                           "linkedin": [{"id": 1, "daily_limit": 1}]}}
        row["approval"] = {"action": "approve", "by": "x", "at": "2026-09-10",
                           "fingerprint": campaigns.fingerprint(row, recs)}
        return row

    def test_the_hoisted_answer_matches_the_computed_one(self):
        from src import eligibility
        recs = []
        row = self.campaign(recs)
        computed = eligibility._campaign(row, recs, None)
        hoisted = eligibility._campaign(
            row, recs, None, campaigns.approval_is_current(row, recs, None))
        self.assertEqual(computed, hoisted)

    def test_a_moved_campaign_is_held_either_way(self):
        from src import eligibility
        recs = []
        row = self.campaign(recs)
        row["provider_status_expected"] = MANUAL_STATUS
        self.assertEqual(eligibility._campaign(row, recs, None),
                         eligibility.HELD_CAMPAIGN_STALE)
        self.assertEqual(
            eligibility._campaign(row, recs, None,
                                  campaigns.approval_is_current(row, recs, None)),
            eligibility.HELD_CAMPAIGN_STALE)

    def test_a_false_hoist_holds_and_never_releases(self):
        """The conservative direction is the safe one."""
        from src import eligibility
        recs = []
        row = self.campaign(recs)
        self.assertEqual(eligibility._campaign(row, recs, None, False),
                         eligibility.HELD_CAMPAIGN_STALE)

    def test_the_send_gate_takes_no_hoist(self):
        """What makes the hoist safe, asserted on the SIGNATURE, not the text.

        The first version of this test read `inspect.getsource` and asserted
        that "approval_is_current" appeared in it. Replacing the actual call
        with `True` left the name behind in the comment above it, so the test
        passed against a gate that had been deleted - the exact failure
        CLAUDE.md describes, produced here on the first attempt.

        The behaviour itself is pinned where it belongs, against the real
        guard: `test_no_write_happens_without_every_gate` refuses at
        `campaign_approval` in six tests, `test_changing_the_expected_status_
        blocks` among them. Mutating the call to `True` reddens all six.

        What remains worth asserting here is narrow and structural: no batch
        answer can reach the send gate, because there is no parameter for one.
        """
        import inspect
        from src import executionguard
        self.assertNotIn("approval_current",
                         inspect.signature(executionguard.authorize)
                         .parameters)


if __name__ == "__main__":
    unittest.main()
