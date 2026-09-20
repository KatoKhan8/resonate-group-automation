"""FULL survives a weak walk. ROOM has to earn a complete, fresh, covering one.

A forward-book walk can only ever UNDERCOUNT commitments, because a row not
yet reached is a row not yet counted. `senderheadroom` is built on that
asymmetry and the tests here are all about which direction it runs:

  - a count that already reaches the limit proves FULL on ANY walk, including
    an incomplete, stale, uncovering one
  - a count below the limit proves NOTHING unless the walk is complete AND
    fresh AND covered every campaign that can book the mailbox AND the limit
    is known

The failure this guards against is a selector reading a zero as free capacity
and putting a cohort on a mailbox that is booked solid - which is the real
defect recorded in
`docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md`, where campaign 487's ten
openers landed on the 23rd because 2736 was full on the 21st and 22nd.

The 487 case is reproduced here as a fixture from the measured numbers.

No network, no provider module, no PII: sender ids and dates only.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import senderheadroom  # noqa: E402


NOW = datetime.datetime(2026, 9, 19, 9, 0, tzinfo=datetime.timezone.utc)
FRESH = "2026-09-19T06:00:00+00:00"
STALE = "2026-09-17T21:14:35+00:00"


def census(campaigns):
    """A census state file shaped exactly like the real one."""
    return {"campaigns": campaigns}


def walk(by_sender_day, complete=True, finished_at=FRESH, rows=1, pages=1):
    return {"by_sender_day": dict(by_sender_day), "complete": complete,
            "finished_at": finished_at, "started_at": finished_at,
            "rows": rows, "pages": pages, "cursor": None}


# The measured 487 case: 327 fills 2736 on Monday, 328 fills it on Tuesday,
# and 487's own ten sit on Wednesday.
def the_487_estate(complete=True, finished_at=FRESH):
    return census({
        "327": walk({"2736|2026-09-21": 15}, complete, finished_at),
        "328": walk({"2736|2026-09-22": 15}, complete, finished_at),
        "352": walk({"3437|2026-09-21": 15, "3437|2026-09-22": 4}, complete,
                    finished_at),
        "487": walk({"2736|2026-09-23": 10}, complete, finished_at),
    })


ACTIVE = ("327", "328", "352", "487")


class TheAsymmetryRunsOneWay(unittest.TestCase):

    def test_full_is_proven_by_an_incomplete_walk(self):
        """An undercount that already reaches the limit is still a full mailbox."""
        state = the_487_estate(complete=False)
        word, reason, free = senderheadroom.verdict(
            state, 2736, "2026-09-21", 15, ACTIVE, now=NOW)
        self.assertEqual(word, senderheadroom.FULL, reason)
        self.assertIsNone(free, "FULL must not report a free count")
        self.assertIn("15 of 15", reason)

    def test_full_is_proven_by_a_stale_walk(self):
        """Old evidence cannot make a booked mailbox emptier than it was."""
        state = the_487_estate(finished_at=STALE)
        word, reason, _ = senderheadroom.verdict(
            state, 2736, "2026-09-22", 15, ACTIVE, now=NOW)
        self.assertEqual(word, senderheadroom.FULL, reason)

    def test_room_is_refused_by_an_incomplete_walk(self):
        """Below the limit on a partial walk is 'not seen yet', not 'free'."""
        state = the_487_estate(complete=False)
        word, reason, free = senderheadroom.verdict(
            state, 2736, "2026-09-23", 15, ACTIVE, now=NOW)
        self.assertEqual(word, senderheadroom.REFUSED, reason)
        self.assertIsNone(free)
        self.assertIn("incomplete", reason)

    def test_room_is_refused_by_a_stale_walk(self):
        """The client inserts rows daily, so yesterday's walk cannot prove free."""
        state = the_487_estate(finished_at=STALE)
        word, reason, _ = senderheadroom.verdict(
            state, 2736, "2026-09-23", 15, ACTIVE, now=NOW)
        self.assertEqual(word, senderheadroom.REFUSED, reason)
        self.assertIn("prove FULL but not ROOM", reason)

    def test_room_is_refused_when_the_walk_missed_an_active_campaign(self):
        """A campaign nobody walked is exactly where the missing rows are."""
        state = the_487_estate()
        word, reason, _ = senderheadroom.verdict(
            state, 2736, "2026-09-23", 15,
            active_campaign_ids=ACTIVE + ("489",), now=NOW)
        self.assertEqual(word, senderheadroom.REFUSED, reason)
        self.assertIn("489", reason)

    def test_room_is_refused_when_the_limit_is_unknown(self):
        """No limit means nothing may be planned, exactly as readiness() says."""
        state = the_487_estate()
        word, reason, _ = senderheadroom.verdict(
            state, 2736, "2026-09-23", None, ACTIVE, now=NOW)
        self.assertEqual(word, senderheadroom.REFUSED, reason)
        self.assertIn("no daily limit", reason)

    def test_room_is_granted_when_every_gate_is_satisfied(self):
        """And only then."""
        state = the_487_estate()
        word, reason, free = senderheadroom.verdict(
            state, 2736, "2026-09-23", 15, ACTIVE, now=NOW)
        self.assertEqual(word, senderheadroom.ROOM, reason)
        self.assertEqual(free, 5, "10 of 15 booked leaves 5")


