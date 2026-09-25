"""A top-up into a sending campaign needs the operator's approval.

`resume_campaign` was gated and `attach_leads` was not, so the standing
directive - "no lead is attached to an active campaign without a review file
approved by me" - could be satisfied on paper while a script attached two
hundred people to a campaign that was already sending. It never calls resume,
so it was never asked.
"""
import unittest
from unittest import mock

from src import reviewapproval
from src.providers import bison


class TopUpNeedsApproval(unittest.TestCase):

    def _campaign(self, status):
        return mock.patch.object(bison, "campaign",
                                 return_value={"status": status})

    def test_attaching_to_an_active_campaign_is_refused(self):
        with self._campaign("active"), \
             mock.patch.object(reviewapproval, "approval_for", return_value=None):
            with self.assertRaises(reviewapproval.NotApproved):
                bison.attach_leads(493, [1, 2, 3])

    def test_every_live_state_is_refused_not_just_active(self):
        for state in bison.LIVE_CAMPAIGN_STATES:
            with self.subTest(state=state):
                with self._campaign(state), \
                     mock.patch.object(reviewapproval, "approval_for",
                                       return_value=None):
                    with self.assertRaises(reviewapproval.NotApproved):
                        bison.attach_leads(493, [1])

    def test_staging_into_a_paused_campaign_is_allowed(self):
        # Staging MUST stay possible without approval or no campaign could
        # ever be built to be approved. The gate is on reaching people.
        with self._campaign("paused"), \
             mock.patch.object(bison, "membership", return_value={1: "paused"}), \
             mock.patch.object(bison, "campaign_lead_count", return_value=1):
            out = bison.attach_leads(503, [1])
        self.assertEqual(out["already"], [1])

    def test_an_approved_live_campaign_may_be_topped_up(self):
        approval = {"campaign": "493", "by": "zvonimir", "review_hash": "abc"}
        with self._campaign("active"), \
             mock.patch.object(reviewapproval, "approval_for", return_value=approval), \
             mock.patch.object(bison, "membership", return_value={1: "active"}), \
             mock.patch.object(bison, "campaign_lead_count", return_value=1):
            out = bison.attach_leads(493, [1])
        self.assertEqual(out["already"], [1])

    def test_an_unreadable_status_refuses_rather_than_guesses(self):
        # The recurring defect: a check that passes because the thing it
        # checks is absent. An unreadable status is not a paused campaign.
        with mock.patch.object(bison, "campaign", side_effect=RuntimeError("502")):
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                bison.attach_leads(493, [1])
        self.assertIn("could not be read", str(caught.exception))

    def test_the_gate_runs_before_anything_is_written(self):
        # If the refusal happened after the membership read, a provider call
        # would already have been made on a campaign we were refusing to touch.
        with self._campaign("active"), \
             mock.patch.object(reviewapproval, "approval_for", return_value=None), \
             mock.patch.object(bison, "membership") as member:
            with self.assertRaises(reviewapproval.NotApproved):
                bison.attach_leads(493, [1])
        member.assert_not_called()


if __name__ == "__main__":
    unittest.main()
