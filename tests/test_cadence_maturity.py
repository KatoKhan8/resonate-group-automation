"""Whether a cadence comparison has been given time to be a comparison.

A four-step arm finishes on day twelve. A seven-step arm finishes on day
thirty-five. Compare them on day fifteen and the four-step arm has had
every chance it will ever get while the seven-step arm has had two thirds
of one — and the four-step arm wins on a difference that is entirely an
artefact of when somebody looked.

That is the largest single way a cadence experiment produces a confident
wrong answer, and it gets worse the bigger the difference between the arms,
which is exactly the difference the experiment was built to measure.
"""
import unittest

from src import (cadencearms as arms, cadenceexposure as exposure,
                 cadencematurity as maturity, events)

SEVEN = [{"key": f"s{i}", "day": d, "channel": "email",
          "template": "persona_pain"}
         for i, d in enumerate((1, 3, 7, 12, 18, 25, 35), start=1)]
FOUR = SEVEN[:4]

TODAY = "2026-09-01"


def an_experiment():
    return arms.experiment("cad-1",
                           [arms.arm("four", "4 steps", FOUR),
                            arms.arm("seven", "7 steps", SEVEN)])


def a_record(rid, arm_id, assigned_at, confirmed=0, stopped=None):
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
            "at": f"2026-0{i + 1}-01T09:00:00+00:00", "sender_id": "mark"})
    if stopped == "reply":
        rec["events"].append({
            "type": events.POSITIVE_REPLY_DETECTED, "contact": "a",
            "channel": "email", "at": "2026-08-20T09:00:00+00:00"})
        rec["paused"] = {"since": "2026-08-20", "reason": "reply_received"}
    return rec


def look(recs, today=TODAY):
    return maturity.maturity(an_experiment(), recs, today=today)