class TheMeasured487CaseReproduces(unittest.TestCase):

    def test_monday_and_tuesday_are_full_and_wednesday_is_the_first_free_day(self):
        """The finding, as a test: the send date is the mailbox."""
        state = the_487_estate()
        self.assertEqual(senderheadroom.verdict(
            state, 2736, "2026-09-21", 15, ACTIVE, now=NOW)[0],
            senderheadroom.FULL)
        self.assertEqual(senderheadroom.verdict(
            state, 2736, "2026-09-22", 15, ACTIVE, now=NOW)[0],
            senderheadroom.FULL)

        day, reason = senderheadroom.earliest_day(
            state, 2736, 15, ACTIVE, need=1, on_or_after="2026-09-21",
            now=NOW)
        self.assertEqual(day, "2026-09-23", reason)

    def test_a_cohort_of_ten_does_not_fit_where_one_does(self):
        """`need` is part of the question: 5 free slots is not room for 10."""
        state = the_487_estate()
        word, reason, _ = senderheadroom.verdict(
            state, 2736, "2026-09-23", 15, ACTIVE, need=10, now=NOW)
        self.assertEqual(word, senderheadroom.FULL, reason)

    def test_a_weekend_is_not_a_sending_day(self):
        """Saturday is skipped even though the mailbox is empty on it."""
        state = the_487_estate()
        day, reason = senderheadroom.earliest_day(
            state, 9999, 15, ACTIVE, on_or_after="2026-09-19", now=NOW)
        self.assertEqual(day, "2026-09-21",
                         f"19th is a Saturday and 20th a Sunday: {reason}")

    def test_the_caller_may_declare_weekends_sendable(self):
        """Sending days belong to the campaign schedule, not to this module."""
        state = the_487_estate()
        day, _ = senderheadroom.earliest_day(
            state, 9999, 15, ACTIVE, on_or_after="2026-09-19",
            sending_days=range(1, 8), now=NOW)
        self.assertEqual(day, "2026-09-19")

    def test_sending_days_are_iso_and_a_zero_based_set_is_refused(self):
        """`geo.windows()["days"]` is `[1..5]` under a comment reading
        "Monday is 1, matching ISO weekday", and schedule.py and ooo.py both
        compare with isoweekday(). This module compared with weekday()
        against a 0-based tuple, so the obvious wiring read Mon-Fri as
        Tue-SATURDAY - refusing Monday and offering a weekend, on an estate
        where both live campaigns are Mon-Fri.

        0 is not an ISO weekday, so a 0-based set is unambiguous evidence of
        the other convention and is refused rather than guessed at."""
        state = the_487_estate()
        with self.assertRaises(senderheadroom.HeadroomRefused) as caught:
            senderheadroom.earliest_day(
                state, 9999, 15, ACTIVE, on_or_after="2026-09-19",
                sending_days=(0, 1, 2, 3, 4), now=NOW)
        self.assertIn("ISO", str(caught.exception))

    def test_the_iso_days_geo_actually_returns_select_monday_to_friday(self):
        """The wiring that was broken, pinned end to end: what
        `geo.windows` returns must select weekdays here, not shift by one.
        2026-09-19 is a Saturday and the 21st is the Monday."""
        from src import geo
        iso_days = geo.windows({})["days"]
        self.assertEqual([1, 2, 3, 4, 5], list(iso_days))
        day, reason = senderheadroom.earliest_day(
            the_487_estate(), 9999, 15, ACTIVE, on_or_after="2026-09-19",
            sending_days=iso_days, now=NOW)
        self.assertEqual("2026-09-21", day,
                         f"ISO Mon-Fri must skip the weekend: {reason}")

    def test_the_default_is_iso_monday_to_friday(self):
        self.assertEqual((1, 2, 3, 4, 5), senderheadroom.WEEKDAYS)


