"""TASK-295: the step key is not the variable number.

Measured from the config at `config/clients/productive.yaml` lines 590-626:

    thread_reply_pattern: [false, true, true, true]

    em1   order 1   subject {SUBJECT_1}   body {BODY_1}   wait 3
    em2   order 2   subject {SUBJECT_1}   body {BODY_2}   wait 4
    em4   order 3   subject {SUBJECT_1}   body {BODY_3}   wait 5
    em5   order 4   subject {SUBJECT_1}   body {BODY_4}   wait 1

Three facts:
1. The step key is not the variable number. em4 is at POSITION 3 and reads
   {BODY_3}; em5 is at POSITION 4 and reads {BODY_4}.
2. There is no SUBJECT_2 and no new-thread step at position 3.
3. A threaded step still carries a subject.

These tests assert on the MAPPING the check reads from the config, not on
hardcoded assumptions.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.qa.check_lead_copy import (                       # noqa: E402
    read_step_mapping, _key_number, _format_step_mapping,
    check_body_present, check_subject_present,
    check_no_unrendered_placeholder, UNRENDERED_RE,
)


class TestStepKeyIsNotVariableNumber(unittest.TestCase):
    """The step key is NOT the variable number. A check that maps
    em5 -> BODY_5 will look for a variable that does not exist."""

    def test_four_step_mapping_positions(self):
        """In a 4-step config (em1, em2, em4, em5), positions are 1-4
        but body fields are body_1, body_2, body_4, body_5."""
        config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em4": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 5},
                    "em5": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>", "wait_in_days": 1},
                },
            }
        }
        steps, pattern, step_to_body = read_step_mapping(config)
        self.assertEqual(len(steps), 4)
        self.assertEqual(steps[0]["key"], "em1")
        self.assertEqual(steps[1]["key"], "em2")
        self.assertEqual(steps[2]["key"], "em4")
        self.assertEqual(steps[3]["key"], "em5")

        self.assertEqual(step_to_body["em1"], "body_1")
        self.assertEqual(step_to_body["em2"], "body_2")
        self.assertEqual(step_to_body["em4"], "body_4")
        self.assertEqual(step_to_body["em5"], "body_5")

        self.assertEqual(pattern, (False, True, True, True))

    def test_four_step_provider_variables(self):
        """The provider variable numbers are by POSITION, not by key.
        em4 is position 3 -> BODY_3; em5 is position 4 -> BODY_4."""
        config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em4": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 5},
                    "em5": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>", "wait_in_days": 1},
                },
            }
        }
        steps, pattern, step_to_body = read_step_mapping(config)
        mapping = _format_step_mapping(steps, pattern, step_to_body)

        self.assertEqual(len(mapping), 4)
        self.assertEqual(mapping[0]["provider_variable"], "BODY_1")
        self.assertEqual(mapping[1]["provider_variable"], "BODY_2")
        self.assertEqual(mapping[2]["provider_variable"], "BODY_3")
        self.assertEqual(mapping[3]["provider_variable"], "BODY_4")

        self.assertEqual(mapping[2]["step_key"], "em4")
        self.assertEqual(mapping[2]["body_field"], "body_4")
        self.assertEqual(mapping[3]["step_key"], "em5")
        self.assertEqual(mapping[3]["body_field"], "body_5")

    def test_five_step_mapping_agrees_by_coincidence(self):
        """At 5 steps, position and key number happen to agree.
        This is a coincidence, not a rule."""
        config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em3": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 4},
                    "em4": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>", "wait_in_days": 9},
                    "em5": {"order": 5, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_5}</p>", "wait_in_days": 1},
                },
            }
        }
        steps, pattern, step_to_body = read_step_mapping(config)
        mapping = _format_step_mapping(steps, pattern, step_to_body)

        self.assertEqual(len(mapping), 5)
        for i, entry in enumerate(mapping):
            expected_key = f"em{i + 1}"
            self.assertEqual(entry["step_key"], expected_key)
            self.assertEqual(entry["provider_variable"], f"BODY_{i + 1}")
            self.assertEqual(entry["body_field"], f"body_{i + 1}")

    def test_three_step_mapping(self):
        """Three-step campaigns (485-500) have em1, em2, em3."""
        config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em3": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 1},
                },
            }
        }
        steps, pattern, step_to_body = read_step_mapping(config)
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[2]["key"], "em3")
        self.assertEqual(step_to_body["em3"], "body_3")

    def test_all_steps_carry_subject_1(self):
        """There is no SUBJECT_2. All four steps carry {SUBJECT_1}."""
        config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em4": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 5},
                    "em5": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>", "wait_in_days": 1},
                },
            }
        }
        steps, _, _ = read_step_mapping(config)
        for step in steps:
            self.assertEqual(step["subject"], "{SUBJECT_1}",
                             f"step {step['key']} should carry SUBJECT_1")

    def test_no_new_thread_at_position_3(self):
        """The first entry is false, the other three are true.
        em4 does NOT open a second thread."""
        config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em4": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 5},
                    "em5": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>", "wait_in_days": 1},
                },
            }
        }
        _, pattern, step_to_body = read_step_mapping(config)
        mapping = _format_step_mapping(
            read_step_mapping(config)[0], pattern, step_to_body)
        self.assertFalse(mapping[0]["thread_reply"])
        self.assertTrue(mapping[1]["thread_reply"])
        self.assertTrue(mapping[2]["thread_reply"])
        self.assertTrue(mapping[3]["thread_reply"])

    def test_key_number_extraction(self):
        """_key_number extracts the trailing number from a step key."""
        self.assertEqual(_key_number("em1"), 1)
        self.assertEqual(_key_number("em4"), 4)
        self.assertEqual(_key_number("li3"), 3)
        self.assertIsNone(_key_number("breakup"))


class TestRenderedRowBodyFieldLookup(unittest.TestCase):
    """The check looks up body fields by step key number, not position."""

    def test_four_step_body_lookup(self):
        """In a 4-step config, em4's body is at body_4, not body_3."""
        config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em4": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 5},
                    "em5": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>", "wait_in_days": 1},
                },
            }
        }
        _, _, step_to_body = read_step_mapping(config)
        self.assertEqual(step_to_body["em4"], "body_4")
        self.assertEqual(step_to_body["em5"], "body_5")

    def test_unrendered_placeholder_detected_in_body_field(self):
        """A surviving {BODY_3} in the rendered body is caught."""
        step_vars = {"subject": "Hello", "body": "Hi Jane, {BODY_3} text"}
        self.assertFalse(
            check_no_unrendered_placeholder(step_vars, {}, ()))

    def test_clean_body_passes(self):
        """A fully rendered body passes the placeholder check."""
        step_vars = {
            "subject": "Hello",
            "body": "Hi Jane, I work with teams on resource planning."
        }
        self.assertTrue(
            check_no_unrendered_placeholder(step_vars, {}, ()))


if __name__ == "__main__":
    unittest.main()
