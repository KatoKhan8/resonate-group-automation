"""TASK-311: the ingest carries the LinkedIn URL and operational columns.

Two source files carry columns the ingest silently discarded:

  1. A ContactOut / AI-ARK people-search export with a `Url` column that is
     a LinkedIn profile on 100% of its 33,887 rows. `columns` deliberately
     refuses to map the header "url" (too vague), so the profile was lost.

  2. A 51,741-row universe with `LinkedIn`, `LinkedIn_URL_Repaired` and
     three operational columns (headcount growth, products & services,
     employee count). The first was recognised; the second and the three
     operational columns were not.

The fix:

  - `linkedinurlrepaired` is now a LinkedIn alias in `columns`.
  - A `Url` column whose value passes `linkedin.canonical` is promoted to
    the contact's `linkedin` field. A company page or search URL is not.
  - Operational columns are extracted from source provenance and carried
    to `rec["company_facts"]` so the pack and copy path can use them.
"""
import os
import shutil
import tempfile
import unittest

from src import columns, identity, linkedin, repo as repo_module, store, workspaces
from src.web import upload
from tests.base import ProviderTest

WS = "productive"


def csv_of(header, *rows):
    return ("\n".join([header] + list(rows)) + "\n").encode("utf-8")


class ImportTest(ProviderTest):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-t311-")
        self._env = {k: os.environ.get(k) for k in
                     ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT",
                      "CLIENTS_DIR", "OUT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        from src.web import demodata
        demodata.install_configs()
        workspaces.ensure(WS, "Productive", client="productive")
        workspaces.add_user("op@x.test", "Op")
        workspaces.assign("op@x.test", WS, workspaces.OPERATOR)

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def repo(self):
        return repo_module.Repo.for_user("op@x.test", WS)

    def parse(self, csv_text, **kw):
        kw.setdefault("suppress", set())
        return upload.parse(csv_text.encode("utf-8"), batch="b1",
                            client="productive", **kw)


class LinkedInUrlRepairedIsRecognised(unittest.TestCase):
    """The column `LinkedIn_URL_Repaired` maps to the linkedin field."""

    def test_linkedin_url_repaired_is_a_linkedin_alias(self):
        got = columns.resolve(["LinkedIn_URL_Repaired", "Domain"])
        self.assertEqual(got["chosen"][columns.LINKEDIN],
                         "LinkedIn_URL_Repaired")

    def test_linkedin_url_repaired_value_lands_on_the_contact(self):
        report = upload.parse(csv_of(
            "Domain,LinkedIn_URL_Repaired,Name",
            "acme.test,https://www.linkedin.com/in/ada-byrne,Ada"),
            history=None)
        self.assertEqual(len(report["rows"]), 1)
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(contact["linkedin"],
                         "https://www.linkedin.com/in/ada-byrne")


class UrlColumnIsPromotedWhenItHoldsAProfile(ImportTest):
    """A column called 'Url' that holds a LinkedIn profile is promoted."""

    def test_a_profile_url_in_url_is_promoted_to_linkedin(self):
        report = self.parse(
            "Url,First Name,Last Name,Company,Domain,Work Email\n"
            "https://www.linkedin.com/in/ada-byrne,Ada,Byrne,Acme,acme.test,"
            "ada@acme.test\n")
        self.assertEqual(len(report["rows"]), 1)
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(contact["linkedin"],
                         "https://www.linkedin.com/in/ada-byrne")

    def test_a_company_page_in_url_is_not_promoted(self):
        """A company page is not a person. It stays in source provenance."""
        report = self.parse(
            "Url,First Name,Last Name,Company,Domain,Work Email\n"
            "https://www.linkedin.com/company/acme,Ada,Byrne,Acme,acme.test,"
            "ada@acme.test\n")
        contact = report["rows"][0]["contacts"][0]
        self.assertNotIn("linkedin", contact)
        self.assertIn("Url", contact.get("source", {}))

    def test_a_search_url_in_url_is_not_promoted(self):
        report = self.parse(
            "Url,First Name,Last Name,Company,Domain,Work Email\n"
            "https://www.linkedin.com/search/results/people/?keywords=cta,"
            "Ada,Byrne,Acme,acme.test,ada@acme.test\n")
        contact = report["rows"][0]["contacts"][0]
        self.assertNotIn("linkedin", contact)

    def test_an_existing_linkedin_column_is_not_overwritten(self):
        """If both 'LinkedIn' and 'Url' are present, the mapped one wins."""
        report = self.parse(
            "Url,LinkedIn,First Name,Last Name,Company,Domain\n"
            "https://www.linkedin.com/in/wrong,https://www.linkedin.com/in/"
            "right,Ada,Byrne,Acme,acme.test\n")
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(contact["linkedin"],
                         "https://www.linkedin.com/in/right")

    def test_the_promoted_profile_is_identity(self):
        """A promoted profile makes the row a distinct person."""
        report = self.parse(
            "Url,First Name,Last Name,Company,Domain\n"
            "https://www.linkedin.com/in/ada-byrne,Ada,Byrne,Acme,acme.test\n"
            "https://www.linkedin.com/in/ben-smith,Ben,Smith,Acme,acme.test\n")
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(len(report["rows"][0]["contacts"]), 2)

    def test_a_bare_vanity_name_in_url_is_promoted(self):
        """`linkedin.canonical` accepts a bare vanity name."""
        report = self.parse(
            "Url,First Name,Last Name,Company,Domain,Work Email\n"
            "ada-byrne,Ada,Byrne,Acme,acme.test,ada@acme.test\n")
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(contact["linkedin"],
                         "https://www.linkedin.com/in/ada-byrne")


class OperationalColumnsAreCarriedThrough(ImportTest):
    """Company-level facts from unmapped columns land on company_facts."""

    def test_headcount_growth_is_extracted(self):
        report = self.parse(
            "Domain,Company,Company_Total_headcount_growth_12_months\n"
            "acme.test,Acme,42\n")
        self.assertEqual(len(report["rows"]), 1)
        facts = report["rows"][0].get("company_facts", {})
        self.assertEqual(facts.get("headcount_growth_12m"), "42")

    def test_products_and_services_is_extracted(self):
        report = self.parse(
            "Domain,Company,Company_Product_and_Services\n"
            "acme.test,Acme,Outsourced project delivery\n")
        facts = report["rows"][0].get("company_facts", {})
        self.assertEqual(facts.get("products_and_services"),
                         "Outsourced project delivery")

    def test_employee_count_is_extracted(self):
        report = self.parse(
            "Domain,Company,Company_Employee_Count\n"
            "acme.test,Acme,75\n")
        facts = report["rows"][0].get("company_facts", {})
        self.assertEqual(facts.get("employees"), "75")

    def test_operational_facts_do_not_appear_in_source_provenance(self):
        """Extracted facts are removed from source, not duplicated."""
        report = self.parse(
            "Domain,Company,Name,Email,"
            "Company_Total_headcount_growth_12_months\n"
            "acme.test,Acme,Ada,ada@acme.test,42\n")
        contact = report["rows"][0]["contacts"][0]
        source = contact.get("source", {})
        self.assertNotIn("Company_Total_headcount_growth_12_months", source)

    def test_a_later_row_at_the_same_domain_fills_missing_facts(self):
        """First writer wins per key, matching contact merge semantics."""
        report = self.parse(
            "Domain,Company,Name,Email,"
            "Company_Total_headcount_growth_12_months,"
            "Company_Product_and_Services\n"
            "acme.test,Acme,Ada,ada@acme.test,42,\n"
            "acme.test,Acme,Ben,ben@acme.test,,Widget delivery\n")
        facts = report["rows"][0].get("company_facts", {})
        self.assertEqual(facts.get("headcount_growth_12m"), "42")
        self.assertEqual(facts.get("products_and_services"),
                         "Widget delivery")

    def test_all_three_task311_columns_together(self):
        report = self.parse(
            "Domain,Company,Name,Email,"
            "Company_Total_headcount_growth_12_months,"
            "Company_Product_and_Services,"
            "Company_Employee_Count\n"
            "acme.test,Acme,Ada,ada@acme.test,42,Project delivery,75\n")
        facts = report["rows"][0].get("company_facts", {})
        self.assertEqual(facts.get("headcount_growth_12m"), "42")
        self.assertEqual(facts.get("products_and_services"), "Project delivery")
        self.assertEqual(facts.get("employees"), "75")


class CommitAppliesCompanyFacts(ImportTest):
    """The commit function writes company_facts onto the record."""

    def test_commit_writes_operational_facts_to_the_record(self):
        parsed = self.parse(
            "Domain,Company,Name,Email,"
            "Company_Total_headcount_growth_12_months,"
            "Company_Product_and_Services,"
            "Company_Employee_Count\n"
            "acme.test,Acme,Ada,ada@acme.test,42,Project delivery,75\n")
        upload.commit(self.repo(), parsed)
        recs = store.load()
        self.assertEqual(len(recs), 1)
        facts = recs[0].get("company_facts", {})
        self.assertEqual(facts.get("headcount_growth_12m"), "42")
        self.assertEqual(facts.get("products_and_services"), "Project delivery")
        self.assertEqual(facts.get("employees"), "75")

    def test_commit_writes_linkedin_from_url_column(self):
        parsed = self.parse(
            "Url,First Name,Last Name,Company,Domain,Work Email\n"
            "https://www.linkedin.com/in/ada-byrne,Ada,Byrne,Acme,acme.test,"
            "ada@acme.test\n")
        upload.commit(self.repo(), parsed)
        recs = store.load()
        contacts = recs[0].get("contacts") or []
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0].get("linkedin"),
                         "https://www.linkedin.com/in/ada-byrne")

    def test_linkedin_verdict_passes_with_promoted_url(self):
        """channels.linkedin_verdict can read the promoted URL."""
        from src import channels
        parsed = self.parse(
            "Url,First Name,Last Name,Company,Domain,Work Email\n"
            "https://www.linkedin.com/in/ada-byrne,Ada,Byrne,Acme,acme.test,"
            "ada@acme.test\n")
        upload.commit(self.repo(), parsed)
        recs = store.load()
        contact = recs[0]["contacts"][0]
        ok, reason = channels.linkedin_verdict(recs[0], contact)
        self.assertTrue(ok, f"linkedin verdict failed: {reason}")


