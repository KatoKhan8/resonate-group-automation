"""What the client-facing role may see, and what writes it may cause.

`viewer` is the role a *client* is given: the person this system is run for,
not by. `_VIEWER` grants exactly `workspace.view` and `reporting.view`.

Two things crossed that line.

**A write reachable by the weakest role, on a GET, with no CSRF.**
`/reporting/editor/export` resolves through `READ_PERMISSIONS` to
`REPORTING_VIEW`, and `api.render_draft` writes a `report_store` row and an
audit entry. Every POST that touches a draft demands `REPORTING_EXPORT`, an
operator permission - so the weaker path wrote and the stronger path was the
one that was gated. Following a link made a client write report history into
the workspace.

The guard went into `render_draft` rather than onto the route. The editor is
deliberately readable by a viewer - `test_report_editor.WhoMayEdit` says "a
viewer may read but not create" - so gating the whole prefix would have taken
away a screen the role is meant to have. What needed refusing was the write,
and the service is where the other fifteen mutators ask.

**The operator's own breakdown, rendered underneath the client's report.**
`/reporting` computed `simple` from `OPERATIONS_VIEW`, handed it to
`pages.reporting`, and then appended `pages.analytics` regardless - a table of
sendable, email eligible, double verified and held counts, under a note
explaining that "a reply here came from a rehearsal, not from a mailbox".

What must not regress in fixing either: a viewer keeps their own report and
keeps being able to download it. `/reporting/client` stays `REPORTING_VIEW`,
because `regenerate_report` marks an existing row and creates no history -
downloading your own report is what the role is for.
"""
import unittest

from src import workspaces as ws
from tests.webbase import WebTest

CLIENT = "client@productive.test"
OPERATOR = "ops@productive.test"


class TheClientViewerBoundary(WebTest):

    def setUp(self):
        self.client = self.signin(CLIENT)
        self.operator = self.signin(OPERATOR)

    # ------------------------------------- the write the weakest role caused

    def test_a_viewer_may_still_read_the_editor(self):
        """Deliberate, and asserted here so the fix cannot creep into it."""
        status, _, _ = self.client.get("/reporting/editor")
        self.assertEqual(status, 200)

    def test_a_viewer_cannot_trigger_the_export_that_writes(self):
        status, _, _ = self.client.get("/reporting/editor/export?draft=1")
        self.assertNotEqual(status, 200)

    def test_an_operator_still_reaches_the_editor(self):
        """Otherwise the guard refuses everybody and proves nothing."""
        status, _, _ = self.operator.get("/reporting/editor")
        self.assertEqual(status, 200)

    def test_the_write_asks_at_the_service_not_only_at_the_route(self):
        """So a second caller cannot reintroduce it by forgetting."""
        from src.web import api
        from src import repo as repo_module
        repo = repo_module.Repo.for_user(CLIENT, "productive")
        self.assertNotIn(ws.REPORTING_EXPORT, ws.GRANTS[ws.VIEWER])
        with self.assertRaises(ws.NotPermitted):
            api.render_draft(repo, "any-draft-id")

    # ----------------------------------- the breakdown a client was reading

    def test_a_viewer_does_not_see_the_operator_breakdown(self):
        status, body, _ = self.client.get("/reporting")
        self.assertEqual(status, 200)
        self.assertNotIn("double verified", body)
        self.assertNotIn("rehearsal", body)

    def test_an_operator_still_sees_it(self):
        status, body, _ = self.operator.get("/reporting")
        self.assertEqual(status, 200)
        self.assertIn("double verified", body)

    # ------------------------------------------ and the role still functions

    def test_a_viewer_still_has_a_reporting_page(self):
        status, body, _ = self.client.get("/reporting")
        self.assertEqual(status, 200)
        self.assertTrue(body.strip())

    def test_a_viewer_can_still_reach_their_own_client_report(self):
        """Downloading your own report is what this role exists for."""
        status, _, _ = self.client.get("/reporting/client")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
