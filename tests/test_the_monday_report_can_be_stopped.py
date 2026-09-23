"""The Monday weekly report: the schedule, the stop, and the PDF.

OPERATOR, 2026-09-23, the second increment: "Monday 08:00 local schedule,
07:30 preview in #resonate-os with a stop, PDF via clientreport from the
report's data dict under the new vocabulary."

Three things are worth testing here and only one of them is the schedule.

**The stop window is the feature.** A preview nobody can act on is a
notification. So the tests that matter are the ones about what happens when
the window was never open: a loop that first ticks at 08:05 has missed the
half hour in which a person could have stopped an unreviewed client
document, and posting anyway is the exact failure the preview exists to
prevent. `MISSED_PREVIEW` is asserted as a first-class outcome rather than
left as "it happens not to post".

**A stop carries a name.** The first question on a Monday a client does not
get their document is who stopped it, and a stop with nobody's name on it is
indistinguishable from a bug that suppressed a report.

**The PDF is fed the report's own dict.** Not a translation of it. That is
the operator's one-vocabulary decision, and the test that proves it is the
one that would fail on an adapter: the eight state names have to reach the
rendered bytes.
"""
import datetime
import os
import tempfile
import unittest

from src import weeklyreportpdf, weeklyreportwatch as watch
from tests.test_client_reports import text_of


# `text_of` is tests/test_client_reports.py's, not a second copy. This file
# briefly carried its own, which is the "parallel representation of one
# truth" CLAUDE.md warns about - and the canonical one is better: it reads
# only the `(...) Tj` text-draw operators and unescapes PDF string literals,
# so a document containing "Acme (Holdings)" is actually findable.
#
# WHY IT MATTERS HERE: clientreport writes page content as FlateDecode
# streams, so `assertNotIn(b"...", raw)` against raw bytes CANNOT FAIL.


def report(**over):
    """A weekly_report-shaped dict, in the operator's vocabulary."""
    accounts = {"untouched": 1200, "sequenced": 210, "engaged": 4,
                "replied": 18, "meeting": 2, "won": 0, "lost": 0,
                "do_not_contact": 6, "unanswerable": 0, "in_flight": 234,
                "multi_dm": 11, "referrals": 0}
    accounts.update(over.pop("accounts", {}))
    out = {"read_at": "2026-09-28T06:00:00Z", "workspace": "productive",
           "accounts": accounts,
           "accounts_without_a_source": ["won", "lost"],
           "replies": {"human": 18, "automated": 5}}
    out.update(over)
    return out


class Watching(unittest.TestCase):

    def setUp(self):
        self._old = os.environ.get(watch.JOURNAL_VAR)
        self.dir = tempfile.mkdtemp()
        os.environ[watch.JOURNAL_VAR] = os.path.join(self.dir, "w.jsonl")
        self.zone = watch.zone()
        # 2026-09-28 is a Monday. 2026-09-29 is a Tuesday.
        self.monday = datetime.date(2026, 9, 28)

    def tearDown(self):
        if self._old is None:
            os.environ.pop(watch.JOURNAL_VAR, None)
        else:
            os.environ[watch.JOURNAL_VAR] = self._old

    def at(self, hour, minute, day=28):
        return datetime.datetime(2026, 9, day, hour, minute, tzinfo=self.zone)

    def outcome(self, hour, minute, day=28, slug="productive"):
        return watch.decide(slug, now=self.at(hour, minute, day))["outcome"]


