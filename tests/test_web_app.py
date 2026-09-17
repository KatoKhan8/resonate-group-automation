"""Every screen renders, and says the true thing when it has nothing to say.

The bar here is not "returns 200". It is that a page which cannot answer a
question says so - `unavailable()` prints *why* a cell is empty, because a
blank cell reads as a broken page, and "we did not look" and "we looked and
found nothing" are different facts an operator has to be able to tell apart.
"""
import json
import re

from src import store
from src.web import upload
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
ADMIN = "admin@productive.test"
VIEWER = "client@productive.test"


class EveryScreen(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)

    def test_every_listing_screen_renders(self):
        for path in ("/", "/batches", "/companies", "/segments", "/contacts",
                     "/campaigns", "/approvals", "/replies", "/reporting",
                     "/compare", "/simulator", "/timezones", "/workspaces",
                     "/settings", "/audit", "/diagnostics", "/upload"):
            status, body, headers = self.session.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn("text/html", headers.get("Content-Type", ""))
            self.assertGreater(len(body), 1500, f"{path} is suspiciously thin")
            self.assertNotIn("None</td>", body, f"{path} rendered a bare None")

    def test_every_detail_screen_renders(self):
        _, body, _ = self.session.get("/companies")
        record_id = re.search(r'href="/companies/([^"]+)"', body).group(1)
        status, detail, _ = self.session.get(f"/companies/{record_id}")
        self.assertEqual(status, 200)
        self.assertIn("ICP", detail)

        _, body, _ = self.session.get("/contacts")
        pair = re.search(r'href="/contacts/([^"/]+)/([^"]+)"', body)
        status, contact, _ = self.session.get(
            f"/contacts/{pair.group(1)}/{pair.group(2)}")
        self.assertEqual(status, 200)

        _, body, _ = self.session.get("/campaigns")
        campaign = re.search(r'href="/campaigns/([^"]+)"', body).group(1)
        self.assertEqual(self.session.get(f"/campaigns/{campaign}")[0], 200)
        self.assertEqual(self.session.get("/batches/uk-digital")[0], 200)

    def test_a_missing_id_is_a_404_not_a_crash(self):
        for path in ("/companies/nope", "/campaigns/nope",
                     "/contacts/nope/nope", "/nope"):
            status, body, _ = self.session.get(path)
            self.assertEqual(status, 404, path)
            self.assertNotIn("Traceback", body)

    def test_the_reporting_screen_states_what_it_cannot_know(self):
        _, body, _ = self.session.get("/reporting")
        self.assertIn("cannot know", body)
        # Nothing has been sent, so no delivery metric may appear as a number.
        self.assertNotIn("Open rate", body)

    def test_every_percentage_carries_its_numerator_and_denominator(self):
        """A percentage with no denominator is a claim, not a measurement."""
        _, body, _ = self.session.get("/reporting?dimension=region")
        percentages = re.findall(r"<b>(\d+)%</b>\s*"
                                 r'<span class="small muted">(\d+) of (\d+)',
                                 body)
        self.assertTrue(percentages, "no inspectable rates rendered")
        for pct, num, den in percentages:
            self.assertEqual(int(pct), round(100 * int(num) / int(den)))

    def test_the_comparison_screen_labels_a_small_sample(self):
        _, body, _ = self.session.get("/compare?dimension=region")
        self.assertIn("Small sample", body)

    def test_the_simulator_runs_offline(self):
        status, body, _ = self.session.get("/simulator?size=500")
        self.assertEqual(status, 200)
        self.assertIn("500", body)

    def test_the_diagnostics_screen_names_credentials_without_values(self):
        _, body, _ = self.session.get("/diagnostics")
        self.assertIn("CONTACTOUT_TOKEN", body)


