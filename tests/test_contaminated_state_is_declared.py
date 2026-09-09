"""Contaminated state files say so, where somebody is already looking.

Two files in `work/` hold test fixtures written before the store barrier
covered anything but the queue. The barrier is closed, so nothing new lands -
but the reading of what is already there was never closed, and it had already
cost something: PRODUCT-GAPS section 22 item 9 cited `work/replywatch.json` as
evidence that reply detection is down. A red team read
`tests/test_replywatch.py`'s error strings as a production signal, because
nothing on any screen said the file was contaminated.

Clearing the files is a destructive write to client state and is a human
decision. So the registry stands in for it - and a registry nothing reads is
the defect this repository keeps finding, which is why the consumption test
below matters more than the registry test.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import check, contamination, store


class TheRegistryDescribesRealFiles(unittest.TestCase):
    def test_every_entry_names_a_file_beside_the_queue(self):
        for entry in contamination.REGISTRY:
            with self.subTest(file=entry.filename):
                self.assertEqual(os.path.dirname(entry.path()),
                                 os.path.dirname(store.queue_path()))

    def test_every_entry_says_what_may_not_be_concluded(self):
        """The useful half. "This file is dirty" stops nobody drawing the
        conclusion anyway."""
        for entry in contamination.REGISTRY:
            with self.subTest(file=entry.filename):
                self.assertTrue(entry.do_not_conclude.strip())
                self.assertTrue(entry.why.strip())
                self.assertTrue(entry.marker.strip())

    def test_the_report_shape_is_stable(self):
        for row in contamination.report():
            self.assertEqual(
                set(row),
                {"file", "path", "present", "fixtures_still_present", "why",
                 "do_not_conclude", "since"})


class ContaminationIsReadFromTheFileNotAssumed(unittest.TestCase):
    """An entry must not outlive its subject.

    Otherwise the registry goes on discrediting a file somebody has rebuilt,
    and the only way to make the report clean is to delete the entry - which
    is how a registry becomes a formality.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-contam-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        saved = {n: os.environ.get(n)
                 for n in ("QUEUE",) + store.STATE_OVERRIDES}
        self.addCleanup(self._restore, saved)
        store.use_directory(os.path.join(self.tmp, "work"))
        self.entry = contamination.REGISTRY[0]

    @staticmethod
    def _restore(saved):
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _write(self, text):
        os.makedirs(os.path.dirname(self.entry.path()), exist_ok=True)
        with open(self.entry.path(), "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_a_missing_file_is_not_contaminated(self):
        self.assertFalse(self.entry.present())
        self.assertFalse(self.entry.proven())

    def test_a_clean_file_is_not_contaminated(self):
        self._write(json.dumps({"id": "draft-1", "created_by": "operator@resonate.test"}))
        self.assertTrue(self.entry.present())
        self.assertFalse(self.entry.proven())

    def test_a_file_still_holding_the_marker_is(self):
        self._write(json.dumps({"id": "draft-1", "created_by": "a@b.test"}))
        self.assertTrue(self.entry.proven())

    def test_the_check_goes_green_once_every_file_is_clean(self):
        self._write(json.dumps({"created_by": "operator@resonate.test"}))
        result = contamination.check()
        self.assertTrue(result["ok"])
        self.assertIn("no state file", result["note"])

    def test_the_check_fails_while_a_file_is_dirty(self):
        """FAIL, not SKIP. A diagnostic nobody can fail is one nobody reads."""
        self._write(json.dumps({"created_by": "a@b.test"}))
        result = contamination.check()
        self.assertFalse(result["ok"])
        self.assertFalse(result["skipped"])
        self.assertIn(self.entry.filename, result["note"])


class TheDiagnosticHasAConsumer(unittest.TestCase):
    """The half that matters. `killswitch` and `pilotcaps` were both computed
    correctly for weeks with no caller; this one is wired to the command an
    operator runs before a batch."""

    def test_check_imports_contamination(self):
        self.assertIs(check.contamination, contamination)

    def test_the_state_check_is_not_in_the_provider_sweep(self):
        """`run()` is the provider sweep. Contamination is not a provider, and
        `tests/test_check.py` asserts that list exactly - correctly."""
        self.assertNotIn("State files", [r["provider"] for r in check.run()])

    def test_the_operator_command_reports_it_and_fails_on_it(self):
        """Asserted through `check.main`, which is what an operator runs."""
        import contextlib
        import io as _io
        tmp = tempfile.mkdtemp(prefix="rga-contam-sweep-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        saved = {n: os.environ.get(n)
                 for n in ("QUEUE",) + store.STATE_OVERRIDES}
        self.addCleanup(ContaminationIsReadFromTheFileNotAssumed._restore,
                        saved)
        store.use_directory(os.path.join(tmp, "work"))
        entry = contamination.REGISTRY[0]
        os.makedirs(os.path.dirname(entry.path()), exist_ok=True)
        with open(entry.path(), "w", encoding="utf-8") as handle:
            handle.write('{"created_by": "a@b.test"}')
        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check.main([])
        self.assertIn("State files", out.getvalue())
        self.assertNotEqual(code, 0)

    def test_a_dirty_file_makes_the_sweep_exit_non_zero(self):
        """The operator-visible consequence, end to end through `main`."""
        tmp = tempfile.mkdtemp(prefix="rga-contam-cli-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        saved = {n: os.environ.get(n)
                 for n in ("QUEUE",) + store.STATE_OVERRIDES}
        self.addCleanup(ContaminationIsReadFromTheFileNotAssumed._restore,
                        saved)
        store.use_directory(os.path.join(tmp, "work"))
        entry = contamination.REGISTRY[0]
        os.makedirs(os.path.dirname(entry.path()), exist_ok=True)
        with open(entry.path(), "w", encoding="utf-8") as handle:
            handle.write('{"created_by": "a@b.test"}')
        self.assertEqual(contamination.main([]), 1)

    def test_it_reports_zero_when_nothing_is_contaminated(self):
        tmp = tempfile.mkdtemp(prefix="rga-contam-clean-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        saved = {n: os.environ.get(n)
                 for n in ("QUEUE",) + store.STATE_OVERRIDES}
        self.addCleanup(ContaminationIsReadFromTheFileNotAssumed._restore,
                        saved)
        store.use_directory(os.path.join(tmp, "work"))
        self.assertEqual(contamination.main([]), 0)


if __name__ == "__main__":
    unittest.main()
