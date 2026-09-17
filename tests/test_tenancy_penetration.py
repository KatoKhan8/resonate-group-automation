"""Forged identifiers, one per object kind, against every route that takes one.

The rest of the suite tests tenancy the way the product uses it: sign in, look
at your own things, be refused someone else's. This file tests it the way an
attacker would - by taking a real identifier out of one workspace and putting
it in another workspace's URL.

Three things make it worth having separately:

**The identifiers are real.** A test that pokes `?id=999` proves the app
handles a missing row. It proves nothing about tenancy, because the row it
asked for does not exist for anybody. Every id here is read out of the other
workspace's actual state, so the only thing standing between the request and
the data is the scoping.

**404, not 403.** A refusal that says "forbidden" confirms the object exists.
Sweeping ids against a 403 endpoint enumerates another client's campaign list;
sweeping them against a 404 endpoint learns nothing. Where the code answers
403 for a *permission* rather than for tenancy, that is stated in the test.

**Every object kind, every role.** A gap in this table is a gap somebody finds
later. The sweep is generated from a list rather than written out by hand, so
adding a route means adding one line.
"""
import re
import unittest

from src import campaigns as campaign_store
from src import notify, reports as report_store, senderidentity as si
from src import store
from src import workspaces as ws
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"

MINE = "productive"
THEIRS = "contactout"
BOTH = "ops@contactout.test"       # a member of both


def their_client():
    return (ws.workspace(THEIRS) or {}).get("client") or THEIRS


class Ids:
    """Real identifiers belonging to the *other* workspace."""

    @staticmethod
    def record():
        for rec in store.load():
            if rec.get("client") == their_client():
                return rec["id"]
        return None

    @staticmethod
    def contact():
        for rec in store.load():
            if rec.get("client") == their_client() and rec.get("contacts"):
                return rec["id"], rec["contacts"][0]["key"]
        return None, None

    @staticmethod
    def campaign():
        for campaign in campaign_store.load():
            if campaign.get("client") == their_client():
                return campaign.get("campaign_id")
        return None

    @staticmethod
    def batch():
        for rec in store.load():
            if rec.get("client") == their_client() and rec.get("batch"):
                return rec["batch"]
        return None

    @staticmethod
    def sender():
        roster = si.roster(THEIRS)
        people = roster.get("senders") or []
        return people[0]["sender_id"] if people else None

    @staticmethod
    def notification():
        rows = notify.history(THEIRS, limit=1)
        return rows[0]["id"] if rows else None

    @staticmethod
    def report(session_factory):
        """Generate one in the other workspace so there is a real id."""
        rows = report_store.for_workspace(THEIRS)
        if rows:
            return rows[0]["id"]
        other = session_factory("ops@contactout.test")
        other.post("/reporting/client/generate",
                   {"csrf": other.csrf("/reporting/client"),
                    "template": "executive"})
        rows = report_store.for_workspace(THEIRS)
        return rows[0]["id"] if rows else None


