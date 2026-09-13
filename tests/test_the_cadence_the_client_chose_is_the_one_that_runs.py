#!/usr/bin/env python3
"""The pacing has to fit the cadence, or the cadence silently shrinks.

Productive moved to a LinkedIn-heavy sequence on 2026-09-13: ~5 email touches
and ~6 LinkedIn activities across 21 days. The fatigue limits in force had
been set for the previous seven-step, email-led shape, and three of them
would have cut the new one down without raising anything:

    week one carries FIVE touches and the weekly cap was four
    the sequence is ELEVEN touches and the total cap was seven
    day one is a LinkedIn action AND an email, and the cross-channel
      minimum was 48 hours

A cadence that quietly runs a third of itself is worse than one that refuses,
because it reports eleven touches and sends four. So the numbers are asserted
against the sequence rather than chosen, and this file fails if either moves
away from the other.

The cross-channel minimum is now ZERO on purpose. Reaching somebody on email
and LinkedIn the same day is the point of a coordinated cadence; what wears a
prospect down is repetition on ONE channel, and that is paced separately.
"""
import unittest

from src import cadence, cadencelibrary, clients, fatigue


class TheClientRunsTheSequenceItNames(unittest.TestCase):

    def setUp(self):
        self.config = clients.load("productive")
        self.steps = cadence.steps_for(config=self.config)

    def test_productive_is_on_the_linkedin_heavy_cadence(self):
        self.assertEqual(self.config.get("cadence"), "productive_li_heavy_v1")

    def test_it_is_the_shape_the_operator_asked_for(self):
        shape = cadencelibrary.shape(self.steps)
        self.assertEqual(shape["email"], 5)
        self.assertEqual(shape["linkedin"], 6)
        self.assertEqual(shape["total"], 11)
        self.assertEqual(shape["days"], 21)

    def test_a_name_nobody_defined_falls_back_rather_than_inventing(self):
        steps = cadence.steps_for(config={"cadence": "no_such_cadence"})
        self.assertEqual(tuple(steps), cadence.STEPS)

    def test_a_campaign_sequence_still_outranks_the_library(self):
        """The library is a fallback, not a new authority."""
        own = [{"key": "only", "day": 1, "channel": "email"}]
        steps = cadence.steps_for(campaign={cadence.CADENCE_KEY: own},
                                  config=self.config)
        self.assertEqual([s["key"] for s in steps], ["only"])


class ThePacingFitsTheSequence(unittest.TestCase):

    def setUp(self):
        self.config = clients.load("productive")
        self.steps = cadence.steps_for(config=self.config)
        self.limits = fatigue.limits(self.config)

    def _value(self, key):
        return self.limits[key]["value"]

    def _busiest_week(self):
        return max(len([s for s in self.steps
                        if lo <= int(s["day"]) <= lo + 6])
                   for lo in range(1, 22))

    def test_the_weekly_cap_admits_the_busiest_week(self):
        busiest = self._busiest_week()
        self.assertGreaterEqual(
            self._value("contact.max_touches_per_week"), busiest,
            f"the sequence puts {busiest} touches in a week and the cap is "
            f"lower, so the cadence cannot run as written")

    def test_the_total_cap_admits_the_whole_sequence(self):
        self.assertGreaterEqual(
            self._value("contact.max_touches_total"), len(self.steps),
            "the sequence is longer than a contact is allowed to receive")

    def test_the_cross_channel_minimum_admits_a_coordinated_day(self):
        """Day one is a LinkedIn action and an email, on purpose."""
        days = [int(s["day"]) for s in self.steps]
        self.assertNotEqual(len(days), len(set(days)),
                            "no two steps share a day; this test is moot")
        self.assertEqual(self._value("contact.min_hours_between_touches"), 0)

    def test_but_one_channel_is_still_paced(self):
        """Zero cross-channel is not zero pacing."""
        per_channel = self._value(
            "contact.min_hours_between_same_channel_touches")
        self.assertGreater(per_channel, 0)
        gaps = []
        for channel in ("email", "linkedin"):
            days = sorted(int(s["day"]) for s in self.steps
                          if s["channel"] == channel)
            gaps += [(b - a) * 24 for a, b in zip(days, days[1:])]
        self.assertLessEqual(
            per_channel, min(gaps),
            f"the tightest same-channel gap in the sequence is {min(gaps)}h "
            f"and the limit is {per_channel}h, so a planned step is blocked")

    def test_every_limit_is_configured_rather_than_defaulted(self):
        """A default is a number nobody chose for this client."""
        unset = [k for k, v in self.limits.items() if not v["configured"]]
        self.assertEqual(unset, [], f"still on library defaults: {unset}")


class ACapabilityNobodyProvedIsNamed(unittest.TestCase):
    """The InMail and Open Profile branches depend on HeyReach.

    Neither is established. A step naming an unproven capability must be
    visible as such, so a planner can hold rather than skip it - a cadence
    that quietly drops its fallback reports six LinkedIn activities and
    performs five.
    """

    def test_the_sequence_declares_what_it_needs_from_the_provider(self):
        steps = cadence.steps_for(config={"cadence": "productive_li_heavy_v1"})
        needed = cadencelibrary.capabilities_used(steps)
        for capability in (cadencelibrary.CAP_CONNECT,
                           cadencelibrary.CAP_MESSAGE,
                           cadencelibrary.CAP_INMAIL,
                           cadencelibrary.CAP_OPEN_PROFILE):
            self.assertIn(capability, needed)

    def test_the_branches_are_on_the_steps_that_fork(self):
        steps = {s["key"]: s for s in
                 cadence.steps_for(config={"cadence": "productive_li_heavy_v1"})}
        self.assertEqual(steps["li1"]["alternative"]["requires"],
                         cadencelibrary.OPEN_PROFILE)
        self.assertEqual(steps["li3"]["alternative"]["requires"],
                         cadencelibrary.CONNECTION_NOT_ACCEPTED)
        self.assertEqual(steps["li3"]["alternative"]["linkedin_action"],
                         "inmail")

    def test_the_balanced_alternative_exists_to_be_compared(self):
        balanced = cadencelibrary.shape(
            cadence.steps_for(config={"cadence": "productive_balanced_v1"}))
        heavy = cadencelibrary.shape(
            cadence.steps_for(config={"cadence": "productive_li_heavy_v1"}))
        self.assertLess(balanced["total"], heavy["total"])
        self.assertLess(balanced["linkedin"], heavy["linkedin"])


if __name__ == "__main__":
    unittest.main()
