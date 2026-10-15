"""A suite that ran zero tests is never a PASS.

THE THIRD INSTANCE OF ONE DEFECT. This repository has now produced the same
shape three times, and the shape is **a control that cannot fail**:

  1. `test_invariants`' allowlist exempted 258 of 258 files, so the invariant
     check passed while watching nothing.
  2. `executionguard.CAPS_ENFORCED_ELSEWHERE` acknowledged ceilings the plan
     never named, so a cap could pass on silence.
  3. `run_suite.classify` returned PASS for a log reading `Ran 0 tests` / `OK`,
     because `_RAN` only answers "did the runner finish" and `Ran 0 tests`
     answers that with yes. Exit code 0, no parsed failures, every condition
     satisfied - a green suite that proved nothing.

The same day, `run_suite.py -v` made argparse exit **having run nothing at
all**, and the invocation was reported as a success by its caller. `-v` is not
a flag this script accepts; it passes `-v` to `unittest` internally. That is
the reason `classify` must assert a COUNT and never trust an exit code.

STANDING RULE, recorded here because a rule in prose is a rule nobody runs:
**the log is the authority, never the exit code.**

WHAT THIS FILE IS. The mutation control on that assertion. `test_zero_tests_is_not_a_pass`
is the guard; `test_the_count_assertion_is_what_refuses_it` proves the guard is
load-bearing by removing it and requiring the verdict to go back to PASS. A
test that still passes with the control stubbed out is not a test, which is the
lesson of instance 1 above.
"""
import unittest
from unittest import mock

import importlib.util
import os


def _load_run_suite():
    """Import `scripts/run_suite.py` by path.

    It is a script rather than a module under `src/`, so a plain import does
    not reach it. Loaded by spec so this test exercises the REAL file the
    operator runs, not a copy of its logic.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "scripts", "run_suite.py")
    spec = importlib.util.spec_from_file_location("_run_suite_under_test",
                                                  path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_suite = _load_run_suite()


EMPTY_BUT_OK = """test suite starting
----------------------------------------------------------------------
Ran 0 tests in 0.000s

OK
"""

REAL_AND_OK = """test_something (tests.test_x.X.test_something) ... ok
----------------------------------------------------------------------
Ran 1 test in 0.001s

OK
"""

DIED_EARLY = """test_something (tests.test_x.X.test_something) ... ok
"""


class TheCountComesFromTheLog(unittest.TestCase):
    """`ran_count` reads the runner's own line and nothing else."""

    def test_it_reads_the_number(self):
        self.assertEqual(run_suite.ran_count(EMPTY_BUT_OK), 0)
        self.assertEqual(run_suite.ran_count(REAL_AND_OK), 1)

    def test_absent_and_zero_are_different_answers(self):
        """Both refuse a verdict, but they are different faults."""
        self.assertIsNone(run_suite.ran_count(DIED_EARLY))
        self.assertEqual(run_suite.ran_count(EMPTY_BUT_OK), 0)

    def test_a_large_count_is_read_whole(self):
        """Not a prefix. `Ran 1646 tests` is 1646, never 1 or 164."""
        self.assertEqual(
            run_suite.ran_count("Ran 1646 tests in 2100.0s\n"), 1646)


class ZeroTestsIsNotAPass(unittest.TestCase):
    """The guard itself."""

    def test_zero_tests_is_not_a_pass(self):
        verdict = run_suite.classify(EMPTY_BUT_OK, exit_code=0,
                                     timed_out=False, failures=[])
        self.assertNotEqual(verdict, "PASS")
        self.assertEqual(verdict, "INCOMPLETE")

    def test_one_real_test_still_passes(self):
        """Or the guard is a ban rather than a check."""
        self.assertEqual(
            run_suite.classify(REAL_AND_OK, exit_code=0, timed_out=False,
                               failures=[]),
            "PASS")

    def test_a_log_with_no_ran_line_is_still_incomplete(self):
        """The older half of the check, which this change must not break."""
        self.assertEqual(
            run_suite.classify(DIED_EARLY, exit_code=0, timed_out=False,
                               failures=[]),
            "INCOMPLETE")

    def test_a_timeout_still_wins_over_everything(self):
        self.assertEqual(
            run_suite.classify(REAL_AND_OK, exit_code=0, timed_out=True,
                               failures=[]),
            "INCOMPLETE")

    def test_real_failures_still_fail(self):
        self.assertEqual(
            run_suite.classify(REAL_AND_OK, exit_code=1, timed_out=False,
                               failures=["FAIL: tests.test_x.X.test_y"]),
            "FAIL")


class TheCountAssertionIsWhatRefusesIt(unittest.TestCase):
    """The mutation control. Remove the assertion and PASS comes back.

    `ran_count` is patched to answer as it did before the fix - a truthy
    number regardless of the log - which is exactly what `classify` saw when
    the count was not consulted at all.
    """

    def test_the_count_assertion_is_what_refuses_it(self):
        stub = mock.Mock(return_value=1)
        with mock.patch.object(run_suite, "ran_count", stub):
            # THE MUTATION APPLIED. Asserted before any conclusion is drawn,
            # because a patch that no-ops looks exactly like a pass.
            self.assertEqual(run_suite.ran_count(EMPTY_BUT_OK), 1)
            verdict = run_suite.classify(EMPTY_BUT_OK, exit_code=0,
                                         timed_out=False, failures=[])
        self.assertTrue(stub.called,
                        "classify never consulted ran_count, so the guard is "
                        "not where this test thinks it is")
        self.assertEqual(
            verdict, "PASS",
            "with the count assertion removed an empty run did NOT come back "
            "as PASS, so something else was refusing it and the guard above "
            "proves nothing")

    def test_and_the_assertion_is_back_afterwards(self):
        """A leaked patch would make every later run in this process lie."""
        self.assertEqual(run_suite.ran_count(EMPTY_BUT_OK), 0)
        self.assertEqual(
            run_suite.classify(EMPTY_BUT_OK, exit_code=0, timed_out=False,
                               failures=[]),
            "INCOMPLETE")


class TheFlagThatRanNothing(unittest.TestCase):
    """`-v` is not accepted, and that must stay loud rather than silent."""

    def test_v_is_not_a_flag_this_script_takes(self):
        """It passes -v to unittest itself; accepting it here would imply
        otherwise. argparse must REJECT it rather than ignore it."""
        parser = run_suite.build_parser()
        with self.assertRaises(SystemExit) as caught:
            parser.parse_args(["-v"])
        # Non-zero, so a caller reading the exit code sees the failure.
        self.assertNotEqual(caught.exception.code, 0)

    def test_the_flags_it_does_take_still_parse(self):
        args = run_suite.build_parser().parse_args(["--offline", "--no-lock"])
        self.assertTrue(args.offline)
        self.assertTrue(args.no_lock)


if __name__ == "__main__":
    unittest.main()
