"""The security acceptance tests for the web application.

Fourteen named properties, each one a sentence somebody could disagree with.
They are written against the running server rather than against the functions
underneath it, because "the repository refuses" and "the URL refuses" are
different claims and only the second one is the product.

The shape of the argument throughout: **a workspace is a boundary, not a
filter.** A filter is something a handler applies and can therefore forget. A
boundary is something a handler cannot reach past because it was handed a
scoped object with no unscoped call on it. Several of these tests exist
specifically to fail if somebody later adds one.
"""
import json
import os
import urllib.error

from src import store, workspaces
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
ADMIN = "admin@productive.test"
OTHER_OPERATOR = "ops@contactout.test"
SUPER = "root@resonate.test"

# A value planted into every credential variable, then hunted for in every
# rendered byte. Distinctive enough that a match cannot be a coincidence.
CANARY = "CANARY-SECRET-6f2a1d9c"


class TenancyBoundary(WebTest):
    """1-5: another workspace's data is unreachable by URL."""

    def test_1_cross_workspace_record_is_not_found(self):
        """A real record id from another workspace answers 404, not 403.

        404 rather than 403 on purpose. "That exists but is not yours" is a
        disclosure: it confirms an id, and ids in this system carry a company.
        A forged id and a real one belonging to somebody else must be
        indistinguishable from outside.
        """
        other = self.a_record("contactout")["id"]
        session = self.signin(OPERATOR)
        status, _, _ = session.get(f"/companies/{other}")
        self.assertEqual(status, 404)

    def test_2_cross_workspace_contact_is_not_found(self):
        other = next(r for r in self.records_of("contactout") if r["contacts"])
        key = other["contacts"][0]["key"]
        session = self.signin(OPERATOR)
        status, _, _ = session.get(f"/contacts/{other['id']}/{key}")
        self.assertEqual(status, 404)

    def test_3_cross_workspace_campaign_is_not_found(self):
        session = self.signin(OPERATOR)
        status, _, _ = session.get("/campaigns/apac-recruiting")
        self.assertEqual(status, 404)

    def test_4_listing_screens_never_carry_another_workspace(self):
        """Not one row, on any listing, from anywhere else.

        The stronger version of the id test: an operator could be refused every
        individual URL and still be shown the other tenant's companies in a
        table. Every domain on every listing is checked against the set that
        belongs to somebody else.
        """
        foreign = {r["domain"] for r in store.load()
                   if r.get("client") != "productive"}
        self.assertTrue(foreign)
        session = self.signin(OPERATOR)
        for path in ("/", "/batches", "/companies", "/segments", "/contacts",
                     "/campaigns", "/approvals", "/replies", "/reporting",
                     "/compare", "/audit", "/diagnostics"):
            status, body, _ = session.get(path)
            self.assertEqual(status, 200, path)
            leaked = sorted(d for d in foreign if d and d in body)
            self.assertEqual(leaked, [], f"{path} leaked {leaked}")

    def test_5_switching_to_a_workspace_you_are_not_in_is_refused(self):
        """And refused at the point of the switch, not filtered afterwards."""
        session = self.signin(OPERATOR)
        status, _, _ = session.post("/select-workspace",
                                    {"csrf": session.csrf(),
                                     "workspace": "contactout"})
        self.assertEqual(status, 404)
        # The session is unchanged, so the next read is still the old tenant.
        _, body, _ = session.get("/companies")
        self.assertIn("uk-digital", body)


