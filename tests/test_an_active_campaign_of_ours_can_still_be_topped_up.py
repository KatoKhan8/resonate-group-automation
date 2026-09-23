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
# `tearDownModule` as well as `setUpModule`: importing half of a module
# fixture pair sets BISON_KEY and BISON_BASE and never puts them back.
# Measured 2026-09-23 - this module was one of twelve leaving the environment
# changed, and the only one whose leak was an import list rather than a
# missing teardown.
from tests.test_our_own_staging_is_not_their_history import (   # noqa: F401
    OURS, THEIRS, WS, StagingTest, campaign_row, lead, membership,
    setUpModule, tearDownModule)


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

    def test_a_queued_lead_survives_the_campaign_sending_to_somebody_else(self):
        """ISSUE-018. This assertion was the OPPOSITE this morning, and the
        evidence changed it.

        It used to read "a campaign that has emailed ANYBODY is disqualified
        for everybody", on the stated worry that a row reading zero may simply
        lag behind the campaign counter. Measured live on 2026-09-22,
        seventeen minutes after campaign 495's first send, at one account:

            <prospect-c>@example.test    camp 495  in_sequence  emails_sent 1
            <prospect-d>@example.test  camp 495  in_sequence  emails_sent 0

        The per-lead counter updated AND discriminated between two leads at
        the same account, so it is the per-lead fact rather than a trailing
        aggregate. Keeping the old rule meant the first send a standing
        campaign made locked it against every remaining lead - 495's next
        top-up was refused at 26 accounts, all of them our own queued rows.
        """
        found = self.account(
            [lead("a@example.test", memberships=[
                membership(OURS, "in_sequence")])],
            campaigns={OURS: self.ACTIVE(emails_sent=1,
                                         total_leads_contacted=1)})
        self.assertEqual(len(found["our_staging_excluded"]), 1)
        self.assertFalse(found["people"][0]["in_sequence"])

    def test_a_STOPPED_row_still_needs_the_whole_campaign_to_be_silent(self):
        """The caution is kept exactly where it belongs.

        A `stopped` or `sending_paused` row means somebody stopped THIS lead
        and the reason is not recorded. That is the case
        `test_a_campaign_that_starts_sending_stops_being_an_artifact` guards,
        and it still requires campaign-level proof - unchanged by ISSUE-018,
        which narrows only the `in_sequence` case.
        """
        found = self.account(
            [lead("a@example.test", memberships=[
                membership(OURS, "stopped")])],
            campaigns={OURS: self.ACTIVE(emails_sent=1,
                                         total_leads_contacted=1)})
        self.assertEqual(found["our_staging_excluded"], [])

    def test_a_lead_the_campaign_DID_email_still_collides(self):
        """The guard that matters, on the lead's own row."""
        found = self.account(
            [lead("a@example.test", sent=1, memberships=[
                membership(OURS, "in_sequence", sent=1)])],
            campaigns={OURS: self.ACTIVE(emails_sent=1,
                                         total_leads_contacted=1)})
        self.assertEqual(found["our_staging_excluded"], [])
        self.assertTrue(found["people"][0]["in_sequence"])

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
