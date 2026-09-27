"""TASK-311: the ingest carries the LinkedIn column onto contacts.

Two source files carry LinkedIn profile URLs the ingest was dropping:

    work/Productive/productive_ICP_safe_to_send (1).csv
        33,887 rows. Column `Url` is a LinkedIn profile on 100%.
        Each row is a contact: First Name, Last Name, Work Email, Url.

    work/Software_Agencies_All_Geo_cleaned - Sheet1.csv
        51,741 rows. Columns `LinkedIn` and `LinkedIn_URL_Repaired`.
        Each row is a company; the LinkedIn URL is a company page, not a
        person. Operational columns (headcount growth, products, employee
        count) are already carried by INGEST_TO_FACTS.

The fix: when a CSV carries contact-level columns (name, email, LinkedIn
URL), the ingest creates a contact per row, grouped by domain. The LinkedIn
URL is validated by linkedin.canonical - a company page or search URL is
NOT bound to a contact.
"""
import os
import unittest

from src import channels, ingest, linkedin, store
from tests.base import QueueTest


class TestIngestCarriesLinkedinUrl(QueueTest):
    """A CSV with a LinkedIn profile URL column creates contacts."""

    def _run(self, csv_lines):
        path = self.write_csv("contacts.csv", csv_lines)
        result = ingest.run(path, client="productive", lane="domains")
        return result, store.load()

    def test_a_linkedin_profile_url_binds_to_a_contact(self):
        _, recs = self._run([
            "company,domain,first name,last name,url",
            "Acme,acme.test,Jane,Doe,https://www.linkedin.com/in/jane-doe",
        ])
        self.assertEqual(len(recs), 1)
        contacts = recs[0]["contacts"]
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["linkedin"],
                         "https://www.linkedin.com/in/jane-doe")
        self.assertEqual(contacts[0]["name"], "Jane Doe")

    def test_a_company_page_is_not_bound_as_a_profile(self):
        """A LinkedIn company page is NOT a person's profile."""
        _, recs = self._run([
            "company,domain,first name,last name,url",
            "Acme,acme.test,Jane,Doe,"
            "https://www.linkedin.com/company/acme-inc",
        ])
        contacts = recs[0]["contacts"]
        self.assertEqual(len(contacts), 1)
        self.assertNotIn("linkedin", contacts[0])

    def test_a_search_url_is_not_bound_as_a_profile(self):
        _, recs = self._run([
            "company,domain,first name,last name,url",
            "Acme,acme.test,Jane,Doe,"
            "https://www.linkedin.com/search/results/people/?keywords=acme",
        ])
        contacts = recs[0]["contacts"]
        self.assertNotIn("linkedin", contacts[0])

    def test_multiple_rows_at_same_domain_create_multiple_contacts(self):
        _, recs = self._run([
            "company,domain,first name,last name,url",
            "Acme,acme.test,Jane,Doe,https://www.linkedin.com/in/jane-doe",
            "Acme,acme.test,John,Smith,https://www.linkedin.com/in/john-smith",
            "Acme,acme.test,Bob,Jones,https://www.linkedin.com/in/bob-jones",
        ])
        self.assertEqual(len(recs), 1)
        contacts = recs[0]["contacts"]
        self.assertEqual(len(contacts), 3)
        profiles = {c["linkedin"] for c in contacts}
        self.assertIn("https://www.linkedin.com/in/jane-doe", profiles)
        self.assertIn("https://www.linkedin.com/in/john-smith", profiles)
        self.assertIn("https://www.linkedin.com/in/bob-jones", profiles)

    def test_contacts_have_keys_assigned(self):
        _, recs = self._run([
            "company,domain,first name,last name,url",
            "Acme,acme.test,Jane,Doe,https://www.linkedin.com/in/jane-doe",
        ])
        contacts = recs[0]["contacts"]
        self.assertTrue(contacts[0].get("key"),
                        "contact has no key assigned")

    def test_email_column_also_triggers_contact_creation(self):
        """A CSV with email but no LinkedIn still creates contacts."""
        _, recs = self._run([
            "company,domain,first name,last name,work email",
            "Acme,acme.test,Jane,Doe,jane@acme.test",
        ])
        contacts = recs[0]["contacts"]
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["email"], "jane@acme.test")

    def test_a_company_only_csv_does_not_create_contacts(self):
        """A CSV with no contact columns creates records with no contacts."""
        _, recs = self._run([
            "company,domain,headline",
            "Acme,acme.test,SEO at scale",
        ])
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["contacts"], [])

    def test_linkedin_verdict_passes_for_a_contact_with_profile(self):
        """The whole point: channels.linkedin_verdict can read the URL."""
        _, recs = self._run([
            "company,domain,first name,last name,url",
            "Acme,acme.test,Jane,Doe,https://www.linkedin.com/in/jane-doe",
        ])
        contact = recs[0]["contacts"][0]
        ok, reason = channels.linkedin_verdict(recs[0], contact)
        self.assertTrue(ok, f"linkedin_verdict refused: {reason}")

    def test_linkedin_verdict_refuses_when_only_company_page(self):
        _, recs = self._run([
            "company,domain,first name,last name,url",
            "Acme,acme.test,Jane,Doe,"
            "https://www.linkedin.com/company/acme-inc",
        ])
        contact = recs[0]["contacts"][0]
        ok, reason = channels.linkedin_verdict(recs[0], contact)
        self.assertFalse(ok)

    def test_bare_vanity_name_is_accepted(self):
        """Some exports store a bare vanity slug rather than a full URL."""
        _, recs = self._run([
            "company,domain,first name,last name,url",
            "Acme,acme.test,Jane,Doe,jane-doe",
        ])
        contacts = recs[0]["contacts"]
        self.assertEqual(contacts[0]["linkedin"],
                         "https://www.linkedin.com/in/jane-doe")


