"""A watchdog kill must read as INCOMPLETE, never as a pass and never as zero.

MEASURED, 2026-10-01, on master 10a38310. `scripts/run_suite.py --timeout 20`
wrote this whole verdict file:

    exit_code=124
    wall_seconds=20.0
    timed_out=True
    log_file=...

There is no `failures=` line, because `_find_failures` looks only for the
`FAIL: name (dotted.path)` blocks unittest prints in its CLOSING summary, and
on a watchdog kill that summary is never reached. Anything reading the verdict
for a failure count finds no count and reads zero. On a real truncated log of
1,129 reached results `_find_failures` returned 0 while the SAME log named 6
failing tests in its inline verbose lines.

So the verdict was blind exactly when it mattered: the base suite on d98c83ce
exited 124 at 2700s with 227 failing tests in the log, and
`grep -cE '^(FAIL|ERROR): '` over that log returned 0.

Two things are asserted here, and neither is cosmetic:

  * a timed-out run reports `status=INCOMPLETE` and never `PASS`, so a reader
    cannot mistake an unfinished run for a green one;
  * the failures the run DID reach before the kill are named, parsed from the
    inline `... FAIL` / `... ERROR` lines, which are the only evidence that
    survives a timeout - and the count is marked PARTIAL, because a partial
    count silently compared against a full baseline invents fixes.

The watchdog default is also pinned at 3600s, the approved figure. The run
that produced the 227-failure baseline was killed at 2700s with the suite
nearly finished; an 1800s default guarantees the blind case on every run.
"""
import importlib.util
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_SUITE = os.path.join(ROOT, "scripts", "run_suite.py")


