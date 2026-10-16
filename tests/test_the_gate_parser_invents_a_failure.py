r"""The gate's parser reads a passing test's own stdout as a failure.

MEASURED 2026-10-16, tree `wt-deepseek-2026-10-16`, on origin/master
`b1f290c84`, against `scripts/run_suite.py` blob `4ca2763b69a5` - md5
`35cda0f7ca9e5e862f50a851bb9f87e8` as this CRLF tree holds it,
`65c50c89ac0e2279fa7178cba251f256` as LF. Nothing here changes that file:
three lanes' recorded numbers went through its current behaviour, so whether
to change it is the operator's decision and not this file's. What this file
does is record the defect as a test, so the day somebody does change it the
change is observable.

## The mechanism, in the file's own words

`_parse_failures` reads a log in two passes.

Pass 1 reads unittest's closing summary and IS anchored - `scripts/run_suite.py:76`:

    _SUMMARY = re.compile(r"^(FAIL|ERROR):\s+\S+\s+\(([^)\s]+)")

applied at line 227 as `_SUMMARY.match(line.strip())`, so the `FAIL:`/`ERROR:`
must be the first thing on the line.

Pass 2 reads the inline verbose lines and is NOT anchored - lines 83-84:

    _INLINE_VERDICT = re.compile(
        r"\.\.\.\s+(ok|FAIL|ERROR|skipped|expected failure|unexpected success)\b")

applied at line 238 as a bare `_INLINE_VERDICT.search(line)`. A search, not a
match, and with no anchor in the pattern either: **the verdict token may sit
anywhere in the line.**

That would be harmless if only unittest wrote those lines. It does not.
`run_suite.py:109-115` hands the child the SAME file object for stdout and
stderr, so everything a test prints lands in the same log, interleaved with
unittest's own writes. And the window is wide: `pending` is opened by the
test's name line (235-237) and closed only when some line holds a verdict
token (242) - and a test with a docstring pushes its real verdict onto a LATER
line, which is exactly why that window exists. Everything a test prints between
its own name and its own verdict is read as though unittest had written it.

## What that costs, measured end to end

The module reproduced below was run for real, `python -m unittest -v`, with
stdout and stderr merged into one file the way `run_suite.py` does it. Exit
code 0. Both tests passed. The log ends `OK`. `_parse_failures` on that log
returns ONE name, and it is the PASSING test. `build_verdict` on the same log
writes:

    status=FAIL
    failures=1
    failures_are_partial=False
    result_line=OK

A green run, reported as a failing one, blaming a test that did nothing. Every
"zero new failing names" verdict this gate has ever produced was computed by
the same code path.

## RED ON PURPOSE

`test_a_green_run_parses_as_green` fails today. It is red because the token is
read out of a passing test's own stdout - not because the fixture is malformed,
and the rest of this file is what establishes the difference:

  * `TheControlsThatGiveTheRedTestItsMeaning` proves the fixture is a green run
    by its own evidence and that a genuine failure is still reported;
  * `test_the_injected_text_is_the_whole_difference...` is the discriminating
    pair: the same log with the printed lines removed reports zero, and with
    them reports one. One difference, two answers.
  * `test_the_same_printed_text_outside_the_window_reports_zero` supplies the
    other half of the mechanism: two real runs of the same module, the same
    printed lines, one where the text lands inside the window and one where
    block buffering puts it below `OK`. One reports a failure and the other
    reports zero, and which one a run gets is decided by buffering.

WHAT MUST CHANGE: the parser must stop treating a line a test printed as a
line unittest wrote. HOW is the operator's call and this file deliberately does
not make it. Two candidate repairs were measured against this fixture and both
are insufficient - end-anchoring because the printed line ENDS with the token
(`test_an_end_anchored_variant_is_not_a_sufficient_repair`), and the closing
summary alone because it does not exist on a killed run, which is the case pass
2 was added for. That narrows the choice rather than making it: nothing here
asserts that any particular repair IS sufficient.

A NOTE ON THIS FILE'S OWN MESSAGES: they do not reprint the fixtures. unittest
echoes an assertion message into the suite log at column 0, which is inside the
same window this file is about - a file documenting that defect must not become
another instance of it. Names and reprs of parsed results are safe; the log
text is not.

A NOTE ON THE GATE, because it is material to whoever integrates this: this
file adds ONE deliberately-failing name until the parser is fixed. This tree's
recorded convention for a finding that asserts the behaviour that should hold
is `@unittest.expectedFailure` (see `MutationsThisGateCannotSee` in
`tests/test_no_activation_without_an_exact_match.py:713-719`), which costs no
baseline name and turns into an UNEXPECTED SUCCESS the day the gap closes. It
was not used here on purpose: under `expectedFailure` a fixture that is
malformed and a parser that is wrong look identical, and a lane report that
cannot tell those two apart is the thing this task exists to end. The operator
can move this one test to `expectedFailure` by adding a single decorator.
"""
import hashlib
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_SUITE = os.path.join(ROOT, "scripts", "run_suite.py")

