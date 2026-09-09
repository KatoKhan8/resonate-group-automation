"""The importer keeps the title, because personas need it.

`title` was already canonical - `account.contact_card` and `dossier` both
read `contact["title"]` - and the CSV importer was the one path with no way
to fill it. A lead list always carries a title, and a 114-row file of named
decision makers arriving with no way to tell a CFO from an intern makes
persona selection and claim licensing guesswork.

Seniority and department are deliberately not accepted. They are not
canonical contact state anywhere in this system, and importing them would
be inventing a second representation of something `personas` derives from
the title.
"""
import unittest

from src.web import upload


class TheImporterKeepsTheTitle(unittest.TestCase):

    def parse(self, csv_text):
        return upload.parse(csv_text.encode("utf-8"), history=None)

    def test_a_title_column_reaches_the_contact(self):
        report = self.parse(
            "domain,company,email,title\n"
            "acme.test,Acme,cfo@acme.test,Chief Financial Officer\n")
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(contact["title"], "Chief Financial Officer")

    def test_a_missing_title_is_absent_rather_than_empty(self):
        """UNKNOWN is not the empty string. A blank cell must not become a
        title nobody wrote, because a downstream reader cannot tell the
        difference between "" and "we never knew"."""
        report = self.parse("domain,company,email\n"
                            "acme.test,Acme,cfo@acme.test\n")
        self.assertNotIn("title", report["rows"][0]["contacts"][0])

    def test_a_formula_in_the_title_column_is_refused(self):
        """The same guard the domain and email columns get. A CSV is
        attacker-controlled and a title lands in a client PDF."""
        report = self.parse(
            "domain,company,email,title\n"
            "acme.test,Acme,cfo@acme.test,=IMPORTXML(1)\n")
        self.assertNotIn("title", report["rows"][0]["contacts"][0])

    def test_title_is_not_identity(self):
        """Two people with the same title at one company are two people.

        Identity stays exactly what `dedupe` treats as identity - a
        normalised mailbox or a canonical profile URL. Adding a field must
        not quietly widen that.
        """
        report = self.parse(
            "domain,company,email,title\n"
            "acme.test,Acme,a@acme.test,Project Manager\n"
            "acme.test,Acme,b@acme.test,Project Manager\n")
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(len(report["rows"][0]["contacts"]), 2)

    def test_a_title_alone_still_does_not_make_a_person(self):
        """A row with a title and no mailbox or profile is not a contact.

        This is the historical collapse bug's other half: five unnamed rows
        at one domain are five duplicate company rows, and a title does not
        change that.
        """
        report = self.parse(
            "domain,company,title\n"
            "acme.test,Acme,Project Manager\n"
            "acme.test,Acme,Operations Lead\n")
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["rows"][0]["contacts"], [])

    def test_seniority_and_department_are_not_imported(self):
        """Not canonical contact state. Importing them would be a second
        representation of what the title already carries."""
        report = self.parse(
            "domain,company,email,title,seniority,department\n"
            "acme.test,Acme,a@acme.test,CFO,c_suite,Finance\n")
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(contact["title"], "CFO")
        self.assertNotIn("seniority", contact)
        self.assertNotIn("department", contact)


if __name__ == "__main__":
    unittest.main()