def load_run_suite():
    spec = importlib.util.spec_from_file_location("run_suite_under_test",
                                                  RUN_SUITE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: A log shaped exactly like a watchdog kill: verbose per-test lines, three of
#: them losing, and then NOTHING - no `Ran N tests`, no `FAILED (...)`, no
#: closing `FAIL:` block. Every name here is invented for this test.
TIMED_OUT_LOG = (
    "network blocked: socket\n"
    "running the full suite offline\n"
    "\n"
    "test_one (tests.test_widget_seal.TheSeal.test_one) ... ok\n"
    "test_two (tests.test_widget_seal.TheSeal.test_two) ... FAIL\n"
    "test_three (tests.test_widget_seal.TheSeal.test_three) ... ERROR\n"
    "test_four (tests.test_sprocket_guard.TheGuard.test_four) ... ok\n"
    "test_five (tests.test_sprocket_guard.TheGuard.test_five)\n"
    "The docstring unittest prints when a test has one, which pushes the\n"
    "verdict onto a later line ... FAIL\n"
    "test_six (tests.test_sprocket_guard.TheGuard.test_six) ... ok\n"
    "\n\nTIMEOUT after 3600s\n"
)

#: The same suite having actually FINISHED, so the closing summary exists.
COMPLETED_LOG = (
    "test_one (tests.test_widget_seal.TheSeal.test_one) ... ok\n"
    "test_two (tests.test_widget_seal.TheSeal.test_two) ... FAIL\n"
    "\n"
    "======================================================================\n"
    "FAIL: test_two (tests.test_widget_seal.TheSeal.test_two)\n"
    "----------------------------------------------------------------------\n"
    "Traceback (most recent call last):\n"
    "AssertionError: invented\n"
    "\n"
    "----------------------------------------------------------------------\n"
    "Ran 2 tests in 0.01s\n"
    "\nFAILED (failures=1)\n"
)

GREEN_LOG = (
    "test_one (tests.test_widget_seal.TheSeal.test_one) ... ok\n"
    "\n"
    "----------------------------------------------------------------------\n"
    "Ran 1 test in 0.01s\n"
    "\nOK\n"
)


def _tmp(name):
    return os.path.join(os.environ.get("TEMP") or "/tmp",
                        "%s-%d.log" % (name, os.getpid()))


class ATimedOutLogStillNamesWhatItReached(unittest.TestCase):
    """The failures a killed run DID observe are evidence, not noise."""

    def setUp(self):
        self.rs = load_run_suite()
        self.path = _tmp("timed-out-suite")
        with io.open(self.path, "w", encoding="utf-8") as fh:
            fh.write(TIMED_OUT_LOG)
        self.addCleanup(self._rm, self.path)

    @staticmethod
    def _rm(path):
        if os.path.exists(path):
            os.remove(path)

    def test_the_three_losing_tests_in_a_killed_run_are_named(self):
        """0 is the wrong answer about a log that holds three failures."""
        found = self.rs._find_failures(self.path)
        blob = "\n".join(found)
        self.assertEqual(
            3, len(found),
            "a timed-out log naming three losing tests parsed as %d. The "
            "closing FAIL: blocks never print on a watchdog kill, so the "
            "inline `... FAIL` lines are the only surviving evidence and must "
            "be read. Got: %r" % (len(found), found))
        self.assertIn("test_widget_seal.TheSeal.test_two", blob)
        self.assertIn("test_widget_seal.TheSeal.test_three", blob)
        # the one whose verdict landed on a later line because of a docstring
        self.assertIn("test_sprocket_guard.TheGuard.test_five", blob)

    def test_a_passing_test_is_never_counted_as_a_failure(self):
        """The positive control: three lose, and the three winners are clean."""
        blob = "\n".join(self.rs._find_failures(self.path))
        for winner in ("TheSeal.test_one", "TheGuard.test_four",
                       "TheGuard.test_six"):
            self.assertNotIn(
                winner, blob,
                "%s passed and was reported as failing:\n%s"
                % (winner, blob))

    def test_a_finished_run_is_not_double_counted(self):
        """A completed log carries BOTH markers for the same test.

        One failing test is one entry, whichever marker named it. Reading the
        inline lines as well as the summary blocks must not turn one failure
        into two - a doubled baseline reports every merge as a regression.
        """
        done = _tmp("completed-suite")
        with io.open(done, "w", encoding="utf-8") as fh:
            fh.write(COMPLETED_LOG)
        self.addCleanup(self._rm, done)
        found = self.rs._find_failures(done)
        self.assertEqual(1, len(found),
                         "one failing test counted as %d: %r"
                         % (len(found), found))


class AKilledRunIsIncompleteNotAPass(unittest.TestCase):
    """The verdict file must say so in a word a reader cannot misread."""

    def setUp(self):
        self.rs = load_run_suite()
        self.path = _tmp("verdict-src")
        self.addCleanup(self._rm, self.path)

    @staticmethod
    def _rm(path):
        if os.path.exists(path):
            os.remove(path)

    def _verdict(self, text, exit_code, timed_out):
        with io.open(self.path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.rs.build_verdict(self.path, exit_code, 3600.0, timed_out)

    def test_a_timeout_is_labelled_incomplete(self):
        v = self._verdict(TIMED_OUT_LOG, 124, True)
        self.assertIn("status=INCOMPLETE", v,
                      "a watchdog kill produced a verdict with no INCOMPLETE "
                      "status:\n" + v)

    def test_a_timeout_never_claims_a_pass(self):
        v = self._verdict(TIMED_OUT_LOG, 124, True)
        self.assertNotIn("status=PASS", v, v)

    def test_a_timeout_never_reports_zero_failures(self):
        """Silence read as zero. That reading must now be impossible."""
        v = self._verdict(TIMED_OUT_LOG, 124, True)
        self.assertNotIn("failures=0", v,
                         "a killed run reported zero failures:\n" + v)
        self.assertIn("failures=3", v,
                      "the three failures the run did reach are missing from "
                      "the verdict:\n" + v)
        self.assertIn("failures_are_partial=True", v,
                      "a partial count that does not say it is partial gets "
                      "compared against a full baseline:\n" + v)

    def test_a_finished_failing_run_is_complete_and_failed(self):
        """INCOMPLETE must mean 'killed', not merely 'red'."""
        v = self._verdict(COMPLETED_LOG, 1, False)
        self.assertIn("status=FAIL", v, v)
        self.assertNotIn("status=INCOMPLETE", v, v)
        self.assertIn("failures_are_partial=False", v, v)

    def test_a_finished_green_run_passes(self):
        """The other direction: the honest parser must still permit a pass."""
        v = self._verdict(GREEN_LOG, 0, False)
        self.assertIn("status=PASS", v, v)
        self.assertIn("failures=0", v, v)


class TheWatchdogIsThirtySixHundredSeconds(unittest.TestCase):
    """The approved figure, pinned where it is actually read."""

    def test_the_default_timeout_is_3600(self):
        rs = load_run_suite()
        self.assertEqual(
            3600, rs.DEFAULT_TIMEOUT,
            "the watchdog default is %s. The base suite needed more than "
            "2700s and was killed at it; a lower default guarantees the "
            "blind timeout case on every run." % (rs.DEFAULT_TIMEOUT,))

    def test_the_cli_default_is_the_same_number(self):
        """A constant nobody wired to argparse changes nothing."""
        rs = load_run_suite()
        self.assertEqual(3600, rs.build_parser().parse_args([]).timeout)


if __name__ == "__main__":
    unittest.main()
