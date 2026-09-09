"""One experiment, everything known about it, and what may be said.

The test that matters most is the composition rule: an evaluator handed a
four-step arm and a seven-step arm on day fifteen will find a winner, it
will be the short arm, and the finding will be about the calendar. So the
report may not act on a verdict while any arm is still immature, however
clean the intervals look.

The second is that every refusal is named. A report saying "no clear
winner" without saying whether that is for want of time, for want of
people, or because the arms genuinely perform alike gets read as the last
of the three.
"""
import unittest

from src import cadencearms as arms, cadencereport as R, events, variants

SEVEN = [{"key": f"s{i}", "day": d, "channel": "email",
          "template": "persona_pain"}
         for i, d in enumerate((1, 3, 7, 12, 18, 25, 35), start=1)]
FOUR = SEVEN[:4]

TODAY = "2026-09-30"
LONG_AGO = "2026-06-01T09:00:00+00:00"


def an_experiment():
    return arms.experiment("cad-1",
                           [arms.arm("four", "4 steps", FOUR),
                            arms.arm("seven", "7 steps", SEVEN)])


def a_record(rid, arm_id, confirmed, replied=False, positive=False,
             unsubscribed=False, assigned_at=LONG_AGO):
    rec = {"id": rid, "client": "demo", "company": rid, "events": [],
           "contacts": [{"key": "a", "name": "A", "email": "a@x.test"}],
           arms.ASSIGNMENT_KEY: {
               "experiment_id": "cad-1", "arm_id": arm_id, "unit": "account",
               "unit_key": rid, "allocation_version": 1, "at": assigned_at,
               "why": "assigned"}}
    steps = SEVEN if arm_id == "seven" else FOUR
    for i in range(confirmed):
        rec["events"].append({
            "type": events.PUSH_MARKED, "contact": "a", "channel": "email",
            "step": steps[i]["key"],
            "at": f"2026-07-{i + 1:02d}T09:00:00+00:00", "sender_id": "m"})
    if replied:
        rec["events"].append({
            "type": (events.POSITIVE_REPLY_DETECTED if positive
                     else events.REPLY_RECEIVED),
            "contact": "a", "channel": "email",
            "at": f"2026-07-{confirmed:02d}T21:00:00+00:00"})
    if unsubscribed:
        rec["events"].append({
            "type": events.CONTACT_SUPPRESSED, "contact": "a",
            "at": f"2026-07-{confirmed:02d}T22:00:00+00:00"})
    return rec


def cohort(arm_id, people, prefix, positives=0, unsubscribes=0,
           confirmed=None, assigned_at=LONG_AGO):
    steps = confirmed if confirmed is not None else len(
        SEVEN if arm_id == "seven" else FOUR)
    out = []
    for index in range(people):
        out.append(a_record(
            f"{prefix}-{index}", arm_id, steps,
            replied=index < positives, positive=index < positives,
            unsubscribed=positives <= index < positives + unsubscribes,
            assigned_at=assigned_at))
    return out


def separated():
    """Enough people, enough outcomes, and a wide gap between the arms."""
    return (cohort("seven", 60, "s", positives=24)
            + cohort("four", 60, "f", positives=3))


class MaturityOutranksTheStatistics(unittest.TestCase):
    """The day-fifteen trap, at the level that decides what is shown."""

    def setUp(self):
        """Assigned fifteen days ago.

        The four-step arm's last step is day 12, so it has run: four
        confirmed and its span elapsed. The seven-step arm's last step is
        day 35, so on day 15 only three of its steps can have gone out -
        which is the point. Giving it all seven would make it a *completed*
        sequence, and a completed sequence is mature whatever the calendar
        says, so the trap would not be set.
        """
        recent = "2026-09-15T09:00:00+00:00"
        self.recs = (cohort("seven", 60, "s", positives=24, confirmed=3,
                            assigned_at=recent)
                     + cohort("four", 60, "f", positives=3, confirmed=4,
                              assigned_at=recent))
        self.found = R.report(an_experiment(), self.recs, today=TODAY)

    def test_the_evaluator_still_finds_a_winner(self):
        """It is doing its job; the numbers really are separated. This
        report is what stops that becoming a decision."""
        self.assertEqual(self.found["evaluation"]["state"], variants.WINNER)

    def test_but_the_report_will_not_act_on_it(self):
        self.assertFalse(self.found["actionable"])
        self.assertIsNone(self.found["leader"])

    def test_and_it_says_time_is_the_reason(self):
        codes = [row["code"] for row in self.found["refusals"]]
        self.assertEqual(codes[0], R.IMMATURE)

    def test_it_says_how_much_longer(self):
        first = self.found["refusals"][0]
        self.assertGreater(first["days_until_mature"], 0)

    def test_the_headline_leads_with_the_time_rather_than_the_winner(self):
        self.assertIn("Too early", self.found["headline"])


class WhenEverythingIsSatisfied(unittest.TestCase):

    def setUp(self):
        self.found = R.report(an_experiment(), separated(), today=TODAY)

    def test_it_is_actionable(self):
        self.assertTrue(self.found["actionable"])
        self.assertEqual(self.found["refusals"], [])

    def test_it_names_the_leader(self):
        self.assertEqual(self.found["leader"], "seven")

    def test_the_headline_is_the_verdict(self):
        self.assertIn("7 steps", self.found["headline"])


