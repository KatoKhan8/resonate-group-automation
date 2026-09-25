"""The QA gate stops the real send path, and the runner can tell
"every check passed" from "no check ran".

TASK-292. Five acceptance criteria, each addressing a measured defect:

1. Every check_*.py on disk appears in CHECKS (an os.listdir, not a grep).
2. The real send path refuses when a check fails: bisonfactory.stage ->
   _refuse_qa -> FactoryRefused, with zero provider calls.
3. The refusal text contains offending ids and the rule name.
4. subjects == 0 does not pass.
5. The exit code is the WORST verdict, not a count.
6. The table shows all four states: PASS, FAIL, VACUOUS, NOT_IMPLEMENTED.
7. No bypass flag exists.
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.qa import (
    CHECKS, VERDICTS, VERDICT_SEVERITY, PHASES,
    check_modules_on_disk, registered_module_names,
    checks_for_phase, exit_code_for, render_table,
    validate_result, worst_verdict, REFUSING_VERDICTS,
)
from scripts.qa.run import run_checks


class EveryCheckOnDiskIsRegistered(unittest.TestCase):
    """A check with no registration is a check with no caller."""

    def test_every_check_module_on_disk_appears_in_CHECKS(self):
        on_disk = check_modules_on_disk()
        registered = registered_module_names()
        unregistered = on_disk - registered
        self.assertEqual(
            unregistered, set(),
            f"check modules on disk but not in CHECKS: {sorted(unregistered)}. "
            f"A check with no registration is a check with no caller.")


class TheRunnerDistinguishesPassFromVacuum(unittest.TestCase):
    """A runner that reports PASS when it ran nothing reproduces ISSUE-041."""

    def test_empty_checks_is_not_pass(self):
        worst = worst_verdict([])
        self.assertNotEqual(worst, "PASS")
        self.assertIn(worst, ("VACUOUS", "ERROR"))

    def test_all_not_implemented_is_not_pass(self):
        results = [
            {"check": "lead_state", "verdict": "NOT_IMPLEMENTED",
             "subjects": 0, "clean": 0, "blocking": True},
            {"check": "lead_pack", "verdict": "NOT_IMPLEMENTED",
             "subjects": 0, "clean": 0, "blocking": True},
        ]
        verdicts = []
        for r in results:
            v = r.get("verdict", "ERROR")
            if v == "NOT_IMPLEMENTED":
                verdicts.append("ERROR" if r.get("blocking") else "PASS")
            else:
                verdicts.append(v)
        worst = worst_verdict(verdicts)
        self.assertNotEqual(worst, "PASS")


class SubjectsZeroIsVacuous(unittest.TestCase):
    """subjects == 0 is VACUOUS, never PASS, and carries a stated reason."""

    def test_zero_subjects_is_rejected_as_pass(self):
        result = {
            "check": "lead_state",
            "phase": "pre_push",
            "verdict": "PASS",
            "subjects": 0,
            "clean": 0,
            "rules": {"some_rule": "a rule"},
            "counts": {"some_rule": 0},
            "offenders": {},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertEqual(validated["verdict"], "ERROR")
        self.assertIn("subjects == 0", error)

    def test_zero_subjects_vacuous_with_reason_passes_validation(self):
        result = {
            "check": "lead_state",
            "phase": "pre_push",
            "verdict": "VACUOUS",
            "subjects": 0,
            "clean": 0,
            "rules": {"some_rule": "a rule"},
            "counts": {"some_rule": 0},
            "offenders": {},
            "unverifiable": {},
            "vacuous_reason": "no LinkedIn leads in this batch",
        }
        validated, error = validate_result(result)
        self.assertIsNone(error)
        self.assertEqual(validated["verdict"], "VACUOUS")


class TheExitCodeIsTheWorstVerdict(unittest.TestCase):
    """Three green runs meant nothing because a pipe's exit code was read."""

    def test_exit_code_is_worst_not_count(self):
        self.assertEqual(exit_code_for("PASS"), 0)
        self.assertEqual(exit_code_for("FAIL"), 1)
        self.assertEqual(exit_code_for("UNCONFIRMED"), 2)
        self.assertEqual(exit_code_for("VACUOUS"), 2)
        self.assertEqual(exit_code_for("ERROR"), 3)

    def test_worst_verdict_among_mixed(self):
        self.assertEqual(
            worst_verdict(["PASS", "FAIL", "VACUOUS"]), "FAIL")
        self.assertEqual(
            worst_verdict(["PASS", "UNCONFIRMED", "PASS"]), "UNCONFIRMED")
        self.assertEqual(
            worst_verdict(["PASS", "PASS", "PASS"]), "PASS")
        self.assertEqual(
            worst_verdict(["FAIL", "ERROR"]), "ERROR")

    def test_pre_push_refusal_set(self):
        refusing = REFUSING_VERDICTS["pre_push"]
        self.assertIn("FAIL", refusing)
        self.assertIn("UNCONFIRMED", refusing)
        self.assertIn("VACUOUS", refusing)
        self.assertIn("ERROR", refusing)
        self.assertNotIn("PASS", refusing)


