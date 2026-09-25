"""Quote verification: every fact's quote must appear verbatim in the input.

THE PROMPT SAYS IT IS CHECKED, SO THIS CHECKS IT. A fact whose span is
absent is a hallucination and the lead loses that fact. This is the
enforcement half - the prompt tells the model the rule, and this module
verifies it mechanically.

## BOTH WAYS

A fact whose quote IS in the input passes. A fact whose quote is NOT in
the input is removed. A fact with no quote field is removed. Whitespace
differences are normalised before comparison.
"""
import unittest

from src import copyextract


INPUT_TEXT = """
We are a creative advertising agency creating custom-made solutions.
We announced a new partnership with Acme Corp last month.
Our team has grown to 45 people across two offices in London and Berlin.
We specialise in brand identity and digital campaigns.
"""


class TestQuoteVerification(unittest.TestCase):
    """Quotes are checked character-for-character (after whitespace normalisation)."""

    def test_exact_quote_passes(self):
        facts = [{
            "text": "They partnered with Acme Corp.",
            "quote": "We announced a new partnership with Acme Corp last month",
            "source_url": "https://example.com",
        }]
        verified, removed = copyextract.verify_quotes(facts, INPUT_TEXT)
        self.assertEqual(len(verified), 1)
        self.assertEqual(len(removed), 0)

    def test_whitespace_normalised(self):
        facts = [{
            "text": "They partnered with Acme Corp.",
            "quote": "We  announced  a  new  partnership",  # extra spaces
            "source_url": "https://example.com",
        }]
        verified, removed = copyextract.verify_quotes(facts, INPUT_TEXT)
        self.assertEqual(len(verified), 1)

    def test_invented_quote_removed(self):
        facts = [{
            "text": "They won an award.",
            "quote": "We won the Agency of the Year award",  # NOT in input
            "source_url": "https://example.com",
        }]
        verified, removed = copyextract.verify_quotes(facts, INPUT_TEXT)
        self.assertEqual(len(verified), 0)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["_remove_reason"], "quote not in input")

    def test_empty_quote_removed(self):
        facts = [{
            "text": "They are creative.",
            "quote": "",
            "source_url": "https://example.com",
        }]
        verified, removed = copyextract.verify_quotes(facts, INPUT_TEXT)
        self.assertEqual(len(verified), 0)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["_remove_reason"], "no quote")

    def test_missing_quote_field_removed(self):
        facts = [{
            "text": "They are creative.",
            "source_url": "https://example.com",
        }]
        verified, removed = copyextract.verify_quotes(facts, INPUT_TEXT)
        self.assertEqual(len(verified), 0)
        self.assertEqual(len(removed), 1)

    def test_mixed_pass_and_fail(self):
        facts = [
            {"text": "Fact 1", "quote": "creative advertising agency",
             "source_url": "https://example.com"},
            {"text": "Fact 2", "quote": "we won best agency",  # invented
             "source_url": "https://example.com"},
            {"text": "Fact 3", "quote": "grown to 45 people",
             "source_url": "https://example.com"},
        ]
        verified, removed = copyextract.verify_quotes(facts, INPUT_TEXT)
        self.assertEqual(len(verified), 2)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["text"], "Fact 2")


class TestParseJson(unittest.TestCase):
    """JSON parsing handles both strict and markdown-wrapped output."""

    def test_strict_json(self):
        raw = '{"facts": [], "angle": null, "usable": false}'
        result = copyextract._parse_json(raw)
        self.assertEqual(result["usable"], False)

    def test_markdown_wrapped(self):
        raw = '```json\n{"facts": [], "angle": null, "usable": false}\n```'
        result = copyextract._parse_json(raw)
        self.assertEqual(result["usable"], False)

    def test_prose_around_json(self):
        raw = 'Here is the result:\n{"facts": [], "angle": null}\nDone.'
        result = copyextract._parse_json(raw)
        self.assertIn("facts", result)


if __name__ == "__main__":
    unittest.main()
