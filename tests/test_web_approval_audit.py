"""Approving outreach is the most consequential act here. It goes in the trail.

`orchestrator.decide` writes the campaign's own log, and that is the right
place for the campaign's history. It is not the place a person auditing *this
workspace* looks. The audit log is, and until now the single decision that
turns copy into something a human has blessed did not appear in it.

Refusals are recorded too. "Somebody tried to approve this and was not allowed
to" is exactly what is invisible when only successes are written down.
"""
from src import campaigns as campaign_store
from src import workspaces
from tests.webbase import WebTest

ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"


class ApprovalIsAudited(WebTest):

    def setUp(self):
        self._campaigns = [dict(c) for c in campaign_store.load()]

    def tearDown(self):
        campaign_store.save(self._campaigns)

    def entries(self, prefix="campaign."):
        return [e for e in workspaces.audit(limit=500)
                if str(e.get("action", "")).startswith(prefix)]

    def decide(self, session, campaign_id, action="approve", fingerprint=None):
        campaign = campaign_store.get(campaign_id)
        return session.post("/approvals/campaign", {
            "csrf": session.csrf("/approvals"), "campaign_id": campaign_id,
            "action": action,
            "fingerprint": (fingerprint if fingerprint is not None
                            else campaign.get("fingerprint") or "")})

    def test_an_approval_that_succeeds_is_recorded_as_approved(self):
        """Named exactly, not "one of four".

        An earlier version of this test accepted any approval-shaped action,
        and the mutation audit caught what that hid: with the success path's
        audit call removed, the *refusal* path still wrote an entry and the
        test still passed. A test that cannot tell an approval from a refusal
        is not testing the approval.
        """
        session = self.signin(REVIEWER)
        status, body, _ = self.decide(session, "dach-software")
        self.assertEqual(status, 200, body[:200])
        self.assertEqual(campaign_store.get("dach-software")["status"],
                         "approved")

        mine = [e for e in self.entries()
                if e["resource_id"] == "dach-software"]
        self.assertTrue(mine, "an approval succeeded and was not recorded")
        self.assertEqual(mine[0]["action"], "campaign.approved")
        self.assertEqual(mine[0]["after"]["status"], "approved")

    def test_a_rejection_is_recorded_as_a_rejection(self):
        session = self.signin(REVIEWER)
        self.decide(session, "us-creative", action="reject")
        mine = [e for e in self.entries() if e["resource_id"] == "us-creative"]
        self.assertTrue(mine)
        self.assertEqual(mine[0]["action"], "campaign.rejected")

    def test_the_entry_names_who_decided_and_which_campaign(self):
        session = self.signin(REVIEWER)
        self.decide(session, "dach-software")
        entry = [e for e in self.entries()
                 if e["resource_id"] == "dach-software"][0]
        self.assertEqual(entry["actor"], REVIEWER)
        self.assertEqual(entry["workspace"], "productive")
        self.assertEqual(entry["resource_id"], "dach-software")
        self.assertIn("status", entry["before"])
        self.assertIn("status", entry["after"])

    def test_a_stale_approval_is_recorded_as_stale_not_as_approved(self):
        session = self.signin(REVIEWER)
        status, _, _ = self.decide(session, "dach-software",
                                   fingerprint="a-campaign-that-moved")
        self.assertEqual(status, 409)
        mine = [e["action"] for e in self.entries()
                if e["resource_id"] == "dach-software"]
        self.assertIn("campaign.approval_stale", mine)
        self.assertNotIn("campaign.approved", mine)
        self.assertNotEqual(campaign_store.get("dach-software")["status"],
                            "approved")

    def test_a_refusal_is_recorded_rather_than_only_the_successes(self):
        """The pattern that matters is the attempt, not only the outcome."""
        session = self.signin(REVIEWER)
        status, _, _ = self.decide(session, "uk-digital",
                                   action="not-a-decision")
        self.assertEqual(status, 403)
        mine = [e["action"] for e in self.entries()
                if e["resource_id"] == "uk-digital"]
        self.assertIn("campaign.approval_refused", mine)

    def test_no_secret_or_payload_reaches_the_entry(self):
        session = self.signin(REVIEWER)
        self.decide(session, "dach-software")
        for entry in self.entries():
            blob = str(entry).lower()
            for forbidden in ("token", "secret", "password", "api_key",
                              "bearer"):
                self.assertNotIn(forbidden, blob)

    def test_a_viewer_who_tries_never_gets_as_far_as_the_handler(self):
        """Refused before dispatch, so it is a permission refusal, not an
        approval refusal - and the security trail is where it lands."""
        viewer = self.signin(VIEWER)
        status, _, _ = viewer.post("/approvals/campaign", {
            "csrf": viewer.csrf(), "campaign_id": "dach-software",
            "action": "approve"})
        self.assertEqual(status, 403)
        refusals = [e for e in workspaces.audit(limit=500)
                    if e["action"] == "security.refused"
                    and e["actor"] == VIEWER]
        self.assertTrue(refusals)

    def test_approving_does_not_launch_anything(self):
        """The whole reason the web path passes `reviewer` and not `admin`.

        `roles.REVIEWER` carries APPROVE_CAMPAIGN and REJECT_CAMPAIGN and
        deliberately not LAUNCH_CAMPAIGN. A workspace admin approving a
        campaign needs the first two; handing them the third because of who
        they are would grant the one permission this build exists to withhold.
        """
        from src import roles

        session = self.signin(ADMIN)
        self.decide(session, "dach-software")
        campaign = campaign_store.get("dach-software")
        self.assertEqual(campaign["launch"]["state"], "not_launched")
        self.assertFalse(roles.may(roles.REVIEWER, roles.LAUNCH_CAMPAIGN))

    def test_an_invented_role_is_refused_rather_than_attempted(self):
        from src import orchestrator, roles

        campaign = dict(campaign_store.get("dach-software"))
        with self.assertRaises(roles.NotPermitted):
            orchestrator.decide(campaign, "somebody@x.test", "approve",
                                config={}, recs=[], role="wizard")

    def test_the_entry_shows_up_on_the_audit_screen(self):
        session = self.signin(REVIEWER)
        self.decide(session, "dach-software")
        admin = self.signin(ADMIN)
        _, body, _ = admin.get("/audit")
        self.assertIn("dach-software", body)
        self.assertIn(REVIEWER, body)