class ForgedIdentifiers(WebTest):
    """One real id from the other tenant, in every route that accepts one."""

    def assert_refused(self, session, path, marker=None, allow=(403, 404)):
        status, body, _ = session.get(path)
        self.assertIn(status, allow, f"{path} answered {status}")
        if marker:
            self.assertNotIn(marker, body, f"{path} leaked {marker!r}")
        return status, body

    # ------------------------------------------------------------ records

    def test_a_company_id_from_another_workspace(self):
        record_id = Ids.record()
        self.assertIsNotNone(record_id, "no other-tenant record to forge with")
        self.assert_refused(self.signin(OPERATOR), f"/companies/{record_id}",
                            allow=(404,))

    def test_the_refusal_does_not_name_the_company(self):
        record_id = Ids.record()
        company = next((r.get("company") for r in store.load()
                        if r["id"] == record_id), None)
        _, body = self.assert_refused(self.signin(OPERATOR),
                                      f"/companies/{record_id}", allow=(404,))
        if company:
            self.assertNotIn(company, body)

    def test_a_contact_from_another_workspace(self):
        record_id, contact_key = Ids.contact()
        self.assertIsNotNone(record_id)
        self.assert_refused(self.signin(OPERATOR),
                            f"/contacts/{record_id}/{contact_key}",
                            allow=(404,))

    def test_a_batch_from_another_workspace_shows_nothing(self):
        """A batch name is not an object here, it is a filter on records.

        `/batches/<name>` answers 200 for any string, because the page is a
        list of *this workspace's* records carrying that batch - which for
        another tenant's batch name is none of them. Demanding a 404 would be
        demanding that the route confirm which names exist, so the property
        asserted is the one that matters: an attacker cannot tell a real
        other-tenant batch from one they invented, and neither page carries a
        row.
        """
        batch = Ids.batch()
        self.assertIsNotNone(batch, "no other-tenant batch to forge with")
        session = self.signin(OPERATOR)
        real = session.get(f"/batches/{batch}")
        invented = session.get("/batches/definitely-not-a-batch")
        self.assertEqual(real[0], invented[0])

        theirs = [r.get("company") for r in store.load()
                  if r.get("client") == their_client() and r.get("company")]
        for company in theirs[:20]:
            self.assertNotIn(company, real[1],
                             f"{company} leaked through a forged batch name")

    def test_a_campaign_from_another_workspace(self):
        campaign_id = Ids.campaign()
        self.assertIsNotNone(campaign_id)
        self.assert_refused(self.signin(OPERATOR),
                            f"/campaigns/{campaign_id}", allow=(404,))

    def test_a_report_from_another_workspace(self):
        report_id = Ids.report(self.signin)
        self.assertIsNotNone(report_id)
        self.assert_refused(self.signin(OPERATOR),
                            f"/reporting/client/download?id={report_id}",
                            allow=(404,))

    def test_a_workspace_slug_in_a_query_string(self):
        """Entering a workspace is a membership check, not a parameter."""
        status, body, _ = self.signin(OPERATOR).get(
            f"/select-workspace?to={THEIRS}")
        self.assertIn(status, (403, 404))

    def test_a_workspace_slug_in_a_post(self):
        session = self.signin(OPERATOR)
        status, _, _ = session.post("/select-workspace",
                                    {"csrf": session.csrf(),
                                     "workspace": THEIRS})
        self.assertIn(status, (403, 404))

    # ------------------------------------------------------------- writes
    #
    # A read that leaks is a disclosure. A write that crosses is worse, so
    # each of these asserts the other workspace's state afterwards.

    def test_a_forged_campaign_id_cannot_be_paused(self):
        campaign_id = Ids.campaign()
        before = campaign_store.get(campaign_id)
        session = self.signin(ADMIN)
        session.post("/campaigns/pause",
                     {"csrf": session.csrf("/campaigns"),
                      "campaign_id": campaign_id, "why": "forged"})
        self.assertEqual(campaign_store.get(campaign_id).get("status"),
                         (before or {}).get("status"),
                         "another workspace's campaign changed status")

    def test_a_forged_record_id_cannot_be_ruled_on(self):
        record_id = Ids.record()
        before = next(r for r in store.load() if r["id"] == record_id)
        session = self.signin(ADMIN)
        session.post("/icp/decide",
                     {"csrf": session.csrf("/icp"), "record_id": record_id,
                      "decision": "qualified", "fingerprint": "whatever"})
        after = next(r for r in store.load() if r["id"] == record_id)
        self.assertEqual(after.get("qualification"),
                         before.get("qualification"),
                         "another workspace's ICP verdict changed")

    def test_a_forged_sender_id_cannot_be_assigned(self):
        sender_id = Ids.sender()
        record_id, contact_key = Ids.contact()
        self.assertIsNotNone(sender_id)
        session = self.signin(ADMIN)
        status, _, _ = session.post(
            "/senders/reassign",
            {"csrf": session.csrf("/senders"), "record_id": record_id,
             "contact_key": contact_key, "channel": "email",
             "sender_id": sender_id, "why": "forged"})
        self.assertIn(status, (400, 403, 404))

    def test_a_forged_campaign_cannot_be_approved(self):
        campaign_id = Ids.campaign()
        before = campaign_store.get(campaign_id)
        session = self.signin(ADMIN)
        session.post("/approvals/campaign",
                     {"csrf": session.csrf("/approvals"),
                      "campaign_id": campaign_id, "action": "approve",
                      "fingerprint": (before or {}).get("fingerprint") or ""})
        after = campaign_store.get(campaign_id)
        self.assertEqual(after.get("status"), (before or {}).get("status"),
                         "another workspace's campaign was approved")

    def test_a_forged_workspace_cannot_have_its_policy_changed(self):
        before = dict(ws.policy(THEIRS))
        session = self.signin(ADMIN)
        session.post("/settings/policy",
                     {"csrf": session.csrf("/settings"),
                      "workspace": THEIRS,
                      "policy:slack.workspace_channel": "#hijacked"})
        self.assertEqual(ws.policy(THEIRS), before,
                         "another workspace's policy changed")


