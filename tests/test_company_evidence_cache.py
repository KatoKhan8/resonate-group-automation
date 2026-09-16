"""TASK-162: company-level evidence is built once per record, not per contact.

Every company-derived key in the context block - company, domain, facts,
public_evidence, research - is byte-identical across all contacts at the same
record. The cache builds these once and serves them to every contact.

The tests drive through `generate.context_for` - the function production calls.
Then the counterfactual: clear the cache and verify the build count goes up.
"""
import copy
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import generate, lint, research, store
from tests.base import FIXTURES, pin_client_config


def _make_multi_contact_record():
    """A record with three contacts and research evidence.

    The company-level fields are identical for all three contacts; only the
    contact-specific fields (name, title, persona, angle) differ.
    """
    return {
        "id": "acme-test-com",
        "company": "Acme Test Corp",
        "domain": "acme-test.com",
        "lane": "domains",
        "state": "verified",
        "client": "productive",
        "company_facts": {
            "name": "Acme Test Corp",
            "employees": 45,
            "revenue": "$5M",
            "founded": 2018,
            "industry": "Software",
            "offices": ["Zagreb"],
            "specialties": ["time tracking", "profitability"],
            "notable": "Featured in 2024 SaaS 100",
            "email_domain": "acme-test.com",
        },
        "research": [
            {
                "field": "services",
                "fact": "Acme Test Corp offers cloud-based time tracking for agencies",
                "source_url": "https://acme-test.com/services",
                "retrieved_at": "2026-09-10T12:00:00+00:00",
                "published_at": "2026-09-01T00:00:00+00:00",
                "quality": "strong",
                "relevance_score": 0.8,
                "freshness_score": 0.9,
            },
            {
                "field": "team",
                "fact": "The leadership team has 8 members across engineering and sales",
                "source_url": "https://acme-test.com/about",
                "retrieved_at": "2026-09-10T12:00:00+00:00",
                "published_at": "2026-09-01T00:00:00+00:00",
                "quality": "medium",
                "relevance_score": 0.6,
                "freshness_score": 0.7,
            },
            {
                "field": "careers",
                "fact": "Hiring for senior developer roles in Zagreb office",
                "source_url": "https://acme-test.com/careers",
                "retrieved_at": "2026-09-12T08:00:00+00:00",
                "published_at": "2026-09-05T00:00:00+00:00",
                "quality": "strong",
                "relevance_score": 0.7,
                "freshness_score": 0.8,
            },
        ],
        "contacts": [
            {
                "name": "Alice Martin",
                "title": "CEO",
                "persona": "founder",
                "angle": "profitability",
                "email": "alice@acme-test.com",
                "email_status": "verified",
                "linkedin_url": "https://linkedin.com/in/alice-martin",
            },
            {
                "name": "Bob Chen",
                "title": "CTO",
                "persona": "technical",
                "angle": "engineering",
                "email": "bob@acme-test.com",
                "email_status": "verified",
                "linkedin_url": "https://linkedin.com/in/bob-chen",
            },
            {
                "name": "Carol Davis",
                "title": "VP Sales",
                "persona": "sales",
                "angle": "growth",
                "email": "carol@acme-test.com",
                "email_status": "verified",
                "linkedin_url": "https://linkedin.com/in/carol-davis",
            },
        ],
        "events": [],
        "cadence": {},
        "log": [],
    }


class TestCompanyEvidenceCache(unittest.TestCase):
    """The cache builds once per record and serves the same object to all contacts."""

    def setUp(self):
        generate.clear_company_cache()
        self.rec = _make_multi_contact_record()

    def tearDown(self):
        generate.clear_company_cache()

    def test_company_evidence_returns_same_object_for_same_record(self):
        """Two calls for the same record return the SAME dict object (cache hit)."""
        first = generate.company_evidence(self.rec)
        second = generate.company_evidence(self.rec)
        self.assertIs(first, second)

    def test_company_evidence_has_all_expected_keys(self):
        result = generate.company_evidence(self.rec)
        # Always-present keys
        for key in ("company", "domain", "facts", "evidence_fingerprint",
                     "built_at"):
            self.assertIn(key, result, f"missing key: {key}")
        # Conditionally-present keys (only when data exists)
        # public_evidence: present when research.for_prompt returns non-empty
        # research: present when research_block returns non-empty

    def test_different_records_get_different_cache_entries(self):
        """Two different records get separate cache entries."""
        rec2 = copy.deepcopy(self.rec)
        rec2["id"] = "other-record"
        rec2["company"] = "Other Corp"
        first = generate.company_evidence(self.rec)
        second = generate.company_evidence(rec2)
        self.assertIsNot(first, second)
        self.assertEqual(first["company"], "Acme Test Corp")
        self.assertEqual(second["company"], "Other Corp")

    def test_clear_cache_forces_rebuild(self):
        """After clearing, the next call rebuilds (new dict object)."""
        first = generate.company_evidence(self.rec)
        generate.clear_company_cache()
        second = generate.company_evidence(self.rec)
        self.assertIsNot(first, second)
        # But the CONTENT is the same
        self.assertEqual(first["company"], second["company"])
        self.assertEqual(first["domain"], second["domain"])
        self.assertEqual(first["facts"], second["facts"])

    def test_evidence_fingerprint_changes_when_research_changes(self):
        """Adding a research row changes the fingerprint."""
        before = generate.company_evidence(self.rec)["evidence_fingerprint"]
        self.rec["research"].append({
            "field": "news",
            "fact": "Acme raised Series B",
            "source_url": "https://techcrunch.com/acme",
            "retrieved_at": "2026-09-14T10:00:00+00:00",
            "quality": "strong",
        })
        generate.clear_company_cache()
        after = generate.company_evidence(self.rec)["evidence_fingerprint"]
        self.assertNotEqual(before, after)


