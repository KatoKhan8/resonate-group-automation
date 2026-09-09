"""A reviewer could approve a campaign and had no way to refuse one.

Everything behind the decision was already two-sided. `_approve_campaign`
reads `action` from the form, `orchestrator.decide` accepts "reject",
`roles.REVIEWER` is chosen because it carries approve *and* reject, and the
audit log has a `campaign.rejected` action to write. The page rendered one
button.

So the only decision a reviewer could record was yes, and approval that
cannot be withheld is not approval - it is a formality with an audit trail.
`tests/test_web_approval_audit.py` posts `action="reject"` directly and
passes, which is what let this stand: the route works, and nothing checked
that a person could reach it.

This file asserts the button exists, and asserts it by driving the page -
finding the form, reading the action out of it, and posting what the page
offers rather than what the route accepts.
"""
import re
import unittest

from src import campaigns as campaign_store
from src import workspaces
from tests.webbase import WebTest

REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
CAMPAIGN = "dach-software"


class ARejectIsOffered(WebTest):

    def setUp(self):
        self._campaigns = [dict(c) for c in campaign_store.load()]
        self.session = self.signin(REVIEWER)

    def tearDown(self):
        campaign_store.save(self._campaigns)

    def form(self, body):
        """The one form on the page that decides this campaign."""
        for match in re.finditer(
                r'<form[^>]*action="/approvals/campaign".*?</form>', body,
                re.S):
            if CAMPAIGN in match.group(0):
                return match.group(0)
        return None

    def buttons(self, form):
        return dict(re.findall(
            r'<button[^>]*name="action"[^>]*value="([^"]+)"[^>]*>(.*?)</button>',
            form or "", re.S))

    def page(self):
        status, body, _ = self.session.get("/approvals")
        self.assertEqual(status, 200)
        return body

    # ------------------------------------------------------- the defect

    def test_the_page_offers_both_decisions(self):
        actions = self.buttons(self.form(self.page()))
        self.assertIn("approve", actions)
        self.assertIn("reject", actions,
                      "a reviewer can only say yes: the page renders no way "
                      "to refuse a campaign the route already refuses")

    def test_they_are_in_one_form_so_both_carry_the_fingerprint(self):
        """Rejecting a plan that changed under the reviewer has the same
        staleness problem as approving one, and the guard is the
        fingerprint. A second form would have needed its own."""
        form = self.form(self.page())
        self.assertIn('name="fingerprint"', form)
        self.assertIn('name="csrf"', form)
        self.assertEqual(len(self.buttons(form)), 2)

    def test_only_approve_is_the_primary_action(self):
        """The destructive-looking one should not be the one a reviewer
        hits by pressing return."""
        form = self.form(self.page())
        primary = re.findall(r'<button class="btn primary"[^>]*value="([^"]+)"',
                             form)
        self.assertEqual(primary, ["approve"])

    # -------------------------------------------- and posting it works

    def submit(self, action):
        campaign = campaign_store.get(CAMPAIGN)
        return self.session.post("/approvals/campaign", {
            "csrf": self.session.csrf("/approvals"), "campaign_id": CAMPAIGN,
            "action": action,
            "fingerprint": campaign.get("fingerprint") or ""})

    def test_posting_the_reject_button_rejects_the_campaign(self):
        before = campaign_store.get(CAMPAIGN)["status"]
        self.assertNotEqual(before, "rejected")
        status, body, _ = self.submit("reject")
        self.assertEqual(status, 200, body[:200])
        self.assertNotEqual(campaign_store.get(CAMPAIGN)["status"], "approved")
        self.assertEqual(
            (campaign_store.get(CAMPAIGN).get("approval") or {}).get("action"),
            "reject")

    def test_it_is_audited_as_a_rejection_and_not_as_an_approval(self):
        self.submit("reject")
        mine = [e for e in workspaces.audit(limit=500)
                if e.get("resource_id") == CAMPAIGN
                and str(e.get("action", "")).startswith("campaign.")]
        self.assertTrue(mine)
        self.assertEqual(mine[0]["action"], "campaign.rejected")

    def test_a_viewer_is_offered_neither(self):
        """The button is rendered on a permission, so adding one must not
        have widened who sees them."""
        viewer = self.signin(VIEWER)
        self.assertEqual(viewer.get("/approvals")[0], 403)

    def test_an_approved_campaign_offers_only_the_decision_left(self):
        """The gate that could not fire.

        `state` reads `approval.action`, whose words are "approve" and
        "reject". It is never "approved", so `state != "approved"` was true
        for every campaign in every state and an already-approved one still
        offered Approve. What is offered now is what would change
        something: an approved campaign can be withdrawn, and cannot be
        approved again.
        """
        self.submit("approve")
        self.assertEqual(campaign_store.get(CAMPAIGN)["status"], "approved")
        actions = self.buttons(self.form(self.page()))
        self.assertEqual(sorted(actions), ["reject"])

    def test_a_rejected_campaign_can_still_be_approved(self):
        """The same rule the other way round. A refusal is a decision, not
        a dead end - a reviewer who rejects and reconsiders has somewhere
        to go."""
        self.submit("reject")
        actions = self.buttons(self.form(self.page()))
        self.assertEqual(sorted(actions), ["approve"])

    def test_an_undecided_campaign_offers_both(self):
        """So the two tests above are about the decision, not about the
        page having stopped rendering buttons."""
        self.assertEqual(sorted(self.buttons(self.form(self.page()))),
                         ["approve", "reject"])


