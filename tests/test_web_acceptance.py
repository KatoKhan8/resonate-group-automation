"""The security acceptance list, one test per required property.

`tests/test_web_security.py` is the working security suite and goes deeper on
most of these. This file exists so the acceptance list can be *read* - each
property the build was asked to prove is one named test here, in the order it
was asked for, and a reviewer checking whether a claim is backed can grep for
the claim rather than for the mechanism.

Everything runs against a real server over real HTTP with a real demo estate.
Nothing here mocks a permission check.
"""
import re

from src import campaigns as campaign_store
from src import store, workspaces
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
BOTH = "ops@contactout.test"       # operator in one workspace, reviewer in another


class Acceptance(WebTest):

    # ---------------------------------------------------------------- 1

    def test_01_a_user_may_belong_to_more_than_one_workspace(self):
        mine = workspaces.workspaces_for(BOTH)
        self.assertGreaterEqual(len(mine), 2)

        session = self.signin(BOTH)
        seen = set()
        for space in mine:
            self.switch(session, space["slug"])
            _, body, _ = session.get("/")
            seen.add(space["slug"])
            self.assertEqual(session.get("/")[0], 200)
        self.assertGreaterEqual(len(seen), 2)

    def test_01b_the_role_follows_the_workspace_not_the_person(self):
        """The same account, two roles, resolved per request."""
        roles = {m["workspace"]: m["role"]
                 for m in workspaces.memberships(email=BOTH)}
        self.assertEqual(len(set(roles.values())), 2, roles)

        session = self.signin(BOTH)
        self.switch(session, "contactout")
        self.assertEqual(session.get("/upload")[0], 200)   # operator
        self.switch(session, "productive")
        self.assertEqual(session.get("/upload")[0], 403)   # reviewer

    # ---------------------------------------------------------------- 2

    def test_02_a_viewer_cannot_approve(self):
        viewer = self.signin(VIEWER)
        self.assertEqual(viewer.get("/approvals")[0], 403)

        before = campaign_store.get("dach-software")
        status, _, _ = viewer.post("/approvals/campaign", {
            "csrf": viewer.csrf(), "campaign_id": "dach-software",
            "action": "approve", "fingerprint": before.get("fingerprint") or ""})
        self.assertEqual(status, 403)
        self.assertEqual(campaign_store.get("dach-software").get("approval"),
                         before.get("approval"))

    # ---------------------------------------------------------------- 3

    def test_03_a_reviewer_cannot_administer_users(self):
        reviewer = self.signin(REVIEWER)
        self.assertEqual(reviewer.get("/users")[0], 403)

        status, _, _ = reviewer.post("/users/add", {
            "csrf": reviewer.csrf(), "email": OPERATOR,
            "role": workspaces.WORKSPACE_ADMIN})
        self.assertEqual(status, 403)
        self.assertEqual(
            workspaces.membership_of(OPERATOR, "productive")["role"],
            workspaces.OPERATOR)

    # ---------------------------------------------------------------- 4

    def test_04_an_operator_cannot_administer_workspace_permissions(self):
        operator = self.signin(OPERATOR)
        self.assertEqual(operator.get("/users")[0], 403)

        status, _, _ = operator.post("/users/role", {
            "csrf": operator.csrf(), "email": OPERATOR,
            "role": workspaces.WORKSPACE_ADMIN})
        self.assertEqual(status, 403)
        self.assertEqual(
            workspaces.membership_of(OPERATOR, "productive")["role"],
            workspaces.OPERATOR)

    def test_04b_an_operator_cannot_change_workspace_policy(self):
        operator = self.signin(OPERATOR)
        before = dict(workspaces.policy("productive"))
        status, _, _ = operator.post("/settings/policy", {
            "csrf": operator.csrf("/settings"),
            "policy:market.size_min_employees": "1"})
        self.assertEqual(status, 403)
        self.assertNotIn("market.size_min_employees",
                         workspaces.policy("productive"))
        self.assertEqual(workspaces.policy("productive"), before)

    # ---------------------------------------------------------------- 5

    def test_05_a_workspace_admin_cannot_reach_another_workspace(self):
        admin = self.signin(ADMIN)
        status, body, _ = admin.post("/select-workspace", {
            "csrf": admin.csrf(), "workspace": "contactout"})
        self.assertEqual(status, 404)

        _, body, _ = admin.get("/companies")
        for rec in store.load():
            if rec.get("client") != "productive":
                self.assertNotIn(rec["id"], body)

    # -------------------------------------------------------------- 6-9

    def forged(self, session, path):
        status, body, _ = session.get(path)
        self.assertEqual(status, 404, path)
        return body

    def test_06_a_forged_campaign_id_cannot_cross_a_workspace(self):
        session = self.signin(OPERATOR)
        theirs = next(c for c in campaign_store.load()
                      if c.get("client") != "productive")
        body = self.forged(session, f"/campaigns/{theirs['campaign_id']}")
        self.assertNotIn(theirs.get("name") or "", body)

    def test_07_a_forged_company_id_cannot_cross_a_workspace(self):
        session = self.signin(OPERATOR)
        theirs = next(r for r in store.load()
                      if r.get("client") != "productive")
        body = self.forged(session, f"/companies/{theirs['id']}")
        self.assertNotIn(theirs.get("company") or "", body)

    def test_08_a_forged_contact_id_cannot_cross_a_workspace(self):
        session = self.signin(OPERATOR)
        theirs = next(r for r in store.load()
                      if r.get("client") != "productive" and r.get("contacts"))
        key = theirs["contacts"][0]["key"]
        self.forged(session, f"/contacts/{theirs['id']}/{key}")

    def test_09_a_forged_batch_id_cannot_cross_a_workspace(self):
        """A batch is not a row, so it cannot 404 the way a record does.

        What it must do instead is answer with *nothing* - a batch that
        belongs to somebody else has no records here, and the page has to
        report that rather than counting theirs.
        """
        session = self.signin(OPERATOR)
        theirs = {r.get("batch") for r in store.load()
                  if r.get("client") == "contactout"} - {None}
        self.assertTrue(theirs)
        for batch in theirs:
            status, body, _ = session.get(f"/batches/{batch}")
            self.assertEqual(status, 200, batch)
            for rec in store.load():
                if rec.get("client") != "productive":
                    self.assertNotIn(rec["id"], body)
                    self.assertNotIn(rec.get("company") or "\0", body)

    def test_09b_a_forged_batch_id_cannot_be_processed_either(self):
        from src import jobs
        before = [dict(j) for j in jobs.load()]
        try:
            session = self.signin(OPERATOR)
            status, body, _ = session.post("/jobs/run", {
                "csrf": session.csrf("/jobs"), "job_type": jobs.ICP_CLASSIFY,
                "batch": "apac-recruiting"})
            self.assertEqual(status, 400)
            self.assertIn("no records", body)
        finally:
            jobs.save(before)

    # --------------------------------------------------------------- 10

    def test_10_an_export_cannot_cross_a_workspace(self):
        session = self.signin(OPERATOR)
        for path in ("/export/contacts.csv", "/export/analytics.csv",
                     "/export/analytics.json"):
            status, body, _ = session.get(path)
            self.assertEqual(status, 200, path)
            for rec in store.load():
                if rec.get("client") != "productive":
                    self.assertNotIn(rec["id"], body, path)

    def test_10b_a_batch_parameter_cannot_widen_an_export(self):
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/export/contacts.csv?batch=apac-recruiting")
        for rec in store.load():
            if rec.get("client") != "productive":
                self.assertNotIn(rec["id"], body)

    # --------------------------------------------------------------- 11

    def test_11_a_super_admin_can_deliberately_inspect_every_workspace(self):
        session = self.signin(SUPER)
        status, body, _ = session.get("/admin")
        self.assertEqual(status, 200)
        for slug in ("productive", "contactout", "demo-client"):
            self.assertIn(slug, body)

    def test_11b_scope_all_is_the_super_admin_check_not_the_parameter(self):
        """An operator may type `?scope=all`. It widens nothing.

        Asserted on the *workspace column* rather than on whether some string
        appears anywhere: a person who is a member of two workspaces shows up
        in both audit logs legitimately, and a test that flagged that would be
        flagging correct behaviour.
        """
        operator = self.signin(OPERATOR)
        status, body, _ = operator.get("/audit?scope=all")
        self.assertEqual(status, 200)
        cells = re.findall(r'<td class="small">([a-z0-9_-]+)</td>', body)
        self.assertTrue(cells, "the audit log rendered no workspace column")
        self.assertEqual(set(cells), {"productive"},
                         "scope=all widened an operator's audit log")

        session = self.signin(SUPER)
        status, wide, _ = session.get("/audit?scope=all")
        self.assertEqual(status, 200)
        wide_cells = set(re.findall(r'<td class="small">([a-z0-9_-]+)</td>',
                                    wide))
        self.assertGreater(len(wide_cells), 1,
                           "a super admin did not get every workspace")

    # --------------------------------------------------------------- 12

    def test_12_no_provider_secret_reaches_a_browser_response(self):
        import os
        canary = "acceptance-canary-never-render-this"
        from src.web import security as web_security
        previous = {}
        for name in web_security.SECRET_ENV:
            previous[name] = os.environ.get(name)
            os.environ[name] = canary
        try:
            session = self.signin(ADMIN)
            for path in ("/", "/settings", "/campaigns", "/outreach",
                         "/replies", "/diagnostics", "/reporting", "/jobs"):
                _, body, _ = session.get(path)
                self.assertNotIn(canary, body, path)
            _, body, _ = self.signin(SUPER).get("/admin")
            self.assertNotIn(canary, body)
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    # --------------------------------------------------------------- 13

    CLIENT_MUST_NOT_SEE = ("contactout", "reoon", "deliverable", "apify",
                           "emailbison", "heyreach", "proofpoint", "mimecast",
                           "barracuda", "credit")

    def test_13_a_client_facing_report_hides_the_operational_stack(self):
        viewer = self.signin(VIEWER)
        for path in ("/", "/reporting"):
            status, body, _ = viewer.get(path)
            self.assertEqual(status, 200, path)
            lowered = body.lower()
            for vendor in self.CLIENT_MUST_NOT_SEE:
                self.assertNotIn(vendor, lowered,
                                 f"{path} names {vendor} to a client")

    def test_13b_a_hand_typed_dimension_does_not_reach_the_vendor_list(self):
        """Narrowed on the server, not hidden in the template."""
        viewer = self.signin(VIEWER)
        for dimension in ("mx_provider", "mx_category", "email_source",
                          "verifier"):
            status, body, _ = viewer.get(f"/reporting?dimension={dimension}")
            self.assertEqual(status, 200, dimension)
            self.assertNotIn("proofpoint", body.lower(), dimension)
            self.assertNotIn("contactout", body.lower(), dimension)

    def test_13c_a_client_cannot_reach_the_operational_screens_at_all(self):
        viewer = self.signin(VIEWER)
        for path in ("/companies", "/contacts", "/campaigns", "/outreach",
                     "/jobs", "/settings", "/diagnostics", "/icp",
                     "/campaigns/new", "/replies", "/approvals", "/batches",
                     "/upload", "/simulator", "/timezones", "/audit"):
            self.assertEqual(viewer.get(path)[0], 403, path)

    # --------------------------------------------------------------- 14

    def test_14_a_direct_api_call_cannot_bypass_a_permission(self):
        """Every mutation, posted by somebody whose role does not carry it."""
        viewer = self.signin(VIEWER)
        token = viewer.csrf()
        for path, fields in (
                ("/icp/decide", {"record_id": "x", "decision": "accept"}),
                ("/campaigns/create", {"segment_key": "x", "name": "x"}),
                ("/campaigns/pause", {"campaign_id": "uk-digital"}),
                ("/campaigns/resume", {"campaign_id": "uk-digital"}),
                ("/jobs/run", {"job_type": "icp_classify", "batch": "x"}),
                ("/jobs/cancel", {"job_id": "x"}),
                ("/replies/handle", {"record_id": "x", "contact_key": "y",
                                     "at": "z"}),
                ("/settings/policy", {"policy:market.size_min_employees": "1"}),
                ("/settings/mapping", {"campaign_id": "uk-digital"}),
                ("/users/add", {"email": OPERATOR, "role": "viewer"}),
                ("/users/role", {"email": OPERATOR, "role": "viewer"}),
                ("/upload/commit", {}),
                ("/approvals/campaign", {"campaign_id": "uk-digital"})):
            status, _, _ = viewer.post(path, dict(fields, csrf=token))
            self.assertEqual(status, 403, f"{path} let a viewer through")

    # --------------------------------------------------------------- 15

    def test_15_a_role_supplied_by_the_browser_is_not_trusted(self):
        viewer = self.signin(VIEWER)
        status, _, _ = viewer.post("/select-workspace", {
            "csrf": viewer.csrf(), "workspace": "productive",
            "role": "super_admin"})
        self.assertEqual(status, 200)
        self.assertEqual(
            workspaces.membership_of(VIEWER, "productive")["role"],
            workspaces.VIEWER)
        self.assertEqual(viewer.get("/companies")[0], 403)

    def test_15b_a_workspace_supplied_by_the_browser_is_checked(self):
        viewer = self.signin(VIEWER)
        status, _, _ = viewer.post("/select-workspace", {
            "csrf": viewer.csrf(), "workspace": "contactout"})
        self.assertEqual(status, 404)

    def test_15c_a_server_decided_verdict_in_a_request_is_refused(self):
        """Refused, not sanitised: a 200 would teach the caller a falsehood."""
        operator = self.signin(OPERATOR)
        for field in ("sendable", "approved", "eligible", "verified",
                      "verdict", "state", "live"):
            status, body, _ = operator.post("/select-workspace", {
                "csrf": operator.csrf(), "workspace": "productive",
                field: "true"})
            self.assertEqual(status, 403, field)
            self.assertIn("decided by the server", body, field)

    def test_15d_the_session_carries_no_role_at_all(self):
        from src.web import app
        for entry in app.STATE["sessions"]._by_token.values():
            self.assertNotIn("role", entry)
            self.assertNotIn("permissions", entry)
            self.assertEqual(sorted(entry),
                             ["created_at", "csrf", "email", "seen_at",
                              "workspace"])
