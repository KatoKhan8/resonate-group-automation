"""A differ read 228 failures as eleven fixed, and exited 0.

MEASURED 2026-10-16, TASK-0300, against `scripts/suite_verdict.txt` at
`status=FAIL`, `failures=228`, 228 name lines. `scripts/task123_diff_failures.py`
printed `Current failures: 1`, `FIXED (11)`, `STILL RED (0)`. Three defects:

* its extractor required a line to END in a parenthesis, which a verdict's
  `  FAIL: dotted.name` lines never do, so the only "name" it ever found was
  the text inside `result_line`'s brackets;
* it compared `tests.`-prefixed baseline names against unprefixed verdict
  names, so even a correct extractor would have called all eleven fixed;
* a verdict it could not read yielded an empty set, and an empty set printed
  "No failures found - suite may have passed!" and returned 0.

The third is the one these tests exist for, and it is the house rule stated
in CLAUDE.md: missing evidence is never positive evidence. A TIMED-OUT verdict
carries no `result_line` at all, because `run_suite._find_result_line` searches
only the last 30 lines - so the reassuring printing was reachable from the one
input where it was most expensive.

WHAT IS ASSERTED HERE IS BEHAVIOUR, never the text of the source: every case
builds a verdict on disk in `run_suite`'s own shape and reads back the returned
name-set or the exception. The exit-code contract is `src/stopwatchdog.py`'s -
0 PASS, 1 STOP, 2 BLIND - for the reason that file gives: an answer this
script has not understood must never read as a pass.
"""
import importlib.util
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    # The script imports its sibling `suite_baseline`, which is not a package,
    # so scripts/ has to be importable before the module body runs.
    scripts = os.path.join(ROOT, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "_t123_differ", os.path.join(scripts, "task123_diff_failures.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HEADER = ("status=%(status)s\n"
          "exit_code=%(exit_code)s\n"
          "wall_seconds=12.5\n"
          "timed_out=%(timed_out)s\n"
          "log_file=C:\\x\\scripts\\suite_run.log\n"
          "results_reached=%(reached)s\n"
          "failures=%(failures)s\n"
          "failures_are_partial=%(partial)s\n")


def verdict(names=(), failures=None, status="FAIL", partial="False",
            timed_out="False", result_line="FAILED (failures=1, errors=0)",
            reached=100, extra=""):
    """A verdict in `run_suite.build_verdict`'s shape, as text."""
    body = HEADER % dict(status=status, exit_code=1 if status == "FAIL" else 0,
                         timed_out=timed_out, reached=reached,
                         failures=len(names) if failures is None else failures,
                         partial=partial)
    if result_line:
        body += "result_line=%s\n" % result_line
    body += extra
    for kind, name in names:
        body += "  %s: %s\n" % (kind, name)
    return body


class _OnDisk(unittest.TestCase):
    """Writes a verdict into a throwaway tree and reads it back."""

    def setUp(self):
        self.differ = _load()
        self.tmp = tempfile.mkdtemp(prefix="t0300-")

    def read(self, text):
        path = os.path.join(self.tmp, "suite_verdict.txt")
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.differ.extract_failures_from_verdict(path)

    def refusal(self, text):
        with self.assertRaises(self.differ.CannotRead) as caught:
            self.read(text)
        return str(caught.exception)


class AVerdictItCannotReadIsNeverZero(_OnDisk):
    """The defect, in all four shapes it can arrive in."""

    def test_a_timed_out_verdict_is_refused_and_names_the_partial_state(self):
        """THE EXPENSIVE CASE. A killed run has no `result_line` at all.

        The old code found no line ending in `)`, concluded zero failures and
        printed that the suite may have passed. The partial state has to be
        named, not swallowed: the names a killed run did print cover only the
        tests it reached, so every test it never ran would read as FIXED.
        """
        text = verdict(names=[("FAIL", "test_x.C.t")], failures=1,
                       status="INCOMPLETE", partial="True", timed_out="True",
                       result_line="")
        reason = self.refusal(text)
        self.assertIn("did not finish", reason)
        self.assertIn("INCOMPLETE", reason)

    def test_failures_are_partial_alone_is_enough_to_refuse(self):
        """`status=FAIL` with a partial list is still a partial list.

        The two keys are written independently by `run_suite.build_verdict`,
        so neither may be the only one read.
        """
        reason = self.refusal(
            verdict(names=[("FAIL", "test_x.C.t")], failures=1,
                    partial="True"))
        self.assertIn("partial", reason.lower())

    def test_a_missing_key_is_refused_by_name(self):
        """A key that is absent is not a key whose value is zero."""
        for key in ("status", "failures", "failures_are_partial"):
            with self.subTest(key=key):
                text = verdict(names=[("FAIL", "test_x.C.t")], failures=1)
                broken = text.replace(key + "=", "renamed_" + key + "=", 1)
                self.assertIn(key, self.refusal(broken))

    def test_a_declared_count_that_disagrees_with_the_names_is_refused(self):
        """Two authorities for one number, so neither is used."""
        reason = self.refusal(
            verdict(names=[("FAIL", "test_x.C.t")], failures=228))
        self.assertIn("228", reason)
        self.assertIn("1", reason)

    def test_a_verdict_with_no_name_lines_but_a_nonzero_count_is_refused(self):
        """The 2026-10-16 shape exactly: 228 declared, 0 readable."""
        reason = self.refusal(verdict(names=(), failures=228))
        self.assertIn("228", reason)


class ItStillCountsTheFailuresThatAreThere(_OnDisk):
    """The paired direction. A refusing instrument that cannot read a real
    verdict is the same defect pointed the other way."""

    def test_the_names_are_read_from_the_indented_lines(self):
        names = self.read(verdict(names=[
            ("FAIL", "test_a.C.t_one"),
            ("ERROR", "test_b.D.t_two"),
            ("FAIL", "test_c.E.t_three")]))
        self.assertEqual(
            {"test_a.C.t_one", "test_b.D.t_two", "test_c.E.t_three"}, names)

    def test_a_result_line_ending_in_a_parenthesis_is_not_a_test_name(self):
        """The original defect, asserted as behaviour.

        `result_line=FAILED (failures=163, errors=68, ...)` is the only line
        in a real verdict that ends in `)`. It must contribute nothing.
        """
        names = self.read(verdict(
            names=[("FAIL", "test_a.C.t_one")],
            result_line="FAILED (failures=163, errors=68, skipped=19)"))
        self.assertEqual({"test_a.C.t_one"}, names)

    def test_a_genuine_zero_is_an_empty_set_and_not_a_refusal(self):
        self.assertEqual(set(), self.read(
            verdict(names=(), failures=0, status="PASS",
                    result_line="OK (skipped=17)")))

    def test_the_prefix_is_normalised_so_the_baseline_can_be_compared(self):
        """`tests.test_x.C.t` and `test_x.C.t` are ONE test.

        The baseline is spelled with the prefix and a verdict without it, and
        a diff whose two sides spell one test two ways reports every entry as
        both gone and new. `suite_baseline.strip_prefix` is the one place that
        decides this; this test proves the differ goes through it.
        """
        names = self.read(verdict(names=[("FAIL", "tests.test_x.C.t")]))
        self.assertEqual({"test_x.C.t"}, names)

    def test_every_baseline_name_survives_normalisation_unprefixed(self):
        """TASK-088's eleven are all `tests.`-prefixed; the comparison set
        must not be."""
        normalised = {self.differ.suite_baseline.strip_prefix(n)
                      for n in self.differ.TASK088_ELEVEN}
        self.assertEqual(11, len(normalised))
        self.assertFalse([n for n in normalised if n.startswith("tests.")])


class TheExitCodeSaysWhichOfThreeThingsHappened(unittest.TestCase):
    """0 clean, 1 failures present, 2 could not read - and 2 is never 0."""

    def setUp(self):
        self.differ = _load()

    def run_main(self, text):
        tmp = tempfile.mkdtemp(prefix="t0300-main-")
        os.makedirs(os.path.join(tmp, "scripts"))
        with io.open(os.path.join(tmp, "scripts", "suite_verdict.txt"), "w",
                     encoding="utf-8") as fh:
            fh.write(text)
        real = self.differ.__file__
        self.differ.__file__ = os.path.join(tmp, "scripts", "x.py")
        buf = io.StringIO()
        stdout = sys.stdout
        sys.stdout = buf
        try:
            code = self.differ.main()
        finally:
            sys.stdout = stdout
            self.differ.__file__ = real
        return code, buf.getvalue()

    def test_the_three_codes_are_distinct(self):
        self.assertEqual({0, 1, 2}, {self.differ.CLEAN,
                                     self.differ.FAILURES_PRESENT,
                                     self.differ.CANNOT_READ})

    def test_an_unreadable_verdict_exits_two_and_says_so(self):
        code, out = self.run_main(
            verdict(names=(), failures=228, result_line=""))
        self.assertEqual(self.differ.CANNOT_READ, code)
        self.assertIn("REFUSED", out)
        self.assertNotIn("may have passed", out)

    def test_failures_present_exits_one(self):
        code, out = self.run_main(verdict(names=[("FAIL", "test_a.C.t")]))
        self.assertEqual(self.differ.FAILURES_PRESENT, code)
        self.assertIn("Current failures: 1", out)

    def test_a_positively_established_zero_exits_zero(self):
        code, out = self.run_main(
            verdict(names=(), failures=0, status="PASS",
                    result_line="OK (skipped=17)"))
        self.assertEqual(self.differ.CLEAN, code)
        self.assertIn("positively established", out)

    def test_a_still_red_baseline_name_is_reported_as_still_red(self):
        """End to end: a baseline name in the verdict, spelled the verdict's
        way, comes out under STILL RED rather than under FIXED."""
        one = sorted(self.differ.TASK088_ELEVEN)[0]
        unprefixed = self.differ.suite_baseline.strip_prefix(one)
        code, out = self.run_main(verdict(names=[("FAIL", unprefixed)]))
        self.assertEqual(self.differ.FAILURES_PRESENT, code)
        self.assertIn("STILL RED (1)", out)
        self.assertIn("FIXED (10)", out)

    def test_the_report_is_printable_on_a_non_utf8_console(self):
        """It died at the FIXED list with a UnicodeEncodeError.

        `sys.stdout.encoding` on the operator's machine is cp1250, which has
        no U+2713, so the report stopped two thirds of the way through and the
        SUMMARY was never reached. Every byte it prints has to survive the
        narrowest codec in play.
        """
        _code, out = self.run_main(verdict(names=[("FAIL", "test_a.C.t")]))
        out.encode("cp1250")
        self.assertIn("SUMMARY", out)


class TheLogFallbackIsAlsoFailClosed(unittest.TestCase):
    """`suite_run.log` is read only when it shows a FINISHED run."""

    def setUp(self):
        self.differ = _load()
        self.tmp = tempfile.mkdtemp(prefix="t0300-log-")

    def read(self, text):
        path = os.path.join(self.tmp, "suite_run.log")
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.differ.extract_failures_from_log(path)

    FINISHED = ("======================================================\n"
                "FAIL: test_t (tests.test_x.C.test_t)\n"
                "------------------------------------------------------\n"
                "Traceback (most recent call last):\n"
                "AssertionError\n"
                "\n"
                "------------------------------------------------------\n"
                "Ran 3 tests in 0.1s\n"
                "\n"
                "FAILED (failures=1)\n")

    def test_a_finished_log_is_read(self):
        self.assertEqual({"test_x.C.test_t"}, self.read(self.FINISHED))

    def test_a_log_with_no_ran_line_is_refused(self):
        killed = self.FINISHED.split("Ran 3 tests")[0]
        with self.assertRaises(self.differ.CannotRead) as caught:
            self.read(killed)
        self.assertIn("did not finish", str(caught.exception))

    def test_a_log_truncated_after_the_ran_line_is_refused(self):
        truncated = self.FINISHED.replace("FAILED (failures=1)\n", "")
        with self.assertRaises(self.differ.CannotRead) as caught:
            self.read(truncated)
        self.assertIn("terminal", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
