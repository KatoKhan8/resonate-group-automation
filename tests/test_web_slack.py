"""The Slack surfaces over real HTTP, and the boundary around each of them.

Three properties, and they are the reason this file exists separately from
`test_notify.py`:

**A channel name is tenant data.** Knowing which room another client's
positive replies land in is a cross-tenant read, however harmless one row
looks. The only screen that shows every workspace's mapping at once is the
super admin's, and reaching it as anybody else is a 404 rather than a 403.

**A viewer cannot change routing.** `slack.workspace_channel` is a workspace
policy, and a client-facing role that could edit it could point its own
alerts - or somebody else's - anywhere.

**Nothing is posted.** Every assertion below runs against a build where
`SLACK_LIVE` is unset, and the last test in the file says so by counting.
"""
import re

from src import notify
from src import workspaces as ws
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
OTHER = "ops@contactout.test"


class TheTogglesAreLabelledForPeople(WebTest):
    """`WORKSPACE_TOGGLES` values are (key, default) pairs, not keys.

    Unpacking one as a bare key put a Python tuple repr on the dashboard:
    `('slack.notify_campaign_milestones', False)` where a sentence belongs.
    """

    def test_no_screen_renders_a_tuple_repr(self):
        for who, path in ((OPERATOR, "/"),
                          (OPERATOR, "/notifications"),
                          (SUPER, "/admin/slack")):
            _, body, _ = self.signin(who).get(path)
            self.assertNotRegex(
                body, r"\(&#x27;slack\.|\('slack\.",
                f"{path} renders a tuple where a label belongs")

    def test_each_toggle_is_named_by_its_policy_label(self):
        _, body, _ = self.signin(OPERATOR).get("/")
        for key, _default in notify.WORKSPACE_TOGGLES.values():
            label = (ws.POLICY_KEYS.get(key) or {}).get("label")
            self.assertTrue(label, f"{key} has no label to render")
            self.assertIn(label, body, key)


class TheAdminSlackConsole(WebTest):
    """`/admin/slack`. Every workspace's routing, for the one role that may."""

    def test_a_super_admin_sees_every_workspace(self):
        _, body, _ = self.signin(SUPER).get("/admin/slack")
        self.assertIn("productive", body)
        self.assertIn("contactout", body)
        self.assertIn("demo-client", body)

    def test_it_names_the_global_operations_channel(self):
        _, body, _ = self.signin(SUPER).get("/admin/slack")
        self.assertIn(notify.ops_channel(), body)

    def test_it_names_the_workspace_with_no_channel(self):
        """The empty cell is the point, so the page says it in words."""
        _, body, _ = self.signin(SUPER).get("/admin/slack")
        self.assertIn("Workspaces with no channel", body)
        self.assertIn("demo-client", body)
        self.assertIn("posted nowhere", body)

    def test_an_admin_is_not_a_super_admin(self):
        """A workspace ADMIN runs one workspace, not the estate."""
        status, _, _ = self.signin(ADMIN).get("/admin/slack")
        self.assertEqual(status, 404)

    def test_an_operator_cannot_reach_it(self):
        status, _, _ = self.signin(OPERATOR).get("/admin/slack")
        self.assertEqual(status, 404)

    def test_a_viewer_cannot_reach_it(self):
        status, _, _ = self.signin(VIEWER).get("/admin/slack")
        self.assertEqual(status, 404)

    def test_an_anonymous_visitor_gets_the_sign_in_page_and_no_channels(self):
        """Every path answers the sign-in page when there is no session.

        The status is 200 by design across the whole app, so the assertion
        that matters is the second one: an unauthenticated request must not
        be able to read a channel name off the refusal.
        """
        status, body, _ = self.anonymous().get("/admin/slack")
        self.assertEqual(status, 200)
        self.assertIn("Sign in", body)
        self.assertNotIn("#client-", body)
        self.assertNotIn("resonate-outbound-ops", body)

    def test_it_is_a_404_and_not_a_403(self):
        """A refusal that confirms the console exists is a disclosure."""
        _, body, _ = self.signin(OPERATOR).get("/admin/slack")
        self.assertNotIn("contactout", body)
        self.assertNotIn("client-", body)


