"""REVIEW is not a verdict, and it may never reach a client export.

ISSUE-019. The first candidate export the operator asked to send Productive was
STOPPED because `_icp_verdict` survived on QUALIFIED **or** REVIEW. 1,508
candidates came out with a median headcount of 16,745, nothing under 20 staff,
a 130,377-employee bank at `icp_score 0.0` and a national education ministry -
for a client who sells to 20+ person agencies. Every row's `why_matched` read
"scored above threshold", and that column is what the client reads.

Operator ruling, 2026-09-22: QUALIFIED only; REVIEW goes to further enrichment.

These tests are written against the defect, not the happy path: the load-bearing
one is that a REVIEW record is ROUTED rather than either exported or discarded.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import icp, nightlysourcing  # noqa: E402


def company(domain, **facts):
    base = {"domain": domain, "company": facts.get("name", domain),
            "headcount": facts.get("headcount"), "industry": facts.get("industry", ""),
            "country": facts.get("country", ""), "description": "",
            "services": [], "specialties": []}
    return base


class _Verdict:
    """A stubbed scorer, so these tests pin the ROUTING and not the ICP rules."""

    def __init__(self, status, score=0.0):
        self.status, self.score = status, score

    def __call__(self, rec, config=None):
        return {"icp_status": self.status, "icp_score": self.score,
                "criteria": {}}


class TestOnlyQualifiedReachesTheCandidateList(unittest.TestCase):

    def setUp(self):
        self._score = icp.score

    def tearDown(self):
        icp.score = self._score

    def test_a_review_record_never_survives(self):
        """The one-line defect that stopped the export."""
        icp.score = _Verdict(icp.REVIEW, 0.0)
        rows = [company("undecided.example.test")]
        survived = nightlysourcing._icp_verdict(rows)
        self.assertEqual(survived, [],
                         "REVIEW reached the candidate list; that is ISSUE-019")

    def test_a_qualified_record_survives(self):
        icp.score = _Verdict(icp.QUALIFIED, 0.9)
        rows = [company("agency.example.test")]
        survived = nightlysourcing._icp_verdict(rows)
        self.assertEqual([c["domain"] for c in survived],
                         ["agency.example.test"])

    def test_the_zero_scored_bank_cannot_come_back(self):
        """The concrete row from ISSUE-019: review status at icp_score 0.0."""
        icp.score = _Verdict(icp.REVIEW, 0.0)
        rows = [company("large-bank.example.test", headcount=130377,
                        industry="banking", country="ES")]
        self.assertEqual(nightlysourcing._icp_verdict(rows), [])


class TestReviewIsRoutedAndNotDiscarded(unittest.TestCase):
    """Undecided is not rejected. Throwing it away is a different wrong answer."""

    def setUp(self):
        self._score = icp.score

    def tearDown(self):
        icp.score = self._score

    def test_review_is_marked_for_enrichment(self):
        icp.score = _Verdict(icp.REVIEW, 0.4)
        row = company("undecided.example.test")
        nightlysourcing._icp_verdict([row])
        self.assertEqual(row.get("_route"), nightlysourcing.ROUTE_ENRICHMENT)
        self.assertEqual(row.get("_drop_reason"), f"icp_{icp.REVIEW}")

    def test_an_outright_rejection_is_not_routed_to_enrichment(self):
        """A decided NO is not an enrichment task, and must not look like one."""
        icp.score = _Verdict("out", 0.0)
        row = company("not-an-agency.example.test")
        nightlysourcing._icp_verdict([row])
        self.assertIsNone(row.get("_route"))

    def test_review_keeps_its_status_and_score_for_the_enrichment_path(self):
        icp.score = _Verdict(icp.REVIEW, 0.42)
        row = company("undecided.example.test")
        nightlysourcing._icp_verdict([row])
        self.assertEqual(row.get("_icp_status"), icp.REVIEW)
        self.assertEqual(row.get("_icp_score"), 0.42)


if __name__ == "__main__":
    unittest.main()
