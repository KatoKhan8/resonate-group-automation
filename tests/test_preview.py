"""The preview: it must answer the operator's questions, and change nothing.

Two halves. The first checks the page actually contains what someone needs to
approve or refuse a campaign. The second checks that opening it cannot approve,
launch, push, mutate or call anything - which is the property that makes it
safe to open on a phone at the weekend.
"""
import os
import unittest

from src import campaigns, demo, evidence, preview, store
from tests.campaignbase import CampaignTest


class PreviewTest(CampaignTest):
    def page(self):
        campaign, recs, config = demo.build(self.config)
        return preview.build(campaign, recs, config), campaign, recs, config


class TestItAnswersTheOperatorsQuestions(PreviewTest):
    def test_every_company_appears(self):
        html, _, _, _ = self.page()
        for _, company, _, _, _, _ in demo.COMPANIES:
            self.assertIn(company, html, company)

    def test_why_this_company_is_answerable(self):
        html, _, _, _ = self.page()
        self.assertIn("Provider waterfall", html)
        self.assertIn("industry", html)

    def test_why_this_person_and_this_angle_are_answerable(self):
        html, _, _, _ = self.page()
        self.assertIn("Why this message?", html)
        self.assertIn("Persona", html)
        self.assertIn("Angle", html)

    def test_why_now_and_what_proves_it_are_answerable(self):
        html, _, _, _ = self.page()
        self.assertIn("Freshness", html)
        self.assertIn("Published", html)
        self.assertIn("View source", html)
        self.assertIn("Vienna office", html)

    def test_what_will_actually_be_sent_is_shown(self):
        html, _, _, _ = self.page()
        self.assertIn("quick question about", html)
        self.assertIn("reconciling time", html)

    def test_generated_and_template_copy_are_distinguished(self):
        html, _, _, _ = self.page()
        self.assertIn("LLM", html)
        self.assertIn("template", html)

    def test_verification_and_held_state_are_visible(self):
        html, _, _, _ = self.page()
        self.assertIn("sendable", html)
        self.assertIn("not sendable", html)
        self.assertIn("Verification", html)

    def test_lint_failures_are_visible(self):
        html, _, _, _ = self.page()
        self.assertIn("lint:", html)

    def test_approval_state_is_visible(self):
        html, _, _, _ = self.page()
        self.assertIn("pending approval", html)

    def test_cost_is_shown_and_unknowns_are_named(self):
        html, _, _, _ = self.page()
        self.assertIn("Expected cost", html)
        self.assertIn("unknown", html)

    def test_the_launch_checklist_is_shown(self):
        html, _, _, _ = self.page()
        self.assertIn("Launch checklist", html)
        self.assertIn("blocked", html)

    def test_every_cadence_step_is_shown_not_just_the_first(self):
        html, _, _, _ = self.page()
        for day in ("day 1", "day 3", "day 5", "day 8", "day 10", "day 15",
                    "day 21"):
            self.assertIn(day, html, day)

    def test_both_channels_appear(self):
        html, _, _, _ = self.page()
        self.assertIn(">email<", html)
        self.assertIn(">linkedin<", html)


class TestPersonalizationMetrics(PreviewTest):
    def test_the_summary_counts_each_quality(self):
        html, campaign, recs, config = self.page()
        data = preview.gather(campaign, recs, config)
        totals = data["totals"]
        self.assertGreater(totals["strong"], 0, "the demo has a strong signal")
        self.assertGreater(totals["none"], 0, "and a company with none")
        self.assertIn("coverage_percent", totals)

    def test_company_and_person_signals_are_counted_separately(self):
        _, campaign, recs, config = self.page()
        totals = preview.gather(campaign, recs, config)["totals"]
        self.assertGreater(totals["company_signal"], 0)
        self.assertGreater(totals["person_signal"], 0)

    def test_apify_used_and_skipped_are_both_counted(self):
        _, campaign, recs, config = self.page()
        totals = preview.gather(campaign, recs, config)["totals"]
        self.assertGreater(totals["apify_used"], 0)
        self.assertGreater(totals["apify_skipped"], 0)

    def test_the_average_signal_age_is_known_or_absent_never_invented(self):
        _, campaign, recs, config = self.page()
        totals = preview.gather(campaign, recs, config)["totals"]
        age = totals["average_signal_age_days"]
        self.assertTrue(age is None or isinstance(age, float))

    def test_generated_and_template_steps_are_counted(self):
        _, campaign, recs, config = self.page()
        totals = preview.gather(campaign, recs, config)["totals"]
        self.assertGreater(totals["generated"], 0)
        self.assertGreater(totals["template"], 0)


