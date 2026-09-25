"""Activation refuses without the operator's approval of a review file.

OPERATOR DIRECTIVE, 2026-09-25, standing: no campaign is activated without a
review file they have approved, by name and by file hash. "Production does not
approve its own work."

This exists because on 2026-09-25 sixty-four emails reached real prospects
from the client's mailboxes carrying a different agency's pitch, signed with
the operator's name rather than the mailbox owner's. Five samples were posted
and read; the reviewer found a genuine defect in them and missed that the
product, the voice and the signature were all wrong - because the reviewer was
the same session that had produced the copy.

THE GATE IS ON THE ACTIVATION CALL, NOT IN THE FACTORY. `bisonfactory.stage`
already carried a copy lint, a tenancy check and an approved-copy check, and
none of them ran: the push used `create_lead` + `attach_leads` directly and
never entered the factory. A gate in the factory is one a script can walk
around, and the script that did was written the same day the lint was merged.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import reviewapproval                                 # noqa: E402


class TestTheApprovalIsRequired(unittest.TestCase):

    def test_no_approval_at_all_refuses(self):
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("503", rows=[])

    def test_an_approval_by_anyone_else_does_not_count(self):
        """Production approving its own work is the incident, in one line."""
        rows = [{"campaign": "503", "review_hash": "abc123",
                 "by": "production-session"}]
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("503", rows=rows)

    def test_an_approval_for_a_DIFFERENT_campaign_does_not_count(self):
        rows = [{"campaign": "504", "review_hash": "abc123",
                 "by": reviewapproval.OPERATOR}]
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("503", rows=rows)

    def test_the_operators_approval_passes(self):
        rows = [{"campaign": "503", "review_hash": "abc123",
                 "by": reviewapproval.OPERATOR}]
        self.assertIsNotNone(reviewapproval.require("503", rows=rows))

    def test_a_DIFFERENT_file_hash_refuses(self):
        """Re-rendering the copy must need a new approval.

        An approval that survived a re-render would approve words nobody read,
        which is the same defect one step later.
        """
        rows = [{"campaign": "503", "review_hash": "abc123",
                 "by": reviewapproval.OPERATOR}]
        with self.assertRaises(reviewapproval.NotApproved):
            reviewapproval.require("503", review_hash="different", rows=rows)

    def test_the_matching_file_hash_passes(self):
        rows = [{"campaign": "503", "review_hash": "abc123",
                 "by": reviewapproval.OPERATOR}]
        self.assertIsNotNone(
            reviewapproval.require("503", review_hash="abc123", rows=rows))

    def test_the_newest_approval_wins(self):
        rows = [{"campaign": "503", "review_hash": "old",
                 "by": reviewapproval.OPERATOR},
                {"campaign": "503", "review_hash": "new",
                 "by": reviewapproval.OPERATOR}]
        self.assertEqual(
            reviewapproval.require("503", review_hash="new", rows=rows)
            .get("review_hash"), "new")

    def test_the_case_of_the_name_does_not_matter(self):
        rows = [{"campaign": "503", "review_hash": "abc123",
                 "by": reviewapproval.OPERATOR.upper()}]
        self.assertIsNotNone(reviewapproval.require("503", rows=rows))

    def test_an_approval_with_no_author_cannot_be_recorded(self):
        with self.assertRaises(ValueError):
            reviewapproval.record("503", "abc123", by="")

    def test_the_file_hash_is_stable_and_discriminates(self):
        a = reviewapproval.file_hash(b"review file one")
        b = reviewapproval.file_hash(b"review file two")
        self.assertEqual(a, reviewapproval.file_hash(b"review file one"))
        self.assertNotEqual(a, b)
        self.assertEqual(len(a), 16)


class TestTheActivationCallsAsk(unittest.TestCase):
    """THE EFFECT: the provider functions themselves refuse.

    Asserted on the real functions rather than on a wrapper, because the
    wrapper is what got bypassed.
    """

    def test_bison_resume_campaign_asks(self):
        import inspect
        from src.providers import bison
        src = inspect.getsource(bison.resume_campaign)
        self.assertIn("reviewapproval.require", src)

    def test_heyreach_activate_campaign_asks(self):
        import inspect
        from src.providers import heyreach
        src = inspect.getsource(heyreach.activate_campaign)
        self.assertIn("reviewapproval.require", src)

    def test_bison_resume_REFUSES_an_unapproved_campaign(self):
        """No network: the refusal must happen before any request is built."""
        from src.providers import bison
        with self.assertRaises(reviewapproval.NotApproved):
            bison.resume_campaign(999999, expect_leads=1)


if __name__ == "__main__":
    unittest.main()