class Upload(WebTest):
    """CSV upload, and the two things a CSV is allowed to do to you."""

    def test_a_formula_cell_is_refused_at_upload(self):
        """The guard on the way in, not only on the way out.

        `src/export.py` prefixes a dangerous cell when writing. That protects
        the file this system produces; it does nothing about a payload landing
        in the queue and being handed to something else later.

        The row is dropped with a stated reason rather than the whole file
        being rejected - the same trade the job model makes, where one bad
        record is recorded and skipped and the batch continues. Refusing 5,000
        domains over one poisoned cell would be the worse outcome; silently
        *accepting* it would be the actual vulnerability.
        """
        for leader in ("=", "+", "@", "\t"):
            parsed = upload.parse(
                f"domain\n{leader}cmd|'/c calc'!A1\ngood.test\n".encode(),
                existing_domains=set(), batch="b", client="productive")
            self.assertEqual([r["domain"] for r in parsed["rows"]],
                             ["good.test"])
            self.assertEqual(len(parsed["excluded"]), 1)
            self.assertIn("formula", parsed["excluded"][0]["reason"])

    def test_a_duplicate_and_an_existing_domain_are_counted_separately(self):
        parsed = upload.parse(
            b"domain\nalpha.test\nalpha.test\nbeta.test\n",
            existing_domains={"beta.test"}, batch="b", client="productive")
        self.assertEqual(parsed["uploaded"], 3)
        self.assertEqual(parsed["unique"], 1)
        self.assertEqual(parsed["duplicates"], 1)
        self.assertEqual(parsed["existing"], 1)
        self.assertFalse(parsed["committed"])

    def test_nothing_is_written_until_commit(self):
        before = len(store.load())
        session = self.signin(OPERATOR)
        status, body, _ = session.post("/upload", {"csrf": session.csrf(),
                                                   "batch": "preview-only"})
        self.assertEqual(len(store.load()), before)


class TheClientFacingCut(WebTest):
    """What a VIEWER sees, and more importantly what it does not contain."""

    def test_a_viewer_sees_no_vendor_no_cost_and_no_machinery(self):
        session = self.signin(VIEWER)
        _, body, _ = session.get("/")
        for forbidden in ("Cost", "credits", "Jobs", "MX and email security",
                          "proofpoint", "mimecast", "Diagnostics"):
            self.assertNotIn(forbidden, body,
                             f"the client-facing dashboard leaked {forbidden!r}")

    def test_a_viewer_reporting_page_hides_provider_operations(self):
        session = self.signin(VIEWER)
        _, body, _ = session.get("/reporting")
        self.assertNotIn("Provider operations", body)
        self.assertNotIn("reoon", body.lower())
        self.assertIn("Email quality", body)

    def test_a_reviewer_sees_the_rules_but_not_the_provider_mapping(self):
        """`provider_settings.view` gates the mapping, not the whole page.

        A reviewer may legitimately want to know what the ICP rules and the
        verification policy are - they are approving work judged by them. Which
        EmailBison campaign this workspace points at is a different question,
        and the note at the foot of that page claims the permission answers it,
        so the page has to be true to the claim.
        """
        reviewer = self.signin("review@productive.test")
        _, body, _ = reviewer.get("/settings")
        self.assertIn("Required confirmations", body)
        self.assertIn("does not carry provider_settings.view", body)

        operator = self.signin(OPERATOR)
        _, body, _ = operator.get("/settings")
        self.assertIn("Required confirmations", body)
        self.assertNotIn("does not carry provider_settings.view", body)

    def test_a_viewer_is_offered_only_the_screens_they_may_open(self):
        session = self.signin(VIEWER)
        _, body, _ = session.get("/")
        offered = set(re.findall(r'<nav class="nav"[^>]*>(.*?)</nav>', body,
                                 re.S)[0].split('href="'))
        links = {chunk.split('"')[0] for chunk in offered if chunk.startswith("/")}
        for path in sorted(links):
            self.assertEqual(session.get(path)[0], 200,
                             f"the nav offered {path} and it was refused")


class Health(WebTest):

    def test_healthz_needs_no_session_and_states_the_safety_position(self):
        session = self.anonymous()
        status, body, _ = session.get("/healthz")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["live_sending"])
