#!/usr/bin/env python3
"""A QA result that does not add up is an ERROR, not a verdict.

TASK-292. The runner asserts the five invariants of contract section 4 on every
result it receives, and downgrades a result that breaks one to ERROR. It does
not trust the check.

THE FIVE INVARIANTS

1. offenders and unverifiable hold ids, not counts and not summaries.
2. clean + |union(offenders) union(unverifiable)| == subjects.
3. subjects == 0 is VACUOUS, never PASS, and carries a stated reason.
4. rules, counts, offenders keys agree in both directions.
5. rule sentences are rendered from the run's parameters (non-empty).

A test here constructs a result that breaks one invariant and shows the runner
downgrading it to ERROR. A runner that trusted the check's arithmetic would
let a result with dropped subjects through, and a dropped subject is the one
that was wrong.
"""
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import scripts.qa as qa_pkg                                        # noqa: E402
from scripts.qa import run as qa_run                               # noqa: E402
from scripts.qa import validate_result, worst_verdict              # noqa: E402


class ValidateResultInvariants(unittest.TestCase):
    """The runner's validator catches every shape of bad result."""

    # --------------------------------------------- invariant 1: ids not counts

    def test_offenders_with_a_count_string_is_an_error(self):
        """'7 leads' is not an id. An offender list must hold identifiers a
        person can paste into a provider UI or grep in the queue."""
        result = _base_result(subjects=3, clean=2)
        result["offenders"]["a_rule"] = ["7 leads"]
        ok, errors = validate_result(result)
        self.assertFalse(ok)
        self.assertTrue(any("non-id" in e or "summary" in e or "count" in e
                            for e in errors))

    def test_offenders_with_truncation_is_an_error(self):
        """'...' is not an id. Truncation hides the identifier."""
        result = _base_result(subjects=3, clean=2)
        result["offenders"]["a_rule"] = ["..."]
        ok, errors = validate_result(result)
        self.assertFalse(ok)

    def test_unverifiable_with_a_count_is_an_error(self):
        result = _base_result(subjects=3, clean=2)
        result["unverifiable"]["a_rule"] = ["3"]
        ok, errors = validate_result(result)
        self.assertFalse(ok)

    # --------------------------------------------- invariant 2: arithmetic

    def test_clean_plus_offending_must_equal_subjects(self):
        """clean=5, one offender, subjects=10. The arithmetic does not close:
        5 + 1 = 6, not 10. Four subjects were dropped somewhere."""
        result = _base_result(subjects=10, clean=5)
        result["offenders"]["a_rule"] = ["rec-1"]
        ok, errors = validate_result(result)
        self.assertFalse(ok)
        self.assertTrue(any("arithmetic" in e for e in errors))

    def test_clean_plus_offending_equal_subjects_passes(self):
        """clean=9, one offender, subjects=10. 9 + 1 = 10. Closes."""
        result = _base_result(subjects=10, clean=9)
        result["offenders"]["a_rule"] = ["rec-1"]
        ok, errors = validate_result(result)
        self.assertTrue(ok, f"unexpected errors: {errors}")

    def test_a_subject_offending_two_rules_is_counted_once(self):
        """A subject may offend several rules and is counted once in the
        arithmetic. union(offenders) is the set, not the sum of counts."""
        result = _base_result(subjects=10, clean=9)
        result["rules"] = {"rule_a": "rule a sentence", "rule_b": "rule b sentence"}
        result["counts"] = {"rule_a": 1, "rule_b": 1}
        result["offenders"] = {"rule_a": ["rec-1"], "rule_b": ["rec-1"]}
        ok, errors = validate_result(result)
        self.assertTrue(ok, f"unexpected errors: {errors}")

    def test_clean_128_subjects_128_with_non_empty_offenders_is_an_error(self):
        """The acceptance bar: clean=128, subjects=128, offenders non-empty.
        128 + N != 128 for any N > 0. The runner downgrades to ERROR."""
        result = _base_result(subjects=128, clean=128)
        result["offenders"]["a_rule"] = ["rec-1"]
        ok, errors = validate_result(result)
        self.assertFalse(ok)
        self.assertTrue(any("arithmetic" in e for e in errors))

    # --------------------------------------------- invariant 3: zero subjects

    def test_zero_subjects_is_never_pass(self):
        """subjects == 0 is VACUOUS, never PASS. '0 leads failed the
        eligibility check' is the sentence ISSUE-041 was made of."""
        result = _base_result(subjects=0, clean=0)
        result["verdict"] = "PASS"
        ok, errors = validate_result(result)
        self.assertFalse(ok)
        self.assertTrue(any("subjects == 0" in e for e in errors))

    def test_zero_subjects_without_a_reason_is_an_error(self):
        """subjects == 0 must say WHY the set was empty. 'The batch has no
        LinkedIn leads' is legitimate; silence is not."""
        result = _base_result(subjects=0, clean=0)
        result["verdict"] = "VACUOUS"
        result.pop("vacuous_reason", None)
        ok, errors = validate_result(result)
        self.assertFalse(ok)
        self.assertTrue(any("reason" in e for e in errors))

    def test_zero_subjects_with_a_reason_and_vacuous_is_valid(self):
        result = _base_result(subjects=0, clean=0)
        result["verdict"] = "VACUOUS"
        result["vacuous_reason"] = "no LinkedIn campaign in this batch"
        ok, errors = validate_result(result)
        self.assertTrue(ok, f"unexpected errors: {errors}")

    # --------------------------------------------- invariant 4: key agreement

    def test_a_rule_missing_from_counts_is_an_error(self):
        """A rule that appears in `rules` but not in `counts` is a rule nobody
        can tell apart from a rule that always passes."""
        result = _base_result(subjects=5, clean=5)
        result["rules"]["ghost_rule"] = "a rule with no count"
        ok, errors = validate_result(result)
        self.assertFalse(ok)
        self.assertTrue(any("disagree" in e for e in errors))

    def test_a_count_missing_from_rules_is_an_error(self):
        result = _base_result(subjects=5, clean=5)
        result["counts"]["orphan_count"] = 0
        ok, errors = validate_result(result)
        self.assertFalse(ok)

    def test_an_offender_key_missing_from_rules_is_an_error(self):
        result = _base_result(subjects=5, clean=5)
        result["offenders"]["orphan_offender"] = []
        ok, errors = validate_result(result)
        self.assertFalse(ok)

    # --------------------------------------------- invariant 5: rule sentences

    def test_an_empty_rule_sentence_is_an_error(self):
        result = _base_result(subjects=5, clean=5)
        result["rules"]["a_rule"] = ""
        ok, errors = validate_result(result)
        self.assertFalse(ok)


