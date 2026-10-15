#!/usr/bin/env python3
"""A bounce nobody has applied is SURFACED, and the address stays sendable.

BORN RED. This is the SOFT half of the 2026-10-15 bounce decision and it is
deliberately a different invariant from
`tests/test_a_provider_bounce_reaches_the_record.py`, which stays red under
SOFT and is supposed to: under SOFT nothing reaches the record, so the send
path cannot refuse and `channels.email_verdict` still answers SENDABLE.

What SOFT promises instead is that a person is told, durably, with enough to
act on and nothing a log may not carry. So this file asserts exactly three
things and one guard:

  - the watcher's own durable sink carries a review line for the bounce;
  - it carries the provider ids a person needs to find the lead, and NO
    prospect address and NO contact key - `emptyrender.scan`'s rule for the
    blank scan, kept here;
  - the record is untouched and the address is still sendable, which is the
    COST of SOFT written down as a test rather than as a caveat;
  - and a queue with no bounce in it surfaces nothing, which is the guard
    against a recorder that reports every row it walks.
"""
import unittest
from unittest import mock

from src import channels, events, store, watchsink
from tests.test_a_provider_bounce_reaches_the_record import (
    ADDRESS, BounceTest, CAMPAIGN, CONTACT_KEY, RECORD_ID)

REVIEW = "BOUNCE-NEEDS-REVIEW"


class ABounceNobodyAppliedIsSurfaced(BounceTest):

    def lines(self):
        return [row.get("line") or "" for row in
                watchsink.events(source="bison", campaign=CAMPAIGN)]

    def review_lines(self):
        return [line for line in self.lines() if REVIEW in line]

    def test_the_watcher_surfaces_the_bounce(self):
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
        self.assertTrue(
            self.review_lines(),
            "the provider reports a bounce on the queue the watcher already "
            f"reads and no review line reached the sink. Lines: {self.lines()}")

    def test_the_review_line_carries_the_ids_and_no_identity(self):
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
        found = self.review_lines()
        self.assertTrue(found, "no review line at all")
        line = found[0]
        self.assertIn("900001", line)
        self.assertNotIn(ADDRESS, line)
        self.assertNotIn(CONTACT_KEY, line)

    def test_nothing_reaches_the_record_and_the_address_stays_sendable(self):
        """THE COST OF SOFT, as a test rather than a caveat.

        If this ever goes red, somebody has made SOFT suppress - which is
        HARD, and a different decision.
        """
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
        rec = store.get(RECORD_ID)
        self.assertEqual(
            [e for e in (rec.get("events") or [])
             if e.get("type") == events.EMAIL_BOUNCED], [])
        self.assertEqual(channels.email_verdict(rec, rec["contacts"][0]),
                         (True, None))


    def test_the_notification_is_planned(self):
        """THE HALF THAT FAILED SILENTLY THE FIRST TIME.

        Measured 2026-10-15: the recorder's first `notify.notify` call used
        keyword names the function does not take, raised TypeError on every
        bounce, was swallowed by the recorder's own `except`, and this file
        still passed on the emit line alone. A surfacing branch whose Slack
        half is dead is SOFT with one surface, and the durable one is a log
        nobody reads.
        """
        from src import notify
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
        rows = [r for r in notify.load()
                if r.get("type") == notify.EMAIL_BOUNCE_NEEDS_REVIEW]
        self.assertTrue(rows, "no notification was planned for the bounce")
        self.assertNotEqual(rows[0].get("status"), notify.FAILED,
                            f"the notification failed to build: "
                            f"{rows[0].get('last_error')}")
        self.assertEqual(rows[0].get("destination"), notify.GLOBAL)
        self.assertEqual(rows[0].get("severity"), notify.ACTION_REQUIRED)
        self.assertNotIn("BOUNCE-REVIEW-UNNOTIFIED", " ".join(self.lines()))

    def test_one_bounce_is_one_notification(self):
        """The watcher re-reads the same bounced row every 180s. Without the
        ids this is a Slack line every three minutes, for ever."""
        from src import notify
        with self.provider_reports_a_bounce():
            self.run_the_scheduled_producers()
            self.run_the_scheduled_producers()
        rows = [r for r in notify.load()
                if r.get("type") == notify.EMAIL_BOUNCE_NEEDS_REVIEW]
        self.assertEqual(len(rows), 1)

    def test_a_queue_with_no_bounce_surfaces_nothing(self):
        """GUARD THE GUARD. A recorder that surfaced every row it walked
        would pass the two tests above and fail this one."""
        with self.provider_reports_nothing():
            self.run_the_scheduled_producers()
        self.assertEqual(self.review_lines(), [])


if __name__ == "__main__":
    unittest.main()
