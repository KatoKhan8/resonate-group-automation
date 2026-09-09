"""Stopping a campaign, and marking a reply read without un-stopping anything.

Two asymmetries are the point of this file.

A campaign can be **paused** from reviewer upward and **launched** by nobody at
all, because the person who can see something is wrong should be able to stop
it without finding somebody more senior first, and nobody should be able to
start it from a browser.

A reply can be marked **handled**, which records that a person read it, and
that is all it does. The pause a reply causes covers both channels for the
whole company, and it is lifted by looking at the company - not by ticking the
reply off a list. A checkbox that lifted it would turn a safety property into
a piece of admin.
"""
from src import campaigns as campaign_store
from src import store, workspaces
from tests.webbase import WebTest

ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"


class PausingACampaign(WebTest):

    def setUp(self):
        self._campaigns = [dict(c) for c in campaign_store.load()]

    def tearDown(self):
        campaign_store.save(self._campaigns)

    def pause(self, session, campaign_id="uk-digital", why="a client asked"):
        return session.post("/campaigns/pause", {
            "csrf": session.csrf("/campaigns"), "campaign_id": campaign_id,
            "why": why})

    def test_a_reviewer_can_stop_a_campaign(self):
        session = self.signin(REVIEWER)
        status, _, _ = self.pause(session)
        self.assertEqual(status, 200)
        campaign = campaign_store.get("uk-digital")
        self.assertEqual(campaign["status"], "paused")
        self.assertEqual(campaign["pause"]["reason"], "a client asked")
        self.assertEqual(campaign["pause"]["by"], REVIEWER)

    def test_pausing_is_audited(self):
        session = self.signin(OPERATOR)
        self.pause(session)
        entries = [e for e in workspaces.audit(limit=200)
                   if e["action"] == "campaign.paused"]
        self.assertTrue(entries)
        self.assertEqual(entries[0]["resource_id"], "uk-digital")

    def test_pausing_twice_is_refused_rather_than_silently_repeated(self):
        session = self.signin(OPERATOR)
        self.pause(session)
        status, body, _ = self.pause(session)
        self.assertEqual(status, 409)
        self.assertIn("already paused", body)

    def test_a_viewer_cannot_pause(self):
        viewer = self.signin(VIEWER)
        status, _, _ = viewer.post("/campaigns/pause", {
            "csrf": viewer.csrf(), "campaign_id": "uk-digital"})
        self.assertEqual(status, 403)
        self.assertNotEqual(campaign_store.get("uk-digital")["status"],
                            "paused")

    def test_pausing_without_a_csrf_token_is_refused(self):
        session = self.signin(OPERATOR)
        status, _, _ = session.post("/campaigns/pause",
                                    {"campaign_id": "uk-digital"})
        self.assertEqual(status, 403)

    def test_another_workspaces_campaign_cannot_be_paused(self):
        session = self.signin(OPERATOR)
        status, _, _ = self.pause(session, campaign_id="apac-recruiting")
        self.assertEqual(status, 404)
        self.assertNotEqual(campaign_store.get("apac-recruiting")["status"],
                            "paused")

    def test_resuming_re_runs_every_check_rather_than_clearing_a_flag(self):
        """A pause is not undone by forgetting about it."""
        session = self.signin(OPERATOR)
        self.pause(session)
        status, body, _ = session.post("/campaigns/resume", {
            "csrf": session.csrf("/campaigns"), "campaign_id": "uk-digital"})
        # Either it passed every check and is running, or it was refused and
        # the blockers are on the page. What must not happen is a campaign
        # that is running without having passed them.
        campaign = campaign_store.get("uk-digital")
        if status == 200 and campaign["status"] == "running":
            self.assertIsNone(campaign["pause"])
        else:
            self.assertEqual(status, 409)
            self.assertEqual(campaign["status"], "paused")
            self.assertIn("cannot resume", body)

    def test_resuming_something_that_is_not_paused_is_refused(self):
        session = self.signin(OPERATOR)
        status, body, _ = session.post("/campaigns/resume", {
            "csrf": session.csrf("/campaigns"), "campaign_id": "us-creative"})
        self.assertEqual(status, 409)
        self.assertIn("not paused", body)


