"""The reversal refuses a damaged line its own pre-pass could not have seen.

TASK-0249. `acde88597` (TASK-0245) repaired `agencydnc._rows_in` so that a
value which decodes cleanly but is not an object counts as DAMAGE. It
deliberately did not touch `scripts/apply_the_90.py`, on the reasoning that one
fix in `_rows_in` closes the reversal site too. TASK-0249 traced line 426's
rows back to where they enter the process and that reasoning holds: the route
is `open(path)` -> `line` -> `line.strip()` -> `agencydnc._rows_in(stripped)`
-> `rows` -> `row.get("fingerprint")`, one hop, through the repaired function.
COVERED.

What the trace also showed is the part the repair could not reach from inside
`_rows_in`, because it is not a defect in `_rows_in` at all:

    412   damaged = agencydnc.damaged_lines(path)      <- reads the file
    413   if damaged: _refuse(...)
    ...
    418   with open(path) as handle:                   <- reads it AGAIN
    424       rows, _bad = agencydnc._rows_in(stripped)
    426           digest = row.get("fingerprint")

Those are two separate reads of the same file, and `_bad` on line 424 is
discarded. So the guard's answer is about the file as it was at line 412, and
the loop acts on the file as it is at line 418. The script's own docstring
(lines 55-59) says a row arriving between apply and reversal is expected and
names two writers that can do it - that is the whole reason the reversal is a
rewrite rather than a byte restore. A line that becomes damaged inside that
window is therefore not hypothetical, and today it is absorbed in silence:
`_rows_in` correctly reports `damaged=True`, nobody reads it, the unreadable
bytes are left out of `kept`, and `kept` is what gets written back over the
roster at lines 454-459.

Measured on the pre-repair code (TASK-0249 SS2): every non-row shape raised
`AttributeError` at line 426, which is thirty lines ABOVE the write, so the
old defect could only ever deny the reversal and never corrupt the file. The
repair turned that raise into a silent completion. That is the right outcome
for `_rows_in` and the wrong one for a reversal that then rewrites the file,
and it is why the refusal belongs at line 424 rather than anywhere in `src/`.

A corrupt line suppressing nobody is the failure `_rows_in`'s own docstring was
written to condemn. A reversal silently deleting one is worse, because it is
permanent.

The pairing is the point throughout: every assertion that the reversal refuses
is matched by one that an undamaged reversal still completes, because a script
that refuses everything protects the roster exactly as well as one that
refuses nothing and is just as useless.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import agencydnc                                      # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "apply_the_90.py")

#: A line that decodes cleanly and is not a row. `_rows_in` reports it as
#: damage since `acde88597`; before that it reported the file as healthy.
SCALAR = "3"

#: A line whose tail is gone. The original damage class, detected both before
#: and after that commit.
TORN = '{"at": "2026-10-16T09:00:00Z", "fingerp'


def _script():
    """The script imported, so `revert()` can be called directly.

    By path, because `scripts/` is not a package - the same way
    `test_a_restore_keeps_the_suppressions.py` loads its drill. Importing is
    side-effect free: everything executable sits under `main()` behind an
    `if __name__ == "__main__"` guard.
    """
    spec = importlib.util.spec_from_file_location("apply_the_90", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(digest):
    return json.dumps({"fingerprint": digest, "reason": agencydnc.REQUESTED,
                       "at": "2026-10-16T09:00:00Z"}, sort_keys=True)


class TheReversalRefusesALineThePrepassDidNotSee(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="task0249-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.script = _script()

        self.doomed = agencydnc.fingerprint("email", "doomed@example.test")
        self.keeper = agencydnc.fingerprint("email", "keeper@example.test")

        # `agencydnc.path()` resolves per call and honours AGENCY_DNC, which
        # exists so a test can point it somewhere disposable. Production
        # `work/` is never on this path.
        self.roster = os.path.join(self.tmp, "agency-dnc.jsonl")
        previous = os.environ.get("AGENCY_DNC")
        os.environ["AGENCY_DNC"] = self.roster
        self.addCleanup(self._restore_env, previous)

        self._write(_row(self.doomed), _row(self.keeper))
        self.manifest = os.path.join(self.tmp, "manifest.json")
        with open(self.manifest, "w", encoding="utf-8") as handle:
            json.dump({"file": self.roster, "set": "the-90",
                       "added": [self.doomed],
                       "before": {"fingerprints": [self.keeper],
                                  "sha256": self._sha256()}}, handle)

    @staticmethod
    def _restore_env(previous):
        if previous is None:
            os.environ.pop("AGENCY_DNC", None)
        else:
            os.environ["AGENCY_DNC"] = previous

    def _write(self, *lines):
        with open(self.roster, "wb") as handle:
            for line in lines:
                handle.write(line.encode("utf-8") + b"\n")

    def _append(self, line):
        with open(self.roster, "ab") as handle:
            handle.write(line.encode("utf-8") + b"\n")

    def _sha256(self):
        with open(self.roster, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def _revert(self):
        """`revert()` on the dry-run path, with its printing captured.

        DRY RUN ALWAYS. `do_apply=False` returns at line 444, before
        `store.refuse_production_write` and before any write, so no assertion
        in this module depends on the write path being safe to exercise - and
        a dry run that silently under-reports is itself the defect, because
        its "would keep N row(s)" is the number a person approves `--apply`
        on.
        """
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = self.script.revert(self.manifest, False)
        return code, buffer.getvalue()

    def _damage_inside_the_window(self, line):
        """Make the file become damaged BETWEEN line 412 and line 418.

        `damaged_lines` is not faked: it is called for real and its genuine,
        honest answer is returned. Only the timing is interposed - a writer
        lands a damaged line just after the guard has read the file, which is
        exactly what the script's docstring says can happen and what makes a
        guard that reads the file separately from the loop unable to bind.
        """
        real = agencydnc.damaged_lines
        self.addCleanup(setattr, agencydnc, "damaged_lines", real)
        appended = []

        def guard_then_write(file_path=None):
            answer = real(file_path)
            if not appended:
                appended.append(line)
                self._append(line)
            return answer

        agencydnc.damaged_lines = guard_then_write
        return appended

    # ------------------------------------------------------- THE REGRESSION
    def test_a_line_that_arrives_after_the_guard_is_refused(self):
        """BORN RED. Today the loop absorbs it and reports a short count."""
        appended = self._damage_inside_the_window(SCALAR)
        with self.assertRaises(SystemExit) as caught:
            self._revert()
        self.assertEqual(appended, [SCALAR],
                         "the window was never exercised; the writer did not "
                         "land its line")
        self.assertEqual(
            caught.exception.code, 2,
            "the reversal must refuse with the script's own refusal code")

    def test_the_refusal_names_why_the_prepass_could_not_see_it(self):
        """A refusal nobody can act on sends somebody to the wrong file."""
        self._damage_inside_the_window(SCALAR)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                self.script.revert(self.manifest, False)
        printed = buffer.getvalue()
        self.assertIn("REFUSED", printed)
        self.assertIn("cannot be fully read", printed)

    def test_the_torn_shape_is_refused_in_the_window_too(self):
        """Not only the scalar. The window is the defect, not one shape."""
        self._damage_inside_the_window(TORN)
        with self.assertRaises(SystemExit):
            self._revert()

    def test_nothing_is_written_when_it_refuses(self):
        """A refusal must leave the roster exactly as it found it.

        The third line is the interposed writer's, not the script's, so the
        assertion is that the file is the two original rows PLUS that line and
        nothing else - no rewrite, no reordering, no dropped bytes.
        """
        self._damage_inside_the_window(SCALAR)
        with self.assertRaises(SystemExit):
            self._revert()
        with open(self.roster, "rb") as handle:
            lines = handle.read().decode("utf-8").splitlines()
        self.assertEqual(
            lines, [_row(self.doomed), _row(self.keeper), SCALAR],
            "the roster is not what it was plus the interposed line; a "
            "refusal must not rewrite the file")

    # ------------------------------------------- the paired negative legs
    def test_an_undamaged_reversal_still_completes(self):
        """Without this the assertions above pass vacuously.

        A reversal that refuses every file protects the roster exactly as
        well as one that refuses none, and is just as useless.
        """
        code, printed = self._revert()
        self.assertEqual(code, 0, "a clean reversal was refused:\n%s" % printed)
        self.assertIn("would remove  1 physical row(s)", printed)
        self.assertIn("would keep    1 row(s)", printed)
        self.assertIn("DRY RUN", printed)

    def test_a_clean_reversal_writes_nothing_either(self):
        before = self._sha256()
        self._revert()
        self.assertEqual(self._sha256(), before)

    def test_damage_present_before_the_call_is_still_refused_at_412(self):
        """The existing guard is not replaced by the new one.

        This line is in the file when `damaged_lines` is asked, so the
        refusal must come from line 413 - and it must still come.

        WHICH guard answers is asserted, not just that something refused.
        Both refusals exit 2 and both say "cannot be fully read", so a test
        that checked only the exit code would pass while the pre-pass had
        gone dead and the loop was doing all the work - and this test passed
        BEFORE the line-424 refusal existed, which is what makes it the
        control for the other direction.
        """
        self._append(SCALAR)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit) as caught:
                self.script.revert(self.manifest, False)
        printed = buffer.getvalue()
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("lines [3] cannot be fully read", printed,
                      "this is not the line-412 pre-pass refusal")
        self.assertNotIn(
            "though", printed,
            "the line-424 refusal answered, so the pre-pass never saw damage "
            "that was in the file before it was asked")

    def test_a_glued_pair_is_not_damage_and_does_not_refuse(self):
        """Two whole rows on one physical line is the case `_rows_in` exists
        for. It is recoverable, so it is NOT damage, and a reversal must not
        refuse on it - otherwise one torn write in the past makes the roster
        permanently un-reversible.
        """
        self._write(_row(self.doomed) + _row(self.keeper))
        code, printed = self._revert()
        self.assertEqual(code, 0, printed)
        self.assertIn("would remove  1 physical row(s)", printed)


if __name__ == "__main__":
    unittest.main()
