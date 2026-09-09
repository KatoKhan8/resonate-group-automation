"""Audit for the research, evidence and preview layer.

Written from the position of someone trying to make this system spend money it
should not, say something it cannot support, or leak something it holds.
"""
import json
import os
import re
import unittest

from src import (claims, demo, evidence, linkedin, personalization, preview,
                 store)
from src.providers import apify, heyreach
from tests.campaignbase import CampaignTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def source_files():
    for root, _, files in os.walk(os.path.join(ROOT, "src")):
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.join(root, name)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestNoResearchWithoutAReason(CampaignTest):
    def enabled(self, **over):
        config = dict(self.config)
        config["research"] = {"recent_signals": {"enabled": True, **over}}
        return config

    def test_a_reason_outside_the_documented_set_cannot_appear(self):
        rec = self.seed_records()[0]
        for reason in personalization.gaps(rec, None, self.enabled()):
            self.assertIn(reason, personalization.GAPS)

    def test_curiosity_is_not_a_reason(self):
        """A record with everything answered plans nothing, whatever is left
        in the budget."""
        rec = self.seed_records()[0]
        rec["research"] = [evidence.make(
            "Acme is hiring a delivery manager to improve utilisation.",
            "https://acme.test/careers", "careers_page", "apify", "acme",
            published_at="2026-08-20", angle_words=["utilisation"],
            today="2026-08-26")]
        personalization.mark_company_done(rec)
        for contact in personalization.selected_contacts(rec, self.enabled()):
            personalization.mark_person_done(rec, contact["key"])
        self.assertEqual(personalization.plan(rec, self.enabled())["planned_calls"], 0)

    def test_the_cap_cannot_be_exceeded_by_asking_twice(self):
        rec = self.seed_records()[0]
        config = self.enabled(max_people_per_company=1)
        for _ in range(5):
            plan = personalization.plan(rec, config)
            self.assertLessEqual(len(plan["people"]), 1)

    def test_a_negative_cap_is_read_as_none(self):
        rec = self.seed_records()[0]
        plan = personalization.plan(rec, self.enabled(max_people_per_company=-5))
        self.assertEqual(plan["people"], [])

    def test_a_nonsense_cap_falls_back_to_the_default(self):
        settings = personalization.settings(
            {"research": {"recent_signals": {"enabled": True,
                                             "max_people_per_company": "lots"}}})
        self.assertEqual(settings["max_people_per_company"],
                         personalization.DEFAULTS["max_people_per_company"])


class TestScrapeScopeAndSSRF(CampaignTest):
    def test_apify_still_refuses_a_private_address(self):
        for url in ("http://127.0.0.1/admin", "http://192.168.1.1/",
                    "http://169.254.169.254/latest/meta-data/",
                    "http://[::1]/", "http://10.0.0.5/"):
            with self.assertRaises(Exception, msg=url):
                apify.check_url(url)

    def test_the_page_ceiling_is_still_hard(self):
        self.assertLessEqual(apify.MAX_PAGES, 10)
        self.assertLessEqual(apify.MAX_ITEMS, 50)

    def test_a_client_cannot_raise_the_hard_ceiling(self):
        config = {"research": {"apify": {"enabled": True,
                                         "max_pages_per_domain": 10_000,
                                         "max_items_per_run": 10_000,
                                         "max_text_chars_per_page": 10_000_000}}}
        settings = apify.settings(config)
        self.assertLessEqual(settings["max_pages_per_domain"], apify.MAX_PAGES)
        self.assertLessEqual(settings["max_items_per_run"], apify.MAX_ITEMS)
        self.assertLessEqual(settings["max_text_chars_per_page"],
                             apify.MAX_TEXT_CHARS)

    def test_research_is_disabled_by_default_for_every_existing_client(self):
        from src import clients
        for name in ("productive",):
            self.assertFalse(personalization.settings(clients.load(name))["enabled"],
                             name)