class ARefusalIsAlwaysNamed(unittest.TestCase):

    def test_too_few_people_is_not_reported_as_no_difference(self):
        """The two states a reader collapses if nobody separates them."""
        recs = cohort("seven", 3, "s", positives=1) + cohort("four", 3, "f")
        found = R.report(an_experiment(), recs, today=TODAY)
        self.assertFalse(found["actionable"])
        self.assertEqual(found["evaluation"]["state"],
                         variants.INSUFFICIENT_DATA)
        self.assertIn(R.NO_WINNER,
                      [row["code"] for row in found["refusals"]])

    def test_arms_that_perform_alike_say_so(self):
        recs = (cohort("seven", 60, "s", positives=9)
                + cohort("four", 60, "f", positives=8))
        found = R.report(an_experiment(), recs, today=TODAY)
        self.assertFalse(found["actionable"])
        self.assertIn(found["evaluation"]["state"],
                      (variants.LEADING, variants.NO_CLEAR_WINNER))

    def test_a_leader_that_costs_more_is_refused(self):
        """A winner on replies that is also the arm burning people is not
        a winner. The safety comparison is a veto, not a footnote."""
        recs = (cohort("seven", 60, "s", positives=24, unsubscribes=30)
                + cohort("four", 60, "f", positives=3))
        found = R.report(an_experiment(), recs, today=TODAY)
        self.assertIn(R.SAFETY_DISAGREES,
                      [row["code"] for row in found["refusals"]])
        self.assertFalse(found["actionable"])

    def test_the_same_experiment_without_the_cost_is_actionable(self):
        """So the veto above is a veto and not a general refusal."""
        found = R.report(an_experiment(), separated(), today=TODAY)
        self.assertTrue(found["actionable"])


class ItAssemblesRatherThanRecomputes(unittest.TestCase):

    def setUp(self):
        self.recs = separated()
        self.found = R.report(an_experiment(), self.recs, today=TODAY)

    def test_the_reply_numbers_are_the_reply_modules(self):
        from src import cadencereplies

        mine = cadencereplies.by_arm(an_experiment(), self.recs,
                                     positive_only=True)
        for arm in self.found["arms"]:
            self.assertEqual(arm["replies"], mine[arm["arm_id"]])

    def test_the_safety_numbers_are_the_safety_modules(self):
        from src import cadencesafety

        mine = cadencesafety.compare(an_experiment(), self.recs)
        self.assertEqual(self.found["safety"], mine)

    def test_the_value_curve_is_the_value_modules(self):
        from src import cadencevalue

        mine = cadencevalue.compare(an_experiment(), self.recs,
                                    positive_only=True)
        for arm in self.found["arms"]:
            self.assertEqual(arm["value"], mine[arm["arm_id"]])

    def test_it_uses_the_one_evaluator_rather_than_a_second(self):
        """A cadence evaluator would be a second set of thresholds and a
        second place to get Wilson wrong."""
        import ast
        import inspect

        source = inspect.getsource(R)
        calls = {node.func.attr for node in ast.walk(ast.parse(source))
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)}
        self.assertIn("evaluate", calls)
        self.assertNotIn("wilson_low", calls)
        self.assertNotIn("wilson_high", calls)

    def test_the_evaluator_is_given_exposure_not_assignment(self):
        """Somebody assigned and suppressed before step one has not
        experienced the cadence. Counting them as an exposure dilutes the
        arm they were assigned to, in proportion to how many people it
        never reached - which is the arm's own fault only if you count
        them."""
        recs = self.recs + cohort("seven", 200, "ghost", confirmed=0)
        found = R.report(an_experiment(), recs, today=TODAY)
        row = next(r for r in found["evaluation"]["rows"]
                   if r["variant_id"] == "seven")
        self.assertEqual(row["exposures"], 60)

    def test_each_arm_carries_its_shape(self):
        shapes = [arm["shape"] for arm in self.found["arms"]]
        self.assertEqual(shapes[0].count("->"), 3)
        self.assertEqual(shapes[1].count("->"), 6)


class ThresholdsMayBeRaisedForCadence(unittest.TestCase):
    """An arm needs more people than a wording does, and a workspace that
    knows it should be able to say so without a second evaluator."""

    def test_a_raised_minimum_makes_a_thin_experiment_insufficient(self):
        recs = separated()
        found = R.report(an_experiment(), recs, today=TODAY,
                         config={"cadence_experiments":
                                 {"minimum_per_variant": 500}})
        self.assertEqual(found["evaluation"]["state"],
                         variants.INSUFFICIENT_DATA)
        self.assertFalse(found["actionable"])

    def test_without_an_override_copys_thresholds_apply(self):
        self.assertEqual(R.thresholds({"experiments": {"a": 1}}),
                         {"experiments": {"a": 1}})

    def test_an_override_does_not_discard_the_rest_of_the_config(self):
        found = R.thresholds({"experiments": {"minimum_lift": 0.5},
                              "cadence_experiments": {"minimum_outcomes": 40},
                              "client": "demo"})
        self.assertEqual(found["experiments"],
                         {"minimum_lift": 0.5, "minimum_outcomes": 40})
        self.assertEqual(found["client"], "demo")


class AnEmptyExperimentSaysSoRatherThanFailing(unittest.TestCase):

    def test_no_records_at_all(self):
        found = R.report(an_experiment(), [], today=TODAY)
        self.assertFalse(found["actionable"])
        self.assertIn(R.IMMATURE, [row["code"] for row in found["refusals"]])

    def test_one_arm_with_nobody_in_it(self):
        found = R.report(an_experiment(),
                         cohort("seven", 40, "s", positives=8), today=TODAY)
        self.assertFalse(found["actionable"])


if __name__ == "__main__":
    unittest.main()
