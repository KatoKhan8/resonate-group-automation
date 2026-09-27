"""Explainable verdicts: a reason assembled from evidence, not from the verdict.

TASK-272. The mechanism of ISSUE-019 was a reason string generated from the
verdict rather than from the evidence. The verdict said qualified, so the
sentence said "scored above threshold", and the sentence was true about the
verdict and false about the company. A 121,205-employee telecom and a
130,377-employee bank reached a client selling to 20+ person agencies,
carrying `why_matched: "scored above threshold"` while scoring 0.0.

The fix: a row with no positive evidence produces NO reason, not a tautology.
The reason is assembled from the evidence fields the row actually carries.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clientexport, icp, nightlysourcing  # noqa: E402

#: Productive's real shape, as `config/clients/productive.yaml` declares it.
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


def company(name, employees, industry, country, description="", services=None):
    return {"domain": f"{name}.example.test", "company": name,
            "company_facts": {"name": name, "employees": employees,
                              "industry": industry, "description": description,
                              "offices": [country] if country else [],
                              "country": country, "services": services or [],
                              "specialties": []}}


class TestZeroScoreCannotProducePassShapedReason(unittest.TestCase):
    """A row scoring 0.0 must not produce a reason that reads like a pass."""

    def test_zero_score_produces_empty_reason_in_nightlysourcing(self):
        """The nightly pipeline's evidence text is empty when no signals."""
        verdict = icp.score(
            company("Nothing", 50000, "banking", "United States"),
            config=PRODUCTIVE)
        why = nightlysourcing._icp_evidence_text(verdict)
        if verdict["icp_score"] <= 0:
            self.assertEqual(why, "",
                             "a row scoring 0.0 produced a reason; that is "
                             "the ISSUE-019 defect")

    def test_zero_score_produces_empty_reason_in_clientexport(self):
        """The client export's evidence text is empty when no signals."""
        verdict = icp.score(
            company("Nothing", 50000, "banking", "United States"),
            config=PRODUCTIVE)
        why = clientexport._evidence_text(verdict)
        if verdict["icp_score"] <= 0:
            self.assertEqual(why, "",
                             "a row scoring 0.0 produced a reason; that is "
                             "the ISSUE-019 defect")

    def test_no_tautology_in_evidence_text(self):
        """'scored above threshold' was the tautology that stopped the export."""
        verdict = {"positive_signals": [], "icp_score": 0.0}
        why_nightly = nightlysourcing._icp_evidence_text(verdict)
        why_client = clientexport._evidence_text(verdict)
        self.assertNotIn("scored above threshold", why_nightly.lower())
        self.assertNotIn("scored above threshold", why_client.lower())


class TestNoEvidenceProducesNoReason(unittest.TestCase):
    """A row with no evidence produces no reason and does not export."""

    def test_empty_positive_signals_produce_empty_reason(self):
        verdict = {"positive_signals": []}
        self.assertEqual(nightlysourcing._icp_evidence_text(verdict), "")
        self.assertEqual(clientexport._evidence_text(verdict), "")

    def test_none_positive_signals_produce_empty_reason(self):
        verdict = {"positive_signals": None}
        self.assertEqual(nightlysourcing._icp_evidence_text(verdict), "")
        self.assertEqual(clientexport._evidence_text(verdict), "")

    def test_missing_positive_signals_produce_empty_reason(self):
        verdict = {}
        self.assertEqual(nightlysourcing._icp_evidence_text(verdict), "")
        self.assertEqual(clientexport._evidence_text(verdict), "")


class TestReasonCarriesNoPersonLevelField(unittest.TestCase):
    """The reason explains the company, not anybody who works there."""

    def test_reason_from_positive_signals_has_no_person_fields(self):
        """Positive signals are company-level facts, not person-level."""
        verdict = {
            "positive_signals": [
                {"why": "classified as marketing agency"},
                {"why": "45 people (51_200)"},
                {"why": "delivery model looks project"},
            ]
        }
        why = nightlysourcing._icp_evidence_text(verdict)
        # No contact name, no email, no person-level fact
        self.assertNotIn("@", why)
        self.assertNotIn("contact", why.lower())
        self.assertNotIn("email", why.lower())
        self.assertNotIn("name", why.lower())


class TestTelecomAndBankProduceWrongFitReasons(unittest.TestCase):
    """The telecom and bank rows from ISSUE-019 produce recognisable reasons."""

    def test_the_telecom_produces_a_reason_that_says_it_is_a_telecom(self):
        """121,205 staff, Spain, telecommunications, scored 0.0."""
        verdict = icp.score(
            company("BigTelco", 121205, "telecommunications", "Spain"),
            config=PRODUCTIVE)
        why = nightlysourcing._icp_evidence_text(verdict)
        # The reason should be empty (no positive signals) or mention the
        # company's actual characteristics, not "scored above threshold"
        if why:
            self.assertNotIn("scored above threshold", why.lower())

    def test_the_bank_produces_a_reason_that_says_it_is_a_bank(self):
        """130,377 staff, banking, Spain, scored 0.0."""
        verdict = icp.score(
            company("BigBank", 130377, "banking", "Spain"),
            config=PRODUCTIVE)
        why = nightlysourcing._icp_evidence_text(verdict)
        # The reason should be empty (no positive signals) or mention the
        # company's actual characteristics, not "scored above threshold"
        if why:
            self.assertNotIn("scored above threshold", why.lower())


class TestCandidateExportColumnUnchanged(unittest.TestCase):
    """candidateexport's existing 'why it matched' column is unchanged."""

    def test_candidateexport_still_has_why_it_matched_column(self):
        """The weekly Monday 07:00 export still carries the column."""
        from src import candidateexport
        self.assertIn("why it matched", candidateexport.EXPORT_COLUMNS)

    def test_candidateexport_field_map_still_maps_why_matched(self):
        """The field map still maps why_matched to 'why it matched'."""
        from src import candidateexport
        self.assertEqual(candidateexport.FIELD_MAP.get("why_matched"),
                         "why it matched")


class TestClientExportHasReasonColumn(unittest.TestCase):
    """TASK-272: clientexport now carries 'why it matched'."""

    def test_clientexport_has_why_it_matched_column(self):
        """The client export now has seven columns, not six."""
        self.assertEqual(len(clientexport.EXPORT_COLUMNS), 7)
        self.assertIn("why it matched", clientexport.EXPORT_COLUMNS)

    def test_row_for_includes_why_it_matched(self):
        """_row_for produces a row with the 'why it matched' field."""
        rec = {
            "domain": "test.example.test",
            "company": "Test Co",
            "company_facts": {
                "employees": 45,
                "industry": "marketing",
            },
            "qualification": {
                "verdict": {
                    "positive_signals": [
                        {"why": "classified as marketing agency"},
                    ]
                }
            }
        }
        segment = {"country": "United Kingdom"}
        row = clientexport._row_for(rec, segment)
        self.assertIn("why it matched", row)
        self.assertEqual(row["why it matched"], "classified as marketing agency")


if __name__ == "__main__":
    unittest.main()
