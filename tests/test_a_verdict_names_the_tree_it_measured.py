"""A verdict file must name the tree it measured, or it is not evidence.

MEASURED 2026-10-17, in this lane's worktree at b1f290c84 (CRLF tree).
`scripts/run_suite.py`'s `build_verdict` wrote eleven lines:

    status=FAIL
    exit_code=1
    wall_seconds=12.5
    timed_out=False
    log_file=scripts/suite_run.log
    results_reached=3
    failures=2
    failures_are_partial=False
    result_line=FAILED (failures=1, errors=1)
      ERROR: tests.test_sprocket_guard.TheGuard.test_three
      FAIL: tests.test_widget_seal.TheSeal.test_two

Not one line says WHICH TREE those numbers came from. The file is written into
`scripts/`, where it outlives the checkout that produced it: a run leaves a
verdict behind, the tree moves, and the file is then read as a finished run of
whatever is checked out when somebody looks at it. That is this repository's
own signature defect - a reference that silently resolves to something other
than what its reader believes - committed by the tool that exists to report
honestly.

Three things are asserted here, and none is cosmetic:

  * a freshly written verdict names its own tree SHA, a UTC timestamp and the
    runner mode, so the in-repo evidence identifies itself;
  * a verdict left behind by a DIFFERENT tree reads as STALE-MISMATCH, and one
    carrying no SHA at all (the shape above, which is every verdict file
    written before this change) reads as UNIDENTIFIED - neither can be read as
    a verdict about the tree you are standing in;
  * the identity is ADDED and moves nothing else: the failure set the existing
    reader `scripts/task123_diff_failures.py` extracts from the same log is
    identical with and without the new lines.

MATCH is the only state that licenses reading a verdict as a statement about
the current tree. Absence never reads as MATCH: a tree SHA that cannot be read
is UNKNOWN, a file with no SHA field is UNIDENTIFIED, and no file at all is
MISSING.

The born-red test of this task is `test_the_verdict_names_the_sha_of_this_tree`
in `TheVerdictNamesItsOwnTree`. At b1f290c84 it fails with

    AssertionError: 'tree_sha=b1f290c847eb2500b7eb39987ac34f6d6a8d00d2' not
    found in 'status=FAIL\nexit_code=1\nwall_seconds=12.5\n...'

: the verdict does not name the tree it measured. The reader tests in the
other classes cannot pass there at all, because `read_verdict` and
`check_verdict` do not exist yet; that is said plainly here rather than
hidden, and the base run is reported exactly as it came out.
"""
import calendar
import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_SUITE = os.path.join(ROOT, "scripts", "run_suite.py")
TASK123 = os.path.join(ROOT, "scripts", "task123_diff_failures.py")

#: A log shaped like a finished, failing run. Every name in it is invented.
LOG = (
    "test_one (tests.test_widget_seal.TheSeal.test_one) ... ok\n"
    "test_two (tests.test_widget_seal.TheSeal.test_two) ... FAIL\n"
    "test_three (tests.test_sprocket_guard.TheGuard.test_three) ... ERROR\n"
    "\n"
    "Ran 3 tests in 1.000s\n"
    "\n"
    "FAILED (failures=1, errors=1)\n"
)

#: THE OLD SHAPE, quoted rather than described. It is the exact output of
#: `build_verdict` at b1f290c84, measured there by running it against LOG and
#: printing every line with repr(). Quoted because this is the artefact under
#: test: verdict files of exactly this shape are lying around on disk right
#: now, and a retyped approximation of one would prove nothing about them.
#: The one line a fixture cannot reproduce verbatim is `log_file=`, which
#: names the absolute path it was written at.
OLD_SHAPE = (
    "status=FAIL\n"
    "exit_code=1\n"
    "wall_seconds=12.5\n"
    "timed_out=False\n"
    "log_file=scripts/suite_run.log\n"
    "results_reached=3\n"
    "failures=2\n"
    "failures_are_partial=False\n"
    "result_line=FAILED (failures=1, errors=1)\n"
    "  ERROR: tests.test_sprocket_guard.TheGuard.test_three\n"
    "  FAIL: tests.test_widget_seal.TheSeal.test_two\n"
)