class Permissions(WebTest):
    """6-9: what a role may do is decided on the server, every request."""

    def tearDown(self):
        # Any test here that moves somebody's role puts it back, because the
        # estate is built once for the class.
        workspaces.assign(REVIEWER, "productive", workspaces.REVIEWER,
                          actor="test-teardown")

    def test_6_permission_is_enforced_by_the_handler_not_the_menu(self):
        """A viewer that types the URL is refused the same as one that cannot
        see the link. The nav is a courtesy; the check is at the boundary."""
        session = self.signin(VIEWER)
        _, shell, _ = session.get("/")
        self.assertNotIn('href="/contacts"', shell)
        for path in ("/contacts", "/companies", "/campaigns", "/replies",
                     "/diagnostics", "/settings", "/batches", "/upload"):
            status, _, _ = session.get(path)
            self.assertEqual(status, 403, f"{path} should be refused")

    def test_7_a_revoked_role_stops_working_immediately(self):
        """No re-login required, because no role is cached in the session.

        A role in a session is a role that keeps working after somebody removed
        it. This test is the reason `Sessions.create` stores an email and a
        workspace and nothing else.
        """
        session = self.signin(REVIEWER)
        self.assertEqual(session.get("/approvals")[0], 200)
        workspaces.assign(REVIEWER, "productive", workspaces.VIEWER,
                          actor="test")
        self.assertEqual(session.get("/approvals")[0], 403)
        workspaces.assign(REVIEWER, "productive", workspaces.REVIEWER,
                          actor="test")
        self.assertEqual(session.get("/approvals")[0], 200)

    def test_8_the_role_never_comes_from_the_browser(self):
        """Sending a role with the sign-in form does not grant it."""
        from tests.webbase import Session
        session = Session(self.base, VIEWER)
        session.post("/login", {"email": VIEWER, "role": workspaces.SUPER_ADMIN,
                                "super_admin": "true"})
        self.assertEqual(session.get("/admin")[0], 404)
        self.assertEqual(session.get("/contacts")[0], 403)

    def test_9_a_workspace_admin_cannot_mint_a_super_admin(self):
        """Super admin is an account-level fact, not a role handed out inside
        a workspace. Otherwise every workspace admin is a super admin."""
        session = self.signin(ADMIN)
        status, body, _ = session.post("/users/role",
                                       {"csrf": session.csrf("/users"),
                                        "email": OPERATOR,
                                        "role": workspaces.SUPER_ADMIN})
        self.assertEqual(status, 403)
        self.assertEqual(
            workspaces.membership_of(OPERATOR, "productive")["role"],
            workspaces.OPERATOR)


class TheGlobalOverviewIsAlsoAClientScreen(WebTest):
    """`/global` is reachable on `workspace.view`, which a client has.

    The workspace dashboard already declines to show a client the machine -
    no batches, no jobs, no Slack posting row. This screen did not, so the
    same person met a client-safe `/` and a `/global` reporting our inbox
    count, our failed jobs and our credit spend.
    """

    MACHINE = ("failed jobs", "credits", "Sender infrastructure", "inboxes")

    def test_a_client_is_not_shown_how_the_machine_is_running(self):
        _, body, _ = self.signin(VIEWER).get("/global")
        for phrase in self.MACHINE:
            self.assertNotIn(phrase, body, phrase)

    def test_an_operator_still_is(self):
        """Hiding it from everybody would be a different bug."""
        _, body, _ = self.signin(OPERATOR).get("/global")
        for phrase in self.MACHINE:
            self.assertIn(phrase, body, phrase)

    def test_the_outcome_numbers_are_still_there_for_the_client(self):
        _, body, _ = self.signin(VIEWER).get("/global")
        for phrase in ("companies", "contacts", "replies", "positive"):
            self.assertIn(phrase, body, phrase)


