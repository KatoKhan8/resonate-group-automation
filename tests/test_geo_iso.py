"""ISO country codes as location evidence.

The offices strings end in two-letter ISO codes. geo.resolve matches free text
against city and country NAMES. The gap is that the evidence is a CODE and the
resolver only reads names. These tests prove the bridge.
"""
import unittest

from src import geo


class TestISOCountryAsArgument(unittest.TestCase):
    """A two-letter ISO code passed as country= must resolve."""

    def test_dk_resolves_denmark(self):
        result = geo.resolve(country="DK")
        self.assertEqual(result["country"], "denmark")
        self.assertEqual(result["country_code"], "DK")
        self.assertEqual(result["region"], geo.NORDICS)

    def test_dk_resolves_a_timezone(self):
        result = geo.resolve(country="DK")
        self.assertEqual(result["timezone"], "Europe/Copenhagen")

    def test_dk_confidence_is_below_city_path(self):
        city_path = geo.resolve(city="Copenhagen")
        iso_path = geo.resolve(country="DK")
        self.assertEqual(city_path["timezone_confidence"], geo.HIGH)
        self.assertLess(
            _confidence_rank(iso_path["timezone_confidence"]),
            _confidence_rank(city_path["timezone_confidence"]),
        )

    def test_gb_resolves(self):
        result = geo.resolve(country="GB")
        self.assertEqual(result["country_code"], "GB")
        self.assertEqual(result["timezone"], "Europe/London")

    def test_pl_resolves(self):
        result = geo.resolve(country="PL")
        self.assertEqual(result["country"], "poland")
        self.assertEqual(result["timezone"], "Europe/Warsaw")

    def test_us_resolves_country_but_no_timezone(self):
        result = geo.resolve(country="US")
        self.assertEqual(result["country"], "united states")
        self.assertEqual(result["country_code"], "US")
        self.assertIsNone(result["timezone"])

    def test_us_is_not_schedulable(self):
        result = geo.resolve(country="US")
        ok, why = geo.schedulable(result)
        self.assertFalse(ok)
        self.assertIn("state", why.lower())

    def test_ca_resolves_country_but_no_timezone(self):
        result = geo.resolve(country="CA")
        self.assertEqual(result["country"], "canada")
        self.assertIsNone(result["timezone"])

    def test_au_resolves_country_but_no_timezone(self):
        result = geo.resolve(country="AU")
        self.assertEqual(result["country"], "australia")
        self.assertIsNone(result["timezone"])

    def test_unknown_iso_returns_blank(self):
        result = geo.resolve(country="ZZ")
        self.assertIsNone(result["country"])
        self.assertIsNone(result["timezone"])

    def test_lowercase_iso_also_resolves(self):
        result = geo.resolve(country="dk")
        self.assertEqual(result["country_code"], "DK")
        self.assertEqual(result["timezone"], "Europe/Copenhagen")


