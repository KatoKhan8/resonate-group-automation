"""The nav chrome cleaner: proved to strip AND proved not to strip content.

The incident's "quote" was the head of a nav strip. Every pack snippet in
the store opens with site nav. This module removes it before the model
sees it, so the model cannot quote what it was never shown.

## BOTH WAYS

A cleaner that strips everything satisfies "remove nav" perfectly and
makes the pipeline useless. So every test has a positive case (nav IS
stripped) and a negative case (content is NOT stripped).
"""
import unittest

from src import packcleaner


class TestSkipPrefix(unittest.TestCase):
    """Known skip-link prefixes are removed."""

    def test_skip_to_content(self):
        raw = "Skip to content About Services Contact We build things."
        self.assertTrue(packcleaner.clean(raw).startswith("We build"))

    def test_skip_to_the_content(self):
        raw = "Skip to the content About Clients Archive Menu We are a team."
        result = packcleaner.clean(raw)
        self.assertNotIn("Skip to", result)

    def test_skip_to_main_content(self):
        raw = "Skip to main content Home Blog About Our approach is different."
        result = packcleaner.clean(raw)
        self.assertIn("Our approach", result)


class TestNavWordStripping(unittest.TestCase):
    """Nav words at the start are stripped; nav words in content are kept."""

    def test_menu_strip(self):
        raw = "Menu About Services Contact We help agencies see margin."
        result = packcleaner.clean(raw)
        self.assertIn("We help agencies", result)

    def test_login_about_pattern(self):
        raw = "Login About Paradigm Leadership Services Recent Work Contact We show project margin."
        result = packcleaner.clean(raw)
        self.assertIn("We show project margin", result)

    def test_about_in_content_is_kept(self):
        raw = "We are a creative agency. About our approach: we focus on margin."
        result = packcleaner.clean(raw)
        self.assertIn("About our approach", result)

    def test_social_labels_stripped(self):
        raw = "Facebook-f Twitter Linkedin Instagram Success Stories Services We drive retail growth."
        result = packcleaner.clean(raw)
        self.assertIn("We drive retail growth", result)


class TestPhoneAndEmail(unittest.TestCase):
    """Phone numbers and emails at the start are stripped."""

    def test_phone_prefix(self):
        raw = "Call +353 1 864 3704 home our work experience We are a team of designers."
        result = packcleaner.clean(raw)
        self.assertIn("We are a team", result)

    def test_email_prefix(self):
        raw = "info@example.com Facebook Twitter About Services We build brands."
        result = packcleaner.clean(raw)
        self.assertIn("We build brands", result)


class TestCookieBanner(unittest.TestCase):
    """Cookie banner text is stripped."""

    def test_cookie_phrase(self):
        raw = "We use cookies to improve your experience. We are a leading agency."
        result = packcleaner.clean(raw)
        self.assertIn("We are a leading agency", result)
        self.assertNotIn("cookies", result.lower().split(".")[0])


class TestNegativeCases(unittest.TestCase):
    """Content that is NOT nav chrome is preserved."""

    def test_clean_content_unchanged(self):
        raw = "We are a creative advertising agency creating custom-made solutions."
        result = packcleaner.clean(raw)
        self.assertEqual(result, raw)

    def test_empty_input(self):
        self.assertEqual(packcleaner.clean(""), "")
        self.assertEqual(packcleaner.clean(None), "")

    def test_short_content_preserved(self):
        raw = "We help agencies."
        result = packcleaner.clean(raw)
        self.assertIn("We help", result)


class TestCleanSources(unittest.TestCase):
    """The batch cleaner reports before/after metrics."""

    def test_metrics(self):
        sources = [
            {"label": "site", "url": "https://example.com",
             "text": "Skip to content About Services We build things."},
            {"label": "posts", "url": "https://li.test/1",
             "text": "We announced a new partnership today."},
        ]
        cleaned, before, after = packcleaner.clean_sources(sources)
        self.assertEqual(len(cleaned), 2)
        self.assertGreater(before, after)
        self.assertIn("We build things", cleaned[0]["text"])
        self.assertEqual(cleaned[1]["text"],
                         "We announced a new partnership today.")

    def test_empty_sources(self):
        cleaned, before, after = packcleaner.clean_sources([])
        self.assertEqual(cleaned, [])
        self.assertEqual(before, 0)
        self.assertEqual(after, 0)


if __name__ == "__main__":
    unittest.main()