class TheUserDirectory(WebTest):
    """A workspace admin manages their workspace, not the address book."""

    def test_the_users_page_does_not_enumerate_other_workspaces_staff(self):
        """Offering a list of every account is a disclosure with no upside.

        A workspace admin at one tenant should not be able to read off the
        staff of every other tenant from a dropdown. To add somebody you
        already know who they are, so the form takes an address.
        """
        session = self.signin(ADMIN)
        status, body, _ = session.get("/users")
        self.assertEqual(status, 200)
        self.assertIn("ops@productive.test", body)      # a member, shown
        for outsider in ("admin@contactout.test", "ops@demo-client.test",
                         "client@demo-client.test", SUPER):
            self.assertNotIn(outsider, body,
                             f"the users page listed {outsider}")

        # And the service layer's own contract, not only today's template.
        # Nothing renders a directory right now, so a function that quietly
        # started returning one would leak nothing until the next page that
        # loops over it - which is a leak nobody would connect to this change.
        from src import repo as repo_module
        from src.web import api

        data = api.workspace_people(
            repo_module.Repo.for_user(ADMIN, "productive"))
        # Two legitimate categories now: people who are in this workspace,
        # and addresses this workspace has invited and not yet let in. Both
        # are this workspace's own business. What must never appear is an
        # address belonging to any other tenant, which is what the loop
        # below still refuses.
        belongs = {m["email"] for m in data["memberships"]}
        belongs |= {i["email"] for i in data.get("invitations") or []}
        belongs |= {i.get("invited_by") for i in data.get("invitations") or []}
        for value in json.dumps(data).split('"'):
            if "@" in value and value not in belongs:
                self.fail(f"workspace_people carried a non-member: {value}")

        # And the invitations it does carry are this workspace's only.
        for entry in data.get("invitations") or []:
            self.assertEqual(entry["workspace"], "productive")

    def test_a_membership_cannot_be_created_for_somebody_who_does_not_exist(self):
        """A row pointing at nobody grants a permission to whoever registers
        that address next.

        The property is unchanged; what changed is what the form does
        instead of refusing. Adding an address nobody has signed in with
        creates an *invitation*, which grants nothing and is read only by
        the OAuth callback after an identity provider has proved that exact
        address. This used to assert the 400 - the symptom - and would have
        gone on passing if a later change had started writing a membership
        while still returning one.
        """
        session = self.signin(ADMIN)
        status, body, _ = session.post("/users/add",
                                       {"csrf": session.csrf("/users"),
                                        "email": "ghost@nowhere.test",
                                        "role": workspaces.OPERATOR})

        # No membership, no user, no permission - which is the whole claim.
        self.assertIsNone(
            workspaces.membership_of("ghost@nowhere.test", "productive"))
        self.assertIsNone(workspaces.user("ghost@nowhere.test"))
        self.assertEqual(
            workspaces.workspaces_for("ghost@nowhere.test"), [])

        # What it did do instead, and only that.
        pending = workspaces.invitations(workspace_slug="productive",
                                         email="ghost@nowhere.test",
                                         status=workspaces.PENDING)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["role"], workspaces.OPERATOR)

    def test_typing_an_invited_address_into_the_demo_form_grants_nothing(self):
        """An invitation is consumed by a *proved* address and nothing else.

        This file runs the demo mechanism - no identity provider - which is
        the one place the question can be asked. `_establish` takes an
        explicit `proved` flag, and only `/auth/callback` sets it; if that
        flag were dropped, typing an invited address into a form would
        create the user and hand over the role an administrator meant for
        somebody who can prove they own the mailbox.

        The mutation audit found this gap by deleting that flag and
        watching every other test stay green.
        """
        invited = "invited.but.unproved@productive.test"
        workspaces.invite(invited, "productive", workspaces.WORKSPACE_ADMIN,
                          actor=ADMIN)
        try:
            session = self.anonymous()
            status, _, _ = session.post("/login", {"email": invited})

            # The demo form answers 200 on success and 400 when it refuses.
            self.assertNotEqual(status, 200, "the form let an invitee in")
            self.assertIsNone(workspaces.user(invited))
            self.assertIsNone(workspaces.membership_of(invited, "productive"))
            # And the invitation is still waiting for somebody who can prove
            # the address, rather than having been spent by a form.
            self.assertEqual(
                len(workspaces.invitations(email=invited,
                                           status=workspaces.PENDING)), 1)
        finally:
            rows = [r for r in workspaces.load()
                    if not (r.get("kind") in ("invitation", "user",
                                              "membership")
                            and r.get("email") == invited)]
            workspaces.save(rows)

    def test_an_admin_can_still_add_and_move_a_real_user(self):
        session = self.signin(ADMIN)
        try:
            session.post("/users/add", {"csrf": session.csrf("/users"),
                                        "email": "ops@demo-client.test",
                                        "role": workspaces.REVIEWER})
            self.assertEqual(
                workspaces.membership_of("ops@demo-client.test",
                                         "productive")["role"],
                workspaces.REVIEWER)
        finally:
            workspaces.remove("ops@demo-client.test", "productive",
                              actor="test-teardown")


