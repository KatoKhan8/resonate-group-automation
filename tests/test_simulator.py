"""The dress rehearsal: everything a campaign would do, and none of it done.

Two properties carry this file. The simulator must send nothing and call
nothing - asserted against the cassette and against the source. And it must not
compute its own verdicts: every number it shows has to match the module that
owns the decision, or the preview stops describing the run it is previewing.
"""
import csv
import inspect
import json
import os
import unittest

from src import (channels, campaigns, clients, eligibility, lint, mx, plan,
                 previewpage, quality, simulator, store, synthetic)
from tests.campaignbase import CampaignTest


class SimulatorTest(CampaignTest):
    SIZE = 56

    def seeded(self):
        recs = synthetic.dataset(self.SIZE, self.config)
        store.save(recs)
        return store.load()

    def result(self, recs=None):
        recs = recs if recs is not None else self.seeded()
        return simulator.simulate(recs=recs, client="demo", config=self.config)


class TestItSendsNothing(SimulatorTest):
    def test_would_send_is_zero(self):
        self.assertEqual(self.result()["would_send"], 0)

    def test_no_provider_was_called(self):
        self.result()
        self.assertEqual(self.cassette.calls, [])

    def test_the_source_contains_no_path_to_a_provider(self):
        for module in (simulator, previewpage):
            source = inspect.getsource(module)
            for banned in ("push.run", "providers.request", "live=True",
                           "bison.", "heyreach.", "slack.post"):
                self.assertNotIn(banned, source, f"{module.__name__}: {banned}")

    def test_it_writes_nothing_to_the_queue(self):
        recs = self.seeded()
        before = json.dumps(recs, sort_keys=True)
        simulator.simulate(recs=recs, client="demo", config=self.config)
        self.assertEqual(json.dumps(store.load(), sort_keys=True), before)


class TestTheHeadline(SimulatorTest):
    def test_every_headline_number_the_brief_asks_for_is_present(self):
        headline = self.result()["headline"]
        for name in ("companies", "contacts", "email_eligible",
                     "linkedin_eligible", "multichannel", "held", "mx_blocked",
                     "lint_failures", "estimated_credits", "approval_state"):
            self.assertIn(name, headline, name)

    def test_accepted_and_rejected_companies_add_up(self):
        headline = self.result()["headline"]
        self.assertEqual(headline["companies_accepted"]
                         + headline["companies_rejected"],
                         headline["companies"])

    def test_the_channel_counts_match_the_channels_module(self):
        recs = self.seeded()
        result = self.result(recs)
        coverage = channels.summarise(recs, self.config)
        self.assertEqual(result["headline"]["email_eligible"],
                         coverage["email_eligible"])
        self.assertEqual(result["headline"]["multichannel"],
                         coverage[channels.MULTICHANNEL])

    def test_the_mx_count_matches_the_mx_module(self):
        recs = self.seeded()
        result = self.result(recs)
        self.assertEqual(result["headline"]["mx_blocked"],
                         mx.summarise(recs, self.config)["blocked"])

    def test_the_personalisation_bands_match_the_quality_module(self):
        recs = self.seeded()
        result = self.result(recs)
        self.assertEqual(result["personalization"]["bands"],
                         quality.distribution(recs, self.config)["bands"])

    def test_the_sizing_matches_the_plan_module(self):
        recs = self.seeded()
        result = self.result(recs)
        self.assertEqual(result["sizing"], plan.size(None, recs, self.config))

    def test_with_no_campaign_the_approval_state_says_so(self):
        self.assertEqual(self.result()["approval"]["state"], "no_campaign")


class TestTheContactCard(SimulatorTest):
    def card(self, shape="clean_multichannel"):
        recs = self.seeded()
        rec_id = recs[synthetic.indices_of(shape, self.SIZE)[0]]["id"]
        result = self.result(recs)
        company = next(c for c in result["companies"]
                       if c["record_id"] == rec_id)
        return company["cards"][0]

    def test_it_carries_every_field_the_brief_lists(self):
        card = self.card()
        for field in ("company", "name", "title", "persona", "email",
                      "email_verification", "mx_provider", "email_eligible",
                      "linkedin", "linkedin_eligible", "why_this_person",
                      "why_this_company", "company_research",
                      "person_research", "personalization_evidence",
                      "timeline"):
            self.assertIn(field, card, field)

    def test_an_excluded_channel_carries_a_code_and_a_sentence(self):
        card = self.card("gateway_proofpoint")
        self.assertFalse(card["email_eligible"])
        self.assertEqual(card["email_excluded_reason"],
                         "mx_protection:proofpoint")
        self.assertIn("Proofpoint", card["email_excluded_explained"])

    def test_the_quality_band_travels_with_its_components(self):
        card = self.card()
        block = card["personalization_quality"]
        self.assertIn(block["band"], quality.BANDS)
        self.assertEqual(sorted(block["components"]),
                         sorted(quality.COMPONENTS))

    def test_a_company_found_but_not_selected_says_why(self):
        recs = self.seeded()
        result = self.result(recs)
        listed = [c for company in result["companies"]
                  for c in company["not_selected"]]
        for entry in listed:
            self.assertTrue(entry["reason"])


