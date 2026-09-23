"""Explainable verdicts: a reason from evidence, not from the verdict.

TASK-272.  One plain-language reason per domain beside the QUALIFIED flag
in every export.  The reason is assembled from the positive signals the
scorer actually found - not from the verdict, because a reason generated
from the verdict is the defect ISSUE-019 / ISSUE-023 pinned: "scored above
threshold" on rows that scored 0.0.

Acceptance:
  - a row scoring 0.0 cannot produce a pass-shaped reason
  - a row with no evidence produces no reason and does not export
  - the reason carries no person-level field
  - the telecom and bank rows from ISSUE-019/023 produce reasons a reader
    would recognise as wrong-fit (or empty, since they are not QUALIFIED)
  - candidateexport's existing column is unchanged
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (candidateexport, clientexport, icp,                   # noqa: E402
                 nightlysourcing)

PRODUCTIVE = {
    "icp": {
        "structural": {
            "geographies": {
                "include": ["United Kingdom", "Spain", "Sweden", "Finland",
                            "United States", "Germany", "France"],
                "exclude": ["India", "Singapore"],
            },
        },
    },
}


def _company(name, employees, industry, country, description="",
             services=None, specialties=None):
    return {"domain": f"{name}.example.test", "company": name,
            "company_facts": {"name": name, "employees": employees,
                              "industry": industry, "description": description,
                              "offices": [country] if country else [],
                              "country": country,
                              "services": services or [],
                              "specialties": specialties or []}}


def _record_with_verdict(verdict):
    """A minimal record with a stored qualification verdict."""
    return {"domain": "test.example.test", "company": "TestCo",
            "company_facts": {"name": "TestCo", "employees": 50,
                              "industry": "marketing", "description": "",
                              "offices": ["United Kingdom"],
                              "country": "United Kingdom",
                              "services": [], "specialties": []},
            "qualification": {"verdict": verdict}}


class TestZeroScoreCannotProducePassReason(unittest.TestCase):
    """A row scoring 0.0 must not produce a reason that reads like a pass."""

    def test_evidence_text_empty_when_no_positive_signals(self):
        verdict = {"icp_status": icp.QUALIFIED, "icp_score": 0.0,
                   "positive_signals": []}
        self.assertEqual(icp.evidence_text(verdict), "")

    def test_evidence_text_empty_when_positive_signals_absent(self):
        verdict = {"icp_status": icp.QUALIFIED, "icp_score": 0.0}
        self.assertEqual(icp.evidence_text(verdict), "")

    def test_no_tautology_fallback(self):
        """The old fallback 'scored above threshold' must not appear."""
        verdict = {"icp_status": icp.QUALIFIED, "icp_score": 0.0,
                   "positive_signals": []}
        reason = icp.evidence_text(verdict).lower()
        self.assertNotIn("scored above threshold", reason)
        self.assertNotIn("above threshold", reason)

    def test_nightlysourcing_evidence_text_delegates(self):
        verdict = {"positive_signals": [], "icp_score": 0.0}
        self.assertEqual(nightlysourcing._icp_evidence_text(verdict), "")

    def test_a_zero_scored_real_company_produces_no_pass_reason(self):
        rec = _company("BigBank", 130377, "banking", "United States")
        verdict = icp.score(rec, config=PRODUCTIVE)
        reason = icp.evidence_text(verdict)
        if verdict["icp_score"] <= 0:
            self.assertNotIn("scored above", reason.lower())
            self.assertNotIn("qualified", reason.lower())


class TestNoEvidenceMeansNoReason(unittest.TestCase):
    """A row with no evidence produces no reason and does not export."""

    def test_clientexport_row_has_empty_reason_with_no_signals(self):
        verdict = {"icp_status": icp.QUALIFIED, "icp_score": 50.0,
                   "positive_signals": [], "negative_signals": []}
        rec = _record_with_verdict(verdict)
        segment = {"country": "United Kingdom"}
        row = clientexport._row_for(rec, segment)
        self.assertEqual(row["why it matched"], "")

    def test_clientexport_reason_for_empty_verdict(self):
        rec = _record_with_verdict({})
        self.assertEqual(clientexport._reason_for(rec), "")

    def test_clientexport_reason_for_no_qualification(self):
        rec = {"domain": "x.example.test", "company": "X",
               "company_facts": {}}
        self.assertEqual(clientexport._reason_for(rec), "")


class TestReasonCarriesNoPersonLevelField(unittest.TestCase):
    """The reason explains the company, not anybody who works there."""

    PERSON_FIELDS = ("email", "name", "first_name", "last_name", "phone",
                     "linkedin", "title")

    def test_reason_from_positive_signals_has_no_person_data(self):
        verdict = {"positive_signals": [
            {"dimension": "employee_count", "why": "50 people (51_200)"},
            {"dimension": "service_not_product",
             "why": "sells delivery rather than licences"},
        ]}
        reason = icp.evidence_text(verdict)
        for field in self.PERSON_FIELDS:
            self.assertNotIn(field, reason.lower())

    def test_reason_from_real_scoring_has_no_person_data(self):
        rec = _company("Agency", 75, "marketing", "United Kingdom",
                       description="digital marketing agency specialising in "
                                   "content and utilisation tracking")
        verdict = icp.score(rec, config=PRODUCTIVE)
        reason = icp.evidence_text(verdict)
        for field in self.PERSON_FIELDS:
            self.assertNotIn(field, reason.lower())

    def test_clientexport_row_has_no_person_data(self):
        verdict = {"positive_signals": [
            {"dimension": "employee_count",
             "why": "75 people (51_200): the size where resourcing stops "
                    "fitting in a spreadsheet"},
        ]}
        rec = _record_with_verdict(verdict)
        row = clientexport._row_for(rec, {"country": "United Kingdom"})
        for field in self.PERSON_FIELDS:
            self.assertNotIn(field, row["why it matched"].lower())


class TestTelecomAndBankRowsWrongFit(unittest.TestCase):
    """The concrete ISSUE-019/023 rows: a reader would see they are wrong-fit."""

    def test_telecom_reason_is_not_a_pass(self):
        rec = _company("BigTelco", 121205, "telecommunications", "Spain")
        verdict = icp.score(rec, config=PRODUCTIVE)
        reason = icp.evidence_text(verdict).lower()
        self.assertNotIn("scored above threshold", reason)
        self.assertNotIn("strong fit", reason)

    def test_bank_reason_is_not_a_pass(self):
        rec = _company("HugeBank", 130377, "banking", "United States")
        verdict = icp.score(rec, config=PRODUCTIVE)
        reason = icp.evidence_text(verdict).lower()
        self.assertNotIn("scored above threshold", reason)
        self.assertNotIn("strong fit", reason)

    def test_telecom_is_not_qualified(self):
        rec = _company("BigTelco", 121205, "telecommunications", "Spain")
        verdict = icp.score(rec, config=PRODUCTIVE)
        self.assertNotEqual(verdict["icp_status"], icp.QUALIFIED)

    def test_bank_is_not_qualified(self):
        rec = _company("HugeBank", 130377, "banking", "United States")
        verdict = icp.score(rec, config=PRODUCTIVE)
        self.assertNotEqual(verdict["icp_status"], icp.QUALIFIED)


class TestCandidateExportColumnUnchanged(unittest.TestCase):
    """candidateexport's 'why it matched' column is unchanged."""

    def test_export_columns_still_has_why_it_matched(self):
        self.assertIn("why it matched", candidateexport.EXPORT_COLUMNS)

    def test_field_map_still_maps_why_matched(self):
        self.assertEqual(
            candidateexport.FIELD_MAP.get("why_matched"),
            "why it matched")

    def test_column_count_unchanged(self):
        self.assertEqual(len(candidateexport.EXPORT_COLUMNS), 8)


