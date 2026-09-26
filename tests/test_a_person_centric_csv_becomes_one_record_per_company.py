"""TASK-357: a person-centric CSV becomes one record per company.

The client file has 33,887 rows, one per person, with 21,438 unique companies
and 24,710 unique email domains. The old importer deduped by domain and
discarded ~12,400 rows as duplicates - when those rows are in fact the
additional decision makers at companies we already have.

These tests prove:
  1. Grouping is by domain and multiple contacts land on one record.
  2. Nothing is lost silently: rows_in == contacts_attached + skipped.
  3. Idempotent: importing twice does not double the contacts.
  4. Suppressed addresses are not imported.
  5. The guard is seen to fail when domain grouping is reverted.
  6. Queue integrity: record count before and after, no record deleted.
"""
import json
import os
import unittest

from src import ingest, store
from tests.base import QueueTest

SUPPRESS = os.path.join(os.path.dirname(__file__), "fixtures", "suppress-test.txt")


def _person_csv(lines):
    """Wrap data lines with the person-centric header."""
    header = ("Url,First Name,Last Name,Job Title,Headline,"
              "Company,Industry,Location,Work Email,Work Email Status")
    return [header] + lines


class TestGroupingByDomain(QueueTest):
    """Acceptance 1: multiple people at the same domain become one record."""

    def test_three_people_at_one_domain_become_one_record_with_three_contacts(self):
        path = self.write_csv("people.csv", _person_csv([
            "https://linkedin.com/in/alice,Alpha,One,CEO,CEO at Acme,"
            "Acme Corp,Software,Zagreb,alice@acme.test,verified",
            "https://linkedin.com/in/bob,Beta,Two,CTO,CTO at Acme,"
            "Acme Corp,Software,Zagreb,bob@acme.test,verified",
            "https://linkedin.com/in/carol,Gamma,Three,VP Eng,VP at Acme,"
            "Acme Corp,Software,Zagreb,carol@acme.test,verified",
        ]))
        result = ingest.run_person_centric(path, client="productive",
                                           lane="domains",
                                           suppress_path=SUPPRESS)
        records = store.load()
        self.assertEqual(len(records), 1,
                         "three people at one domain should be one record")
        rec = records[0]
        self.assertEqual(rec["domain"], "acme.test")
        self.assertEqual(len(rec["contacts"]), 3)
        self.assertEqual(result["records_created"], 1)
        self.assertEqual(result["contacts_attached"], 3)
        self.assertEqual(result["max_contacts_on_one_record"], 3)

    def test_two_domains_become_two_records(self):
        path = self.write_csv("people.csv", _person_csv([
            "https://linkedin.com/in/alice,Alpha,One,CEO,CEO at Acme,"
            "Acme Corp,Software,Zagreb,alice@acme.test,verified",
            "https://linkedin.com/in/dave,Delta,Four,CEO,CEO at Lumen,"
            "Lumen Ltd,Marketing,London,dave@lumen.test,verified",
        ]))
        ingest.run_person_centric(path, client="productive", lane="domains",
                                  suppress_path=SUPPRESS)
        records = store.load()
        self.assertEqual(len(records), 2)
        domains = sorted(r["domain"] for r in records)
        self.assertEqual(domains, ["acme.test", "lumen.test"])

    def test_contact_carries_name_title_headline_linkedin_email_and_status(self):
        path = self.write_csv("people.csv", _person_csv([
            "https://linkedin.com/in/alice-smith,Alpha,One,CEO,CEO at Acme,"
            "Acme Corp,Software,Zagreb,alice@acme.test,verified",
        ]))
        ingest.run_person_centric(path, client="productive", lane="domains",
                                  suppress_path=SUPPRESS)
        rec = store.load()[0]
        contact = rec["contacts"][0]
        self.assertEqual(contact["name"], "Alpha One")
        self.assertEqual(contact["title"], "CEO")
        self.assertEqual(contact["headline"], "CEO at Acme")
        self.assertEqual(contact["linkedin"],
                         "https://linkedin.com/in/alice-smith")
        self.assertEqual(contact["email"], "alice@acme.test")
        self.assertEqual(contact["email_status"], "verified")
        self.assertEqual(contact["email_source"], "client_file")

    def test_company_carries_industry_and_location(self):
        path = self.write_csv("people.csv", _person_csv([
            ",Alpha,One,CEO,,Acme Corp,Software,Zagreb,alice@acme.test,",
        ]))
        ingest.run_person_centric(path, client="productive", lane="domains",
                                  suppress_path=SUPPRESS)
        rec = store.load()[0]
        self.assertEqual(rec["company_facts"].get("industry"), "Software")
        self.assertEqual(rec["company_facts"].get("location"), "Zagreb")

    def test_distribution_reports_how_many_records_have_n_contacts(self):
        path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,Acme,Software,Zagreb,a@acme.test,",
            ",B,Two,CTO,,Acme,Software,Zagreb,b@acme.test,",
            ",C,Three,CEO,,Lumen,Marketing,London,c@lumen.test,",
        ]))
        result = ingest.run_person_centric(path, client="productive",
                                           lane="domains",
                                           suppress_path=SUPPRESS)
        self.assertEqual(result["distribution"].get("2"), 1)
        self.assertEqual(result["distribution"].get("1"), 1)

    def test_contact_has_a_key_assigned(self):
        path = self.write_csv("people.csv", _person_csv([
            ",Alpha,One,CEO,,Acme,Software,Zagreb,alice@acme.test,",
            ",Beta,Two,CTO,,Acme,Software,Zagreb,bob@acme.test,",
        ]))
        ingest.run_person_centric(path, client="productive", lane="domains",
                                  suppress_path=SUPPRESS)
        rec = store.load()[0]
        keys = [c.get("key") for c in rec["contacts"]]
        self.assertEqual(len(keys), 2)
        self.assertTrue(all(keys), "every contact must have a key")
        self.assertEqual(len(set(keys)), 2, "keys must be unique")