class Exports(WebTest):
    """10-11: exports are permissioned and never cross a workspace."""

    def test_10_export_requires_the_export_permission(self):
        for email, expected in ((OPERATOR, 200), (REVIEWER, 403),
                                (VIEWER, 403)):
            session = self.signin(email)
            self.assertEqual(session.get("/export/contacts.csv")[0], expected,
                             email)
            self.assertEqual(session.get("/export/analytics.csv")[0], expected,
                             email)

    def test_10b_an_export_guards_a_cell_that_would_execute(self):
        """With a value that actually needs guarding.

        Checking a clean export for unguarded formulas proves nothing: there
        were none to guard. This plants one in a field that reaches the CSV -
        a prospect's job title, which arrives from a provider and is exactly
        the kind of field an attacker can choose - and asserts it comes back
        prefixed. The mutation audit found this hole too.
        """
        recs = store.load()
        target = next(r for r in recs
                      if r["client"] == "productive" and r.get("contacts"))
        original = target["contacts"][0].get("title")
        target["contacts"][0]["title"] = '=cmd|\'/c calc\'!A1'
        store.save(recs)
        try:
            session = self.signin(OPERATOR)
            status, body, _ = session.get("/export/contacts.csv")
            self.assertEqual(status, 200)
            self.assertNotIn(",=cmd", body)
            self.assertIn("'=cmd", body)
        finally:
            recs = store.load()
            for rec in recs:
                if rec["id"] == target["id"]:
                    rec["contacts"][0]["title"] = original
            store.save(recs)

    def test_11_an_export_contains_only_this_workspace(self):
        """And carries the CSV formula guard the CLI export uses."""
        session = self.signin(OPERATOR)
        status, body, headers = session.get("/export/contacts.csv")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers.get("Content-Disposition", ""))
        for rec in store.load():
            if rec.get("client") != "productive":
                self.assertNotIn(rec["domain"], body)
        # Every cell that could be read as a formula is prefixed. The web
        # export goes through `export.to_csv`, which is `write_csv` minus the
        # file handle - one guard, not two.
        for line in body.splitlines()[1:]:
            for cell in line.split(","):
                bare = cell.strip('"')
                self.assertFalse(bare[:1] in ("=", "+", "@"),
                                 f"unguarded formula cell: {cell!r}")


