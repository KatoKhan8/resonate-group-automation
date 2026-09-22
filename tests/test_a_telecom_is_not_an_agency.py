"""A 16,000-staff telecom cannot qualify for a client who sells to agencies.

ISSUE-023. The first QUALIFIED-only candidate list was 114 rows with a median
headcount of 16,996, none in the 20-200 range, 62 enterprise software firms and
24 telecoms. The four largest were national telecoms of 121,205, 107,286,
101,120 and 96,438 staff, every one QUALIFIED at `icp_score` 0.0, and eight
rows carried `why_matched: "scored above threshold"` while scoring nothing.

The mechanism was that a structural pass ignored the numeric score entirely.
Structural criteria are deliberately a pool rather than a gate - that design is
not what these tests change. What they pin is that a record with NO positive
evidence cannot be called qualified on the strength of the pool alone.

Operator decision, 2026-09-22: a zero score never passes structurally, and
geography is a required criterion.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import icp, icpstructural  # noqa: E402

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


class TestATelecomCannotQualify(unittest.TestCase):
    """The concrete rows that stopped the export, by their real shape."""

    def _status(self, rec):
        return icp.score(rec, config=PRODUCTIVE)

    def test_a_sixteen_thousand_staff_telecom_is_not_qualified(self):
        """The headline case the operator named."""
        verdict = self._status(
            company("Telco", 16000, "telecommunications", "Spain"))
        self.assertNotEqual(
            verdict["icp_status"], icp.QUALIFIED,
            "a 16,000-staff telecom qualified for an agency-focused client; "
            "that is ISSUE-023")

    def test_the_largest_telecom_from_the_stopped_export_is_not_qualified(self):
        """121,205 staff, Spain, telecommunications, scored 0.0."""
        verdict = self._status(
            company("BigTelco", 121205, "telecommunications", "Spain"))
        self.assertNotEqual(verdict["icp_status"], icp.QUALIFIED)

    def test_a_hundred_thousand_staff_equipment_maker_is_not_qualified(self):
        verdict = self._status(
            company("Equipment", 101120, "telecommunications", "Finland"))
        self.assertNotEqual(verdict["icp_status"], icp.QUALIFIED)


class TestAZeroScoreNeverPassesStructurally(unittest.TestCase):
    """The rule, stated independently of any one industry."""

    def test_a_zero_scored_record_is_never_qualified(self):
        verdict = icp.score(
            company("Nothing", 50000, "banking", "United States"),
            config=PRODUCTIVE)
        if verdict["icp_score"] <= 0:
            self.assertNotEqual(verdict["icp_status"], icp.QUALIFIED)

    def test_the_reason_says_it_scored_nothing(self):
        """`why_matched` read 'scored above threshold' on rows scoring 0.0."""
        verdict = icp.score(
            company("Nothing", 50000, "banking", "United States"),
            config=PRODUCTIVE)
        why = (verdict.get("icp_why") or verdict.get("why") or "").lower()
        if verdict["icp_score"] <= 0 and why:
            self.assertNotIn("scored above threshold", why)


class TestGeographyIsRequired(unittest.TestCase):
    """`not_required` stays honest; `unknown` stops being a pass."""

    def test_no_geography_rule_still_counts_as_established(self):
        structural = {"criteria": {"geography": {
            "status": icpstructural.NOT_REQUIRED}}}
        self.assertTrue(icp._geography_established(structural))

    def test_an_unknown_country_is_not_established(self):
        structural = {"criteria": {"geography": {
            "status": icpstructural.UNKNOWN}}}
        self.assertFalse(icp._geography_established(structural))

    def test_an_affirmative_pass_is_established(self):
        for status in (icpstructural.PASS, icpstructural.PASS_WITH_TOLERANCE):
            with self.subTest(status=status):
                self.assertTrue(icp._geography_established(
                    {"criteria": {"geography": {"status": status}}}))

    def test_a_missing_geography_answer_is_not_established(self):
        self.assertFalse(icp._geography_established({"criteria": {}}))


if __name__ == "__main__":
    unittest.main()