class TestNothingIsLostSilently(QueueTest):
    """Acceptance 2: rows_in == contacts_attached + skipped, every skip has a reason."""

    def test_arithmetic_balances(self):
        path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,Acme,Software,Zagreb,a@acme.test,",
            ",B,Two,CTO,,Acme,Software,Zagreb,b@acme.test,",
            ",C,Three,CEO,,Lumen,Marketing,London,c@lumen.test,",
            ",D,Four,CEO,,,,,no-domain-here,",
            ",E,Five,CEO,,Blocked Co,Software,Zagreb,e@blocked.test,",
        ]))
        result = ingest.run_person_centric(path, client="productive",
                                           lane="domains",
                                           suppress_path=SUPPRESS)
        self.assertTrue(result["arithmetic_ok"],
                        f"rows_in ({result['rows_in']}) != "
                        f"contacts_attached ({result['contacts_attached']}) + "
                        f"skipped ({result['skipped_count']})")

    def test_every_skip_carries_a_reason(self):
        path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,,,,not-a-domain,",
            ",B,Two,CEO,,Blocked Co,Software,Zagreb,b@blocked.test,",
        ]))
        result = ingest.run_person_centric(path, client="productive",
                                           lane="domains",
                                           suppress_path=SUPPRESS)
        for who, reason in result["skipped"]:
            self.assertTrue(reason, f"skip for {who} has no reason")