class AcceptanceCriteria(unittest.TestCase):
    """The acceptance command from the task, driven through a fixture."""

    def test_contacts_carry_linkedin_profiles_after_import(self):
        """Replicates the acceptance check with fixture data."""
        tmp = tempfile.mkdtemp(prefix="rga-t311-accept-")
        env = {k: os.environ.get(k) for k in
               ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT",
                "CLIENTS_DIR", "OUT")}
        try:
            store.use_directory(os.path.join(tmp, "work"))
            os.environ["CLIENTS_DIR"] = os.path.join(tmp, "clients")
            os.environ["OUT"] = os.path.join(tmp, "out")
            from src.web import demodata
            demodata.install_configs()
            workspaces.ensure(WS, "Productive", client="productive")
            workspaces.add_user("op@x.test", "Op")
            workspaces.assign("op@x.test", WS, workspaces.OPERATOR)

            csv_data = csv_of(
                "Url,First Name,Last Name,Company,Domain,Work Email",
                "https://www.linkedin.com/in/ada,Ada,A,Acme,acme.test,"
                "ada@acme.test",
                "https://www.linkedin.com/in/ben,Ben,B,Acme,acme.test,"
                "ben@acme.test",
                "https://www.linkedin.com/in/clara,Clara,C,Other,other.test,"
                "clara@other.test",
            )
            parsed = upload.parse(csv_data, batch="b1", client="productive",
                                  suppress=set())
            repo = repo_module.Repo.for_user("op@x.test", WS)
            upload.commit(repo, parsed)

            rs = store.load()
            c = [x for r in rs for x in (r.get("contacts") or [])]
            n = sum(1 for x in c
                    if "linkedin.com/in/" in str(
                        x.get("linkedin") or "").lower())
            self.assertEqual(n, 3, f"{n} of {len(c)} contacts carry a "
                                   f"LinkedIn profile")
            self.assertGreater(n, 0)
        finally:
            for key, value in env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