class OneWorkspaceCannotReadAnothersChannel(WebTest):

    def test_the_history_is_scoped_to_the_session_workspace(self):
        _, body, _ = self.signin(OPERATOR).get("/notifications")
        self.assertIn("productive", body)
        self.assertNotIn("#client-contactout-replies", body)

    def test_scope_all_does_nothing_for_a_non_super_admin(self):
        """A parameter that widens a scope on its own is the vulnerability."""
        _, body, _ = self.signin(OPERATOR).get("/notifications?scope=all")
        self.assertNotIn("#client-contactout-replies", body)
        self.assertNotIn("Kestrel Labs", body)

    def test_scope_all_widens_it_for_a_super_admin(self):
        _, body, _ = self.signin(SUPER).get("/notifications?scope=all")
        self.assertIn("#client-contactout-replies", body)
        self.assertIn("#client-productive-replies", body)

    def test_a_viewer_cannot_read_the_notification_log_at_all(self):
        """It carries provider names, capacity warnings and QA verdicts."""
        status, _, _ = self.signin(VIEWER).get("/notifications")
        self.assertEqual(status, 403)

    def test_the_dashboard_slack_panel_is_this_workspace_only(self):
        _, body, _ = self.signin(OPERATOR).get("/")
        self.assertIn("#client-productive-replies", body)
        self.assertNotIn("#client-contactout-replies", body)

    def test_the_same_person_in_two_workspaces_sees_two_answers(self):
        """`ops@contactout.test` is in both, with different roles."""
        session = self.signin(OTHER)
        _, body, _ = session.get("/")
        self.assertIn("#client-contactout-replies", body)
        self.assertNotIn("#client-productive-replies", body)


class AClientIsNotShownTheMachine(WebTest):

    def test_a_viewers_dashboard_names_its_own_channel(self):
        """Knowing where your replies land is part of what you bought."""
        _, body, _ = self.signin(VIEWER).get("/")
        self.assertIn("#client-productive-replies", body)

    def test_a_viewers_dashboard_does_not_name_the_operations_channel(self):
        """Where credit exposure is discussed is not part of what you bought."""
        _, body, _ = self.signin(VIEWER).get("/")
        self.assertNotIn(notify.ops_channel(), body)
        self.assertNotIn("resonate-outbound-ops", body)

    def test_a_viewers_dashboard_offers_no_link_it_would_be_refused_from(self):
        _, body, _ = self.signin(VIEWER).get("/")
        self.assertNotIn('href="/notifications"', body)

    def test_no_screen_leaks_a_credential(self):
        for who, path in ((SUPER, "/admin/slack"), (SUPER, "/notifications"),
                          (OPERATOR, "/notifications"), (OPERATOR, "/"),
                          (VIEWER, "/")):
            _, body, _ = self.signin(who).get(path)
            lowered = body.lower()
            for forbidden in ("xoxb-", "signing_secret", "bearer ",
                              "api_key", "webhook_url"):
                self.assertNotIn(forbidden, lowered, f"{path} for {who}")