class Secrets(WebTest):
    """12: no credential reaches a browser, from any screen."""

    def test_12_no_secret_appears_in_any_rendered_byte(self):
        planted = {}
        from src.web import security
        for name in security.SECRET_ENV:
            planted[name] = os.environ.get(name)
            os.environ[name] = CANARY
        try:
            for email in (SUPER, ADMIN, OPERATOR, REVIEWER, VIEWER):
                session = self.signin(email)
                for path in ("/", "/settings", "/diagnostics", "/admin",
                             "/audit", "/reporting", "/campaigns", "/replies",
                             "/workspaces", "/users"):
                    status, body, _ = session.get(path)
                    self.assertNotIn(CANARY, body,
                                     f"{email} saw a secret on {path}")
        finally:
            for name, value in planted.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_12b_credential_status_reports_presence_and_never_a_value(self):
        """The contract of the function, not only of the page that calls it.

        Walking every screen for a canary proves no *current* page prints a
        credential. It does not stop `credential_status()` from starting to
        return values, because today no template renders them - the leak would
        arrive with whichever page renders that dict next. The mutation audit
        found exactly this hole: swapping `configured(name)` for
        `os.environ.get(name)` changed nothing that any test could see.

        So the contract is asserted where it lives: this function answers
        `True` or `False`, and nothing else, whatever the environment holds.
        """
        from src.web import api, security

        planted = {}
        for name in security.SECRET_ENV:
            planted[name] = os.environ.get(name)
            os.environ[name] = CANARY
        try:
            status = security.credential_status()
            self.assertEqual(sorted(status), sorted(security.SECRET_ENV))
            for name, value in status.items():
                self.assertIsInstance(value, bool, name)

            # And through both service functions that hand it onwards.
            from src import repo as repo_module
            repo = repo_module.Repo.for_user(OPERATOR, "productive")
            for source in (api.diagnostics(repo)["credentials"],
                           api.admin_overview()["credentials"]):
                for name, value in source.items():
                    self.assertIsInstance(value, bool, name)
                self.assertNotIn(CANARY, json.dumps(source))
        finally:
            for name, value in planted.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_13_the_audit_log_records_who_and_what_and_no_secret(self):
        """An audit trail that carries payloads is a second copy of the data.

        Entries carry an actor, a workspace, an action, an identifier and a
        before/after - never message bodies, provider payloads or credentials.
        """
        session = self.signin(OPERATOR)
        session.get("/export/contacts.csv")
        entries = workspaces.audit(workspace_slug="productive")
        exported = [e for e in entries if e["action"] == "export.contacts"]
        self.assertTrue(exported, "an export must be recorded")
        self.assertEqual(exported[0]["actor"], OPERATOR)
        self.assertEqual(exported[0]["workspace"], "productive")
        blob = json.dumps(entries)
        for forbidden in ("password", "token", "Bearer ", CANARY):
            self.assertNotIn(forbidden, blob)


class ClientSuppliedVerdicts(WebTest):
    """14: the browser cannot decide anything the server decides."""

    def test_14_a_request_carrying_a_verdict_is_refused_not_ignored(self):
        """Refused, so a caller who sent it learns that it did not work.

        Silently ignoring `sendable=true` is worse than refusing it: the sender
        gets a 200 and believes something about this system that is false.
        """
        session = self.signin(OPERATOR)
        for field in ("sendable", "approved", "eligible", "verified",
                      "email_eligible", "would_send", "live"):
            status, body, _ = session.post(
                "/select-workspace",
                {"csrf": session.csrf(), "workspace": "productive",
                 field: "true"})
            self.assertEqual(status, 403, field)
            self.assertIn("decided by the server", body)


class Csrf(WebTest):
    """Every mutation needs the session's token, compared in constant time."""

    def test_a_post_without_a_token_is_refused(self):
        session = self.signin(OPERATOR)
        status, _, _ = session.post("/select-workspace",
                                    {"workspace": "productive"})
        self.assertEqual(status, 403)

    def test_a_post_with_another_sessions_token_is_refused(self):
        one = self.signin(OPERATOR)
        two = self.signin(ADMIN)
        status, _, _ = one.post("/select-workspace",
                                {"csrf": two.csrf(), "workspace": "productive"})
        self.assertEqual(status, 403)


