"""What a cadence cost the people who received it.

A seven-step arm that earns two points more replies and three times the
unsubscribes is not better; it is a different trade, and an unsubscribe
does not convert into a reply at any exchange rate. The tests that matter
most here are the ones about what this module refuses to do: net the two,
and name a safer arm on three unsubscribes against one.
"""
import unittest

from src import cadencearms as arms, cadencesafety as S, events

SEVEN = [{"key": f"s{i}", "day": d, "channel": "email",
          "template": "persona_pain"}
         for i, d in enumerate((1, 3, 7, 12, 18, 25, 35), start=1)]
FOUR = SEVEN[:4]


def an_experiment():
    return arms.experiment("cad-1",
                           [arms.arm("four", "4 steps", FOUR),
                            arms.arm("seven", "7 steps", SEVEN)])


def a_record(rid, arm_id, confirmed, harm=None, after=None, classification=None):
    """`confirmed` steps delivered, then optionally something went wrong.

    `harm` is an event type; `after` is the step position it followed.
    """
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
    if harm:
        entry = {"type": harm, "contact": "a", "channel": "email",
                 "at": f"2026-07-{(after or confirmed):02d}T21:00:00+00:00"}
        if classification:
            entry["classification"] = classification
        rec["events"].append(entry)
    return rec


def cohort(arm_id, people, prefix, harm=None, after=None, confirmed=None,
           classification=None, harmed=0):
    steps = confirmed if confirmed is not None else len(
        SEVEN if arm_id == "seven" else FOUR)
    out = []
    for index in range(people):
        out.append(a_record(
            f"{prefix}-{index}", arm_id, steps,
            harm=harm if index < harmed else None, after=after,
            classification=classification))
    return out


class OnePersonIsCountedOnce(unittest.TestCase):
    """Somebody who replies negatively and then unsubscribes is one person
    harmed. Counting events would make the same person two casualties."""

    def test_two_harms_from_one_contact_are_one(self):
        rec = a_record("r1", "seven", 3, harm=events.CONTACT_SUPPRESSED,
                       after=3)
        rec["events"].append({
            "type": events.REPLY_RECEIVED, "contact": "a", "channel": "email",
            "classification": "negative", "at": "2026-07-03T20:00:00+00:00"})
        recs = [rec] + cohort("seven", 39, "s", confirmed=3)
        found = S.by_arm(an_experiment(), recs)["seven"]
        self.assertEqual(found["harmed"], 1)

    def test_but_each_kind_is_still_named(self):
        """The rate is about people; the breakdown is about what happened,
        and an operator needs both."""
        rec = a_record("r1", "seven", 3, harm=events.CONTACT_SUPPRESSED,
                       after=3)
        rec["events"].append({
            "type": events.REPLY_RECEIVED, "contact": "a", "channel": "email",
            "classification": "negative", "at": "2026-07-03T20:00:00+00:00"})
        found = S.by_arm(an_experiment(), [rec])["seven"]
        self.assertEqual(found["by_kind"][S.UNSUBSCRIBED], 1)
        self.assertEqual(found["by_kind"][S.NEGATIVE_REPLY], 1)


class ContextIsNotHarm(unittest.TestCase):
    """A bounce is a fact about an address, a hold is a pause somebody
    applied, a drop is an operator's decision. None of them is a recipient
    telling us we went too far, and mixing them in would let list quality
    masquerade as fatigue."""

    def rate_with(self, kind):
        recs = cohort("seven", 40, "s", harm=kind, after=3, confirmed=3,
                      harmed=8)
        return S.by_arm(an_experiment(), recs)["seven"]

    def test_a_bounce_is_not_in_the_harm_rate(self):
        found = self.rate_with(events.EMAIL_BOUNCED)
        self.assertEqual(found["harmed"], 0)
        self.assertEqual(found["context"][S.BOUNCED], 8)

    def test_a_hold_is_not_in_the_harm_rate(self):
        found = self.rate_with(events.CONTACT_HELD)
        self.assertEqual(found["harmed"], 0)
        self.assertEqual(found["context"][S.HELD], 8)

    def test_a_drop_is_not_in_the_harm_rate(self):
        found = self.rate_with(events.RECORD_DROPPED)
        self.assertEqual(found["harmed"], 0)
        self.assertEqual(found["context"][S.DROPPED], 8)

    def test_an_unsubscribe_is(self):
        """So the three above are exclusions rather than a broken counter."""
        found = self.rate_with(events.CONTACT_SUPPRESSED)
        self.assertEqual(found["harmed"], 8)
        self.assertAlmostEqual(found["rate"], 8 / 40)


