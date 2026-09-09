"""A domain is a company. Rows at one domain are people at that company.

The defect this file exists to prevent had two halves, and both shipped:

**Rows 2..N at a seen domain were discarded** as "duplicate row in this
file". At the domain layer a repeated domain is a repeated company, which
is true and was the wrong conclusion: a contact-level list of five people
at one company is not four mistakes.

**The contact columns were never written.** `commit` built each record
from `domain` and `company` alone, so the email and linkedin columns were
parsed, used for hygiene matching, and then dropped. A five-person file
committed as one company with *zero* contacts, while the upload screen
told the operator that other columns were "carried through".

What makes a row a distinct person is strong identity and nothing else: a
normalised mailbox or a canonical profile URL, exactly what `dedupe`
treats as identity. A name is never identity - two people share one and
one person has three - so five unnamed rows at one domain are still one
company.
"""
import os
import shutil
import tempfile
import unittest

from src import identity, repo as repo_module, store, workspaces
from src.web import upload
from tests.base import ProviderTest

WS = "productive"


class ImportTest(ProviderTest):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-import-")
        self._env = {k: os.environ.get(k) for k in
                     ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT",
                      "CLIENTS_DIR", "OUT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.environ["OUT"] = os.path.join(self.tmp, "out")

        from src.web import demodata
        demodata.install_configs()
        workspaces.ensure(WS, "Productive", client="productive")
        workspaces.ensure("contactout", "ContactOut", client="contactout")
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


class FivePeopleAtOneCompany(ImportTest):
    """The headline case, written the way somebody would actually send it."""

    CSV = ("company,domain,name,email\n"
           "Productive,prod-test.example,Ana CEO,ana@prod-test.example\n"
           "Productive,prod-test.example,Boris COO,boris@prod-test.example\n"
           "Productive,prod-test.example,Clara CFO,clara@prod-test.example\n"
           "Productive,prod-test.example,Dan VP Ops,dan@prod-test.example\n"
           "Productive,prod-test.example,Eve Delivery,eve@prod-test.example\n")

    def test_it_is_one_company(self):
        out = self.parse(self.CSV)
        self.assertEqual(out["unique"], 1)

    def test_it_is_five_contacts(self):
        out = self.parse(self.CSV)
        self.assertEqual(out["contacts"], 5)
        self.assertEqual(
            [c["name"] for c in out["rows"][0]["contacts"]],
            ["Ana CEO", "Boris COO", "Clara CFO", "Dan VP Ops",
             "Eve Delivery"])

    def test_nothing_is_reported_as_a_duplicate(self):
        """Four discarded rows was the old answer, and it was wrong."""
        out = self.parse(self.CSV)
        self.assertEqual(out["duplicates"], 0)
        self.assertEqual(out["duplicate_contacts"], 0)

    def test_the_four_later_rows_are_reported_as_people_joining(self):
        """"4 rows were dropped" and "4 more people joined this account"
        are opposite outcomes and must not share a counter."""
        out = self.parse(self.CSV)
        self.assertEqual(out["additional_contacts"], 4)
        self.assertEqual(len(out["attached"]), 4)

    def test_committing_writes_all_five_onto_one_record(self):
        parsed = self.parse(self.CSV)
        records = upload.commit(self.repo(), parsed)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]["contacts"]), 5)

    def test_every_committed_contact_has_a_stable_key(self):
        parsed = self.parse(self.CSV)
        records = upload.commit(self.repo(), parsed)
        keys = [c["key"] for c in records[0]["contacts"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(keys))

    def test_the_contacts_survive_a_reload(self):
        """Written to the queue, not merely returned."""
        parsed = self.parse(self.CSV)
        upload.commit(self.repo(), parsed)
        stored = self.repo().record("prod-test-example")
        self.assertEqual(len(stored["contacts"]), 5)


class WhatStillCountsAsADuplicate(ImportTest):

    def test_two_rows_with_no_identity_at_one_domain_are_one_company(self):
        """Nothing distinguishes them, so the second is a repeated company
        row and is still excluded."""
        out = self.parse("company,domain\nA,a-test.example\n"
                         "A,a-test.example\n")
        self.assertEqual(out["unique"], 1)
        self.assertEqual(out["duplicates"], 1)
        self.assertEqual(out["contacts"], 0)

    def test_the_same_mailbox_twice_is_one_contact(self):
        out = self.parse("company,domain,name,email\n"
                         "A,a-test.example,Ana,ana@a-test.example\n"
                         "A,a-test.example,Ana Again,ana@a-test.example\n")
        self.assertEqual(out["contacts"], 1)
        self.assertEqual(out["duplicate_contacts"], 1)

    def test_mailbox_identity_ignores_case_and_spacing(self):
        out = self.parse("company,domain,name,email\n"
                         "A,a-test.example,Ana,ana@a-test.example\n"
                         "A,a-test.example,Ana,  ANA@A-TEST.EXAMPLE  \n")
        self.assertEqual(out["contacts"], 1)
        self.assertEqual(out["duplicate_contacts"], 1)

    def test_the_same_profile_twice_is_one_contact(self):
        out = self.parse(
            "company,domain,name,linkedin\n"
            "A,a-test.example,Ana,https://linkedin.com/in/ana-x/\n"
            "A,a-test.example,Ana,https://www.linkedin.com/in/ana-x\n")
        self.assertEqual(out["contacts"], 1)
        self.assertEqual(out["duplicate_contacts"], 1)

    def test_a_name_is_never_identity(self):
        """Two different people can share a name and one person can be
        written three ways. A file of names alone is a domain list."""
        out = self.parse("company,domain,name\n"
                         "A,a-test.example,Ana\n"
                         "A,a-test.example,Boris\n")
        self.assertEqual(out["unique"], 1)
        self.assertEqual(out["contacts"], 0)
        self.assertEqual(out["duplicates"], 1)

    def test_a_person_with_only_a_profile_is_still_a_person(self):
        out = self.parse(
            "company,domain,name,email,linkedin\n"
            "A,a-test.example,Ana,ana@a-test.example,\n"
            "A,a-test.example,Dan,,https://linkedin.com/in/dan-x\n")
        self.assertEqual(out["contacts"], 2)
        self.assertEqual(out["additional_contacts"], 1)

    def test_two_people_at_different_companies_stay_apart(self):
        out = self.parse("company,domain,name,email\n"
                         "A,a-test.example,Ana,ana@a-test.example\n"
                         "B,b-test.example,Boris,boris@b-test.example\n")
        self.assertEqual(out["unique"], 2)
        self.assertEqual(out["additional_contacts"], 0)


class TheCountsAreHonest(ImportTest):

    def test_uploaded_counts_every_row_read(self):
        out = self.parse("company,domain,name,email\n"
                         "A,a-test.example,Ana,ana@a-test.example\n"
                         "A,a-test.example,Bo,bo@a-test.example\n"
                         "A,a-test.example,Bo,bo@a-test.example\n")
        self.assertEqual(out["uploaded"], 3)
        self.assertEqual(out["unique"], 1)
        self.assertEqual(out["contacts"], 2)
        self.assertEqual(out["additional_contacts"], 1)
        self.assertEqual(out["duplicate_contacts"], 1)

    def test_each_attached_row_says_which_row_it_was(self):
        """An operator reading the preview has to be able to find the row."""
        out = self.parse("company,domain,name,email\n"
                         "A,a-test.example,Ana,ana@a-test.example\n"
                         "A,a-test.example,Bo,bo@a-test.example\n")
        self.assertEqual([e["row"] for e in out["attached"]], [3])

    def test_working_state_does_not_leak_into_the_result(self):
        """`identities` was a set used while parsing. A set does not
        serialise, and nothing downstream needs it."""
        out = self.parse("company,domain,name,email\n"
                         "A,a-test.example,Ana,ana@a-test.example\n")
        self.assertNotIn("identities", out["rows"][0])


class ContactColumnsAreStillGuarded(ImportTest):

    def test_a_formula_in_an_email_column_is_not_stored(self):
        """The same attack as a formula in the domain column, on whoever
        opens the export later."""
        out = self.parse("company,domain,name,email\n"
                         'A,a-test.example,Ana,"=cmd|calc"\n')
        self.assertEqual(out["contacts"], 0)

    def test_a_formula_row_does_not_become_a_person(self):
        out = self.parse("company,domain,name,email\n"
                         "A,a-test.example,Ana,ana@a-test.example\n"
                         'A,a-test.example,Bo,"=HYPERLINK(1)"\n')
        self.assertEqual(out["contacts"], 1)
        self.assertEqual(out["duplicates"], 1)


class ImportStaysInsideOneWorkspace(ImportTest):

    def test_committed_records_belong_to_the_committing_workspace(self):
        parsed = self.parse("company,domain,name,email\n"
                            "A,a-test.example,Ana,ana@a-test.example\n")
        records = upload.commit(self.repo(), parsed)
        self.assertEqual(records[0]["client"], "productive")
        other = repo_module.Repo.for_user("op@x.test", WS)
        self.assertEqual(len(other.records()), 1)

    def test_a_committed_batch_cannot_be_committed_twice(self):
        parsed = self.parse("company,domain,name,email\n"
                            "A,a-test.example,Ana,ana@a-test.example\n")
        upload.commit(self.repo(), parsed)
        with self.assertRaises(upload.UploadRefused):
            upload.commit(self.repo(), parsed)


class KeysAreDeterministic(ImportTest):

    def test_the_same_file_produces_the_same_keys_twice(self):
        csv = ("company,domain,name,email\n"
               "A,a-test.example,Ana Smith,ana@a-test.example\n"
               "A,a-test.example,Bo Jones,bo@a-test.example\n")
        first = [c["key"] for c in
                 identity.assign_keys(
                     [dict(p) for p in self.parse(csv)["rows"][0]["contacts"]])]
        second = [c["key"] for c in
                  identity.assign_keys(
                      [dict(p) for p in self.parse(csv)["rows"][0]["contacts"]])]
        self.assertEqual(first, second)

    def test_two_people_with_the_same_name_both_survive(self):
        """A collision in the readable key is not a collision in identity."""
        parsed = self.parse("company,domain,name,email\n"
                            "A,a-test.example,Ana Smith,ana1@a-test.example\n"
                            "A,a-test.example,Ana Smith,ana2@a-test.example\n")
        records = upload.commit(self.repo(), parsed)
        keys = [c["key"] for c in records[0]["contacts"]]
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2)