class TestEvidenceHonesty(CampaignTest):
    def test_a_date_is_never_invented(self):
        entry = evidence.make("Acme opened an office.", "https://acme.test/n",
                              "news", "apify", "acme", published_at=None,
                              today="2026-08-26")
        self.assertIsNone(entry["published_at"])
        self.assertIsNone(entry["age_days"])
        self.assertEqual(entry["freshness_bucket"], evidence.UNKNOWN)

    def test_an_undated_signal_never_counts_as_recent(self):
        entry = evidence.make("Acme opened a Vienna office.", "https://x.test",
                              "news", "apify", "acme", published_at=None,
                              today="2026-08-26")
        self.assertNotEqual(entry["freshness_bucket"], evidence.HIGH)

    def test_stale_evidence_is_bucketed_not_hidden(self):
        entry = evidence.make("Acme opened a Vienna office.", "https://x.test",
                              "news", "apify", "acme",
                              published_at="2020-01-01", today="2026-08-26")
        self.assertEqual(entry["freshness_bucket"], evidence.BACKGROUND)

    def test_the_scores_are_deterministic(self):
        args = ("Acme is hiring five implementation managers.",
                "https://acme.test/careers", "careers_page", "apify", "acme")
        first = evidence.make(*args, published_at="2026-08-20", today="2026-08-26")
        second = evidence.make(*args, published_at="2026-08-20", today="2026-08-26")
        self.assertEqual(first, second)

    def test_no_module_asks_a_model_what_evidence_is_worth(self):
        """Scoring is arithmetic over the client's own vocabulary. The proof
        is that it imports nothing that could ask, and scores identically on
        repeated calls with no model available."""
        import inspect
        source = inspect.getsource(evidence)
        for banned in ("from . import llm", "import llm", "openai",
                       "anthropic", "requests.post", "urlopen"):
            self.assertNotIn(banned, source, banned)
        args = ("Acme is hiring five delivery managers.", "https://acme.test/c",
                "careers_page", "apify", "acme")
        scores = {evidence.make(*args, published_at="2026-08-20",
                                today="2026-08-26")["relevance_score"]
                  for _ in range(5)}
        self.assertEqual(len(scores), 1)


class TestNoRawScrapePersistence(CampaignTest):
    def test_only_normalised_evidence_is_stored(self):
        campaign, recs, config = demo.build(self.config)
        for rec in recs:
            for entry in rec.get("research") or []:
                self.assertLessEqual(len(entry.get("fact") or ""), 600)
                for banned in ("html", "raw", "body_html", "markdown", "dom"):
                    self.assertNotIn(banned, entry, banned)

    def test_the_working_directory_is_gitignored(self):
        import subprocess
        for path in ("work/apify/raw.json", "out/campaign-preview.html"):
            result = subprocess.run(["git", "check-ignore", "-v", path],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, path)

    def test_every_company_and_address_is_fictional(self):
        """linkedin.com appears in profile URLs and should; what must never
        appear is a real company domain or a real address."""
        campaign, recs, config = demo.build(self.config)
        for rec in recs:
            self.assertTrue(rec["domain"].endswith(".test"), rec["domain"])
            for contact in rec["contacts"]:
                self.assertTrue(contact["email"].endswith(".test"))
            for entry in rec.get("research") or []:
                url = entry.get("source_url") or ""
                self.assertRegex(url, r"^https://[a-z]+\.test/", url)


class TestClaimsCannotBeBypassed(CampaignTest):
    def test_there_is_no_function_that_edits_a_sentence(self):
        source = read(os.path.join(ROOT, "src", "claims.py"))
        for banned in ("def patch", "def fix", "def soften", "def rewrite",
                       ".replace(sentence"):
            self.assertNotIn(banned, source, banned)

    def test_an_unsupported_claim_raises_rather_than_returning_a_fixed_step(self):
        rec = self.seed_records()[0]
        step = {"subject": "hi", "body": "You raised a Series C last month."}
        original = dict(step)
        with self.assertRaises(claims.UnsupportedClaim):
            claims.require(step, rec)
        self.assertEqual(step, original)

    def test_evidence_from_another_record_does_not_support_this_one(self):
        rec = self.seed_records()[0]
        other = evidence.make("Borealis opened a Vienna office.",
                              "https://borealis.test/n", "news", "apify",
                              "borealis", published_at="2026-08-20",
                              today="2026-08-26")
        problems = claims.check("You raised a Series B.", rec, chosen=[other])
        self.assertTrue(problems)


