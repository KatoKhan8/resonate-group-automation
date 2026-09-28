"""An approval does not survive a re-render.

TASK-328. The review hash was recorded by `reviewapproval.record`, quoted to
the operator, and stored - but never verified by any production call site.
`resume_campaign`, `activate_campaign` and the `attach_leads` top-up path
each called `reviewapproval.require(campaign_id)` without forwarding
`review_hash`, so the mismatch branch inside `require` was unreachable.

The consequence: approval was campaign-level and permanent. Once a campaign
carried any approval row, a later resume, activate or attach top-up passed
the gate carrying whatever copy was current - including copy regenerated
after the operator approved. On 2026-09-25, 64 emails carrying a different
agency's pitch reached real prospects through exactly this gap.

This test proves the hash now flows from caller to gate, and that a mismatch
refuses with a message naming the campaign and both hashes.
"""
import inspect
import unittest
from unittest import mock

from src import reviewapproval
from src.providers import bison, heyreach


HASH_A = "aabb112233445566"
HASH_B = "ff00112233445566"
CAMPAIGN_ID = "493"


def _approval_row(campaign=CAMPAIGN_ID, review_hash=HASH_A):
    return {"campaign": str(campaign), "review_hash": review_hash,
            "by": reviewapproval.OPERATOR, "at": "2026-09-28T00:00:00",
            "source": "test", "note": ""}


class TheGateRefusesAMismatchedHash(unittest.TestCase):
    """The whole task: a hash that does not match the recorded one refuses,
    and the refusal names the campaign and both hashes."""

    def test_a_mismatched_hash_refuses_and_names_both_sides(self):
        rows = [_approval_row(review_hash=HASH_A)]
        with self.assertRaises(reviewapproval.NotApproved) as caught:
            reviewapproval.require(CAMPAIGN_ID, review_hash=HASH_B, rows=rows)
        msg = str(caught.exception)
        self.assertIn(CAMPAIGN_ID, msg)
        self.assertIn(HASH_A, msg)
        self.assertIn(HASH_B, msg)

    def test_a_matching_hash_proceeds_past_the_gate(self):
        rows = [_approval_row(review_hash=HASH_A)]
        result = reviewapproval.require(CAMPAIGN_ID, review_hash=HASH_A,
                                        rows=rows)
        self.assertIsNotNone(result)
        self.assertEqual(result["review_hash"], HASH_A)

    def test_omitting_the_hash_proceeds(self):
        """Current documented behaviour: the default is permissive so that
        pre-existing approvals are not broken. Making it mandatory is an
        operator decision, not a code decision (see TASK-328)."""
        rows = [_approval_row(review_hash=HASH_A)]
        result = reviewapproval.require(CAMPAIGN_ID, rows=rows)
        self.assertIsNotNone(result)


