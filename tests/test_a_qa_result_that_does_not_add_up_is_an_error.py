"""A QA result that does not add up is an ERROR, not a verdict.

The runner asserts the five invariants of contract §4 on every result it
receives, and downgrades a result that breaks one to ERROR. It does not
trust the check.

These tests drive the RUNNER, not the check. A check that returns bad
arithmetic is not a PASS with a note — it is ERROR(3), and the table says so.
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from scripts.qa import (                          # noqa: E402
    CHECKS, ERROR, FAIL, PASS, UNCONFIRMED, VACUOUS, VERDICT_EXIT,
    checks_for_phase, exit_code, worst_verdict,
)
from scripts.qa.run import (                       # noqa: E402
    _validate_result, _not_implemented_result, _vacuous_result,
    run_phase, render_table, NOT_IMPLEMENTED,
)


def _good_result(check="lead_state", phase="pre_push", subjects=10,
                 clean=8, verdict=FAIL):
    """A well-formed FAIL result: arithmetic closes, ids are ids."""
    return {
        "check": check,
        "phase": phase,
        "verdict": verdict,
        "subjects": subjects,
        "clean": clean,
        "refused": verdict != PASS,
        "rules": {
            "rule_a": "rule a fires when condition a is met",
            "rule_b": "rule b fires when condition b is met",
        },
        "counts": {"rule_a": 1, "rule_b": 1},
        "offenders": {
            "rule_a": ["rec-0001:alice@example.com"],
            "rule_b": ["rec-0002:bob@example.com"],
        },
        "unverifiable": {},
        "evidence": {},
        "measured_at": "2026-09-25T06:00:00Z",
    }


class Invariant1_OffendersHoldIds(unittest.TestCase):
    """offenders and unverifiable hold IDS, never counts and never '...'."""

    def test_count_string_is_rejected(self):
        result = _good_result()
        result["offenders"]["rule_a"] = ["7 leads"]
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("not an id", reason.lower())

    def test_ellipsis_is_rejected(self):
        result = _good_result()
        result["offenders"]["rule_a"] = ["rec-0001:alice@example.com", "..."]
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)

    def test_empty_string_is_rejected(self):
        result = _good_result()
        result["offenders"]["rule_a"] = [""]
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)

    def test_truncation_ellipsis_is_rejected(self):
        result = _good_result()
        result["offenders"]["rule_a"] = ["…"]
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)

    def test_real_ids_pass(self):
        result = _good_result()
        verdict, reason = _validate_result(result)
        self.assertIsNone(verdict)


class Invariant2_ArithmeticCloses(unittest.TestCase):
    """clean + |union(offenders) ∪ union(unverifiable)| == subjects."""

    def test_dropped_subject_is_caught(self):
        result = _good_result(subjects=10, clean=9)
        # 9 clean + 2 offenders = 11 != 10
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("arithmetic", reason.lower())

    def test_double_counted_offender_is_caught(self):
        """A subject in two rules is counted ONCE in the union."""
        result = _good_result(subjects=10, clean=9)
        # Same id in two rules: union is 1, so 9 + 1 = 10 ✓
        result["offenders"] = {
            "rule_a": ["rec-0001:alice@example.com"],
            "rule_b": ["rec-0001:alice@example.com"],
        }
        result["counts"] = {"rule_a": 1, "rule_b": 1}
        verdict, reason = _validate_result(result)
        self.assertIsNone(verdict)

    def test_correct_arithmetic_passes(self):
        result = _good_result(subjects=10, clean=8)
        # 8 clean + 2 unique offenders = 10 ✓
        verdict, reason = _validate_result(result)
        self.assertIsNone(verdict)

    def test_clean_128_subjects_128_with_nonempty_offenders_is_error(self):
        """Acceptance bar: clean=128, subjects=128, offenders non-empty."""
        result = {
            "check": "lead_state",
            "phase": "pre_push",
            "verdict": PASS,
            "subjects": 128,
            "clean": 128,
            "refused": False,
            "rules": {"rule_x": "a rule"},
            "counts": {"rule_x": 1},
            "offenders": {"rule_x": ["rec-9999:someone@example.com"]},
            "unverifiable": {},
            "evidence": {},
            "measured_at": "2026-09-25T06:00:00Z",
        }
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("arithmetic", reason.lower())


class Invariant3_ZeroSubjectsIsVacuous(unittest.TestCase):
    """subjects == 0 is VACUOUS, never PASS, and carries a stated reason."""

    def test_zero_subjects_with_pass_verdict_is_error(self):
        result = {
            "check": "lead_state",
            "phase": "pre_push",
            "verdict": PASS,
            "subjects": 0,
            "clean": 0,
            "refused": False,
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
            "evidence": {},
            "measured_at": "2026-09-25T06:00:00Z",
        }
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("VACUOUS", reason)

    def test_zero_subjects_with_vacuous_verdict_passes(self):
        result = _vacuous_result("lead_state", "pre_push",
                                 "no LinkedIn leads in this batch")
        verdict, reason = _validate_result(result)
        self.assertIsNone(verdict)


class Invariant4_KeysAgree(unittest.TestCase):
    """rules, counts, offenders keys agree in both directions."""

    def test_rule_missing_from_counts_is_caught(self):
        result = _good_result()
        result["counts"] = {"rule_a": 1}  # rule_b missing
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("disagree", reason.lower())

    def test_rule_missing_from_offenders_is_caught(self):
        result = _good_result()
        del result["offenders"]["rule_b"]
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("offenders", reason.lower())

    def test_offender_key_not_in_rules_is_caught(self):
        result = _good_result()
        result["offenders"]["phantom_rule"] = ["rec-0099:x@y.com"]
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("not in rules", reason.lower())

    def test_count_does_not_match_offenders_length_is_caught(self):
        result = _good_result()
        result["counts"]["rule_a"] = 99  # but offenders has 1
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("counts", reason.lower())


class Invariant5_RulesRendered(unittest.TestCase):
    """Rule sentences are non-empty strings rendered from run parameters."""

    def test_empty_sentence_is_caught(self):
        result = _good_result()
        result["rules"]["rule_a"] = ""
        verdict, reason = _validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertIn("sentence", reason.lower())


class ExitCodeIsWorstVerdict(unittest.TestCase):
    """The exit code is the WORST verdict, not a count or a boolean."""

    def test_all_pass_is_zero(self):
        self.assertEqual(exit_code(worst_verdict([PASS, PASS])), 0)

    def test_one_fail_is_one(self):
        self.assertEqual(exit_code(worst_verdict([PASS, FAIL, PASS])), 1)

    def test_unconfirmed_beats_fail(self):
        self.assertEqual(exit_code(worst_verdict([FAIL, UNCONFIRMED])), 2)

    def test_error_is_worst(self):
        self.assertEqual(exit_code(worst_verdict([FAIL, ERROR, VACUOUS])), 3)

    def test_vacuous_is_two(self):
        self.assertEqual(exit_code(VACUOUS), 2)

    def test_empty_verdicts_is_vacuous(self):
        """No checks ran is NOT a pass."""
        self.assertEqual(exit_code(worst_verdict([])), 2)


class EveryCheckOnDiskIsRegistered(unittest.TestCase):
    """Every scripts/qa/check_*.py on disk appears in CHECKS."""

    def test_no_unregistered_checks(self):
        import scripts.qa as qa_pkg
        pkg_dir = os.path.dirname(qa_pkg.__file__)
        on_disk = set()
        for fname in os.listdir(pkg_dir):
            if fname.startswith("check_") and fname.endswith(".py"):
                on_disk.add(fname[len("check_"):-len(".py")])
        registered = {check_id for check_id, _, _, _ in CHECKS}
        unregistered = on_disk - registered
        self.assertEqual(
            unregistered, set(),
            "check modules on disk not in CHECKS: %s" % sorted(unregistered))


class FourStateTable(unittest.TestCase):
    """One passed, one failed, one vacuous, one not implemented — all four rows."""

    def test_all_four_rows_present(self):
        results = [
            {"check": "lead_state", "phase": "pre_push", "verdict": PASS,
             "subjects": 128, "clean": 128, "offenders": {}, "evidence": {}},
            {"check": "lead_copy", "phase": "pre_push", "verdict": FAIL,
             "subjects": 128, "clean": 119,
             "offenders": {"step1_without_pack_fact": [
                 "rec-%04d:x@y.com" % i for i in range(9)]},
             "evidence": {}},
            {"check": "campaign_heyreach", "phase": "pre_push",
             "verdict": VACUOUS, "subjects": 0, "clean": 0,
             "offenders": {},
             "evidence": {"vacuous_reason":
                          "no LinkedIn campaign in this batch"}},
            {"check": "campaign_bison", "phase": "pre_push",
             "verdict": NOT_IMPLEMENTED, "subjects": 0, "clean": 0,
             "offenders": {}, "evidence": {"not_implemented": "module not found"}},
        ]
        table = render_table(results, phase="pre_push",
                             batch="batch-2-2026-09-25",
                             campaigns=["502", "503"])
        for check_id in ("lead_state", "lead_copy", "campaign_heyreach",
                         "campaign_bison"):
            self.assertIn(check_id, table,
                          "table missing row for %s" % check_id)
        self.assertIn("PASS", table)
        self.assertIn("FAIL", table)
        self.assertIn("VACUOUS", table)
        self.assertIn("NOT_IMPLEMENTED", table)
        self.assertIn("REFUSED", table)
        # No prospect ids in the table.
        self.assertNotIn("rec-0000", table)
        self.assertNotIn("x@y.com", table)


class RunnerRefusesOnEmptyChecks(unittest.TestCase):
    """A runner that reports PASS when it ran nothing is rejected."""

    def test_empty_checks_for_phase_is_vacuous(self):
        """If the phase matched no check, that is not a pass."""
        worst, results = run_phase("ongoing", workspaces="/nonexistent")
        # No check modules exist, so all are NOT_IMPLEMENTED.
        # worst_verdict of NOT_IMPLEMENTED values...
        # NOT_IMPLEMENTED is not in VERDICT_EXIT, so worst_verdict uses
        # max with key VERDICT_EXIT.get(v, 3) -> 3 for all.
        # The runner should not return PASS.
        self.assertNotEqual(worst, PASS)


if __name__ == "__main__":
    unittest.main()
