"""A QA result that does not add up is an ERROR, not whatever the check said.

TASK-292. The runner asserts five invariants on every result it receives,
and downgrades a result that breaks one to ERROR. It does not trust the check.

The five invariants (contract section 4):
1. offenders and unverifiable hold ids, not counts or summaries.
2. clean + |union(offenders) ∪ union(unverifiable)| == subjects.
3. subjects == 0 is VACUOUS, never PASS.
4. Every key in counts, offenders, unverifiable exists in rules, and vice versa.
5. rules sentences are rendered from this run's parameters.
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.qa import validate_result


class ArithmeticInvariant(unittest.TestCase):
    """clean + |union(offenders) ∪ union(unverifiable)| == subjects."""

    def test_clean_plus_offenders_equals_subjects_passes(self):
        result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 128,
            "clean": 121,
            "rules": {
                "unverified": "needs two providers",
                "in_sequence": "already in a sequence",
            },
            "counts": {"unverified": 5, "in_sequence": 2},
            "offenders": {
                "unverified": ["rec-001", "rec-002", "rec-003",
                               "rec-004", "rec-005"],
                "in_sequence": ["rec-006", "rec-007"],
            },
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertIsNone(error)
        self.assertEqual(validated["verdict"], "FAIL")

    def test_arithmetic_mismatch_is_downgraded_to_error(self):
        result = {
            "check": "lead_state",
            "verdict": "PASS",
            "subjects": 128,
            "clean": 128,
            "rules": {"some_rule": "a rule"},
            "counts": {"some_rule": 0},
            "offenders": {"some_rule": ["rec-001"]},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertEqual(validated["verdict"], "ERROR")
        self.assertIn("arithmetic does not close", error)

    def test_duplicate_offenders_counted_once(self):
        """A subject may offend several rules and is counted once."""
        result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 10,
            "clean": 9,
            "rules": {
                "rule_a": "first rule",
                "rule_b": "second rule",
            },
            "counts": {"rule_a": 1, "rule_b": 1},
            "offenders": {
                "rule_a": ["rec-001"],
                "rule_b": ["rec-001"],
            },
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertIsNone(error)
        self.assertEqual(validated["verdict"], "FAIL")

    def test_unverifiable_included_in_arithmetic(self):
        result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 10,
            "clean": 8,
            "rules": {"rule_a": "text"},
            "counts": {"rule_a": 1},
            "offenders": {"rule_a": ["rec-001"]},
            "unverifiable": {"rule_a": ["rec-002"]},
        }
        validated, error = validate_result(result)
        self.assertIsNone(error)


class OffendersHoldIdsNotCounts(unittest.TestCase):
    """offenders and unverifiable hold ids, never counts or summaries."""

    def test_string_ids_pass(self):
        result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 5,
            "clean": 3,
            "rules": {"rule_a": "text"},
            "counts": {"rule_a": 2},
            "offenders": {"rule_a": ["rec-001:alice", "rec-002:bob"]},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertIsNone(error)

    def test_count_instead_of_ids_is_error(self):
        result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 5,
            "clean": 3,
            "rules": {"rule_a": "text"},
            "counts": {"rule_a": 2},
            "offenders": {"rule_a": "2 leads"},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertEqual(validated["verdict"], "ERROR")
        self.assertIn("not a list", error)

    def test_empty_string_id_is_error(self):
        result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 5,
            "clean": 4,
            "rules": {"rule_a": "text"},
            "counts": {"rule_a": 1},
            "offenders": {"rule_a": [""]},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertEqual(validated["verdict"], "ERROR")


class RuleKeysAgreeInBothDirections(unittest.TestCase):
    """Every key in counts, offenders, unverifiable exists in rules,
    and every key in rules exists in counts."""

    def test_matching_keys_pass(self):
        result = {
            "check": "lead_state",
            "verdict": "PASS",
            "subjects": 10,
            "clean": 10,
            "rules": {"rule_a": "text", "rule_b": "text"},
            "counts": {"rule_a": 0, "rule_b": 0},
            "offenders": {},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertIsNone(error)

    def test_count_key_not_in_rules_is_error(self):
        result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 5,
            "clean": 4,
            "rules": {"rule_a": "text"},
            "counts": {"rule_a": 1, "rule_b": 0},
            "offenders": {"rule_a": ["rec-001"]},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertEqual(validated["verdict"], "ERROR")
        self.assertIn("counts has keys not in rules", error)

    def test_rule_key_not_in_counts_is_error(self):
        result = {
            "check": "lead_state",
            "verdict": "PASS",
            "subjects": 10,
            "clean": 10,
            "rules": {"rule_a": "text", "rule_b": "text"},
            "counts": {"rule_a": 0},
            "offenders": {},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertEqual(validated["verdict"], "ERROR")
        self.assertIn("rules has keys not in counts", error)

    def test_offender_key_not_in_rules_is_error(self):
        result = {
            "check": "lead_state",
            "verdict": "FAIL",
            "subjects": 5,
            "clean": 4,
            "rules": {"rule_a": "text"},
            "counts": {"rule_a": 1},
            "offenders": {"rule_a": ["rec-001"],
                          "rule_z": ["rec-002"]},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertEqual(validated["verdict"], "ERROR")
        self.assertIn("offenders has keys not in rules", error)


class SubjectsZeroIsNeverPass(unittest.TestCase):
    """subjects == 0 is VACUOUS, never PASS, and carries a stated reason."""

    def test_zero_subjects_pass_is_error(self):
        result = {
            "check": "lead_state",
            "verdict": "PASS",
            "subjects": 0,
            "clean": 0,
            "rules": {"rule_a": "text"},
            "counts": {"rule_a": 0},
            "offenders": {},
            "unverifiable": {},
        }
        validated, error = validate_result(result)
        self.assertEqual(validated["verdict"], "ERROR")
        self.assertIn("subjects == 0", error)

    def test_zero_subjects_vacuous_is_valid(self):
        result = {
            "check": "lead_state",
            "verdict": "VACUOUS",
            "subjects": 0,
            "clean": 0,
            "rules": {"rule_a": "text"},
            "counts": {"rule_a": 0},
            "offenders": {},
            "unverifiable": {},
            "vacuous_reason": "no LinkedIn leads in this batch",
        }
        validated, error = validate_result(result)
        self.assertIsNone(error)
        self.assertEqual(validated["verdict"], "VACUOUS")


if __name__ == "__main__":
    raise unittest.main()
