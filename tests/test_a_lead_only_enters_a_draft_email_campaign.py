"""`EMAIL_ADD_LEAD`'s predicate, written before the permission exists.

The verb is NOT in `SUPPORTED`, so none of this runs in production yet. It is
tested now because the grant that turns the verb on is a smaller decision
when the thing it turns on is already scoped and its refusals are proven.

Every test below drives a REFUSAL except the last, because that is the shape
of the predicate: one accepting branch and seven that raise. A guard is only
as good as the branch that fires when it should, so each refusal is asserted
on its own cause rather than on "something raised".
"""
import unittest
from unittest import mock

from src import campaigns, providerwrites as pw
from tests.base import ProviderTest


class LeadsOnlyEnterADraft(ProviderTest):

    CANON = "productive-email-next-cohort"
    PROVIDER = "5001"

    def _row(self, bison_id=PROVIDER):
        campaigns.save([{"campaign_id": self.CANON,
                         "bison_campaign_id": bison_id}])

    def _provider_says(self, status):
        """Patch the campaign read. Nothing here reaches a network."""
        return mock.patch("src.providers.bison.campaign",
                          return_value={"id": self.PROVIDER,
                                        "status": status})

    # ---------------------------------------------------- the arguments

    def test_a_missing_provider_id_refuses(self):
        self._row()
        with self.assertRaises(pw.WriteRefused) as e:
            pw._is_a_draft_campaign_this_deployment_staged(None, self.CANON)
        self.assertIn("provider_campaign_id", str(e.exception))

    def test_a_missing_canonical_id_refuses(self):
        self._row()
        with self.assertRaises(pw.WriteRefused) as e:
            pw._is_a_draft_campaign_this_deployment_staged(self.PROVIDER, None)
        self.assertIn("CANONICAL", str(e.exception))

    # ---------------------------------------------------- ownership

    def test_a_campaign_we_have_no_row_for_refuses(self):
        """No canonical row: nothing proves the campaign is ours."""
        with self.assertRaises(pw.WriteRefused) as e:
            pw._is_a_draft_campaign_this_deployment_staged(
                self.PROVIDER, "a-row-that-does-not-exist")
        self.assertIn("could not be read", str(e.exception))

    def test_a_row_bound_to_a_different_campaign_refuses(self):
        """The row is ours and the destination is not the one it names."""
        self._row(bison_id="9999")
        with self.assertRaises(pw.WriteRefused) as e:
            pw._is_a_draft_campaign_this_deployment_staged(
                self.PROVIDER, self.CANON)
        self.assertIn("mismatched binding", str(e.exception))

    def test_a_row_with_no_binding_at_all_refuses(self):
        self._row(bison_id="")
        with self.assertRaises(pw.WriteRefused) as e:
            pw._is_a_draft_campaign_this_deployment_staged(
                self.PROVIDER, self.CANON)
        self.assertIn("mismatched binding", str(e.exception))

    # ---------------------------------------------------- provider state

    def test_an_unreadable_campaign_refuses_rather_than_defaulting(self):
        """The failure mode that would make an outage look like a safe draft."""
        self._row()
        with mock.patch("src.providers.bison.campaign",
                        side_effect=RuntimeError("provider down")):
            with self.assertRaises(pw.WriteRefused) as e:
                pw._is_a_draft_campaign_this_deployment_staged(
                    self.PROVIDER, self.CANON)
        self.assertIn("could not be established", str(e.exception))

    def test_an_absent_status_is_not_a_draft(self):
        self._row()
        with mock.patch("src.providers.bison.campaign",
                        return_value={"id": self.PROVIDER}):
            with self.assertRaises(pw.WriteRefused) as e:
                pw._is_a_draft_campaign_this_deployment_staged(
                    self.PROVIDER, self.CANON)
        self.assertIn("no status at all", str(e.exception))

    def test_paused_refuses_and_this_is_the_whole_point(self):
        """PAUSED is the branch LINKEDIN_ADD_LEAD got wrong once.

        A paused campaign does not send, and the lead added to it IS sent to
        the moment somebody resumes. Those are different claims and only the
        second one is what this permission is about.
        """
        self._row()
        with self._provider_says("paused"):
            with self.assertRaises(pw.WriteRefused) as e:
                pw._is_a_draft_campaign_this_deployment_staged(
                    self.PROVIDER, self.CANON)
        self.assertIn("one resume away", str(e.exception))

    def test_every_sending_state_refuses(self):
        self._row()
        for status in ("active", "queued", "starting", "completed",
                       "failed", "archived", "pending deletion"):
            with self.subTest(status=status), self._provider_says(status):
                with self.assertRaises(pw.WriteRefused):
                    pw._is_a_draft_campaign_this_deployment_staged(
                        self.PROVIDER, self.CANON)

    def test_a_draft_we_staged_is_the_one_accepting_case(self):
        self._row()
        with self._provider_says("draft"):
            self.assertTrue(
                pw._is_a_draft_campaign_this_deployment_staged(
                    self.PROVIDER, self.CANON))

    def test_the_status_is_read_at_the_moment_of_the_write(self):
        """Not taken from the canonical row, which can be stale.

        A row asserting the campaign is a draft must not be able to carry the
        decision: a human can press Start in the vendor UI between the plan
        and the write.
        """
        campaigns.save([{"campaign_id": self.CANON,
                         "bison_campaign_id": self.PROVIDER,
                         "provider_status_expected": "draft",
                         "status": "draft"}])
        with self._provider_says("active"):
            with self.assertRaises(pw.WriteRefused) as e:
                pw._is_a_draft_campaign_this_deployment_staged(
                    self.PROVIDER, self.CANON)
        self.assertIn("'active'", str(e.exception))

    # ---------------------------------------------------- not wired

    def test_the_verb_is_still_refused_because_nothing_wired_it(self):
        """The predicate existing is not the permission existing."""
        self.assertFalse(pw.is_supported(pw.EMAIL_ADD_LEAD))
        self.assertNotIn(pw.EMAIL_ADD_LEAD, pw.CONDITIONAL)
        # And the pass-through in `require_conditional_permission` must not be
        # mistaken for approval: with no condition registered it returns True,
        # which is exactly why `is_supported` is the gate and this is not.
        self.assertTrue(pw.require_conditional_permission(
            pw.EMAIL_ADD_LEAD, self.PROVIDER, self.CANON))


if __name__ == "__main__":
    unittest.main()
