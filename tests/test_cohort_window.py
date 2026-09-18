"""Cohort send-window proposal from recipient locations (TASK-227).

A campaign sends to a cohort, not to a timezone. When the schedule is set to
09:00-17:00 Europe/Zagreb but the recipients are in US Eastern, 09:00 Zagreb
is 03:00 Eastern. This function proposes a coherent window from the recipients
themselves, classifying each as RESOLVED, AMBIGUOUS, or UNKNOWN.

The rule that outranks the feature: missing evidence is never positive evidence
and a guessed timezone is worse than a missing one.
"""
import unittest

from src import geo


def _rec(offices=None, country=None, city=None, state=None, domain=None):
    """Build a minimal record shaped like a queue record."""
    facts = {"industry": "Software", "employees": 50,
             "description": "Test company"}
    if offices:
        facts["offices"] = offices
    if country:
        facts["country"] = country
    if city:
        facts["city"] = city
    if state:
        facts["state"] = state
    return {
        "id": f"test-{domain or 'rec'}",
        "domain": domain or "test.test",
        "company": "Test Co",
        "client": "demo",
        "state": "enriched",
        "company_facts": facts,
        "research": [],
    }


class TestClassifyRecipient(unittest.TestCase):
    """Each recipient is classified RESOLVED, AMBIGUOUS, or UNKNOWN."""

    def test_single_zone_country_is_resolved(self):
        rec = _rec(country="Germany")
        c = geo._classify_recipient(rec)
        self.assertEqual(c["status"], geo.RESOLVED)
        self.assertEqual(c["timezone"], "Europe/Berlin")
        self.assertIn(c["confidence"], (geo.HIGH, geo.MEDIUM))

    def test_city_is_resolved_with_high_confidence(self):
        rec = _rec(city="Zagreb")
        c = geo._classify_recipient(rec)
        self.assertEqual(c["status"], geo.RESOLVED)
        self.assertEqual(c["timezone"], "Europe/Zagreb")
        self.assertEqual(c["confidence"], geo.HIGH)

    def test_multi_timezone_country_is_ambiguous_not_resolved(self):
        """The test that matters most: US known only as a country must NOT
        return a timezone. It is AMBIGUOUS - we know where it is, but we
        cannot pick a zone without a state or city."""
        rec = _rec(country="United States")
        c = geo._classify_recipient(rec)
        self.assertNotEqual(c["status"], geo.RESOLVED)
        self.assertIsNone(c["timezone"])

    def test_multi_timezone_country_is_not_unknown_either(self):
        """US is not UNKNOWN - we know the country. It is AMBIGUOUS because
        the country spans several zones."""
        rec = _rec(country="United States")
        c = geo._classify_recipient(rec)
        self.assertEqual(c["status"], geo.AMBIGUOUS)
        self.assertEqual(c["country"], "united states")

    def test_no_location_evidence_is_unknown(self):
        rec = _rec()
        c = geo._classify_recipient(rec)
        self.assertEqual(c["status"], geo.UNKNOWN)
        self.assertIsNone(c["timezone"])
        self.assertIsNone(c["country"])

    def test_iso_code_for_multi_zone_country_is_ambiguous(self):
        rec = _rec(country="US")
        c = geo._classify_recipient(rec)
        self.assertEqual(c["status"], geo.AMBIGUOUS)
        self.assertIsNone(c["timezone"])

    def test_australia_without_state_is_ambiguous(self):
        rec = _rec(country="Australia")
        c = geo._classify_recipient(rec)
        self.assertEqual(c["status"], geo.AMBIGUOUS)
        self.assertIsNone(c["timezone"])

    def test_canada_without_state_is_ambiguous(self):
        rec = _rec(country="Canada")
        c = geo._classify_recipient(rec)
        self.assertEqual(c["status"], geo.AMBIGUOUS)
        self.assertIsNone(c["timezone"])

    def test_us_with_state_resolves(self):
        rec = _rec(country="United States", state="california")
        c = geo._classify_recipient(rec)
        self.assertEqual(c["status"], geo.RESOLVED)
        self.assertEqual(c["timezone"], "America/Los_Angeles")