class TestTheTimeline(SimulatorTest):
    def timeline(self, shape="clean_multichannel"):
        recs = self.seeded()
        rec_id = recs[synthetic.indices_of(shape, self.SIZE)[0]]["id"]
        result = self.result(recs)
        company = next(c for c in result["companies"]
                       if c["record_id"] == rec_id)
        return company["cards"][0]["timeline"]

    def test_every_configured_step_appears(self):
        from src import cadence
        steps = {row["step"] for row in self.timeline()}
        self.assertEqual(steps, {spec["key"] for spec in cadence.STEPS})

    def test_it_is_in_day_order(self):
        days = [row["day"] or 0 for row in self.timeline()]
        self.assertEqual(days, sorted(days))

    def test_the_timeline_is_never_silently_compressed(self):
        """A gateway removes the email steps from the run, not from the page."""
        timeline = self.timeline("gateway_proofpoint")
        email_steps = [row for row in timeline if row["channel"] == "email"]
        self.assertTrue(email_steps)
        for row in email_steps:
            self.assertNotEqual(row["status"], "eligible")

    def test_a_skipped_step_carries_its_reason(self):
        timeline = self.timeline("gateway_proofpoint")
        skipped = [row for row in timeline
                   if row["status"] in ("skipped", "blocked")]
        self.assertTrue(skipped)
        for row in skipped:
            self.assertTrue(row["reason"] or row["blocked_by"], row)

    def test_both_channels_are_linted_after_expansion(self):
        timeline = self.timeline()
        linkedin = [row for row in timeline if row["channel"] == "linkedin"]
        self.assertTrue(linkedin)
        for row in linkedin:
            self.assertIn("lint", row)
            self.assertIn(row["lint_verdict"], ("clean", "held", "failed"))

    def test_the_copy_shown_is_the_copy_that_would_be_sent(self):
        timeline = self.timeline()
        emails = [row for row in timeline
                  if row["channel"] == "email" and row["subject"]]
        self.assertTrue(emails)
        for row in emails:
            self.assertTrue(row["body"])


class TestTheQAMetrics(SimulatorTest):
    def test_every_metric_the_brief_asks_for_is_present(self):
        qa = simulator.qa_metrics(self.result())
        for name in ("lint_pass_rate", "verified_email_rate",
                     "mx_exclusion_rate", "linkedin_coverage",
                     "multichannel_coverage", "personalization_bands",
                     "held_count", "research_failure_count",
                     "identity_ambiguity_count"):
            self.assertIn(name, qa, name)

    def test_rates_are_none_rather_than_zero_with_nothing_to_divide(self):
        qa = simulator.qa_metrics(simulator.simulate(recs=[], client="demo",
                                                     config=self.config))
        self.assertIsNone(qa["lint_pass_rate"])
        self.assertIsNone(qa["verified_email_rate"])

    def test_the_lint_pass_rate_is_a_share_of_steps_considered(self):
        qa = simulator.qa_metrics(self.result())
        self.assertGreaterEqual(qa["lint_pass_rate"], 0.0)
        self.assertLessEqual(qa["lint_pass_rate"], 1.0)
        self.assertGreater(qa["steps_considered"], 0)

    def test_nothing_is_hidden_behind_a_single_score(self):
        qa = simulator.qa_metrics(self.result())
        self.assertNotIn("score", qa)
        self.assertNotIn("overall", qa)


class TestTheSlackPreview(SimulatorTest):
    def preview(self):
        campaign, recs, _ = self.approved_campaign()
        recs = store.load()
        result = simulator.simulate(recs=recs, campaign=campaign,
                                    config=self.config)
        return simulator.slack_preview(result, campaign, self.config), campaign

    def test_it_is_built_and_not_delivered(self):
        payload, _ = self.preview()
        self.assertFalse(payload["delivered"])
        self.assertIn("preview", payload["why_not_delivered"])

    def test_nothing_reached_slack(self):
        self.preview()
        self.assertEqual(self.cassette.calls, [])

    def test_it_summarises_what_the_brief_asks_for(self):
        payload, _ = self.preview()
        joined = " ".join(payload["preview_lines"])
        for word in ("email eligible", "linkedin eligible", "multichannel",
                     "held", "MX excluded", "lint failures", "personalisation",
                     "estimated credits"):
            self.assertIn(word, joined, word)

    def test_the_qa_block_travels_with_it(self):
        payload, _ = self.preview()
        self.assertIn("lint_pass_rate", payload["qa"])

    def test_the_existing_approval_actions_are_still_there(self):
        payload, _ = self.preview()
        self.assertTrue(payload.get("actions"))