#: The verbatim bytes of a REAL run:
#:
#:     py -3 -m unittest -v sample_gate_module     # cwd holding that module
#:
#: with stdout and stderr merged into one file object, exactly as
#: `run_suite.py:109-115` does it. Exit code 0. Both tests pass. Nothing is
#: substituted: the only field that varies between regenerations is the
#: wall-clock in `Ran 2 tests in X.XXXs`, which the parser never reads.
#:
#: The module it came from, and it is invented for this file:
#:
#:     import sys, unittest
#:
#:     class SampleSuite(unittest.TestCase):
#:         def test_alpha(self):
#:             """Formats a message, and passes."""
#:             print("checking upstream ... ERROR")
#:             print("formatted: ERROR: widget (sprocket) is broken")
#:             sys.stdout.flush()
#:             self.assertTrue(True)
#:
#:         def test_beta(self):
#:             """Compares two integers, and passes."""
#:             self.assertEqual(2, 1 + 1)
GREEN_LOG_PRINTED = (
    "test_alpha (sample_gate_module.SampleSuite.test_alpha)\n"
    "Formats a message, and passes. ... checking upstream ... ERROR\n"
    "formatted: ERROR: widget (sprocket) is broken\n"
    "ok\n"
    "test_beta (sample_gate_module.SampleSuite.test_beta)\n"
    "Compares two integers, and passes. ... ok\n"
    "\n"
    "----------------------------------------------------------------------\n"
    "Ran 2 tests in 0.000s\n"
    "\n"
    "OK\n"
)

#: The two lines `test_alpha` printed, and nothing else. Note what is in them:
#: the inline verdict shape `... ERROR` that `_INLINE_VERDICT` searches for,
#: AND the closing-summary shape `ERROR: widget (sprocket)` that `_SUMMARY`
#: matches. Both regexes have something to be fooled by; only one of them is.
INJECTED = (
    "checking upstream ... ERROR\n"
    "formatted: ERROR: widget (sprocket) is broken\n"
)

#: The same run with those two lines taken out and nothing else touched. What
#: is left on the docstring line is ` ... ` with the verdict arriving on the
#: next line, which is a shape a real run produces whenever a test flushes
#: between unittest's two writes.
GREEN_LOG_SILENT = GREEN_LOG_PRINTED.replace(INJECTED, "")

#: The verbatim bytes of a SECOND real run of the SAME module, the same way,
#: with ONE difference: `test_alpha` does not flush. `print` to a redirected
#: stdout is block-buffered, so the two lines sit in the buffer until the
#: interpreter exits and are then written after unittest has already finished
#: - below `Ran 2 tests` and below `OK`, outside the window `pending` opens.
#: Exit code 0. Both tests pass. The SAME text is in this log.
GREEN_LOG_BUFFERED = (
    "test_alpha (sample_gate_module.SampleSuite.test_alpha)\n"
    "Formats a message, and passes. ... ok\n"
    "test_beta (sample_gate_module.SampleSuite.test_beta)\n"
    "Compares two integers, and passes. ... ok\n"
    "\n"
    "----------------------------------------------------------------------\n"
    "Ran 2 tests in 0.000s\n"
    "\n"
    "OK\n"
    "checking upstream ... ERROR\n"
    "formatted: ERROR: widget (sprocket) is broken\n"
)

