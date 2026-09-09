"""Which cohorts are doing better, said carefully enough to act on.

Four properties, and every test is one of them:

**Small samples say nothing.** The failure this is built against is
optimising on four replies against three. Below the floor a cohort gets no
state, no lift, no recommendation and no boost - not cautious ones, none.

**It is observational.** Every account in a cohort was chosen, worked and
written to by somebody. "These accounts replied more often" is supportable;
"being a German agency causes replies" is not, and only the second invites
a decision the evidence cannot carry.

**It recommends and never acts.** No path from here changes the ICP,
targeting, or a campaign. A person accepts or ignores.

**It cannot override a refusal.** A cohort boost may raise attention. It
cannot make a suppressed account eligible.
"""
import unittest

from src import eligibility, hygiene, learning, priority


def rows(count, hits, **parts):
    """`count` contacted accounts in one cohort, `hits` of which converted."""
    return [{**parts, learning.CONTACTED: True,
             learning.POSITIVE: index < hits}
            for index in range(count)]


class SmallSamplesSayNothing(unittest.TestCase):

    def cohort(self, count, hits):
        data = rows(count, hits, country="Germany", vertical="agency")
        found = learning.describe(data, ("country", "vertical"))
        return found["cohorts"][0]

    def test_a_handful_of_replies_produces_no_state(self):
        cohort = self.cohort(10, 4)
        self.assertEqual(cohort["state"], learning.INSUFFICIENT_DATA)

    def test_it_produces_no_lift_rather_than_a_cautious_one(self):
        """A number with a caveat beside it is still a number somebody
        will quote."""
        self.assertIsNone(self.cohort(10, 4)["lift"])

    def test_it_produces_no_confidence_bound(self):
        self.assertIsNone(self.cohort(10, 4)["low"])

    def test_it_produces_no_recommendation(self):
        data = rows(10, 4, country="Germany", vertical="agency")
        found = learning.describe(data, ("country", "vertical"))
        self.assertEqual(learning.recommend(found)["recommendations"], [])

    def test_it_produces_no_priority_boost(self):
        self.assertEqual(learning.boost(self.cohort(10, 4)), 0.0)

    def test_enough_volume_but_too_few_outcomes_is_still_nothing(self):
        """Both floors, not either."""
        cohort = self.cohort(200, 2)
        self.assertEqual(cohort["state"], learning.INSUFFICIENT_DATA)

    def test_the_floor_is_reported_so_it_can_be_argued_with(self):
        found = learning.describe(rows(10, 4, country="DE", vertical="a"),
                                  ("country", "vertical"))
        self.assertEqual(found["floor"]["contacted"],
                         learning.DEFAULTS["minimum_contacted"])

    def test_the_reason_says_what_would_be_enough(self):
        cohort = self.cohort(10, 4)
        self.assertIn(str(learning.DEFAULTS["minimum_contacted"]),
                      cohort["why"])


