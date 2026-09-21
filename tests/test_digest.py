"""One message a day instead of nineteen carrying one fact each.

`notify` routes an ordinary reply to `NOWHERE` on purpose - a neutral or
negative reply belongs in the Reply Center where somebody is already looking.
That decision leaves a gap: without a summary the quiet replies are invisible
unless somebody goes looking. This is the other half of that trade, so the
tests below are mostly about not lying in the summary.

Three rules carry it. Every number is counted from the event log rather than
derived from a plan - a prepared payload is not a send. A window is stated
rather than implied. And nothing is posted: building a digest records a
notification, and whether anything reaches Slack is `SLACK_LIVE`'s business.
"""
import os
import unittest

from tests.webbase import WebTest

from src import digest, notify, store


class TheWindow(unittest.TestCase):

    def test_it_is_stated_rather_than_implied(self):
        found = digest.window(now="2026-09-06T12:00:00+00:00", hours=24)
        self.assertEqual(found["since"], "2026-09-05T12:00:00+00:00")
        self.assertEqual(found["until"], "2026-09-06T12:00:00+00:00")
        self.assertEqual(found["hours"], 24)

    def test_an_explicit_period_is_kept(self):
        found = digest.window(since="2026-09-01T00:00:00+00:00",
                              until="2026-09-03T00:00:00+00:00")
        self.assertEqual(found["hours"], 48)

    def test_a_naive_timestamp_is_refused_rather_than_assumed_utc(self):
        """Assuming a zone would move an event by hours and report it with
        confidence. Unreadable is unknown."""
        self.assertIsNone(digest._moment("2026-09-06T12:00:00"))
        self.assertIsNone(digest._moment("not a time"))
        self.assertIsNone(digest._moment(""))

    def test_an_event_outside_the_window_is_outside_it(self):
        period = digest.window(since="2026-09-01T00:00:00+00:00",
                               until="2026-09-02T00:00:00+00:00")
        self.assertTrue(digest._within("2026-09-01T12:00:00+00:00", period))
        self.assertFalse(digest._within("2026-09-03T12:00:00+00:00", period))
        self.assertFalse(digest._within("2026-08-30T12:00:00+00:00", period))
        self.assertFalse(digest._within(None, period))


class WhatItCounts(WebTest):

    def build(self, workspace="productive", **kw):
        return digest.build(workspace, **kw)

    def test_it_counts_replies_from_the_event_log(self):
        found = self.build(hours=24 * 400)["activity"]
        self.assertGreater(found["replies"], 0)
        self.assertGreater(found["people_replied"], 0)

    def test_one_reply_is_counted_once(self):
        """A reply leaves `reply_received`, `reply_classified` and often a
        positive marker. Counting all three would treble a quiet day.

        Checked against the event log directly. The first version of this
        test asserted that the parts summed to the total, which they do by
        construction whatever is counted - it would have passed happily
        while the digest reported three replies for one.
        """
        from src import events
        expected = 0
        for rec in store.load():
            if rec.get("client") != "productive":
                continue
            expected += len([e for e in rec.get("events") or []
                             if e.get("type") == events.REPLY_CLASSIFIED])
        found = self.build(hours=24 * 4000)["activity"]
        self.assertGreater(expected, 0, "the estate has classified replies")
        self.assertEqual(found["replies"], expected)
        self.assertLessEqual(found["people_replied"], found["replies"])

    def test_confirmed_sends_are_confirmed_sends(self):
        """Not prepared payloads and not approvals. The digest's number is
        the same thing the client funnel calls `Confirmed sent`.

        Sends, not people. The funnel counts `push_marked` events, so
        thirteen sends can reach twelve people - which is why the digest
        reports both rather than letting one stand for the other.
        """
        from src import report
        recs = [r for r in store.load() if r.get("client") == "productive"]
        funnel = report.funnel_for(recs)
        found = self.build(hours=24 * 4000)["activity"]
        self.assertEqual(found["confirmed_touches"], funnel["contacted"])
        self.assertLessEqual(found["people_contacted"],
                             found["confirmed_touches"])

    def test_a_narrow_window_sees_less_than_a_wide_one(self):
        wide = self.build(hours=24 * 400)["activity"]
        narrow = self.build(since="2000-01-01T00:00:00+00:00",
                            until="2000-01-02T00:00:00+00:00")["activity"]
        self.assertEqual(narrow["replies"], 0)
        self.assertEqual(narrow["confirmed_touches"], 0)
        self.assertGreater(wide["replies"], narrow["replies"])

    def test_another_workspace_is_another_digest(self):
        mine = self.build("productive", hours=24 * 400)["activity"]
        theirs = self.build("demo-client", hours=24 * 400)["activity"]
        self.assertNotEqual(mine, theirs)

    def test_outstanding_comes_from_tasks_and_agrees_with_it(self):
        """The digest and the work queue must not disagree about how much
        is waiting, which is why neither counts for itself."""
        from src import tasks
        found = self.build()
        self.assertEqual(found["outstanding_total"],
                         sum(r["count"] for r in tasks.collect("productive")))

    def test_nothing_is_written_by_building_one(self):
        import copy
        before = copy.deepcopy(store.load())
        self.build()
        self.assertEqual(store.load(), before)