#: Invented, 40 hex characters like a git object name, and deliberately not
#: any sha this repository has. `read_verdict` compares them as strings and
#: never asks git whether they exist - the question is which tree a file
#: NAMES, not which commits are real.
SHA_A = "a" * 40
SHA_B = "b" * 40


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_run_suite():
    return load(RUN_SUITE, "run_suite_under_test")


def git_head():
    """This tree's HEAD, read independently of the module under test.

    Independent on purpose: an assertion that asks the module for the sha it
    should have written, and then checks it wrote that, marks its own homework.
    """
    try:
        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=120,
                             check=False)
    except Exception:                                          # noqa: BLE001
        return ""
    return (out.stdout or "").strip()


def state_line(printed):
    """The state the instrument printed, as a bare word."""
    for line in printed.splitlines():
        if line.startswith("state="):
            return line.split("=", 1)[1]
    return ""


def blank_log_path(line):
    """`log_file=` names where the run happened; two runs never share it."""
    return "log_file=<the log this was built from>" \
        if line.startswith("log_file=") else line


class VerdictFixture(unittest.TestCase):
    """Every file this module writes goes to a temp directory, never the repo."""

    def setUp(self):
        self.rs = load_run_suite()
        self.dir = tempfile.mkdtemp(prefix="merge0180-verdict-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.verdict = os.path.join(self.dir, "suite_verdict.txt")

    def log_path(self):
        path = os.path.join(self.dir, "suite_run.log")
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(LOG)
        return path

    def verdict_of(self, log_path=None, **kwargs):
        return self.rs.build_verdict(log_path or self.log_path(), 1, 12.5,
                                     False, **kwargs)

    def put(self, text):
        with io.open(self.verdict, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return self.verdict


class TheVerdictNamesItsOwnTree(VerdictFixture):
    """The born-red test of this task, and the change it exists to hold down."""

    def test_the_verdict_names_the_sha_of_this_tree(self):
        """BORN RED at b1f290c84, green at the fix - and this is the test.

        A verdict that does not name its tree is read as a verdict of whatever
        is checked out when somebody looks at it, which is how a leftover file
        came to be quoted as a finished run of a tree nobody ran. The SHA is
        the field that makes that reading impossible, so it is asserted
        against the sha this tree is really on.
        """
        real = git_head()
        if not real:
            self.skipTest("git could not name this tree's HEAD")
        verdict = self.verdict_of()
        self.assertIn("tree_sha=%s" % real, verdict,
                      "the verdict does not name the tree it measured:\n"
                      + verdict)

    def test_the_identity_comes_before_the_status(self):
        """A reader that stops at the first line must still see the tree.

        Identity after the verdict is identity a reader has already stopped
        reading for, so the field is asserted to precede `status=`.
        """
        verdict = self.verdict_of(tree_sha=SHA_A, mode="offline")
        body = verdict.splitlines()
        self.assertLess(body.index("tree_sha=%s" % SHA_A),
                        body.index("status=FAIL"),
                        "the tree this verdict is about is named after the "
                        "verdict itself:\n" + verdict)

    def test_the_verdict_carries_the_time_it_was_written(self):
        """A UTC stamp, and the real one - a constant would be no better.

        The stamp is parsed and compared against the clock, so a literal would
        fail here rather than pass as "there is a timestamp".
        """
        verdict = self.verdict_of(tree_sha=SHA_A)
        found = re.search(r"(?m)^written_at=(\S+)$", verdict)
        self.assertIsNotNone(found,
                             "no written_at line in the verdict:\n" + verdict)
        stamp = found.group(1)
        parsed = time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
        self.assertLess(abs(calendar.timegm(parsed) - time.time()), 120,
                        "written_at=%s is not when this verdict was written"
                        % stamp)

    def test_the_verdict_names_the_runner_that_measured_it(self):
        verdict = self.verdict_of(tree_sha=SHA_A, mode="offline")
        self.assertIn("mode=offline", verdict, verdict)
        verdict = self.verdict_of(tree_sha=SHA_A, mode="unittest")
        self.assertIn("mode=unittest", verdict, verdict)

    def test_a_caller_that_says_nothing_gets_unknown_not_a_blank(self):
        """No silent blank fields, and no guessed ones either.

        A blank identity field is the field a reader skips, so an unstated
        tree becomes UNKNOWN and an unstated runner becomes `unknown`. Both
        are values `read_verdict` refuses to match, which is the point: an
        unidentifiable verdict must not be readable as a live one.
        """
        verdict = self.verdict_of(tree_sha="", mode="")
        self.assertIn("tree_sha=UNKNOWN", verdict, verdict)
        self.assertIn("mode=unknown", verdict, verdict)
        self.assertNotIn("tree_sha=\n", verdict, verdict)


class TheRunnerWritesAVerdictThatIdentifiesItself(VerdictFixture):
    """The production path, not only `build_verdict` on its own.

    A field the writer never passes is a field that is always UNKNOWN. So
    `run_suite` is driven end to end here with its subprocess intercepted: the
    suite command writes the synthetic log and returns an exit code of its
    own, while `git rev-parse` is passed through to the real command, because
    the identity has to be a real read of this tree. No suite runs, no lock is
    taken, nothing binds a socket.
    """

    def drive(self, returncode, offline):
        real = git_head()
        if not real:
            self.skipTest("git could not name this tree's HEAD")
        log_path = os.path.join(self.dir, "suite_run.log")
        verdict_path = os.path.join(self.dir, "suite_verdict.txt")

        class FakeProc:
            pass

        proc = FakeProc()
        proc.returncode = returncode

        def fake_run(cmd, *args, **kwargs):
            if cmd and cmd[0] == "git":
                return subprocess.run(cmd, *args, **kwargs)
            stdout = kwargs.get("stdout")
            stdout.write(LOG)
            stdout.flush()
            return proc

        with mock.patch.object(self.rs, "subprocess",
                               mock.Mock(run=fake_run)), \
                mock.patch.object(self.rs, "LOG_FILE", log_path), \
                mock.patch.object(self.rs, "VERDICT_FILE", verdict_path), \
                contextlib.redirect_stdout(io.StringIO()):
            code = self.rs.run_suite(3600, offline)

        with io.open(verdict_path, "r", encoding="utf-8") as fh:
            written = fh.read()
        return real, code, verdict_path, written

    def test_the_written_file_names_this_tree_and_the_offline_runner(self):
        real, code, _, written = self.drive(1, True)
        self.assertEqual(1, code, "the suite's own exit code must survive")
        self.assertIn("tree_sha=%s" % real, written, written)
        self.assertIn("mode=offline", written, written)
        self.assertIn("status=FAIL", written, written)

    def test_the_file_the_runner_wrote_is_the_one_that_matches(self):
        """The writer and the reader, against one file on disk.

        Both halves could be right about different strings; this is the arm
        that says the file the production writer leaves is the file the
        production reader calls MATCH.
        """
        real, _, verdict_path, written = self.drive(0, False)
        self.assertIn("mode=unittest", written, written)
        result = self.rs.read_verdict(verdict_path, tree_sha=real)
        self.assertEqual("MATCH", result["state"], result)
        self.assertEqual("unittest", result["fields"].get("mode"), result)


class ALeftoverVerdictIsNotAVerdictAboutThisTree(VerdictFixture):
    """The file outlives the tree, and that is the whole defect."""

    def test_a_verdict_from_another_tree_is_stale_mismatch(self):
        self.put("tree_sha=%s\nstatus=PASS\nfailures=0\n" % SHA_A)
        result = self.rs.read_verdict(self.verdict, tree_sha=SHA_B)
        self.assertEqual("STALE-MISMATCH", result["state"], result)
        self.assertEqual(SHA_A, result["recorded_sha"], result)
        self.assertEqual(SHA_B, result["asked_sha"], result)

    def test_a_verdict_from_this_tree_is_a_match(self):
        self.put("tree_sha=%s\nstatus=PASS\nfailures=0\n" % SHA_A)
        result = self.rs.read_verdict(self.verdict, tree_sha=SHA_A)
        self.assertEqual("MATCH", result["state"], result)

    def test_the_old_shape_is_unidentified_and_is_never_a_match(self):
        """Every verdict written before this change has this shape.

        It names no tree, so it identifies none - and UNIDENTIFIED is kept
        apart from STALE-MISMATCH on purpose: one is a file saying it is about
        a tree that is not this one, the other is a file saying nothing about
        any tree. Neither is MATCH, and the reading this task exists to kill
        is the one that treats the second as the first.
        """
        self.put(OLD_SHAPE)
        result = self.rs.read_verdict(self.verdict, tree_sha=SHA_A)
        self.assertEqual("UNIDENTIFIED", result["state"], result)
        self.assertIsNone(result["recorded_sha"], result)
        self.assertNotEqual("MATCH", result["state"])
        self.assertEqual("FAIL", result["fields"].get("status"),
                         "the fields it does carry are still parsed: %r"
                         % (result,))

    def test_a_file_that_cannot_name_its_tree_is_unknown(self):
        self.put("tree_sha=UNKNOWN\nstatus=PASS\nfailures=0\n")
        result = self.rs.read_verdict(self.verdict, tree_sha=SHA_A)
        self.assertEqual("UNKNOWN", result["state"], result)
        self.assertNotEqual("MATCH", result["state"])

    def test_a_tree_that_cannot_be_read_is_unknown(self):
        """The other side of the same question, and it must not become MATCH.

        An empty sha means git could not say which tree this is. Nothing about
        the file then licenses reading it: the comparison never happened, and
        a comparison that never happened is not a match.
        """
        self.put("tree_sha=%s\nstatus=PASS\n" % SHA_A)
        result = self.rs.read_verdict(self.verdict, tree_sha="")
        self.assertEqual("UNKNOWN", result["state"], result)
        self.assertIsNone(result["asked_sha"], result)

    def test_no_verdict_file_at_all_is_missing(self):
        result = self.rs.read_verdict(self.verdict, tree_sha=SHA_A)
        self.assertEqual("MISSING", result["state"], result)
        self.assertNotEqual("MATCH", result["state"])

    def test_a_stale_file_is_not_a_blank_file(self):
        """The numbers are still parsed; only the licence to act is withheld."""
        self.put("tree_sha=%s\nstatus=FAIL\nfailures=7\nlog_file=x\n" % SHA_A)
        result = self.rs.read_verdict(self.verdict, tree_sha=SHA_B)
        self.assertEqual("STALE-MISMATCH", result["state"], result)
        self.assertEqual("FAIL", result["fields"].get("status"), result)
        self.assertEqual("7", result["fields"].get("failures"), result)


class OneInstrumentPrintsBothArms(VerdictFixture):
    """Both answers, once each, from the same instrument.

    A reader that can only say MATCH is not evidence for anything. These arms
    run through `check_verdict` - the same call the `--check-verdict` flag
    makes - so the instrument that reports a clean match is the one that was
    shown saying STALE-MISMATCH first.
    """

    def run_instrument(self, text, asked):
        self.put(text)
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = self.rs.check_verdict(self.verdict, tree_sha=asked)
        return code, printed.getvalue()

    def test_an_old_shape_file_prints_unidentified_and_exits_nonzero(self):
        code, printed = self.run_instrument(OLD_SHAPE, SHA_A)
        self.assertEqual("UNIDENTIFIED", state_line(printed), printed)
        self.assertNotEqual(0, code, printed)

    def test_a_file_from_another_tree_prints_stale_mismatch(self):
        code, printed = self.run_instrument(
            "tree_sha=%s\nstatus=PASS\n" % SHA_A, SHA_B)
        self.assertEqual("STALE-MISMATCH", state_line(printed), printed)
        self.assertEqual(3, code, printed)

    def test_a_file_from_this_tree_prints_match_and_exits_zero(self):
        code, printed = self.run_instrument(
            "tree_sha=%s\nstatus=PASS\n" % SHA_A, SHA_A)
        self.assertEqual("MATCH", state_line(printed), printed)
        self.assertEqual(0, code, printed)

    def test_both_arms_from_one_instrument_in_one_test(self):
        """STALE-MISMATCH and MATCH, printed once each by the same reader."""
        code_stale, stale = self.run_instrument(
            "tree_sha=%s\nstatus=PASS\n" % SHA_A, SHA_B)
        code_match, match = self.run_instrument(
            "tree_sha=%s\nstatus=PASS\n" % SHA_A, SHA_A)
        self.assertEqual(1, stale.count("state="), stale)
        self.assertEqual(1, match.count("state="), match)
        self.assertEqual("STALE-MISMATCH", state_line(stale), stale)
        self.assertEqual("MATCH", state_line(match), match)
        self.assertNotIn("state=MATCH", stale, stale)
        self.assertEqual((3, 0), (code_stale, code_match),
                         "stale:\n%s\nmatch:\n%s" % (stale, match))

    def test_a_file_with_no_sha_is_not_printed_as_a_match(self):
        code, printed = self.run_instrument(
            "status=PASS\nfailures=0\nexit_code=0\n", SHA_A)
        self.assertNotIn("state=MATCH", printed, printed)
        self.assertNotEqual(0, code, printed)


class TheIdentityMovesNothingElse(VerdictFixture):
    """The existing reader of this file must see exactly what it saw before.

    `scripts/task123_diff_failures.py` reads failure names out of the verdict
    by looking for a trailing parenthesised name. MEASURED here, on a verdict
    of either shape, it returns exactly one string - `failures=1, errors=1`,
    taken from the `result_line=` field - and NEITHER of the two real failure
    names, which the verdict writes unparenthesised. That is a pre-existing
    defect in the reader (it was written for the closing-summary form), it is
    unchanged by this task, and it is recorded for the operator rather than
    fixed here. What this class holds is the only thing this change is allowed
    to affect: that set is the SAME before and after the identity lines.
    """

    def failure_set(self, text):
        reader = load(TASK123, "task123_under_test")
        self.put(text)
        return reader.extract_failures_from_verdict(self.verdict)

    def test_the_new_lines_add_no_names_to_the_existing_reader(self):
        new = self.verdict_of(tree_sha=SHA_A, mode="unittest")
        without = "".join(line + "\n" for line in new.splitlines()
                          if not line.startswith(
                              ("tree_sha=", "written_at=", "mode=")))
        self.assertNotEqual(without, new,
                            "the identity lines are not in the verdict at "
                            "all:\n" + new)
        before = self.failure_set(without)
        after = self.failure_set(new)
        self.assertEqual(before, after,
                         "the identity lines moved the failure set: %r -> %r"
                         % (sorted(before), sorted(after)))

    def test_an_old_shape_file_reads_the_same_as_a_new_one(self):
        old = self.failure_set(OLD_SHAPE)
        new = self.failure_set(self.verdict_of(tree_sha=SHA_A, mode="unittest"))
        self.assertEqual(old, new,
                         "a verdict written before this change is not read "
                         "the same way as one written after it: %r -> %r"
                         % (sorted(old), sorted(new)))

    def test_the_quoted_old_shape_is_what_the_writer_writes(self):
        """The literal above is the shape the writer actually produces.

        `OLD_SHAPE` is quoted from a base run. If the writer's own non-identity
        lines drift from it, the STALE-MISMATCH and UNIDENTIFIED arms would be
        testing a file nobody writes - so the two are compared here line for
        line, with the identity lines removed and the log path blanked, the
        one line a fixture cannot reproduce verbatim.
        """
        new = self.verdict_of(tree_sha=SHA_A, mode="unittest")
        without = [blank_log_path(line) for line in new.splitlines()
                   if not line.startswith(
                       ("tree_sha=", "written_at=", "mode="))]
        quoted = [blank_log_path(line) for line in OLD_SHAPE.splitlines()]
        self.assertEqual(quoted, without,
                         "the quoted old shape is not what the writer writes")


if __name__ == "__main__":
    unittest.main()