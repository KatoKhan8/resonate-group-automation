#!/usr/bin/env python3
"""Tests for inferred geography evidence (TASK-190).

The TLD inference in geo.from_domain_tld is the only free source wired as
code. The others (research text vertical signals, domain name keywords) are
reported as findings but not wired: their reliability is MEDIUM or below, and
the task says "if a source is only 80% reliable, do NOT wire it".

Two invariants the task enforces:
1. Inference may only move UNKNOWN to PASS, never UNKNOWN to FAIL.
2. Every inferred fact carries provenance the claims gate can read.
"""
import unittest

from src.geo import (
    from_domain_tld, FROM_TLD, TLD_TO_ISO, HIGH, MEDIUM, ISO_TO_COUNTRY,
)


class TestTLDMapping(unittest.TestCase):
    """The TLD table maps ccTLDs to ISO codes correctly."""

    def test_unambiguous_ccTLDs(self):
        cases = {
            "dk": "DK", "se": "SE", "no": "NO", "fi": "FI",
            "de": "DE", "at": "AT", "ch": "CH",
            "nl": "NL", "be": "BE",
            "pl": "PL", "cz": "CZ", "si": "SI", "lt": "LT",
            "ee": "EE", "hr": "HR", "ro": "RO", "hu": "HU",
            "uk": "GB", "ie": "IE",
            "es": "ES", "it": "IT", "pt": "PT", "cy": "CY",
            "au": "AU", "nz": "NZ", "ca": "CA", "us": "US",
            "jp": "JP", "kr": "KR", "in": "IN",
        }
        for tld, expected_iso in cases.items():
            self.assertEqual(TLD_TO_ISO.get(tld), expected_iso,
                             f".{tld} should map to {expected_iso}")

    def test_ambiguous_TLDs_excluded(self):
        for tld in ("com", "net", "org", "io", "ai", "co", "edu",
                    "app", "cloud", "media", "agency", "marketing",
                    "digital", "work", "africa"):
            self.assertNotIn(tld, TLD_TO_ISO,
                             f".{tld} should NOT be in the TLD table")


class TestFromDomainTLD(unittest.TestCase):
    """from_domain_tld returns country with provenance, or None."""

    def test_included_country(self):
        result = from_domain_tld("example.se")
        self.assertIsNotNone(result)
        self.assertEqual(result["country"], "sweden")
        self.assertEqual(result["country_code"], "SE")
        self.assertTrue(result["inferred"])
        self.assertEqual(result["inference_method"], FROM_TLD)
        self.assertEqual(result["inference_input"], "example.se")

    def test_generic_tld_returns_none(self):
        self.assertIsNone(from_domain_tld("example.com"))
        self.assertIsNone(from_domain_tld("example.net"))
        self.assertIsNone(from_domain_tld("example.io"))
        self.assertIsNone(from_domain_tld("example.ai"))

    def test_no_dot_returns_none(self):
        self.assertIsNone(from_domain_tld("localhost"))
        self.assertIsNone(from_domain_tld(""))
        self.assertIsNone(from_domain_tld(None))

    def test_second_level_domain(self):
        result = from_domain_tld("example.co.uk")
        self.assertIsNotNone(result)
        self.assertEqual(result["country"], "united kingdom")

    def test_com_au(self):
        result = from_domain_tld("example.com.au")
        self.assertIsNotNone(result)
        self.assertEqual(result["country"], "australia")

    def test_provenance_fields_present(self):
        result = from_domain_tld("example.de")
        self.assertIn("inferred", result)
        self.assertIn("inference_method", result)
        self.assertIn("inference_input", result)
        self.assertTrue(result["inferred"])
        self.assertEqual(result["inference_method"], FROM_TLD)
        self.assertEqual(result["inference_input"], "example.de")

    def test_region_populated(self):
        result = from_domain_tld("example.pl")
        self.assertIsNotNone(result)
        self.assertEqual(result["region"], "CEE")
        self.assertEqual(result["region_confidence"], HIGH)

    def test_never_returns_fail(self):
        """Inference may only move UNKNOWN to PASS, never to FAIL.

        The function returns a country or None. It never says "excluded" or
        "not in any market". The caller checks against the include list.
        """
        for tld in TLD_TO_ISO:
            domain = f"test.{tld}"
            result = from_domain_tld(domain)
            if result is not None:
                self.assertIn("country", result)
                self.assertIsNotNone(result["country"])
                self.assertFalse(result.get("excluded", False),
                                 f"TLD .{tld} must not produce an exclusion")

    def test_country_name_in_iso_to_country(self):
        """Every TLD maps to a country name the rest of the system knows."""
        for tld, iso in TLD_TO_ISO.items():
            result = from_domain_tld(f"test.{tld}")
            if result is not None:
                self.assertIn(result["country"], ISO_TO_COUNTRY.values(),
                              f".{tld} -> {result['country']} is not in "
                              f"ISO_TO_COUNTRY")


class TestInferenceSafety(unittest.TestCase):
    """The inference cannot produce a FAIL on any criterion."""

    def test_inferred_flag_always_true_when_present(self):
        for tld in TLD_TO_ISO:
            result = from_domain_tld(f"test.{tld}")
            if result is not None:
                self.assertTrue(result.get("inferred"),
                                f".{tld} result must be marked inferred")

    def test_inference_input_is_the_domain(self):
        result = from_domain_tld("mycompany.dk")
        self.assertEqual(result["inference_input"], "mycompany.dk")

    def test_timezone_source_is_tld(self):
        result = from_domain_tld("example.fi")
        self.assertEqual(result["timezone_source"], FROM_TLD)
        self.assertEqual(result["timezone_confidence"], MEDIUM)


if __name__ == "__main__":
    unittest.main()