class SuperAdmin(WebTest):
    """The one deliberate way across the boundary, and it is recorded."""

    def test_a_super_admin_sees_every_workspace(self):
        session = self.signin(SUPER)
        status, body, _ = session.get("/admin")
        self.assertEqual(status, 200)
        for slug in ("productive", "contactout", "demo-client"):
            self.assertIn(slug, body)

    def test_a_super_admin_crossing_is_attributed_to_super_admin(self):
        membership = workspaces.membership_of(SUPER, "contactout")
        self.assertEqual(membership["role"], workspaces.SUPER_ADMIN)
        self.assertEqual(membership["via"], "super_admin")

    def test_scope_all_on_the_audit_log_needs_a_super_admin_not_a_parameter(self):
        """A query parameter that widens a scope on its own is the bug.

        The operator asks for every workspace and gets their own; the super
        admin asks and gets all of them. Same URL, different answer, decided
        on the server.
        """
        import re

        def workspaces_shown(body):
            table = re.search(r'<table id="audit">.*?</table>', body, re.S)
            self.assertIsNotNone(table, "no audit table rendered")
            # The third cell of each row is the workspace. Matching on the
            # column rather than on the whole page, because `ops@contactout
            # .test` is a *member of productive* and their address is not a
            # cross-tenant leak.
            return set(re.findall(r"<td class=\"small\">([a-z0-9-]+)</td>",
                                  table.group(0)))

        operator = self.signin(OPERATOR)
        _, body, _ = operator.get("/audit?scope=all")
        self.assertEqual(workspaces_shown(body), {"productive"})

        root = self.signin(SUPER)
        _, body, _ = root.get("/audit?scope=all")
        self.assertEqual(workspaces_shown(body),
                         {"productive", "contactout", "demo-client"})

    def test_admin_is_not_found_rather_than_forbidden(self):
        """A workspace user should not learn that an admin console exists."""
        for email in (ADMIN, OPERATOR, REVIEWER, VIEWER):
            session = self.signin(email)
            self.assertEqual(session.get("/admin")[0], 404, email)



class WriteEndpointsAreGuardedToo(WebTest):
    """A permission on the GET and none on the POST is not a permission.

    `permission_for` runs on the read side. Every write route therefore
    carries its own check, and these are the ones written from outside,
    because "the handler asks" and "the URL refuses" are different claims
    and only the second is the product.
    """

    def _multipart(self, fields, content, filename="probe.csv"):
        boundary = "----rga-test-boundary"
        parts = []
        for key, value in fields.items():
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f"{value}\r\n")
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="csv"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: text/csv\r\n\r\n{content}\r\n")
        parts.append(f"--{boundary}--\r\n")
        return ("".join(parts).encode(),
                f"multipart/form-data; boundary={boundary}")

    def _upload_as(self, email):
        import urllib.request

        session = self.signin(email)
        body, content_type = self._multipart(
            {"csrf": session.csrf("/") or "", "batch": "probe"},
            "company,domain\nProbe Ltd,probe-not-a-real-domain.test\n")
        request = urllib.request.Request(
            self.base + "/upload", data=body,
            headers={"Content-Type": content_type})
        try:
            with session.opener.open(request, timeout=30) as response:
                return response.status, response.read().decode(
                    "utf-8", "replace")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8", "replace")

    def test_a_viewer_cannot_parse_a_csv_through_the_upload_post(self):
        """This one was real.

        The CSV preview answers "have we seen these domains before" by
        reading this workspace's records: how many are suppressed, how
        many already exist, how many were previously engaged. The GET was
        403 for a viewer and the POST was 200, which made it an oracle -
        a client-facing role could learn the shape of the outreach
        history one upload at a time, without ever committing anything.
        """
        self.assertEqual(self.signin(VIEWER).get("/upload")[0], 403)
        status, body = self._upload_as(VIEWER)
        self.assertEqual(status, 403, "POST /upload must refuse a viewer")
        for leak in ("already exist", "suppressed", "cold-eligible"):
            self.assertNotIn(leak, body)

    def test_a_reviewer_cannot_either(self):
        self.assertEqual(self._upload_as(REVIEWER)[0], 403)

    def test_an_operator_still_can(self):
        """The guard has to stop the right people and nobody else."""
        status, body = self._upload_as(OPERATOR)
        self.assertEqual(status, 200)
        self.assertIn("Parsed, nothing committed", body)

    def test_a_viewer_cannot_record_a_signal(self):
        session = self.signin(VIEWER)
        status, _, _ = session.post("/signals", {
            "csrf": session.csrf("/") or "",
            "record_id": self.a_record("productive")["id"],
            "type": "hiring_surge",
            "evidence": "7 open delivery roles on the careers page"})
        self.assertEqual(status, 403)

    def test_a_reviewer_can_read_signals_but_not_write_one(self):
        """The two halves of the same permission line."""
        session = self.signin(REVIEWER)
        self.assertEqual(session.get("/signals")[0], 200)
        status, _, _ = session.post("/signals", {
            "csrf": session.csrf("/signals") or "",
            "record_id": self.a_record("productive")["id"],
            "type": "funding",
            "evidence": "Series A reported in the trade press"})
        self.assertEqual(status, 403)


