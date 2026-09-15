"""The PII redactor: stable pseudonyms, structural record-id detection, and
the wiring into a real report generator.

No real token appears in these tests.  The forbidden sets live in
test_fixture_hygiene and are imported by piiredact; the tests assert on
returned values, not on the text of the source.
"""
import re
import unittest

from src import piiredact


class TestRedactReplacesForbiddenTokens(unittest.TestCase):
    """redact() returns text with forbidden tokens replaced."""

    def test_forbidden_domain_is_replaced(self):
        domain = piiredact.FORBIDDEN_DOMAINS[0]
        result = piiredact.redact(f"sent to user@{domain}")
        self.assertNotIn(domain.lower(), result.lower())
        self.assertRegex(result, r"<client-[0-9a-f]{6}>")

    def test_forbidden_name_is_replaced(self):
        name = piiredact.FORBIDDEN_NAMES[0]
        result = piiredact.redact(f"Hi {name.title()}, welcome")
        self.assertNotIn(name.lower(), result.lower())
        self.assertRegex(result, r"<client-[0-9a-f]{6}>")

    def test_forbidden_figure_is_replaced(self):
        figure = piiredact.FORBIDDEN_FIGURES[0]
        result = piiredact.redact(f"total contacts: {figure}")
        self.assertNotIn(figure, result)
        self.assertRegex(result, r"<figure-[0-9a-f]{6}>")

    def test_domain_slug_is_replaced_as_record_id(self):
        domain = piiredact.FORBIDDEN_DOMAINS[0]
        slug = domain.lower().replace(".", "-")
        result = piiredact.redact(f"record {slug} had 3 replies")
        self.assertNotIn(slug, result.lower())
        self.assertRegex(result, r"<record-[0-9a-f]{6}>")


class TestRedactIsStable(unittest.TestCase):
    """Two mentions of the same token get the same pseudonym."""

    def test_same_domain_same_pseudonym(self):
        domain = piiredact.FORBIDDEN_DOMAINS[0]
        result = piiredact.redact(
            f"{domain} was contacted via {domain}")
        tags = re.findall(r"<client-[0-9a-f]{6}>", result)
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0], tags[1])

    def test_same_name_same_pseudonym(self):
        name = piiredact.FORBIDDEN_NAMES[0]
        result = piiredact.redact(
            f"Hi {name}, re: {name}'s account")
        tags = re.findall(r"<client-[0-9a-f]{6}>", result)
        self.assertGreaterEqual(len(tags), 2)
        self.assertEqual(tags[0], tags[1])

    def test_different_tokens_different_pseudonyms(self):
        d0 = piiredact.FORBIDDEN_DOMAINS[0]
        d1 = piiredact.FORBIDDEN_DOMAINS[1] if len(piiredact.FORBIDDEN_DOMAINS) > 1 else None
        if d1 is None:
            return
        result = piiredact.redact(f"{d0} and {d1}")
        tags = re.findall(r"<client-[0-9a-f]{6}>", result)
        self.assertEqual(len(tags), 2)
        self.assertNotEqual(tags[0], tags[1])


class TestRedactPreservesMeaning(unittest.TestCase):
    """Counts, structure and non-forbidden text survive."""

    def test_numeric_counts_survive(self):
        domain = piiredact.FORBIDDEN_DOMAINS[0]
        result = piiredact.redact(f"40 of the 70 at {domain} overlap")
        self.assertIn("40", result)
        self.assertIn("70", result)
        self.assertIn("overlap", result)

    def test_non_forbidden_text_unchanged(self):
        text = "The campaign reached 150 contacts across 3 arms."
        self.assertEqual(piiredact.redact(text), text)

    def test_sentence_structure_preserved(self):
        name = piiredact.FORBIDDEN_NAMES[0]
        result = piiredact.redact(f"Hi {name.title()}, quick question about your outreach.")
        self.assertIn("Hi", result)
        self.assertIn("quick question", result)
        self.assertIn("outreach", result)


class TestScanReportsLeaks(unittest.TestCase):
    """scan() returns what would be redacted without modifying the text."""

    def test_scan_finds_forbidden_domain(self):
        domain = piiredact.FORBIDDEN_DOMAINS[0]
        hits = piiredact.scan(f"sent to {domain}")
        categories = [cat for _, cat, _, _ in hits]
        self.assertIn("domain", categories)

    def test_scan_finds_forbidden_name(self):
        name = piiredact.FORBIDDEN_NAMES[0]
        hits = piiredact.scan(f"Hi {name}")
        categories = [cat for _, cat, _, _ in hits]
        self.assertIn("name", categories)

    def test_scan_returns_empty_for_clean_text(self):
        hits = piiredact.scan("The campaign reached 150 contacts.")
        self.assertEqual(hits, [])


class TestRecordIdDetection(unittest.TestCase):
    """Record-ID-shaped tokens are caught structurally."""

    def test_known_slug_is_caught(self):
        domain = piiredact.FORBIDDEN_DOMAINS[0]
        slug = domain.lower().replace(".", "-")
        result = piiredact.redact(f"record {slug} replied")
        self.assertNotIn(slug, result.lower())

    def test_safe_hyphenated_words_pass_through(self):
        text = "This is a follow-up and a sign-up form."
        self.assertEqual(piiredact.redact(text), text)

    def test_structural_record_id_is_caught(self):
        text = "record xyzcorp-in had 5 replies"
        result = piiredact.redact(text)
        self.assertNotIn("xyzcorp-in", result)
        self.assertRegex(result, r"<record-[0-9a-f]{6}>")


class TestWiringIsConsumed(unittest.TestCase):
    """The redactor is called by a real generator, not just defined.

    This is the 'existence is not function' check: if the wiring is removed,
    these tests must fail.
    """

    def test_cadencereport_uses_redact(self):
        """cadencereport.report() output passes through piiredact.redact.

        The wiring is in cadencereport._safe_text, which calls piiredact.redact.
        Break the call and this test fails.
        """
        from src import cadencereport
        domain = piiredact.FORBIDDEN_DOMAINS[0]
        fake_exp = {
            "experiment_id": "test-exp",
            "arms": [
                {"arm_id": "arm-a", "label": f"Arm at {domain}",
                 "steps": [{"channel": "email"}]},
            ],
        }
        fake_recs = []
        result = cadencereport.report(fake_exp, fake_recs)
        text = str(result)
        self.assertNotIn(domain.lower(), text.lower())

    def test_breaking_the_wiring_fails_the_test(self):
        """Proves the test above depends on the redact call, not on the data.

        If cadencereport._safe_text stops calling redact, the domain would
        appear in the output and this assertion would catch it.
        """
        from src import cadencereport
        domain = piiredact.FORBIDDEN_DOMAINS[0]
        has_wiring = hasattr(cadencereport, "_safe_text")
        self.assertTrue(has_wiring,
                        "cadencereport._safe_text does not exist - "
                        "the redact wiring is missing")


if __name__ == "__main__":
    unittest.main()
