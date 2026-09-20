"""Campaign `active` was never evidence that a campaign is sending.

On 2026-09-20 campaign 487 read `active` for hours while all ten of its leads
read `sending_paused`, and then the campaign itself flipped to `paused`.
`resume_campaign` confirms the CAMPAIGN's status and nothing else, because it
was written before anybody knew the two could disagree.

So the recovery runner's acceptance test is the MEMBERSHIP. These tests pin
the distinction that matters most: a resume that leaves the campaign `active`
with its leads still `sending_paused` is the SAME FAULT SURVIVING THE REMEDY,
and it is the outcome that would otherwise be announced as a fix.

The rest pin the authorization's conditions, each of which refuses rather
than defaults:

    1  inside 487's own window, because a resume outside it is measured to
       move a campaign to `failed`
    2  provider truth first, including the case where the fault has cleared
       on its own - which is a REFUSAL, not a disappointment
    3  expect_leads, so a cohort that changed under us stops the write
    4  the membership is the acceptance test
    5  once
    6  the approved copy

No network: a fake provider. No real prospect's name or address.
"""
import datetime
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from scripts import resume_487  # noqa: E402

UTC = datetime.timezone.utc


class FakeBison:
    """Only the reads and the one write the runner makes."""

    def __init__(self, status="paused", membership=None, leads=10,
                 senders=(2736,), timezone="Europe/Zagreb",
                 after=None, after_status="active", raises=None):
        self._status = status
        self._membership = membership if membership is not None else {
            i: "sending_paused" for i in range(leads)}
        self._leads = leads
        self._senders = list(senders)
        self._timezone = timezone
        self._after = after
        self._after_status = after_status
        self._raises = raises
        self.resumed = 0

    def campaign(self, campaign_id):
        return {"status": self._status}

    def membership(self, campaign_id):
        return dict(self._membership)

    def campaign_lead_count(self, campaign_id):
        return self._leads

    def campaign_senders(self, campaign_id):
        return list(self._senders)

    def schedule(self, campaign_id):
        return {"timezone": self._timezone}

    def resume_campaign(self, campaign_id, expect_leads=None):
        if self._raises:
            raise self._raises
        self.resumed += 1
        if self._after is not None:
            self._membership = dict(self._after)
        self._status = self._after_status
        return {"campaign_id": campaign_id, "status": self._status}


MONDAY_IN = datetime.datetime(2026, 9, 21, 7, 15, tzinfo=UTC)
SUNDAY = datetime.datetime(2026, 9, 20, 12, 50, tzinfo=UTC)
MONDAY_EARLY = datetime.datetime(2026, 9, 21, 3, 0, tzinfo=UTC)
FRIDAY_LATE = datetime.datetime(2026, 9, 25, 16, 0, tzinfo=UTC)


class WindowGateTest(unittest.TestCase):
    """Condition 1. It refuses rather than waits, and says when."""

    def test_inside_the_window_passes(self):
        self.assertTrue(resume_487.window_gate(MONDAY_IN))

    def test_a_sunday_is_refused_and_names_the_monday(self):
        """The day the incident was found. A resume here is measured to move
        a campaign to `failed` within seconds."""
        with self.assertRaises(resume_487.Refused) as caught:
            resume_487.window_gate(SUNDAY)
        self.assertIn("2026-09-21T07:00Z", str(caught.exception))
        self.assertIn("Nothing written", str(caught.exception))

    def test_before_the_window_on_a_weekday_names_the_same_morning(self):
        with self.assertRaises(resume_487.Refused) as caught:
            resume_487.window_gate(MONDAY_EARLY)
        self.assertIn("2026-09-21T07:00Z", str(caught.exception))

    def test_after_the_window_on_a_friday_names_the_next_monday(self):
        with self.assertRaises(resume_487.Refused) as caught:
            resume_487.window_gate(FRIDAY_LATE)
        self.assertIn("2026-09-28T07:00Z", str(caught.exception))

    def test_it_does_not_wait_or_sleep_it_returns(self):
        """A session reaching this at 03:00Z writes nothing and is told what
        time to come back, rather than blocking until the window opens."""
        started = datetime.datetime.now()
        with self.assertRaises(resume_487.Refused):
            resume_487.window_gate(SUNDAY)
        self.assertLess((datetime.datetime.now() - started).total_seconds(), 1)


class TruthGateTest(unittest.TestCase):
    """Conditions 2 and 3."""

    def test_a_paused_campaign_with_the_expected_shape_passes(self):
        bison = FakeBison()
        row, counted, schedule = resume_487.truth_gate(bison)
        self.assertEqual("paused", row["status"])
        self.assertEqual({"sending_paused": 10}, counted)

    def test_a_fault_that_cleared_itself_is_a_refusal_not_a_resume(self):
        """The most important refusal here: writing would send to ten people
        a campaign is already about to reach."""
        bison = FakeBison(status="active",
                          membership={i: "in_sequence" for i in range(10)})
        with self.assertRaises(resume_487.Refused) as caught:
            resume_487.truth_gate(bison)
        self.assertIn("cleared on its own", str(caught.exception))
        self.assertEqual(0, bison.resumed)

    def test_a_campaign_that_is_not_paused_is_out_of_scope(self):
        with self.assertRaises(resume_487.Refused) as caught:
            resume_487.truth_gate(FakeBison(status="draft"))
        self.assertIn("covers nothing else", str(caught.exception))

    def test_a_cohort_that_changed_under_us_stops_the_write(self):
        with self.assertRaises(resume_487.Refused) as caught:
            resume_487.truth_gate(FakeBison(leads=14))
        self.assertIn("14", str(caught.exception))

    def test_an_unexpected_sender_stops_the_write(self):
        with self.assertRaises(resume_487.Refused) as caught:
            resume_487.truth_gate(FakeBison(senders=(2736, 2737)))
        self.assertIn("2737", str(caught.exception))

    def test_a_different_timezone_means_the_window_gate_used_a_wrong_clock(self):
        """The window was computed as 07:00-15:00Z from Europe/Zagreb being
        UTC+2. If the provider says otherwise, that arithmetic is void."""
        with self.assertRaises(resume_487.Refused) as caught:
            resume_487.truth_gate(FakeBison(timezone="America/New_York"))
        self.assertIn("wrong clock", str(caught.exception))


class VerdictTest(unittest.TestCase):
    """Condition 4, and the whole point of the runner."""

    def test_ten_in_sequence_is_the_only_recovery(self):
        self.assertEqual("RECOVERED",
                         resume_487.verdict({"in_sequence": 10}))

    def test_active_with_leads_still_paused_is_the_fault_surviving(self):
        """THE OUTCOME THAT WOULD OTHERWISE BE ANNOUNCED AS A FIX. The
        campaign status says active; ten people are still not being sent to;
        and that is exactly the state 487 was in for hours on the 20th."""
        self.assertEqual("FAULT-SURVIVED",
                         resume_487.verdict({"sending_paused": 10}))

    def test_a_partial_recovery_is_not_a_recovery(self):
        self.assertEqual("FAULT-SURVIVED",
                         resume_487.verdict({"in_sequence": 7,
                                             "sending_paused": 3}))

    def test_a_status_this_runner_cannot_classify_is_not_guessed(self):
        self.assertEqual("UNCLASSIFIED",
                         resume_487.verdict({"something_new": 10}))

    def test_an_empty_membership_is_not_a_recovery(self):
        self.assertEqual("UNCLASSIFIED", resume_487.verdict({}))


if __name__ == "__main__":
    unittest.main()
