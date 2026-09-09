"""Per-workspace policy, and the three settings that are deliberately absent.

A workspace's rules live in a hand-written client YAML file with comments in
it. `src/clients.py` says in its own docstring why a form must not rewrite one:
"a misparsed persona cap is a spend, and a misparsed geo is a live customer
getting cold sequenced". So the file stays the baseline and what a workspace
admin changes is an override, merged on read.

What is tested here is mostly the shape of the refusals. A settings screen that
can switch off double verification or MX filtering is not a settings screen, it
is a way round the two safety properties this build is built on.
"""
from src import repo as repo_module
from src import workspaces
from tests.webbase import WebTest

ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"


class PolicyOverrides(WebTest):

    def setUp(self):
        self.session = self.signin(ADMIN)
        self._rows = [dict(r) for r in workspaces.load()]

    def tearDown(self):
        workspaces.save(self._rows)

    def save(self, session=None, **updates):
        session = session or self.session
        fields = {"csrf": session.csrf("/settings")}
        fields.update({f"policy:{k}": v for k, v in updates.items()})
        return session.post("/settings/policy", fields)

    def current(self):
        return workspaces.policy("productive")

    def test_the_form_renders_with_every_editable_key(self):
        status, body, _ = self.session.get("/settings")
        self.assertEqual(status, 200)
        for key in workspaces.POLICY_KEYS:
            self.assertIn(key, body)

    def test_an_override_is_stored_and_takes_effect_on_the_next_read(self):
        status, _, _ = self.save(**{"market.size_min_employees": "15"})
        self.assertEqual(status, 200)
        self.assertEqual(self.current()["market.size_min_employees"], 15)

        repo = repo_module.Repo.for_user(ADMIN, "productive")
        self.assertEqual(repo.config()["market"]["size_min_employees"], 15)

    def test_the_client_config_file_is_not_rewritten(self):
        import os
        from src import clients
        path = clients.path_for("productive")
        def snapshot():
            with open(path, encoding="utf-8") as fh:
                return os.path.getmtime(path), fh.read()

        before = snapshot()
        self.save(**{"market.size_min_employees": "22"})
        after = snapshot()
        self.assertEqual(before[1], after[1],
                         "the hand-written client config was rewritten")

    def test_a_change_lands_in_the_audit_log_with_a_before_and_an_after(self):
        self.save(**{"market.size_min_employees": "31"})
        entries = [e for e in workspaces.audit(limit=200)
                   if e["action"] == "workspace.policy_changed"]
        self.assertTrue(entries)
        self.assertEqual(entries[0]["after"]["market.size_min_employees"], 31)
        self.assertEqual(entries[0]["actor"], ADMIN)

    def test_an_override_does_not_leak_into_another_workspace(self):
        self.save(**{"market.size_min_employees": "99"})
        theirs = repo_module.Repo.for_user("ops@contactout.test", "contactout")
        self.assertNotEqual(theirs.config().get("market", {})
                            .get("size_min_employees"), 99)

    def test_a_blank_cap_removes_the_override_rather_than_storing_null(self):
        self.save(**{"dm_plan.max_batch_credits": "500"})
        self.assertEqual(self.current()["dm_plan.max_batch_credits"], 500)
        self.save(**{"dm_plan.max_batch_credits": ""})
        self.assertNotIn("dm_plan.max_batch_credits", self.current())


class WhatThisScreenRefuses(WebTest):

    def setUp(self):
        self.session = self.signin(ADMIN)
        self._rows = [dict(r) for r in workspaces.load()]

    def tearDown(self):
        workspaces.save(self._rows)

    def save(self, **updates):
        fields = {"csrf": self.session.csrf("/settings")}
        fields.update({f"policy:{k}": v for k, v in updates.items()})
        return self.session.post("/settings/policy", fields)

    def test_double_verification_cannot_be_lowered_to_one(self):
        """A property of this build, not a setting."""
        status, body, _ = self.save(
            **{"verification.required_confirmations": "1"})
        self.assertEqual(status, 400)
        self.assertIn("between 2 and 3", body)
        self.assertNotIn("verification.required_confirmations",
                         workspaces.policy("productive"))

        repo = repo_module.Repo.for_user(ADMIN, "productive")
        from src import verification
        self.assertGreaterEqual(
            verification.policy_for(repo.config())["required_confirmations"], 2)

    def test_mx_filtering_cannot_be_switched_off_from_here(self):
        status, body, _ = self.save(
            **{"email_security.mx_filter.enabled": "false"})
        self.assertEqual(status, 400)
        self.assertIn("not a workspace-overridable setting", body)

    def test_review_enrichment_cannot_be_widened_from_a_form(self):
        """/icp says widening it is a config change. This keeps that true."""
        status, body, _ = self.save(
            **{"dm_plan.allow_review_enrichment": "true"})
        self.assertEqual(status, 400)
        self.assertIn("not a workspace-overridable setting", body)

        repo = repo_module.Repo.for_user(ADMIN, "productive")
        from src import dmplan
        self.assertFalse(
            dmplan.settings(repo.config())["allow_review_enrichment"])

    def test_an_invented_key_is_refused_not_ignored(self):
        before = dict(workspaces.policy("productive"))
        status, body, _ = self.save(**{"anything.at.all": "1"})
        self.assertEqual(status, 400)
        self.assertNotIn("anything.at.all", workspaces.policy("productive"))
        self.assertEqual(workspaces.policy("productive"), before,
                         "a refused request moved something else")

    def test_a_value_out_of_range_is_refused_not_clamped(self):
        """Somebody told the system does what they asked, when it did not."""
        status, body, _ = self.save(**{"sending.daily_email_volume": "99999"})
        self.assertEqual(status, 400)
        self.assertNotIn("sending.daily_email_volume",
                         workspaces.policy("productive"))

    def test_one_bad_value_saves_none_of_the_others(self):
        before = dict(workspaces.policy("productive"))
        status, _, _ = self.save(**{"market.size_min_employees": "12",
                                    "sending.daily_email_volume": "99999"})
        self.assertEqual(status, 400)
        self.assertEqual(workspaces.policy("productive"), before,
                         "a half-applied policy is rules nobody chose")


