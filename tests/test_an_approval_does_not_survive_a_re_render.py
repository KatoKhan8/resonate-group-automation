"""An approval does not survive a re-render.

TASK-328: the review hash was computed, stored, and quoted to the operator,
but every production call site called `reviewapproval.require(campaign_id)`
without forwarding `review_hash`. The mismatch branch inside `require` was
therefore unreachable: approval was campaign-level and permanent, and a
re-render that changed every word still passed the gate carrying the old
hash.

These tests drive through the REAL entry points - `resume_campaign`,
`activate_campaign`, and `attach_leads` - with fake transports so no
provider is ever called. They assert on BEHAVIOUR (the refusal is raised,
the hash is forwarded, the error names both hashes) rather than on the text
of the source.
"""
import unittest
from unittest import mock

from src import reviewapproval
from src.providers import bison, heyreach


def _approval_row(campaign, review_hash):
    return {"campaign": str(campaign), "review_hash": review_hash,
            "by": reviewapproval.OPERATOR}


# --------------------------------------------------------------------- bison

class ResumeCampaignHashGate(unittest.TestCase):
    """`bison.resume_campaign` forwards review_hash to the gate."""

    def test_mismatched_hash_refuses_and_names_both(self):
        """The real gate refuses when the hash does not match, and the error
        names the campaign and both hashes so the operator can see why."""
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "draft"}), \
             mock.patch.object(reviewapproval, "approval_for",
                               return_value=_approval_row(
                                   "493", "aaaa1111bbbb2222")):
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                bison.resume_campaign("493", expect_leads=1,
                                      review_hash="cccc3333dddd4444")
        msg = str(caught.exception)
        self.assertIn("493", msg)
        self.assertIn("aaaa1111bbbb2222", msg)
        self.assertIn("cccc3333dddd4444", msg)

    def test_matching_hash_is_forwarded_to_the_gate(self):
        """When the hash matches, the gate returns and execution continues.
        We verify the hash reached `require` by spying on it."""
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "require",
                               return_value=_approval_row(
                                   "503", "abcdef0123456789")) as req, \
             mock.patch.object(bison, "campaign_lead_count", return_value=5), \
             mock.patch.object(bison, "_patch",
                               return_value=(200, {"status": "active"})):
            try:
                bison.resume_campaign("503", expect_leads=5,
                                      review_hash="abcdef0123456789")
            except reviewapproval.NotApproved:
                self.fail("resume_campaign refused a matching review_hash")
        req.assert_called_once_with("503", review_hash="abcdef0123456789")

    def test_hash_omitted_is_forwarded_as_none(self):
        """Current documented behaviour: when no hash is given the gate
        receives None and does not compare. This is NOT silently changed."""
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "require",
                               return_value=_approval_row(
                                   "503", "abcdef0123456789")) as req, \
             mock.patch.object(bison, "campaign_lead_count", return_value=5), \
             mock.patch.object(bison, "_patch",
                               return_value=(200, {"status": "active"})):
            try:
                bison.resume_campaign("503", expect_leads=5)
            except reviewapproval.NotApproved:
                self.fail("resume_campaign refused when no review_hash was "
                          "given; the default must remain permissive")
        req.assert_called_once_with("503", review_hash=None)


# ------------------------------------------------------------------ heyreach

