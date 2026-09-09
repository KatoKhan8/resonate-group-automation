"""Cadence steps as UTC instants, in the prospect's own local time.

`geo` already proves the window conversion and daylight saving. What is tested
here is the layer above it: a whole cadence, a whole batch, and the two ways
this goes quietly wrong - a step that lands on a weekend, and a company whose
timezone nobody actually knows.

Nothing here sends. `would_send` is asserted, not assumed.
"""
import datetime
import unittest

from src import cadence, geo, schedule

START = datetime.date(2026, 9, 1)          # a Tuesday
WINTER = datetime.date(2026, 1, 13)        # a Tuesday
SUMMER = datetime.date(2026, 7, 14)        # a Tuesday

available = geo.available()


class TestTheContract(unittest.TestCase):
    def test_nothing_here_would_send(self):
        self.assertEqual(schedule.demo(START)["would_send"], 0)

    def test_a_batch_reports_every_company_it_was_given(self):
        result = schedule.demo(START)
        self.assertEqual(result["companies"],
                         result["schedulable"] + result["held"])

    def test_every_step_of_the_clients_cadence_appears(self):
        plan = schedule.for_company(
            {"timezone": "Europe/Zagreb", "timezone_confidence": geo.HIGH},
            START)
        self.assertEqual([s["step"] for s in plan["steps"]],
                         [s["key"] for s in cadence.STEPS])


class TestAnUnknownTimezone(unittest.TestCase):
    """A guessed timezone sends at 04:00; a missing one stops the send."""

    def test_a_company_with_no_timezone_is_held_not_guessed(self):
        plan = schedule.for_company({"timezone": None}, START)
        self.assertFalse(plan["schedulable"])
        self.assertTrue(plan["why"])

    def test_a_held_company_gets_no_instant_on_any_step(self):
        plan = schedule.for_company({"timezone": None}, START)
        for step in plan["steps"]:
            self.assertIsNone(step["utc_at"], step["step"])
            self.assertIsNone(step["local_at"], step["step"])
            self.assertEqual(step["status"], schedule.HELD)

    def test_every_held_step_carries_the_reason(self):
        for step in schedule.for_company({"timezone": None}, START)["steps"]:
            self.assertTrue(step["why"], step["step"])

    def test_an_ambiguous_country_is_held(self):
        plan = schedule.for_company(geo.resolve(country="United States"), START)
        self.assertFalse(plan["schedulable"])

    def test_a_low_confidence_timezone_is_held(self):
        plan = schedule.for_company(
            {"timezone": "Europe/Zagreb", "timezone_confidence": geo.LOW},
            START)
        self.assertFalse(plan["schedulable"])

    def test_held_companies_are_counted_separately_from_scheduled_ones(self):
        result = schedule.for_batch(
            [{"domain": "a.test", "timezone": "Europe/London",
              "timezone_confidence": geo.HIGH},
             {"domain": "b.test", "timezone": None}], START)
        self.assertEqual(result["schedulable"], 1 if available else 0)
        self.assertEqual(result["held"], 1 if available else 2)


@unittest.skipUnless(available, "no IANA timezone database on this machine")
class TestPlacement(unittest.TestCase):
    def test_a_step_lands_inside_the_configured_window(self):
        step = schedule.place("Europe/Zagreb", START, "email")
        self.assertEqual(step["local_at"][11:16], "09:30")

    def test_linkedin_and_email_have_different_windows(self):
        email = schedule.place("Europe/Zagreb", START, "email")
        linkedin = schedule.place("Europe/Zagreb", START, "linkedin")
        self.assertNotEqual(email["local_at"][11:16],
                            linkedin["local_at"][11:16])

    def test_the_offset_into_the_window_is_configurable(self):
        config = {"scheduling": {"offsets": {"email": 0}}}
        step = schedule.place("Europe/Zagreb", START, "email", config)
        self.assertEqual(step["local_at"][11:16], "09:00")

    def test_an_offset_never_runs_past_the_end_of_the_window(self):
        """A 45-minute offset into a 30-minute window would send outside it."""
        config = {"scheduling": {
            "windows": {"email": {"start": "09:00", "end": "09:30"}},
            "offsets": {"email": 600}}}
        step = schedule.place("Europe/Zagreb", START, "email", config)
        self.assertLessEqual(step["local_at"][11:16], "09:30")

    def test_the_window_the_step_was_placed_in_is_reported(self):
        step = schedule.place("Europe/Zagreb", START, "email")
        self.assertEqual(step["window_local"], "09:00-11:30")