class ARefusedDayIsNeverFallenThroughTo(unittest.TestCase):

    def test_earliest_day_returns_none_rather_than_a_refused_day(self):
        """The whole point: REFUSED is not ROOM, even when nothing else is left."""
        state = the_487_estate(complete=False)
        day, reason = senderheadroom.earliest_day(
            state, 2736, 15, ACTIVE, on_or_after="2026-09-21", now=NOW)
        self.assertIsNone(day, f"a partial walk proved a day free: {reason}")
        self.assertIn("incomplete", reason)

    def test_a_mailbox_booked_solid_reports_no_day_and_says_so(self):
        state = census({"352": walk(
            {f"3437|2026-09-{d:02d}": 15 for d in range(21, 30)})})
        day, reason = senderheadroom.earliest_day(
            state, 3437, 15, ("352",), on_or_after="2026-09-21",
            horizon_days=8, now=NOW)
        self.assertIsNone(day)
        self.assertIn("booked to this mailbox's limit", reason)

    def test_a_missing_census_file_is_refused_and_not_read_as_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "nope.json")
            with self.assertRaises(senderheadroom.HeadroomRefused) as caught:
                senderheadroom.load_state(missing)
        self.assertIn("not the same as zero", str(caught.exception))

    def test_a_file_that_is_not_a_census_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "other.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"something": "else"}, handle)
            with self.assertRaises(senderheadroom.HeadroomRefused):
                senderheadroom.load_state(path)


class FreshnessUsesTheStalestWalk(unittest.TestCase):

    def test_the_oldest_finished_at_decides(self):
        """A census is only as current as its stalest campaign."""
        state = census({"327": walk({"2736|2026-09-23": 1}, finished_at=FRESH),
                        "352": walk({"3437|2026-09-23": 1},
                                    finished_at=STALE)})
        fresh, age, stamp = senderheadroom.freshness(state, now=NOW)
        self.assertFalse(fresh)
        self.assertEqual(stamp, STALE)
        self.assertGreater(age, 24)

    def test_an_unparseable_stamp_is_not_fresh(self):
        """Confusion must not read as currency."""
        state = census({"327": walk({"2736|2026-09-23": 1},
                                    finished_at="whenever")})
        fresh, age, _ = senderheadroom.freshness(state, now=NOW)
        self.assertFalse(fresh)
        self.assertIsNone(age)


class RankingIsLatencyOnly(unittest.TestCase):

    def test_soonest_first_and_the_unprovable_last(self):
        state = the_487_estate()
        ranked = senderheadroom.rank(
            state, [(2736, 15), (3437, 15), (9999, None)],
            ACTIVE, on_or_after="2026-09-21", now=NOW)
        self.assertEqual([r["sender_id"] for r in ranked][:2], [3437, 2736],
                         "3437 is free on the 22nd, 2736 not until the 23rd")
        self.assertIsNone(ranked[-1]["day"],
                          "the mailbox with no known limit sorts last")
        self.assertEqual(ranked[-1]["sender_id"], 9999)

    def test_a_refused_mailbox_is_kept_rather_than_dropped(self):
        """A caller explaining a slow choice needs to see what refused."""
        state = the_487_estate()
        ranked = senderheadroom.rank(
            state, [(2736, 15), (9999, None)], ACTIVE,
            on_or_after="2026-09-21", now=NOW)
        self.assertEqual(len(ranked), 2)
        self.assertTrue(any(r["day"] is None for r in ranked))


