"""ISSUE-021: re-staging a lead already on the campaign is not a new touch.

`stage` re-submits EVERY lead on the campaign, not only the new ones. So once
a campaign has emailed somebody, that lead's account reads `in_sequence` or
`touched` because of OUR OWN send, the account gate says STOP, and
`_refuse_colliding_leads` refuses the WHOLE stage rather than one lead.

Measured 2026-09-22: campaign 495 sent one email at 13:02:46Z; its next
top-up was refused because two already-contacted contacts at one account were
in the set, blocking 34 leads that had nothing to do with them.

The gate exists to stop us ADDING somebody to an account already in play. A
lead already on the campaign is not being added. Whether it should have been
was decided when it was, and re-deciding it on a state our own send created is
circular.
"""
import unittest
from unittest import mock

from src import bisonfactory


def _lead(email):
    return {"email": email, "record_id": "rec-1", "contact_key": email.split("@")[0]}


class AnExistingMemberIsNotRechecked(unittest.TestCase):

    def _run(self, wanted, already_on, policy):
        """Run the gate with `account_policy` forced to one verdict."""
        checked = []

        def _check_account(domain, expect_workspace=None):
            checked.append(domain)
            return {"domain": domain}

        with mock.patch("src.collision.check_account", _check_account), \
             mock.patch("src.collision.account_policy",
                        return_value=(policy, "forced")):
            try:
                bisonfactory._refuse_colliding_leads(
                    wanted, workspace_id=10, already_on=already_on)
                raised = None
            except bisonfactory.FactoryRefused as exc:
                raised = exc
        return checked, raised

    def test_the_defect_itself(self):
        """A contacted member must not block the leads staged beside it."""
        checked, raised = self._run(
            wanted=[_lead("dan@a.example.test"), _lead("new@b.example.test")],
            already_on=["dan@a.example.test"],
            policy="stop")
        self.assertNotIn("a.example.test", checked)
        self.assertIn("b.example.test", checked)
        self.assertIsNotNone(raised)          # the NEW lead still refuses
        self.assertIn("b.example.test", str(raised))
        self.assertNotIn("dan@a.example.test", str(raised))

    def test_a_clean_stage_of_only_existing_members_passes(self):
        checked, raised = self._run(
            wanted=[_lead("dan@a.example.test")],
            already_on=["dan@a.example.test"],
            policy="stop")
        self.assertEqual(checked, [])
        self.assertIsNone(raised)

    def test_a_lead_not_on_the_campaign_is_still_refused(self):
        """The guard is not weakened for anybody being genuinely added."""
        checked, raised = self._run(
            wanted=[_lead("new@b.example.test")],
            already_on=["dan@a.example.test"],
            policy="stop")
        self.assertEqual(checked, ["b.example.test"])
        self.assertIsNotNone(raised)

    def test_an_empty_already_on_checks_everything(self):
        """An unreadable queue yields an empty set, so nothing is skipped."""
        checked, _raised = self._run(
            wanted=[_lead("dan@a.example.test")],
            already_on=(),
            policy="stop")
        self.assertEqual(checked, ["a.example.test"])

    def test_matching_is_case_and_space_insensitive(self):
        checked, _raised = self._run(
            wanted=[_lead("  DAN@A.Example.Test  ")],
            already_on=["dan@a.example.test"],
            policy="stop")
        self.assertEqual(checked, [])


class TheMembershipReadOnlyEverAddsChecks(unittest.TestCase):

    def test_an_unreadable_queue_is_an_empty_set_not_a_claim(self):
        with mock.patch("src.providers.bison.scheduled_emails",
                        side_effect=RuntimeError("provider down")):
            self.assertEqual(bisonfactory._already_on_campaign(495), set())

    def test_no_provider_id_is_an_empty_set(self):
        self.assertEqual(bisonfactory._already_on_campaign(None), set())

    def test_it_reads_the_addresses_the_queue_carries(self):
        rows = [{"lead": {"email": "Dan@A.Example.Test"}},
                {"lead": {"email": "jason@a.example.test"}},
                {"lead": {}}]
        with mock.patch("src.providers.bison.scheduled_emails",
                        return_value=rows):
            self.assertEqual(bisonfactory._already_on_campaign(495),
                             {"dan@a.example.test", "jason@a.example.test"})


if __name__ == "__main__":
    unittest.main()
