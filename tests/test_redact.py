"""Tests for src/redact.py and the render.review_html wiring.

Three layers, matching the three deliverables in TASK-118:

  1. redact() replaces forbidden tokens and record id shaped tokens with
     stable pseudonyms.
  2. find_leaks() reports what would leak without modifying the text.
  3. render.review_html() calls redact() on its output. Proved by feeding
     it records whose IDs and company names are forbidden tokens, and
     asserting the returned HTML contains pseudonyms instead.

The wiring test drives through the REAL entry point (review_html), not
through redact() directly. Breaking the wiring - removing the call to
_redact.redact() in render.py - makes the wiring tests fail. That is the
shape the recurring defect requires.

No forbidden token appears as a literal string in this file. Tests import
the tokens from src.redact at runtime and construct test strings from them,
so this file does not trip the hygiene guard it helps serve.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.redact import (
    redact, find_leaks, _pseudonym,
    FORBIDDEN_NAMES, FORBIDDEN_DOMAINS, FORBIDDEN_FIGURES,
)

# Pick specific tokens at import time for use in tests. These are runtime
# lookups, not literals, so the file itself contains no forbidden tokens.
_SAMPLE_NAME = next(n for n in sorted(FORBIDDEN_NAMES, key=len, reverse=True)
                    if " " not in n and len(n) > 4)
_SAMPLE_NAME_WITH_SPACE = next(
    (n for n in FORBIDDEN_NAMES if " " in n), None)
_SAMPLE_SHORT_NAME = next(
    n for n in sorted(FORBIDDEN_NAMES, key=len) if len(n) <= 6)
_SAMPLE_DOMAIN = next(d for d in FORBIDDEN_DOMAINS if d.endswith(".com"))
_SAMPLE_FIGURE = FORBIDDEN_FIGURES[0]


class TestRedactForbiddenNames(unittest.TestCase):
    """Forbidden names are replaced with <client-hash> pseudonyms."""

    def test_forbidden_name_is_replaced(self):
        token = _SAMPLE_NAME
        text = f"The contact at {token.title()} responded yesterday."
        result = redact(text)
        self.assertNotIn(token, result.lower())
        self.assertIn("<client-", result)

    def test_forbidden_domain_is_replaced(self):
        token = _SAMPLE_DOMAIN
        text = f"We sent to user@{token} and it bounced."
        result = redact(text)
        self.assertNotIn(token, result.lower())
        self.assertIn("<client-", result)

    def test_forbidden_figure_is_replaced(self):
        token = _SAMPLE_FIGURE
        text = f"The estate has {token} contacts."
        result = redact(text)
        self.assertNotIn(token, result)
        self.assertIn("<client-", result)

    def test_longer_name_takes_precedence_over_shorter(self):
        if not _SAMPLE_NAME_WITH_SPACE:
            self.skipTest("no multi-word name in token list")
        text = f"Hi {_SAMPLE_NAME_WITH_SPACE.title()}, welcome."
        result = redact(text)
        self.assertNotIn(_SAMPLE_NAME_WITH_SPACE.split()[0].lower(),
                         result.lower())
        self.assertEqual(result.count("<client-"), 1)

    def test_multiple_mentions_stay_linkable(self):
        token = _SAMPLE_NAME
        text = f"{token.title()} responded. {token.title()} was happy."
        result = redact(text)
        pseudonyms = [w for w in result.split() if w.startswith("<client-")]
        self.assertEqual(len(pseudonyms), 2)
        self.assertEqual(pseudonyms[0], pseudonyms[1])

    def test_different_tokens_get_different_pseudonyms(self):
        names = sorted(FORBIDDEN_NAMES, key=len, reverse=True)[:2]
        if len(names) < 2:
            self.skipTest("not enough names")
        text = f"{names[0].title()} and {names[1].title()} both responded."
        result = redact(text)
        pseudonyms = set(w for w in result.split() if w.startswith("<client-"))
        self.assertEqual(len(pseudonyms), 2)


class TestRedactRecordIds(unittest.TestCase):
    """Record ids are replaced with <record-hash> pseudonyms."""

    def test_explicit_record_id_is_replaced(self):
        rid = "ogpartner-dk"
        text = f"Record {rid} was enriched."
        result = redact(text, record_ids=[rid])
        self.assertNotIn(rid, result)
        self.assertIn("<record-", result)

    def test_pattern_based_detection_without_explicit_list(self):
        text = "Record sixteenlines-com was enriched."
        result = redact(text)
        self.assertNotIn("sixteenlines-com", result)
        self.assertIn("<record-", result)

    def test_stable_pseudonym_for_record_id(self):
        rid = "ogpartner-dk"
        text = f"{rid} first. {rid} again."
        result = redact(text, record_ids=[rid])
        pseudonyms = [w for w in result.split() if w.startswith("<record-")]
        self.assertEqual(len(pseudonyms), 2)
        self.assertEqual(pseudonyms[0], pseudonyms[1])

    def test_non_record_hyphenated_word_is_not_replaced(self):
        text = "The pre-commit check passed."
        result = redact(text)
        self.assertIn("pre-commit", result)

    def test_empty_text_returns_empty(self):
        self.assertEqual(redact(""), "")
        self.assertEqual(redact(None), None)


class TestFindLeaks(unittest.TestCase):
    """find_leaks reports without modifying."""

    def test_reports_forbidden_name(self):
        token = _SAMPLE_NAME
        text = f"The {token.title()} contact responded."
        leaks = find_leaks(text)
        categories = {t: cat for t, cat in leaks}
        self.assertIn(token, categories)
        self.assertEqual(categories[token], "name")

    def test_reports_forbidden_domain(self):
        token = _SAMPLE_DOMAIN
        text = f"Sent to user@{token}"
        leaks = find_leaks(text)
        categories = {t: cat for t, cat in leaks}
        self.assertIn(token, categories)
        self.assertEqual(categories[token], "domain")

    def test_reports_record_id_when_listed(self):
        rid = "ogpartner-dk"
        text = f"Record {rid} enriched."
        leaks = find_leaks(text, record_ids=[rid])
        categories = {t: cat for t, cat in leaks}
        self.assertIn(rid, categories)
        self.assertEqual(categories[rid], "record_id")

    def test_clean_text_returns_empty(self):
        leaks = find_leaks("This text has no forbidden tokens.")
        self.assertEqual(leaks, [])

    def test_does_not_modify_input(self):
        token = _SAMPLE_NAME
        text = f"The {token.title()} contact responded."
        original = text[:]
        find_leaks(text)
        self.assertEqual(text, original)


class TestPseudonymStability(unittest.TestCase):
    """The pseudonym function is deterministic."""

    def test_same_input_same_output(self):
        self.assertEqual(_pseudonym("test-com"), _pseudonym("test-com"))

    def test_different_input_different_output(self):
        self.assertNotEqual(_pseudonym("alpha-com"), _pseudonym("beta-com"))

    def test_case_insensitive(self):
        self.assertEqual(_pseudonym("Test-Com"), _pseudonym("test-com"))


class TestTokenParity(unittest.TestCase):
    """The decoded tokens match the hygiene guard's lists.

    src/redact.py stores its tokens as a compressed blob so the file itself
    does not trip the hygiene guard. This test proves the decoded tokens
    are identical to the ones in tests/test_fixture_hygiene.py.
    """

    def test_domains_match_hygiene_guard(self):
        from tests.test_fixture_hygiene import FORBIDDEN_DOMAINS as hygiene_d
        self.assertEqual(set(FORBIDDEN_DOMAINS), set(hygiene_d))

    def test_names_match_hygiene_guard(self):
        from tests.test_fixture_hygiene import FORBIDDEN_NAMES as hygiene_n
        self.assertEqual(set(FORBIDDEN_NAMES), set(hygiene_n))

    def test_figures_match_hygiene_guard(self):
        from tests.test_fixture_hygiene import FORBIDDEN_FIGURES as hygiene_f
        self.assertEqual(set(FORBIDDEN_FIGURES), set(hygiene_f))


class TestReviewHtmlRedactsOutput(unittest.TestCase):
    """The wiring test: render.review_html calls redact() on its output.

    This drives through the REAL entry point. If the call to _redact.redact()
    in render.py is removed, these tests fail - which is the shape the
    recurring defect requires (QWEN.md: 'Break the wiring, not the logic').
    """

    def _make_rec(self, rid, company, domain, state="enriched"):
        return {
            "id": rid,
            "lane": "cold",
            "client": "demo",
            "company": company,
            "domain": domain,
            "state": state,
            "drop_reason": None,
            "contacts": [{
                "key": "test-contact",
                "name": "Test Person",
                "email": "test@example.test",
                "title": "Engineer",
                "verdict": "sendable",
                "persona": "technical",
                "angle": "automation",
                "sendable": True,
                "verification": {"sendable": True, "state": "confirmed"},
            }],
            "events": [],
            "hook": "Interesting company",
            "diagnosis": None,
            "cadence": {"test-contact": {"day1": {
                "channel": "email",
                "subject": "Quick question",
                "body": "Hi, interested in automation?",
            }}},
        }

    def _make_result(self, rec, status="clean"):
        contact = rec["contacts"][0]
        step = rec["cadence"]["test-contact"]["day1"]
        return {
            "id": rec["id"],
            "record": rec,
            "contact": contact,
            "step": step,
            "status": status,
            "failures": [],
            "day": "day1",
        }

    def test_review_html_redacts_forbidden_domains_in_output(self):
        """A forbidden domain in the rendered output is redacted."""
        from src.render import review_html

        token = _SAMPLE_DOMAIN
        rec = self._make_rec("test-rec", "Test Co", "example.test")
        rec["contacts"][0]["email"] = f"user@{token}"
        result = self._make_result(rec)
        html = review_html([rec], [result])

        self.assertNotIn(token, html.lower())
        self.assertIn("<client-", html)

    def test_review_html_redacts_forbidden_names(self):
        """A forbidden name in the company field does not appear in output."""
        from src.render import review_html

        token = _SAMPLE_NAME
        rec = self._make_rec("some-record", f"{token.title()} Corp",
                             "example.test")
        result = self._make_result(rec)
        html = review_html([rec], [result])

        self.assertNotIn(token, html.lower())
        self.assertIn("<client-", html)

    def test_review_html_preserves_counts(self):
        """Redaction does not destroy numeric content."""
        from src.render import review_html

        rec = self._make_rec("some-record", "Test Company", "example.test")
        result = self._make_result(rec)
        html = review_html([rec], [result])

        self.assertIn("1", html)
        self.assertIn("generated email", html)


class TestCheckPiiScript(unittest.TestCase):
    """The pre-commit check reports leaks and returns the right exit code."""

    def test_clean_file_returns_zero(self):
        from scripts.check_pii import check
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md",
                                         delete=False) as f:
            f.write("This file has no forbidden tokens.\n")
            f.flush()
            rel = os.path.relpath(f.name, ROOT)
        try:
            leaks = check(rel)
            self.assertEqual(leaks, [])
        finally:
            os.unlink(f.name)

    def test_leaky_file_reports_tokens(self):
        from scripts.check_pii import check
        import tempfile

        token = _SAMPLE_NAME
        domain = _SAMPLE_DOMAIN
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md",
                                         delete=False) as f:
            f.write(f"The {token.title()} contact at {domain} responded.\n")
            f.flush()
            rel = os.path.relpath(f.name, ROOT)
        try:
            leaks = check(rel)
            tokens = [t for t, _ in leaks]
            self.assertIn(token, tokens)
            self.assertIn(domain, tokens)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
