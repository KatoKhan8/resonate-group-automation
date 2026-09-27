"""TASK-311: the ingest carries the LinkedIn URL and operational columns.

Two source files carry columns the ingest used to silently discard:

  work/Productive/productive_ICP_safe_to_send (1).csv
    Column `Url` is a LinkedIn profile on 100% of rows.

  work/Software_Agencies_All_Geo_cleaned - Sheet1.csv
    Columns `LinkedIn`, `LinkedIn_URL_Repaired`, headcount growth,
    products and services, employee count.

The ingest now maps foreign headers via `columns.py`, extracts contacts
(name, email, linkedin, title), groups them by domain, and stores
operational columns on `company_facts`.
"""
import os
import unittest

from src import ingest, linkedin, store
from tests.base import QueueTest


class TestInestCarriesLinkedIn(QueueTest):
    """A CSV with LinkedIn URLs binds them onto contacts."""

    def test_linkedin_url_from_canonical_column(self):
        path = self.write_csv("li.csv", [
            "Company,Domain,LinkedIn,First Name,Last Name,Work Email,Job Title",
            "Acme,acme.test,https://www.linkedin.com/in/jan-novak,Jan,Novak,"
            "jan@acme.test,CTO",
        ])
        result = ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(len(recs), 1)
        contacts = recs[0].get("contacts") or []
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["linkedin"],
                         "https://www.linkedin.com/in/jan-novak")
        self.assertEqual(contacts[0]["email"], "jan@acme.test")
        self.assertEqual(contacts[0]["name"], "Jan Novak")
        self.assertEqual(contacts[0]["title"], "CTO")
        self.assertEqual(result["contacts"], 1)
        self.assertEqual(result["contacts_with_linkedin"], 1)

    def test_linkedin_url_validated_not_trusted(self):
        """A company page or search URL is NOT a profile."""
        path = self.write_csv("li_bad.csv", [
            "Company,Domain,LinkedIn,Name",
            "Acme,acme.test,https://www.linkedin.com/company/acme,Acme Team",
            "Beta,beta.test,https://www.linkedin.com/search/results?keywords=x,"
            "Searcher",
            "Gamma,gamma.test,https://www.google.com/search?q=test,"
            "Gamma Person",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = {r["domain"]: r for r in store.load()}
        # Company page: linkedin.canonical returns None
        acme_contacts = recs["acme.test"].get("contacts") or []
        self.assertEqual(len(acme_contacts), 1)
        self.assertIsNone(acme_contacts[0]["linkedin"])

        # Search URL: also not a profile
        beta_contacts = recs["beta.test"].get("contacts") or []
        self.assertEqual(len(beta_contacts), 1)
        self.assertIsNone(beta_contacts[0]["linkedin"])

        # Not LinkedIn at all: also not a profile
        gamma_contacts = recs["gamma.test"].get("contacts") or []
        self.assertEqual(len(gamma_contacts), 1)
        self.assertIsNone(gamma_contacts[0]["linkedin"])

    def test_multiple_contacts_at_one_domain(self):
        """Five rows at one domain are five contacts, not one record."""
        path = self.write_csv("multi.csv", [
            "Company,Domain,LinkedIn,Name,Work Email",
            "Acme,acme.test,https://www.linkedin.com/in/alice,Alice,"
            "alice@acme.test",
            "Acme,acme.test,https://www.linkedin.com/in/bob,Bob,"
            "bob@acme.test",
            "Acme,acme.test,https://www.linkedin.com/in/carol,Carol,"
            "carol@acme.test",
        ])
        result = ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(len(recs), 1)
        contacts = recs[0].get("contacts") or []
        self.assertEqual(len(contacts), 3)
        profiles = {c["linkedin"] for c in contacts}
        self.assertIn("https://www.linkedin.com/in/alice", profiles)
        self.assertIn("https://www.linkedin.com/in/bob", profiles)
        self.assertIn("https://www.linkedin.com/in/carol", profiles)
        self.assertEqual(result["contacts"], 3)
        self.assertEqual(result["contacts_with_linkedin"], 3)

    def test_duplicate_contact_at_same_domain_is_not_doubled(self):
        """The same email twice at one domain is one contact, not two."""
        path = self.write_csv("dup.csv", [
            "Company,Domain,Name,Work Email",
            "Acme,acme.test,Alice,alice@acme.test",
            "Acme,acme.test,Alice,alice@acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(len(recs), 1)
        contacts = recs[0].get("contacts") or []
        self.assertEqual(len(contacts), 1)

    def test_company_row_without_contacts_still_deduplicates(self):
        """A company-only row at a seen domain is a duplicate, not silent."""
        path = self.write_csv("company_dup.csv", [
            "Company,Domain",
            "Acme,acme.test",
            "Acme,acme.test",
        ])
        result = ingest.run(path, client="productive", lane="domains")
        self.assertEqual(len(result["queued"]), 1)
        self.assertEqual(len(result["dropped"]), 1)
        self.assertEqual(result["dropped"][0][1], "duplicate domain")


class TestOperationalColumns(QueueTest):
    """Operational columns from the Software Agencies file are carried."""

    def test_headcount_growth_on_company_facts(self):
        path = self.write_csv("ops.csv", [
            "Company,Domain,Company_Total_headcount_growth_12_months,"
            "Company_Product_and_Services,Company_Employee_Count",
            "Acme,acme.test,42,consulting and staffing,150",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(len(recs), 1)
        facts = recs[0].get("company_facts") or {}
        self.assertEqual(facts.get("headcount_growth_12m"), "42")
        self.assertEqual(facts.get("products_and_services"),
                         "consulting and staffing")
        self.assertEqual(facts.get("employee_count"), "150")

    def test_operational_columns_merge_across_rows_at_same_domain(self):
        """Two rows at one domain: operational facts from both are kept."""
        path = self.write_csv("ops_multi.csv", [
            "Company,Domain,Company_Employee_Count,Company_Size",
            "Acme,acme.test,150,medium",
            "Acme,acme.test,,large",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        facts = recs[0].get("company_facts") or {}
        self.assertEqual(facts.get("employee_count"), "150")
        self.assertEqual(facts.get("company_size"), "large")


class TestAcceptanceCommand(QueueTest):
    """The acceptance command from TASK-311."""

    def test_contacts_carry_linkedin_profile(self):
        path = self.write_csv("acceptance.csv", [
            "Company,Domain,LinkedIn,Name",
            "Acme,acme.test,https://www.linkedin.com/in/jan-novak,Jan",
            "Beta,beta.test,https://www.linkedin.com/in/ana-kovac,Ana",
            "Gamma,gamma.test,https://www.linkedin.com/company/gamma,Gamma",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        contacts = [x for r in recs for x in (r.get("contacts") or [])]
        n = sum(1 for x in contacts
                if "linkedin.com/in/" in str(
                    x.get("linkedin") or "").lower())
        # Two have /in/ profiles; the third is a company page (rejected)
        self.assertEqual(n, 2)
        self.assertTrue(n > 0, "assertion from the acceptance command")


class TestBackwardCompatibility(QueueTest):
    """JSONL and directory sources still work unchanged."""

    def test_jsonl_source_unchanged(self):
        """JSONL rows are already canonical; no column mapping needed."""
        import json
        path = os.path.join(self.tmp, "batch.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"company": "Acme", "domain": "acme.test",
                        "context": "testing", "signal": "hot"}, f)
            f.write("\n")
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["domain"], "acme.test")
        self.assertEqual(recs[0]["context"], "testing")


if __name__ == "__main__":
    unittest.main()