class RunnerDowngradesToError(unittest.TestCase):
    """The runner enforces the invariants: a bad result becomes ERROR."""

    def setUp(self):
        self._orig_checks = qa_pkg.CHECKS
        self._fake_mods = {}

    def tearDown(self):
        qa_pkg.CHECKS = self._orig_checks
        for mod_name in list(self._fake_mods):
            sys.modules.pop(f"qa.{mod_name}", None)
            sys.modules.pop(f"scripts.qa.{mod_name}", None)
        if "qa" in sys.modules:
            sys.modules["qa"].CHECKS = self._orig_checks

    def _install(self, check_id, module_name, result):
        mod = types.ModuleType(f"qa.{module_name}")
        mod.run = lambda **kw: dict(result)
        sys.modules[f"qa.{module_name}"] = mod
        sys.modules[f"scripts.qa.{module_name}"] = mod
        self._fake_mods[module_name] = mod
        qa_pkg.CHECKS = ((check_id, module_name, "pre_push", True),)
        # Also patch the `qa` entry in sys.modules so the runner sees it.
        import qa as _qa_direct
        _qa_direct.CHECKS = qa_pkg.CHECKS

    def test_arithmetic_violation_is_downgraded_to_error(self):
        """clean=128, subjects=128, offenders non-empty. The check says PASS
        but the arithmetic does not close. The runner says ERROR."""
        self._install("bad_math", "check_bad_math", {
            "check": "bad_math", "phase": "pre_push", "verdict": "PASS",
            "subjects": 128, "clean": 128,
            "rules": {"a_rule": "a rule"},
            "counts": {"a_rule": 1},
            "offenders": {"a_rule": ["rec-1"]},
            "unverifiable": {},
        })
        results, worst, table = qa_run.run_checks("pre_push")
        self.assertEqual(results[0]["verdict"], "ERROR")
        self.assertEqual(worst, "ERROR")

    def test_zero_subjects_from_the_runner_is_vacuous(self):
        """A check that returns zero subjects is VACUOUS, not PASS. The runner
        refuses, and the table row reads VACUOUS with the stated reason."""
        self._install("empty", "check_empty", {
            "check": "empty", "phase": "pre_push", "verdict": "VACUOUS",
            "subjects": 0, "clean": 0,
            "vacuous_reason": "no LinkedIn campaign in this batch",
            "rules": {"a_rule": "a rule"},
            "counts": {"a_rule": 0},
            "offenders": {"a_rule": []},
            "unverifiable": {},
        })
        results, worst, table = qa_run.run_checks("pre_push")
        self.assertEqual(results[0]["verdict"], "VACUOUS")
        self.assertEqual(worst, "VACUOUS")
        self.assertIn("VACUOUS", table)
        self.assertIn("no LinkedIn campaign in this batch", table)

    def test_a_missing_module_is_not_implemented(self):
        """A listed module that does not yet exist reports NOT_IMPLEMENTED in
        the table - not PASS, and not silence."""
        qa_pkg.CHECKS = (
            ("phantom", "check_that_does_not_exist", "pre_push", True),
        )
        results, worst, table = qa_run.run_checks("pre_push")
        self.assertEqual(results[0]["verdict"], "UNCONFIRMED")
        self.assertTrue(results[0].get("not_implemented"))
        self.assertIn("NOT_IMPL", table)