class TestClientExportHasReasonColumn(unittest.TestCase):
    """clientexport now carries 'why it matched' as its seventh column."""

    def test_export_columns_has_seven(self):
        self.assertEqual(len(clientexport.EXPORT_COLUMNS), 7)

    def test_last_column_is_why_it_matched(self):
        self.assertEqual(clientexport.EXPORT_COLUMNS[-1], "why it matched")

    def test_row_for_includes_reason(self):
        verdict = {"positive_signals": [
            {"dimension": "employee_count",
             "why": "50 people (51_200)"},
        ]}
        rec = _record_with_verdict(verdict)
        row = clientexport._row_for(rec, {"country": "Germany"})
        self.assertIn("why it matched", row)
        self.assertIn("50 people", row["why it matched"])


class TestEvidenceTextFromRealSignals(unittest.TestCase):
    """evidence_text builds from positive signals when they exist."""

    def test_single_signal(self):
        verdict = {"positive_signals": [
            {"dimension": "employee_count", "why": "75 people (51_200)"},
        ]}
        self.assertEqual(icp.evidence_text(verdict),
                         "75 people (51_200)")

    def test_multiple_signals_joined(self):
        verdict = {"positive_signals": [
            {"dimension": "employee_count", "why": "75 people (51_200)"},
            {"dimension": "service_not_product",
             "why": "sells delivery rather than licences"},
        ]}
        reason = icp.evidence_text(verdict)
        self.assertIn("75 people", reason)
        self.assertIn("sells delivery", reason)
        self.assertIn("; ", reason)

    def test_capped_at_three_signals(self):
        verdict = {"positive_signals": [
            {"dimension": f"d{i}", "why": f"reason {i}"}
            for i in range(5)
        ]}
        reason = icp.evidence_text(verdict)
        parts = reason.split("; ")
        self.assertEqual(len(parts), 3)

    def test_signals_without_why_are_skipped(self):
        verdict = {"positive_signals": [
            {"dimension": "d1", "why": ""},
            {"dimension": "d2", "why": "real reason"},
        ]}
        self.assertEqual(icp.evidence_text(verdict), "real reason")


if __name__ == "__main__":
    unittest.main()
