"""Building a campaign from a segment, over real HTTP.

The builder's job is to show what `campaignseg.assign` already decided and let
a person say yes to it. What these tests hold is mostly that it cannot do more
than that: it creates a *draft*, it cannot put one company in two campaigns, it
cannot be pointed at another workspace's segment, and creating one sends
nothing and spends nothing.
"""
import re

from src import campaigns as campaign_store
from src import store
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
ADMIN = "admin@productive.test"


class TheBuilderRenders(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)

    def test_the_segment_list_renders(self):
        status, body, _ = self.session.get("/campaigns/new")
        self.assertEqual(status, 200)
        self.assertIn("Campaign builder", body)
        self.assertIn("segment", body)

    def a_segment(self):
        _, body, _ = self.session.get("/campaigns/new")
        found = re.search(r'href="/campaigns/new\?segment=([^"]+)"', body)
        self.assertIsNotNone(found, "no segment offered by the builder")
        return found.group(1)

    def test_choosing_a_segment_opens_it_up(self):
        status, body, _ = self.session.get(
            "/campaigns/new?segment=" + self.a_segment())
        self.assertEqual(status, 200)
        for word in ("Personas", "Angles", "Channel strategy", "Timezones",
                     "Who would be in it"):
            self.assertIn(word, body)

    def test_the_grouping_is_explained_by_the_engine_not_the_page(self):
        """`campaignseg.why_together` is the first answer. There is no second."""
        _, body, _ = self.session.get(
            "/campaigns/new?segment=" + self.a_segment())
        self.assertIn("note", body)
        self.assertNotIn("Traceback", body)

    def test_an_unknown_segment_renders_the_list_without_erroring(self):
        status, body, _ = self.session.get("/campaigns/new?segment=nope")
        self.assertEqual(status, 200)
        self.assertNotIn("Who would be in it", body)

    def test_the_page_states_that_creating_sends_nothing(self):
        _, body, _ = self.session.get(
            "/campaigns/new?segment=" + self.a_segment())
        self.assertIn("draft", body)
        self.assertIn("Nothing is sent", body)


class CreatingOne(WebTest):
    """Each test creates a campaign, so each one puts the estate back.

    The demo estate is built once per class - it takes a few seconds and
    rebuilding it per test would make this file the slowest in the suite. But
    creating a campaign consumes the one segment that is free, so without a
    restore the second test in the class would find nothing to build and pass
    by skipping, which is the worst outcome available.
    """

    def setUp(self):
        self.session = self.signin(OPERATOR)
        self._campaigns = [dict(c) for c in campaign_store.load()]

    def tearDown(self):
        campaign_store.save(self._campaigns)

    def a_buildable_segment(self):
        _, body, _ = self.session.get("/campaigns/new")
        for found in re.finditer(
                r'href="/campaigns/new\?segment=([^"]+)"', body):
            key = found.group(1)
            _, detail, _ = self.session.get("/campaigns/new?segment=" + key)
            if 'action="/campaigns/create"' in detail:
                return key, detail
        self.skipTest("every demo segment is already in a campaign")

    def test_creating_prepares_it_and_does_nothing_else(self):
        """"Nothing else" is every assertion below except the status.

        This used to require `draft`, and stopping at draft was the
        defect: `orchestrator.prepare` is the only setter of
        `ready_for_review` and the only caller of `assign_cadence_arms`,
        and it had no web caller - so `src/tasks.py`, which files its rows
        for `ready_for_review` and `awaiting_approval`, never mentioned a
        campaign built in the product. The work queue silently omitted its
        most consequential row.

        Preparing is not deciding, and the rest of this test is what says
        so: no provider campaign on either channel, no approval, not
        launched. Those are unchanged and are the real content of
        "nothing else".
        """
        key, _ = self.a_buildable_segment()
        before = {c["campaign_id"] for c in campaign_store.load()}
        status, body, _ = self.session.post("/campaigns/create", {
            "csrf": self.session.csrf("/campaigns/new"),
            "segment_key": key, "name": "Built by a test",
            "campaign_id": "built-by-a-test"})
        self.assertEqual(status, 200)

        made = campaign_store.get("built-by-a-test")
        self.assertIsNotNone(made)
        self.assertEqual(made["status"], "ready_for_review")
        self.assertEqual(made["client"], "productive")
        self.assertTrue(made["record_ids"])
        # Nothing about sending, and no provider campaign.
        self.assertIsNone(made["bison_campaign_id"])
        self.assertIsNone(made["heyreach_campaign_id"])
        self.assertIsNone(made["approval"])
        self.assertEqual(made["launch"]["state"], "not_launched")
        self.assertNotIn("built-by-a-test", before)

    def test_the_same_company_is_never_put_in_two_campaigns(self):
        key, _ = self.a_buildable_segment()
        self.session.post("/campaigns/create", {
            "csrf": self.session.csrf("/campaigns/new"),
            "segment_key": key, "name": "First", "campaign_id": "first-one"})
        first = campaign_store.get("first-one")
        self.assertIsNotNone(first)

        status, body, _ = self.session.post("/campaigns/create", {
            "csrf": self.session.csrf("/campaigns/new"),
            "segment_key": key, "name": "Second",
            "campaign_id": "second-one"})
        self.assertEqual(status, 400)
        self.assertIn("already in a campaign", body)
        self.assertIsNone(campaign_store.get("second-one"))

    def test_a_campaign_needs_a_name_a_person_will_recognise(self):
        key, _ = self.a_buildable_segment()
        status, body, _ = self.session.post("/campaigns/create", {
            "csrf": self.session.csrf("/campaigns/new"),
            "segment_key": key, "name": "   ", "campaign_id": "nameless"})
        self.assertEqual(status, 400)
        self.assertIsNone(campaign_store.get("nameless"))

    def test_an_id_that_is_not_a_slug_is_refused(self):
        key, _ = self.a_buildable_segment()
        status, body, _ = self.session.post("/campaigns/create", {
            "csrf": self.session.csrf("/campaigns/new"),
            "segment_key": key, "name": "Traversal",
            "campaign_id": "../../etc/passwd"})
        self.assertEqual(status, 400)
        self.assertIn("not a usable campaign id", body)

    def test_a_duplicate_id_is_refused_rather_than_overwriting(self):
        existing = campaign_store.load()[0]["campaign_id"]
        key, _ = self.a_buildable_segment()
        status, body, _ = self.session.post("/campaigns/create", {
            "csrf": self.session.csrf("/campaigns/new"),
            "segment_key": key, "name": "Clash", "campaign_id": existing})
        self.assertEqual(status, 400)
        self.assertIn("already exists", body)

    def test_creating_without_a_csrf_token_is_refused(self):
        key, _ = self.a_buildable_segment()
        status, _, _ = self.session.post("/campaigns/create", {
            "segment_key": key, "name": "No token", "campaign_id": "no-token"})
        self.assertEqual(status, 403)
        self.assertIsNone(campaign_store.get("no-token"))

    def test_creating_is_written_to_the_audit_log(self):
        key, _ = self.a_buildable_segment()
        self.session.post("/campaigns/create", {
            "csrf": self.session.csrf("/campaigns/new"),
            "segment_key": key, "name": "Audited",
            "campaign_id": "audited-one"})
        admin = self.signin(ADMIN)
        _, log, _ = admin.get("/audit")
        self.assertIn("campaign.created", log)
        self.assertIn("audited-one", log)