class ActivateCampaignHashGate(unittest.TestCase):
    """`heyreach.activate_campaign` forwards review_hash to the gate."""

    def test_mismatched_hash_refuses_and_names_both(self):
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "DRAFT"}), \
             mock.patch.object(reviewapproval, "approval_for",
                               return_value=_approval_row(
                                   "605732", "old_hash_value1")):
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                heyreach.activate_campaign("605732", expect_leads=10,
                                           review_hash="new_hash_value1")
        msg = str(caught.exception)
        self.assertIn("605732", msg)
        self.assertIn("old_hash_value1", msg)
        self.assertIn("new_hash_value1", msg)

    def test_matching_hash_is_forwarded_to_the_gate(self):
        campaign_read_side_effect = [
            {"status": "DRAFT"},
            {"status": "IN_PROGRESS"},
        ]
        with mock.patch.object(heyreach, "campaign_read",
                               side_effect=campaign_read_side_effect), \
             mock.patch.object(reviewapproval, "require",
                               return_value=_approval_row(
                                   "605732", "old_hash_value1")) as req, \
             mock.patch.object(heyreach, "campaign_leads",
                               return_value=([], 10)), \
             mock.patch.object(heyreach, "_write", return_value=(200, {})):
            try:
                heyreach.activate_campaign("605732", expect_leads=10,
                                           review_hash="old_hash_value1")
            except reviewapproval.NotApproved:
                self.fail("activate_campaign refused a matching review_hash")
        req.assert_called_once_with("605732", review_hash="old_hash_value1")

    def test_hash_omitted_is_forwarded_as_none(self):
        campaign_read_side_effect = [
            {"status": "DRAFT"},
            {"status": "IN_PROGRESS"},
        ]
        with mock.patch.object(heyreach, "campaign_read",
                               side_effect=campaign_read_side_effect), \
             mock.patch.object(reviewapproval, "require",
                               return_value=_approval_row(
                                   "605732", "old_hash_value1")) as req, \
             mock.patch.object(heyreach, "campaign_leads",
                               return_value=([], 10)), \
             mock.patch.object(heyreach, "_write", return_value=(200, {})):
            try:
                heyreach.activate_campaign("605732", expect_leads=10)
            except reviewapproval.NotApproved:
                self.fail("activate_campaign refused when no review_hash was "
                          "given; the default must remain permissive")
        req.assert_called_once_with("605732", review_hash=None)


# --------------------------------------------------------- attach_leads topup

class AttachLeadsHashGate(unittest.TestCase):
    """`bison.attach_leads` forwards review_hash through the top-up gate."""

    def test_mismatched_hash_refuses_and_names_both(self):
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "approval_for",
                               return_value=_approval_row(
                                   "493", "original_hash123")):
            with self.assertRaises(reviewapproval.NotApproved) as caught:
                bison.attach_leads("493", [1],
                                   review_hash="rerendered_hash1")
        msg = str(caught.exception)
        self.assertIn("493", msg)
        self.assertIn("original_hash123", msg)
        self.assertIn("rerendered_hash1", msg)

    def test_matching_hash_is_forwarded_to_the_gate(self):
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "require",
                               return_value=_approval_row(
                                   "493", "abcdef0123456789")) as req, \
             mock.patch.object(bison, "membership",
                               return_value={1: "active"}), \
             mock.patch.object(bison, "campaign_lead_count", return_value=1):
            out = bison.attach_leads("493", [1],
                                     review_hash="abcdef0123456789")
        self.assertEqual(out["already"], [1])
        req.assert_called_once_with("493", review_hash="abcdef0123456789")

    def test_hash_omitted_is_forwarded_as_none(self):
        with mock.patch.object(bison, "campaign",
                               return_value={"status": "active"}), \
             mock.patch.object(reviewapproval, "require",
                               return_value=_approval_row(
                                   "493", "abcdef0123456789")) as req, \
             mock.patch.object(bison, "membership",
                               return_value={1: "active"}), \
             mock.patch.object(bison, "campaign_lead_count", return_value=1):
            out = bison.attach_leads("493", [1])
        self.assertEqual(out["already"], [1])
        req.assert_called_once_with("493", review_hash=None)


# ------------------------------------------ the gate itself, driven directly

class TheGateRefusesAMismatchDirectly(unittest.TestCase):
    """The refusal fires through `require` itself, naming both hashes."""

    def test_mismatch_refuses_with_campaign_and_both_hashes(self):
        rows = [_approval_row("493", "aaaa1111bbbb2222")]
        with self.assertRaises(reviewapproval.NotApproved) as caught:
            reviewapproval.require("493", review_hash="cccc3333dddd4444",
                                   rows=rows)
        msg = str(caught.exception)
        self.assertIn("493", msg)
        self.assertIn("aaaa1111bbbb2222", msg)
        self.assertIn("cccc3333dddd4444", msg)


# ------------------------------------ every call site accepts the parameter

class EveryCallSiteAcceptsReviewHash(unittest.TestCase):
    """Assert on the signature that each function accepts review_hash."""

    def test_resume_campaign_accepts_review_hash(self):
        import inspect
        params = inspect.signature(bison.resume_campaign).parameters
        self.assertIn("review_hash", params)

    def test_activate_campaign_accepts_review_hash(self):
        import inspect
        params = inspect.signature(heyreach.activate_campaign).parameters
        self.assertIn("review_hash", params)

    def test_attach_leads_accepts_review_hash(self):
        import inspect
        params = inspect.signature(bison.attach_leads).parameters
        self.assertIn("review_hash", params)


if __name__ == "__main__":
    unittest.main()
