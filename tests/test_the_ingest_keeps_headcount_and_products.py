"""TASK-348: the ingest carries headline, industry, headcount and products.

A CSV row with positioning and headcount columns must survive the ingest
with those values on company_facts, and a pack built from that record must
expose them as facts with the CSV named as source and verification set to
client-provided - never verified research.
"""
import os
import unittest

from src import ingest, packfacts, store
from tests.base import QueueTest


class TestInestCarriesHeadlineAndIndustry(QueueTest):
    """The Productive CSV has Headline and Industry; they must reach company_facts."""

    def _run(self, csv_lines):
        path = self.write_csv("productive.csv", csv_lines)
        result = ingest.run(path, client="productive", lane="domains")
        return result, store.load()

    def test_headline_and_industry_survive_ingest(self):
        _, recs = self._run([
            "company,domain,headline,industry",
            "Acme,acme.test,SEO & paid media at scale,Marketing & Advertising",
        ])
        self.assertEqual(len(recs), 1)
        facts = recs[0]["company_facts"]
        self.assertEqual(facts.get("headline"), "SEO & paid media at scale")
        self.assertEqual(facts.get("industry"), "Marketing & Advertising")

    def test_empty_columns_are_not_carried(self):
        _, recs = self._run([
            "company,domain,headline,industry",
            "Acme,acme.test,,",
        ])
        facts = recs[0]["company_facts"]
        self.assertNotIn("headline", facts)
        self.assertNotIn("industry", facts)

    def test_headcount_columns_are_carried_when_present(self):
        _, recs = self._run([
            "company,domain,company_employee_count,company_size,"
            "company_total_headcount_growth_12_months,company_product_and_services",
            "Acme,acme.test,42,11-50,35%,"
            "SEO; PPC; content marketing",
        ])
        facts = recs[0]["company_facts"]
        self.assertEqual(facts.get("headcount"), "42")
        self.assertEqual(facts.get("employee_range"), "11-50")
        self.assertEqual(facts.get("headcount_growth_12m"), "35%")
        self.assertEqual(facts.get("products"), "SEO; PPC; content marketing")

    def test_dropped_rows_also_carry_their_facts(self):
        """A row dropped for no domain still has its facts for auditability."""
        _, recs = self._run([
            "company,domain,headline,industry",
            "Acme,,SEO specialist,Marketing",
        ])
        self.assertEqual(recs[0]["state"], "dropped")
        self.assertEqual(recs[0]["company_facts"].get("headline"),
                         "SEO specialist")


class TestGuardFailsWhenMappingBroken(QueueTest):
    """The guard: if INGEST_TO_FACTS loses a key, the normal test fails.

    This is demonstrated externally (break the mapping, run the suite,
    restore, run again) rather than caught inside a test - a test that
    expects its own assertion to fail is not a guard, it is a no-op.
    """

    def test_headline_is_in_facts_when_mapping_is_intact(self):
        """This is the guard.  Remove 'headline' from INGEST_TO_FACTS and
        this test fails.  That is the whole point."""
        path = self.write_csv("guard.csv", [
            "company,domain,headline,industry",
            "Acme,acme.test,SEO at scale,Marketing",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        facts = recs[0]["company_facts"]
        self.assertIn("headline", facts)
        self.assertIn("industry", facts)


class TestPackExposesIngestFactsWithSource(QueueTest):
    """A pack built from an ingested record exposes facts WITH a source."""

    def test_pack_includes_ingest_facts_with_batch_source(self):
        path = self.write_csv("source.csv", [
            "company,domain,headline,industry",
            "Acme,acme.test,SEO at scale,Marketing",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        pack, _ = packfacts.pack_for(recs[0])
        ingest_facts = [f for f in pack["facts"]
                        if f.get("fact_key") in packfacts.INGEST_FACT_KEYS]
        self.assertTrue(ingest_facts, "no ingest facts in the pack")
        for fact in ingest_facts:
            self.assertEqual(fact["verification"], "client-provided")
            self.assertIn("source.csv", fact["source"])

    def test_no_fabricated_provenance(self):
        """A fact from a client CSV is NOT marked as verified research."""
        path = self.write_csv("provenance.csv", [
            "company,domain,headline",
            "Acme,acme.test,Growth marketing agency",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        pack, _ = packfacts.pack_for(recs[0])
        for fact in pack["facts"]:
            if fact.get("fact_key") == "headline":
                self.assertEqual(fact["verification"], "client-provided")
                self.assertNotEqual(fact["verification"], "verified")
                self.assertIn("provenance.csv", fact["source"])
                break
        else:
            self.fail("headline fact not found in pack")

    def test_missing_batch_names_source_as_unknown(self):
        """A record with no batch still gets a source, never a fabricated one."""
        rec = {
            "id": "test", "domain": "acme.test", "research": [],
            "company_facts": {"headline": "SEO agency"},
        }
        pack, _ = packfacts.pack_for(rec)
        headline_facts = [f for f in pack["facts"]
                          if f.get("fact_key") == "headline"]
        self.assertEqual(len(headline_facts), 1)
        self.assertEqual(headline_facts[0]["source"], "unknown")


class TestRealProductiveCsvCoverage(unittest.TestCase):
    """Measure coverage on the real Productive CSV, if available."""

    CSV = os.path.join("work", "Productive",
                       "productive_ICP_safe_to_send (1).csv")

    @unittest.skipUnless(os.path.exists(CSV), "Productive CSV not in this worktree")
    def test_headline_and_industry_coverage(self):
        rows = ingest.read_rows(self.CSV)
        total = len(rows)
        with_headline = sum(1 for r in rows if (r.get("headline") or "").strip())
        with_industry = sum(1 for r in rows if (r.get("industry") or "").strip())
        with_either = sum(
            1 for r in rows
            if (r.get("headline") or "").strip()
            or (r.get("industry") or "").strip()
        )
        print(f"\nProductive CSV: {total} rows")
        print(f"  headline:  {with_headline} ({100*with_headline/total:.1f}%)")
        print(f"  industry:  {with_industry} ({100*with_industry/total:.1f}%)")
        print(f"  either:    {with_either} ({100*with_either/total:.1f}%)")
        self.assertGreater(with_headline, 0, "headline is 0% - column not carried")
        self.assertGreater(with_industry, 0, "industry is 0% - column not carried")


if __name__ == "__main__":
    unittest.main()