#: A hand-written log in the shape unittest writes, in the style
#: `tests/test_a_timed_out_suite_is_never_reported_as_a_pass.py` established:
#: two verbose results, one genuinely losing, then the closing summary that
#: names the same test again. Both markers describe ONE failure and the parser
#: must count it once. The module name is invented.
ONE_GENUINE_FAILURE = (
    "test_alpha (sample_gate_module.SampleSuite.test_alpha) ... ok\n"
    "test_gamma (sample_gate_module.SampleSuite.test_gamma) ... FAIL\n"
    "\n"
    "======================================================================\n"
    "FAIL: test_gamma (sample_gate_module.SampleSuite.test_gamma)\n"
    "----------------------------------------------------------------------\n"
    "Traceback (most recent call last):\n"
    '  File "tests\\test_sample_gate.py", line 12, in test_gamma\n'
    "    self.assertEqual(1, 2)\n"
    "AssertionError: 1 != 2\n"
    "\n"
    "----------------------------------------------------------------------\n"
    "Ran 2 tests in 0.011s\n"
    "\n"
    "FAILED (failures=1)\n"
)

#: The three compiled patterns whose TEXT is the thing being proven present on
#: disk. Behaviour cannot tell a stale load from a current one when the two
#: agree; the bytes can.
PATTERNS = ("_SUMMARY", "_INLINE_NAME", "_INLINE_VERDICT")


def load_run_suite():
    """The parser this file is about, loaded from the file it lives in."""
    return _load_module_at(RUN_SUITE, "run_suite_under_test")


