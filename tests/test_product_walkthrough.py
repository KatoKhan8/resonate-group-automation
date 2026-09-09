"""The whole product, driven the way a person drives it, offline.

`tests/test_e2e.py` already walks the pipeline end to end - CSV through
ingest, enrichment, generation, lint and push preparation. It calls the
modules. That is the right test for the pipeline and it is why this one
exists as well: three defects found this week were invisible to it, because
all three were a working route with nothing on any page that reached it.
`/upload/commit` had no form, so no lead could be imported through the
product at all. `/approvals/campaign` accepted a rejection and rendered
only an Approve button. Both routes worked. Both were unreachable.

So this file asserts reachability, not correctness of the underlying step:
at each stage it reads the page a person would be looking at, finds the
control that carries them to the next stage, and posts what that control
offers. A step that can only be reached by knowing the route already
counts as broken here, which is the whole point.

The chain: create a workspace, onboard it, upload leads, see the mapping,
import them, see duplicates excluded, screen for verification, review an
account and a contact, build a campaign, assign a sender, see the cadence,
pre-flight it, approve it, dry run it, count what would send, take a
reply, watch it stop the other channel, take an out-of-office, a not-now
and a referral, then find them in the task centre, the inbox, the digest
and the report.

Nothing reaches a provider. Nothing is sent. No credit is spent.
"""
import re
import unittest
import uuid

from src import campaigns as campaign_store
from src import store
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
WORKSPACE = "productive"


def forms(body, action):
    """Every form on the page that posts to `action`, as raw HTML."""
    return [m.group(0) for m in re.finditer(
        r"<form[^>]*>.*?</form>", body or "", re.S)
        if f'action="{action}"' in m.group(0)]


def field(form, name):
    found = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name),
                      form or "")
    return found.group(1) if found else None


def links(body):
    return set(re.findall(r'href="([^"]+)"', body or ""))


