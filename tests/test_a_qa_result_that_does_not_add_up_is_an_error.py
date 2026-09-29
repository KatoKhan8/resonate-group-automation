"""A QA result that does not add up is an ERROR.

TASK-292. These tests prove:

1. A check returning clean=128, subjects=128 while offenders is non-empty
   is downgraded to ERROR by the runner.
2. subjects == 0 does not pass — it is VACUOUS with a stated reason.
3. The runner downgrades results that break any of the five invariants.
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import (
    PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR, NOT_IMPLEMENTED,
    validate_result, validate_invariant_1_ids,
    validate_invariant_2_arithmetic, validate_invariant_3_vacuous,
    validate_invariant_4_keys_agree, validate_invariant_5_rule_sentences,
)
from scripts.qa import run as qa_run


class TestArithmeticInvariant(unittest.TestCase):
    """clean + |union(offenders) ∪ union(unverifiable)| == subjects.

    A check whose arithmetic does not close has dropped subjects somewhere,
    and a dropped subject is the one that was wrong.
    """

    def test_clean_plus_offenders_must_equal_subjects(self):
        """clean=128, subjects=128, offenders non-empty -> ERROR."""
        result = {
            "check": "test_check",
            "phase": "pre_push",
            "verdict": PASS,
            "subjects": 128,
            "clean": 128,
            "rules": {"rule_a": "some rule"},
            "counts": {"rule_a": 2},
            "offenders": {"rule_a": ["rec-001:john@test.com",
                                     "rec-002:jane@test.com"]},
            "unverifiable": {},
        }
        # 128 + 2 = 130 != 128
        problems = validate_invariant_2_arithmetic(result)
        self.assertTrue(len(problems) > 0)
        self.assertIn("arithmetic", problems[0])

    def test_arithmetic_closes_when_correct(self):
        """clean=126, subjects=128, 2 offenders -> OK."""
        result = {
            "check": "test_check",
            "phase": "pre_push",
            "verdict": FAIL,
            "subjects": 128,
            "clean": 126,
            "rules": {"rule_a": "some rule"},
            "counts": {"rule_a": 2},
            "offenders": {"rule_a": ["rec-001:john@test.com",
                                     "rec-002:jane@test.com"]},
            "unverifiable": {},
        }
        # 126 + 2 = 128 == 128
        problems = validate_invariant_2_arithmetic(result)
        self.assertEqual(problems, [])

    def test_union_deduplication(self):
        """A subject offending two rules is counted once."""
        result = {
            "check": "test_check",
            "phase": "pre_push",
            "verdict": FAIL,
            "subjects": 10,
            "clean": 9,
            "rules": {"rule_a": "rule a", "rule_b": "rule b"},
            "counts": {"rule_a": 1, "rule_b": 1},
            "offenders": {
                "rule_a": ["rec-001"],
                "rule_b": ["rec-001"],  # same subject
            },
            "unverifiable": {},
        }
        # union = {rec-001}, |union| = 1
        # 9 + 1 = 10 == 10
        problems = validate_invariant_2_arithmetic(result)
        self.assertEqual(problems, [])

    def test_runner_downgrades_bad_arithmetic_to_error(self):
        """The runner asserts the invariant and downgrades to ERROR."""
        import tempfile
        import types

        # Create a fake check module that returns bad arithmetic.
        fake_module = types.ModuleType("scripts.qa.check_fake_test")
        fake_module.run = lambda **kw: {
            "check": "fake_test",
            "phase": "pre_push",
            "verdict": PASS,
            "subjects": 10,
            "clean": 10,  # 10 + 1 != 10
            "rules": {"rule_a": "some rule"},
            "counts": {"rule_a": 1},
            "offenders": {"rule_a": ["rec-001:john@test.com"]},
            "unverifiable": {},
            "measured_at": "2026-09-29T00:00:00Z",
        }

        # Register it temporarily - patch BOTH scripts.qa AND scripts.qa.run
        import scripts.qa as qa_init
        from scripts.qa import CheckEntry
        new_checks = (
            CheckEntry("fake_test", "scripts.qa.check_fake_test",
                       "pre_push", True),
        )
        original_checks = qa_init.CHECKS
        original_by_id = qa_init.CHECK_BY_ID
        original_run_checks = qa_run.CHECKS
        
        qa_init.CHECKS = new_checks
        qa_init.CHECK_BY_ID = {c.check_id: c for c in new_checks}
        qa_run.CHECKS = new_checks

        # Patch the import to find our fake module.
        import sys
        sys.modules["scripts.qa.check_fake_test"] = fake_module

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results, worst, exit_code, table, outdir = qa_run.run_phase(
                    "pre_push",
                    workspaces=tmpdir,
                    output_dir=os.path.join(tmpdir, "qa"),
                )
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["verdict"], ERROR)
                self.assertIn("validation_problems", results[0])
        finally:
            qa_init.CHECKS = original_checks
            qa_init.CHECK_BY_ID = original_by_id
            qa_run.CHECKS = original_run_checks
            del sys.modules["scripts.qa.check_fake_test"]


class TestVacuousNotPass(unittest.TestCase):
    """subjects == 0 is VACUOUS, never PASS."""

    def test_zero_subjects_is_not_pass(self):
        result = {
            "subjects": 0,
            "verdict": PASS,
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
        }
        problems = validate_invariant_3_vacuous(result)
        self.assertTrue(len(problems) > 0)
        self.assertIn("VACUOUS", problems[0])

    def test_zero_subjects_with_reason_is_ok(self):
        result = {
            "subjects": 0,
            "verdict": VACUOUS,
            "vacuous_reason": "no LinkedIn campaign in this batch",
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
        }
        problems = validate_invariant_3_vacuous(result)
        self.assertEqual(problems, [])

    def test_zero_subjects_without_reason_is_flagged(self):
        result = {
            "subjects": 0,
            "verdict": VACUOUS,
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
        }
        problems = validate_invariant_3_vacuous(result)
        self.assertTrue(any("vacuous_reason" in p for p in problems))

    def test_runner_refuses_zero_subjects(self):
        """Register a check that returns zero subjects, assert VACUOUS."""
        import tempfile
        import types
        import sys

        fake_module = types.ModuleType("scripts.qa.check_zero_subj")
        fake_module.run = lambda **kw: {
            "check": "zero_subj",
            "phase": "pre_push",
            "verdict": VACUOUS,
            "subjects": 0,
            "clean": 0,
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
            "vacuous_reason": "no subjects in this batch",
            "measured_at": "2026-09-29T00:00:00Z",
        }

        import scripts.qa as qa_init
        from scripts.qa import CheckEntry
        new_checks = (
            CheckEntry("zero_subj", "scripts.qa.check_zero_subj",
                       "pre_push", True),
        )
        original_checks = qa_init.CHECKS
        original_by_id = qa_init.CHECK_BY_ID
        original_run_checks = qa_run.CHECKS
        
        qa_init.CHECKS = new_checks
        qa_init.CHECK_BY_ID = {c.check_id: c for c in new_checks}
        qa_run.CHECKS = new_checks
        sys.modules["scripts.qa.check_zero_subj"] = fake_module

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results, worst, exit_code, table, outdir = qa_run.run_phase(
                    "pre_push",
                    workspaces=tmpdir,
                    output_dir=os.path.join(tmpdir, "qa"),
                )
                self.assertEqual(results[0]["verdict"], VACUOUS)
                self.assertIn("VACUOUS", table)
                self.assertIn("no subjects", table)
        finally:
            qa_init.CHECKS = original_checks
            qa_init.CHECK_BY_ID = original_by_id
            qa_run.CHECKS = original_run_checks
            del sys.modules["scripts.qa.check_zero_subj"]


class TestIdInvariant(unittest.TestCase):
    """Offenders and unverifiable hold ids, never counts or summaries."""

    def test_count_is_not_an_id(self):
        result = {
            "offenders": {"rule_a": ["7 leads"]},
            "unverifiable": {},
        }
        problems = validate_invariant_1_ids(result)
        self.assertTrue(len(problems) > 0)

    def test_truncation_is_not_an_id(self):
        result = {
            "offenders": {"rule_a": ["..."]},
            "unverifiable": {},
        }
        problems = validate_invariant_1_ids(result)
        self.assertTrue(len(problems) > 0)

    def test_bare_number_is_not_an_id(self):
        result = {
            "offenders": {"rule_a": ["42"]},
            "unverifiable": {},
        }
        problems = validate_invariant_1_ids(result)
        self.assertTrue(len(problems) > 0)

    def test_real_id_is_accepted(self):
        result = {
            "offenders": {"rule_a": ["rec-0912:jane.doe@example.com"]},
            "unverifiable": {},
        }
        problems = validate_invariant_1_ids(result)
        self.assertEqual(problems, [])


class TestKeyAgreement(unittest.TestCase):
    """Every key in counts, offenders, unverifiable exists in rules."""

    def test_extra_key_in_counts(self):
        result = {
            "rules": {"rule_a": "some rule"},
            "counts": {"rule_a": 0, "rule_b": 1},
            "offenders": {},
            "unverifiable": {},
        }
        problems = validate_invariant_4_keys_agree(result)
        self.assertTrue(any("not in rules" in p for p in problems))

    def test_missing_key_in_counts(self):
        result = {
            "rules": {"rule_a": "some rule", "rule_b": "another rule"},
            "counts": {"rule_a": 0},
            "offenders": {},
            "unverifiable": {},
        }
        problems = validate_invariant_4_keys_agree(result)
        self.assertTrue(any("not in counts" in p for p in problems))

    def test_all_keys_agree(self):
        result = {
            "rules": {"rule_a": "some rule"},
            "counts": {"rule_a": 0},
            "offenders": {"rule_a": []},
            "unverifiable": {"rule_a": []},
        }
        problems = validate_invariant_4_keys_agree(result)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
