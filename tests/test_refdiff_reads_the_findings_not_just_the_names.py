"""TASK-0150: a merge gate that reads only failing NAMES cannot see the 25th
violation of a rule that already fails on 24.

Born red against `scripts/ops/refdiff.py`'s finding leg, added 2026-10-15
after `webapp/0030` measured the hole: a branch put a real surname in a
tracked file, `test_no_real_person_or_client_named` failed on BOTH sides (24
entries at master, 25 on the branch), the failing-name set was identical, and
the gate reported CLEAN. The test fired; the gate read the wrong field.

Every name, path and finding below is invented. The real 24 entries are the
operator's separate matter and stay out of this file.
"""
import importlib.util
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIFF = os.path.join(ROOT, "scripts", "ops", "refdiff.py")
RUN_SUITE = os.path.join(ROOT, "scripts", "run_suite.py")
SUITE_BASELINE = os.path.join(ROOT, "scripts", "suite_baseline.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RULE = "tests.test_example_rule.TestTheRule.test_example_rule"
SHORT = "test_example_rule.TestTheRule.test_example_rule"

ENTRIES_24 = [f"docs/AA-{i:02d}.md: namealpha{i:02d}" for i in range(1, 25)]
ENTRY_25 = "docs/BB-NEW-2026-10-15.md: namenew"


def make_log(entries, *, tree="a", chars=840, diff=1337, count=None,
             closing_block=True, ran_line=True):
    """A finished `-v` suite log with ONE failing rule test.

    Mirrors the anatomy `run_suite` writes: inline verdicts for the names,
    then, only if the run finished, the closing block whose AssertionError
    carries unittest's list-diff scaffolding AND the full joined entry list.
    The scaffolding digits and the absolute tree path are the volatile parts
    the gate must normalise away; the entry lines are the finding set.
    """
    if count is None:
        count = len(entries)
    lines = [
        "running the full suite offline",
        "",
        "test_ok_one (tests.test_widget_seal.TheSeal.test_ok_one) ... ok",
        f"test_example_rule ({RULE}) ... FAIL",
        "test_ok_two (tests.test_widget_seal.TheSeal.test_ok_two) ... ok",
        "",
    ]
    if closing_block:
        lines += [
            "=" * 70,
            f"FAIL: test_example_rule ({RULE})",
            "-" * 70,
            "Traceback (most recent call last):",
            '  File "C:\\trees\\wt-%s\\tests\\test_example_rule.py", line 9, '
            "in test_example_rule" % tree,
            "    self.assertEqual(hits, [], 'entries:\\n' + '\\n'.join(hits))",
            "AssertionError: Lists differ: ['docs/AA-01.md: namealpha01', "
            f"[{chars} chars]4.md: namealpha24'] != []",
            "",
            f"First list contains {count} additional elements.",
            "First extra element 0:",
            "'docs/AA-01.md: namealpha01'",
            "",
            "Diff is %d characters long. Set self.maxDiff to None to see it. "
            " : entries (measured under C:\\trees\\wt-%s\\work):" % (diff, tree),
        ]
        lines += list(entries)
        lines.append("")
    if ran_line:
        lines += [
            "-" * 70,
            "Ran 3 tests in 0.012s",
            "",
            "FAILED (failures=1)",
        ]
    return "\n".join(lines) + "\n"


class GateTestCase(unittest.TestCase):
    """Loads the gate exactly as the operator's shell would."""

    @classmethod
    def setUpClass(cls):
        cls.run_suite = _load(RUN_SUITE, "rs_gate_test")
        cls.baseline = _load(SUITE_BASELINE, "sb_gate_test")
        cls.refdiff = _load(REFDIFF, "refdiff_gate_test")

    def names_of(self, text):
        return self.refdiff.names(text, self.run_suite, self.baseline)


class TestTheOldFieldCannotSeeIt(GateTestCase):

    def test_the_failing_name_set_is_identical_24_vs_25(self):
        """The blindness, pinned: the old comparison is a set of NAMES."""
        ref = make_log(ENTRIES_24)
        branch = make_log(ENTRIES_24 + [ENTRY_25], tree="b", chars=900,
                          diff=1420, count=25)
        self.assertEqual(self.names_of(ref), self.names_of(branch))
        self.assertEqual(self.names_of(ref), {SHORT})


class TestTheFindingLeg(GateTestCase):

    def test_a_twenty_fifth_entry_in_an_already_failing_rule_is_new(self):
        ref = make_log(ENTRIES_24)
        branch = make_log(ENTRIES_24 + [ENTRY_25])
        per_test, unknown = self.refdiff.compare_findings(
            self.refdiff.payloads(ref, self.run_suite, self.baseline),
            self.refdiff.payloads(branch, self.run_suite, self.baseline),
            self.names_of(ref) & self.names_of(branch))
        self.assertEqual(unknown, [])
        self.assertEqual(list(per_test), [SHORT])
        new, gone = per_test[SHORT]
        self.assertEqual(sorted(new), [ENTRY_25])
        self.assertEqual(sum(gone.values()), 0)

    def test_a_fixed_entry_is_reported_gone_both_directions(self):
        ref = make_log(ENTRIES_24 + [ENTRY_25])
        branch = make_log(ENTRIES_24)
        per_test, _ = self.refdiff.compare_findings(
            self.refdiff.payloads(ref, self.run_suite, self.baseline),
            self.refdiff.payloads(branch, self.run_suite, self.baseline),
            self.names_of(ref) & self.names_of(branch))
        new, gone = per_test[SHORT]
        self.assertEqual(sorted(gone), [ENTRY_25])
        self.assertEqual(sum(new.values()), 0)

    def test_scaffolding_digits_and_tree_paths_alone_do_not_block(self):
        """`[N chars]`, `Diff is N characters long` and the absolute tree
        path move with the log, not the findings; they must cancel."""
        ref = make_log(ENTRIES_24, tree="a", chars=840, diff=1337)
        branch = make_log(ENTRIES_24, tree="b", chars=900, diff=1420)
        per_test, unknown = self.refdiff.compare_findings(
            self.refdiff.payloads(ref, self.run_suite, self.baseline),
            self.refdiff.payloads(branch, self.run_suite, self.baseline),
            self.names_of(ref) & self.names_of(branch))
        self.assertEqual((per_test, unknown), ({}, []))


class TestMain(GateTestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old = os.environ.get("REFDIFF_SCRIPTS")
        os.environ["REFDIFF_SCRIPTS"] = os.path.join(ROOT, "scripts")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("REFDIFF_SCRIPTS", None)
        else:
            os.environ["REFDIFF_SCRIPTS"] = self._old

    def write(self, name, text):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", newline="\n") as handle:
            handle.write(text)
        return path

    def run_main(self, ref_text, branch_text):
        import contextlib
        import io
        ref = self.write("ref.log", ref_text)
        branch = self.write("branch.log", branch_text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.refdiff.main([ref, branch, "branch"])
        return code, out.getvalue()

    def test_a_clean_branch_is_clean_and_says_identical(self):
        code, out = self.run_main(make_log(ENTRIES_24),
                                  make_log(ENTRIES_24, tree="b", chars=900,
                                           diff=1420))
        self.assertEqual(code, 0, out)
        self.assertIn("control, one planted finding:      PASS", out)
        self.assertIn("FINDINGS: identical inside every test failing on "
                      "both sides", out)
        self.assertIn("VERDICT: CLEAN - no new name", out)

    def test_the_twenty_fifth_entry_blocks_the_merge(self):
        code, out = self.run_main(make_log(ENTRIES_24),
                                  make_log(ENTRIES_24 + [ENTRY_25]))
        self.assertEqual(code, 1, out)
        self.assertIn(f"      + {ENTRY_25}", out)
        self.assertIn("VERDICT: NEW FINDINGS - do not merge", out)

    def test_an_unfinished_run_never_reads_as_no_new_finding(self):
        ref = make_log(ENTRIES_24)
        killed = make_log(ENTRIES_24 + [ENTRY_25], closing_block=False,
                          ran_line=False)
        code, out = self.run_main(ref, killed)
        self.assertIn("FINDINGS: NOT COMPARED", out, out)
        self.assertIn("do not read this as 'no new finding'", out)
        self.assertEqual(code, 0, "the name verdict keeps its old semantics")

    def test_a_missing_closing_block_blocks_rather_than_guesses(self):
        """Names say the test fails on both sides; the branch log carries no
        block to read. Zero-on-both-sides is not 'no change' - it REFUSES."""
        ref = make_log(ENTRIES_24)
        blockless = make_log(ENTRIES_24 + [ENTRY_25], closing_block=False)
        code, out = self.run_main(ref, blockless)
        self.assertEqual(code, 1, out)
        self.assertIn("FINDINGS UNKNOWN", out)
        self.assertIn("closing block missing", out)


if __name__ == "__main__":
    unittest.main()
