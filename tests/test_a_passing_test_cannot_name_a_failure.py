"""A passing test's own stdout must not become a recorded failing name.

MEASURED 2026-10-17 at 9a5869a20 (scripts/run_suite.py blob
386336ee66352c2561f4a57205fedcb46ddd45c2). Two shapes are pinned here, and
each log below is the byte-for-byte output of a real run of a synthetic module
whose single test PASSES and prints:

  pass 1, `_SUMMARY`  a line that STARTS with `FAIL:`/`ERROR:`/
                      `UNEXPECTED SUCCESS:` after stripping. Applied at
                      `line.strip()`, so indentation is no defence either.
  pass 2, `_INLINE_VERDICT`  the token matched wherever it sits on the line, so
                      `name (dotted.path) ... ERROR: refused` - a token in the
                      middle of a sentence - records a name.

Both fired on a green run: `_parse_failures` returned a name no test failed,
and `build_verdict` then wrote `status=FAIL  failures=1` under a log ending
`OK`. That is scoring a passing test as a failure, and every "zero new failing
names" number this estate quotes comes through this parser.

The repair this file pins: a closing-summary marker line counts only where
unittest writes one - directly under its separator line of `=` - and a
RECORDABLE verdict is the last thing on its line, because the result object
writes it with `writeln`.

WHAT THIS FILE DOES NOT CLAIM, because the fixtures say it is still open: a
printed line that EXACTLY imitates unittest - `name (dotted.path) ... FAIL`,
token at end of line - is byte-identical to unittest's own output and is still
recorded. `test_an_end_of_line_token_is_still_read` asserts that hole stays
open rather than leaving a reader to assume this file closed it.
"""
import importlib.util
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_SUITE = os.path.join(ROOT, "scripts", "run_suite.py")


