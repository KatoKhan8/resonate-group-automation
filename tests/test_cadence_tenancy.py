"""A cadence experiment sees exactly the records it was handed.

Tenancy in this build is enforced where identity exists - `Repo.for_user`
scopes what a request may read, and `tests/test_web_invariants.py` holds
that. The cadence modules sit below that line: they are pure functions
over a list of records, so their tenancy is whatever their caller's was.

That is only true while they *stay* pure. A single `store.load()` inside
any of them would quietly widen every caller to the whole estate,
including a tenant-scoped one, and nothing about the call site would look
different. So the structural half of this file asserts they read no state
outside their own command line, and the behavioural half proves a report
built from one workspace's records contains nothing from another's while
both sit in the same store.
"""
import ast
import inspect
import unittest

from src import (cadencearms as arms, cadenceexposure, cadencematurity,
                 cadencereplies, cadencereport, cadencesafety, cadencevalue,
                 events)

MODULES = (arms, cadenceexposure, cadencematurity, cadencereplies,
           cadencevalue, cadencesafety, cadencereport)

LOADERS = {"store", "campaigns", "clients"}

SEVEN = [{"key": f"s{i}", "day": d, "channel": "email",
          "template": "persona_pain"}
         for i, d in enumerate((1, 3, 7, 12, 18, 25, 35), start=1)]
FOUR = SEVEN[:4]


def an_experiment():
    return arms.experiment("cad-1",
                           [arms.arm("four", "4 steps", FOUR),
                            arms.arm("seven", "7 steps", SEVEN)])


def a_record(rid, client, arm_id, confirmed=3, replied=False):
    rec = {"id": rid, "client": client, "company": rid, "events": [],
           "contacts": [{"key": "a", "name": "A", "email": f"a@{rid}.test"}],
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
    if replied:
        rec["events"].append({
            "type": events.POSITIVE_REPLY_DETECTED, "contact": "a",
            "channel": "email",
            "at": f"2026-07-{confirmed:02d}T21:00:00+00:00"})
    return rec


class TheyReadNoStateOfTheirOwn(unittest.TestCase):
    """The property that makes the caller's scope the only scope."""

    def loaders_in(self, module):
        found = []
        for node in ast.parse(inspect.getsource(module)).body:
            if not isinstance(node, ast.FunctionDef) or node.name == "main":
                continue
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr in ("load", "save")
                        and isinstance(inner.func.value, ast.Name)
                        and inner.func.value.id in LOADERS):
                    found.append(f"{node.name} -> {inner.func.value.id}"
                                 f".{inner.func.attr}")
        return found

    def test_no_cadence_module_loads_the_estate(self):
        for module in MODULES:
            self.assertEqual(self.loaders_in(module), [],
                             f"{module.__name__} reads state outside its CLI")

    def test_the_command_lines_do_load_it(self):
        """So the assertion above is about the library rather than about
        modules that happen never to touch a store."""
        loading = [m.__name__ for m in MODULES
                   if "store.load()" in inspect.getsource(m)]
        self.assertEqual(len(loading), len(MODULES))

    def test_none_of_them_writes(self):
        for module in MODULES:
            source = inspect.getsource(module)
            for banned in ("store.save", "store.log", "events.record"):
                self.assertNotIn(banned, source,
                                 f"{module.__name__} writes state")


class OneWorkspacesRecordsProduceOneWorkspacesReport(unittest.TestCase):
    """Both estates in one list, as they sit in one store. What comes back
    is a property of what was passed in."""

    def setUp(self):
        self.mine = [a_record(f"mine-{i}", "demo", "seven", replied=i < 3)
                     for i in range(10)]
        self.theirs = [a_record(f"theirs-{i}", "other", "four", replied=True)
                       for i in range(30)]

    def report(self, recs):
        return cadencereport.report(an_experiment(), recs, today="2026-09-30")

    def test_the_exposure_count_is_of_the_records_given(self):
        rows = cadenceexposure.exposures(an_experiment(), self.mine)
        self.assertEqual(len(rows), len(self.mine))

    def test_a_report_over_one_estate_does_not_see_the_other(self):
        mine = self.report(self.mine)
        seven = next(a for a in mine["arms"] if a["arm_id"] == "seven")
        four = next(a for a in mine["arms"] if a["arm_id"] == "four")
        self.assertEqual(seven["replies"]["exposed"], 10)
        self.assertEqual(four["replies"]["exposed"], 0)

    def test_and_the_other_estate_reports_its_own(self):
        theirs = self.report(self.theirs)
        four = next(a for a in theirs["arms"] if a["arm_id"] == "four")
        self.assertEqual(four["replies"]["exposed"], 30)

    def test_the_two_together_are_visibly_different_from_either(self):
        """Guarding the two above: if the modules ignored their argument
        and read everything, all three of these would agree."""
        both = self.report(self.mine + self.theirs)
        four = next(a for a in both["arms"] if a["arm_id"] == "four")
        self.assertEqual(four["replies"]["exposed"], 30)
        seven = next(a for a in both["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["replies"]["exposed"], 10)

    def test_the_safety_numbers_follow_the_same_list(self):
        found = cadencesafety.by_arm(an_experiment(), self.mine)
        self.assertEqual(found["four"]["exposed"], 0)
        self.assertEqual(found["seven"]["exposed"], 10)

    def test_so_do_the_step_values(self):
        rows = cadencevalue.step_value(an_experiment(), self.mine, "seven")
        self.assertEqual(rows[0]["reached"], 10)

    def test_and_maturity(self):
        found = cadencematurity.maturity(an_experiment(), self.mine,
                                         today="2026-09-30")
        seven = next(a for a in found["arms"] if a["arm_id"] == "seven")
        self.assertEqual(seven["assigned"], 10)

    def test_and_reply_attribution(self):
        found = cadencereplies.by_arm(an_experiment(), self.mine)
        self.assertEqual(found["seven"]["exposed"], 10)
        self.assertEqual(found["four"]["exposed"], 0)


if __name__ == "__main__":
    unittest.main()
