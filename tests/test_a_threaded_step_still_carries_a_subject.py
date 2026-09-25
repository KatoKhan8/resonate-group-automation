"""TASK-295: a threaded step still carries a subject.

`bisonfactory._sequence_steps` says it in its own docstring: "A follow-up
step STILL CARRIES `email_subject` - the flag is the mechanism, not subject
omission."

So "step 2 has no subject" is NOT how a threaded step is detected. A check
that treats an empty subject on step 2 as correct threading will pass a step
that sends with no subject line.

These tests verify that:
1. A threaded step with a subject passes.
2. A threaded step with an empty subject FAILS.
3. A threaded step with a DIFFERENT subject from the opener FAILS.
4. The opener (step 1) with an empty subject FAILS.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.qa.check_lead_copy import (                       # noqa: E402
    check_subject_matches_the_step,
    check_subject_present,
    read_step_mapping,
    _format_step_mapping,
)


class TestThreadedStepStillCarriesSubject(unittest.TestCase):
    """A threaded step STILL CARRIES email_subject. The flag is the
    mechanism, not subject omission."""

    def test_threaded_step_with_matching_subject_passes(self):
        """Step 2 is threaded and carries the same subject as step 1."""
        pattern = (False, True, True, True)
        step_vars = {
            "subject": "Resource planning for teams",
            "opener_subject": "Resource planning for teams",
        }
        step_info = {"position": 2}
        self.assertTrue(
            check_subject_matches_the_step(step_vars, step_info, pattern))

    def test_threaded_step_with_empty_subject_fails(self):
        """Step 2 is threaded but has an empty subject. This is a FAULT,
        not correct threading."""
        pattern = (False, True, True, True)
        step_vars = {
            "subject": "",
            "opener_subject": "Resource planning for teams",
        }
        step_info = {"position": 2}
        self.assertFalse(
            check_subject_matches_the_step(step_vars, step_info, pattern))

    def test_threaded_step_with_different_subject_fails(self):
        """Step 2 is threaded but carries a different subject."""
        pattern = (False, True, True, True)
        step_vars = {
            "subject": "A different subject entirely",
            "opener_subject": "Resource planning for teams",
        }
        step_info = {"position": 2}
        self.assertFalse(
            check_subject_matches_the_step(step_vars, step_info, pattern))

    def test_opener_with_subject_passes(self):
        """Step 1 (the opener) with a subject passes."""
        pattern = (False, True, True, True)
        step_vars = {
            "subject": "Resource planning for teams",
            "opener_subject": "Resource planning for teams",
        }
        step_info = {"position": 1}
        self.assertTrue(
            check_subject_matches_the_step(step_vars, step_info, pattern))

    def test_opener_with_empty_subject_fails(self):
        """Step 1 (the opener) with an empty subject fails."""
        pattern = (False, True, True, True)
        step_vars = {
            "subject": "",
            "opener_subject": "",
        }
        step_info = {"position": 1}
        self.assertFalse(
            check_subject_matches_the_step(step_vars, step_info, pattern))

    def test_new_thread_step_with_own_subject_passes(self):
        """A non-threaded follow-up step with its own subject passes."""
        pattern = (False, False, True, True)
        step_vars = {
            "subject": "A fresh subject for a new thread",
            "opener_subject": "Resource planning for teams",
        }
        step_info = {"position": 2}
        self.assertTrue(
            check_subject_matches_the_step(step_vars, step_info, pattern))

    def test_subject_present_separate_from_threading(self):
        """subject_present checks non-emptiness regardless of threading."""
        step_vars = {"subject": "Hello", "body": "World"}
        self.assertTrue(check_subject_present(step_vars, {}, ()))

        step_vars_empty = {"subject": "", "body": "World"}
        self.assertFalse(check_subject_present(step_vars_empty, {}, ()))

        step_vars_whitespace = {"subject": "  ", "body": "World"}
        self.assertFalse(
            check_subject_present(step_vars_whitespace, {}, ()))


class TestSubjectPresentRule(unittest.TestCase):
    """subject_present: non-empty after strip, for every step."""

    def test_empty_subject_fails(self):
        step_vars = {"subject": "", "body": "Some body text"}
        self.assertFalse(check_subject_present(step_vars, {}, ()))

    def test_whitespace_only_subject_fails(self):
        step_vars = {"subject": "   \t  ", "body": "Some body text"}
        self.assertFalse(check_subject_present(step_vars, {}, ()))

    def test_nonempty_subject_passes(self):
        step_vars = {"subject": "Hello World", "body": "Some body text"}
        self.assertTrue(check_subject_present(step_vars, {}, ()))


class TestSubjectMatchesThreadingFromConfig(unittest.TestCase):
    """The threading pattern is read from the config, not hardcoded."""

    def test_four_step_all_threaded_after_opener(self):
        """In the 4-step config, steps 2-4 are all threaded."""
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

        opener_subject = "Resource planning for teams"
        for entry in mapping:
            step_vars = {
                "subject": opener_subject,
                "opener_subject": opener_subject,
            }
            step_info = {"position": entry["position"]}
            self.assertTrue(
                check_subject_matches_the_step(
                    step_vars, step_info, pattern),
                f"step {entry['step_key']} at position "
                f"{entry['position']} should pass with matching subject")

    def test_four_step_empty_subject_on_threaded_step_fails(self):
        """An empty subject on a threaded step is a fault, not correct."""
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
        _, pattern, _ = read_step_mapping(config)

        for position in (2, 3, 4):
            step_vars = {
                "subject": "",
                "opener_subject": "Resource planning for teams",
            }
            step_info = {"position": position}
            self.assertFalse(
                check_subject_matches_the_step(
                    step_vars, step_info, pattern),
                f"empty subject at position {position} should fail")


if __name__ == "__main__":
    unittest.main()