class WhatItWillSayWithEnoughEvidence(unittest.TestCase):

    def described(self):
        data = (rows(120, 18, country="Germany", vertical="agency")
                + rows(400, 20, country="UK", vertical="agency"))
        return learning.describe(data, ("country", "vertical"))

    def test_a_clearly_better_cohort_is_named(self):
        found = self.described()
        leader = found["cohorts"][0]
        self.assertEqual(leader["cohort"], "Germany / agency")
        self.assertEqual(leader["state"], learning.HIGH_CONFIDENCE)

    def test_the_baseline_is_the_workspace_and_not_a_benchmark(self):
        """What this workspace actually does is the only fair comparison:
        the copy, the senders and the ICP are roughly constant within it."""
        found = self.described()
        self.assertAlmostEqual(found["baseline"]["rate"], 38 / 520.0, places=6)

    def test_a_cohort_behind_the_baseline_is_named_too(self):
        behind = [c for c in self.described()["cohorts"]
                  if c["cohort"] == "UK / agency"][0]
        self.assertEqual(behind["state"], learning.DECLINING)

    def test_confidence_requires_the_lower_bound_to_clear_the_baseline(self):
        """Not the raw rate. A plain proportion says one reply from one
        send is a hundred per cent.

        This fixture is chosen so the two answers differ: 6 of 40 is well
        above a 10.2% baseline, and its Wilson lower bound is 7.1% - below
        it. Reading the raw rate would call this clearly ahead; reading the
        interval calls it promising, which is what 6 replies supports.
        """
        data = (rows(40, 6, country="DE", vertical="agency")
                + rows(900, 90, country="UK", vertical="agency"))
        found = learning.describe(data, ("country", "vertical"))
        cohort = [c for c in found["cohorts"] if c["cohort"] == "DE / agency"][0]

        self.assertGreater(cohort["rate"], cohort["baseline_rate"])
        self.assertLess(cohort["low"], cohort["baseline_rate"])
        self.assertEqual(cohort["state"], learning.PROMISING)

    def test_the_summary_counts_only_cohorts_that_said_something(self):
        data = (rows(120, 18, country="Germany", vertical="agency")
                + rows(8, 3, country="Spain", vertical="agency"))
        found = learning.describe(data, ("country", "vertical"))
        self.assertEqual(len(found["cohorts"]), 2)
        self.assertEqual(found["cohorts_with_enough_data"], 1)


class ItIsObservational(unittest.TestCase):

    def described(self):
        data = (rows(120, 18, country="Germany", vertical="agency")
                + rows(400, 20, country="UK", vertical="agency"))
        return learning.describe(data, ("country", "vertical"))

    def test_no_cohort_claims_a_cause(self):
        for cohort in self.described()["cohorts"]:
            self.assertNotIn("cause", cohort)
            self.assertNotIn("because", cohort)

    def test_the_summary_says_what_else_differed(self):
        self.assertIn("chosen, worked and written to",
                      self.described()["note"])

    def test_a_declining_cohort_does_not_say_stop(self):
        """It may be the cohort, the copy, the senders or the timing. The
        number does not say which."""
        found = self.described()
        behind = [r for r in learning.recommend(found)["recommendations"]
                  if r["kind"] == "examine"][0]
        self.assertNotIn("stop", behind["what"].lower())
        self.assertIn("does not say which", behind["why"])

    def test_opens_and_clicks_are_not_outcomes(self):
        """They measure whether a message was rendered."""
        self.assertNotIn("opened", learning.OUTCOMES)
        self.assertNotIn("clicked", learning.OUTCOMES)

    def test_the_default_objective_is_a_positive_reply(self):
        """A cohort generating many "no thank you"s is not performing."""
        self.assertEqual(learning.DEFAULT_OBJECTIVE, learning.POSITIVE)


class IncompleteRowsAreExcludedNotBucketed(unittest.TestCase):

    def test_a_row_missing_a_dimension_is_skipped(self):
        """An "unknown country" cohort is a data-quality report wearing a
        market segment, and acting on it means acting on the accounts we
        know least about."""
        data = (rows(60, 10, country="Germany", vertical="agency")
                + rows(60, 30, country=None, vertical="agency"))
        found = learning.describe(data, ("country", "vertical"))
        self.assertEqual([c["cohort"] for c in found["cohorts"]],
                         ["Germany / agency"])
        self.assertEqual(found["skipped_incomplete"], 60)

    def test_the_word_unknown_is_treated_as_missing(self):
        data = rows(60, 10, country="unknown", vertical="agency")
        found = learning.describe(data, ("country", "vertical"))
        self.assertEqual(found["cohorts"], [])
        self.assertEqual(found["skipped_incomplete"], 60)

    def test_skipped_rows_are_counted_not_hidden(self):
        data = rows(20, 5, country="", vertical="agency")
        found = learning.describe(data, ("country", "vertical"))
        self.assertEqual(found["skipped_incomplete"], 20)


