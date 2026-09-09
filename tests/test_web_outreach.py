"""The full outreach preview: one campaign, every step, and what would not run.

The property this file protects is that the preview is a preview of *this*
campaign as the engine would run it - not a redrawing of it. Every step, lint
result, eligibility verdict and provider payload on the page came out of
`cadence.build`, `lint.check_step`, `eligibility.decide`, `qa.report` and
`push.payloads`. And nothing on it sends.
"""
import re

from src import store
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"


class ThePreviewRenders(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)

    def test_it_renders_and_picks_a_campaign_by_default(self):
        status, body, _ = self.session.get("/outreach")
        self.assertEqual(status, 200)
        self.assertIn("Full outreach preview", body)
        self.assertIn("Every contact, every step", body)

    def test_a_named_campaign_is_the_one_shown(self):
        status, body, _ = self.session.get("/outreach?campaign=uk-digital")
        self.assertEqual(status, 200)
        self.assertIn("uk-digital", body)

    def test_an_unknown_campaign_says_so_rather_than_erroring(self):
        status, body, _ = self.session.get("/outreach?campaign=not-a-campaign")
        self.assertEqual(status, 200)
        self.assertIn("Nothing to preview", body)
        self.assertNotIn("Traceback", body)

    def test_a_step_that_will_not_run_is_shown_in_place_with_its_reason(self):
        """A timeline that drops its blocked steps shows a different campaign."""
        _, body, _ = self.session.get("/outreach")
        self.assertIn("Why a step would not run", body)
        self.assertIn("what it means", body)

    def test_the_qa_report_and_the_payloads_are_both_on_the_page(self):
        _, body, _ = self.session.get("/outreach")
        self.assertIn("QA report", body)
        self.assertIn("Provider payloads", body)

    def test_the_cap_is_stated_rather_than_silently_applied(self):
        """Showing the first forty and calling it the campaign is worse than
        showing forty and saying so."""
        _, body, _ = self.session.get("/outreach")
        # Either everything fits, or the page says what it left out.
        if "Showing" in body:
            self.assertIn("are counted in every number above", body)

    def test_the_send_window_note_points_at_the_timezone_screen(self):
        _, body, _ = self.session.get("/outreach")
        self.assertIn("/timezones", body)


class NothingOnThisPageSends(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)

    def test_the_page_states_that_nothing_is_sent(self):
        _, body, _ = self.session.get("/outreach")
        self.assertIn("Nothing here is sent", body)
        self.assertIn("push.run(live=True)", body)

    def test_every_payload_carries_delivered_false(self):
        _, body, _ = self.session.get("/outreach")
        self.assertIn("delivered", body)
        self.assertNotIn('"delivered": true', body.lower().replace(" ", " "))

    def test_the_only_form_on_this_screen_is_a_get(self):
        """The campaign chooser reads. Nothing on this page writes anything.

        Checked as "no POST form whose action is this screen" rather than "no
        form at all": a page with a picker is not a page with a button.
        """
        _, body, _ = self.session.get("/outreach")
        posts = re.findall(r'<form[^>]*method="post"[^>]*>', body)
        for form in posts:
            # The workspace switcher lives in the shell on every page.
            self.assertIn("/select-workspace", form)

    def test_a_post_to_the_preview_is_a_404_not_a_send(self):
        status, _, _ = self.session.post(
            "/outreach", {"csrf": self.session.csrf()})
        self.assertEqual(status, 404)


class WhoMaySeeIt(WebTest):

    def test_a_viewer_cannot_reach_the_preview(self):
        """The copy, the gateway reasons and the payloads are internal."""
        viewer = self.signin(VIEWER)
        self.assertEqual(viewer.get("/outreach")[0], 403)

    def test_a_reviewer_can_reach_it(self):
        """Reviewing a campaign means reading what it would say."""
        reviewer = self.signin(REVIEWER)
        status, body, _ = reviewer.get("/outreach")
        self.assertEqual(status, 200)
        self.assertIn("Full outreach preview", body)