class OnlyTheRightRoleChangesRouting(WebTest):

    def _set_channel(self, session, value, expect=(200, 303, 302)):
        csrf = session.csrf("/settings")
        status, body, _ = session.post(
            "/settings/policy",
            {"csrf": csrf or "",
             f"policy:{notify.WORKSPACE_CHANNEL_KEY}": value})
        return status, body

    def test_a_viewer_cannot_change_the_channel(self):
        viewer = self.signin(VIEWER)
        before = notify.workspace_channel("productive")
        status, _ = self._set_channel(viewer, "#somewhere-else")
        self.assertIn(status, (403, 404))
        self.assertEqual(notify.workspace_channel("productive"), before)

    def test_a_reviewer_cannot_change_the_channel(self):
        reviewer = self.signin(REVIEWER)
        before = notify.workspace_channel("productive")
        status, _ = self._set_channel(reviewer, "#somewhere-else")
        self.assertIn(status, (403, 404))
        self.assertEqual(notify.workspace_channel("productive"), before)

    def test_an_admin_can_change_its_own_workspaces_channel(self):
        admin = self.signin(ADMIN)
        self._set_channel(admin, "#client-productive-moved")
        self.assertEqual(notify.workspace_channel("productive"),
                         "#client-productive-moved")
        # Put it back; the other classes in this file read it.
        ws.set_policy("productive",
                      {notify.WORKSPACE_CHANNEL_KEY:
                       "#client-productive-replies"}, actor="test")

    def test_changing_one_workspace_leaves_the_other_alone(self):
        admin = self.signin(ADMIN)
        before = notify.workspace_channel("contactout")
        self._set_channel(admin, "#client-productive-again")
        self.assertEqual(notify.workspace_channel("contactout"), before)
        ws.set_policy("productive",
                      {notify.WORKSPACE_CHANNEL_KEY:
                       "#client-productive-replies"}, actor="test")

    def test_a_change_reaches_the_audit_log(self):
        admin = self.signin(ADMIN)
        self._set_channel(admin, "#client-productive-audited")
        entries = ws.audit(limit=50)
        self.assertTrue(
            any(notify.WORKSPACE_CHANNEL_KEY in str(e) for e in entries),
            "changing where a client's replies are announced is not in the "
            "audit log")
        ws.set_policy("productive",
                      {notify.WORKSPACE_CHANNEL_KEY:
                       "#client-productive-replies"}, actor="test")


class TheDemoScenariosAreVisibleAndFictional(WebTest):

    def test_the_scenarios_render_for_a_super_admin(self):
        _, body, _ = self.signin(SUPER).get("/notifications?scope=all")
        self.assertIn("Slack scenarios", body)
        self.assertIn("Harbourline Studio", body)

    def test_the_scenarios_are_not_shown_inside_one_workspace(self):
        """The board names every room, so it is not a workspace screen."""
        _, body, _ = self.signin(OPERATOR).get("/notifications")
        self.assertNotIn("Slack scenarios", body)
        self.assertNotIn("Kestrel Labs", body)

    def test_they_span_more_than_one_workspace(self):
        from src.web import demoslack

        spaces = {s["workspace"] for s in demoslack.SCENARIOS
                  if s["workspace"]}
        self.assertGreaterEqual(len(spaces), 2)

    def test_one_of_them_has_nowhere_to_go(self):
        from src.web import demoslack

        listed = demoslack.scenarios()
        unconfigured = [s for s in listed
                        if s["status"] == notify.UNCONFIGURED]
        self.assertTrue(unconfigured,
                        "the demo configures every workspace, so it never "
                        "shows what an unmapped one does")
        self.assertIsNone(unconfigured[0]["channel"])

    def test_the_unconfigured_one_is_not_diverted_to_the_ops_channel(self):
        from src.web import demoslack

        for scenario in demoslack.scenarios():
            if scenario["status"] == notify.UNCONFIGURED:
                self.assertNotEqual(scenario["channel"], notify.ops_channel())

    def test_the_same_event_reaches_two_different_rooms(self):
        from src.web import demoslack

        rooms = {s["channel"] for s in demoslack.scenarios()
                 if s["type"] == notify.POSITIVE_REPLY and s["channel"]}
        self.assertGreaterEqual(len(rooms), 2)


class NothingIsPosted(WebTest):
    """The count that matters for this mission."""

    def test_slack_is_not_live(self):
        from src.providers import slack

        self.assertFalse(slack.live())

    def test_every_demo_notification_is_planned_not_sent(self):
        for scenario in notify.load():
            self.assertNotEqual(scenario["status"], notify.SENT,
                                f"{scenario['type']} claims to have been sent")

    def test_posting_is_refused_even_when_asked_directly(self):
        rows = [r for r in notify.load() if r.get("channel")]
        self.assertTrue(rows, "no routable notification to try")
        result = notify.deliver(rows[0]["id"])
        self.assertEqual(result["status"], notify.FAILED)
        self.assertIn("SlackPostingNotEnabled", result["last_error"])

    def test_a_refused_post_changed_nothing_else(self):
        rows = [r for r in notify.load() if r.get("channel")]
        before = len(notify.load())
        notify.deliver(rows[0]["id"])
        self.assertEqual(len(notify.load()), before)

    def test_no_page_claims_a_message_was_sent(self):
        _, body, _ = self.signin(SUPER).get("/notifications?scope=all")
        self.assertIn("Slack posting is disabled", body)
        self.assertFalse(re.search(r"\bposted to #", body))