class TestPreviewCannotAct(CampaignTest):
    def test_it_imports_nothing_that_mutates(self):
        source = read(os.path.join(ROOT, "src", "preview.py"))
        for banned in ("store.save", "campaigns.save", "orchestrator.decide",
                       "orchestrator.launch", "push.run", "slack.post",
                       "poller.run", "inbound.ingest"):
            self.assertNotIn(banned, source, banned)

    def test_it_makes_no_provider_call(self):
        campaign, recs, config = demo.build(self.config)
        preview.build(campaign, recs, config)
        self.assertEqual(self.cassette.calls, [])

    def test_the_page_contains_no_authenticated_link(self):
        campaign, recs, config = demo.build(self.config)
        html = preview.build(campaign, recs, config)
        # Built rather than written out: tests/test_fixture_hygiene.py forbids
        # a real domain literal in test data, and it is right to.
        from src.providers import bison, contactout, heyreach, apify
        for base in (contactout.BASE, heyreach.BASE, apify.BASE, bison.base()):
            host = base.split("//", 1)[-1].split("/", 1)[0]
            self.assertNotIn(host, html, host)

    def test_source_links_are_public_pages_only(self):
        campaign, recs, config = demo.build(self.config)
        html = preview.build(campaign, recs, config)
        for url in re.findall(r"href='([^']+)'", html):
            self.assertFalse(url.startswith("file:"), url)
            self.assertNotIn("token", url)
            self.assertNotIn("api_key", url)


class TestIdentityIsNeverFuzzy(CampaignTest):
    def test_no_module_matches_a_person_by_name(self):
        for path in source_files():
            source = read(path)
            for banned in ("SequenceMatcher", "difflib", "rapidfuzz",
                           "thefuzz", "levenshtein"):
                self.assertNotIn(banned, source, f"{path}: {banned}")

    def test_a_near_miss_url_never_matches(self):
        self.assertFalse(linkedin.same_profile(
            "https://www.linkedin.com/in/jan-novak",
            "https://www.linkedin.com/in/jan-novak-2"))

    def test_custom_fields_are_not_assumed_to_round_trip(self):
        """Confirmed live: they do not. Nothing may depend on them."""
        source = read(os.path.join(ROOT, "src", "adapters.py"))
        self.assertIn("customFields", source)
        # The adapter reads them if present but never requires them.
        campaign, recs, config = demo.build(self.config)
        from src import adapters
        page = {"items": [{"id": "t", "correspondentProfile":
                           {"profileUrl": "https://www.linkedin.com/in/x",
                            "customFields": []},
                           "messages": [{"sender": "CORRESPONDENT", "body": "hi",
                                         "createdAt": "2026-08-26T10:00:00Z"}]}]}
        mapped = adapters.from_heyreach(page)
        self.assertEqual(len(mapped), 1)
        self.assertIsNone(mapped[0].get("record_id"))
        self.assertTrue(mapped[0].get("linkedin"))

    def test_the_day_eight_step_still_requires_a_real_acceptance(self):
        from src import cadence
        spec = next(s for s in cadence.STEPS if s["key"] == "day8")
        self.assertEqual(spec.get("requires"), cadence.ACCEPT_EVENT)
        self.assertFalse(heyreach.CONNECTION_STATUS_AVAILABLE)


class TestNoLiveCallsAnywhereInResearch(CampaignTest):
    def test_the_new_modules_reach_no_provider_on_import_or_use(self):
        campaign, recs, config = demo.build(self.config)
        for rec in recs:
            personalization.plan(rec, config)
            personalization.apply(rec, config)
        preview.build(campaign, recs, config)
        self.assertEqual(self.cassette.calls, [])

    def test_no_llm_is_called_by_the_research_layer(self):
        for name in ("evidence.py", "personalization.py", "claims.py",
                     "preview.py", "demo.py"):
            source = read(os.path.join(ROOT, "src", name))
            self.assertNotIn("llm.run", source, name)
            self.assertNotIn("llm.complete", source, name)


if __name__ == "__main__":
    unittest.main()
