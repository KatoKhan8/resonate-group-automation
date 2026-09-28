"""An approval does not survive a re-render.

TASK-328. The review hash was computed, quoted to the operator, stored by
`record()`, and then never verified by anything: every production call to
`reviewapproval.require` passed `review_hash=None`, so the mismatch branch
was unreachable and approval was campaign-level and permanent. Once a
campaign carried any approval row, a later activation carried whatever copy
was current - including copy regenerated after the operator approved.

The fix threads `review_hash` from the activation entry points to the gate.
These tests assert on BEHAVIOUR through the real provider functions, not on
the text of the source. A fake transport stands in for the provider.
"""
import unittest
from unittest import mock

from src import reviewapproval
from src.providers import bison, heyreach


def _approval_row(campaign_id, review_hash):
    return {"campaign": str(campaign_id), "review_hash": review_hash,
            "by": reviewapproval.OPERATOR}


# ------------------------------------------------------------------ helpers

def _mock_bison_past_gate(*, approval_row, patch_return=None):
    """Stack the mocks that sit between the gate and the network for
    `bison.resume_campaign`. Returns a context-manager tuple."""
    return (
        mock.patch.object(reviewapproval, "approval_for",
                          return_value=approval_row),
        mock.patch("src.generate_campaign.refuse_dry_run_records"),
        mock.patch.object(bison, "_patch",
                          return_value=(200, patch_return or {})),
        mock.patch.object(bison, "campaign",
                          return_value={"status": "active"}),
    )


def _mock_heyreach_past_gate(*, approval_row):
    """Stack the mocks that sit between the gate and the network for
    `heyreach.activate_campaign`."""
    return (
        mock.patch.object(reviewapproval, "approval_for",
                          return_value=approval_row),
        mock.patch("src.generate_campaign.refuse_dry_run_records"),
        mock.patch.object(heyreach, "_write",
                          return_value={"status": "IN_PROGRESS"}),
        mock.patch.object(heyreach, "campaign_read",
                          return_value={"status": "IN_PROGRESS"}),
    )


class MismatchedHashRefuses(unittest.TestCase):
    """THE WHOLE TASK. A hash that does not match the recorded one refuses,
    and the refusal names the campaign and both hashes."""

    def test_resume_campaign_refuses_and_names_both_hashes(self):
        row = _approval_row("493", "aaaa1111bbbb2222")
        mocks = _mock_bison_past_gate(approval_row=row)
        with mocks[0], mocks[1], mocks[2], mocks[3]:
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                bison.resume_campaign("493", review_hash="ffff0000eeee1111")
        msg = str(caught.exception)
        self.assertIn("493", msg)
        self.assertIn("aaaa1111bbbb2222", msg)
        self.assertIn("ffff0000eeee1111", msg)

    def test_activate_campaign_refuses_and_names_both_hashes(self):
        row = _approval_row("605732", "cccc3333dddd4444")
        mocks = _mock_heyreach_past_gate(approval_row=row)
        with mocks[0], mocks[1], mocks[2], mocks[3]:
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                heyreach.activate_campaign("605732",
                                           review_hash="9999aaaa8888bbbb")
        msg = str(caught.exception)
        self.assertIn("605732", msg)
        self.assertIn("cccc3333dddd4444", msg)
        self.assertIn("9999aaaa8888bbbb", msg)

    def test_attach_leads_topup_refuses_and_names_both_hashes(self):
        row = _approval_row("493", "abc123")
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "approval_for",
                               return_value=row):
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                bison.attach_leads("493", [1], review_hash="xyz789")
        msg = str(caught.exception)
        self.assertIn("493", msg)
        self.assertIn("abc123", msg)
        self.assertIn("xyz789", msg)


