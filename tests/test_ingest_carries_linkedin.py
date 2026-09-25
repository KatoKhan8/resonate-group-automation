"""TASK-311: the ingest carries the LinkedIn URL and operational columns.

Two source files were silently dropping columns the ingest did not know how
to read. A ContactOut people-search export carries `Url` (a LinkedIn profile
on 100% of its rows) and `Work Email`. A software-agencies universe carries
`LinkedIn`, `LinkedIn_URL_Repaired`, headcount growth, products and services,
and employee count. Every one of those was dropped on the way in.

These tests prove the fix:

  - A LinkedIn profile URL survives the ingest and lands on the contact
  - A company page, search URL or truncated share link does NOT
  - Contact columns (email, name, title) are bound to the contact
  - Operational columns (headcount growth, employee count, products) are
    attached to `company_facts`
  - The acceptance command from the task file passes
"""
import os
import unittest

from src import ingest, store, linkedin
from tests.base import QueueTest


class TestInestCarriesLinkedInURL(QueueTest):
    """A people-search export with a `Url` column: LinkedIn survives."""

    def test_linkedin_profile_url_is_carried(self):
        path = self.write_csv("people.csv", [
            "Url,First Name,Last Name,Work Email,Company,Company Website",
            "https://www.linkedin.com/in/jan-novak,Jan,Novak,"
            "jan@acme.test,Acme,acme.test",
        ])
        result = ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(len(recs), 1)
        contacts = recs[0].get("contacts") or []
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["linkedin"],
                         "https://www.linkedin.com/in/jan-novak")

    def test_email_is_carried_alongside_linkedin(self):
        path = self.write_csv("people.csv", [
            "Url,First Name,Last Name,Work Email,Company,Company Website",
            "https://www.linkedin.com/in/jan-novak,Jan,Novak,"
            "jan@acme.test,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        contact = recs[0]["contacts"][0]
        self.assertEqual(contact["email"], "jan@acme.test")
        self.assertEqual(contact["name"], "Jan Novak")

    def test_linkedin_column_name_is_mapped_directly(self):
        """The Software_Agencies file uses `LinkedIn` as the header."""
        path = self.write_csv("agencies.csv", [
            "LinkedIn,Company,Domain",
            "https://www.linkedin.com/in/jane-doe,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(recs[0]["contacts"][0]["linkedin"],
                         "https://www.linkedin.com/in/jane-doe")

    def test_linkedin_url_repaired_is_mapped(self):
        """`LinkedIn_URL_Repaired` is a LinkedIn alias."""
        path = self.write_csv("agencies.csv", [
            "LinkedIn_URL_Repaired,Company,Domain",
            "https://www.linkedin.com/in/jane-doe,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(recs[0]["contacts"][0]["linkedin"],
                         "https://www.linkedin.com/in/jane-doe")


class TestLinkedInValidation(QueueTest):
    """A LinkedIn value that is not a profile URL is NOT a profile."""

    def test_company_page_is_refused(self):
        path = self.write_csv("people.csv", [
            "Url,First Name,Last Name,Company,Company Website",
            "https://www.linkedin.com/company/acme,Jan,Novak,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        contacts = recs[0].get("contacts") or []
        # The contact may exist (from name/email) but must NOT carry linkedin
        for c in contacts:
            self.assertNotIn("linkedin", c)

    def test_search_url_is_refused(self):
        path = self.write_csv("people.csv", [
            "Url,First Name,Last Name,Company,Company Website",
            "https://www.linkedin.com/search/results/people/?keywords=jan,"
            "Jan,Novak,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        for c in (recs[0].get("contacts") or []):
            self.assertNotIn("linkedin", c)

    def test_empty_url_is_not_a_profile(self):
        path = self.write_csv("people.csv", [
            "Url,First Name,Last Name,Company,Company Website",
            ",Jan,Novak,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        for c in (recs[0].get("contacts") or []):
            self.assertNotIn("linkedin", c)

    def test_valid_profile_passes_canonical_check(self):
        """The linkedin module's own canonical() accepts /in/ profiles."""
        self.assertIsNotNone(
            linkedin.canonical("https://www.linkedin.com/in/jan-novak"))

    def test_company_page_fails_canonical_check(self):
        """The linkedin module's own canonical() refuses /company/ pages."""
        self.assertIsNone(
            linkedin.canonical("https://www.linkedin.com/company/acme"))


class TestOperationalColumns(QueueTest):
    """Headcount growth, products and services, employee count."""

    def test_headcount_growth_is_attached_to_company_facts(self):
        path = self.write_csv("agencies.csv", [
            "Company,Domain,"
            "Company_Total_headcount_growth_12_months,"
            "Company_Product_and_Services,"
            "Company_Employee_Count",
            "Acme,acme.test,+40%,"
            "Web development and design,50",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        facts = recs[0].get("company_facts") or {}
        self.assertEqual(facts.get("headcount_growth_12m"), 40.0)
        self.assertEqual(facts.get("products_and_services"),
                         "Web development and design")
        self.assertEqual(facts.get("employee_count"), 50)

    def test_employee_count_is_parsed_as_integer(self):
        path = self.write_csv("agencies.csv", [
            "Company,Domain,Company_Employee_Count",
            "Acme,acme.test,150",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        facts = recs[0].get("company_facts") or {}
        self.assertEqual(facts.get("employee_count"), 150)
        self.assertIsInstance(facts.get("employee_count"), int)

    def test_headcount_growth_handles_percentage_format(self):
        path = self.write_csv("agencies.csv", [
            "Company,Domain,Company_Total_headcount_growth_12_months",
            "Acme,acme.test,-15%",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        facts = recs[0].get("company_facts") or {}
        self.assertEqual(facts.get("headcount_growth_12m"), -15.0)


class TestContactCreation(QueueTest):
    """Contacts are created from the contact columns."""

    def test_contact_has_a_key(self):
        path = self.write_csv("people.csv", [
            "Url,First Name,Last Name,Work Email,Company,Company Website",
            "https://www.linkedin.com/in/jan-novak,Jan,Novak,"
            "jan@acme.test,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        contact = recs[0]["contacts"][0]
        self.assertTrue(contact.get("key"),
                        "contact must have a key assigned")

    def test_contact_without_email_or_linkedin_is_not_created(self):
        """A row with only company info and no person columns: no contact."""
        path = self.write_csv("companies.csv", [
            "Company,Domain",
            "Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(recs[0].get("contacts") or [], [])

    def test_title_is_carried(self):
        path = self.write_csv("people.csv", [
            "First Name,Last Name,Job Title,Company,Domain",
            "Jan,Novak,CTO,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        contact = recs[0]["contacts"][0]
        self.assertEqual(contact.get("title"), "CTO")

    def test_source_provenance_is_kept(self):
        """Unmapped columns are kept as source provenance on the contact."""
        path = self.write_csv("people.csv", [
            "First Name,Last Name,Company,Domain,Location,Industry",
            "Jan,Novak,Acme,acme.test,Zagreb,IT",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        contact = recs[0]["contacts"][0]
        source = contact.get("source") or {}
        self.assertIn("Location", source)
        self.assertEqual(source["Location"], "Zagreb")


class TestColumnMappingReport(QueueTest):
    """The result reports what happened to the columns."""

    def test_result_includes_column_mapping(self):
        path = self.write_csv("people.csv", [
            "Url,First Name,Last Name,Work Email,Company,Company Website",
            "https://www.linkedin.com/in/jan-novak,Jan,Novak,"
            "jan@acme.test,Acme,acme.test",
        ])
        result = ingest.run(path, client="productive", lane="domains")
        self.assertIn("column_mapping", result)
        self.assertIn("contacts_found", result)
        self.assertIn("linkedin_found", result)
        self.assertEqual(result["contacts_found"], 1)
        self.assertEqual(result["linkedin_found"], 1)


class TestAcceptanceCommand(QueueTest):
    """The acceptance command from the task file."""

    def test_acceptance_command_passes(self):
        path = self.write_csv("people.csv", [
            "Url,First Name,Last Name,Work Email,Company,Company Website",
            "https://www.linkedin.com/in/jan-novak,Jan,Novak,"
            "jan@acme.test,Acme,acme.test",
            "https://www.linkedin.com/in/jane-doe,Jane,Doe,"
            "jane@acme.test,Acme,acme.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        rs = store.load()
        c = [x for r in rs for x in (r.get("contacts") or [])]
        n = sum(1 for x in c
                if "linkedin.com/in/" in str(
                    x.get("linkedin") or "").lower())
        self.assertGreater(n, 0,
                           f"{n} of {len(c)} contacts carry a LinkedIn profile")


class TestBackwardCompatibility(QueueTest):
    """The existing phase1.csv fixture still works unchanged."""

    def test_phase1_csv_still_produces_the_same_records(self):
        from tests.base import FIXTURES
        csv_path = os.path.join(FIXTURES, "phase1.csv")
        suppress = os.path.join(FIXTURES, "suppress-test.txt")
        result = ingest.run(csv_path, client="productive", lane="domains",
                            suppress_path=suppress)
        self.assertEqual(sorted(result["queued"]), ["harbourline", "meridian"])
        self.assertEqual(dict(result["dropped"]), {
            "blocked-co": "suppressed (live account)",
            "meridian-again": "duplicate domain",
            "some-company": "no domain",
        })

    def test_phase1_records_have_no_contacts(self):
        """phase1.csv has no contact columns; records should have none."""
        from tests.base import FIXTURES
        csv_path = os.path.join(FIXTURES, "phase1.csv")
        suppress = os.path.join(FIXTURES, "suppress-test.txt")
        ingest.run(csv_path, client="productive", lane="domains",
                   suppress_path=suppress)
        for rec in store.load():
            self.assertEqual(rec.get("contacts") or [], [])


if __name__ == "__main__":
    unittest.main()
