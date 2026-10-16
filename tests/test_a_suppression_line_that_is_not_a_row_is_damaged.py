"""A do-not-contact line that decodes to a scalar is DAMAGED, not a row.

TASK-0245. `_rows_in` recovers every JSON value on one physical line, which it
was written to do because a torn write glues two rows together. It did not
check that a recovered value is an OBJECT, and two things followed:

1. `load` iterates those values and calls `row.get("fingerprint")`. A line
   holding `"x"`, `3`, `null`, `true`, `1.5` or `[1, 2]` reaches that line and
   raises `AttributeError`. `lookup` is on the send path, so that is no answer
   at the moment the code is deciding whether a human may be contacted - and
   `strict=True`, which exists so a caller can refuse rather than under-report
   the roster, raises the wrong exception from the wrong line before it can
   refuse.

2. `damaged_lines` returns `[]` for the same file. `[]` is its word for
   healthy, and its docstring says it exists so that "the file is clean" is a
   measurement rather than an assumption. The instrument built to find this
   could not see it.

The second defect is what makes the first dangerous rather than merely rude.
`scripts/apply_the_90.py` opens its `--revert` path by refusing when
`damaged_lines` reports anything - the correct guard, deliberately placed - and
then walks the rows calling `row.get("fingerprint")` itself at line 425. A
scalar line is `damaged=False`, so it passes the only guard written to stop it
and kills the reversal instead. One fix in `_rows_in` closes both.

Recovery is preserved on purpose: a good row glued to a scalar still yields the
good row AND reports the line, because "a corrupt line suppresses nobody" is
the failure this module's own docstring was written to condemn.

The pairing is the point. A detector that calls everything damaged is as
useless as one that calls nothing damaged, so every assertion that something
IS damaged is matched by one that a healthy file is still healthy.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import agencydnc                              # noqa: E402

# Every shape a JSON line can take that is not an object. The array is here
# because the guard has to be "is this a row", not "is this a scalar".
NOT_A_ROW = {
    "string": '"x"',
    "int": "3",
    "null": "null",
    "true": "true",
    "float": "1.5",
    "list": "[1, 2]",
}

EMAIL = "sarah@acme.test"


def _row(digest, reason=agencydnc.REQUESTED):
    return json.dumps({"fingerprint": digest, "reason": reason,
                       "at": "2026-10-16T09:00:00Z"}, sort_keys=True)


class ASuppressionLineThatIsNotARowIsDamaged(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="task0245-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.real = agencydnc.fingerprint("email", EMAIL)

    def _write(self, *lines):
        """One file, one line per argument, written as bytes.

        Bytes rather than text mode so the fixture cannot pick up this tree's
        line-ending flavour - the same file has to mean the same thing in the
        LF trees and the CRLF ones.
        """
        path = os.path.join(self.tmp, "agency-dnc.jsonl")
        with open(path, "wb") as handle:
            for line in lines:
                handle.write(line.encode("utf-8") + b"\n")
        return path

    # ------------------------------------------------- the raise, every shape
    def test_load_does_not_raise_on_a_line_that_is_not_a_row(self):
        """THE REGRESSION. Six shapes, each on its own file."""
        for name, payload in NOT_A_ROW.items():
            with self.subTest(shape=name):
                path = self._write(payload)
                try:
                    index = agencydnc.load(path)
                except AttributeError as exc:
                    self.fail(
                        "load raised on a %s line (%s): %s. lookup is on the "
                        "send path, so this is no answer while deciding "
                        "whether a human may be contacted"
                        % (name, payload, exc))
                self.assertEqual(
                    index, {},
                    "a %s line is not a row and must contribute no "
                    "suppression" % name)

    def test_lookup_answers_instead_of_raising(self):
        """The send path itself, not only `load`.

        The file holds a real suppression AND a scalar. `lookup` must still
        say the person is suppressed - losing the good row would be the
        fail-open this module exists to prevent.
        """
        path = self._write(NOT_A_ROW["int"], _row(self.real))
        index = agencydnc.load(path)
        notice = agencydnc.lookup({"email": EMAIL}, index=index)
        self.assertIsNotNone(
            notice,
            "the good row on the same file as a scalar was lost; a torn "
            "write must not un-suppress somebody who asked to be removed")
        self.assertIn(agencydnc.NOTICE, notice)

    def test_the_index_class_survives_it_too(self):
        """`hygiene.check` asks `Index.get`, so it must load at all."""
        path = self._write(NOT_A_ROW["null"], _row(self.real))
        index = agencydnc.Index(agencydnc.load(path))
        self.assertEqual(len(index), 1)
        self.assertIn(agencydnc.NOTICE, index.get("email:%s" % EMAIL))

    # ------------------------------------------- C2, the paired detector legs
    def test_damaged_lines_reports_a_line_that_is_not_a_row(self):
        """POSITIVE LEG. The instrument must see it."""
        for name, payload in NOT_A_ROW.items():
            with self.subTest(shape=name):
                path = self._write(payload)
                self.assertEqual(
                    agencydnc.damaged_lines(path), [1],
                    "damaged_lines called a file healthy whose %s line takes "
                    "load down; [] is its word for healthy" % name)

    def test_a_healthy_file_is_still_healthy(self):
        """NEGATIVE LEG, and without it the leg above passes vacuously.

        Three real rows, a comment and a blank line - everything `load`
        documents as legitimate. A detector that reported damage here would
        satisfy the positive leg while being worthless.
        """
        path = self._write(
            "# the agency do-not-contact list",
            _row(self.real),
            "",
            _row("b" * 64, agencydnc.LEGAL),
            _row("c" * 64, agencydnc.INTERNAL))
        self.assertEqual(agencydnc.damaged_lines(path), [],
                         "a healthy file was reported damaged")
        self.assertEqual(len(agencydnc.load(path)), 3)

    def test_a_glued_pair_is_still_recovered_and_still_healthy(self):
        """The case `_rows_in` was written for must not regress.

        Two complete objects on one physical line is a torn write that has
        already been glued. Both rows are recoverable, so the line is NOT
        damaged and both must load.
        """
        path = self._write(_row(self.real) + _row("b" * 64))
        self.assertEqual(agencydnc.damaged_lines(path), [])
        self.assertEqual(len(agencydnc.load(path)), 2)

    def test_a_good_row_glued_to_a_scalar_keeps_the_good_row(self):
        """Recovery and reporting at the same time, which is the contract."""
        path = self._write(_row(self.real) + "3")
        self.assertEqual(
            agencydnc.damaged_lines(path), [1],
            "the scalar on this line was not reported")
        index = agencydnc.load(path)
        self.assertIn(
            self.real, index,
            "the recoverable row was discarded; discarding the line is the "
            "behaviour this module replaced")

    def test_a_torn_tail_is_still_damaged(self):
        """The original damage class must keep being detected."""
        path = self._write('{"at": "2026-10-16T09:00:00Z", "fingerp')
        self.assertEqual(agencydnc.damaged_lines(path), [1])
        self.assertEqual(agencydnc.load(path), {})

    # -------------------------------------------------------- the strict leg
    def test_strict_refuses_with_the_roster_message(self):
        """`strict=True` must refuse, in its own words, not crash."""
        path = self._write(NOT_A_ROW["string"], _row(self.real))
        with self.assertRaises(ValueError) as caught:
            agencydnc.load(path, strict=True)
        self.assertIn("could not be fully read", str(caught.exception))
        self.assertNotIsInstance(
            caught.exception, AttributeError,
            "strict raised the wrong exception from the wrong line")

    # --------------------------------- the contract two other call sites read
    def test_rows_in_hands_back_only_rows(self):
        """`scripts/apply_the_90.py:425` calls `.get` on these directly.

        It does so AFTER refusing on `damaged_lines`, so a value that decodes
        cleanly and is not a row walks past the guard and kills the reversal.
        The contract this asserts is what makes that site safe without
        touching it.
        """
        for name, payload in NOT_A_ROW.items():
            with self.subTest(shape=name):
                rows, damaged = agencydnc._rows_in(_row(self.real) + payload)
                self.assertTrue(
                    damaged,
                    "a %s value on the line was not reported as damage, so "
                    "the reversal guard cannot see it" % name)
                self.assertTrue(
                    all(isinstance(r, dict) for r in rows),
                    "_rows_in handed back a %s; every caller does "
                    "row.get(...) on these" % name)


if __name__ == "__main__":
    unittest.main()