class TestProposeCohortWindowSingleRegion(unittest.TestCase):
    """A single-region cohort proposes that region's window."""

    def test_three_croatian_companies_propose_zagreb(self):
        recipients = [
            _rec(city="Zagreb", domain="a.hr"),
            _rec(city="Split", country="Croatia", domain="b.hr"),
            _rec(offices=["Zagreb, HR"], domain="c.hr"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["timezone"], "Europe/Zagreb")
        self.assertEqual(result["region"], geo.CEE)
        self.assertIsNotNone(result["window"])
        self.assertEqual(result["window"]["start"], "09:00")
        self.assertIsNone(result["reason"])

    def test_three_german_companies_propose_berlin(self):
        recipients = [
            _rec(city="Berlin", domain="a.de"),
            _rec(city="Munich", domain="b.de"),
            _rec(country="Germany", domain="c.de"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["timezone"], "Europe/Berlin")
        self.assertEqual(result["region"], geo.DACH)

    def test_summary_counts_are_correct(self):
        recipients = [
            _rec(city="Zagreb", domain="a.hr"),
            _rec(city="Zagreb", domain="b.hr"),
            _rec(city="Zagreb", domain="c.hr"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertEqual(result["summary"]["resolved"], 3)
        self.assertEqual(result["summary"]["ambiguous"], 0)
        self.assertEqual(result["summary"]["unknown"], 0)
        self.assertEqual(result["summary"]["total"], 3)


class TestProposeCohortWindowMultiTimezone(unittest.TestCase):
    """A three-continent cohort returns NO PROPOSAL."""

    def test_three_continents_no_proposal(self):
        recipients = [
            _rec(city="Zagreb", domain="a.hr"),
            _rec(city="New York", domain="b.com"),
            _rec(city="Sydney", domain="c.au"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["timezone"])
        self.assertIsNone(result["window"])
        self.assertIn("multiple timezones", result["reason"])

    def test_two_european_zones_no_proposal(self):
        """Even within Europe, London and Berlin are different zones."""
        recipients = [
            _rec(city="London", domain="a.uk"),
            _rec(city="London", domain="b.uk"),
            _rec(city="Berlin", domain="c.de"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertIn("multiple timezones", result["reason"])


class TestProposeCohortWindowTooFewResolved(unittest.TestCase):
    """When too few resolve, return NO PROPOSAL with the reason."""

    def test_all_unknown_no_proposal(self):
        recipients = [_rec(), _rec(), _rec()]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertIn("no recipients resolved", result["reason"])

    def test_all_ambiguous_no_proposal(self):
        """Three US-only companies: all AMBIGUOUS, none RESOLVED."""
        recipients = [
            _rec(country="United States", domain="a.com"),
            _rec(country="United States", domain="b.com"),
            _rec(country="United States", domain="c.com"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertEqual(result["summary"]["resolved"], 0)
        self.assertEqual(result["summary"]["ambiguous"], 3)

    def test_too_few_resolved_no_proposal(self):
        recipients = [
            _rec(city="Zagreb", domain="a.hr"),
            _rec(country="United States", domain="b.com"),
            _rec(domain="c.com"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertIn("only 1", result["reason"])

    def test_empty_recipients_no_proposal(self):
        result = geo.propose_cohort_window([], min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no recipients provided")

    def test_mixed_with_enough_resolved_proposes(self):
        """Two resolved + one unknown with min_resolved=2 should propose."""
        recipients = [
            _rec(city="Zagreb", domain="a.hr"),
            _rec(city="Zagreb", domain="b.hr"),
            _rec(domain="c.com"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=2)
        self.assertTrue(result["ok"])
        self.assertEqual(result["timezone"], "Europe/Zagreb")


class TestProposeCohortWindowMultiZoneCountry(unittest.TestCase):
    """The critical test: a country spanning several timezones, known only
    as a country, must return UNKNOWN/AMBIGUOUS and must NOT return a
    timezone."""

    def test_us_only_country_does_not_become_a_timezone(self):
        """If the cohort is three US companies with no state/city, no
        timezone may be proposed - even though the country is known."""
        recipients = [
            _rec(country="United States", domain="a.com"),
            _rec(country="United States", domain="b.com"),
            _rec(country="United States", domain="c.com"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["timezone"])
        for c in result["classifications"]:
            if c["country"] == "united states":
                self.assertIsNone(c["timezone"])
                self.assertNotEqual(c["status"], geo.RESOLVED)

    def test_canada_only_country_does_not_become_a_timezone(self):
        recipients = [
            _rec(country="Canada", domain="a.ca"),
            _rec(country="Canada", domain="b.ca"),
            _rec(country="Canada", domain="c.ca"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["timezone"])

    def test_australia_only_country_does_not_become_a_timezone(self):
        recipients = [
            _rec(country="Australia", domain="a.au"),
            _rec(country="Australia", domain="b.au"),
            _rec(country="Australia", domain="c.au"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["timezone"])


class TestProposeCohortWindowIsReadOnly(unittest.TestCase):
    """The function must not mutate its inputs or call any provider."""

    def test_does_not_mutate_recipients(self):
        import copy
        recipients = [
            _rec(city="Zagreb", domain="a.hr"),
            _rec(city="Zagreb", domain="b.hr"),
            _rec(city="Zagreb", domain="c.hr"),
        ]
        original = copy.deepcopy(recipients)
        geo.propose_cohort_window(recipients, min_resolved=3)
        self.assertEqual(recipients, original)

    def test_classifications_carry_evidence(self):
        """Every classification must carry a 'why' - no default dressed
        as an answer."""
        recipients = [
            _rec(city="Zagreb", domain="a.hr"),
            _rec(country="United States", domain="b.com"),
            _rec(domain="c.com"),
        ]
        result = geo.propose_cohort_window(recipients, min_resolved=1)
        for c in result["classifications"]:
            self.assertTrue(c["why"], f"classification missing 'why': {c}")


if __name__ == "__main__":
    unittest.main()
