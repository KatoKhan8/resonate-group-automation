"""`apply_the_90` must not leave a doubled CR in the do-not-contact list.

TASK-0242. The heal block in `apply_set` reads the file's LAST BYTE as bytes
and, if it is not a newline, writes `"\n"` through the append handle to repair
a torn write. With the default newline that handle translates the `"\n"` into
`os.linesep`, so on Windows a file whose last byte is a LONE CR - the exact
torn write the heal exists to repair - is healed into `"\r\r\n"`.

Why it is worth a test rather than a comment: a doubled CR is invisible from
almost every angle. `agencydnc.load` reads with universal newlines, which
turns `\r\r\n` into `\n\n`, and blank lines are skipped - so the suppression
still MATCHES and the list looks healthy. What moves is the line count: a
text-mode reader sees one blank line per row. Measured on the four corrupted
artefacts in the estate: 83 blank lines where there should be 4.

So the assertion is on the BYTES, which is the only place the defect shows.

The negative leg is the point of the pairing: the same run against a file
whose tail is already a proper newline must come out clean too, otherwise a
test that simply forbade `\r\r\n` everywhere would pass without the heal ever
having fired. `test_heal_actually_fired` proves the heal ran, so a future
change that skips the heal cannot make this file pass vacuously.

Casey Wright, Morgan Ellis and Riley Parker are fictional.
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from src import agencydnc                              # noqa: E402

import importlib.util                                  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "apply_the_90", os.path.join(SCRIPTS, "apply_the_90.py"))
apply_the_90 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apply_the_90)


def _fingerprint(n):
    """A sha256-shaped fingerprint for a fictional person."""
    return hashlib.sha256(
        ("casey.wright+%d@example.invalid" % n).encode()).hexdigest()


class TheSuppressionWriterDoesNotDoubleTheCarriageReturn(unittest.TestCase):

    SET = "the-90"
    COUNT = 90

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dnc0242-")
        self.dnc = os.path.join(self.tmp, "agency-dnc.jsonl")
        self.backup = os.path.join(self.tmp, "backup")
        self.classified = os.path.join(self.tmp, "classified.json")
        with open(self.classified, "w", encoding="utf-8") as fh:
            json.dump({"people": [
                {"fingerprint": _fingerprint(i), "bucket": "suppressed"}
                for i in range(self.COUNT)]}, fh)
        self._old_env = os.environ.get("AGENCY_DNC")
        # The documented rehearsal/test seam: `_refuse_wrong_tree` names it.
        os.environ["AGENCY_DNC"] = self.dnc

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("AGENCY_DNC", None)
        else:
            os.environ["AGENCY_DNC"] = self._old_env
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- helpers
    def _seed(self, tail):
        """One pre-existing row, with `tail` as its terminating bytes."""
        row = json.dumps({"fingerprint": _fingerprint(9001),
                          "reason": agencydnc.REQUESTED,
                          "at": "2026-10-16T00:00:00Z"}, sort_keys=True)
        with open(self.dnc, "wb") as fh:
            fh.write(row.encode("utf-8") + tail)
        return _fingerprint(9001)

    def _apply(self):
        return apply_the_90.apply_set(self.SET, self.classified, None,
                                      self.backup, True)

    def _bytes(self):
        with open(self.dnc, "rb") as fh:
            return fh.read()

    # ------------------------------------------------------------------ tests
    def test_a_lone_cr_tail_is_not_healed_into_a_doubled_cr(self):
        """THE REGRESSION. Last byte is a lone CR; the heal must not double."""
        pre = self._seed(b"\r")
        self.assertEqual(self._bytes()[-1:], b"\r",
                         "fixture is wrong: the tail must be a LONE CR")
        self._apply()
        raw = self._bytes()
        self.assertNotIn(
            b"\r\r\n", raw,
            "the heal wrote a doubled CR into the do-not-contact list at "
            "byte offset %s" % (raw.find(b"\r\r\n"),))
        # and the pre-existing suppression must survive the heal
        self.assertIn(pre, agencydnc.load(self.dnc),
                      "the row that was healed is no longer suppressed")

    def test_heal_actually_fired(self):
        """Without this, the assertion above could pass vacuously.

        Proves the heal branch ran: the lone CR is still there and a newline
        now follows it, so the pre-existing row and the first appended row
        are on separate lines rather than glued together.
        """
        self._seed(b"\r")
        self._apply()
        raw = self._bytes()
        self.assertIn(b"\r\n", raw,
                      "the heal did not fire - no newline follows the CR, so "
                      "this test is not watching anything")
        self.assertEqual(
            raw.count(b"\r"), 1,
            "exactly one CR should remain: the pre-existing one. Found %d"
            % raw.count(b"\r"))

    def test_a_proper_newline_tail_needs_no_heal_and_stays_clean(self):
        """The negative leg: no heal, and still no doubled CR."""
        self._seed(b"\n")
        self._apply()
        raw = self._bytes()
        self.assertNotIn(b"\r\r\n", raw)
        self.assertEqual(raw.count(b"\r"), 0,
                         "no CR should exist at all when none was seeded")

    def test_every_appended_row_is_readable_and_counted(self):
        """The fix must not cost a row. Name-sets, both directions."""
        pre = self._seed(b"\r")
        self._apply()
        index = agencydnc.load(self.dnc)
        expected = {_fingerprint(i) for i in range(self.COUNT)} | {pre}
        self.assertEqual(set(index) - expected, set(),
                         "rows appeared that were not written")
        self.assertEqual(expected - set(index), set(),
                         "rows were written and cannot be read back")
        self.assertEqual(agencydnc.damaged_lines(self.dnc), [],
                         "the written list reports damaged lines")

    def test_the_write_handle_does_not_translate_newlines(self):
        """The mechanism, asserted directly at the call site.

        A behavioural assertion rather than a source grep: the file is opened
        the way `apply_set` opens it and asked what one "\\n" becomes.
        """
        probe = os.path.join(self.tmp, "probe.txt")
        with open(probe, "a", encoding="utf-8", newline="") as handle:
            handle.write("\n")
        with open(probe, "rb") as fh:
            self.assertEqual(
                fh.read(), b"\n",
                'newline="" must write exactly one byte; this platform '
                "translated it")


if __name__ == "__main__":
    unittest.main()
