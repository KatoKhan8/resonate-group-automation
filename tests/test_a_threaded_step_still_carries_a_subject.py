"""A threaded step still carries a subject. TASK-295.

From `bisonfactory._sequence_steps` docstring:
    "A follow-up step STILL CARRIES `email_subject` - the flag is the
    mechanism, not subject omission."

So "step 2 has no subject" is NOT how a threaded step is detected. A check
that treats an empty subject on step 2 as correct threading will pass a step
that sends with no subject line.

THESE TESTS PROVE:
1. A threaded step with a subject PASSES.
2. A threaded step with NO subject FAILS.
3. A threaded step with a DIFFERENT subject from the opener FAILS.
4. The thread_reply flag is the mechanism, not subject omission.
"""
import unittest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.qa import check_lead_copy


class ThreadedStepWithSubjectPasses(unittest.TestCase):
    """A threaded step that carries the same subject as the opener is fine."""

    def test_threaded_step_with_matching_subject_passes(self):
        thread_pattern = (False, True, True, True)
        opener_subject = "Your platform margin, in real time"
        step_data = {"subject": opener_subject, "body": "Some body text."}
        result = check_lead_copy.check_subject_matches(
            step_data, position=2, thread_reply_pattern=thread_pattern,
            opener_subject=opener_subject)
        self.assertTrue(result)

    def test_opener_with_subject_passes(self):
        thread_pattern = (False, True, True, True)
        opener_subject = "Your platform margin"
        step_data = {"subject": opener_subject, "body": "Body."}
        result = check_lead_copy.check_subject_matches(
            step_data, position=1, thread_reply_pattern=thread_pattern,
            opener_subject=opener_subject)
        self.assertTrue(result)


class ThreadedStepWithoutSubjectFails(unittest.TestCase):
    """A threaded step with NO subject FAILS.

    This is the critical test. The old assumption was that threaded steps
    legitimately carry no subject because the provider prepends Re:. That
    is wrong: the provider stores both, and the flag is the mechanism.
    An empty subject on a threaded step means the email sends with no
    subject line, which is the defect ISSUE-025 was about.
    """

    def test_threaded_step_with_empty_subject_fails(self):
        thread_pattern = (False, True, True, True)
        opener_subject = "Your platform margin"
        step_data = {"subject": "", "body": "Some body text."}
        result = check_lead_copy.check_subject_matches(
            step_data, position=2, thread_reply_pattern=thread_pattern,
            opener_subject=opener_subject)
        self.assertFalse(result,
                         "A threaded step with empty subject must FAIL")

    def test_threaded_step_with_none_subject_fails(self):
        thread_pattern = (False, True, True)
        step_data = {"subject": None, "body": "Body."}
        result = check_lead_copy.check_subject_matches(
            step_data, position=3, thread_reply_pattern=thread_pattern,
            opener_subject="Some subject")
        self.assertFalse(result)


class ThreadedStepWithDifferentSubjectFails(unittest.TestCase):
    """A threaded step carrying a DIFFERENT subject from the opener FAILS.

    The threading invariant: only the opener owns a subject. Follow-ups
    carry the SAME subject (the provider renders Re:). A different subject
    on a threaded step violates the invariant.
    """

    def test_different_subject_on_threaded_step_fails(self):
        thread_pattern = (False, True, True)
        opener_subject = "Your platform margin"
        step_data = {"subject": "A completely different subject",
                     "body": "Body."}
        result = check_lead_copy.check_subject_matches(
            step_data, position=2, thread_reply_pattern=thread_pattern,
            opener_subject=opener_subject)
        self.assertFalse(result,
                         "A threaded step with a different subject must FAIL")


class NewThreadStepCarriesOwnSubject(unittest.TestCase):
    """A new-thread step (thread_reply=false) carries its own subject."""

    def test_new_thread_step_with_subject_passes(self):
        thread_pattern = (False, False)
        step_data = {"subject": "My own subject", "body": "Body."}
        result = check_lead_copy.check_subject_matches(
            step_data, position=2, thread_reply_pattern=thread_pattern,
            opener_subject="Different opener subject")
        self.assertTrue(result)

    def test_new_thread_step_without_subject_fails(self):
        thread_pattern = (False, False)
        step_data = {"subject": "", "body": "Body."}
        result = check_lead_copy.check_subject_matches(
            step_data, position=2, thread_reply_pattern=thread_pattern,
            opener_subject="Opener subject")
        self.assertFalse(result)


class SubjectPresentRule(unittest.TestCase):
    """The subject_present rule: non-empty after strip."""

    def test_empty_subject_fails(self):
        step_data = {"subject": "", "body": "body"}
        result = check_lead_copy.check_subject_present(step_data, 1, False)
        self.assertFalse(result)

    def test_whitespace_only_subject_fails(self):
        step_data = {"subject": "   ", "body": "body"}
        result = check_lead_copy.check_subject_present(step_data, 1, False)
        self.assertFalse(result)

    def test_nonempty_subject_passes(self):
        step_data = {"subject": "Hello", "body": "body"}
        result = check_lead_copy.check_subject_present(step_data, 1, False)
        self.assertTrue(result)

    def test_threaded_step_with_subject_passes_subject_present(self):
        """A threaded step with a subject passes the subject_present rule.

        This is the same step as test_threaded_step_with_matching_subject_passes
        but testing the simpler presence check. The point: subject_present
        does not care about threading; it only checks non-empty.
        """
        step_data = {"subject": "Re: something", "body": "body"}
        result = check_lead_copy.check_subject_present(step_data, 2, True)
        self.assertTrue(result)


class EmptyrenderClassifySubjectAgrees(unittest.TestCase):
    """emptyrender.classify_subject already takes thread_reply.

    The check's subject rule must not duplicate it in a way that disagrees.
    An empty subject on a threaded row: classify_subject returns None (fine).
    But our check says FAIL because a threaded step STILL CARRIES a subject.

    THIS IS A DELIBERATE DISAGREEMENT. emptyrender operates on RENDERED ROWS
    at the provider, where an empty subject on a thread_reply row is the
    provider's own storage convention. Our check operates on PRE-PUSH copy,
    where every step must carry a subject because the template references it.
    """

    def test_classify_subject_empty_threaded_returns_none(self):
        """emptyrender says an empty subject on a threaded row is fine."""
        from src import emptyrender
        result = emptyrender.classify_subject("", thread_reply=True)
        self.assertIsNone(result)

    def test_our_check_says_empty_threaded_subject_fails(self):
        """Our pre-push check says the same row fails.

        Different contexts, different answers. The provider row is already
        written; our check runs before the write.
        """
        thread_pattern = (False, True)
        step_data = {"subject": "", "body": "body"}
        result = check_lead_copy.check_subject_matches(
            step_data, position=2, thread_reply_pattern=thread_pattern,
            opener_subject="Opener")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