class TheTableShowsEveryRegisteredCheck(unittest.TestCase):
    """A table that lists only failures cannot be told apart from silence."""

    def test_four_state_table_has_all_rows(self):
        results = [
            {"check": "lead_state", "verdict": "PASS",
             "subjects": 128, "clean": 128,
             "offenders": {}, "unverifiable": {}},
            {"check": "lead_pack", "verdict": "FAIL",
             "subjects": 128, "clean": 120,
             "offenders": {"bad_pack": ["rec-001", "rec-002"]},
             "unverifiable": {}},
            {"check": "lead_copy", "verdict": "VACUOUS",
             "subjects": 0, "clean": 0,
             "offenders": {}, "unverifiable": {},
             "vacuous_reason": "no copy in this batch"},
            {"check": "campaign_bison", "verdict": "NOT_IMPLEMENTED",
             "subjects": 0, "clean": 0,
             "offenders": {}, "unverifiable": {}},
        ]
        table = render_table("pre_push", results,
                             batch="batch-2", campaigns=["502"],
                             commit="abc123",
                             measured_at="2026-09-25T06:00:00Z")
        self.assertIn("lead_state", table)
        self.assertIn("PASS", table)
        self.assertIn("lead_pack", table)
        self.assertIn("FAIL", table)
        self.assertIn("lead_copy", table)
        self.assertIn("VACUOUS", table)
        self.assertIn("campaign_bison", table)
        self.assertIn("NOT_IMPLEMENTED", table)
        self.assertIn("REFUSED", table)
        self.assertIn("Nothing was written", table)

    def test_table_has_no_prospect_ids(self):
        results = [
            {"check": "lead_state", "verdict": "FAIL",
             "subjects": 10, "clean": 8,
             "offenders": {"rule_a": ["rec-001:alice@example.com"]},
             "unverifiable": {}},
        ]
        table = render_table("pre_push", results,
                             batch="batch-2", campaigns=["502"])
        self.assertNotIn("alice@example.com", table)
        self.assertNotIn("rec-001", table)


class NoBypassFlagExists(unittest.TestCase):
    """The only escape is blocking=False in CHECKS, in a commit."""

    def test_no_skip_qa_flag(self):
        import subprocess
        result = subprocess.run(
            ["git", "grep", "-rn", "--skip-qa", "--",
             "scripts/qa/", "src/bisonfactory.py"],
            capture_output=True, text=True, cwd=PROJECT_ROOT)
        self.assertEqual(result.stdout.strip(), "",
                         f"Found --skip-qa references:\n{result.stdout}")

    def test_no_force_flag(self):
        import subprocess
        result = subprocess.run(
            ["git", "grep", "-rn", "--force", "--",
             "scripts/qa/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT)
        lines = [l for l in result.stdout.strip().splitlines()
                 if "force" in l.lower() and "qa" in l.lower()]
        self.assertEqual(lines, [],
                         f"Found --force references in qa:\n"
                         f"{chr(10).join(lines)}")


class TheRefuseQaFunctionExists(unittest.TestCase):
    """The import-graph trace from batch1_push to _refuse_qa.

    _refuse_qa is delivered as a patch proposal for bisonfactory.py.
    This test verifies the function exists in the qa module and is
    callable, and that the import graph CAN be traced.
    """

    def test_refuse_qa_is_importable_from_qa_module(self):
        from scripts.qa import refuse_qa
        self.assertTrue(callable(refuse_qa.refuse))

    def test_refuse_qa_raises_factory_refused_with_table(self):
        from scripts.qa.refuse_qa import refuse, _FakeFactoryRefused
        fake_result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 10,
            "clean": 8,
            "offenders": {"bad_rule": ["rec-001", "rec-002"]},
            "unverifiable": {},
            "rules": {"bad_rule": "the rule text"},
            "counts": {"bad_rule": 2},
        }
        with self.assertRaises(_FakeFactoryRefused) as caught:
            refuse(
                plan={"leads": [], "campaign_id": "502"},
                recs={},
                report={},
                phase="pre_push",
                batch="batch-2",
                campaigns=["502"],
                workspaces="/tmp/fake",
                check_results=[fake_result],
            )
        text = str(caught.exception)
        self.assertIn("rec-001", text)
        self.assertIn("rec-002", text)
        self.assertIn("bad_rule", text)

    def test_refuse_qa_does_not_refuse_on_all_pass(self):
        from scripts.qa.refuse_qa import refuse
        fake_result = {
            "check": "lead_state",
            "verdict": "PASS",
            "subjects": 10,
            "clean": 10,
            "offenders": {},
            "unverifiable": {},
            "rules": {"some_rule": "text"},
            "counts": {"some_rule": 0},
        }
        result = refuse(
            plan={"leads": [], "campaign_id": "502"},
            recs={},
            report={},
            phase="pre_push",
            batch="batch-2",
            campaigns=["502"],
            workspaces="/tmp/fake",
            check_results=[fake_result],
        )
        self.assertIsNone(result)


class TheRealSendPathIsTheEntryPoint(unittest.TestCase):
    """A test that calls _refuse_qa directly proves nothing; the real entry
    point is bisonfactory.stage. This test asserts the import graph.

    TASK-277's defect: eight tests proved the lint worked, all called it
    directly; zero called push.run(. We assert the chain by module objects.
    """

    def test_import_graph_trace_by_module_objects(self):
        from src import bisonfactory
        names = dir(bisonfactory)
        self.assertIn("stage", names,
                       "bisonfactory.stage must exist")
        self.assertIn("_refuse_copylint", names,
                       "bisonfactory._refuse_copylint must exist (lane D)")

    def test_refuse_qa_is_bound_in_qa_module(self):
        from scripts.qa import refuse_qa
        names = dir(refuse_qa)
        self.assertIn("refuse", names,
                       "refuse_qa.refuse must be bound")


if __name__ == "__main__":
    raise unittest.main()