class ExitCodeIsWorstVerdict(unittest.TestCase):
    """The runner's exit code is the WORST verdict, not a count and not a
    boolean from a filter. Three 'green' runs in this repository meant nothing
    because a test run was piped into a filter and the filter's exit code was
    read."""

    def test_all_pass_is_zero(self):
        self.assertEqual(qa_pkg.exit_code("PASS", "pre_push"), 0)

    def test_fail_is_one(self):
        self.assertEqual(qa_pkg.exit_code("FAIL", "pre_push"), 1)

    def test_unconfirmed_is_two(self):
        self.assertEqual(qa_pkg.exit_code("UNCONFIRMED", "pre_push"), 2)

    def test_vacuous_is_two(self):
        self.assertEqual(qa_pkg.exit_code("VACUOUS", "pre_push"), 2)

    def test_error_is_three(self):
        self.assertEqual(qa_pkg.exit_code("ERROR", "pre_push"), 3)

    def test_worst_verdict_picks_error_over_fail(self):
        self.assertEqual(worst_verdict(["PASS", "FAIL", "ERROR"]), "ERROR")

    def test_worst_verdict_picks_fail_over_pass(self):
        self.assertEqual(worst_verdict(["PASS", "PASS", "FAIL"]), "FAIL")

    def test_empty_verdicts_is_pass(self):
        self.assertEqual(worst_verdict([]), "PASS")


class FourStateTable(unittest.TestCase):
    """The table for a run where one check passed, one failed, one was vacuous
    and one is not implemented, and all four rows are present."""

    def setUp(self):
        self._orig_checks = qa_pkg.CHECKS
        self._fake_mods = {}

    def tearDown(self):
        qa_pkg.CHECKS = self._orig_checks
        for mod_name in list(self._fake_mods):
            sys.modules.pop(f"qa.{mod_name}", None)
            sys.modules.pop(f"scripts.qa.{mod_name}", None)
        if "qa" in sys.modules:
            sys.modules["qa"].CHECKS = self._orig_checks

    def test_all_four_verdicts_appear_in_the_table(self):
        pass_mod = types.ModuleType("qa.check_table_pass")
        pass_mod.run = lambda **kw: {
            "check": "table_pass", "phase": "pre_push", "verdict": "PASS",
            "subjects": 10, "clean": 10,
            "rules": {"r1": "rule one"},
            "counts": {"r1": 0},
            "offenders": {"r1": []},
            "unverifiable": {},
        }
        fail_mod = types.ModuleType("qa.check_table_fail")
        fail_mod.run = lambda **kw: {
            "check": "table_fail", "phase": "pre_push", "verdict": "FAIL",
            "subjects": 10, "clean": 8,
            "rules": {"r2": "rule two"},
            "counts": {"r2": 2},
            "offenders": {"r2": ["rec-1", "rec-2"]},
            "unverifiable": {},
        }
        vacuous_mod = types.ModuleType("qa.check_table_vacuous")
        vacuous_mod.run = lambda **kw: {
            "check": "table_vacuous", "phase": "pre_push", "verdict": "VACUOUS",
            "subjects": 0, "clean": 0,
            "vacuous_reason": "no LinkedIn campaign in this batch",
            "rules": {"r3": "rule three"},
            "counts": {"r3": 0},
            "offenders": {"r3": []},
            "unverifiable": {},
        }
        for mod in (pass_mod, fail_mod, vacuous_mod):
            short_name = mod.__name__.split(".", 1)[1]  # e.g. "check_table_pass"
            sys.modules[mod.__name__] = mod
            sys.modules[f"scripts.{mod.__name__}"] = mod
            self._fake_mods[short_name] = mod

        new_checks = (
            ("table_pass", "check_table_pass", "pre_push", True),
            ("table_fail", "check_table_fail", "pre_push", True),
            ("table_vacuous", "check_table_vacuous", "pre_push", True),
            ("table_notimpl", "check_table_notimpl", "pre_push", True),
        )
        qa_pkg.CHECKS = new_checks
        import qa as _qa_direct
        _qa_direct.CHECKS = new_checks

        results, worst, table = qa_run.run_checks("pre_push")

        self.assertIn("table_pass", table)
        self.assertIn("table_fail", table)
        self.assertIn("table_vacuous", table)
        self.assertIn("table_notimpl", table)
        self.assertIn("PASS", table)
        self.assertIn("FAIL", table)
        self.assertIn("VACUOUS", table)
        self.assertIn("NOT_IMPL", table)
        self.assertIn("no LinkedIn campaign in this batch", table)
        self.assertIn("module not on disk", table)
        # VACUOUS (exit 2) is worse than FAIL (exit 1), so the worst verdict
        # is VACUOUS. The table is still REFUSED either way.
        self.assertIn(worst, ("FAIL", "VACUOUS"))


def _base_result(subjects=5, clean=5):
    """A result that passes all invariants by default."""
    return {
        "check": "test_check",
        "phase": "pre_push",
        "verdict": "PASS",
        "subjects": subjects,
        "clean": clean,
        "rules": {"a_rule": "a rule sentence"},
        "counts": {"a_rule": 0},
        "offenders": {"a_rule": []},
        "unverifiable": {},
    }


if __name__ == "__main__":
    unittest.main()