class ThereIsNoLaunchControl(WebTest):

    def test_no_screen_offers_a_launch(self):
        session = self.signin(ADMIN)
        for path in ("/campaigns", "/campaigns/uk-digital", "/approvals",
                     "/outreach"):
            _, body, _ = session.get(path)
            self.assertNotIn('action="/campaigns/launch"', body, path)
            self.assertNotIn(">Launch<", body, path)

    def test_the_campaign_list_says_so_out_loud(self):
        session = self.signin(ADMIN)
        _, body, _ = session.get("/campaigns")
        self.assertIn("Nothing here launches", body)
        self.assertIn("push.run(live=True)", body)

    def test_a_posted_launch_is_a_404(self):
        session = self.signin(ADMIN)
        status, _, _ = session.post("/campaigns/launch", {
            "csrf": session.csrf("/campaigns"), "campaign_id": "uk-digital"})
        self.assertEqual(status, 404)


class HandlingAReply(WebTest):

    def setUp(self):
        self._records = [dict(r) for r in store.load()]

    def tearDown(self):
        store.save(self._records)

    def a_reply(self, session):
        _, body, _ = session.get("/replies")
        import re
        found = re.search(
            r'name="record_id" value="([^"]+)"[^>]*>\s*'
            r'<input type="hidden" name="contact_key" value="([^"]+)"[^>]*>\s*'
            r'<input type="hidden" name="at" value="([^"]+)"', body)
        self.assertIsNotNone(found, "no unhandled reply on the replies screen")
        return found.groups()

    def test_an_operator_can_mark_one_handled(self):
        session = self.signin(OPERATOR)
        record_id, contact_key, at = self.a_reply(session)
        status, _, _ = session.post("/replies/handle", {
            "csrf": session.csrf("/replies"), "record_id": record_id,
            "contact_key": contact_key, "at": at, "note": "called them back"})
        self.assertEqual(status, 200)

        rec = store.get(record_id)
        handled = [e for e in rec["events"] if e.get("handled")]
        self.assertTrue(handled)
        self.assertEqual(handled[0]["handled"]["by"], OPERATOR)
        self.assertEqual(handled[0]["handled"]["note"], "called them back")

    def test_marking_it_handled_does_not_un_pause_the_company(self):
        """The one property this screen must not be able to break."""
        session = self.signin(OPERATOR)
        record_id, contact_key, at = self.a_reply(session)
        before = bool(store.get(record_id).get("paused"))
        session.post("/replies/handle", {
            "csrf": session.csrf("/replies"), "record_id": record_id,
            "contact_key": contact_key, "at": at})
        self.assertEqual(bool(store.get(record_id).get("paused")), before)

    def test_the_page_says_that_handling_lifts_nothing(self):
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/replies")
        self.assertIn("does <b>not</b> un-pause anything", body)

    def test_handling_is_audited(self):
        session = self.signin(OPERATOR)
        record_id, contact_key, at = self.a_reply(session)
        session.post("/replies/handle", {
            "csrf": session.csrf("/replies"), "record_id": record_id,
            "contact_key": contact_key, "at": at})
        entries = [e for e in workspaces.audit(limit=200)
                   if e["action"] == "reply.handled"]
        self.assertTrue(entries)

    def test_handling_the_same_reply_twice_is_refused(self):
        session = self.signin(OPERATOR)
        record_id, contact_key, at = self.a_reply(session)
        fields = {"csrf": session.csrf("/replies"), "record_id": record_id,
                  "contact_key": contact_key, "at": at}
        session.post("/replies/handle", fields)
        status, body, _ = session.post(
            "/replies/handle", dict(fields, csrf=session.csrf("/replies")))
        self.assertEqual(status, 409)
        self.assertIn("already been marked handled", body)

    def test_a_reviewer_sees_replies_but_cannot_mark_them(self):
        """`replies.manage` is an operator's, `replies.view` a reviewer's."""
        reviewer = self.signin(REVIEWER)
        status, body, _ = reviewer.get("/replies")
        self.assertEqual(status, 200)
        self.assertNotIn('action="/replies/handle"', body)

        status, _, _ = reviewer.post("/replies/handle", {
            "csrf": reviewer.csrf("/replies"), "record_id": "anything",
            "contact_key": "x", "at": "y"})
        self.assertEqual(status, 403)

    def test_another_workspaces_reply_cannot_be_marked(self):
        theirs = next(r for r in store.load()
                      if r.get("client") == "contactout")
        session = self.signin(OPERATOR)
        status, _, _ = session.post("/replies/handle", {
            "csrf": session.csrf("/replies"), "record_id": theirs["id"],
            "contact_key": "x", "at": "y"})
        self.assertEqual(status, 404)
