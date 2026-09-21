"""The unintegrated-work scan compared task files and nearly caused a regression.

`scripts/task173_scan.py --unintegrated` decided a task was UNINTEGRATED by
comparing the TASK FILE'S STAGE - TODO on master, DONE on a branch - and
never looked at the code. So a task whose work was already integrated still
reported as stranded, and the obvious response to that report is to merge
the branch.

Measured 2026-09-21: **six of the twelve reported tasks were already
integrated.**

  TASK-229  its three files are BYTE-IDENTICAL on master and on its branch,
            by blob hash. Merging would have deleted 12,487 lines of later
            work, because the branch is simply old.

  TASK-232  worse. Its branch carries an older `stoppedcause.py` that
            classifies a stopped membership from the events feed. Master
            carries a NEWER one with a `NEVER_CONTACTED` outcome the branch
            does not have - and `THE-THIRTY-THREE-ANSWERED-2026-09-18` says
            the events feed COULD NOT have answered the question, because it
            replays ten days and the memberships are months old. Merging on
            the report's word would have deleted the classification that
            works and restored the one that provably cannot.

The scan is derived state, and this is the same failure this repository keeps
paying for: a derived artefact that drifts from the truth it describes and is
believed because it is precise. A ledger somebody has to remember to update
is a ledger that drifts - and a drifted ledger is worse than none.

These tests pin the CODE check, not the formatting of the report.
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "scripts", "task173_scan.py")


def load_scan():
    spec = importlib.util.spec_from_file_location("scan_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheCodeDecidesNotTheTaskFile(unittest.TestCase):

    def setUp(self):
        self.scan = load_scan()
        self.calls = []

    def stub_git(self, names, blobs):
        """`names` is the --name-only output; `blobs` maps 'ref:path' -> hash."""
        def fake(*args, **kw):
            self.calls.append(args)
            if args[0] == "diff":
                return names
            if args[0] == "rev-parse":
                return blobs.get(args[1], "")
            return ""
        self.scan.git = fake

    def test_identical_blobs_read_as_already_integrated(self):
        """TASK-229 exactly: every file the same object on both sides."""
        self.stub_git("src/reservoir.py\nscripts/build_ready_reservoir.py",
                      {"master:src/reservoir.py": "aaa",
                       "origin/b:src/reservoir.py": "aaa",
                       "master:scripts/build_ready_reservoir.py": "bbb",
                       "origin/b:scripts/build_ready_reservoir.py": "bbb"})
        self.assertTrue(self.scan.code_already_on_master("origin/b"))

    def test_one_differing_blob_is_enough_to_stay_unintegrated(self):
        """TASK-232 exactly: the branch really does carry different code -
        older code, but the scan must not decide that; it must report it so a
        person compares them."""
        self.stub_git("src/stoppedcause.py\ntests/test_stopped_cause.py",
                      {"master:src/stoppedcause.py": "newer",
                       "origin/b:src/stoppedcause.py": "older",
                       "master:tests/test_stopped_cause.py": "ccc",
                       "origin/b:tests/test_stopped_cause.py": "ccc"})
        self.assertFalse(self.scan.code_already_on_master("origin/b"))

    def test_a_branch_with_no_code_at_all_is_integrated(self):
        """TASK-212 and TASK-224: a finding, recorded in the task file, with
        nothing to merge."""
        self.stub_git("docs/qwen-tasks/DONE/TASK-212-x.md", {})
        self.assertTrue(self.scan.code_already_on_master("origin/b"))

    def test_docs_alone_do_not_make_a_branch_unintegrated(self):
        self.stub_git("docs/SOMETHING.md\nREADME.md", {})
        self.assertTrue(self.scan.code_already_on_master("origin/b"))

    def test_a_file_absent_from_master_is_not_integrated(self):
        """New code has no blob on master. `rev-parse` answers empty, and an
        empty answer must never compare equal to an empty answer."""
        self.stub_git("src/brand_new.py",
                      {"master:src/brand_new.py": "",
                       "origin/b:src/brand_new.py": "ddd"})
        self.assertFalse(self.scan.code_already_on_master("origin/b"))

    def test_an_unreadable_branch_stays_unintegrated(self):
        """Fail closed. Unknown is not integrated - keep reporting it."""
        def boom(*a, **k):
            raise RuntimeError("no such ref")
        self.scan.git = boom
        self.assertFalse(self.scan.code_already_on_master("origin/gone"))

    def test_it_compares_blobs_rather_than_diffing(self):
        """Behavioural: two files are the same file when git says they are
        the same object. A diff against a merge base answers a different
        question and is what made the old report wrong."""
        self.stub_git("src/a.py",
                      {"master:src/a.py": "same", "origin/b:src/a.py": "same"})
        self.scan.code_already_on_master("origin/b")
        verbs = [c[0] for c in self.calls]
        self.assertIn("rev-parse", verbs)
        self.assertEqual(2, verbs.count("rev-parse"),
                         "one blob hash per side, per file")




class TheReportActuallyConsultsIt(unittest.TestCase):
    """Existence is not function.

    The tests above prove `code_already_on_master` is correct. They do NOT
    prove the report calls it - and when the call was removed by hand, every
    one of them still passed and the printed report was identical, because
    the task files had already been reconciled by then. A check nothing
    consults is the recurring defect in this repository, so the call site is
    pinned separately from the function.
    """

    def test_the_unintegrated_set_is_filtered_through_the_code_check(self):
        scan = load_scan()
        asked = []

        scan.code_already_on_master = lambda ref: (asked.append(ref) or True)
        scan.full_scan = lambda: (
            {"TASK-900": ("TODO", "docs/qwen-tasks/TODO/TASK-900-x.md")},
            {"origin/b": {"TASK-900": ("DONE",
                                       "docs/qwen-tasks/DONE/TASK-900-x.md")}},
            ["TASK-900"])
        scan.check_result_blocks = lambda *a, **k: {}

        import io as _io
        out = _io.StringIO()
        stdout, sys.stdout = sys.stdout, out
        try:
            scan.full_report(unintegrated_only=True)
        finally:
            sys.stdout = stdout

        self.assertEqual(["origin/b"], asked,
                         "the report did not ask whether the code was "
                         "already on master")
        text = out.getvalue()
        self.assertIn("UNINTEGRATED tasks: 0", text)
        self.assertIn("ALREADY INTEGRATED", text)
        self.assertIn("DO NOT MERGE", text)

    def test_a_branch_whose_code_differs_is_still_reported(self):
        scan = load_scan()
        scan.code_already_on_master = lambda ref: False
        scan.full_scan = lambda: (
            {"TASK-901": ("TODO", "docs/qwen-tasks/TODO/TASK-901-x.md")},
            {"origin/b": {"TASK-901": ("DONE",
                                       "docs/qwen-tasks/DONE/TASK-901-x.md")}},
            ["TASK-901"])
        scan.check_result_blocks = lambda *a, **k: {}

        import io as _io
        out = _io.StringIO()
        stdout, sys.stdout = sys.stdout, out
        try:
            scan.full_report(unintegrated_only=True)
        finally:
            sys.stdout = stdout
        self.assertIn("UNINTEGRATED tasks: 1", out.getvalue())

if __name__ == "__main__":
    unittest.main()
