#!/usr/bin/env python3
"""The membership status and the reply counter disagree. The status wins.

Measured on the live Productive estate, 2026-09-13, while clearing accounts
for a second live cohort. `grayloon.com` carries EmailBison campaign 274 with
`status: replied` and `replies: 0` on the same row.

That matters because `account_policy` read the COUNTER. The account was
holding only because `replied` was an unrecognised word, and the obvious
tidy-up - declare the word known, since it plainly is - would have moved the
account from HOLD to ALLOW and emailed a second person at a company that had
already answered. Adding a word to the known set is not the same as
understanding what it says.

The estate's full vocabulary, counted the same day: `stopped` 8,
`sequence_finished` 19, `in_sequence` 7, `bounced` 1, `replied` 1.
"""
import unittest

from src import collision


def account(*campaigns, **over):
    """One person at one account, with the campaign rows the provider gives."""
    person = {"email": "somebody@acme.test", "lead_id": 1,
              "replies": over.pop("replies", 0), "emails_sent": 14,
              "in_sequence": any(c.get("status") == collision.IN_SEQUENCE
                                 for c in campaigns),
              "campaigns": list(campaigns)}
    known = collision.KNOWN_STATUSES
    row = {"domain": "acme.test", "workspace": 10, "leads": 1,
           "people": [person], "emails_sent_total": 14,
           "anyone_in_sequence": person["in_sequence"],
           "unknown_statuses": sorted({
               str(c.get("status") or "").lower() for c in campaigns
               if c.get("status")
               and str(c.get("status")).lower() not in known}),
           "any_bounce": any(c.get("status") == "bounced" for c in campaigns),
           "verdict": "touched"}
    row.update(over)
    return row


def campaign(status, **over):
    row = {"campaign_id": 274, "status": status, "emails_sent": 5,
           "replies": 0, "interested": False}
    row.update(over)
    return row


class AReplyIsAReplyHoweverItIsRecorded(unittest.TestCase):

    def test_a_replied_status_stops_the_account_with_no_reply_counted(self):
        """The measured grayloon row, exactly."""
        verdict, why = collision.account_policy(
            account(campaign("replied", replies=0),
                    campaign("sequence_finished", campaign_id=352)))
        self.assertEqual(verdict, collision.STOP, why)
        self.assertIn("replied", why)

    def test_the_counter_still_works_on_its_own(self):
        """Guard the guard: the original path must not have been replaced."""
        verdict, why = collision.account_policy(
            account(campaign("sequence_finished"), replies=2))
        self.assertEqual(verdict, collision.STOP, why)

    def test_interested_still_works_on_its_own(self):
        verdict, why = collision.account_policy(
            account(campaign("sequence_finished", interested=True)))
        self.assertEqual(verdict, collision.STOP, why)


class AnEarlyEndingIsNamedRatherThanUnread(unittest.TestCase):
    """`stopped` reached the same HOLD before, for a worse reason."""

    def test_stopped_holds_and_says_why(self):
        verdict, why = collision.account_policy(account(campaign("stopped")))
        self.assertEqual(verdict, collision.HOLD, why)
        self.assertIn("ended early", why)
        self.assertNotIn("no verified meaning", why)

    def test_a_bounce_still_holds(self):
        verdict, why = collision.account_policy(account(campaign("bounced")))
        self.assertEqual(verdict, collision.HOLD, why)

    def test_a_finished_campaign_is_history_not_a_conflict(self):
        verdict, why = collision.account_policy(
            account(campaign("sequence_finished")))
        self.assertEqual(verdict, collision.ALLOW, why)

    def test_mid_sequence_still_outranks_everything(self):
        verdict, why = collision.account_policy(
            account(campaign(collision.IN_SEQUENCE), campaign("stopped")))
        self.assertEqual(verdict, collision.STOP, why)
        self.assertIn("mid-sequence", why)


class AWordNobodyHasVerifiedStillHolds(unittest.TestCase):
    """The vocabulary grew. The refusal to guess did not."""

    def test_an_unrecognised_status_holds(self):
        verdict, why = collision.account_policy(
            account(campaign("quarantined")))
        self.assertEqual(verdict, collision.HOLD, why)
        self.assertIn("no verified meaning", why)

    def test_the_known_set_is_exactly_what_was_measured(self):
        """Named explicitly, so the next addition is a decision.

        Each of these was read off the live estate rather than guessed, and
        `replied` in particular needed more than adding to this set - see
        `ANSWERED_STATUSES`.
        """
        self.assertEqual(
            collision.KNOWN_STATUSES,
            frozenset({"in_sequence", "sequence_finished", "sending_paused",
                       "replied", "bounced", "stopped"}))


if __name__ == "__main__":
    unittest.main()