class EveryCallSiteForwardsTheHash(unittest.TestCase):
    """Assert on BEHAVIOUR, not on the text of the source. A grep for the
    parameter name would pass on a comment."""

    def test_resume_campaign_accepts_review_hash(self):
        sig = inspect.signature(bison.resume_campaign)
        self.assertIn("review_hash", sig.parameters)

    def test_activate_campaign_accepts_review_hash(self):
        sig = inspect.signature(heyreach.activate_campaign)
        self.assertIn("review_hash", sig.parameters)

    def test_attach_leads_accepts_review_hash(self):
        sig = inspect.signature(bison.attach_leads)
        self.assertIn("review_hash", sig.parameters)

    def test_resume_campaign_refuses_on_hash_mismatch(self):
        """Driven through the REAL entry point, not through require directly.
        The mismatch must propagate from resume_campaign to the gate."""
        rows = [_approval_row(review_hash=HASH_A)]
        with mock.patch.object(reviewapproval, "load", return_value=rows):
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                bison.resume_campaign(CAMPAIGN_ID, review_hash=HASH_B)
        msg = str(caught.exception)
        self.assertIn(HASH_A, msg)
        self.assertIn(HASH_B, msg)

    def test_resume_campaign_proceeds_on_matching_hash(self):
        """The positive direction: matching hash passes the gate. The call
        will fail later (no transport), but it gets PAST the approval."""
        rows = [_approval_row(review_hash=HASH_A)]
        with mock.patch.object(reviewapproval, "load", return_value=rows), \
             mock.patch.object(bison, "campaign_lead_count", return_value=0), \
             mock.patch.object(bison, "campaign",
                               return_value={"status": "paused"}), \
             mock.patch("src.providers.bison._post",
                        side_effect=RuntimeError("stop")):
            try:
                bison.resume_campaign(CAMPAIGN_ID, expect_leads=0,
                                      review_hash=HASH_A)
            except RuntimeError:
                pass
            except reviewapproval.NotApproved:
                self.fail("resume_campaign refused a matching hash")

    def test_attach_leads_refuses_on_hash_mismatch_into_live(self):
        """attach_leads into a live campaign with a mismatched hash refuses.
        Uses a fake campaign() return - no provider call."""
        rows = [_approval_row(review_hash=HASH_A)]
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "load", return_value=rows):
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                bison.attach_leads(CAMPAIGN_ID, [1], review_hash=HASH_B)
        msg = str(caught.exception)
        self.assertIn(HASH_A, msg)
        self.assertIn(HASH_B, msg)

    def test_attach_leads_proceeds_on_matching_hash(self):
        """Positive: matching hash, paused campaign - gets past the gate."""
        rows = [_approval_row(review_hash=HASH_A)]
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "paused"}), \
             mock.patch.object(reviewapproval, "load", return_value=rows), \
             mock.patch.object(bison, "membership", return_value={1: "paused"}), \
             mock.patch.object(bison, "campaign_lead_count", return_value=1):
            out = bison.attach_leads(CAMPAIGN_ID, [1], review_hash=HASH_A)
        self.assertEqual(out["already"], [1])

    def test_activate_campaign_refuses_on_hash_mismatch(self):
        """Driven through the REAL heyreach entry point."""
        rows = [_approval_row(review_hash=HASH_A)]
        with mock.patch.object(reviewapproval, "load", return_value=rows):
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                heyreach.activate_campaign(CAMPAIGN_ID, review_hash=HASH_B)
        msg = str(caught.exception)
        self.assertIn(HASH_A, msg)
        self.assertIn(HASH_B, msg)


class NoProviderCallIsMade(unittest.TestCase):
    """The refusal happens before any transport call. A mismatched hash must
    not reach the network."""

    def test_resume_campaign_refuses_before_posting(self):
        rows = [_approval_row(review_hash=HASH_A)]
        with mock.patch.object(reviewapproval, "load", return_value=rows), \
             mock.patch("src.providers.bison._post") as post:
            with self.assertRaises(reviewapproval.NotApproved):
                bison.resume_campaign(CAMPAIGN_ID, review_hash=HASH_B)
        post.assert_not_called()

    def test_activate_campaign_refuses_before_posting(self):
        rows = [_approval_row(review_hash=HASH_A)]
        with mock.patch.object(reviewapproval, "load", return_value=rows), \
             mock.patch("src.providers.heyreach.request") as req:
            with self.assertRaises(reviewapproval.NotApproved):
                heyreach.activate_campaign(CAMPAIGN_ID, review_hash=HASH_B)
        req.assert_not_called()

    def test_attach_leads_refuses_before_membership_read(self):
        rows = [_approval_row(review_hash=HASH_A)]
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "load", return_value=rows), \
             mock.patch.object(bison, "membership") as member:
            with self.assertRaises(reviewapproval.NotApproved):
                bison.attach_leads(CAMPAIGN_ID, [1], review_hash=HASH_B)
        member.assert_not_called()


if __name__ == "__main__":
    unittest.main()
