"""ISSUE-019, from the other end: the ruling was enforced only at the writer.

`4afb54d5` implemented the operator's QUALIFIED-only ruling in
`nightlysourcing`, where records ENTER the candidate list, and the register
recorded it as implemented and standing. It is - for records added after it.

`candidates.jsonl` already held 1,394 REVIEW records when it landed, and
`candidateexport.exportable_candidates()` filtered on `state == "new"` and
nothing else. So every one of them was still exportable, and calling the
function on 2026-09-24 returned all 1,508 rows: 1,394 REVIEW, 1,410 at
`icp_score` 0.0, median headcount 16,745, for a client who sells to 20+
person marketing and creative agencies.

A gate at the writer protects the future. A gate at the reader protects the
file as it is. These tests are about the reader.

THEY DO NOT CLAIM THE EXPORT CAN SHIP. ISSUE-023 is open and separate: the
114 QUALIFIED rows are themselves wrong, 58 of them scoring 0.0 while passing
structurally. Dropping REVIEW removes undecided rows; it does not remove a
121,205-employee telecom the scorer affirmatively qualified. The last test
here pins that distinction so nobody reads a green suite as permission.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import candidateexport                                # noqa: E402


REVIEW = {"domain": "a.example", "state": "new", "icp_status": "review",
          "icp_score": 0.0, "headcount": 96438}
QUALIFIED = {"domain": "b.example", "state": "new", "icp_status": "qualified",
             "icp_score": 41.0, "headcount": 44}
EXPORTED = {"domain": "c.example", "state": "exported",
            "icp_status": "qualified", "icp_score": 38.0, "headcount": 60}


class TheReaderGatesOnTheVERDICT(unittest.TestCase):

    def _with(self, rows):
        from src import candidatelist
        real = candidatelist.load
        candidatelist.load = lambda: list(rows)
        self.addCleanup(setattr, candidatelist, "load", real)
        return candidateexport.exportable_candidates()

    def test_a_review_record_is_not_exportable(self):
        got = self._with([REVIEW])
        self.assertEqual(got, [], "REVIEW is not a verdict and may not ship")

    def test_a_qualified_new_record_is_exportable(self):
        self.assertEqual(len(self._with([QUALIFIED])), 1)

    def test_the_state_gate_still_applies(self):
        """Already exported stays out - this adds a condition, not replaces."""
        self.assertEqual(self._with([EXPORTED]), [])

    def test_the_mixed_file_yields_only_the_qualified_one(self):
        got = self._with([REVIEW, QUALIFIED, EXPORTED])
        self.assertEqual([r["domain"] for r in got], ["b.example"])

    def test_a_missing_verdict_is_not_exportable(self):
        """Absent is not qualified. Missing evidence is never positive."""
        self.assertEqual(self._with([{"domain": "d.example", "state": "new"}]), [])

    def test_the_verdict_is_compared_case_and_space_insensitively(self):
        row = dict(QUALIFIED, icp_status="  QUALIFIED ")
        self.assertEqual(len(self._with([row])), 1)

    def test_only_qualified_is_exportable(self):
        self.assertEqual(candidateexport.EXPORTABLE_ICP, "qualified")


class ThisDoesNotUnblockTheExport(unittest.TestCase):
    """ISSUE-023 is open and this change does not touch it."""

    def test_a_zero_scoring_enterprise_that_is_QUALIFIED_still_passes(self):
        """The defect ISSUE-023 names, asserted so nobody thinks it is gone.

        A 121,205-employee telecom that the scorer affirmatively qualified at
        `icp_score` 0.0 is still exportable after this fix, because the fault
        is in the verdict rather than in who reads it. The export stays
        STOPPED on the operator's scorer-threshold decision.
        """
        from src import candidatelist
        telecom = {"domain": "e.example", "state": "new",
                   "icp_status": "qualified", "icp_score": 0.0,
                   "headcount": 121205}
        real = candidatelist.load
        candidatelist.load = lambda: [telecom]
        self.addCleanup(setattr, candidatelist, "load", real)
        self.assertEqual(len(candidateexport.exportable_candidates()), 1,
                         "if this ever returns 0, ISSUE-023 was fixed "
                         "somewhere else and this test should be rewritten "
                         "rather than deleted")


if __name__ == "__main__":
    unittest.main()
