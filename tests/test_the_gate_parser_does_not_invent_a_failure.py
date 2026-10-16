"""The merge gate's own parser must not invent a failure that is not there.

`scripts/run_suite.py` is the merge gate's only instrument, and
`_parse_failures` is how it answers "which tests failed". Pass 2 of that
function read the inline `-v` lines with an UNANCHORED `_INLINE_VERDICT.search`
over the whole line. `startTest` writes the description and `" ... "` with no
newline, so anything the test prints lands on the head line itself - which
means a test that PASSES while printing `GET /v1/x -> 500 ... ERROR` had its
own stdout read as the runner's verdict, and the gate reported a failure where
the truth was zero. TASK 0251 found the live regex; TASK 0253 reproduced the
invention on a real captured log and fixed it.

THIS RUNS IN THE DIRECTION THAT FAILS A GREEN BRANCH. The same parser's other
known defect (TASK-0290: a killed log, 207 names reported where the truth was
228) runs in the direction that PASSES a merge. Both are the same family - a
text scrape of a test runner's output that answers confidently about something
it did not measure.

WHY ANCHORING ALONE WAS NOT THE FIX, measured in TASK 0253. TASK-0290's
`_VERDICT_EOL` right-anchors the verdict to end-of-line, which is correct and
necessary. It is not sufficient: on the real log captured for this test the
printed string ENDS at the word `ERROR`, so the right anchor matches it
happily and the invention survives. 0290's synthetic fixture happened to put
trailing text after `ERROR`, which hid the case. The fix that works is
positional rather than textual - **on a head line the verdict is whatever
immediately follows that head's own `" ... "`, and nothing else on the line is
eligible.**

THE OTHER DIRECTION, and the reason this file asserts counts upward too.
A pattern tightened until it sees nothing always reports clean. ~169 tests in
a full run close on a BARE verdict - the token alone on its own line, because
the test printed a newline first - and the old pattern, which demanded a
literal `...`, could not see any of them. `C5_ALL_BARE` is that control: the
old reader scored `_count_results` 0 against the runner's own `Ran 3`, and the
fixed one scores 3. So the fix sees strictly LESS in the invented-failure
direction and strictly MORE in the bare-verdict direction, which is what
distinguishes a repair from a blindfold.

FIXTURES ARE REAL. All three were captured by running a throwaway test module
alone under `py -3 -u -m unittest -v` and keeping the bytes, rather than
hand-writing what unittest is believed to print. `-u` matters: with stdout
block-buffered to a file the prints do not interleave with the runner's stream
and the defect cannot be reproduced at all.
"""
import importlib.util
import os
import re
import unittest


def _load_run_suite():
    """Import `scripts/run_suite.py` by path - the REAL file, not a copy.

    Same loader as `test_a_suite_that_ran_nothing_is_not_a_pass`, for the same
    reason: the gate is a script rather than a module under `src/`, and a test
    that re-implements its logic proves nothing about the file the operator
    runs.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "scripts", "run_suite.py")
    spec = importlib.util.spec_from_file_location(
        "_run_suite_parser_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_suite = _load_run_suite()


#: C1. Four tests, ALL FOUR PASS, one of them prints a string containing
#: `... ERROR` on its own stdout. unittest's own trailer declares `Ran 4` and
#: `OK`, so the truth about this log is zero failures and zero errors.
C1_PASSING_TEST_PRINTS_ERROR = """\
test_four (c1mod.A.test_four) ... ok
test_one (c1mod.A.test_one) ... ok
test_three (c1mod.A.test_three) ... provider said: GET /v1/x -> 500 ... ERROR
ok
test_two (c1mod.A.test_two) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.000s

OK
"""

#: C2. One test really does raise. The truth here is exactly one ERROR, named,
#: and it has to survive the fix.
C2_GENUINE_ERROR = """\
test_one (c2mod.B.test_one) ... ok
test_three (c2mod.B.test_three) ... ok
test_two (c2mod.B.test_two) ... ERROR

======================================================================
ERROR: test_two (c2mod.B.test_two)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "c2mod.py", line 10, in test_two
    raise RuntimeError("this one really is broken")
RuntimeError: this one really is broken

----------------------------------------------------------------------
Ran 3 tests in 0.001s

