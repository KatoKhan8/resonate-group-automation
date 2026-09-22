"""ISSUE-014: an ACTIVATED campaign of ours must not collide with itself.

`staging_artifact_evidence`'s `zero_send` arm cannot be proven for a campaign
reading `active` - correctly, since one that started a moment ago also reports
zero. But this system ACTIVATES the campaigns it fills, so from the moment it
does, every account they hold reads `in_sequence` from OUR OWN membership and
every later batch is refused at it. Measured on 2026-09-22: 95 of 95 accounts
across the four campaigns sending that day read STOP, with zero client-side
`in_sequence` rows among them, and batch 3's push was refused entirely.

The per-lead row answers what the aggregate cannot: it carries THIS lead's
`emails_sent` FOR THIS CAMPAIGN. Zero there is not a counter that might lag -
it is the lead's own row.

Everything the old path refused, it still refuses. These tests assert both
halves.
"""
import unittest

from src import collision
from tests.test_our_own_staging_is_not_their_history import (   # noqa: F401
    OURS, THEIRS, WS, StagingTest, campaign_row, lead, membership,
    setUpModule)


class AnActiveCampaignOfOursDoesNotCollideWithItself(StagingTest):

    ACTIVE = staticmethod(lambda **kw: campaign_row(status="active", **kw))

    def test_the_defect_itself(self):
        """A lead in our ACTIVE campaign, sent nothing, must not read STOP."""
        found = self.account(
            [lead("a@example.test", memberships=[
                membership(OURS, "in_sequence")])],
            campaigns={OURS: self.ACTIVE()})
        self.assertEqual(len(found["our_staging_excluded"]), 1)
        self.assertFalse(found["people"][0]["in_sequence"])
        policy, _why = collision.account_policy(found)
        self.assertEqual(policy, collision.ALLOW)

    def test_the_client_history_underneath_it_still_shows(self):
        """Excluding our row must not erase what the CLIENT did.

        This is the shape measured live: three finished client campaigns and
        one in_sequence row of ours. The client's 21 emails stay visible and
        the account's own total is untouched.
        """
        found = self.account(
            [lead("a@example.test", sent=21, memberships=[
                membership(THEIRS, "sequence_finished", sent=21),
                membership(OURS, "in_sequence")])],
            campaigns={OURS: self.ACTIVE()})
        self.assertEqual(found["emails_sent_total"], 21)
        self.assertEqual(
            [c["campaign_id"] for c in found["people"][0]["campaigns"]],
            [THEIRS])

    def test_a_lead_our_active_campaign_HAS_emailed_still_collides(self):
        """The guard, on the only evidence that matters: the lead's own row."""
        found = self.account(
            [lead("a@example.test", sent=1, memberships=[
                membership(OURS, "in_sequence", sent=1)])],
            campaigns={OURS: self.ACTIVE(emails_sent=1,
                                         total_leads_contacted=1)})
        self.assertEqual(found["our_staging_excluded"], [])
        self.assertTrue(found["people"][0]["in_sequence"])

    def test_a_campaign_that_has_emailed_ANYBODY_is_disqualified_for_everybody(self):
        """A row reading zero on a campaign that has sent may simply lag.

        So one send by the campaign stops the per-lead path for every lead on
        it, not merely for the lead it sent to.
        """
        found = self.account(
            [lead("a@example.test", memberships=[
                membership(OURS, "in_sequence")])],
            campaigns={OURS: self.ACTIVE(emails_sent=1,
                                         total_leads_contacted=1)})
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_campaign_that_is_not_ours_is_never_excluded(self):
        found = self.account(
            [lead("a@example.test", memberships=[
                membership(THEIRS, "in_sequence")])])
        self.assertEqual(found["our_staging_excluded"], [])
        self.assertTrue(found["people"][0]["in_sequence"])

    def test_a_bounced_row_on_our_active_campaign_is_kept(self):
        """A bounce is a fact even when every counter reads zero."""
        found = self.account(
            [lead("a@example.test", lead_status="bounced", memberships=[
                membership(OURS, "bounced")])],
            campaigns={OURS: self.ACTIVE()})
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_sequence_finished_row_on_our_active_campaign_is_kept(self):
        """A campaign that sent nothing cannot have finished a sequence.

        The row contradicts itself, and a contradiction is kept and looked at
        rather than resolved in favour of sending.
        """
        found = self.account(
            [lead("a@example.test", memberships=[
                membership(OURS, "sequence_finished")])],
            campaigns={OURS: self.ACTIVE()})
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_replied_row_is_kept_even_with_zero_counters(self):
        found = self.account(
            [lead("a@example.test", memberships=[
                membership(OURS, "replied")])],
            campaigns={OURS: self.ACTIVE()})
        self.assertEqual(found["our_staging_excluded"], [])

    def test_an_interested_row_is_kept(self):
        found = self.account(
            [lead("a@example.test", memberships=[
                membership(OURS, "in_sequence", interested=True)])],
            campaigns={OURS: self.ACTIVE()})
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_row_reporting_opens_or_replies_is_kept(self):
        for field in ("replies", "opens"):
            with self.subTest(field=field):
                found = self.account(
                    [lead("a@example.test", memberships=[
                        membership(OURS, "in_sequence", **{field: 1})])],
                    campaigns={OURS: self.ACTIVE()})
                self.assertEqual(found["our_staging_excluded"], [])


if __name__ == "__main__":
    unittest.main()
