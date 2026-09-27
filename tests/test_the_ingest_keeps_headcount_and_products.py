"""TASK-348: the ingest carries headline, industry, headcount and products.

A CSV row with positioning and headcount columns must survive the ingest
with those values on company_facts, and `packfacts` must expose them with the
CSV file AND ROW named as their source and verification set to CLIENT_SUPPLIED
- never verified research.

OPERATOR DECISION, Zvonimir, 2026-09-27, is why they are no longer in
`pack["facts"]`: that list is the prospect-facing claim licence and a client
CSV may never be one on its own. They are in `unused[CLIENT_SUPPLIED]`, which
is the same facts with their provenance, and the qualification and strategy
paths read `company_facts` on the record directly - the assertions below that
the values survive the ingest are exactly what those readers depend on.
`test_a_client_csv_fact_cannot_license_a_claim` proves both halves through the
real send path.
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
    """The ingested facts are exposed WITH their file and row, and not as a
    claim licence."""

    def _supplied(self, rec):
        _pack, unused = packfacts.pack_for(rec)
        return unused[packfacts.CLIENT_SUPPLIED]

    def test_client_supplied_facts_name_the_batch_file_and_the_row(self):
        path = self.write_csv("source.csv", [
            "company,domain,headline,industry",
            "Acme,acme.test,SEO at scale,Marketing",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        supplied = self._supplied(recs[0])
        ingest_facts = [f for f in supplied
                        if f.get("fact_key") in packfacts.INGEST_FACT_KEYS]
        self.assertTrue(ingest_facts, "no client-supplied facts exposed")
        for fact in ingest_facts:
            self.assertEqual(fact["verification"], packfacts.CLIENT_SUPPLIED)
            self.assertIn("source.csv", fact["source"])
            self.assertEqual(fact["source_row"], 1)

    def test_the_row_is_the_row_this_record_came_from(self):
        """Three rows, three records, three different rows recorded.

        A constant would satisfy the test above. The row has to identify
        WHICH line of the file the value was typed on, so it is asserted per
        record against the order of the file.
        """
        path = self.write_csv("rows.csv", [
            "company,domain,headline",
            "First,first.test,first headline",
            "Second,second.test,second headline",
            "Third,third.test,third headline",
        ])
        ingest.run(path, client="productive", lane="domains")
        by_headline = {}
        for rec in store.load():
            for fact in self._supplied(rec):
                if fact["fact_key"] == "headline":
                    by_headline[fact["snippet"]] = fact["source_row"]
        self.assertEqual(by_headline, {"first headline": 1,
                                       "second headline": 2,
                                       "third headline": 3})

    def test_no_fabricated_provenance(self):
        """A fact from a client CSV is NOT marked as verified research."""
        path = self.write_csv("provenance.csv", [
            "company,domain,headline",
            "Acme,acme.test,Growth marketing agency",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        for fact in self._supplied(recs[0]):
            if fact.get("fact_key") == "headline":
                self.assertEqual(fact["verification"],
                                 packfacts.CLIENT_SUPPLIED)
                self.assertNotEqual(fact["verification"], "verified")
                self.assertIn("provenance.csv", fact["source"])
                break
        else:
            self.fail("headline fact not found")

    def test_no_fabricated_source_url_either(self):
        """The CSV filename is not offered in a field that means public source.

        `source_url` is what `identity_of` reads and what every reader treats
        as a page somebody could open. A batch filename sitting in it is the
        confusion the operator's decision ends.
        """
        path = self.write_csv("nourl.csv", [
            "company,domain,headline",
            "Acme,acme.test,Growth marketing agency",
        ])
        ingest.run(path, client="productive", lane="domains")
        for fact in self._supplied(store.load()[0]):
            self.assertIsNone(fact.get("source_url"))

    def test_missing_batch_names_source_as_unknown(self):
        """A record with no batch still gets a source, never a fabricated one."""
        rec = {
            "id": "test", "domain": "acme.test", "research": [],
            "company_facts": {"headline": "SEO agency"},
        }
        headline_facts = [f for f in self._supplied(rec)
                          if f.get("fact_key") == "headline"]
        self.assertEqual(len(headline_facts), 1)
        self.assertEqual(headline_facts[0]["source"], "unknown")
        self.assertEqual(headline_facts[0]["source_row"],
                         packfacts.UNKNOWN_ROW)

    def test_a_record_that_predates_row_capture_is_not_row_zero(self):
        """History is not rewritten, and absence is not a number.

        The 527 records already in the live store carry a batch with no row.
        Reporting 0 for them would be a fabricated provenance that reads as a
        real line of a real file.
        """
        old = {"id": "old", "domain": "acme.test", "research": [],
               "batch": {"id": "b-1", "source": "productive-09-07.csv"},
               "company_facts": {"headline": "SEO agency"}}
        row_zero = {"id": "zero", "domain": "acme.test", "research": [],
                    "batch": {"id": "b-1", "source": "productive-09-07.csv",
                              "row": 0},
                    "company_facts": {"headline": "SEO agency"}}
        self.assertEqual(self._supplied(old)[0]["source_row"],
                         packfacts.UNKNOWN_ROW)
        self.assertEqual(self._supplied(row_zero)[0]["source_row"], 0)
        self.assertNotEqual(self._supplied(old)[0]["source_row"],
                            self._supplied(row_zero)[0]["source_row"])

    def test_a_bare_string_batch_does_not_crash_the_pack(self):
        """527 records in the live store carry `batch` as a bare STRING.

        `report.batch_of` measured that and says so. Reading `.get("source")`
        straight off it raised AttributeError, so `pack_for` could not be
        called at all for those records - and it is called per lead on the
        send path. The string is the batch's name and it carries no row.
        """
        rec = {"id": "stringy", "domain": "acme.test", "research": [],
               "batch": "productive-2026-09-07",
               "company_facts": {"headline": "SEO agency"}}
        supplied = self._supplied(rec)
        self.assertEqual(supplied[0]["source"], "productive-2026-09-07")
        self.assertEqual(supplied[0]["source_row"], packfacts.UNKNOWN_ROW)


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