class WhoMayBuild(WebTest):

    def test_a_viewer_cannot_reach_the_builder(self):
        viewer = self.signin(VIEWER)
        self.assertEqual(viewer.get("/campaigns/new")[0], 403)

    def test_a_reviewer_cannot_reach_the_builder(self):
        """`campaign.create` belongs to the people who run the machine."""
        reviewer = self.signin(REVIEWER)
        self.assertEqual(reviewer.get("/campaigns/new")[0], 403)

    def test_a_reviewer_posting_a_creation_directly_is_refused(self):
        reviewer = self.signin(REVIEWER)
        status, _, _ = reviewer.post("/campaigns/create", {
            "csrf": reviewer.csrf(), "segment_key": "anything",
            "name": "Forged", "campaign_id": "forged-one"})
        self.assertEqual(status, 403)
        self.assertIsNone(campaign_store.get("forged-one"))


class TheBuilderCannotCrossAWorkspace(WebTest):

    def test_a_foreign_segment_key_builds_nothing(self):
        theirs = None
        for rec in store.load():
            if rec.get("client") != "productive":
                key = (rec.get("qualification") or {}).get("segment_key")
                if key:
                    theirs = key
                    break
        self.assertIsNotNone(theirs, "no second-workspace segment to forge")

        session = self.signin(OPERATOR)
        status, body, _ = session.post("/campaigns/create", {
            "csrf": session.csrf("/campaigns/new"),
            "segment_key": theirs, "name": "Cross tenant",
            "campaign_id": "cross-tenant"})
        made = campaign_store.get("cross-tenant")
        if made is not None:
            # A segment key can legitimately repeat across workspaces. What
            # must never happen is another workspace's records joining it.
            mine = {r["id"] for r in store.load()
                    if r.get("client") == "productive"}
            self.assertTrue(set(made["record_ids"]) <= mine,
                            "a campaign was built over another workspace's "
                            "records")
            self.assertEqual(made["client"], "productive")
        else:
            self.assertEqual(status, 400)

    def test_the_builder_lists_only_this_workspaces_companies(self):
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/campaigns/new")
        for found in re.finditer(r'href="/campaigns/new\?segment=([^"]+)"',
                                 body):
            _, detail, _ = session.get(
                "/campaigns/new?segment=" + found.group(1))
            for rec in store.load():
                if rec.get("client") != "productive":
                    self.assertNotIn(f'/companies/{rec["id"]}"', detail)
