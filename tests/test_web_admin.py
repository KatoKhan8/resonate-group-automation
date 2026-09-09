"""The super admin's control centre, and the refusal trail underneath it.

Two things are being held here. The console has to actually show the things a
super admin is the only person who can see - every workspace, the provider
spend, the failed jobs, the events that matched nothing, the global suppression
list, the refusals - and none of it may leak to anybody else, including through
the one screen that is deliberately unscoped.
"""
from src import jobs, store, workspaces
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
VIEWER = "client@productive.test"


class TheControlCentre(WebTest):

    def setUp(self):
        self.session = self.signin(SUPER)

    def test_every_section_the_brief_asks_for_is_on_the_page(self):
        status, body, _ = self.session.get("/admin")
        self.assertEqual(status, 200)
        for section in ("Workspaces", "Users", "Roles and what each one carries",
                        "Provider usage", "Credits, by call", "Failed jobs",
                        "Unmatched provider events", "Global suppression",
                        "Security events", "Feature flags",
                        "Where the state lives"):
            self.assertIn(section, body, f"/admin is missing: {section}")

    def test_it_shows_every_workspace_not_just_the_current_one(self):
        _, body, _ = self.session.get("/admin")
        for slug in ("productive", "contactout", "demo-client"):
            self.assertIn(slug, body)

    def test_the_role_table_is_read_from_the_permission_model(self):
        """A table typed into a page is a second statement of the model."""
        _, body, _ = self.session.get("/admin")
        for role in workspaces.ROLES:
            self.assertIn(role, body)
        for permission in ("campaign.approve", "contacts.export",
                           "provider_settings.manage"):
            self.assertIn(permission, body)

    def test_live_sending_is_reported_as_off_and_says_what_holds_it(self):
        _, body, _ = self.session.get("/admin")
        self.assertIn("live_sending", body)
        self.assertIn("LiveSendNotEnabled", body)

    def test_demo_mode_is_not_reported_as_a_boolean_it_was_not_told(self):
        """`None` is "set per process", not "off"."""
        _, body, _ = self.session.get("/admin")
        self.assertIn("per process", body)

    def test_a_cost_nobody_reported_is_absent_rather_than_zero(self):
        from src.web import api
        costs = api.spend_ledger()
        if costs["reported_cost"] is None:
            self.assertIn("not reported",
                          self.session.get("/admin")[1])

    def test_the_suppression_list_is_named_as_global(self):
        _, body, _ = self.session.get("/admin")
        self.assertIn("every workspace", body)


class SystemHealthSaysWhyItSaysWhat(WebTest):
    """A state and its explanation have to be about the same thing.

    `all(exists)` reported the state store *degraded* on any install where
    no job had run, because `jobs.jsonl` does not exist until the first one
    does - and the sentence beside that word was the standing note about one
    process and a lock, which has nothing to do with a missing file.
    """

    def component(self, name="State store"):
        from src.web import api

        for entry in api.system_health()["components"]:
            if entry["name"] == name:
                return entry
        self.fail(f"no {name} component")

    def test_a_log_nothing_has_written_to_is_not_a_fault(self):
        from src import jobs

        self.assertEqual(jobs.load(), [], "this test needs no jobs to exist")
        entry = self.component()
        self.assertEqual(entry["state"], "healthy", entry["why"])
        self.assertIn("not written yet", entry["why"])

    def test_a_store_missing_while_its_rows_are_loaded_is_a_fault(self):
        from src.web import api

        state, why = api._state_store_health({
            "files": {"queue": {"exists": False}},
            "counts": {"records": 57},
            "note": "the standing note.",
        })
        self.assertEqual(state, "degraded")
        self.assertIn("queue", why)
        self.assertIn("not a fresh install", why)

    def test_the_page_still_renders_it(self):
        status, body, _ = self.signin(SUPER).get("/admin/health")
        self.assertEqual(status, 200)
        self.assertIn("State store", body)