class DeliberateBreak(unittest.TestCase):
    """Break the guard; confirm the intended test fails for the intended reason.

    A red test is not proof by itself. Each case here removes exactly one
    protection and asserts that the module would then say something it must
    never say - so a future edit that quietly drops the guard is caught by the
    test above it rather than by a campaign sending late.
    """

    def test_without_the_completeness_gate_a_partial_walk_would_read_as_free(self):
        state = the_487_estate(complete=False)
        complete, incomplete = senderheadroom.completeness(state)
        self.assertFalse(complete)
        self.assertEqual(len(incomplete), 4)

        # The value the gate is standing in front of: below the limit.
        used = senderheadroom.committed(state, 2736, "2026-09-23")
        self.assertLess(used, 15,
                        "if completeness stopped being checked, 10 < 15 is "
                        "exactly what would be mistaken for room")
        # And with the gate in place it is refused instead.
        self.assertEqual(senderheadroom.verdict(
            state, 2736, "2026-09-23", 15, ACTIVE, now=NOW)[0],
            senderheadroom.REFUSED)

    def test_without_the_coverage_gate_an_unwalked_campaigns_rows_vanish(self):
        """489's five rows are real and a walk that skipped it would miss them."""
        state = the_487_estate()
        covers, missing = senderheadroom.coverage(state, ACTIVE + ("489",))
        self.assertFalse(covers)
        self.assertEqual(missing, ("489",))
        # Without 489 in the active set the same state answers ROOM.
        self.assertEqual(senderheadroom.verdict(
            state, 2736, "2026-09-23", 15, ACTIVE, now=NOW)[0],
            senderheadroom.ROOM)
        # With it, it must not.
        self.assertEqual(senderheadroom.verdict(
            state, 2736, "2026-09-23", 15, ACTIVE + ("489",), now=NOW)[0],
            senderheadroom.REFUSED)

    def test_full_does_not_depend_on_any_of_the_gates(self):
        """All four weakened at once, and FULL still holds."""
        state = the_487_estate(complete=False, finished_at=STALE)
        word, reason, _ = senderheadroom.verdict(
            state, 2736, "2026-09-21", 15,
            active_campaign_ids=ACTIVE + ("489", "999"), now=NOW)
        self.assertEqual(word, senderheadroom.FULL, reason)


class TheSchedulerPlacesTheWholeCohort(unittest.TestCase):
    """The rule the provider was MEASURED to follow, from a complete walk.

    `docs/THE-SCHEDULER-PLACES-THE-WHOLE-COHORT-2026-09-19.md`. The first
    reading of the 487 case was "the first day with a free slot", and it is
    refuted: sender 3437 had two free slots on the 22nd and one on the 23rd
    and campaign 489's five leads went to the 24th anyway.

    The rule that fits both campaigns exactly is **the first sending day with
    room for the WHOLE cohort**, and cohort SIZE is what discriminates the
    two. These are the real books, with each campaign's own rows removed -
    the counterfactual of where the scheduler would place it.
    """

    def book(self, by_day):
        return census({"client": walk(by_day)})

    def test_the_ten_of_487_fit_on_the_23rd_and_not_before(self):
        state = self.book({"2736|2026-09-21": 15, "2736|2026-09-22": 15,
                           "2736|2026-09-23": 5})
        day, reason = senderheadroom.earliest_day(
            state, 2736, 15, ("client",), need=10,
            on_or_after="2026-09-21", now=NOW)
        self.assertEqual(day, "2026-09-23", reason)

    def test_the_five_of_489_skip_two_days_that_have_room_for_fewer(self):
        """The case the single-slot rule gets wrong."""
        state = self.book({"3437|2026-09-21": 16, "3437|2026-09-22": 13,
                           "3437|2026-09-23": 14, "3437|2026-09-24": 8})
        day, reason = senderheadroom.earliest_day(
            state, 3437, 15, ("client",), need=5,
            on_or_after="2026-09-21", now=NOW)
        self.assertEqual(day, "2026-09-24", reason)

    def test_one_lead_would_have_gone_three_days_earlier(self):
        """Cohort size is a scheduling input, not only a safety cap."""
        state = self.book({"3437|2026-09-21": 16, "3437|2026-09-22": 13,
                           "3437|2026-09-23": 14, "3437|2026-09-24": 8})
        day, _ = senderheadroom.earliest_day(
            state, 3437, 15, ("client",), need=1,
            on_or_after="2026-09-21", now=NOW)
        self.assertEqual(day, "2026-09-22",
                         "a single lead fits where a cohort of five does not")

    def test_an_overbooked_mailbox_is_full_rather_than_negative(self):
        """MEASURED: client campaign 352 books 16 on a mailbox whose limit is 15.

        `daily_limit` is therefore not a hard provider cap. FULL must still
        refuse - it means 'at or past the number we treat as the limit', not
        'the provider will refuse more' - and it must not underflow into
        reporting free capacity.
        """
        state = self.book({"3437|2026-09-21": 16})
        word, reason, free = senderheadroom.verdict(
            state, 3437, "2026-09-21", 15, ("client",), need=1, now=NOW)
        self.assertEqual(word, senderheadroom.FULL, reason)
        self.assertIsNone(free)
        self.assertIn("16 of 15", reason)


