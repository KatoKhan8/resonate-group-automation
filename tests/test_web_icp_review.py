"""The ICP review screen, over real HTTP against a real demo estate.

The page is where a human makes the decision PLAYBOOK section 1 reserves for
one: `review` and `unknown` mean zero person credits until somebody looks.
What these tests hold is that the screen makes the decision *recordable*
without making it *powerful* - the decision is stored, the audit log gets an
entry, and what it unlocks is still the client config's call rather than the
reviewer's.
"""
import re

from src import dmplan, icp, qualify, store
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
ADMIN = "admin@productive.test"


class TheQueueRenders(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)

    def test_the_page_renders_and_counts_every_status(self):
        status, body, _ = self.session.get("/icp")
        self.assertEqual(status, 200)
        for word in ("ICP review", "qualified", "review", "unknown",
                     "rejected"):
            self.assertIn(word, body)

    def test_the_filters_narrow_without_erroring(self):
        for query in ("?status=review", "?status=qualified", "?decided=no",
                      "?decided=yes", "?status=unknown&decided=no"):
            status, body, _ = self.session.get("/icp" + query)
            self.assertEqual(status, 200, query)
            self.assertNotIn("Traceback", body)

    def test_a_forged_status_narrows_to_nothing_rather_than_erroring(self):
        status, body, _ = self.session.get("/icp?status=%27+OR+1%3D1")
        self.assertEqual(status, 200)
        self.assertIn("No company matches this filter", body)

    def test_the_page_names_the_gate_rather_than_implying_one(self):
        """"Accepted" and "will be enriched" are different facts."""
        _, body, _ = self.session.get("/icp")
        self.assertIn("allow_review_enrichment", body)

    def test_what_is_missing_is_shown_beside_the_score(self):
        """A low score on no evidence is a task, not a rejection."""
        _, body, _ = self.session.get("/icp")
        self.assertIn("what is missing", body)


class WhoMayDecide(WebTest):

    def a_reviewable(self, session):
        """A record on the page that has not been decided yet."""
        _, body, _ = session.get("/icp?decided=no")
        found = re.search(
            r'name="record_id" value="([^"]+)"[^>]*>\s*'
            r'<input type="hidden" name="fingerprint" value="([^"]*)"', body)
        self.assertIsNotNone(found, "no undecided company on the review page")
        return found.group(1), found.group(2)

    def test_a_viewer_cannot_even_see_the_queue(self):
        viewer = self.signin(VIEWER)
        status, _, _ = viewer.get("/icp")
        self.assertEqual(status, 403)

    def test_a_viewer_posting_the_decision_directly_is_refused(self):
        """The menu is a courtesy. The handler is the control.

        A viewer never sees this screen, so the only way they reach the
        decision is by constructing the request. That is the path that has to
        be closed, and it is closed in the handler rather than by the absence
        of a button.
        """
        reviewer = self.signin(REVIEWER)
        record_id, fingerprint = self.a_reviewable(reviewer)

        viewer = self.signin(VIEWER)
        status, body, _ = viewer.post("/icp/decide", {
            "csrf": viewer.csrf(), "record_id": record_id,
            "fingerprint": fingerprint, "decision": "accept"})
        self.assertEqual(status, 403)
        self.assertIsNone(qualify.review_of(store.get(record_id)))

    def test_the_buttons_appear_for_a_role_that_may_use_them(self):
        session = self.signin(REVIEWER)
        _, body, _ = session.get("/icp?decided=no")
        self.assertIn('action="/icp/decide"', body)

    def test_a_reviewer_can_record_a_decision(self):
        session = self.signin(REVIEWER)
        record_id, fingerprint = self.a_reviewable(session)
        status, body, _ = session.post("/icp/decide", {
            "csrf": session.csrf("/icp"), "record_id": record_id,
            "fingerprint": fingerprint, "decision": "accept",
            "note": "checked their case studies"})
        self.assertEqual(status, 200)

        review = qualify.review_of(store.get(record_id))
        self.assertIsNotNone(review)
        self.assertEqual(review["decision"], "accept")
        self.assertEqual(review["by"], REVIEWER)
        self.assertEqual(review["note"], "checked their case studies")

    def test_the_decision_lands_in_the_audit_log(self):
        session = self.signin(REVIEWER)
        record_id, fingerprint = self.a_reviewable(session)
        session.post("/icp/decide", {
            "csrf": session.csrf("/icp"), "record_id": record_id,
            "fingerprint": fingerprint, "decision": "reject",
            "note": "already a customer"})

        admin = self.signin(ADMIN)
        _, log, _ = admin.get("/audit")
        self.assertIn("icp.reviewed", log)
        self.assertIn(REVIEWER, log)

    def test_a_decision_that_is_not_a_decision_is_refused(self):
        session = self.signin(REVIEWER)
        record_id, fingerprint = self.a_reviewable(session)
        status, body, _ = session.post("/icp/decide", {
            "csrf": session.csrf("/icp"), "record_id": record_id,
            "fingerprint": fingerprint, "decision": "probably"})
        self.assertEqual(status, 409)
        self.assertIsNone(qualify.review_of(store.get(record_id)))

    def test_a_stale_fingerprint_is_refused_rather_than_applied(self):
        """Approve means approve *this*, the same as everywhere else here."""
        session = self.signin(REVIEWER)
        record_id, _ = self.a_reviewable(session)
        status, body, _ = session.post("/icp/decide", {
            "csrf": session.csrf("/icp"), "record_id": record_id,
            "fingerprint": "a-verdict-that-moved", "decision": "accept"})
        self.assertEqual(status, 409)
        self.assertIn("changed after this page was rendered", body)
        self.assertIsNone(qualify.review_of(store.get(record_id)))

    def test_a_decision_without_a_csrf_token_is_refused(self):
        session = self.signin(REVIEWER)
        record_id, fingerprint = self.a_reviewable(session)
        status, _, _ = session.post("/icp/decide", {
            "record_id": record_id, "fingerprint": fingerprint,
            "decision": "accept"})
        self.assertEqual(status, 403)


