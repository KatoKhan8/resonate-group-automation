"""Revival, read over HTTP.

The assertion that matters is the second table. A screen that showed only
the accounts worth reviving would hide the ones that are quiet, past
cooling, and have nothing new behind them - and that hidden queue is
exactly where somebody reaches for a repeat campaign.
"""
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
VIEWER = "client@productive.test"


class TheRevivalScreen(WebTest):

    def page(self, email=OPERATOR):
        return self.signin(email).get("/revival")

    def test_it_renders(self):
        status, body, _ = self.page()
        self.assertEqual(status, 200)
        self.assertIn("Revival", body)
        self.assertNotIn("Traceback", body)

    def test_it_shows_every_verdict_not_only_the_ready_ones(self):
        _, body, _ = self.page()
        for label in ("Closed", "Not yet", "Nothing new to say",
                      "Worth looking at again"):
            self.assertIn(label, body, label)

    def test_it_shows_the_queue_with_nothing_new(self):
        _, body, _ = self.page()
        self.assertIn("Quiet, and nothing new to say", body)

    def test_it_says_a_repeat_is_not_a_revival(self):
        _, body, _ = self.page()
        self.assertIn("same campaign with a later date", body)

    def test_it_says_a_verdict_is_not_an_instruction(self):
        _, body, _ = self.page()
        self.assertIn("never an instruction", body)

    def test_the_route_needs_the_operations_permission(self):
        from src.web import app

        self.assertIn("/revival", [path for path, _ in app.READ_PERMISSIONS])

    def test_a_viewer_cannot_read_it(self):
        """It names accounts that unsubscribed and accounts that are
        already clients. That is agency working state."""
        status, _, _ = self.page(VIEWER)
        self.assertIn(status, (403, 404))

    def test_the_api_refuses_a_viewer_on_its_own(self):
        """Two gates, and the HTTP refusal cannot tell you which one acted.
        Removing the route-table entry fails the test above; removing the
        permission check inside the API used to fail nothing at all, which
        is how defence in depth quietly becomes defence in one place."""
        from src import repo as repo_module, workspaces
        from src.web import api

        with self.assertRaises(workspaces.NotPermitted):
            api.revival_view(repo_module.Repo.for_user(VIEWER, "productive"))

    def test_the_refresh_api_refuses_a_viewer_on_its_own_too(self):
        from src import repo as repo_module, workspaces
        from src.web import api

        with self.assertRaises(workspaces.NotPermitted):
            api.refresh_plan(repo_module.Repo.for_user(VIEWER, "productive"))