@unittest.skipUnless(available, "no IANA timezone database on this machine")
class TestWeekends(unittest.TestCase):
    """Day 5 of a Tuesday start is a Saturday. It must not silently send."""

    def test_a_weekend_step_rolls_forward_to_a_sending_day(self):
        saturday = datetime.date(2026, 9, 5)
        step = schedule.place("Europe/Zagreb", saturday, "email")
        self.assertEqual(step["status"], schedule.ROLLED)
        self.assertIn(datetime.date.fromisoformat(step["date"]).isoweekday(),
                      geo.windows(None)["days"])

    def test_the_roll_is_stated_rather_than_silent(self):
        step = schedule.place("Europe/Zagreb", datetime.date(2026, 9, 5),
                              "email")
        self.assertIn("rolled forward", step["why"])

    def test_a_weekday_step_is_not_rolled(self):
        step = schedule.place("Europe/Zagreb", START, "email")
        self.assertEqual(step["status"], schedule.SCHEDULED)

    def test_no_step_of_a_cadence_lands_on_a_non_sending_day(self):
        days = geo.windows(None)["days"]
        for step in schedule.for_timezone("Europe/Zagreb", START):
            self.assertIn(
                datetime.date.fromisoformat(step["date"]).isoweekday(), days,
                step["step"])

    def test_a_client_may_configure_weekend_sending(self):
        config = {"scheduling": {"windows": {"days": [1, 2, 3, 4, 5, 6, 7]}}}
        step = schedule.place("Europe/Zagreb", datetime.date(2026, 9, 5),
                              "email", config)
        self.assertEqual(step["status"], schedule.SCHEDULED)


@unittest.skipUnless(available, "no IANA timezone database on this machine")
class TestDaylightSavingAcrossACadence(unittest.TestCase):
    """The same local time is a different UTC instant on different dates."""

    def test_europe_a_cadence_in_winter_differs_from_one_in_summer(self):
        winter = schedule.place("Europe/Zagreb", WINTER, "email")
        summer = schedule.place("Europe/Zagreb", SUMMER, "email")
        self.assertEqual(winter["local_at"][11:16], summer["local_at"][11:16])
        self.assertNotEqual(winter["utc_at"][11:16], summer["utc_at"][11:16])

    def test_europe_the_offset_moves_by_exactly_one_hour(self):
        winter = schedule.place("Europe/London", WINTER, "email")
        summer = schedule.place("Europe/London", SUMMER, "email")
        self.assertEqual(summer["utc_offset_hours"]
                         - winter["utc_offset_hours"], 1.0)

    def test_us_the_offset_moves_by_exactly_one_hour(self):
        winter = schedule.place("America/New_York", WINTER, "email")
        summer = schedule.place("America/New_York", SUMMER, "email")
        self.assertEqual(summer["utc_offset_hours"]
                         - winter["utc_offset_hours"], 1.0)

    def test_a_zone_without_dst_does_not_move(self):
        winter = schedule.place("America/Phoenix", WINTER, "email")
        summer = schedule.place("America/Phoenix", SUMMER, "email")
        self.assertEqual(winter["utc_offset_hours"],
                         summer["utc_offset_hours"])

    def test_the_southern_hemisphere_runs_the_other_way(self):
        self.assertTrue(schedule.place("Australia/Sydney", WINTER,
                                       "email")["is_dst"])
        self.assertFalse(schedule.place("Australia/Sydney", SUMMER,
                                        "email")["is_dst"])

    def test_a_cadence_spanning_a_dst_change_keeps_one_local_time(self):
        """The 21-day cadence crosses the European change on 25 October 2026."""
        steps = schedule.for_timezone("Europe/London",
                                      datetime.date(2026, 10, 13))
        locals_ = {s["local_at"][11:16] for s in steps
                   if s["channel"] == "email"}
        self.assertEqual(len(locals_), 1, locals_)
        offsets = {s["utc_offset_hours"] for s in steps}
        self.assertEqual(len(offsets), 2, "the cadence should cross the change")


@unittest.skipUnless(available, "no IANA timezone database on this machine")
class TestABatchAcrossFourCities(unittest.TestCase):
    """London, New York, Zagreb and Sydney: the spread is the whole point."""

    def setUp(self):
        self.result = schedule.demo(START)

    def test_all_four_are_schedulable(self):
        self.assertEqual(self.result["schedulable"], 4)
        self.assertEqual(self.result["held"], 0)

    def test_the_same_local_time_spans_most_of_a_day_in_utc(self):
        span = self.result["first_step_utc_span"]
        self.assertGreater(span["hours"], 12)
        self.assertLess(span["hours"], 24)

    def test_sydney_fires_before_london_on_the_same_local_morning(self):
        by_zone = {r["timezone"]: r["steps"][0]["utc_at"]
                   for r in self.result["rows"]}
        self.assertLess(by_zone["Australia/Sydney"], by_zone["Europe/London"])

    def test_london_fires_before_new_york_on_the_same_local_morning(self):
        by_zone = {r["timezone"]: r["steps"][0]["utc_at"]
                   for r in self.result["rows"]}
        self.assertLess(by_zone["Europe/London"], by_zone["America/New_York"])

    def test_every_company_is_counted_in_the_timezone_breakdown(self):
        self.assertEqual(sum(self.result["timezones"].values()),
                         self.result["schedulable"])

    def test_every_scheduled_step_carries_both_times(self):
        for row in self.result["rows"]:
            for step in row["steps"]:
                self.assertTrue(step["local_at"], step["step"])
                self.assertTrue(step["utc_at"], step["step"])


if __name__ == "__main__":
    unittest.main()