class TestOfficeStringParsing(unittest.TestCase):
    """from_record must extract a trailing ISO code from office strings."""

    def _rec(self, offices, **kw):
        facts = {"offices": offices, "industry": "Software",
                 "employees": 50, "description": "Test company"}
        facts.update(kw)
        return {"id": "test-iso", "domain": "test-iso.test",
                "company": "Test ISO", "client": "demo",
                "state": "enriched", "company_facts": facts,
                "research": []}

    def test_trailing_gb_resolves(self):
        rec = self._rec(["London, London, W4 5PY, GB"])
        result = geo.from_record(rec)
        self.assertEqual(result["country_code"], "GB")
        self.assertIsNotNone(result["timezone"])

    def test_trailing_dk_resolves(self):
        rec = self._rec(
            ["Islands Brygge 79A, Kobenhavn S, Hovedstaden, 2300, DK"])
        result = geo.from_record(rec)
        self.assertEqual(result["country_code"], "DK")
        self.assertEqual(result["timezone"], "Europe/Copenhagen")

    def test_trailing_us_does_not_produce_timezone(self):
        rec = self._rec(["1001 Brickell Bay Drive, Suite 2700 I-5, US"])
        result = geo.from_record(rec)
        self.assertEqual(result["country_code"], "US")
        self.assertIsNone(result["timezone"])
        ok, _ = geo.schedulable(result)
        self.assertFalse(ok)

    def test_trailing_ie_resolves(self):
        rec = self._rec(
            ["107C Bann Road, Dublin Industrial Estate, IE"])
        result = geo.from_record(rec)
        self.assertEqual(result["country_code"], "IE")

    def test_trailing_pl_resolves(self):
        rec = self._rec(["ulica Wyspianskiego, 39A, PL"])
        result = geo.from_record(rec)
        self.assertEqual(result["country_code"], "PL")
        self.assertEqual(result["timezone"], "Europe/Warsaw")

    def test_explicit_country_takes_precedence_over_office_iso(self):
        rec = self._rec(["Some Address, GB"], country="Germany")
        result = geo.from_record(rec)
        self.assertEqual(result["country_code"], "DE")

    def test_office_with_city_name_resolves_city(self):
        rec = self._rec(["Berlin, DE"])
        result = geo.from_record(rec)
        self.assertEqual(result["timezone"], "Europe/Berlin")
        self.assertEqual(result["timezone_source"], geo.FROM_CITY)


class TestCommaSeparatedCityFallback(unittest.TestCase):
    """Each comma-separated part of an office should be tried as a city."""

    def _rec(self, offices, **kw):
        facts = {"offices": offices, "industry": "Software",
                 "employees": 50, "description": "Test company"}
        facts.update(kw)
        return {"id": "test-city", "domain": "test-city.test",
                "company": "Test City", "client": "demo",
                "state": "enriched", "company_facts": facts,
                "research": []}

    def test_city_in_middle_of_office_string(self):
        rec = self._rec(["10 Main Street, Copenhagen, 12345, DK"])
        result = geo.from_record(rec)
        self.assertEqual(result["city"], "copenhagen")
        self.assertEqual(result["timezone_source"], geo.FROM_CITY)

    def test_newcastle_does_not_match_new_york(self):
        rec = self._rec(["Newcastle, GB"])
        result = geo.from_record(rec)
        self.assertNotEqual(result.get("city"), "new york")

    def test_no_city_still_resolves_country_from_iso(self):
        rec = self._rec(["1001 Brickell Bay Drive, US"])
        result = geo.from_record(rec)
        self.assertEqual(result["country_code"], "US")
        self.assertIsNone(result["city"])


class TestNothingThatResolvesTodayStops(unittest.TestCase):
    """Regression: every resolution that works now must keep working."""

    def test_country_by_name_still_resolves(self):
        result = geo.resolve(country="Germany")
        self.assertEqual(result["country_code"], "DE")
        self.assertEqual(result["timezone"], "Europe/Berlin")

    def test_city_still_resolves(self):
        result = geo.resolve(city="London")
        self.assertEqual(result["timezone"], "Europe/London")
        self.assertEqual(result["timezone_confidence"], geo.HIGH)

    def test_us_by_name_still_holds(self):
        result = geo.resolve(country="United States")
        self.assertIsNone(result["timezone"])
        ok, why = geo.schedulable(result)
        self.assertFalse(ok)

    def test_australia_by_name_still_holds(self):
        result = geo.resolve(country="Australia")
        self.assertIsNone(result["timezone"])

    def test_blank_input_still_blank(self):
        result = geo.resolve()
        self.assertIsNone(result["country"])
        self.assertIsNone(result["timezone"])

    def test_single_zone_country_still_high(self):
        result = geo.resolve(country="United Kingdom")
        self.assertEqual(result["timezone_confidence"], geo.HIGH)
        self.assertEqual(result["timezone_source"], geo.FROM_COUNTRY_SINGLE)


def _confidence_rank(label):
    return {"high": 3, "medium": 2, "low": 1, "unknown": 0}.get(label, -1)


if __name__ == "__main__":
    unittest.main()