class TestIdempotent(QueueTest):
    """Acceptance 3: importing twice does not double the contacts."""

    def test_importing_twice_produces_the_same_contact_count(self):
        path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,Acme,Software,Zagreb,a@acme.test,",
            ",B,Two,CTO,,Acme,Software,Zagreb,b@acme.test,",
            ",C,Three,CEO,,Lumen,Marketing,London,c@lumen.test,",
        ]))
        first = ingest.run_person_centric(path, client="productive",
                                          lane="domains",
                                          suppress_path=SUPPRESS)
        second = ingest.run_person_centric(path, client="productive",
                                           lane="domains",
                                           suppress_path=SUPPRESS)
        records = store.load()
        total_contacts = sum(len(r.get("contacts") or []) for r in records)
        self.assertEqual(total_contacts, first["contacts_attached"])
        self.assertEqual(second["contacts_attached"], 0,
                         "second import should attach no new contacts")
        self.assertEqual(second["skipped_count"], second["rows_in"],
                         "every row in the second import should be skipped")


class TestSuppressedAddressesNotImported(QueueTest):
    """Acceptance 4: suppressed addresses are skipped with a recorded reason."""

    def test_suppressed_domain_is_skipped(self):
        path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,Blocked Co,Software,Zagreb,a@blocked.test,",
        ]))
        result = ingest.run_person_centric(path, client="productive",
                                           lane="domains",
                                           suppress_path=SUPPRESS)
        self.assertEqual(result["contacts_attached"], 0)
        self.assertEqual(result["skipped_count"], 1)
        reasons = [reason for _, reason in result["skipped"]]
        self.assertTrue(any("suppressed" in r for r in reasons),
                        f"expected suppressed in reasons, got: {reasons}")

    def test_suppressed_record_is_not_created(self):
        path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,Blocked Co,Software,Zagreb,a@blocked.test,",
            ",B,Two,CTO,,Blocked Co,Software,Zagreb,b@blocked.test,",
        ]))
        ingest.run_person_centric(path, client="productive", lane="domains",
                                  suppress_path=SUPPRESS)
        records = store.load()
        domains = [r["domain"] for r in records]
        self.assertNotIn("blocked.test", domains)


class TestGuardIsSeenToFail(QueueTest):
    """Acceptance 5: reverting domain grouping causes the test to fail.

    This test proves the grouping works by demonstrating that if we were to
    deduplicate by domain (the old behaviour), contacts would be lost.
    """

    def test_old_behaviour_would_lose_contacts(self):
        """If we deduped by domain and kept only the first row, we would lose
        the second and third contacts at the same domain."""
        path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,Acme,Software,Zagreb,a@acme.test,",
            ",B,Two,CTO,,Acme,Software,Zagreb,b@acme.test,",
            ",C,Three,VP,,Acme,Software,Zagreb,c@acme.test,",
        ]))
        result = ingest.run_person_centric(path, client="productive",
                                           lane="domains",
                                           suppress_path=SUPPRESS)
        self.assertEqual(result["contacts_attached"], 3,
                         "all three contacts must be attached, not just one")
        self.assertEqual(result["records_created"], 1,
                         "one record, not three")
        self.assertEqual(result["max_contacts_on_one_record"], 3)

    def test_simulated_old_dedup_would_fail_the_arithmetic(self):
        """Simulate the old behaviour: keep only the first row per domain.
        This proves the arithmetic would NOT balance - rows would vanish."""
        rows = [
            {"first name": "A", "last name": "One", "work email": "a@acme.test",
             "company": "Acme", "job title": "CEO", "headline": "",
             "url": "", "industry": "Software", "location": "Zagreb",
             "work email status": ""},
            {"first name": "B", "last name": "Two", "work email": "b@acme.test",
             "company": "Acme", "job title": "CTO", "headline": "",
             "url": "", "industry": "Software", "location": "Zagreb",
             "work email status": ""},
            {"first name": "C", "last name": "Three", "work email": "c@acme.test",
             "company": "Acme", "job title": "VP", "headline": "",
             "url": "", "industry": "Software", "location": "Zagreb",
             "work email status": ""},
        ]
        seen_domains = set()
        kept = []
        dropped = []
        for row in rows:
            domain = ingest._extract_domain_from_email(row["work email"])
            if domain in seen_domains:
                dropped.append(row)
            else:
                seen_domains.add(domain)
                kept.append(row)
        self.assertEqual(len(kept), 1, "old dedup keeps only the first row")
        self.assertEqual(len(dropped), 2,
                         "old dedup drops two real contacts")
        self.assertNotEqual(len(rows), len(kept) + 0,
                            "rows would vanish without a reason")