class MultipleMemberships(WebTest):
    """One person, two workspaces, two different roles."""

    def test_the_role_follows_the_workspace_not_the_person(self):
        session = self.signin(OTHER_OPERATOR)
        # Signed in to their first workspace: operator in contactout.
        _, body, _ = session.get("/")
        self.assertIn("operator", body)
        self.assertEqual(session.get("/upload")[0], 200)

        self.switch(session, "productive")
        # Same person, same session, reviewer here - so no upload.
        self.assertEqual(session.get("/upload")[0], 403)
        self.assertEqual(session.get("/approvals")[0], 200)


class Headers(WebTest):
    """The response headers that make a rendered page safe to be wrong in."""

    def test_every_page_carries_the_security_headers(self):
        session = self.signin(OPERATOR)
        for path in ("/", "/companies", "/reporting", "/login"):
            _, _, headers = session.get(path)
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(headers.get("X-Frame-Options"), "DENY")
            self.assertIn("default-src 'none'",
                          headers.get("Content-Security-Policy", ""))
            self.assertIn("frame-ancestors 'none'",
                          headers.get("Content-Security-Policy", ""))

    def test_the_session_cookie_is_httponly_and_samesite(self):
        """Read off the 303 itself, not off the page it redirects to.

        `urllib` follows the redirect by default and hands back the final
        response's headers, which do not carry the cookie. A test that looked
        there would pass a build that set no flags at all.
        """
        import urllib.parse
        import urllib.request

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **kw):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        data = urllib.parse.urlencode({"email": OPERATOR}).encode()
        try:
            with opener.open(self.base + "/login", data, timeout=30) as r:
                headers = dict(r.headers)
        except urllib.error.HTTPError as e:
            with e:                     # the 303 is a response; close it
                headers = dict(e.headers)
        cookie = headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Path=/", cookie)

    def test_an_anonymous_request_reaches_no_data(self):
        session = self.anonymous()
        for path in ("/", "/companies", "/admin", "/export/contacts.csv"):
            status, body, _ = session.get(path)
            # Redirected to the sign-in page, and nothing else rendered.
            self.assertIn("Sign in", body)


class Escaping(WebTest):
    """Prospect names and scraped evidence are attacker-controlled text."""

    def test_a_script_tag_in_a_company_name_renders_inert(self):
        recs = store.load()
        target = next(r for r in recs if r["client"] == "productive")
        original = target["company"]
        target["company"] = '<script>alert("xss")</script>'
        store.save(recs)
        try:
            session = self.signin(OPERATOR)
            status, body, _ = session.get("/companies")
            self.assertEqual(status, 200)
            self.assertNotIn('<script>alert("xss")</script>', body)
            self.assertIn("&lt;script&gt;", body)
        finally:
            recs = store.load()
            for rec in recs:
                if rec["id"] == target["id"]:
                    rec["company"] = original
            store.save(recs)


class LiveSending(WebTest):
    """The invariant the whole build is under: nothing sends."""

    def test_health_and_every_screen_say_sending_is_disabled(self):
        session = self.signin(OPERATOR)
        status, body, _ = session.get("/healthz")
        self.assertEqual(json.loads(body)["live_sending"], False)
        for path in ("/", "/campaigns", "/approvals"):
            _, page, _ = session.get(path)
            self.assertIn("Live sending", page)
            self.assertIn("disabled", page)

    def test_no_route_can_launch(self):
        """There is no launch handler, and the nav offers no path to one."""
        session = self.signin(ADMIN)
        for path in ("/launch", "/campaigns/uk-digital/launch", "/send",
                     "/push"):
            status, _, _ = session.get(path)
            self.assertIn(status, (403, 404), path)