class NotSupplyingTheActiveSetIsNotAnEmptyOne(unittest.TestCase):
    """`active_campaign_ids` defaulted to `()`, so coverage passed vacuously.

    Flagged by Buggie's audit on 2026-09-20, which judged it latent because
    nothing in `src/` picks senders from this module yet. It was not latent
    for a reader: the first analysis of 489's schedule that evening obtained
    ROOM by passing the WALKED campaign list as the active list - the same
    error in different clothes - when the true answer was REFUSED.

    An empty tuple is an ASSERTION that nothing else can book. Omitting the
    argument is the ABSENCE of one. Those must not be the same answer on a
    safety path, and the difference is pinned here.
    """

    def state(self, finished_at=FRESH):
        return {"campaigns": {"327": {
            "complete": True,
            "finished_at": finished_at,
            "by_sender_day": {"2736|2026-09-23": 1},
        }}}

    def test_omitting_the_active_set_refuses_rather_than_reporting_room(self):
        word, reason, free = senderheadroom.verdict(
            self.state(), 2736, "2026-09-23", 15, need=1, now=NOW)
        self.assertEqual(word, senderheadroom.REFUSED, reason)
        self.assertIsNone(free)
        self.assertIn("active_campaign_ids", reason)

    def test_an_explicit_empty_tuple_is_still_an_assertion_and_permits_room(self):
        """Deliberate, and the reason the sentinel is not just `None`: a
        caller that genuinely knows nothing else can book may say so."""
        word, reason, free = senderheadroom.verdict(
            self.state(), 2736, "2026-09-23", 15, (), need=1, now=NOW)
        self.assertEqual(word, senderheadroom.ROOM, reason)
        self.assertEqual(14, free)

    def test_full_still_wins_over_the_missing_active_set(self):
        """The ordering is load-bearing: FULL is sound on evidence too weak
        for anything else, so it must answer before this refusal."""
        state = {"campaigns": {"327": {
            "complete": True, "finished_at": FRESH,
            "by_sender_day": {"2736|2026-09-23": 15}}}}
        word, reason, _ = senderheadroom.verdict(
            state, 2736, "2026-09-23", 15, need=1, now=NOW)
        self.assertEqual(word, senderheadroom.FULL, reason)

    def test_earliest_day_refuses_every_day_when_the_active_set_is_missing(self):
        day, reason = senderheadroom.earliest_day(
            self.state(), 2736, 15, need=1, now=NOW)
        self.assertIsNone(day)
        self.assertIn("active_campaign_ids", reason)

    def test_the_sentinel_is_not_equal_to_an_empty_tuple(self):
        self.assertIsNot(senderheadroom.UNSUPPLIED, ())
        self.assertNotEqual(senderheadroom.UNSUPPLIED, ())

    def test_every_public_selector_defaults_to_the_sentinel(self):
        """Behavioural guard: a new selector added with `=()` reintroduces
        the hole, so the default is asserted rather than assumed."""
        import inspect
        for name in ("verdict", "earliest_day", "rank"):
            with self.subTest(function=name):
                params = inspect.signature(
                    getattr(senderheadroom, name)).parameters
                self.assertIs(
                    params["active_campaign_ids"].default,
                    senderheadroom.UNSUPPLIED,
                    f"{name} must not default active_campaign_ids to a value "
                    f"that makes coverage() pass vacuously")


if __name__ == "__main__":
    unittest.main()