class TestTheFingerprintBanner(PreviewTest):
    def test_an_unapproved_campaign_says_so(self):
        html, _, _, _ = self.page()
        self.assertIn("Not yet approved", html)

    def test_an_approved_and_unchanged_campaign_says_so(self):
        _, campaign, recs, config = self.page()
        fingerprint = campaigns.fingerprint(campaign, recs, config)
        campaign["approval"] = {"action": "approve", "by": "U0DEMOADMIN1",
                                "fingerprint": fingerprint}
        html = preview.build(campaign, recs, config)
        self.assertIn("Approved, and unchanged", html)
        self.assertNotIn("RE-APPROVAL REQUIRED", html)

    def test_a_changed_campaign_demands_re_approval(self):
        _, campaign, recs, config = self.page()
        campaign["approval"] = {"action": "approve", "by": "U0DEMOADMIN1",
                                "fingerprint": "a-fingerprint-from-yesterday"}
        html = preview.build(campaign, recs, config)
        self.assertIn("CAMPAIGN CHANGED SINCE APPROVAL", html)
        self.assertIn("RE-APPROVAL REQUIRED", html)

    def test_the_fingerprint_shown_is_the_one_approval_uses(self):
        _, campaign, recs, config = self.page()
        data = preview.gather(campaign, recs, config)
        self.assertEqual(data["fingerprint"],
                         campaigns.fingerprint(campaign, recs, config))


class TestFilters(PreviewTest):
    def test_every_filter_has_a_button(self):
        html, _, _, _ = self.page()
        for key, label in preview.FILTERS:
            self.assertIn(f"data-filter='{key}'", html)

    def test_people_carry_the_flags_the_filters_match(self):
        html, _, _, _ = self.page()
        self.assertIn("data-flags=", html)
        for flag in ("champion", "buyer", "email", "linkedin", "strong", "weak"):
            self.assertIn(flag, html, flag)

    def test_the_filtering_is_plain_javascript_with_no_framework(self):
        html, _, _, _ = self.page()
        for framework in ("react", "vue", "angular", "jquery", "cdn."):
            self.assertNotIn(framework, html.lower(), framework)


class TestItChangesNothing(PreviewTest):
    def test_building_it_calls_no_provider(self):
        self.page()
        self.assertEqual(self.cassette.calls, [])

    def test_the_page_has_no_form_and_no_fetch(self):
        html, _, _, _ = self.page()
        for dangerous in ("<form", "fetch(", "XMLHttpRequest", "navigator.send",
                          "method='post'", 'method="post"'):
            self.assertNotIn(dangerous, html, dangerous)

    def test_the_module_imports_nothing_that_can_send(self):
        import inspect
        source = inspect.getsource(preview)
        for banned in ("push.run", "orchestrator.launch", "orchestrator.decide",
                       "slack.post", "providers.request", "campaigns.save",
                       "store.save"):
            self.assertNotIn(banned, source, banned)

    def test_building_it_does_not_write_the_queue(self):
        campaign, recs, config = demo.build(self.config)
        before = os.path.exists(self.queue)
        preview.build(campaign, recs, config)
        self.assertEqual(os.path.exists(self.queue), before)

    def test_a_campaign_is_not_approved_by_being_previewed(self):
        _, campaign, recs, config = self.page()
        self.assertIsNone(campaign.get("approval"))
        self.assertEqual(campaign["status"], "awaiting_approval")

    def test_no_credential_reaches_the_page(self):
        import os as _os
        _os.environ["HEYREACH_KEY"] = "synthetic-preview-key-000111"
        try:
            html, _, _, _ = self.page()
        finally:
            _os.environ.pop("HEYREACH_KEY", None)
        self.assertNotIn("synthetic-preview-key", html)
        for token in ("Bearer", "x-api-key", "token=", "api_key"):
            self.assertNotIn(token, html, token)

    def test_addresses_are_masked_unless_asked_for(self):
        campaign, recs, config = demo.build(self.config)
        masked = preview.build(campaign, recs, config)
        self.assertIn("***@", masked)
        revealed = preview.build(campaign, recs, config, reveal_emails=True)
        self.assertIn("@northwind.test", revealed)

    def test_the_html_is_escaped(self):
        campaign, recs, config = demo.build(self.config)
        recs[0]["company"] = "<script>alert(1)</script>"
        html = preview.build(campaign, recs, config)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestTheDemoCoversTheCases(PreviewTest):
    def test_it_has_at_least_five_companies_and_ten_people(self):
        _, _, recs, _ = self.page()
        self.assertGreaterEqual(len(recs), 5)
        self.assertGreaterEqual(sum(len(r["contacts"]) for r in recs), 10)

    def test_it_contains_every_signal_case(self):
        _, _, recs, _ = self.page()
        qualities = set()
        for rec in recs:
            for entry in rec.get("research") or []:
                qualities.add(entry["quality"])
        self.assertIn(evidence.STRONG, qualities)
        self.assertIn(evidence.UNUSABLE, qualities, "the irrelevant company")
        self.assertTrue(any(not r.get("research") for r in recs),
                        "and one with no signal at all")

    def test_it_contains_a_held_contact_a_dropped_record_and_a_lint_failure(self):
        _, _, recs, _ = self.page()
        self.assertTrue(any(r["state"] == "dropped" for r in recs))
        self.assertTrue(any(not c.get("sendable")
                            for r in recs for c in r["contacts"]))
        html, campaign, recs, config = self.page()
        self.assertIn("lint:", html)

    def test_every_domain_is_fictional(self):
        _, _, recs, _ = self.page()
        for rec in recs:
            self.assertTrue(rec["domain"].endswith(".test"), rec["domain"])
            for contact in rec["contacts"]:
                self.assertTrue(contact["email"].endswith(".test"))


if __name__ == "__main__":
    unittest.main()