class TestTheReportingPreview(SimulatorTest):
    def test_pre_send_metrics_are_zero_not_missing(self):
        report = simulator.reporting_preview(self.result())
        for name in ("emails_sent", "linkedin_actions", "replies",
                     "positive_replies"):
            self.assertEqual(report[name], 0, name)

    def test_unobservable_metrics_are_none_not_zero(self):
        report = simulator.reporting_preview(self.result())
        self.assertIsNone(report["meetings"])

    def test_it_reports_what_has_actually_been_produced(self):
        report = simulator.reporting_preview(self.result())
        self.assertGreater(report["emails_generated"], 0)
        self.assertGreater(report["contacts_found"], 0)

    def test_personas_are_counted(self):
        report = simulator.reporting_preview(self.result())
        self.assertIn("champion", report["personas"])


class TestTheFiveFiles(SimulatorTest):
    def written(self, reveal=False, max_cards=previewpage.MAX_CARDS):
        out = os.path.join(self.tmp, "out")
        return previewpage.write_all(self.result(), out, reveal,
                                     max_cards), out

    def test_all_five_are_written(self):
        paths, _ = self.written()
        for name in previewpage.FILES:
            self.assertTrue(os.path.exists(paths[name]), name)

    def test_every_filename_says_preview(self):
        """So none of them is ever mistaken for something to upload."""
        for name in previewpage.FILES:
            self.assertIn("preview", name)

    def test_the_json_holds_every_card_even_when_the_page_does_not(self):
        paths, _ = self.written(max_cards=5)
        with open(paths["preview.json"], encoding="utf-8") as f:
            data = json.load(f)
        cards = sum(len(c["cards"]) for c in data["companies"])
        self.assertGreater(cards, 5)

    def test_the_page_says_what_it_left_out(self):
        paths, _ = self.written(max_cards=5)
        with open(paths["preview.html"], encoding="utf-8") as f:
            page = f.read()
        self.assertIn("are not shown on this page", page)

    def test_addresses_are_masked_by_default(self):
        recs = self.seeded()
        paths, _ = self.written()
        with open(paths["preview.html"], encoding="utf-8") as f:
            page = f.read()
        address = next(c["email"] for r in recs for c in r["contacts"]
                       if c.get("email"))
        self.assertNotIn(address, page)

    def test_hostile_names_cannot_execute_in_the_csv(self):
        paths, _ = self.written()
        with open(paths["emailbison-preview.csv"], encoding="utf-8",
                  newline="") as f:
            rows = list(csv.reader(f))
        from src import export
        for row in rows:
            for cell in row:
                self.assertFalse(cell[:1] in export.FORMULA_LEADERS, cell[:40])

    def test_hostile_names_cannot_escape_the_html(self):
        paths, _ = self.written()
        with open(paths["preview.html"], encoding="utf-8") as f:
            page = f.read()
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("onerror=alert", page)

    def test_the_heyreach_preview_cannot_be_posted_as_it_stands(self):
        paths, _ = self.written()
        with open(paths["heyreach-preview.json"], encoding="utf-8") as f:
            payload = json.load(f)
        self.assertTrue(payload["preview"])
        self.assertIsNone(payload["campaign_id"])
        self.assertEqual(payload["would_send"], 0)

    def test_the_heyreach_preview_carries_the_linkedin_steps(self):
        paths, _ = self.written()
        with open(paths["heyreach-preview.json"], encoding="utf-8") as f:
            payload = json.load(f)
        self.assertTrue(payload["leads"])
        self.assertTrue(payload["leads"][0]["steps"])

    def test_the_report_page_distinguishes_zero_from_unobservable(self):
        paths, _ = self.written()
        with open(paths["report-preview.html"], encoding="utf-8") as f:
            page = f.read()
        self.assertIn("not observable by this system", page)
        self.assertIn("emails sent", page)

    def test_the_page_states_that_nothing_was_sent(self):
        paths, _ = self.written()
        with open(paths["preview.html"], encoding="utf-8") as f:
            page = f.read()
        self.assertIn("Nothing here has been sent", page)


if __name__ == "__main__":
    unittest.main()