if __name__ == "__main__":
    unittest.main()


class NoCellIsUnbounded(unittest.TestCase):
    """A CSV is untrusted input and a cell has no natural length.

    The contact columns were already bounded and the company name was not -
    same file, same source, two different answers. A sixty-thousand
    character company name renders a page nobody can scroll, and travels
    into a provider payload and a client PDF on the way.
    """

    def parse(self, company="Acme Services", first_name="Person"):
        from src.web import upload

        newline = chr(10)
        header = "company,domain,email,first_name" + newline
        row = f"{company},acme.test,a@acme.test,{first_name}" + newline
        return upload.parse((header + row).encode("utf-8"),
                            batch="b1", client="demo")

    def test_a_very_long_company_name_is_bounded(self):
        from src.web import upload

        parsed = self.parse(company="A" * 60000)
        self.assertEqual(len(parsed["rows"][0]["company"]), upload.MAX_CELL)

    def test_a_very_long_contact_field_is_bounded(self):
        from src.web import upload

        parsed = self.parse(first_name="B" * 60000)
        contact = parsed["rows"][0]["contacts"][0]
        self.assertEqual(len(contact["first_name"]), upload.MAX_CELL)

    def test_both_use_the_same_limit(self):
        """Two numbers for one question is how they drift apart."""
        from src.web import upload

        long_company = self.parse(company="A" * 60000)["rows"][0]["company"]
        long_person = self.parse(
            first_name="B" * 60000)["rows"][0]["contacts"][0]["first_name"]
        self.assertEqual(len(long_company), len(long_person))
        self.assertEqual(len(long_company), upload.MAX_CELL)

    def test_a_mailbox_truncated_out_of_shape_makes_no_contact(self):
        """The bound applies before identity is decided, so a truncated
        address is simply not an address - and a row with no identity is
        not a person. Better than a contact addressed to two hundred b's."""
        from src.web import upload

        newline = chr(10)
        header = "company,domain,email" + newline
        row = "Acme,acme.test," + "b" * 60000 + "@acme.test" + newline
        parsed = upload.parse((header + row).encode("utf-8"),
                              batch="b1", client="demo")
        self.assertEqual(parsed["rows"][0]["contacts"], [])

    def test_an_ordinary_name_is_untouched(self):
        parsed = self.parse(company="Acme Services")
        self.assertEqual(parsed["rows"][0]["company"], "Acme Services")