class TestLinkedinColumnsSoftwareAgencies(QueueTest):
    """The Software Agencies CSV has LinkedIn and LinkedIn_URL_Repaired.

    These are company pages, not person profiles. linkedin.canonical refuses
    them, so no contact gets a linkedin field. The operational columns
    (headcount growth, products, employee count) are already carried by
    INGEST_TO_FACTS and tested separately.
    """

    def test_company_linkedin_url_is_not_bound_to_a_contact(self):
        path = self.write_csv("agencies.csv", [
            "company,domain,linkedin,company_employee_count,"
            "company_total_headcount_growth_12_months,"
            "company_product_and_services",
            "Acme,acme.test,https://www.linkedin.com/company/acme,"
            "42,35%,SEO; PPC",
        ])
        ingest.run(path, client="productive", lane="domains")
        recs = store.load()
        self.assertEqual(len(recs), 1)
        facts = recs[0]["company_facts"]
        self.assertEqual(facts.get("headcount"), "42")
        self.assertEqual(facts.get("headcount_growth_12m"), "35%")
        self.assertEqual(facts.get("products"), "SEO; PPC")


class TestAcceptanceCriteria(QueueTest):
    """The acceptance command from the task file."""

    def test_contacts_carry_linkedin_profiles(self):
        path = self.write_csv("productive.csv", [
            "company,domain,first name,last name,url,work email",
            "Acme,acme.test,Jane,Doe,"
            "https://www.linkedin.com/in/jane-doe,jane@acme.test",
            "Acme,acme.test,John,Smith,"
            "https://www.linkedin.com/in/john-smith,john@acme.test",
            "Other,other.test,Bob,Jones,"
            "https://www.linkedin.com/in/bob-jones,bob@other.test",
        ])
        ingest.run(path, client="productive", lane="domains")
        rs = store.load()
        c = [x for r in rs for x in (r.get("contacts") or [])]
        n = sum(1 for x in c
                if "linkedin.com/in/" in str(x.get("linkedin") or "").lower())
        self.assertEqual(n, 3, f"expected 3 contacts with LinkedIn profiles, "
                               f"got {n} of {len(c)}")


class TestRealProductiveCsvLinkedinCoverage(unittest.TestCase):
    """Measure LinkedIn coverage on the real Productive CSV, if available."""

    CSV = os.path.join("work", "Productive",
                       "productive_ICP_safe_to_send (1).csv")

    @unittest.skipUnless(os.path.exists(CSV), "Productive CSV not in worktree")
    def test_linkedin_url_coverage(self):
        rows = ingest.read_rows(self.CSV)
        total = len(rows)
        linkedin_headers = [h for h in rows[0].keys()
                            if h in ingest.LINKEDIN_COLUMNS]
        with_profile = 0
        with_non_profile = 0
        empty = 0
        for row in rows:
            for h in linkedin_headers:
                val = (row.get(h) or "").strip()
                if not val:
                    continue
                if linkedin.canonical(val):
                    with_profile += 1
                else:
                    with_non_profile += 1
                break
            else:
                empty += 1
        print(f"\nProductive CSV: {total} rows")
        print(f"  LinkedIn headers found: {linkedin_headers}")
        print(f"  valid profile URL:  {with_profile} "
              f"({100*with_profile/total:.1f}%)")
        print(f"  non-profile URL:    {with_non_profile} "
              f"({100*with_non_profile/total:.1f}%)")
        print(f"  empty/absent:       {empty} "
              f"({100*empty/total:.1f}%)")
        self.assertGreater(with_profile, 0,
                           "no valid LinkedIn profiles found - "
                           "column not carried?")


if __name__ == "__main__":
    unittest.main()