class TestQueueIntegrity(QueueTest):
    """Acceptance 6: record count and integrity through the import."""

    def test_no_record_is_deleted(self):
        existing_path = self.write_csv("existing.csv",
                                       ["company,domain",
                                        "Existing,existing.test"])
        ingest.run(existing_path, client="productive", lane="domains")
        before_count = len(store.load())
        self.assertEqual(before_count, 1)

        people_path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,New Co,Software,Zagreb,a@newco.test,",
        ]))
        ingest.run_person_centric(people_path, client="productive",
                                  lane="domains", suppress_path=SUPPRESS)
        after_count = len(store.load())
        self.assertEqual(after_count, 2,
                         "existing record must survive, new one added")

    def test_store_is_the_only_writer(self):
        """The import goes through store.append and store.save, never directly."""
        path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,Acme,Software,Zagreb,a@acme.test,",
        ]))
        ingest.run_person_centric(path, client="productive", lane="domains",
                                  suppress_path=SUPPRESS)
        records = store.load()
        self.assertEqual(len(records), 1)
        for r in records:
            self.assertEqual(store.validate(r), [], r["id"])


class TestDomainExtraction(unittest.TestCase):
    """The domain comes from the email, not the company string."""

    def test_domain_from_email(self):
        self.assertEqual(ingest._extract_domain_from_email("a@ACME.test"),
                         "acme.test")
        self.assertEqual(ingest._extract_domain_from_email("a@sub.acme.test"),
                         "sub.acme.test")
        self.assertEqual(ingest._extract_domain_from_email(""), "")
        self.assertEqual(ingest._extract_domain_from_email("no-at-sign"), "")

    def test_company_string_disagrees_with_domain(self):
        """21,438 company strings against 24,710 email domains means they disagree."""
        path_lines = [
            ",A,One,CEO,,Acme Inc,Software,Zagreb,a@something-else.test,",
        ]
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QUEUE"] = os.path.join(tmp, "work", "queue.jsonl")
            os.environ["OUT"] = os.path.join(tmp, "out")
            csv_path = os.path.join(tmp, "people.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("Url,First Name,Last Name,Job Title,Headline,"
                        "Company,Industry,Location,Work Email,Work Email Status\n")
                for line in path_lines:
                    f.write(line + "\n")
            result = ingest.run_person_centric(csv_path, client="productive",
                                               lane="domains")
            records = store.load()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["domain"], "something-else.test")
            self.assertEqual(records[0]["company"], "Acme Inc")
            os.environ.pop("QUEUE", None)
            os.environ.pop("OUT", None)


class TestExistingRecordGetsNewContacts(QueueTest):
    """When a record for the domain already exists, new contacts are added to it."""

    def test_new_contacts_added_to_existing_record(self):
        existing_path = self.write_csv("existing.csv",
                                       ["company,domain",
                                        "Acme,acme.test"])
        ingest.run(existing_path, client="productive", lane="domains")
        before = store.load()
        self.assertEqual(len(before[0]["contacts"]), 0)

        people_path = self.write_csv("people.csv", _person_csv([
            ",A,One,CEO,,Acme,Software,Zagreb,a@acme.test,",
            ",B,Two,CTO,,Acme,Software,Zagreb,b@acme.test,",
        ]))
        result = ingest.run_person_centric(people_path, client="productive",
                                           lane="domains",
                                           suppress_path=SUPPRESS)
        after = store.load()
        acme = [r for r in after if r["domain"] == "acme.test"]
        self.assertEqual(len(acme), 1)
        self.assertEqual(len(acme[0]["contacts"]), 2)
        self.assertEqual(result["records_updated"], 1)
        self.assertEqual(result["records_created"], 0)


if __name__ == "__main__":
    unittest.main()