class OnlyASuperAdmin(WebTest):

    def test_a_workspace_admin_gets_a_404_not_a_403(self):
        """Learning that an admin console exists here is a disclosure."""
        admin = self.signin(ADMIN)
        status, body, _ = admin.get("/admin")
        self.assertEqual(status, 404)
        self.assertNotIn("Provider usage", body)
        self.assertNotIn("Feature flags", body)

    def test_an_operator_and_a_viewer_get_the_same_404(self):
        for email in (OPERATOR, VIEWER):
            status, body, _ = self.signin(email).get("/admin")
            self.assertEqual(status, 404, email)
            self.assertNotIn("contactout", body, email)

    def test_no_credential_value_appears_on_the_console(self):
        import os
        canary = "canary-value-that-must-never-render"
        os.environ["CONTACTOUT_TOKEN"] = canary
        try:
            _, body, _ = self.signin(SUPER).get("/admin")
            self.assertNotIn(canary, body)
            self.assertIn("CONTACTOUT_TOKEN", body)
        finally:
            os.environ.pop("CONTACTOUT_TOKEN", None)


class TheRefusalTrail(WebTest):
    """A refusal that leaves no trace is a refusal nobody can review."""

    def refusals(self):
        return [e for e in workspaces.audit(limit=5000)
                if e.get("action") == "security.refused"]

    def test_a_permission_refusal_is_recorded(self):
        before = len(self.refusals())
        viewer = self.signin(VIEWER)
        self.assertEqual(viewer.get("/companies")[0], 403)
        after = self.refusals()
        self.assertGreater(len(after), before)
        self.assertEqual(after[0]["actor"], VIEWER)
        self.assertIn("/companies", after[0]["resource_id"])
        self.assertEqual(after[0]["metadata"]["kind"], "refused")

    def test_a_cross_workspace_reach_is_recorded_as_such(self):
        theirs = next(r for r in store.load()
                      if r.get("client") == "contactout")
        session = self.signin(OPERATOR)
        self.assertEqual(session.get(f"/companies/{theirs['id']}")[0], 404)
        kinds = {e["metadata"].get("kind") for e in self.refusals()}
        self.assertIn("cross_workspace", kinds)

    def test_a_refused_workspace_switch_is_recorded(self):
        session = self.signin(OPERATOR)
        session.post("/select-workspace",
                     {"csrf": session.csrf(), "workspace": "contactout"})
        kinds = {e["metadata"].get("kind") for e in self.refusals()}
        self.assertIn("not_a_member", kinds)

    def test_the_trail_never_records_what_was_sent(self):
        """An attacker who chooses what goes in your log has a second tool."""
        session = self.signin(VIEWER)
        session.get("/companies?secret=do-not-log-me-please")
        session.post("/icp/decide", {
            "csrf": session.csrf(), "record_id": "also-do-not-log-me",
            "decision": "accept", "note": "nor-this"})
        for entry in self.refusals():
            blob = str(entry)
            self.assertNotIn("do-not-log-me", blob)
            self.assertNotIn("nor-this", blob)

    def test_the_refusals_reach_the_console(self):
        viewer = self.signin(VIEWER)
        viewer.get("/companies")
        _, body, _ = self.signin(SUPER).get("/admin")
        self.assertIn("refusal(s)", body)
        self.assertIn(VIEWER, body)
        self.assertIn("refused", body)

    def test_a_failure_to_log_never_turns_a_refusal_into_a_500(self):
        """The refusal is the point; the record of it is not worth losing it."""
        import unittest.mock as mock
        from src import workspaces as ws_module

        viewer = self.signin(VIEWER)
        with mock.patch.object(ws_module, "record",
                               side_effect=OSError("disk full")):
            status, _, _ = viewer.get("/companies")
        self.assertEqual(status, 403)


class FailedJobsSurface(WebTest):

    def setUp(self):
        self._jobs = [dict(j) for j in jobs.load()]

    def tearDown(self):
        jobs.save(self._jobs)

    def test_a_failed_job_is_listed_with_the_reason_it_stopped(self):
        broken = jobs.new(jobs.ICP_CLASSIFY, "productive", batch="uk-digital",
                          total=10)
        broken["status"] = jobs.FAILED
        broken["error"] = "stopped after 20 failures in 40 records"
        jobs.append(broken)

        _, body, _ = self.signin(SUPER).get("/admin")
        self.assertIn(broken["id"], body)
        self.assertIn("stopped after 20 failures", body)

    def test_with_no_failures_the_page_says_so_rather_than_showing_nothing(self):
        _, body, _ = self.signin(SUPER).get("/admin")
        self.assertIn("No job has failed", body)