class MatchingHashProceeds(unittest.TestCase):
    """A matching hash passes the gate. The function continues past
    `reviewapproval.require` toward the provider call."""

    def test_resume_campaign_proceeds_on_matching_hash(self):
        row = _approval_row("493", "match_hash_1")
        mocks = _mock_bison_past_gate(approval_row=row)
        with mocks[0], mocks[1], mocks[2], mocks[3]:
            result = bison.resume_campaign("493", review_hash="match_hash_1")
        self.assertEqual(result["campaign_id"], "493")

    def test_activate_campaign_proceeds_on_matching_hash(self):
        row = _approval_row("605732", "match_hash_2")
        mocks = _mock_heyreach_past_gate(approval_row=row)
        with mocks[0], mocks[1], mocks[2], mocks[3]:
            result = heyreach.activate_campaign("605732",
                                                review_hash="match_hash_2")
        self.assertEqual(result["campaign_id"], "605732")

    def test_attach_leads_topup_proceeds_on_matching_hash(self):
        row = _approval_row("493", "match_hash_3")
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "approval_for",
                               return_value=row), \
             mock.patch.object(bison, "membership", return_value={1: "active"}), \
             mock.patch.object(bison, "campaign_lead_count", return_value=1):
            result = bison.attach_leads("493", [1], review_hash="match_hash_3")
        self.assertEqual(result["already"], [1])


class HashOmittedProceeds(unittest.TestCase):
    """When no hash is passed the gate stays permissive. This is the
    documented current behaviour: making the hash mandatory would refuse
    every campaign whose approval row predates this change, including 493
    which is ACTIVE and sending right now. The default stays permissive
    until the operator decides otherwise."""

    def test_resume_campaign_proceeds_without_hash(self):
        row = _approval_row("493", "any_hash")
        mocks = _mock_bison_past_gate(approval_row=row)
        with mocks[0], mocks[1], mocks[2], mocks[3]:
            result = bison.resume_campaign("493")
        self.assertEqual(result["campaign_id"], "493")

    def test_activate_campaign_proceeds_without_hash(self):
        row = _approval_row("605732", "any_hash")
        mocks = _mock_heyreach_past_gate(approval_row=row)
        with mocks[0], mocks[1], mocks[2], mocks[3]:
            result = heyreach.activate_campaign("605732")
        self.assertEqual(result["campaign_id"], "605732")

    def test_attach_leads_topup_proceeds_without_hash(self):
        row = _approval_row("493", "any_hash")
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "approval_for",
                               return_value=row), \
             mock.patch.object(bison, "membership", return_value={1: "active"}), \
             mock.patch.object(bison, "campaign_lead_count", return_value=1):
            result = bison.attach_leads("493", [1])
        self.assertEqual(result["already"], [1])


class EveryCallSiteForwardsTheHash(unittest.TestCase):
    """Assert on behaviour, not on the text of the source. Each function
    accepts `review_hash` and a mismatch at the gate is raised - proving the
    parameter reached `reviewapproval.require` rather than stopping at the
    function signature."""

    def test_resume_campaign_accepts_and_enforces_review_hash(self):
        import inspect
        sig = inspect.signature(bison.resume_campaign)
        self.assertIn("review_hash", sig.parameters)
        row = _approval_row("493", "real_hash")
        mocks = _mock_bison_past_gate(approval_row=row)
        with mocks[0], mocks[1], mocks[2], mocks[3]:
            with self.assertRaises(reviewapproval.NotApproved):
                bison.resume_campaign("493", review_hash="wrong_hash")

    def test_activate_campaign_accepts_and_enforces_review_hash(self):
        import inspect
        sig = inspect.signature(heyreach.activate_campaign)
        self.assertIn("review_hash", sig.parameters)
        row = _approval_row("605732", "real_hash")
        mocks = _mock_heyreach_past_gate(approval_row=row)
        with mocks[0], mocks[1], mocks[2], mocks[3]:
            with self.assertRaises(reviewapproval.NotApproved):
                heyreach.activate_campaign("605732", review_hash="wrong_hash")

    def test_attach_leads_accepts_and_enforces_review_hash(self):
        import inspect
        sig = inspect.signature(bison.attach_leads)
        self.assertIn("review_hash", sig.parameters)
        row = _approval_row("493", "real_hash")
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "approval_for",
                               return_value=row):
            with self.assertRaises(reviewapproval.NotApproved):
                bison.attach_leads("493", [1], review_hash="wrong_hash")


if __name__ == "__main__":
    unittest.main()