class ItRecommendsAndNeverActs(unittest.TestCase):

    def described(self):
        data = (rows(120, 18, country="Germany", vertical="agency")
                + rows(400, 20, country="UK", vertical="agency"))
        return learning.describe(data, ("country", "vertical"))

    def test_recommendations_are_phrased_as_something_to_consider(self):
        for row in learning.recommend(self.described())["recommendations"]:
            self.assertTrue(row["what"].startswith("Consider"), row["what"])

    def test_it_says_nothing_changes_until_a_person_decides(self):
        self.assertIn("until a person decides",
                      learning.recommend(self.described())["note"])

    def test_it_says_it_cannot_change_the_icp(self):
        self.assertIn("can change the ICP",
                      learning.recommend(self.described())["note"])
        self.assertIn("none of them",
                      learning.recommend(self.described())["note"])

    def test_the_module_has_no_path_that_writes_anything(self):
        """The strongest form of "it never acts": there is nothing here
        that could."""
        import inspect
        source = inspect.getsource(learning)
        for forbidden in ("store.save", "set_policy", "qualify.", "open(",
                          "write("):
            self.assertNotIn(forbidden, source, forbidden)


class ABoostIsNotAPermission(unittest.TestCase):

    def leader(self):
        data = (rows(120, 18, country="Germany", vertical="agency")
                + rows(400, 20, country="UK", vertical="agency"))
        return learning.describe(data, ("country", "vertical"))["cohorts"][0]

    def test_a_boost_is_bounded_even_by_an_extraordinary_cohort(self):
        """This one converts at 50% against a 1% baseline - a lift of 8.2,
        which un-capped would be a boost of 0.41. The ceiling is the point:
        the strongest cohort anybody will ever see still cannot dominate
        the four components that are measured better than it is.
        """
        data = (rows(200, 100, country="DE", vertical="agency")
                + rows(2000, 20, country="UK", vertical="agency"))
        found = learning.describe(data, ("country", "vertical"))
        cohort = [c for c in found["cohorts"] if c["cohort"] == "DE / agency"][0]

        self.assertGreater(cohort["lift"] * 0.05,
                           learning.DEFAULTS["maximum_boost"])
        self.assertEqual(learning.boost(cohort),
                         learning.DEFAULTS["maximum_boost"])

    def test_a_promising_cohort_earns_no_boost_at_all(self):
        """Ahead of the baseline is not the same as clearly ahead, and
        only the second is evidence enough to move a score."""
        data = (rows(40, 6, country="DE", vertical="agency")
                + rows(900, 90, country="UK", vertical="agency"))
        found = learning.describe(data, ("country", "vertical"))
        cohort = [c for c in found["cohorts"] if c["cohort"] == "DE / agency"][0]

        self.assertEqual(cohort["state"], learning.PROMISING)
        self.assertEqual(learning.boost(cohort), 0.0)

    def test_a_declining_cohort_earns_nothing_rather_than_a_penalty(self):
        data = (rows(120, 18, country="Germany", vertical="agency")
                + rows(400, 20, country="UK", vertical="agency"))
        behind = [c for c in
                  learning.describe(data, ("country", "vertical"))["cohorts"]
                  if c["state"] == learning.DECLINING][0]
        self.assertEqual(learning.boost(behind), 0.0)

    def test_eligibility_never_consults_learning(self):
        """The boost raises attention. Whether anything may be sent is
        decided somewhere that has never heard of it."""
        import inspect
        for module in (eligibility, hygiene):
            self.assertNotIn("learning", inspect.getsource(module))

    def test_priority_does_not_import_learning_either(self):
        """A cohort boost is an input a caller may add, not something the
        scorer reaches for on its own."""
        import inspect
        self.assertNotIn("import learning", inspect.getsource(priority))


if __name__ == "__main__":
    unittest.main()