class TheDayFifteenTrap(unittest.TestCase):
    """Both arms assigned on the same day, read fifteen days later."""

    def setUp(self):
        assigned = "2026-08-17T09:00:00+00:00"       # 15 days before TODAY
        self.recs = ([a_record(f"f{i}", "four", assigned) for i in range(10)]
                     + [a_record(f"s{i}", "seven", assigned)
                        for i in range(10)])
        self.found = look(self.recs)

    def test_the_short_arm_has_had_its_full_chance(self):
        four = next(a for a in self.found["arms"] if a["arm_id"] == "four")
        self.assertEqual(four["level"], maturity.MATURE)

    def test_the_long_arm_has_not(self):
        seven = next(a for a in self.found["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["level"], maturity.IMMATURE)

    def test_the_comparison_is_refused(self):
        """The whole point. One mature arm and one immature arm is not a
        comparison, however good the numbers look."""
        self.assertFalse(self.found["comparable"])
        self.assertEqual(self.found["level"], maturity.IMMATURE)

    def test_it_names_the_arm_holding_it_back(self):
        self.assertEqual(self.found["held_back_by"], ["seven"])

    def test_it_says_how_much_longer(self):
        seven = next(a for a in self.found["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["days_until_mature"], 35 + 3 - 15)

    def test_it_explains_the_trap_rather_than_only_reporting_it(self):
        self.assertIn("when somebody looked", self.found["note"])


class TimeIsCountedFromEachAssignment(unittest.TestCase):
    """An experiment started six weeks ago may contain a contact assigned
    yesterday. Measuring from the experiment's start would call that cohort
    mature."""

    def test_a_recently_assigned_contact_holds_its_arm_back(self):
        old = "2026-06-01T09:00:00+00:00"
        recs = [a_record(f"f{i}", "four", old) for i in range(9)]
        recs.append(a_record("f-new", "four", "2026-08-31T09:00:00+00:00"))
        four = next(a for a in look(recs)["arms"] if a["arm_id"] == "four")
        self.assertEqual(four["level"], maturity.PARTIALLY_MATURE)
        self.assertEqual(four["had_full_chance"], 9)
        self.assertEqual(four["assigned"], 10)

    def test_everybody_assigned_long_enough_is_mature(self):
        old = "2026-06-01T09:00:00+00:00"
        recs = ([a_record(f"f{i}", "four", old) for i in range(5)]
                + [a_record(f"s{i}", "seven", old) for i in range(5)])
        found = look(recs)
        self.assertEqual(found["level"], maturity.MATURE)
        self.assertTrue(found["comparable"])

    def test_one_finished_contact_does_not_make_a_cohort_readable(self):
        """Below the partial threshold an arm stays immature however long
        one of its contacts has been in it."""
        old = "2026-06-01T09:00:00+00:00"
        recent = "2026-08-31T09:00:00+00:00"
        recs = [a_record("f-old", "four", old)]
        recs += [a_record(f"f{i}", "four", recent) for i in range(30)]
        four = next(a for a in look(recs)["arms"] if a["arm_id"] == "four")
        self.assertEqual(four["level"], maturity.IMMATURE)

    def test_an_arm_nobody_is_in_is_immature_rather_than_mature(self):
        """Vacuously mature would let an empty arm certify a comparison."""
        recs = [a_record(f"f{i}", "four", "2026-06-01T09:00:00+00:00")
                for i in range(5)]
        seven = next(a for a in look(recs)["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["level"], maturity.IMMATURE)
        self.assertEqual(seven["assigned"], 0)
        self.assertFalse(look(recs)["comparable"])


class ASequenceThatEndedIsFinished(unittest.TestCase):
    """They are not waiting for step seven. Step seven is never coming, and
    holding the arm immature on their account would keep it immature for
    ever."""

    def test_a_contact_who_replied_early_is_mature(self):
        rec = a_record("s1", "seven", "2026-08-30T09:00:00+00:00",
                       confirmed=3, stopped="reply")
        found = maturity.contact_maturity(an_experiment(), rec,
                                          rec["contacts"][0], today=TODAY)
        self.assertTrue(found["finished"])
        self.assertTrue(found["had_full_chance"])
        self.assertIn("ended", found["why"])

    def test_a_completed_arm_is_mature_even_if_it_finished_early(self):
        rec = a_record("f1", "four", "2026-08-30T09:00:00+00:00", confirmed=4)
        found = maturity.contact_maturity(an_experiment(), rec,
                                          rec["contacts"][0], today=TODAY)
        self.assertTrue(found["had_full_chance"])

    def test_a_contact_still_running_is_not(self):
        rec = a_record("s1", "seven", "2026-08-30T09:00:00+00:00", confirmed=2)
        found = maturity.contact_maturity(an_experiment(), rec,
                                          rec["contacts"][0], today=TODAY)
        self.assertFalse(found["finished"])
        self.assertFalse(found["had_full_chance"])

    def test_an_arm_where_everybody_stopped_early_is_mature(self):
        recs = [a_record(f"s{i}", "seven", "2026-08-30T09:00:00+00:00",
                         confirmed=3, stopped="reply") for i in range(5)]
        recs += [a_record(f"f{i}", "four", "2026-06-01T09:00:00+00:00")
                 for i in range(5)]
        found = look(recs)
        self.assertTrue(found["comparable"])

    def test_an_unassigned_contact_is_not_an_immature_one(self):
        """Counting them would hold every arm immature for as long as the
        audience keeps growing."""
        rec = {"id": "x", "client": "demo", "events": [],
               "contacts": [{"key": "a", "email": "a@x.test"}]}
        self.assertIsNone(maturity.contact_maturity(
            an_experiment(), rec, rec["contacts"][0], today=TODAY))


class TheArmsSpanIsItsLastStepPlusSettling(unittest.TestCase):

    def test_the_span_is_the_last_step(self):
        self.assertEqual(maturity.arm_span({"steps": SEVEN}), 35)
        self.assertEqual(maturity.arm_span({"steps": FOUR}), 12)

    def test_an_empty_arm_spans_nothing(self):
        self.assertEqual(maturity.arm_span({"steps": []}), 0)
        self.assertEqual(maturity.arm_span(None), 0)

    def test_settling_days_are_added(self):
        """A step scheduled for day 35 does not arrive at 00:00 on day 35:
        sending is paced, windows are respected, and a provider takes its
        own time."""
        found = maturity.arm_maturity(an_experiment(), "seven", [],
                                      today=TODAY)
        self.assertEqual(found["span_days"],
                         35 + maturity.DEFAULTS["settling_days"])

    def test_the_settling_period_is_configurable(self):
        found = maturity.arm_maturity(
            an_experiment(), "seven", [], today=TODAY,
            config={"cadence_maturity": {"settling_days": 10}})
        self.assertEqual(found["span_days"], 45)


class ItJudgesTimeAndNotOutcomes(unittest.TestCase):

    def test_it_does_not_reach_the_evaluator(self):
        """Maturity says whether a comparison may mean anything yet;
        `variants.evaluate` says what it means. An evaluator that also
        decided maturity could talk itself into a verdict.

        Asserted on the import graph rather than by searching the source
        for words - a test that reads prose fails when somebody writes
        some, which has happened repeatedly in this repository.

        It does read *whether a sequence ended*, through
        `cadenceexposure`, and that depends on replies. Ending is a fact
        about time, not an outcome: somebody who replied at step three is
        finished with the arm whatever the reply said.
        """
        import ast
        import inspect

        imported = set()
        for node in ast.walk(ast.parse(inspect.getsource(maturity))):
            if isinstance(node, ast.ImportFrom):
                imported.update(a.name.split(" as ")[0] for a in node.names)
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
        self.assertNotIn("variants", imported)
        self.assertNotIn("learning", imported)

    def test_ending_is_read_as_time_rather_than_as_an_outcome(self):
        """A negative reply and a positive one both finish the arm. If
        maturity treated them differently it would be judging results."""
        positive = a_record("s1", "seven", "2026-08-30T09:00:00+00:00",
                            confirmed=3, stopped="reply")
        negative = a_record("s2", "seven", "2026-08-30T09:00:00+00:00",
                            confirmed=3)
        negative["contacts"][0]["unsubscribed"] = True

        for rec in (positive, negative):
            found = maturity.contact_maturity(an_experiment(), rec,
                                              rec["contacts"][0], today=TODAY)
            self.assertTrue(found["had_full_chance"], rec["id"])

    def test_it_writes_no_state(self):
        import inspect

        source = inspect.getsource(maturity)
        for banned in ("store.save", "store.log", "events.record"):
            self.assertNotIn(banned, source, banned)

    def test_it_does_not_mutate_the_records_it_reads(self):
        import copy

        recs = [a_record("f1", "four", "2026-06-01T09:00:00+00:00",
                         confirmed=2)]
        before = copy.deepcopy(recs)
        look(recs)
        self.assertEqual(recs, before)


if __name__ == "__main__":
    unittest.main()