class ADecisionCannotCrossAWorkspace(WebTest):

    def test_a_foreign_record_id_is_not_found_rather_than_decided(self):
        theirs = [r for r in store.load() if r.get("client") == "contactout"]
        self.assertTrue(theirs, "the demo estate has no second workspace")
        target = theirs[0]

        session = self.signin(REVIEWER)
        status, _, _ = session.post("/icp/decide", {
            "csrf": session.csrf("/icp"), "record_id": target["id"],
            "fingerprint": (target.get("qualification") or {}).get(
                "inputs_fingerprint") or "",
            "decision": "accept"})
        self.assertEqual(status, 404)
        self.assertIsNone(qualify.review_of(store.get(target["id"])))

    def test_the_queue_only_ever_lists_this_workspace(self):
        session = self.signin(REVIEWER)
        _, body, _ = session.get("/icp")
        for rec in store.load():
            if rec.get("client") != "productive":
                self.assertNotIn(rec["id"], body)


class WhatTheDecisionActuallyUnlocks(WebTest):
    """The reviewer records a conclusion. The client config sets the budget."""

    def undecided_with(self, session, status):
        _, body, _ = session.get(f"/icp?status={status}&decided=no")
        return re.search(
            r'name="record_id" value="([^"]+)"[^>]*>\s*'
            r'<input type="hidden" name="fingerprint" value="([^"]*)"', body)

    def test_accepting_does_not_widen_the_spend_gate_by_itself(self):
        """`review` and `unknown` are the same rule: not knowing is not
        permission. Either one proves the property."""
        session = self.signin(REVIEWER)
        found = (self.undecided_with(session, "review")
                 or self.undecided_with(session, "unknown"))
        self.assertIsNotNone(
            found, "the demo estate has no company awaiting an ICP decision, "
                   "so the review queue demonstrates nothing")
        record_id, fingerprint = found.group(1), found.group(2)

        session.post("/icp/decide", {
            "csrf": session.csrf("/icp"), "record_id": record_id,
            "fingerprint": fingerprint, "decision": "accept"})

        rec = store.get(record_id)
        verdict = (rec.get("qualification") or {}).get("verdict") or {}
        allowed, why = dmplan.may_enrich({}, [], rec, verdict, {})
        self.assertFalse(allowed,
                         "one click in a browser widened what a client agreed "
                         "to spend")

    def test_rejecting_blocks_enrichment_whatever_the_score_said(self):
        session = self.signin(REVIEWER)
        _, body, _ = session.get("/icp?status=qualified&decided=no")
        found = re.search(
            r'name="record_id" value="([^"]+)"[^>]*>\s*'
            r'<input type="hidden" name="fingerprint" value="([^"]*)"', body)
        if not found:
            self.skipTest("no qualified company left undecided")
        record_id, fingerprint = found.group(1), found.group(2)

        session.post("/icp/decide", {
            "csrf": session.csrf("/icp"), "record_id": record_id,
            "fingerprint": fingerprint, "decision": "reject"})

        rec = store.get(record_id)
        allowed, why = dmplan.may_enrich(
            {"dm_approval": {}}, [], rec,
            {"icp_status": icp.QUALIFIED, "icp_tier": icp.TIER_A}, {})
        self.assertFalse(allowed)
        self.assertIn("rejected it", why)