class WhereItHappened(unittest.TestCase):
    """"Half the unsubscribes arrive after step five" decides whether step
    five should exist. "The seven-step arm has more unsubscribes" does not,
    because it has more steps for them to arrive after."""

    def test_it_places_each_one_after_a_step(self):
        recs = cohort("seven", 40, "s", harm=events.CONTACT_SUPPRESSED,
                      after=5, confirmed=5, harmed=6)
        found = S.by_arm(an_experiment(), recs)["seven"]
        self.assertEqual(found["after_step"], {"s5": 6})

    def test_it_uses_the_last_step_before_and_not_the_last_overall(self):
        """The same rule as a reply, through the same function - two copies
        would be two chances to disagree about which step somebody was
        on."""
        rec = a_record("r1", "seven", 6, harm=events.CONTACT_SUPPRESSED,
                       after=3)
        found = S.contact_outcomes(an_experiment(), rec, rec["contacts"][0])
        self.assertEqual(found[0]["after_step"], "s3")

    def test_an_unsubscribe_before_any_touch_is_unattributed(self):
        rec = a_record("r1", "seven", 3)
        rec["events"].append({"type": events.CONTACT_SUPPRESSED,
                              "contact": "a",
                              "at": "2026-06-15T09:00:00+00:00"})
        found = S.contact_outcomes(an_experiment(), rec, rec["contacts"][0])
        self.assertFalse(found[0]["attributed"])

    def test_a_contact_outside_the_experiment_reports_nothing(self):
        rec = {"id": "x", "client": "demo", "events": [],
               "contacts": [{"key": "a", "email": "a@x.test"}]}
        self.assertIsNone(
            S.contact_outcomes(an_experiment(), rec, rec["contacts"][0]))

    def test_a_record_level_suppression_counts_for_its_contacts(self):
        """It has no contact on it and applies to everybody at the
        company."""
        rec = a_record("r1", "seven", 3)
        rec["events"].append({"type": events.ACCOUNT_SUPPRESSED,
                              "at": "2026-07-03T21:00:00+00:00"})
        found = S.contact_outcomes(an_experiment(), rec, rec["contacts"][0])
        self.assertEqual([row["kind"] for row in found],
                         [S.ACCOUNT_SUPPRESSED])


class TheDenominatorIsWhoStarted(unittest.TestCase):

    def test_somebody_never_touched_is_not_in_it(self):
        recs = (cohort("seven", 20, "s", harm=events.CONTACT_SUPPRESSED,
                       after=3, confirmed=3, harmed=4)
                + cohort("seven", 10, "n", confirmed=0))
        found = S.by_arm(an_experiment(), recs)["seven"]
        self.assertEqual(found["exposed"], 20)
        self.assertAlmostEqual(found["rate"], 4 / 20)

    def test_an_arm_nobody_started_has_no_rate_rather_than_zero(self):
        recs = cohort("seven", 10, "s", confirmed=3)
        self.assertIsNone(S.by_arm(an_experiment(), recs)["four"]["rate"])


class ItRefusesToNameASaferArmOnNoise(unittest.TestCase):
    """Three unsubscribes against one, on forty people each, is not
    evidence - and a comparison that named a winner there would license
    lengthening a cadence on nothing."""

    def compare(self, seven_harmed, four_harmed, people=40):
        recs = (cohort("seven", people, "s",
                       harm=events.CONTACT_SUPPRESSED, after=3, confirmed=3,
                       harmed=seven_harmed)
                + cohort("four", people, "f",
                         harm=events.CONTACT_SUPPRESSED, after=3, confirmed=3,
                         harmed=four_harmed))
        return S.compare(an_experiment(), recs)

    def test_a_small_difference_names_nobody(self):
        found = self.compare(3, 1)
        self.assertIsNone(found["costs_more"])
        # And the intervals genuinely do overlap - otherwise the refusal
        # above would be an accident of some other check.
        seven, four = found["arms"]["seven"], found["arms"]["four"]
        self.assertLess(four["low"], seven["high"])
        self.assertLess(seven["low"], four["high"])

    def test_a_large_one_does(self):
        """So the refusal above is a refusal and not an inability."""
        found = self.compare(30, 0)
        self.assertEqual(found["costs_more"], ["seven"])

    def test_an_arm_nobody_started_is_left_out_of_the_comparison(self):
        recs = cohort("seven", 40, "s", harm=events.CONTACT_SUPPRESSED,
                      after=3, confirmed=3, harmed=4)
        found = S.compare(an_experiment(), recs)
        self.assertEqual(found["measured"], ["seven"])
        self.assertIsNone(found["costs_more"])


class ItWillNotNetTheCostAgainstTheReturn(unittest.TestCase):
    """The single most useful-looking output this codebase could produce
    and the one most likely to burn a sending domain."""

    def test_it_does_not_read_replies_at_all(self):
        import ast
        import inspect

        imported = set()
        for node in ast.walk(ast.parse(inspect.getsource(S))):
            if isinstance(node, ast.ImportFrom):
                imported.update(a.name for a in node.names)
        self.assertNotIn("cadencevalue", imported)

    def test_no_field_combines_a_reply_with_a_harm(self):
        recs = cohort("seven", 40, "s", harm=events.CONTACT_SUPPRESSED,
                      after=3, confirmed=3, harmed=4)
        found = S.compare(an_experiment(), recs)
        for key in ("net", "score", "efficiency", "ratio", "value"):
            self.assertNotIn(key, found)
            self.assertNotIn(key, found["arms"]["seven"])

    def test_it_says_so_where_somebody_would_read_it(self):
        recs = cohort("seven", 40, "s", confirmed=3)
        self.assertIn("exchange rate",
                      S.compare(an_experiment(), recs)["note"])

    def test_it_writes_no_state(self):
        import inspect

        source = inspect.getsource(S)
        for banned in ("store.save", "store.log", "events.record"):
            self.assertNotIn(banned, source, banned)


if __name__ == "__main__":
    unittest.main()