class TheSchedule(Watching):

    def test_it_is_monday_only(self):
        # Tuesday 07:30 is not a preview.
        self.assertEqual(self.outcome(7, 30, day=29), watch.WAITING)

    def test_nothing_happens_before_half_seven(self):
        self.assertEqual(self.outcome(7, 29), watch.WAITING)

    def test_the_preview_is_due_at_half_seven(self):
        self.assertEqual(self.outcome(7, 30), watch.PREVIEWED)

    def test_the_local_zone_is_zagreb_and_it_resolved(self):
        """If `zoneinfo` has no database this silently becomes UTC and every
        post moves by an hour or two, so the resolution is asserted rather
        than assumed."""
        self.assertEqual(watch.TIMEZONE, "Europe/Zagreb")
        self.assertTrue(watch.zone_is_real())

    def test_the_schedule_is_local_and_not_utc(self):
        """THE TEST THE OTHERS COULD NOT FAIL. Every case above builds its
        `now` with `tzinfo=watch.zone()`, so if the zone silently became UTC
        both sides of the comparison would move together and nothing would
        complain - while every real post moved by two hours.

        So this one fixes a UTC instant. 2026-09-28 05:30Z is 07:30 in
        Zagreb under CEST; under a UTC fallback it would be 05:30 and far
        too early to preview.
        """
        utc = datetime.timezone.utc
        at_0530z = datetime.datetime(2026, 9, 28, 5, 30, tzinfo=utc)
        self.assertEqual(watch.decide("productive", now=at_0530z)["outcome"],
                         watch.PREVIEWED)
        # And 07:30Z is 09:30 local - past the post hour, window missed.
        at_0730z = datetime.datetime(2026, 9, 28, 7, 30, tzinfo=utc)
        self.assertEqual(watch.decide("productive", now=at_0730z)["outcome"],
                         watch.MISSED_PREVIEW)

    def test_the_post_hour_is_eight_local(self):
        self.assertEqual(watch.post_at(self.at(7, 30)).hour, 8)
        self.assertEqual(watch.preview_at(self.at(7, 30)).hour, 7)
        self.assertEqual(watch.preview_at(self.at(7, 30)).minute, 30)


class TheStopWindow(Watching):

    def test_the_window_is_open_between_the_preview_and_the_post(self):
        watch.record_preview("productive", self.monday, at=self.at(7, 30))
        self.assertEqual(self.outcome(7, 45), watch.WAITING)

    def test_it_delivers_at_eight_when_nobody_stopped_it(self):
        watch.record_preview("productive", self.monday, at=self.at(7, 30))
        self.assertEqual(self.outcome(8, 0), watch.DELIVERED)

    def test_a_stop_holds_the_client_post(self):
        watch.record_preview("productive", self.monday, at=self.at(7, 30))
        watch.stop("productive", self.monday, by="zvonimir", reason="wrong")
        self.assertEqual(self.outcome(8, 0), watch.STOPPED)

    def test_a_stop_outranks_the_preview_however_it_is_ordered(self):
        """A stop that landed in the same second as a preview is still a
        stop. Precedence, not file position."""
        watch.stop("productive", self.monday, by="zvonimir")
        watch.record_preview("productive", self.monday, at=self.at(7, 30))
        self.assertEqual(watch.state_of("productive", self.monday),
                         watch.STOPPED)

    def test_a_stop_that_arrives_after_delivery_does_not_rewrite_history(self):
        """The client HAS the document. `stopped` would be a lie about what
        happened, and the Monday readback is what somebody checks when they
        ask whether it went. Precedence, not file position - this is the
        half of `state_of` the ordering test above does not reach."""
        watch.record_preview("productive", self.monday, at=self.at(7, 30))
        watch.record_delivery("productive", self.monday, at=self.at(8, 0))
        watch.stop("productive", self.monday, by="zvonimir", reason="late")
        self.assertEqual(watch.state_of("productive", self.monday),
                         watch.DELIVERED)
        self.assertEqual(self.outcome(8, 5), watch.ALREADY)

    def test_a_stop_must_carry_who_stopped_it(self):
        with self.assertRaises(ValueError):
            watch.stop("productive", self.monday, by="")

    def test_delivering_twice_is_impossible(self):
        watch.record_preview("productive", self.monday, at=self.at(7, 30))
        watch.record_delivery("productive", self.monday, at=self.at(8, 0))
        self.assertEqual(self.outcome(8, 5), watch.ALREADY)


class TheWindowThatWasNeverOpen(Watching):
    """The half hour is the feature, so missing it is not a near miss."""

    def test_a_loop_that_wakes_after_eight_refuses_to_post(self):
        # No preview was ever recorded - the machine was asleep, or the loop
        # was started late. Posting now puts an UNREVIEWED client document
        # in a client channel.
        self.assertEqual(self.outcome(8, 5), watch.MISSED_PREVIEW)

    def test_and_it_still_refuses_later_that_day(self):
        self.assertEqual(self.outcome(16, 0), watch.MISSED_PREVIEW)

    def test_the_refusal_says_why(self):
        decision = watch.decide("productive", now=self.at(8, 5))
        self.assertIn("nobody had the window", decision["why"])

    def test_next_monday_is_unaffected(self):
        """A missed week does not poison the next one - the id is per
        Monday, so 2026-10-05 starts clean."""
        self.assertEqual(
            self.outcome(7, 30, day=28), watch.PREVIEWED)
        later = datetime.datetime(2026, 10, 5, 7, 30, tzinfo=self.zone)
        self.assertEqual(watch.decide("productive", now=later)["outcome"],
                         watch.PREVIEWED)