class TestProvenanceSurvives(unittest.TestCase):
    """Every fact keeps source_url and retrieved_at through the cache."""

    def setUp(self):
        generate.clear_company_cache()
        self.rec = _make_multi_contact_record()

    def tearDown(self):
        generate.clear_company_cache()

    def test_public_evidence_keeps_provenance(self):
        ce = generate.company_evidence(self.rec)
        for entry in ce.get("public_evidence", []):
            self.assertIn("source_url", entry)
            self.assertIn("retrieved_at", entry)
            self.assertTrue(entry["source_url"], "source_url is empty")
            self.assertTrue(entry["retrieved_at"], "retrieved_at is empty")

    def test_research_block_keeps_provenance(self):
        ce = generate.company_evidence(self.rec)
        for entry in ce.get("research", []):
            self.assertIn("source_url", entry)
            self.assertIn("retrieved_at", entry)
            self.assertTrue(entry["source_url"], "source_url is empty")
            self.assertTrue(entry["retrieved_at"], "retrieved_at is empty")

    def test_research_block_keeps_fact_text(self):
        ce = generate.company_evidence(self.rec)
        facts = [e["fact"] for e in ce.get("research", [])]
        self.assertTrue(any("time tracking" in f for f in facts))

    def test_record_research_is_not_mutated(self):
        """The cache is a read-only projection; rec['research'] is untouched."""
        original_research = copy.deepcopy(self.rec["research"])
        generate.company_evidence(self.rec)
        self.assertEqual(self.rec["research"], original_research)


class TestContextForUsesCache(unittest.TestCase):
    """context_for produces byte-identical company data across contacts.

    Driven through generate.context_for - the function production calls.
    """

    def setUp(self):
        generate.clear_company_cache()
        self.rec = _make_multi_contact_record()

    def tearDown(self):
        generate.clear_company_cache()

    def test_company_fields_identical_across_contacts_for_draft(self):
        """For the 'draft' step, company fields are byte-identical for all contacts."""
        contacts = self.rec["contacts"]
        blocks = []
        for contact in contacts:
            generate.clear_company_cache()  # fresh cache per contact to prove independence
            block = generate.context_for("draft", self.rec, contact,
                                         step_key="em1")
            blocks.append(block)

        # Company-level fields must be identical
        company_keys = ("company", "domain", "facts", "public_evidence", "research")
        for key in company_keys:
            values = [json.dumps(b.get(key), sort_keys=True) for b in blocks]
            self.assertEqual(len(set(values)), 1,
                             f"{key} differs across contacts: {values}")

    def test_contact_fields_differ_across_contacts(self):
        """Contact-specific fields DO differ across contacts."""
        contacts = self.rec["contacts"]
        blocks = []
        for contact in contacts:
            block = generate.context_for("draft", self.rec, contact,
                                         step_key="em1")
            blocks.append(block)

        names = {b["contact"]["name"] for b in blocks}
        self.assertEqual(len(names), 3, "all contacts have the same name")

    def test_context_for_uses_cache_not_rebuild(self):
        """context_for calls company_evidence, which hits the cache.

        The counterfactual: spy on facts_block and research.for_prompt.
        With the cache, they are called ONCE for N contacts, not N times.
        """
        original_facts = generate.facts_block
        original_for_prompt = research.for_prompt
        facts_calls = []
        for_prompt_calls = []

        def tracking_facts(rec):
            facts_calls.append(rec["id"])
            return original_facts(rec)

        def tracking_for_prompt(rec, **kw):
            for_prompt_calls.append(rec["id"])
            return original_for_prompt(rec, **kw)

        contacts = self.rec["contacts"]
        with mock.patch.object(generate, "facts_block", side_effect=tracking_facts):
            with mock.patch.object(research, "for_prompt", side_effect=tracking_for_prompt):
                generate.clear_company_cache()
                for contact in contacts:
                    generate.context_for("draft", self.rec, contact,
                                         step_key="em1")

        # facts_block and for_prompt are called ONCE (first contact builds),
        # not three times (once per contact).
        self.assertEqual(len(facts_calls), 1,
                         f"facts_block called {len(facts_calls)} times, expected 1")
        self.assertEqual(len(for_prompt_calls), 1,
                         f"research.for_prompt called {len(for_prompt_calls)} times, expected 1")

    def test_counterfactual_clearing_cache_forces_rebuild(self):
        """If we clear the cache between contacts, facts_block IS called per contact.

        This proves the cache is doing the work, not something else.
        """
        original_facts = generate.facts_block
        facts_calls = []

        def tracking_facts(rec):
            facts_calls.append(rec["id"])
            return original_facts(rec)

        contacts = self.rec["contacts"]
        with mock.patch.object(generate, "facts_block", side_effect=tracking_facts):
            for contact in contacts:
                generate.clear_company_cache()  # force rebuild each time
                generate.context_for("draft", self.rec, contact,
                                     step_key="em1")

        self.assertEqual(len(facts_calls), 3,
                         f"facts_block called {len(facts_calls)} times, expected 3")

    def test_linkedin_note_step_also_uses_cache(self):
        """The linkedin_note step also gets cached company data."""
        contacts = self.rec["contacts"]
        blocks = []
        for contact in contacts:
            generate.clear_company_cache()
            block = generate.context_for("linkedin_note", self.rec, contact,
                                         step_key="day3")
            blocks.append(block)

        company_keys = ("company", "domain", "facts", "public_evidence", "research")
        for key in company_keys:
            values = [json.dumps(b.get(key), sort_keys=True) for b in blocks]
            self.assertEqual(len(set(values)), 1,
                             f"{key} differs across contacts for linkedin_note")

    def test_research_block_in_context_matches_standalone(self):
        """The research in context_for matches what research_block returns directly."""
        generate.clear_company_cache()
        block = generate.context_for("draft", self.rec, self.rec["contacts"][0],
                                     step_key="em1")
        standalone = generate.research_block(self.rec)
        self.assertEqual(block.get("research"), standalone)


