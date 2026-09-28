"""TASK-547: app payload extraction recovers text from Inertia and Next.js shells.

An Inertia app carries its page data in a `data-page` attribute. A Next.js app
carries it in a `<script id="__NEXT_DATA__">` tag. Both are JSON, and both
contain the prose the browser would render if it could run JavaScript.

The extraction must NOT weaken `looks_like_an_app`: a shell with no recoverable
payload must still be refused. The gate measures whether the extracted text
reaches `min_useful_chars`; if it does not, the shell is still rejected.
"""
import unittest

from src import webfetch


class AppPayloadExtractionTests(unittest.TestCase):
    """Text is recovered from Inertia and Next.js app shells."""

    def test_inertia_data_page_attribute_is_extracted(self):
        """An Inertia shell carries its copy in data-page JSON."""
        markup = '''
        <html>
        <body>
        <div id="app" data-page='{"props":{"title":"Acme Corp",
            "description":"We build software for people","features":["fast","reliable"]}}'>
        </div>
        <script>/* 500 bytes of framework code */</script>
        </body>
        </html>
        '''
        text = webfetch.readable_text(markup)
        self.assertIn("Acme Corp", text)
        self.assertIn("We build software for people", text)
        self.assertIn("fast", text)
        self.assertIn("reliable", text)

    def test_nextjs_next_data_script_is_extracted(self):
        """A Next.js shell carries its copy in __NEXT_DATA__ JSON."""
        markup = '''
        <html>
        <body>
        <div id="__next"></div>
        <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"company":"Acme Inc",
            "tagline":"Building the future","services":["consulting","training"]}}}
        </script>
        <script>/* framework code */</script>
        </body>
        </html>
        '''
        text = webfetch.readable_text(markup)
        self.assertIn("Acme Inc", text)
        self.assertIn("Building the future", text)
        self.assertIn("consulting", text)
        self.assertIn("training", text)

    def test_a_shell_with_no_payload_is_still_refused(self):
        """The gate must not weaken. A shell with no recoverable payload
        returns empty text and looks_like_an_app still fires."""
        markup = '''
        <html>
        <body>
        <div id="app"></div>
        <script>/* 1000 bytes of framework code, no data */</script>
        </body>
        </html>
        '''
        text = webfetch.readable_text(markup)
        # The shell has no prose in the body and no payload to extract.
        self.assertLess(len(text), 100,
                        "a shell with no payload must return minimal text")
        # looks_like_an_app must still fire.
        conf = {"min_useful_chars": 400}
        self.assertTrue(webfetch.looks_like_an_app(markup, text, conf),
                        "a shell with no recoverable payload must be refused")

    def test_a_shell_with_sufficient_payload_text_is_kept(self):
        """If the payload contains enough prose, the page is kept.
        This is the point: recover real text, never admit shells as evidence."""
        # Build a payload with enough UNIQUE text to pass min_useful_chars.
        # readable_text deduplicates repeated lines, so we need unique content.
        prose_parts = [
            "Acme is a software company that builds tools for teams.",
            "We focus on usability and reliability in everything we do.",
            "Our customers love our products and recommend them widely.",
            "The platform handles project management and team collaboration.",
            "We serve startups and enterprises across multiple industries.",
            "Security and performance are core to our architecture.",
            "Our team has decades of combined experience in software.",
            "We offer consulting, training, and ongoing support services.",
        ]
        prose = " ".join(prose_parts)
        markup = f'''
        <html>
        <body>
        <div id="app" data-page='{{"props":{{"content":"{prose}"}}}}'></div>
        <script>/* framework code */</script>
        </body>
        </html>
        '''
        text = webfetch.readable_text(markup)
        conf = {"min_useful_chars": 400}
        # The extracted text is sufficient, so looks_like_an_app returns False.
        self.assertGreaterEqual(len(text), 400,
                                f"expected 400+ chars, got {len(text)}: {text[:100]}")
        self.assertFalse(webfetch.looks_like_an_app(markup, text, conf),
                         "a shell with sufficient payload text is not an app")

    def test_malformed_json_is_silently_ignored(self):
        """A broken payload must not crash the extraction."""
        markup = '''
        <html>
        <body>
        <div id="app" data-page='{"props":{broken json'></div>
        <script>/* framework code */</script>
        </body>
        </html>
        '''
        # Must not raise.
        text = webfetch.readable_text(markup)
        self.assertIsInstance(text, str)

    def test_deeply_nested_json_is_bounded(self):
        """Pathological nesting must not hang the extraction."""
        # Build a deeply nested structure.
        nested = {"level": 0}
        current = nested
        for i in range(1, 20):
            current["child"] = {"level": i}
            current = current["child"]
        current["text"] = "deep value"

        import json
        payload = json.dumps({"props": nested})
        markup = f'<div data-page=\'{payload}\'></div>'

        # Must not hang, and must not extract the deep value (depth > 10).
        text = webfetch.readable_text(markup)
        self.assertNotIn("deep value", text,
                         "depth bounding must prevent extraction beyond 10 levels")

    def test_non_string_json_values_are_ignored(self):
        """Numbers, booleans, and null are not prose."""
        markup = '''
        <html>
        <body>
        <div data-page='{"props":{"count":42,"active":true,"name":null,
            "real_text":"Acme Corp"}}'></div>
        </body>
        </html>
        '''
        text = webfetch.readable_text(markup)
        self.assertIn("Acme Corp", text)
        # Numbers and booleans should not appear as "42" or "True".
        self.assertNotIn("42", text)
        self.assertNotIn("True", text)


class LooksLikeAnAppGateHoldsTests(unittest.TestCase):
    """The gate that refuses app shells must not weaken."""

    def test_a_prose_page_is_not_an_app(self):
        """A normal page with prose in the body is not refused."""
        markup = '''
        <html>
        <body>
        <h1>About Acme</h1>
        <p>Acme is a software company that builds tools for teams. We focus
        on usability and reliability. Our customers love our products.</p>
        </body>
        </html>
        '''
        text = webfetch.readable_text(markup)
        conf = {"min_useful_chars": 100}
        self.assertFalse(webfetch.looks_like_an_app(markup, text, conf))

    def test_an_empty_shell_is_an_app(self):
        """A shell with no prose and no payload is refused."""
        markup = '''
        <html>
        <body>
        <div id="app"></div>
        <script>/* lots of framework code */</script>
        </body>
        </html>
        '''
        text = webfetch.readable_text(markup)
        conf = {"min_useful_chars": 400}
        self.assertTrue(webfetch.looks_like_an_app(markup, text, conf))

    def test_a_shell_with_insufficient_payload_is_still_an_app(self):
        """A shell with a payload that yields < min_useful_chars is refused.
        The gate measures the extracted text, not the payload's existence."""
        markup = '''
        <html>
        <body>
        <div id="app" data-page='{"props":{"title":"Acme"}}'></div>
        <script>/* lots of framework code */</script>
        </body>
        </html>
        '''
        text = webfetch.readable_text(markup)
        conf = {"min_useful_chars": 400}
        # The payload yielded "Acme" (4 chars), which is < 400.
        self.assertLess(len(text), 400)
        self.assertTrue(webfetch.looks_like_an_app(markup, text, conf),
                        "a shell with insufficient payload text is still an app")


if __name__ == "__main__":
    unittest.main()
