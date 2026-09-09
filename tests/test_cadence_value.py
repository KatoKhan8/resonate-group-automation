"""What each step adds, and where a sequence stops paying.

"Seven steps got 34 replies, four got 29" cannot tell apart a world where
steps five to seven earned five replies from one where they earned none
and the difference is noise. Both produce those totals. The number that
decides whether to run three more steps is the marginal one.

The two failure modes tested here are the two ways a marginal number goes
wrong: dividing a late step's replies by the whole arm, which makes every
sequence look like it decays; and reading an empty column as evidence that
a step earns nothing when the truth is that nine people reached it.
"""
import unittest

from src import cadencearms as arms, cadencevalue as V, events

SEVEN = [{"key": f"s{i}", "day": d, "channel": "email",
          "template": "persona_pain"}
         for i, d in enumerate((1, 3, 7, 12, 18, 25, 35), start=1)]
FOUR = SEVEN[:4]


def an_experiment():
    return arms.experiment("cad-1",
                           [arms.arm("four", "4 steps", FOUR),
                            arms.arm("seven", "7 steps", SEVEN)])


def a_record(rid, arm_id, confirmed, reply_after=None, positive=False):
    """`confirmed` steps delivered; a reply after step `reply_after`."""
    rec = {"id": rid, "client": "demo", "company": rid, "events": [],
           "contacts": [{"key": "a", "name": "A", "email": "a@x.test"}],
           arms.ASSIGNMENT_KEY: {
               "experiment_id": "cad-1", "arm_id": arm_id, "unit": "account",
               "unit_key": rid, "allocation_version": 1,
               "at": "2026-06-01T09:00:00+00:00", "why": "assigned"}}
    steps = SEVEN if arm_id == "seven" else FOUR
    for i in range(confirmed):
        rec["events"].append({
            "type": events.PUSH_MARKED, "contact": "a", "channel": "email",
            "step": steps[i]["key"],
            "at": f"2026-07-{i + 1:02d}T09:00:00+00:00", "sender_id": "m"})
    if reply_after:
        # Half a day after the step it follows, and before the next one.
        rec["events"].append({
            "type": (events.POSITIVE_REPLY_DETECTED if positive
                     else events.REPLY_RECEIVED),
            "contact": "a", "channel": "email",
            "at": f"2026-07-{reply_after:02d}T21:00:00+00:00"})
    return rec


def cohort(arm_id, people, replies_after=(), positive=False, steps=None,
           prefix=None):
    """`people` contacts who each received `steps` of the arm's sequence.

    The repliers are listed as step positions: `(2, 2, 5)` means three of
    them replied, two after step two and one after step five. Everybody
    else received the whole arm and said nothing.
    """
    whole = len(SEVEN if arm_id == "seven" else FOUR)
    steps = whole if steps is None else steps
    recs, replies = [], list(replies_after)
    # `prefix` because two cohorts on one arm would otherwise generate the
    # same record ids, and attribution deduplicates by (record, contact) -
    # so the second cohort would silently vanish into the first.
    prefix = prefix or arm_id
    for index in range(people):
        after = replies.pop() if replies else None
        recs.append(a_record(f"{prefix}-{index}", arm_id, steps,
                             reply_after=after, positive=positive))
    return recs


class TheDenominatorIsWhoReachedThatStep(unittest.TestCase):
    """Dividing by the whole arm makes every sequence look like it decays,
    whether it does or not, because the denominator stays still while the
    population shrinks."""

    def setUp(self):
        # 40 people reach step 2. Of those, 20 go on to reach step 5.
        self.recs = ([a_record(f"a{i}", "seven", 2) for i in range(20)]
                     + [a_record(f"b{i}", "seven", 5) for i in range(20)])
        # One reply after step 5, from somebody who got that far.
        self.recs[-1] = a_record("b19", "seven", 5, reply_after=5)
        self.rows = V.step_value(an_experiment(), self.recs, "seven")

    def test_an_early_step_is_over_everybody(self):
        self.assertEqual(self.rows[0]["reached"], 40)

    def test_a_late_step_is_over_the_people_who_got_there(self):
        self.assertEqual(self.rows[4]["reached"], 20)

    def test_the_rate_uses_that_denominator(self):
        self.assertAlmostEqual(self.rows[4]["rate"], 1 / 20)

    def test_a_step_nobody_reached_has_no_rate_rather_than_zero(self):
        """Zero per cent and no evidence are different answers."""
        self.assertEqual(self.rows[6]["reached"], 0)
        self.assertIsNone(self.rows[6]["rate"])

    def test_the_cumulative_rate_is_over_everybody_who_started(self):
        """A different question from the marginal one, and a screen showing
        only one of them misleads either way."""
        self.assertAlmostEqual(self.rows[4]["cumulative_rate"], 1 / 40)


class ARateAfterStepOneIsConditional(unittest.TestCase):
    """The people who reach step five are exactly the people who did not
    reply to steps one to four. That conditioning is the decision, not a
    bias to remove - the fifth step would be sent to survivors."""

    def setUp(self):
        self.rows = V.step_value(an_experiment(),
                                 cohort("seven", 40, (2, 2, 5)), "seven")

    def test_the_first_step_is_unconditional(self):
        self.assertFalse(self.rows[0]["conditional"])
        self.assertIsNone(self.rows[0]["why_conditional"])

    def test_every_later_step_says_what_it_is_conditional_on(self):
        for row in self.rows[1:]:
            self.assertTrue(row["conditional"])
            self.assertIn("did not reply", row["why_conditional"])