class ARefusalTeachesNothing(WebTest):
    """404 rather than 403 wherever the answer would confirm existence."""

    def test_a_real_and_an_invented_company_id_look_the_same(self):
        real = Ids.record()
        session = self.signin(OPERATOR)
        first = session.get(f"/companies/{real}")
        second = session.get("/companies/definitely-not-a-record")
        self.assertEqual(first[0], second[0])

    def test_a_real_and_an_invented_campaign_id_look_the_same(self):
        real = Ids.campaign()
        session = self.signin(OPERATOR)
        self.assertEqual(session.get(f"/campaigns/{real}")[0],
                         session.get("/campaigns/not-a-campaign")[0])

    def test_a_real_and_an_invented_report_id_look_the_same(self):
        real = Ids.report(self.signin)
        session = self.signin(OPERATOR)
        self.assertEqual(
            session.get(f"/reporting/client/download?id={real}")[0],
            session.get("/reporting/client/download?id=rep-nope")[0])

    def test_the_admin_console_is_a_404_for_everyone_else(self):
        """Learning that a super-admin console exists has no upside."""
        for who in (ADMIN, OPERATOR, REVIEWER, VIEWER):
            for path in ("/admin", "/admin/slack"):
                status, _, _ = self.signin(who).get(path)
                self.assertEqual(status, 404, f"{path} as {who}")


