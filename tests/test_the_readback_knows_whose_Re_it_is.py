"""`bison_readback` compared raw subjects and failed correct campaigns.

EmailBison prepends "Re: " itself on a `thread_reply` step. The readback did
not know that, so it reported

    step_2_subject   {SUBJECT_1}   Re: {SUBJECT_1}   ** FAIL **

on campaigns 487 and 489 - both correct, both PASS under
`configdiff.compare_bison` in the same minute. This readback is the COMPARE
half of WRITE -> READ BACK -> COMPARE -> RECONCILE, so a spurious FAIL is not
cosmetic: it teaches an operator to ignore the verdict, or blocks a valid
activation.

The fix imports `bisonfactory._comparable_step` rather than re-deriving the
rule. These tests exist for the three cases a re-derivation gets wrong, and
they matter more than the case that now passes.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from src.bisonfactory import _comparable_step  # noqa: E402


def compares_equal(expected_subject, observed_subject, expected_tr,
                   observed_tr=None):
    """The readback's subject verdict, through the shared normalisation."""
    observed_tr = expected_tr if observed_tr is None else observed_tr
    exp, _, _ = _comparable_step(expected_subject, "<p>x</p>", bool(expected_tr))
    obs, _, _ = _comparable_step(observed_subject, "<p>x</p>", bool(observed_tr))
    return exp == obs


class TestTheProvidersOwnPrefixIsNotDrift(unittest.TestCase):
    def test_a_threaded_follow_up_wearing_the_providers_Re_matches(self):
        self.assertTrue(compares_equal("{SUBJECT_1}", "Re: {SUBJECT_1}",
                                       expected_tr=True))

    def test_the_opener_matches_itself_untouched(self):
        self.assertTrue(compares_equal("{SUBJECT_1}", "{SUBJECT_1}",
                                       expected_tr=False))


class TestWhatMustStillFail(unittest.TestCase):
    """Three ways to get this wrong, and the normalisation must catch all of
    them. A helper that strips "Re: " unconditionally passes the first two and
    is the exact defect campaign 485 carried."""

    def test_a_follow_up_wearing_a_DIFFERENT_subject_under_its_Re(self):
        """`Re: {SUBJECT_2}` is a second subject, not a thread continuation.

        This is what 485 held, and why 485 could not be corrected in place.
        Stripping the prefix must not make it look like SUBJECT_1.
        """
        self.assertFalse(compares_equal("{SUBJECT_1}", "Re: {SUBJECT_2}",
                                        expected_tr=True))

    def test_a_Re_on_a_step_that_is_not_a_thread_reply(self):
        """The flag licenses the strip, never the text.

        A step with `thread_reply: false` carrying "Re: " opens a NEW thread
        whose subject happens to start with Re:, which is a different message
        to the prospect and must read as drift.
        """
        self.assertFalse(compares_equal("{SUBJECT_1}", "Re: {SUBJECT_1}",
                                        expected_tr=False))

    def test_a_follow_up_that_stopped_being_a_thread_reply(self):
        """Canonical says threaded, the provider says it is not.

        The subjects would compare equal if only the expected side were
        normalised. They must not: the two sides are normalised by their OWN
        flag, so a disagreement about threading shows up in the subject too.
        """
        self.assertFalse(compares_equal("{SUBJECT_1}", "Re: {SUBJECT_1}",
                                        expected_tr=True, observed_tr=False))

    def test_an_entirely_different_subject(self):
        self.assertFalse(compares_equal("{SUBJECT_1}", "Re: something else",
                                        expected_tr=True))


class TestTheScriptUsesTheSharedRuleAndNotACopy(unittest.TestCase):
    def test_bison_readback_imports_the_factorys_normalisation(self):
        """Behaviour, not source text: the name the script holds must BE the
        factory's function, so the two cannot drift."""
        import bison_readback
        from src import bisonfactory
        self.assertIs(bison_readback._comparable_step,
                      bisonfactory._comparable_step)


if __name__ == "__main__":
    unittest.main()