class AnEmptyColumnIsNotEvidenceOfNothing(unittest.TestCase):
    """Zero replies after step six means the step earns nothing, or that
    nine people reached it. Those are not the same finding."""

    def test_a_step_with_enough_reach_and_no_replies_says_so(self):
        rows = V.step_value(an_experiment(), cohort("seven", 40, (2,)),
                            "seven")
        self.assertEqual(rows[5]["verdict"], V.NO_EVIDENCE)
        self.assertGreaterEqual(rows[5]["reached"], 30)

    def test_a_step_too_few_reached_says_that_instead(self):
        rows = V.step_value(an_experiment(), cohort("seven", 9, (2,)),
                            "seven")
        self.assertEqual(rows[5]["verdict"], V.TOO_FEW)

    def test_a_step_with_a_reply_pays_however_thin(self):
        """One reply is evidence that replies arrive there. It is not
        evidence of a rate, which is what the interval is for."""
        rows = V.step_value(an_experiment(), cohort("seven", 9, (6,)),
                            "seven")
        self.assertEqual(rows[5]["verdict"], V.PAYS)

    def test_the_threshold_is_configurable(self):
        rows = V.step_value(an_experiment(), cohort("seven", 9, (2,)),
                            "seven", config={"cadence_value":
                                             {"minimum_reached": 5}})
        self.assertEqual(rows[5]["verdict"], V.NO_EVIDENCE)


class WhereTheSequenceStopsPaying(unittest.TestCase):

    def settles(self, recs, arm="seven"):
        return V.curve(an_experiment(), recs, arm)

    def test_it_names_the_last_step_that_earns_anything(self):
        """40 people reach all seven; replies arrive after steps 1, 2 and 3
        and never after that."""
        found = self.settles(cohort("seven", 40, (3, 2, 2, 1)))
        self.assertEqual(found["settles_at"], 3)
        self.assertEqual(found["last_paying_step"], 3)

    def test_it_names_the_steps_that_earned_nothing(self):
        found = self.settles(cohort("seven", 40, (3, 2, 2, 1)))
        self.assertEqual(found["steps_after_settling"],
                         ["s4", "s5", "s6", "s7"])

    def test_one_thin_step_afterwards_and_there_is_no_answer(self):
        """A column that is empty because nobody got there is not a column
        that earned nothing, and one of those anywhere after the candidate
        settling point makes the whole finding unavailable."""
        recs = cohort("seven", 40, (3, 2, 2, 1))
        # Only nine of them ever reach step six.
        for rec in recs[9:]:
            rec["events"] = [e for e in rec["events"]
                             if e.get("step") not in ("s6", "s7")]
        found = self.settles(recs)
        self.assertIsNone(found["settles_at"])
        self.assertIn("too few", found["why"])

    def test_replies_still_arriving_at_the_last_step_is_not_settling(self):
        found = self.settles(cohort("seven", 40, (7, 3, 2)))
        self.assertIsNone(found["settles_at"])
        self.assertIn("still arriving", found["why"])

    def test_an_arm_with_no_replies_at_all_has_no_settling_point(self):
        """Nothing arrived after any step. That is an arm that did not
        work, not a sequence that stops paying after step zero."""
        found = self.settles(cohort("seven", 40))
        self.assertIsNone(found["settles_at"])
        self.assertIn("no replies", found["why"])

    def test_it_reports_rather_than_recommends(self):
        found = self.settles(cohort("seven", 40, (3, 2, 2, 1)))
        self.assertIn("conditional", found["note"])
        self.assertNotIn("recommend", json_of(found))


class TheArmsAreMeasuredSeparately(unittest.TestCase):

    def test_compare_returns_a_curve_for_each(self):
        recs = cohort("seven", 40, (5, 2)) + cohort("four", 40, (2, 2))
        found = V.compare(an_experiment(), recs)
        self.assertEqual(sorted(found), ["four", "seven"])
        self.assertEqual(len(found["four"]["steps"]), 4)
        self.assertEqual(len(found["seven"]["steps"]), 7)

    def test_a_four_step_arm_is_never_asked_about_step_five(self):
        recs = cohort("four", 40, (2,))
        rows = V.step_value(an_experiment(), recs, "four")
        self.assertEqual([row["index"] for row in rows], [1, 2, 3, 4])

    def test_positive_only_narrows_what_counts(self):
        recs = (cohort("seven", 20, (2,), positive=True, prefix="p")
                + cohort("seven", 20, (3,), prefix="n"))
        every = V.step_value(an_experiment(), recs, "seven")
        good = V.step_value(an_experiment(), recs, "seven",
                            positive_only=True)
        self.assertEqual(sum(r["replies"] for r in every), 2)
        self.assertEqual(sum(r["replies"] for r in good), 1)


class ItCountsPeopleAndNotMessages(unittest.TestCase):

    def test_a_second_reply_from_one_person_is_not_a_second_success(self):
        recs = cohort("seven", 40, (2,))
        # recs[0] is the one who replied - `cohort` pops from the end of
        # the list, so the first record gets the first reply.
        recs[0]["events"].append({
            "type": events.REPLY_RECEIVED, "contact": "a", "channel": "email",
            "at": "2026-07-06T09:00:00+00:00"})
        rows = V.step_value(an_experiment(), recs, "seven")
        self.assertEqual(sum(row["replies"] for row in rows), 1)


def json_of(value):
    import json

    return json.dumps(value, default=str)


if __name__ == "__main__":
    unittest.main()