class WhoMayChangeIt(WebTest):

    def setUp(self):
        self._rows = [dict(r) for r in workspaces.load()]

    def tearDown(self):
        workspaces.save(self._rows)

    def test_an_operator_reads_the_page_but_gets_no_form(self):
        session = self.signin(OPERATOR)
        status, body, _ = session.get("/settings")
        self.assertEqual(status, 200)
        self.assertIn("not change them", body)
        self.assertNotIn('action="/settings/policy"', body)

    def test_an_operator_posting_a_policy_change_is_refused(self):
        session = self.signin(OPERATOR)
        before = dict(workspaces.policy("productive"))
        status, _, _ = session.post("/settings/policy", {
            "csrf": session.csrf("/settings"),
            "policy:market.size_min_employees": "1"})
        self.assertEqual(status, 403)
        self.assertNotIn("market.size_min_employees",
                         workspaces.policy("productive"))
        self.assertEqual(workspaces.policy("productive"), before)

    def test_a_viewer_cannot_reach_the_page_at_all(self):
        self.assertEqual(self.signin(VIEWER).get("/settings")[0], 403)


class TheProviderMapping(WebTest):

    def setUp(self):
        from src import campaigns as campaign_store
        self._campaigns = [dict(c) for c in campaign_store.load()]

    def tearDown(self):
        from src import campaigns as campaign_store
        campaign_store.save(self._campaigns)

    def test_an_admin_can_record_a_mapping(self):
        from src import campaigns as campaign_store
        session = self.signin(ADMIN)
        status, _, _ = session.post("/settings/mapping", {
            "csrf": session.csrf("/settings"), "campaign_id": "uk-digital",
            "bison": "bison-123", "heyreach": "hr-456"})
        self.assertEqual(status, 200)
        campaign = campaign_store.get("uk-digital")
        self.assertEqual(campaign["bison_campaign_id"], "bison-123")
        self.assertEqual(campaign["heyreach_campaign_id"], "hr-456")

    def test_recording_a_mapping_is_audited(self):
        session = self.signin(ADMIN)
        session.post("/settings/mapping", {
            "csrf": session.csrf("/settings"), "campaign_id": "uk-digital",
            "bison": "bison-789"})
        entries = [e for e in workspaces.audit(limit=200)
                   if e["action"] == "provider_mapping.changed"]
        self.assertTrue(entries)
        self.assertEqual(entries[0]["after"]["bison"], "bison-789")

    def test_an_operator_cannot_change_a_mapping(self):
        from src import campaigns as campaign_store
        session = self.signin(OPERATOR)
        status, _, _ = session.post("/settings/mapping", {
            "csrf": session.csrf("/settings"), "campaign_id": "uk-digital",
            "bison": "forged"})
        self.assertEqual(status, 403)
        self.assertNotEqual(
            campaign_store.get("uk-digital")["bison_campaign_id"], "forged")

    def test_another_workspaces_campaign_cannot_be_remapped(self):
        from src import campaigns as campaign_store
        session = self.signin(ADMIN)
        status, _, _ = session.post("/settings/mapping", {
            "csrf": session.csrf("/settings"),
            "campaign_id": "apac-recruiting", "bison": "stolen"})
        self.assertEqual(status, 404)
        self.assertNotEqual(
            campaign_store.get("apac-recruiting")["bison_campaign_id"],
            "stolen")

    def test_the_page_states_that_nothing_is_created_at_the_provider(self):
        session = self.signin(ADMIN)
        _, body, _ = session.get("/settings")
        self.assertIn("records a <b>pointer</b>", body)
        self.assertIn("creates nothing at", body)