class ARejectionIsNotAStaleApproval(WebTest):
    """Found by the test above failing for the wrong reason.

    `approval_is_current` answers False for a rejection on purpose - a
    refusal is not a live approval. `approval_queue` then derived
    `stale = bool(approval) and not current`, so every rejected campaign
    came back stale: tagged "stale" on the approvals page, and counted on
    /diagnostics under "stale approvals" as something needing a reviewer.
    A rejection is a decision that has been made.
    """

    def setUp(self):
        self._campaigns = [dict(c) for c in campaign_store.load()]
        self.session = self.signin(REVIEWER)

    def tearDown(self):
        campaign_store.save(self._campaigns)

    def reject(self):
        campaign = campaign_store.get(CAMPAIGN)
        return self.session.post("/approvals/campaign", {
            "csrf": self.session.csrf("/approvals"), "campaign_id": CAMPAIGN,
            "action": "reject",
            "fingerprint": campaign.get("fingerprint") or ""})

    def queue(self):
        from src.web import api
        from src.repo import Repo
        repo = Repo.for_user(REVIEWER, "productive")
        return {c["campaign_id"]: c
                for c in api.approval_queue(repo)["campaigns"]}

    def test_a_rejected_campaign_is_not_marked_stale(self):
        self.reject()
        self.assertFalse(self.queue()[CAMPAIGN]["stale"])

    def test_and_diagnostics_does_not_count_it_as_one(self):
        from src.web import api
        from src.repo import Repo

        self.reject()
        repo = Repo.for_user(REVIEWER, "productive")
        stale = api.diagnostics(repo)["stale_approvals"]
        self.assertNotIn(CAMPAIGN, [c["campaign_id"] for c in stale])

    def test_an_approval_that_no_longer_fits_its_plan_still_is_stale(self):
        """The state the flag exists for, so the fix did not empty it."""
        campaign = campaign_store.get(CAMPAIGN)
        self.session.post("/approvals/campaign", {
            "csrf": self.session.csrf("/approvals"), "campaign_id": CAMPAIGN,
            "action": "approve",
            "fingerprint": campaign.get("fingerprint") or ""})
        current = campaign_store.get(CAMPAIGN)
        current["approval"] = dict(current["approval"],
                                   fingerprint="a-different-plan")
        campaign_store.save([c if c["campaign_id"] != CAMPAIGN else current
                             for c in campaign_store.load()])
        self.assertTrue(self.queue()[CAMPAIGN]["stale"])


if __name__ == "__main__":
    unittest.main()