class TheSentences(WebTest):

    def test_no_sends_reads_as_none_recorded_not_as_zero(self):
        """Nothing in this build sends. "0 sent" would read as a bad day
        rather than as a system that cannot do it yet."""
        found = digest.build("productive",
                             since="2000-01-01T00:00:00+00:00",
                             until="2000-01-02T00:00:00+00:00")
        text = "\n".join(digest.lines(found))
        self.assertIn("Confirmed sends: none recorded", text)
        self.assertIn("Replies: none", text)

    def test_the_first_line_names_the_workspace_and_the_window(self):
        text = digest.lines(digest.build("productive"))
        self.assertIn("productive", text[0])
        self.assertIn("24", text[0])

    def test_the_outstanding_work_is_listed_by_kind(self):
        text = "\n".join(digest.lines(digest.build("productive")))
        self.assertIn("Waiting for somebody", text)
        self.assertIn("Campaign waiting for approval", text)


class Announcing(WebTest):

    def setUp(self):
        super().setUp()
        # The digest moved to the team status channel by operator decision on
        # 2026-09-21, so these tests have to configure one. Before that it
        # rode the ops channel this class's fixture already sets.
        self._status_channel = os.environ.get(notify.STATUS_CHANNEL_VAR)
        os.environ[notify.STATUS_CHANNEL_VAR] = "C0STATUSTEST"
        self.addCleanup(self._restore_status_channel)
        notify.save([n for n in notify.load()
                     if n.get("type") != notify.OPERATIONS_DIGEST])

    def _restore_status_channel(self):
        if self._status_channel is None:
            os.environ.pop(notify.STATUS_CHANNEL_VAR, None)
        else:
            os.environ[notify.STATUS_CHANNEL_VAR] = self._status_channel

    def rows(self):
        return [n for n in notify.load()
                if n.get("type") == notify.OPERATIONS_DIGEST]

    def test_it_goes_to_the_team_status_channel_at_info(self):
        """By construction never urgent: anything urgent has its own kind
        and was sent when it happened.

        MOVED 2026-09-21 by operator decision, from the ops channel to the
        team status feed: "Route to #resonate-os ... the 07:00 daily digest."
        Ops keeps everything that needs doing; the digest is something to
        read. A route change is a visible edit to this table and an operator
        decision, never a quiet one - which is why this test changed rather
        than went away.
        """
        destination, severity = notify.ROUTES[notify.OPERATIONS_DIGEST]
        self.assertEqual(destination, notify.STATUS)
        self.assertEqual(severity, notify.INFO)

    def test_recording_one_does_not_post_it(self):
        digest.announce(digest.build("productive"))
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], notify.PLANNED)

    def test_the_body_carries_the_summary(self):
        digest.announce(digest.build("productive"))
        self.assertIn("Waiting for somebody",
                      self.rows()[0]["payload"]["summary"])

    def test_the_same_window_twice_is_one_notification(self):
        """A cron that fires twice, or an operator running it by hand after
        it already ran, must not double-post the day."""
        built = digest.build("productive")
        digest.announce(built)
        digest.announce(built)
        self.assertEqual(len(self.rows()), 1)

    def test_a_different_window_is_a_different_notification(self):
        """The other half, and the half that matters more: yesterday's
        digest must not swallow today's. Without the window in the id both
        of these collapse into one, and the second day is never announced.
        """
        digest.announce(digest.build(
            "productive", since="2026-09-01T00:00:00+00:00",
            until="2026-09-02T00:00:00+00:00"))
        digest.announce(digest.build(
            "productive", since="2026-09-02T00:00:00+00:00",
            until="2026-09-03T00:00:00+00:00"))
        self.assertEqual(len(self.rows()), 2)

    def test_two_workspaces_are_two_notifications(self):
        built = digest.build("productive")
        digest.announce(built)
        digest.announce(digest.build("demo-client",
                                     until=built["window"]["until"]))
        self.assertEqual(len(self.rows()), 2)


if __name__ == "__main__":
    unittest.main()