def _load_module_at(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def patterns_absent_from(path, mod, attrs):
    """Which of `attrs` hold a pattern the bytes at `path` do NOT contain.

    Content, not mtime, and that distinction is load-bearing here.
    `scripts/run_suite.py` is the artefact under measurement, so "the code I
    loaded is the code on disk" is a claim about a `__pycache__` entry until
    the bytes are compared - CPython picks the cache entry by source mtime
    truncated to WHOLE SECONDS and by size. MEASURED 2026-10-16 on this
    machine, CPython 3.14.3, cache tag `cpython-314`: load a copy, rewrite it
    with one character changed and the size held equal, put the original mtime
    back, load again - what came back was the ORIGINAL pattern. The cache
    masked the rewrite. Reading the bytes is what does not mask it.

    An empty list is the honest load: every pattern the module carries is text
    this file actually holds.
    """
    with io.open(path, "rb") as fh:
        raw = fh.read()
    return [a for a in attrs
            if getattr(mod, a).pattern.encode("utf-8") not in raw]


class TheParserInventsAFailureFromAPassingTestsOwnOutput(unittest.TestCase):
    """GREEN_LOG_PRINTED is a green run. The parser must say zero."""

    def setUp(self):
        # Fresh module per test, so the swap in
        # `test_only_the_loose_search_is_what_reads_it` cannot reach a sibling.
        self.rs = load_run_suite()

    def test_a_green_run_parses_as_green(self):
        """RED ON PURPOSE. Fails on the current code, and this is the finding.

        The log is green by its own evidence: exit code 0, `Ran 2 tests`, ends
        `OK`, and both verbose verdicts are `ok`. A parser that reads a run
        truthfully returns no failures for it. On the current code it returns
        one, and the name it blames is the test that PASSED, because that
        test's own stdout carries the inline verdict shape and pass 2 searches
        for it mid-line.

        It is red for that reason and no other - the fixture is a verbatim real
        log, and the tests around this one are the controls that establish the
        difference between a malformed fixture and a wrong parser.
        """
        found = self.rs._parse_failures(GREEN_LOG_PRINTED)
        self.assertEqual(
            [], found,
            "the log is green by its own evidence (exit code 0, `Ran 2 tests`, "
            "`OK`) and the parser named %d failing test(s): %r. A passing "
            "test's own stdout is being read as a verdict: _INLINE_VERDICT is "
            "applied as a bare `.search` (scripts/run_suite.py:238) over a "
            "window opened by the test's name line and closed by anything that "
            "looks like a verdict, and the child's stdout is merged into the "
            "same log the parser reads (109-115). The test it blames passed."
            % (len(found), found))

    def test_the_two_logs_differ_by_only_the_two_lines_the_test_printed(self):
        """The pair below means nothing unless the pair is one change.

        Two unrelated fixtures can give two answers for two unrelated reasons.
        These two are the same run, and the only difference is what the passing
        test printed - asserted by construction, not asserted in prose.
        """
        self.assertNotEqual(GREEN_LOG_PRINTED, GREEN_LOG_SILENT)
        self.assertEqual(GREEN_LOG_SILENT,
                         GREEN_LOG_PRINTED.replace(INJECTED, ""),
                         "the silent log is not the printed log minus the two "
                         "printed lines, so the pair is not a controlled pair")
        self.assertNotIn("ERROR", GREEN_LOG_SILENT,
                         "the silent log still holds ERROR text, so it is not "
                         "the clean log the negative control needs")
        self.assertIn("Ran 2 tests in", GREEN_LOG_SILENT)

    def test_the_injected_text_is_the_whole_difference_between_one_and_zero(self):
        """The discriminating pair: same log, one difference, two answers.

        This PINS the defect, and it is meant to. It passes while the parser
        behaves as measured and MUST be inverted - both halves - on the day the
        parser stops reading a printed line as a verdict. It is here because a
        red test on its own is an assertion; this is the experiment. Two logs
        that differ only in inert printed text cannot honestly produce two
        different answers, and today they do.
        """
        silent = self.rs._parse_failures(GREEN_LOG_SILENT)
        printed = self.rs._parse_failures(GREEN_LOG_PRINTED)
        self.assertEqual(
            [], silent,
            "the clean log already reports %r, so this pair cannot attribute "
            "anything to the printed text" % (silent,))
        self.assertEqual(
            1, len(printed),
            "MEASURED BEHAVIOUR, AND A DEFECT: the log with the passing test's "
            "own stdout reports %d failure(s) %r. When the parser is fixed this "
            "assertion must be changed to 0 together with the red test above - "
            "the pair is the proof and half of it inverting silently would "
            "break it." % (len(printed), printed))

    def test_the_closing_summary_regex_does_not_read_it_as_a_failure(self):
        """_SUMMARY is anchored, and the anchor is what saves it.

        Asserting that the summary pass finds nothing here would be worth
        little on its own - an anchored pattern that is never given the text
        would also find nothing. The second half removes the `^` from the SAME
        pattern and gets a hit on the line the test printed, which is what
        makes this evidence that `_SUMMARY` is correct rather than lucky.
        """
        anchored = [line.strip() for line in GREEN_LOG_PRINTED.splitlines()
                    if self.rs._SUMMARY.match(line.strip())]
        self.assertEqual([], anchored,
                         "_SUMMARY matched a line of a green log: %r" % (anchored,))

        without_the_anchor = re.compile(self.rs._SUMMARY.pattern.replace("^", "", 1))
        loose = [line.strip() for line in GREEN_LOG_PRINTED.splitlines()
                 if without_the_anchor.search(line.strip())]
        self.assertEqual(
            1, len(loose),
            "the same pattern with its `^` removed finds %d line(s) of the "
            "green log, so this fixture does give _SUMMARY something to be "
            "fooled by and the anchor is what stops it. Got: %r"
            % (len(loose), loose))

    def test_the_same_printed_text_outside_the_window_reports_zero(self):
        """The other half of the mechanism: the window, not just the text.

        Two real runs of the same module, same tests, same printed lines. In
        one the test flushes and the text lands between its own name line and
        its own verdict; in the other it does not, the block buffer flushes at
        interpreter exit, and the identical text lands below `OK`. The parser
        reports one failure for the first and zero for the second. So the
        invention needs the text AND the window, and which of the two a run
        gets is decided by buffering - not by the test's author and not by
        anything the test can assert about itself.
        """
        self.assertIn(INJECTED, GREEN_LOG_BUFFERED,
                      "the buffered log does not hold the same printed text, "
                      "so this control is not a control")
        self.assertEqual(
            [], self.rs._parse_failures(GREEN_LOG_BUFFERED),
            "the same printed text outside the window reported %r; if this "
            "file's account of the mechanism is right it can only be zero"
            % (self.rs._parse_failures(GREEN_LOG_BUFFERED),))

        inside = GREEN_LOG_PRINTED.splitlines()
        alpha = [i for i, l in enumerate(inside) if l.startswith("test_alpha (")]
        printed = [i for i, l in enumerate(inside) if "checking upstream" in l]
        beta = [i for i, l in enumerate(inside) if l.startswith("test_beta (")]
        self.assertTrue(
            alpha[0] < printed[0] < beta[0],
            "in the log that invents a failure the printed text is not between "
            "the test's name line and the next test, so `inside the window` is "
            "not what this file means by it: %r" % ([alpha, printed, beta],))

        outside = GREEN_LOG_BUFFERED.splitlines()
        done = [i for i, l in enumerate(outside) if l.strip() == "OK"]
        later = [i for i, l in enumerate(outside) if "checking upstream" in l]
        self.assertTrue(
            later and done and later[0] > done[0],
            "in the buffered log the printed text is not below `OK`, so the "
            "two logs do not differ in the way this control claims: %r"
            % ([done, later],))

    def test_an_end_anchored_variant_is_not_a_sufficient_repair(self):
        """Recorded so the cheap repair is not shipped believing it works.

        Measured while building this file, and it corrected an assumption in
        it: requiring the verdict token to be the LAST thing on the line does
        not help here, because the line the passing test printed ENDS with the
        token. A variant that anchors the search to the end of the line still
        invents the failure. Nothing here asserts what a sufficient repair
        would be - only that this one is not, and the assertion is the
        evidence rather than a claim about it.
        """
        original = self.rs._INLINE_VERDICT
        self.addCleanup(setattr, self.rs, "_INLINE_VERDICT", original)
        self.rs._INLINE_VERDICT = re.compile(
            r"\.\.\.\s+(ok|FAIL|ERROR|skipped|expected failure|"
            r"unexpected success)\s*$")
        try:
            found = self.rs._parse_failures(GREEN_LOG_PRINTED)
        finally:
            self.rs._INLINE_VERDICT = original
        self.assertEqual(
            1, len(found),
            "an end-anchored variant reported %r, so it does NOT invent a "
            "failure here and the note in this file's docstring about it is "
            "wrong" % (found,))


class TheControlsThatGiveTheRedTestItsMeaning(unittest.TestCase):
    """A red test is evidence only if the same reading is right elsewhere."""

    def setUp(self):
        self.rs = load_run_suite()

    def test_the_fixture_is_a_green_run_by_its_own_evidence(self):
        """Before the parser is asked, the log says what it is.

        If this log were a disguised failure, the red test above would be red
        for the wrong reason and would still look identical. So the log's own
        summary is asserted first: two tests ran, the run ended `OK`, nothing
        printed `FAILED`, and the closing-summary marker is absent. Those four
        facts come from unittest, not from this file.
        """
        self.assertIn("Ran 2 tests in", GREEN_LOG_PRINTED)
        self.assertTrue(GREEN_LOG_PRINTED.rstrip().endswith("OK"))
        self.assertNotIn("FAILED", GREEN_LOG_PRINTED,
                         "the fixture's own summary reports a failed run, so "
                         "it is not a green log and the red test would be red "
                         "for the wrong reason")
        started = [line for line in GREEN_LOG_PRINTED.splitlines()
                   if self.rs._INLINE_NAME.match(line)]
        self.assertEqual(
            2, len(started),
            "the fixture does not hold two started tests, so it is not the "
            "two-test run this file describes: %r" % (started,))
        self.assertEqual(
            [], [line for line in GREEN_LOG_PRINTED.splitlines()
                 if self.rs._SUMMARY.match(line.strip())],
            "the fixture holds a closing-summary failure marker")

    def test_a_genuine_failure_is_still_reported(self):
        """The positive control: one real failure, named once.

        Without this, a parser that reported nothing would satisfy the red
        test's assertion and the defect would be invisible. One test loses
        here and exactly one name must come back - by both markers, which
        unittest writes for a finished run, and counted once.
        """
        found = self.rs._parse_failures(ONE_GENUINE_FAILURE)
        self.assertEqual(
            1, len(found),
            "a log naming one genuine failing test parsed as %d: %r"
            % (len(found), found))
        self.assertEqual("FAIL: sample_gate_module.SampleSuite.test_gamma",
                         found[0])
        self.assertNotIn("test_alpha", found[0],
                         "the passing test of the positive control was blamed")

    def test_a_silent_green_log_reports_zero(self):
        """The negative control: nothing failing, nothing that looks like it.

        This log holds no failure and no `ERROR` text anywhere, so zero is the
        only answer a parser of any design may give. It is here to catch a
        reading that invents a name from something other than the two printed
        lines - the discriminating pair would not notice that.
        """
        self.assertNotIn("ERROR", GREEN_LOG_SILENT)
        self.assertNotIn("FAIL", GREEN_LOG_SILENT)
        self.assertEqual([], self.rs._parse_failures(GREEN_LOG_SILENT))


class TheParserUnderTestIsTheBytesOnDisk(unittest.TestCase):
    """A pyc is not the source, so "I ran the current code" needs proving.

    Both directions, and neither is decoration. Positive: every pattern the
    loaded module carries is text the file holds right now. Negative: the same
    reading, pointed at a module and a file that disagree, reports the
    disagreement - so if the load above had been stale, this reading would have
    said so instead of agreeing with it.
    """

    def test_every_loaded_pattern_is_in_the_file_on_disk(self):
        rs = load_run_suite()
        self.assertEqual(
            [], patterns_absent_from(RUN_SUITE, rs, PATTERNS),
            "a pattern compiled into the loaded module is not text this file "
            "holds, so the module did not come from these bytes and every "
            "measurement in this file is about some other version of the "
            "parser. Patterns: %r" % ({a: getattr(rs, a).pattern
                                       for a in PATTERNS},))

    def test_a_stale_load_is_something_this_reading_would_catch(self):
        """The proof has teeth, and the artefact was not touched to give it.

        A copy is loaded, the copy's bytes are then rewritten so that its
        summary pattern loses its anchor, and the reading from the first load
        is pointed at the rewritten file. It must report the divergence. The
        second load, from the rewritten file, must carry the rewritten pattern
        and must behave differently - the two loads are compared by what they
        DO to a genuine `FAIL:` line, not only by the text they carry.
        """
        before = hashlib.md5(io.open(RUN_SUITE, "rb").read()).hexdigest()
        work = tempfile.mkdtemp(prefix="gate-parser-pyc-")
        self.addCleanup(shutil.rmtree, work, True)
        copy = os.path.join(work, "run_suite.py")
        original = io.open(RUN_SUITE, "rb").read()
        with io.open(copy, "wb") as fh:
            fh.write(original)
        first_state = os.stat(copy)
        stale = _load_module_at(copy, "run_suite_copy_stale")

        target = b'r"^(FAIL|ERROR)'
        self.assertEqual(
            1, original.count(target),
            "the rewrite target appears %d times in run_suite.py, not once, so "
            "the rewrite below would land somewhere other than where this test "
            "believes it lands" % (original.count(target),))
        mutated = original.replace(target, b'r" (FAIL|ERROR)')
        self.assertEqual(len(original), len(mutated),
                         "this rewrite is meant to hold the size equal, which "
                         "is the case a pyc can be chosen by")
        self.assertNotEqual(original, mutated)
        with io.open(copy, "wb") as fh:
            fh.write(mutated)
        # Forward, so the second load is decided by the file and not by which
        # invalidation scheme this interpreter happens to use. The same-second
        # case is the hazard, it is measured in `patterns_absent_from`, and it
        # is what the reading above exists to survive.
        os.utime(copy, (first_state.st_mtime + 2.0, first_state.st_mtime + 2.0))

        self.assertEqual(
            ["_SUMMARY"], patterns_absent_from(copy, stale, ["_SUMMARY"]),
            "the stale module's pattern is still text the rewritten file "
            "holds, so this probe cannot tell a stale load from a current one")
        fresh = _load_module_at(copy, "run_suite_copy_fresh")
        self.assertNotEqual(stale._SUMMARY.pattern, fresh._SUMMARY.pattern)

        genuine = ("FAIL: test_gamma "
                   "(sample_gate_module.SampleSuite.test_gamma)")
        self.assertTrue(stale._SUMMARY.match(genuine),
                        "the stale module does not read a genuine summary line, "
                        "so this probe is not measuring what it claims")
        self.assertFalse(fresh._SUMMARY.match(genuine),
                         "the rewritten module still reads a genuine summary "
                         "line, so the rewrite did not change behaviour and the "
                         "two loads cannot be told apart by it")

        after = hashlib.md5(io.open(RUN_SUITE, "rb").read()).hexdigest()
        self.assertEqual(before, after,
                         "scripts/run_suite.py changed while this file ran. "
                         "This file reads that artefact; it does not write it.")


if __name__ == "__main__":
    unittest.main()