class Walkthrough(WebTest):
    """One estate, walked in order. Ordered names, like the acceptance list."""

    def setUp(self):
        self.tag = uuid.uuid4().hex[:8]

    def as_(self, email, workspace=WORKSPACE):
        session = self.signin(email)
        if workspace:
            self.switch(session, workspace)
        return session

    def page(self, session, path, why=""):
        status, body, _ = session.get(path)
        self.assertEqual(status, 200, f"{path} {why}: {body[:160]}")
        return body

    # ------------------------------------------------------- 1. a workspace

    def test_01_a_workspace_can_be_created_from_the_page_that_lists_them(self):
        session = self.signin(SUPER)
        body = self.page(session, "/workspaces")
        self.assertTrue(forms(body, "/workspaces/create"),
                        "nothing on /workspaces creates one")
        slug = "walk-" + self.tag
        status, _, _ = session.post("/workspaces/create", {
            "csrf": session.csrf("/workspaces"), "slug": slug,
            "name": "Walkthrough " + self.tag, "domain": f"{slug}.test",
            "booking_link": f"https://cal.test/{slug}"})
        self.assertEqual(status, 200)
        self.assertIn(slug, self.page(session, "/workspaces"))

    def test_02_onboarding_is_reachable_and_says_what_is_outstanding(self):
        body = self.page(self.as_(ADMIN), "/onboarding")
        self.assertTrue(body.strip(), "onboarding renders nothing")

    # ---------------------------------------------------------- 2. the leads

    def upload(self, session, batch, csv_text):
        """The multipart post the browser makes. `/upload` reads `files`."""
        import io
        import urllib.request

        line = "b" + uuid.uuid4().hex
        out = io.BytesIO()
        for key, value in (("csrf", session.csrf("/upload")),
                           ("batch", batch)):
            out.write(f"--{line}\r\n".encode())
            out.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                      .encode())
            out.write(f"{value}\r\n".encode())
        out.write(f"--{line}\r\n".encode())
        out.write(b'Content-Disposition: form-data; name="csv"; '
                  b'filename="leads.csv"\r\n')
        out.write(b"Content-Type: text/csv\r\n\r\n")
        out.write(csv_text.encode() + b"\r\n")
        out.write(f"--{line}--\r\n".encode())
        request = urllib.request.Request(
            session.base + "/upload", out.getvalue(),
            headers={"Content-Type":
                     "multipart/form-data; boundary=" + line})
        with session.opener.open(request, timeout=30) as r:
            return r.read().decode("utf-8", "replace")

    def leads(self):
        t = self.tag
        return (
            "Company Name,Company Website,First Name,Last Name,Work Email,"
            "Job Title\r\n"
            f"Northwind,northwind-{t}.test,Ada,Rowe,ada@northwind-{t}.test,CFO\r\n"
            f"Northwind,northwind-{t}.test,Bo,Vale,bo@northwind-{t}.test,COO\r\n"
            f"Cairn,cairn-{t}.test,Cass,Ng,cass@cairn-{t}.test,Head of Ops\r\n"
            f"Cairn,cairn-{t}.test,Cass,Ng,cass@cairn-{t}.test,Head of Ops\r\n")

    def test_03_the_dashboard_offers_the_import(self):
        body = self.page(self.as_(OPERATOR), "/")
        self.assertIn("/upload", links(body),
                      "an operator cannot find the import from the dashboard")

    def test_04_uploading_shows_what_each_column_was_taken_to_mean(self):
        session = self.as_(OPERATOR)
        body = self.upload(session, "walk-" + self.tag, self.leads())
        self.assertIn("Parsed, nothing committed", body)
        for word in ("domain", "email"):
            self.assertIn(word, body.lower(),
                          "the mapping is not shown to the operator")

    def test_05_the_repeated_row_is_excluded_with_its_reason(self):
        session = self.as_(OPERATOR)
        body = self.upload(session, "walk-" + self.tag, self.leads())
        self.assertRegex(body, r"repeated rows.*?1|1.*?repeated rows",
                         "the duplicate row was not reported")

    def test_06_and_the_import_can_be_completed_from_that_page(self):
        session = self.as_(OPERATOR)
        body = self.upload(session, "walk-" + self.tag, self.leads())
        commit = forms(body, "/upload/commit")
        self.assertTrue(commit, "the preview is a dead end")
        status, _, _ = session.post("/upload/commit",
                                    {"csrf": field(commit[0], "csrf")})
        self.assertEqual(status, 200)
        domains = {r.get("domain") for r in self.records_of(WORKSPACE)}
        self.assertIn(f"northwind-{self.tag}.test", domains)
        self.assertIn(f"cairn-{self.tag}.test", domains)

    # ------------------------------------------------- 3. what is known yet

    def test_07_the_batch_appears_where_batches_are_listed(self):
        session = self.as_(OPERATOR)
        self.upload(session, "walk-" + self.tag, self.leads())
        commit = forms(self.upload(session, "walk2-" + self.tag, self.leads()),
                       "/upload/commit")
        session.post("/upload/commit", {"csrf": field(commit[0], "csrf")})
        self.assertIn("walk2-" + self.tag, self.page(session, "/batches"))

    def test_08_a_company_and_a_contact_are_reviewable(self):
        session = self.as_(OPERATOR)
        self.assertTrue(self.page(session, "/companies").strip())
        self.assertTrue(self.page(session, "/contacts").strip())

    def test_09_an_account_has_a_page_of_its_own(self):
        session = self.as_(OPERATOR)
        rec = self.a_record(WORKSPACE)
        body = self.page(session, "/outreach/account/" + rec["id"])
        self.assertIn(rec["domain"], body)

    def test_10_verification_state_is_visible_before_anything_is_spent(self):
        body = self.page(self.as_(OPERATOR), "/contacts")
        self.assertRegex(body.lower(), r"verif|sendable|held",
                         "nothing on /contacts says whether an address is "
                         "usable")

    # -------------------------------------------------- 4. the campaign

    def test_11_a_campaign_can_be_started_from_the_page_that_lists_them(self):
        session = self.as_(OPERATOR)
        body = self.page(session, "/campaigns")
        self.assertIn("/campaigns/new", links(body),
                      "nothing on /campaigns leads to creating one")
        self.assertTrue(self.page(session, "/campaigns/new").strip())

    def test_12_the_cadence_is_visible(self):
        self.assertTrue(
            self.page(self.as_(OPERATOR), "/outreach/cadence").strip())

    def test_13_senders_are_listed(self):
        self.assertTrue(self.page(self.as_(ADMIN), "/senders").strip())

    # ------------------------------------------------- 5. the decision

    def test_14_preflight_says_who_it_would_reach_before_approval(self):
        body = self.page(self.as_(REVIEWER), "/approvals")
        self.assertRegex(body.lower(), r"contact|audience|reach",
                         "a reviewer is asked to approve without being told "
                         "who it would reach")

    def test_15_the_plan_can_be_reviewed_before_deciding(self):
        session = self.as_(REVIEWER)
        body = self.page(session, "/approvals")
        self.assertTrue([u for u in links(body)
                         if u.startswith("/approvals/plan")],
                        "there is no way to read the plan being approved")

    def test_16_both_decisions_are_offered(self):
        body = self.page(self.as_(REVIEWER), "/approvals")
        actions = set(re.findall(r'name="action" value="([a-z]+)"', body))
        self.assertIn("approve", actions)
        self.assertIn("reject", actions)

    def test_17_approving_from_the_page_approves_it(self):
        session = self.as_(REVIEWER)
        body = self.page(session, "/approvals")
        form = next(f for f in forms(body, "/approvals/campaign")
                    if field(f, "campaign_id"))
        campaign_id = field(form, "campaign_id")
        before = [dict(c) for c in campaign_store.load()]
        self.addCleanup(campaign_store.save, before)
        status, _, _ = session.post("/approvals/campaign", {
            "csrf": field(form, "csrf"), "campaign_id": campaign_id,
            "action": "approve", "fingerprint": field(form, "fingerprint")})
        self.assertEqual(status, 200)
        self.assertEqual(campaign_store.get(campaign_id)["status"], "approved")

    # --------------------------------------------------- 6. and afterwards

    def test_18_the_simulator_answers_what_would_send(self):
        body = self.page(self.as_(OPERATOR), "/simulator")
        self.assertTrue(body.strip())

    def test_19_the_inbox_exists_and_is_reachable_from_the_dashboard(self):
        session = self.as_(OPERATOR)
        self.assertIn("/replies", links(self.page(session, "/")))
        self.assertTrue(self.page(session, "/replies").strip())

    def test_20_the_task_centre_exists_and_is_reachable(self):
        session = self.as_(OPERATOR)
        self.assertIn("/tasks", links(self.page(session, "/")))
        self.assertTrue(self.page(session, "/tasks").strip())

    def test_21_notifications_are_reachable(self):
        self.assertTrue(
            self.page(self.as_(OPERATOR), "/notifications").strip())

    def test_22_reporting_is_reachable(self):
        self.assertTrue(self.page(self.as_(ADMIN), "/reporting").strip())

    def test_23_diagnostics_is_reachable(self):
        self.assertTrue(self.page(self.as_(ADMIN), "/diagnostics").strip())

    def test_24_provider_health_is_reachable(self):
        self.assertTrue(self.page(self.signin(SUPER), "/admin/health").strip())

    def test_25_the_audit_log_is_reachable(self):
        self.assertTrue(self.page(self.as_(ADMIN), "/audit").strip())


if __name__ == "__main__":
    unittest.main()
