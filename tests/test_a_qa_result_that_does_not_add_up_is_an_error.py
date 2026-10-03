"""A QA result that does not add up is an ERROR.

TASK-292. The runner asserts the five invariants of contract section 4
on every result it receives, and downgrades a result that breaks one to
ERROR. It does not trust the check.

The five invariants:
1. offenders and unverifiable hold ids, never counts and never summaries.
2. The arithmetic closes: clean + |union(offenders) U union(unverifiable)|
   == subjects.
3. subjects == 0 is VACUOUS, never PASS, and carries a stated reason.
4. Every key in counts, offenders and unverifiable exists in rules, and
   every key in rules exists in counts.
5. rules sentences are rendered from this run's parameters.
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import (
    PASS, FAIL, UNCONFIRMED, VACUOUS, ERROR,
    validate_result,
)


def _good_result(**overrides):
    """A result that passes all five invariants."""
    base = {
        "check": "test_check",
        "phase": "pre_push",
        "verdict": PASS,
        "subjects": 10,
        "clean": 10,
        "rules": {"rule_a": "rule A description"},
        "counts": {"rule_a": 0},
        "offenders": {"rule_a": []},
        "unverifiable": {},
    }
    base.update(overrides)
    return base


class ArithmeticInvariant(unittest.TestCase):
    """A check returning clean=128, subjects=128 while its offenders list
    is non-empty is downgraded to ERROR. The arithmetic invariant must be
    enforced by the runner, not by the check's good manners."""

    def test_clean_equals_subjects_but_offenders_nonempty_is_error(self):
        result = {
            "check": "test_check",
            "phase": "pre_push",
            "verdict": PASS,
            "subjects": 128,
            "clean": 128,
            "rules": {"rule_x": "some rule"},
            "counts": {"rule_x": 3},
            "offenders": {"rule_x": ["rec-001", "rec-002", "rec-003"]},
            "unverifiable": {},
        }
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR,
                         "clean=128 + 3 offenders != subjects=128; "
                         "must be downgraded to ERROR")
        self.assertTrue(any("arithmetic" in r for r in reasons))

    def test_arithmetic_closes_correctly(self):
        result = _good_result(
            subjects=10,
            clean=8,
            counts={"rule_a": 2},
            offenders={"rule_a": ["rec-001", "rec-002"]},
        )
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, PASS)
        self.assertEqual(reasons, [])

    def test_arithmetic_with_unverifiable(self):
        result = {
            "check": "test_check",
            "phase": "pre_push",
            "verdict": FAIL,
            "subjects": 10,
            "clean": 7,
            "rules": {"rule_a": "desc", "rule_b": "desc2"},
            "counts": {"rule_a": 2, "rule_b": 1},
            "offenders": {"rule_a": ["rec-001", "rec-002"], "rule_b": []},
            "unverifiable": {"rule_b": ["rec-003"]},
        }
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, FAIL)
        self.assertEqual(reasons, [])

    def test_arithmetic_with_overlap(self):
        """A subject may offend several rules and is counted once."""
        result = {
            "check": "test_check",
            "phase": "pre_push",
            "verdict": FAIL,
            "subjects": 10,
            "clean": 9,
            "rules": {"rule_a": "desc", "rule_b": "desc2"},
            "counts": {"rule_a": 1, "rule_b": 1},
            "offenders": {"rule_a": ["rec-001"], "rule_b": ["rec-001"]},
            "unverifiable": {},
        }
        # rec-001 appears in both offenders lists; union is 1 unique id.
        # clean(9) + 1 = 10 = subjects. Passes.
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, FAIL)
        self.assertEqual(reasons, [])


class IdsNotCounts(unittest.TestCase):
    """offenders and unverifiable hold ids, never counts and never
    summaries."""

    def test_count_string_is_not_an_id(self):
        result = _good_result(
            subjects=10,
            clean=5,
            counts={"rule_a": 5},
            offenders={"rule_a": ["7 leads"]},
        )
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertTrue(any("non-id" in r for r in reasons))

    def test_ellipsis_is_not_an_id(self):
        result = _good_result(
            subjects=10,
            clean=5,
            counts={"rule_a": 5},
            offenders={"rule_a": ["..."]},
        )
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertTrue(any("non-id" in r for r in reasons))

    def test_real_ids_pass(self):
        result = _good_result(
            subjects=10,
            clean=8,
            counts={"rule_a": 2},
            offenders={"rule_a": ["rec-0912:jane.doe@example.com",
                                  "rec-1188:john@other.com"]},
        )
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, PASS)


class KeysAgreeInBothDirections(unittest.TestCase):
    """Every key in counts, offenders and unverifiable exists in rules,
    and every key in rules exists in counts."""

    def test_rule_missing_from_counts(self):
        result = _good_result(
            rules={"rule_a": "desc", "rule_b": "desc2"},
            counts={"rule_a": 0},
            offenders={"rule_a": [], "rule_b": []},
        )
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertTrue(any("absent from counts" in r for r in reasons))

    def test_count_without_rule(self):
        result = _good_result(
            rules={"rule_a": "desc"},
            counts={"rule_a": 0, "rule_orphan": 5},
            offenders={"rule_a": []},
        )
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertTrue(any("absent from rules" in r for r in reasons))

    def test_offender_without_rule(self):
        result = _good_result(
            rules={"rule_a": "desc"},
            counts={"rule_a": 0},
            offenders={"rule_a": [], "rule_orphan": ["rec-001"]},
        )
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertTrue(any("absent from rules" in r for r in reasons))


class RuleSentencesNotEmpty(unittest.TestCase):
    """rules sentences are rendered from this run's parameters."""

    def test_empty_rule_sentence_is_error(self):
        result = _good_result(
            rules={"rule_a": ""},
            counts={"rule_a": 0},
            offenders={"rule_a": []},
        )
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR)
        self.assertTrue(any("empty" in r for r in reasons))


class MissingFieldsAreError(unittest.TestCase):
    """A result missing subjects or clean is ERROR."""

    def test_missing_subjects(self):
        result = {"check": "x", "verdict": PASS, "clean": 0,
                  "rules": {}, "counts": {}, "offenders": {},
                  "unverifiable": {}}
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR)

    def test_missing_clean(self):
        result = {"check": "x", "verdict": PASS, "subjects": 0,
                  "rules": {}, "counts": {}, "offenders": {},
                  "unverifiable": {}}
        verdict, reasons = validate_result(result)
        self.assertEqual(verdict, ERROR)


if __name__ == "__main__":
    unittest.main()