class AReportIsAnnouncedTwice(WebTest):
    """One export, two notifications, and they say different things.

    The operations channel is told a report was produced and by whom, which is
    an audit trail somebody watches across every client. The workspace's own
    channel is told its report is ready. Two rows rather than one message
    copied to two rooms, because a shared row eventually leaks the wrong half
    into the wrong room.
    """

    def before(self, event_type):
        return len([r for r in notify.load() if r["type"] == event_type])

    def test_an_export_reaches_the_operations_channel(self):
        before = self.before(notify.REPORT_GENERATED)
        status, _, _ = self.signin(OPERATOR).get("/export/contacts.csv")
        self.assertEqual(status, 200)
        rows = [r for r in notify.load()
                if r["type"] == notify.REPORT_GENERATED]
        self.assertGreater(len(rows), before)
        self.assertEqual(rows[-1]["destination"], notify.GLOBAL)

    def test_the_client_side_one_is_off_until_a_client_asks_for_it(self):
        """A ping for every export is how a client channel gets muted.

        `slack.notify_reports` defaults to off, so the row is routed to the
        workspace and then suppressed. It is recorded either way, because
        "we decided not to tell them" is a fact somebody may need to check.
        """
        self.signin(OPERATOR).get("/export/analytics.csv")
        rows = [r for r in notify.load()
                if r["type"] == notify.REPORT_AVAILABLE
                and r["workspace"] == "productive"]
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["destination"], notify.WORKSPACE)
        self.assertEqual(rows[-1]["status"], notify.SUPPRESSED)
        self.assertIsNone(rows[-1]["channel"])

    def test_switching_it_on_sends_it_to_that_workspaces_own_channel(self):
        ws.set_policy("productive", {"slack.notify_reports": "on"},
                      actor="test")
        try:
            self.signin(OPERATOR).get("/export/analytics.csv")
            rows = [r for r in notify.load()
                    if r["type"] == notify.REPORT_AVAILABLE
                    and r["workspace"] == "productive"
                    and r["status"] == notify.PLANNED]
            self.assertTrue(rows)
            self.assertEqual(rows[-1]["channel"],
                             "#client-productive-replies")
        finally:
            ws.set_policy("productive", {"slack.notify_reports": "off"},
                          actor="test")

    def test_the_client_facing_one_does_not_name_the_person(self):
        """Who ran the export is operational. The client asked for a report."""
        self.signin(OPERATOR).get("/export/analytics.json")
        available = [r for r in notify.load()
                     if r["type"] == notify.REPORT_AVAILABLE][-1]
        self.assertNotIn("by", available["payload"])
        self.assertNotIn(OPERATOR, str(available["payload"]))

    def test_the_operational_one_does_name_the_person(self):
        self.signin(OPERATOR).get("/export/analytics.json")
        generated = [r for r in notify.load()
                     if r["type"] == notify.REPORT_GENERATED][-1]
        self.assertEqual(generated["payload"].get("by"), OPERATOR)

    def test_one_workspaces_export_never_names_another(self):
        ws.set_policy("contactout", {"slack.notify_reports": "on"},
                      actor="test")
        try:
            self.signin(OTHER).get("/export/contacts.csv")
            rows = [r for r in notify.load()
                    if r["type"] == notify.REPORT_AVAILABLE
                    and r["workspace"] == "contactout"
                    and r["status"] == notify.PLANNED]
            self.assertTrue(rows)
            self.assertEqual(rows[-1]["channel"],
                             "#client-contactout-replies")
            self.assertNotEqual(rows[-1]["channel"],
                                "#client-productive-replies")
        finally:
            ws.set_policy("contactout", {"slack.notify_reports": "off"},
                          actor="test")

    def test_neither_of_them_was_posted(self):
        self.signin(OPERATOR).get("/export/contacts.csv")
        for row in notify.load():
            self.assertNotEqual(row["status"], notify.SENT)