class ThePreviewCannotCrossAWorkspace(WebTest):

    def test_another_workspaces_campaign_is_not_previewable(self):
        session = self.signin(OPERATOR)
        status, body, _ = session.get("/outreach?campaign=apac-recruiting")
        # Either not found, or - never - somebody else's contacts.
        self.assertIn(status, (200, 404))
        for rec in store.load():
            if rec.get("client") != "productive":
                self.assertNotIn(rec["id"], body)

    def test_the_campaign_picker_lists_only_this_workspace(self):
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/outreach")
        options = re.findall(r'<option value="([^"]+)"', body)
        mine = {c.get("campaign_id") for c in
                __import__("src.campaigns", fromlist=["load"]).load()
                if c.get("client") == "productive"}
        theirs = {c.get("campaign_id") for c in
                  __import__("src.campaigns", fromlist=["load"]).load()
                  if c.get("client") != "productive"}
        for option in options:
            self.assertNotIn(option, theirs)
        self.assertTrue(set(options) & mine)


class TheNumbersAddUp(WebTest):
    """A summary is a claim; the cards underneath are the evidence for it."""

    def test_would_run_plus_would_not_equals_every_step(self):
        from src import repo as repo_module
        from src.web import api
        repo = repo_module.Repo.for_user(OPERATOR, "productive")
        data = api.full_outreach(repo, "uk-digital")
        totals = data["totals"]
        self.assertEqual(totals["will_run"] + totals["blocked"],
                         totals["steps"])
        self.assertEqual(totals["email_steps"] + totals["linkedin_steps"],
                         totals["steps"])

    def test_every_blocked_reason_names_a_gate_the_engine_knows(self):
        from src import repo as repo_module
        from src.web import api
        repo = repo_module.Repo.for_user(OPERATOR, "productive")
        data = api.full_outreach(repo, "uk-digital")
        for row in data["blocked_reasons"]:
            self.assertTrue(row["reason"])
            self.assertIsInstance(row["steps"], int)
            self.assertIn("means", row)

    def test_the_omitted_count_is_the_difference_not_a_guess(self):
        from src import repo as repo_module
        from src.web import api
        repo = repo_module.Repo.for_user(OPERATOR, "productive")
        data = api.full_outreach(repo, "uk-digital", cap=2)
        self.assertEqual(data["shown"], min(2, data["totals"]["contacts"]))
        self.assertEqual(data["omitted"],
                         data["totals"]["contacts"] - data["shown"])


class ThePayloadPreviewExplainsARefusalRatherThanRaising(WebTest):
    """`push.payloads` refuses by raising - correct for a sender, fatal for
    a screen.

    The campaign-level guards (freeze, rejection, already launched,
    approval, provider mapping) used to be skipped at the payload gate
    because nothing handed it a campaign. Once it had one, an unapproved
    demo campaign refused every item and this page raised instead of
    saying so.
    """

    def preview(self):
        from src import repo as repo_module
        from src.web import api

        repo = repo_module.Repo.for_user(OPERATOR, "productive")
        return api.provider_preview(repo, "uk-digital")

    def test_the_page_still_renders(self):
        self.assertIsNotNone(self.preview())

    def test_the_payload_is_empty_from_refusal_and_not_from_emptiness(self):
        """`ready` is zero either way, so zero on its own proves nothing.

        What proves it is that the collector found steps to send and every
        one of them was stopped at the gate for a campaign reason.
        """
        from src import push, repo as repo_module

        repo = repo_module.Repo.for_user(OPERATOR, "productive")
        campaign = repo.campaign("uk-digital")
        ids = set(campaign.get("record_ids") or [])
        collected = [item for item in
                     push.collect(repo.records(), day=21, client=repo.client,
                                  campaign_rows=[campaign])[0]
                     if item["record"]["id"] in ids]
        self.assertTrue(collected, "nothing was collected; the fixture is "
                                   "hollow and every assertion here is too")

        found = self.preview()
        self.assertEqual(found["ready"], 0)
        refused = [row for row in found["skipped"]
                   if "campaign" in str(row.get("why"))]
        self.assertEqual(len(refused), len(collected))

    def test_the_reason_is_shown_beside_the_other_exclusions(self):
        found = self.preview()
        reasons = " ".join(str(row.get("why")) for row in found["skipped"])
        self.assertIn("campaign", reasons)

    def test_the_rendered_panel_names_it(self):
        from src.web import pages

        html = pages.provider_previews(self.preview())
        self.assertIn("Excluded from the executable payload", html)
        self.assertIn("campaign", html)