FAILED (errors=1)
"""

#: C2 with the closing summary block removed - the killed-run case, where pass
#: 2 is the only channel there is. The invention must not come back when the
#: summary is unavailable, and the real failure must still be found.
C2_NO_SUMMARY = """\
test_one (c2mod.B.test_one) ... ok
test_three (c2mod.B.test_three) ... ok
test_two (c2mod.B.test_two) ... ERROR
"""

#: C1 with the closing summary removed, for the same reason in the other
#: direction: a killed log where nothing failed must still report nothing.
C1_NO_SUMMARY = """\
test_four (c1mod.A.test_four) ... ok
test_one (c1mod.A.test_one) ... ok
test_three (c1mod.A.test_three) ... provider said: GET /v1/x -> 500 ... ERROR
ok
"""

#: C5. Three tests, all pass, every one printing a line that ends in a
#: newline - so every verdict is written BARE on its own line. The B7
#: counter-control: a parser that has been tightened into blindness scores
#: zero results here while the runner declares three.
C5_ALL_BARE = """\
test_one (c5mod.C.test_one) ... doing something quite ordinary
ok
test_three (c5mod.C.test_three) ... and once more
ok
test_two (c5mod.C.test_two) ... and again
ok

----------------------------------------------------------------------
Ran 3 tests in 0.000s

OK
"""

#: A skipped verdict is the one that carries a trailing payload, because
#: `addSkip` writes `skipped {reason!r}`. An end-of-line anchor with no
#: allowance for it loses the log's own `skipped=N`, so it is asserted.
SKIP_WITH_REASON = """\
test_one (s.S.test_one) ... skipped 'not today'
test_two (s.S.test_two)
A docstring that pushes the verdict onto this line. ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.000s

OK (skipped=1)
"""


def declared_ran(log_text):
    """The runner's own `Ran N tests` figure - the authority for the count."""
    found = re.search(r"^Ran (\d+) tests?", log_text, re.M)
    return int(found.group(1)) if found else None


class TheParserDoesNotInventAFailure(unittest.TestCase):

    def test_a_passing_test_printing_error_is_not_a_failure(self):
        """C1. Truth is zero, and the parser must say zero.

        Asserted as a NAME SET rather than a count, so that a wrong answer
        names the test it invented. A count alone cannot tell "invented one"
        from "found a real one and lost another".
        """
        self.assertEqual([], run_suite._parse_failures(
            C1_PASSING_TEST_PRINTS_ERROR))

    def test_the_invented_name_was_the_test_that_printed(self):
        """The specific invention this file exists to stop.

        The defect named `c1mod.A.test_three` - the test whose stdout carried
        the string - and nothing else. Naming it keeps the assertion above
        honest: if some other guard starts answering, or the parser invents a
        DIFFERENT name, the set assertion fails and this one explains why.
        """
        names = run_suite._parse_failures(C1_PASSING_TEST_PRINTS_ERROR)
        self.assertNotIn("ERROR: c1mod.A.test_three", names)
        self.assertNotIn("FAIL: c1mod.A.test_three", names)

    def test_the_invention_does_not_return_without_a_summary_block(self):
        """C1 killed. Pass 2 is the only channel; it must still report zero."""
        self.assertEqual([], run_suite._parse_failures(C1_NO_SUMMARY))

    def test_a_genuine_error_is_still_counted(self):
        """C2. The fix is not allowed to make the instrument blind."""
        self.assertEqual(["ERROR: c2mod.B.test_two"],
                         run_suite._parse_failures(C2_GENUINE_ERROR))

    def test_a_genuine_error_is_still_counted_without_a_summary_block(self):
        """C2 killed - the inline channel alone, which is 0290's condition."""
        self.assertEqual(["ERROR: c2mod.B.test_two"],
                         run_suite._parse_failures(C2_NO_SUMMARY))

    def test_a_skip_with_a_reason_is_not_read_as_a_failure(self):
        """`skipped 'reason'` and a docstring-wrapped `ok`, both clean."""
        self.assertEqual([], run_suite._parse_failures(SKIP_WITH_REASON))