class OneWorkspaceIsNotAnother(Watching):

    def test_a_stop_on_one_client_does_not_stop_another(self):
        watch.record_preview("productive", self.monday, at=self.at(7, 30))
        watch.record_preview("contactout", self.monday, at=self.at(7, 30))
        watch.stop("productive", self.monday, by="zvonimir")
        self.assertEqual(self.outcome(8, 0, slug="productive"),
                         watch.STOPPED)
        self.assertEqual(self.outcome(8, 0, slug="contactout"),
                         watch.DELIVERED)


class ThePdf(unittest.TestCase):
    """Fed `weekly_report`'s dict, not a translation of it."""

    def raw(self, **over):
        return weeklyreportpdf.build(report(**over), "Productive")

    def test_it_builds_a_pdf(self):
        raw = self.raw()
        self.assertTrue(raw.startswith(b"%PDF"))

    def test_it_refuses_a_dict_that_is_not_a_weekly_report(self):
        for bad in ({}, {"emails": 3}, None, "accounts"):
            with self.assertRaises(ValueError):
                weeklyreportpdf.build(bad, "Productive")

    def test_the_account_section_is_not_the_not_assembled_excuse(self):
        """The whole point of the vocabulary change. If `_accounts` cannot
        read the dict it prints an honest paragraph saying the section has
        no data behind it - which, on a document whose SUBJECT is accounts,
        means the feature did not ship."""
        self.assertNotIn("is not assembled for this report",
                         text_of(self.raw()))

    def test_all_eight_state_names_reach_the_rendered_page(self):
        """The operator's vocabulary, in the document a client receives.
        This is the test an ADAPTER would fail: mapping the eight onto the
        old four would put `Targeted` and `Contacted` on the page instead."""
        body = text_of(self.raw())
        for label in ("Untouched", "Sequenced", "Engaged", "Replied",
                      "Meetings", "Won", "Lost", "Do not contact"):
            self.assertIn(label, body, "%r is not on the page" % label)
        for retired in ("Accounts targeted", "Accounts contacted",
                        "Positive accounts"):
            self.assertNotIn(retired, body)

    def test_the_unanswerable_tile_renders_even_at_zero(self):
        """A tile that only appears when the number is non-zero is a tile
        nobody notices has appeared."""
        self.assertIn("Cannot be placed", text_of(self.raw()))

    def test_won_and_lost_say_why_they_are_zero(self):
        """`0 won` read as a measurement is the failure. The page has to
        carry the sentence that says nothing here records a deal."""
        body = text_of(self.raw())
        self.assertIn("no source", body)

    def test_a_reply_ledger_that_could_not_be_read_drops_its_section(self):
        """Rather than printing `not tracked` next to a Slack post that
        already said the ledger failed."""
        data = report()
        data.pop("replies")
        data["replies_error"] = "the reply ledger could not be read"
        self.assertNotIn("replies",
                         weeklyreportpdf.sections_available(data))

    def test_the_dropped_section_is_absent_from_the_DOCUMENT(self):
        """Asserting the section LIST is half a test: the list is an input
        to `build`, and a renderer that ignored it would pass. This reads
        the bytes a client would receive."""
        data = report()
        data.pop("replies")
        data["replies_error"] = "the reply ledger could not be read"
        body = text_of(weeklyreportpdf.build(data, "Productive"))
        self.assertNotIn("Reply Analysis", body)
        # And the section that IS fed still rendered.
        self.assertIn("Account Engagement", body)

    def test_the_appendix_is_never_dropped(self):
        """It is the page that bounds every other page."""
        data = report()
        data.pop("replies")
        self.assertIn("appendix", weeklyreportpdf.sections_available(data))

    def test_it_never_asks_for_a_section_the_template_lacks(self):
        from src import clientreport

        offered = set(clientreport.sections_for(weeklyreportpdf.TEMPLATE))
        self.assertTrue(set(weeklyreportpdf.WEEKLY_SECTIONS) <= offered)


if __name__ == "__main__":
    unittest.main()