def load_run_suite():
    spec = importlib.util.spec_from_file_location("run_suite_under_test",
                                                  RUN_SUITE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: `py -3 -B -m unittest fx_a1a_summary_fail -v` with stdout and stderr on the
#: same file object, the way run_suite.py hands them to the child. The run is
#: green - `Ran 1 test`, no `FAILED`, `OK` - and the last line is the passing
#: test's own print(). Position is not the defence: pass 1 reads the whole log.
PRINTED_SUMMARY_LOG = (
    "test_passes_but_prints_a_summary_block_line "
    "(fx_a1a_summary_fail.FxA1a.test_passes_but_prints_a_summary_block_line)"
    " ... ok\n"
    "\n"
    "----------------------------------------------------------------------\n"
    "Ran 1 test in 0.000s\n"
    "\n"
    "OK\n"
    "FAIL: test_fake (fx_a1a_summary_fail.FxA1a.test_fake)\n"
)

#: The same shape from `fx_d0_midline_error`: the printed line carries both the
#: name and a recording token, with text after the token.
PRINTED_MIDLINE_LOG = (
    "test_prints_a_verdict_token_mid_line "
    "(fx_d0_midline_error.FxD0.test_prints_a_verdict_token_mid_line) ... ok\n"
    "\n"
    "----------------------------------------------------------------------\n"
    "Ran 1 test in 0.000s\n"
    "\n"
    "OK\n"
    "test_fake (fx_d0_midline_error.FxD0.test_fake) ... ERROR: refused\n"
)

#: The same line with the token moved to the end. Nothing about the line is
#: unittest's except its position, and it is still read. Invented log.
PRINTED_EOL_LOG = PRINTED_MIDLINE_LOG.replace(
    "... ERROR: refused", "... ERROR")

#: A finished run that really failed, so a tightening cannot pass this file by
#: refusing everything.
GENUINE_SUMMARY_LOG = (
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

#: A killed run: no closing summary at all, so the inline lines are the only
#: evidence - including one whose verdict landed two lines below its name.
GENUINE_INLINE_LOG = (
    "test_two (tests.test_widget_seal.TheSeal.test_two) ... FAIL\n"
    "test_three (tests.test_widget_seal.TheSeal.test_three)\n"
    "The docstring unittest prints when a test has one, and then\n"
    "a second line of it before the verdict ... ERROR\n"
)

PRINTING_MODULE = '''\
import unittest


class PrintsItsOwnSummaryLine(unittest.TestCase):

    def test_passes_but_prints_a_failing_summary_line(self):
        print("FAIL: test_fake (prints_a_summary_line.Phantom.test_fake)")
        self.assertTrue(True, "synthetic: this test passes")
'''


def _tmpdir():
    import tempfile
    return tempfile.mkdtemp(prefix="printed-name-")


class APrintedSummaryLineIsNotAFailure(unittest.TestCase):

    def setUp(self):
        self.rs = load_run_suite()

    def test_the_log_really_is_a_green_run(self):
        """Asserted before the parser is asked anything: exit 0, no FAILED."""
        self.assertIn("Ran 1 test in", PRINTED_SUMMARY_LOG)
        self.assertIn("\nOK\n", PRINTED_SUMMARY_LOG)
        self.assertNotIn("FAILED", PRINTED_SUMMARY_LOG)
        self.assertNotIn("\n======================================================================\n",
                         PRINTED_SUMMARY_LOG)

    def test_a_printed_summary_line_names_nothing(self):
        found = self.rs._parse_failures(PRINTED_SUMMARY_LOG)
        self.assertEqual(
            [], found,
            "a green run whose test printed one line parsed as %r. The "
            "printed line is not evidence about any test." % (found,))

    def test_a_genuine_summary_block_is_still_read(self):
        """The positive control: refusing everything is not a repair."""
        found = self.rs._parse_failures(GENUINE_SUMMARY_LOG)
        self.assertEqual(
            ["FAIL: tests.test_widget_seal.TheSeal.test_two"], found,
            "the closing `FAIL:` block under its `======` separator is the "
            "authority for a finished run and must still be read. Got: %r"
            % (found,))

    def test_a_genuine_inline_verdict_is_still_read(self):
        """The other control: a killed run's only evidence, docstring and all.

        The verdict here is two lines below its name line, which is what a
        docstring does to the description block. A rule that bounds how far a
        name may reach forward would drop this failure.
        """
        found = self.rs._parse_failures(GENUINE_INLINE_LOG)
        self.assertEqual(
            ["ERROR: tests.test_widget_seal.TheSeal.test_three",
             "FAIL: tests.test_widget_seal.TheSeal.test_two"], found,
            "a killed run's inline verdicts are the only evidence that "
            "survives it. Got: %r" % (found,))


class APrintedMidlineTokenIsNotAFailure(unittest.TestCase):

    def setUp(self):
        self.rs = load_run_suite()

    def test_a_midline_token_names_nothing(self):
        found = self.rs._parse_failures(PRINTED_MIDLINE_LOG)
        self.assertEqual(
            [], found,
            "`... ERROR: refused` is not a verdict: the result object writes "
            "its verdict with `writeln`, so nothing follows the token on a "
            "line it wrote. Got: %r" % (found,))

    def test_an_end_of_line_token_is_still_read(self):
        """The boundary, asserted so it cannot be mistaken for closed.

        The same printed line with the token at the end is indistinguishable
        from unittest's own bytes and IS recorded. This file does not fix
        that; it records where the fix stops.
        """
        found = self.rs._parse_failures(PRINTED_EOL_LOG)
        self.assertEqual(
            ["ERROR: fx_d0_midline_error.FxD0.test_fake"], found,
            "an end-of-line token on a name line is still read - that is the "
            "open hole, and this assertion is its record. Got: %r" % (found,))


class TheShapeIsLiveNotJustRecorded(unittest.TestCase):
    """A real subprocess, so the log is produced, not asserted."""

    def setUp(self):
        self.rs = load_run_suite()
        self.dir = _tmpdir()
        self.addCleanup(self._rmtree, self.dir)
        with io.open(os.path.join(self.dir, "prints_a_summary_line.py"), "w",
                     encoding="utf-8") as fh:
            fh.write(PRINTING_MODULE)
        self.log = os.path.join(self.dir, "run.log")

    @staticmethod
    def _rmtree(path):
        import shutil
        shutil.rmtree(path, ignore_errors=True)

    def _run(self):
        with open(self.log, "w") as fh:
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "unittest",
                 "prints_a_summary_line", "-v"],
                stdout=fh, stderr=fh, cwd=self.dir, timeout=120)
        with open(self.log, "r", errors="replace") as fh:
            return proc.returncode, fh.read()

    def test_a_green_run_is_verdicted_green(self):
        rc, text = self._run()
        self.assertEqual(0, rc, text)
        self.assertIn("\nOK\n", text, text)
        verdict = self.rs.build_verdict(self.log, rc, 1.0, False)
        self.assertIn("failures=0", verdict, verdict)
        self.assertIn("status=PASS", verdict, verdict)
        self.assertNotIn("status=FAIL", verdict, verdict)


if __name__ == "__main__":
    unittest.main()