class TheParserIsNotMerelyBlind(unittest.TestCase):
    """B7. A regex tightened until it sees nothing always reports clean.

    These assert the count UPWARD, against the runner's own `Ran N tests`,
    which is the only authority for how many tests reported a verdict. Without
    them, deleting the body of `_parse_failures` would pass the class above.
    """

    def test_a_bare_verdict_is_a_verdict(self):
        """C5. Every verdict on its own line; the old pattern saw none."""
        self.assertEqual(declared_ran(C5_ALL_BARE),
                         run_suite._count_results(C5_ALL_BARE))

    def test_the_head_line_form_is_still_counted(self):
        """The ordinary `name (path) ... ok` form keeps working."""
        self.assertEqual(declared_ran(C2_GENUINE_ERROR),
                         run_suite._count_results(C2_GENUINE_ERROR))

    def test_a_printed_line_does_not_cost_the_real_verdict(self):
        """C1: four tests ran, four verdicts, including the printer's."""
        self.assertEqual(declared_ran(C1_PASSING_TEST_PRINTS_ERROR),
                         run_suite._count_results(
                             C1_PASSING_TEST_PRINTS_ERROR))

    def test_a_skip_and_a_wrapped_docstring_both_report(self):
        self.assertEqual(declared_ran(SKIP_WITH_REASON),
                         run_suite._count_results(SKIP_WITH_REASON))


class TheHeadLocalRuleIsWhatRefusesIt(unittest.TestCase):
    """The mutation control: prove the fix is load-bearing, not decorative.

    `test_a_suite_that_ran_nothing_is_not_a_pass` establishes the shape - a
    guard is only a guard if removing it brings the defect back. Here the
    removal is done without editing the file: pass 2's head branch is replayed
    with the OLD unanchored search, and the invention is required to return.
    A fix that still looks fixed with its own rule stubbed out is not a fix.
    """

    OLD_INLINE_VERDICT = re.compile(
        r"\.\.\.\s+(ok|FAIL|ERROR|skipped|expected failure"
        r"|unexpected success)\b")

    def _old_pass_two(self, log_text):
        """`_parse_failures` pass 2 exactly as it stood before TASK 0253."""
        kinds = {}
        pending = None
        for line in log_text.splitlines():
            head = run_suite._INLINE_NAME.match(line)
            if head:
                pending = head.group(2)
            verdict = self.OLD_INLINE_VERDICT.search(line)
            if verdict and pending:
                if verdict.group(1) in ("FAIL", "ERROR"):
                    kinds.setdefault(pending, verdict.group(1))
                pending = None
        return [f"{kinds[name]}: {name}" for name in sorted(kinds)]

    def test_the_old_reader_really_did_invent_it(self):
        """Without this, the fixtures above could be proving nothing.

        If the old pattern were innocent on this log, every assertion in the
        first class would pass for free and the file would be a control that
        cannot fail - this repository's own signature defect.
        """
        self.assertEqual(["ERROR: c1mod.A.test_three"],
                         self._old_pass_two(C1_PASSING_TEST_PRINTS_ERROR))

    def test_the_old_reader_was_blind_to_a_bare_verdict(self):
        """And the other direction, so the repair is not a blindfold."""
        pending = None
        n = 0
        for line in C5_ALL_BARE.splitlines():
            head = run_suite._INLINE_NAME.match(line)
            if head:
                pending = head.group(2)
            if pending and self.OLD_INLINE_VERDICT.search(line):
                n += 1
                pending = None
        self.assertEqual(0, n)
        self.assertEqual(3, run_suite._count_results(C5_ALL_BARE))

    def test_the_head_verdict_pattern_exists_and_is_anchored(self):
        """The rule itself, asserted on behaviour rather than on source text.

        A head line whose printed stdout ends at the word ERROR must yield no
        verdict from `_HEAD_VERDICT`, because the token immediately after that
        head's own `" ... "` is not a verdict. This is the single positional
        fact the whole fix rests on.
        """
        poisoned = ("test_three (c1mod.A.test_three) ... "
                    "provider said: GET /v1/x -> 500 ... ERROR")
        clean = "test_two (c2mod.B.test_two) ... ERROR"
        self.assertIsNone(run_suite._HEAD_VERDICT.match(poisoned))
        self.assertEqual("ERROR",
                         run_suite._HEAD_VERDICT.match(clean).group(1))


if __name__ == "__main__":
    unittest.main()
