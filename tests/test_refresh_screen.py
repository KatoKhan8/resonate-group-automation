"""The refresh plan, read over HTTP.

The failure this guards against is a screen that shows a selection and
implies it is the whole answer: no cap, no exclusions, no note saying the
credits are an estimate and nothing has been spent.
"""
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
VIEWER = "client@productive.test"


class TheRefreshScreen(WebTest):

    def page(self, email=OPERATOR):
        session = self.signin(email)
        return session.get("/refresh")

    def test_it_renders(self):
        status, body, _ = self.page()
        self.assertEqual(status, 200)
        self.assertIn("Refresh plan", body)
        self.assertNotIn("Traceback", body)

    def test_it_says_nothing_was_spent(self):
        _, body, _ = self.page()
        self.assertIn("nothing here is refreshed", body.lower())

    def test_it_calls_the_credits_an_estimate(self):
        """The whole sentence, not the word. "Estimated credits" appears in
        the summary line above regardless, so asserting on "estimate" alone
        passes with the caveat deleted."""
        _, body, _ = self.page()
        self.assertIn("if every call it names is made", body)

    def test_the_route_needs_the_operations_permission(self):
        """The API refuses a viewer on its own, and this is the second
        gate. Both exist deliberately; a test that only exercised the
        refusal could not tell which one was doing it."""
        from src.web import app

        self.assertIn("/refresh", [path for path, _ in app.READ_PERMISSIONS])

    def test_it_says_there_is_no_scheduler(self):
        """"Weekly" must not imply a timer that does not exist."""
        _, body, _ = self.page()
        self.assertIn("no scheduler", body.lower())

    def test_it_shows_what_it_left_out(self):
        _, body, _ = self.page()
        self.assertIn("Not refreshed", body)
        self.assertIn("Left out", body)

    def test_a_viewer_cannot_read_it(self):
        """What an agency would spend is agency working state."""
        status, _, _ = self.page(VIEWER)
        self.assertIn(status, (403, 404))