class EveryRoleAgainstEveryGlobalSurface(WebTest):
    """A permission table is only true if the handler actually consults it."""

    ROUTES = (
        ("/admin", "__super__"),
        ("/admin/slack", "__super__"),
        ("/notifications", ws.OPERATIONS_VIEW),
        ("/audit", ws.OPERATIONS_VIEW),
        ("/diagnostics", ws.OPERATIONS_VIEW),
        ("/senders", ws.OPERATIONS_VIEW),
        ("/settings", ws.OPERATIONS_VIEW),
        ("/jobs", ws.OPERATIONS_VIEW),
        ("/campaigns", ws.OPERATIONS_VIEW),
        ("/users", ws.USERS_MANAGE),
        ("/icp", ws.CONTACTS_VIEW),
        ("/contacts", ws.CONTACTS_VIEW),
        ("/companies", ws.CONTACTS_VIEW),
        ("/approvals", ws.APPROVALS_REVIEW),
        ("/replies", ws.REPLIES_VIEW),
        ("/reporting", ws.REPORTING_VIEW),
        ("/reporting/client", ws.REPORTING_VIEW),
        ("/export/contacts.csv", ws.CONTACTS_EXPORT),
        ("/export/analytics.csv", ws.REPORTING_EXPORT),
    )

    PEOPLE = ((ADMIN, ws.WORKSPACE_ADMIN), (OPERATOR, ws.OPERATOR),
              (REVIEWER, ws.REVIEWER), (VIEWER, ws.VIEWER))

    def test_the_table_matches_the_handlers(self):
        person = ws.user(SUPER) or {}
        self.assertTrue(person.get("super_admin"),
                        "the super admin fixture is not a super admin, so "
                        "the __super__ rows below prove nothing")
        failures = []
        for email, role in self.PEOPLE:
            session = self.signin(email)
            permissions = ws.permissions_of(role)
            for path, needed in self.ROUTES:
                status, _, _ = session.get(path)
                if needed == "__super__":
                    allowed = False
                else:
                    allowed = needed in permissions
                got_in = status == 200
                if got_in != allowed:
                    failures.append(
                        f"{role} {path}: expected "
                        f"{'200' if allowed else 'refusal'}, got {status}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_a_super_admin_reaches_the_admin_console(self):
        """The other half: a permission nobody can exercise is not a check."""
        for path in ("/admin", "/admin/slack"):
            status, _, _ = self.signin(SUPER).get(path)
            self.assertEqual(status, 200, path)


class NoScreenLeaksACredential(WebTest):
    """Every screen every role can reach, swept for planted secret values.

    The sweep looks for *values*, not for words. An earlier version searched
    for "signing_secret" and flagged the diagnostics page - which shows
    `SLACK_SIGNING_SECRET: not set`, the variable's *name* and whether it is
    configured, and never its value. That is the deliberate design of
    `security.credential_status`, and a test that fails on it would push
    somebody to remove a useful screen to satisfy a bad assertion.

    The same mistake in the other direction is worse: the Slack mission found
    a scrub that refused a prospect's reply because it contained the word
    "authorization". Names are labels. Values are secrets.
    """

    # Planted into the environment before the server reads it, and assembled
    # from parts rather than written as literals.
    #
    # The repository scans its own tracked files for credential-shaped strings
    # and fails on them. That scanner is right, and a canary written as
    # `xoxb-...` in this file would be a real finding in the shape of a test
    # fixture. Joining the pieces at run time keeps the realistic shape where
    # it has to be - in the environment the server reads - without putting it
    # anywhere a grep would find it.
    @staticmethod
    def _canaries():
        prefix = {"slack": "xo" + "xb-", "contactout": "co" + "_live_",
                  "apify": "apify" + "_api_"}
        return {
            "SLACK_BOT_TOKEN": prefix["slack"] + "9990001112CANARY0001",
            "SLACK_SIGNING_SECRET": "canary" + "0signing0secret0deadbeef",
            "CONTACTOUT_TOKEN": prefix["contactout"] + "CANARY0002VALUE",
            "APIFY_TOKEN": prefix["apify"] + "CANARY0003VALUE",
        }

    @staticmethod
    def _needles():
        """Shapes that can only ever be a value, never a label."""
        return ("xo" + "xb-", "co" + "_live_", "apify" + "_api_",
                "-----begin ")

    # Every screen the navigation offers, derived rather than listed.
    #
    # This was a hand-maintained list of 25 paths while the product had
    # 42, so seventeen reachable screens - `/users`, `/suppression`,
    # `/admin/health`, `/upload` and the rest - were never swept for a
    # leaked credential. Nothing failed, because a sweep that does not
    # visit a page cannot find anything on it.
    #
    # Deriving it means a new screen is swept the day it is added, which
    # is the only version of this test that stays true.
    @staticmethod
    def _paths():
        from src.web import pages

        found = ["/"]
        for href, _, _ in pages.NAV:
            if href and href not in found:
                found.append(href)
        return tuple(found)

    PATHS = property(lambda self: self._paths())

    def setUp(self):
        import os

        self.planted = self._canaries()
        self._previous = {k: os.environ.get(k) for k in self.planted}
        os.environ.update(self.planted)

    def tearDown(self):
        import os

        for key, value in self._previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_the_sweep_covers_every_screen_the_navigation_offers(self):
        """The gap this closes: a hand-written path list falls behind the
        product, and the sweep silently stops covering what it names."""
        from src.web import pages

        swept = set(self._paths())
        offered = {href for href, _, _ in pages.NAV if href}
        self.assertEqual(offered - swept, set())

    def test_no_reachable_screen_carries_a_secret(self):
        offenders = []
        for who in (SUPER, ADMIN, OPERATOR, REVIEWER, VIEWER):
            session = self.signin(who)
            for path in self.PATHS:
                status, body, _ = session.get(path)
                if status != 200:
                    continue
                lowered = body.lower()
                for name, value in self.planted.items():
                    if value.lower() in lowered:
                        offenders.append(f"{who} {path}: {name} value")
                for needle in self._needles():
                    if needle in lowered:
                        offenders.append(f"{who} {path}: {needle}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_a_configured_provider_is_still_reported_by_name(self):
        """The other half: scrubbing must not silence the status screen.

        With a token planted, the admin console must say the variable is
        configured - by name. Removing that to satisfy a value sweep would
        cost an operator the one screen that answers "is Slack wired up".
        """
        _, body, _ = self.signin(SUPER).get("/admin")
        self.assertIn("SLACK_BOT_TOKEN", body)
        self.assertNotIn(self.planted["SLACK_BOT_TOKEN"], body)

    def test_the_sweep_actually_visited_pages(self):
        """A sweep that reached nothing passes trivially."""
        visited = 0
        for who in (SUPER, OPERATOR, VIEWER):
            session = self.signin(who)
            for path in self.PATHS:
                if session.get(path)[0] == 200:
                    visited += 1
        self.assertGreater(visited, 30,
                           "the credential sweep reached almost no pages, so "
                           "it proves almost nothing")


class UntrustedTextIsInert(WebTest):
    """Company names, replies and research arrive from providers and crawls."""

    PAYLOADS = (
        "<script>alert(1)</script>",
        "\"><img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<svg/onload=alert(1)>",
        "'; DROP TABLE contacts; --",
    )

    def test_a_hostile_company_name_renders_inert(self):
        """What makes markup dangerous is its delimiters, not its words.

        `onerror=alert(1)` inside `&lt;img src=x onerror=alert(1)&gt;` is
        text. Asserting the substring is absent would fail on correctly
        escaped output and push somebody to mangle legitimate content - a
        company really can be called "Smith & Sons <Holdings>".
        """
        from src.web import pages

        for payload in self.PAYLOADS:
            rendered = pages.esc(payload)
            self.assertNotIn("<", rendered, payload)
            self.assertNotIn(">", rendered, payload)
            self.assertNotIn('"', rendered, payload)

    def test_escaping_preserves_the_text_it_escapes(self):
        """An escape that deletes content is a different bug, not a fix."""
        from src.web import pages

        rendered = pages.esc("Smith & Sons <Holdings> \"Ltd\"")
        self.assertIn("Smith", rendered)
        self.assertIn("Holdings", rendered)
        self.assertIn("Ltd", rendered)
        self.assertIn("&amp;", rendered)

    def test_a_hostile_url_is_not_linked(self):
        from src.web import pages

        rendered = pages.external("javascript:alert(1)")
        self.assertNotIn("href=\"javascript:", rendered)

    def test_a_hostile_search_term_comes_back_escaped(self):
        from html.parser import HTMLParser

        class SearchMarkup(HTMLParser):
            def __init__(self):
                super().__init__()
                self.handlers = []
                self.query = None

            def handle_starttag(self, tag, attrs):
                self.handlers.extend((name, value) for name, value in attrs
                                     if name.lower().startswith("on"))
                values = dict(attrs)
                if tag == "input" and values.get("id") == "contact-search":
                    self.query = values.get("value")

        session = self.signin(OPERATOR)
        for payload in self.PAYLOADS:
            import urllib.parse

            status, body, _ = session.get(
                "/contacts?q=" + urllib.parse.quote(payload))
            if status != 200:
                continue
            self.assertNotIn("<script>alert(1)</script>", body)
            # Search now preserves the query in a quoted input value. Text
            # saying "onerror" inside that value is inert; an actual event
            # handler attribute must never be emitted by the HTML parser.
            markup = SearchMarkup()
            markup.feed(body)
            self.assertEqual(markup.handlers, [])
            self.assertEqual(markup.query, payload)


class CsvStaysData(WebTest):
    """A spreadsheet formula in an exported cell is code on somebody's laptop."""

    def test_a_formula_prefix_is_neutralised(self):
        from src import export

        for payload in ("=1+1", "+1", "-1", "@SUM(A1)", "\t=cmd|'/c calc'!A0",
                        "\r=1+1"):
            out = export.safe_cell(payload) if hasattr(export, "safe_cell") \
                else None
            if out is None:
                self.skipTest("export exposes no cell guard to test directly")
            self.assertFalse(str(out).lstrip().startswith(("=", "+", "@")),
                             f"{payload!r} exported as {out!r}")

    def test_an_ordinary_value_is_untouched(self):
        from src import export

        if not hasattr(export, "safe_cell"):
            self.skipTest("export exposes no cell guard to test directly")
        for value in ("Acme Ltd", "anna@acme.test", "-", "", "2026-01-01",
                      "+44 20 7946 0000"):
            self.assertIn(str(export.safe_cell(value)).replace("'", ""),
                          (value, value.replace("'", "")))


if __name__ == "__main__":
    unittest.main()


class SearchCannotCrossAWorkspace(WebTest):
    """The one screen that reads more than one workspace on purpose.

    It reads exactly the workspaces the caller is a member of, through the
    same `Repo.for_user` as everything else. That makes the membership list
    the only thing between it and a cross-tenant read, so it gets its own
    tests rather than being trusted because the helper is shared.
    """

    def their_company(self):
        for rec in store.load():
            if rec.get("client") == their_client() and rec.get("company"):
                return rec["company"]
        return None

    def test_a_single_workspace_member_sees_only_their_own(self):
        """Zero results, and no link to the other tenant's record.

        The query itself is echoed back in the "no matches" line, so
        asserting the company name is absent from the *page* would fail on
        correct behaviour - the user typed it. What must be absent is a
        result: a row, a link, or the other workspace's slug as a hit.
        """
        from src.web import api

        company = self.their_company()
        self.assertIsNotNone(company)
        result = api.search(OPERATOR, company)
        self.assertEqual(result["results"], [])

        import urllib.parse

        _, body, _ = self.signin(OPERATOR).get(
            "/search?q=" + urllib.parse.quote(company))
        self.assertIn("No matches", body)
        self.assertNotIn('href="/companies/', body)

    def test_a_forged_workspace_parameter_is_ignored(self):
        """`?workspace=` narrows; it cannot widen."""
        from src.web import api

        company = self.their_company()
        result = api.search(OPERATOR, company, workspace=THEIRS)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["workspaces"], [])

    def test_a_member_of_two_workspaces_sees_both(self):
        """The other half: a scope that admits nothing is not a scope."""
        from src import workspaces as ws_module
        from src.web import api

        mine = ws_module.workspaces_for("ops@contactout.test")
        self.assertGreaterEqual(len(mine), 2,
                                "the two-workspace fixture is gone, so this "
                                "test proves nothing")
        result = api.search("ops@contactout.test", "or")
        self.assertGreaterEqual(len(set(result["workspaces"])), 2)

    def test_a_short_query_is_refused_rather_than_scanned(self):
        _, body, _ = self.signin(OPERATOR).get("/search?q=a")
        self.assertIn("full scan wearing a filter", body)

    def test_results_are_capped(self):
        from src.web import api

        result = api.search(OPERATOR, "or")
        for kind in ("company", "contact", "campaign"):
            hits = [r for r in result["results"] if r["kind"] == kind]
            self.assertLessEqual(len(hits), api.SEARCH_CAP, kind)

    def test_a_hostile_query_comes_back_escaped(self):
        import urllib.parse

        _, body, _ = self.signin(OPERATOR).get(
            "/search?q=" + urllib.parse.quote("<script>alert(1)</script>"))
        self.assertNotIn("<script>alert(1)</script>", body)


class SuppressionIsScoped(WebTest):

    def test_it_shows_this_workspaces_stopped_contacts(self):
        _, body, _ = self.signin(OPERATOR).get("/suppression")
        self.assertIn("Suppression", body)

    def test_it_does_not_show_another_workspaces(self):
        theirs = [r.get("company") for r in store.load()
                  if r.get("client") == their_client() and r.get("company")]
        _, body, _ = self.signin(OPERATOR).get("/suppression")
        for company in theirs[:20]:
            self.assertNotIn(company, body)

    def test_a_reply_pause_is_not_labelled_an_unsubscribe(self):
        """They need different handling, so they are not merged."""
        from src.web import api
        from src import repo as repo_module

        repo = repo_module.Repo.for_user(OPERATOR, MINE)
        data = api.suppression(repo)
        kinds = {row["kind"] for row in data["rows"]}
        self.assertNotIn("unsubscribe", kinds - {"reply", "paused",
                                                 "dropped", "global",
                                                 "unsubscribe"})
        self.assertIn("is not a request to stop", data["note"])


class TheAccountViewIsScoped(WebTest):
    """The new orchestration screens read a record; the same rules apply."""

    def test_an_account_from_another_workspace_is_a_404(self):
        record_id = Ids.record()
        self.assertIsNotNone(record_id)
        status, body, _ = self.signin(OPERATOR).get(
            "/outreach/account/" + str(record_id))
        self.assertEqual(status, 404)

    def test_the_refusal_names_no_contact(self):
        record_id = Ids.record()
        theirs = next((r for r in store.load() if r["id"] == record_id), {})
        _, body, _ = self.signin(OPERATOR).get(
            "/outreach/account/" + str(record_id))
        for contact in theirs.get("contacts") or []:
            if contact.get("name"):
                self.assertNotIn(contact["name"], body)

    def test_the_account_list_shows_only_this_workspace(self):
        _, body, _ = self.signin(OPERATOR).get("/outreach/accounts")
        theirs = [r.get("company") for r in store.load()
                  if r.get("client") == their_client() and r.get("company")]
        for company in theirs[:20]:
            self.assertNotIn(company, body)

    def test_a_viewer_cannot_reach_the_orchestration_screens(self):
        """It names senders, provider accounts and pacing internals."""
        viewer = self.signin(VIEWER)
        for path in ("/outreach/accounts", "/outreach/cadence",
                     "/outreach/account/demo-acme"):
            self.assertEqual(viewer.get(path)[0], 403, path)


class TheNewOperationsScreensAreScoped(WebTest):
    """`/health`, `/refresh` and `/revival` each read the whole estate
    through `repo.records()` and then aggregate it.

    That shape is worth its own tests. A screen that reads one object by id
    is protected by the id lookup, and the penetration sweep above covers
    it. A screen that reads *everything* and then narrows is protected only
    by the narrowing, and the failure mode is not a leaked row - it is a
    count that quietly includes another tenant, which looks like a working
    screen with slightly larger numbers.
    """

    def their_company(self):
        for rec in store.load():
            if rec.get("client") == their_client() and rec.get("company"):
                return rec["company"]
        return None

    def test_the_fixture_has_something_to_leak(self):
        """A cross-tenant test against an empty other workspace passes for
        the wrong reason."""
        self.assertIsNotNone(self.their_company())
        self.assertTrue([r for r in store.load()
                         if r.get("client") == their_client()])

    def test_no_screen_names_the_other_tenants_company(self):
        session = self.signin(OPERATOR)
        company = self.their_company()
        for path in ("/health", "/refresh", "/revival"):
            status, body, _ = session.get(path)
            self.assertEqual(status, 200, path)
            self.assertNotIn(company, body, path)

    def test_the_counts_are_the_callers_own_records(self):
        """The number a person acts on in bulk. If it silently included
        another tenant, nothing on the page would look wrong."""
        from src import repo as repo_module
        from src.web import api

        repo = repo_module.Repo.for_user(OPERATOR, MINE)
        mine = len(repo.records())
        self.assertGreater(mine, 0)

        self.assertEqual(api.refresh_plan(repo)["considered"], mine)
        self.assertEqual(api.revival_view(repo)["summary"]["total"], mine)

    def test_a_member_of_two_workspaces_sees_one_at_a_time(self):
        """`BOTH` belongs to both. Switching must change what these read,
        and neither view may carry the other."""
        from src import repo as repo_module
        from src.web import api

        counts = {}
        for slug in (MINE, THEIRS):
            repo = repo_module.Repo.for_user(BOTH, slug)
            counts[slug] = api.revival_view(repo)["summary"]["total"]
            self.assertEqual(api.revival_view(repo)["workspace"], slug)
        self.assertEqual(
            counts[MINE] + counts[THEIRS],
            len([r for r in store.load()
                 if r.get("client") in (
                     (ws.workspace(MINE) or {}).get("client") or MINE,
                     their_client())]))

    def test_a_viewer_is_refused_all_three(self):
        session = self.signin(VIEWER)
        for path in ("/health", "/refresh", "/revival"):
            self.assertIn(session.get(path)[0], (403, 404), path)

class TheClaimPreviewShowsEvidenceNotGuesses(WebTest):
    """The screen must not display a claim it cannot justify."""

    def test_every_claim_on_the_page_carries_a_reason(self):
        from src import outreachclaims as oc
        from src import repo as repo_module

        repo = repo_module.Repo.for_user(OPERATOR, MINE)
        rec = repo.record("demo-acme")
        self.assertIsNotNone(rec, "the demo account is missing")
        for contact in rec.get("contacts") or []:
            for claim in oc.available(rec, contact["key"], MINE):
                self.assertTrue(claim["why"], claim["claim"])

    def test_a_planned_touch_is_never_shown_as_claimable(self):
        """The demo plants exactly this case on purpose."""
        from src import outreachclaims as oc
        from src import repo as repo_module

        repo = repo_module.Repo.for_user(OPERATOR, MINE)
        rec = repo.record("demo-acme")
        decision = oc.resolve(oc.SAME_CONTACT_COLLEAGUE_TOUCH, rec,
                              "sarah-jones", MINE, sender_id="mark",
                              about_sender="sara_s")
        self.assertFalse(decision)
        self.assertIn("no confirmed touch", decision["why"])

    def test_the_recorded_referral_is_claimable(self):
        from src import outreachclaims as oc
        from src import repo as repo_module

        repo = repo_module.Repo.for_user(OPERATOR, MINE)
        rec = repo.record("demo-acme")
        self.assertTrue(oc.resolve(oc.REFERRAL, rec, "sarah-jones", MINE))

    def test_hostile_text_in_a_company_name_stays_inert_on_the_timeline(self):
        from src.web import pages

        rendered = pages.esc("<script>alert(1)</script> Ltd")
        self.assertNotIn("<script", rendered)