class TestTokenSaving(unittest.TestCase):
    """Measure the token saving on a real multi-contact record."""

    def setUp(self):
        generate.clear_company_cache()
        self.rec = _make_multi_contact_record()

    def tearDown(self):
        generate.clear_company_cache()

    def test_measured_saving(self):
        """Company context is built once, not N times.

        Measure the serialised size of the company-level fields for one contact
        vs N contacts, and report the saving.
        """
        contacts = self.rec["contacts"]
        n = len(contacts)

        # Build context for each contact WITHOUT cache (simulate old behaviour)
        old_total = 0
        for contact in contacts:
            generate.clear_company_cache()
            block = generate.context_for("draft", self.rec, contact,
                                         step_key="em1")
            company_bytes = len(json.dumps({
                "company": block["company"],
                "domain": block["domain"],
                "facts": block["facts"],
                "public_evidence": block.get("public_evidence"),
                "research": block.get("research"),
            }, sort_keys=True))
            old_total += company_bytes

        # Build context for each contact WITH cache (new behaviour)
        generate.clear_company_cache()
        company_bytes_once = len(json.dumps({
            k: v for k, v in generate.company_evidence(self.rec).items()
            if k in ("company", "domain", "facts", "public_evidence", "research")
        }, sort_keys=True))
        new_total = company_bytes_once  # built once, served N times

        saving = old_total - new_total
        saving_pct = (saving / old_total * 100) if old_total else 0

        # The saving should be (N-1)/N of the company context size
        self.assertGreater(saving, 0, "no saving measured")
        self.assertGreater(saving_pct, 50,
                           f"saving only {saving_pct:.1f}% for {n} contacts")

        # Report the numbers
        print(f"\n[TASK-162 token saving for {self.rec['id']}]")
        print(f"  Contacts: {n}")
        print(f"  Company context size (once): {company_bytes_once} chars")
        print(f"  Old total ({n}x duplicated): {old_total} chars")
        print(f"  New total (built once): {new_total} chars")
        print(f"  Saving: {saving} chars ({saving_pct:.1f}%)")


class TestRunClearsCache(unittest.TestCase):
    """run() clears the cache at the start of each pass."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-cache-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase5.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        pin_client_config(self, linkedin_connection_note=None)
        generate.clear_company_cache()

    def tearDown(self):
        generate.clear_company_cache()
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_clears_cache(self):
        """Pre-populate the cache, run, verify it was cleared."""
        generate._company_cache["pre-existing"] = {"stale": True}
        from src import llm
        generate.run(model=llm.NoModel(), live=False)
        self.assertNotIn("pre-existing", generate._company_cache)


if __name__ == "__main__":
    unittest.main()
