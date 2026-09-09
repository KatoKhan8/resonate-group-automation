"""Somebody else's export, understood without being edited first.

`upload.parse` used to require a literal `domain` column and read `company`,
`email` and `title` by their exact lowercase names. No export anybody
actually has uses those words, so every real file was refused with an error
naming a column the user had never heard of.

The mapping is deterministic on purpose. A mapper that guesses is worse than
one that refuses, and two of the exclusions here are safety rather than
tidiness:

  `personal email` is never the address we would write to
  `company linkedin url` is never a person's identity

Both are preserved as source metadata, which is provenance and never a
decision.
"""
import unittest

from src import columns
from src.web import upload


def csv_of(header, *rows):
    return ("\n".join([header] + list(rows)) + "\n").encode("utf-8")


class Resolving(unittest.TestCase):

    def resolve(self, *headers):
        return columns.resolve(list(headers))

    def test_punctuation_and_case_carry_no_meaning(self):
        for spelling in ("First Name", "first_name", "FirstName", "FIRST-NAME",
                         "  first   name  "):
            with self.subTest(spelling=spelling):
                got = self.resolve(spelling)
                self.assertEqual(got["mapping"][spelling], columns.FIRST_NAME)

    def test_the_ordinary_spellings_of_each_field(self):
        cases = {
            "Company Website": columns.DOMAIN,
            "Domain": columns.DOMAIN,
            "Organization": columns.COMPANY,
            "Account Name": columns.COMPANY,
            "Work Email": columns.EMAIL,
            "Business Email": columns.EMAIL,
            "LinkedIn URL": columns.LINKEDIN,
            "Linkedin_Profile": columns.LINKEDIN,
            "Job Title": columns.TITLE,
            "Role": columns.TITLE,
            "Surname": columns.LAST_NAME,
            "Given Name": columns.FIRST_NAME,
            "Full Name": columns.NAME,
        }
        for header, field in cases.items():
            with self.subTest(header=header):
                self.assertEqual(self.resolve(header)["mapping"][header], field)

    def test_a_personal_address_is_never_the_address_we_write_to(self):
        """Safety, not tidiness. A personal address in a work export is
        exactly the one nobody consented to be contacted at."""
        got = self.resolve("Personal Email", "Work Email")
        self.assertEqual(got["chosen"][columns.EMAIL], "Work Email")
        self.assertIn("Personal Email", got["unmapped"])

    def test_a_personal_address_alone_still_does_not_become_the_email(self):
        got = self.resolve("Personal Email")
        self.assertNotIn(columns.EMAIL, got["chosen"])
        self.assertIn("Personal Email", got["unmapped"])

    def test_a_company_page_is_never_a_persons_identity(self):
        """`dedupe` treats a canonical profile URL as identity, so mapping a
        company page there would merge every employee into one contact."""
        got = self.resolve("Company LinkedIn URL", "LinkedIn URL")
        self.assertEqual(got["chosen"][columns.LINKEDIN], "LinkedIn URL")
        self.assertIn("Company LinkedIn URL", got["unmapped"])

    def test_a_company_page_alone_still_does_not_become_a_person(self):
        """Asserted without a real profile column beside it. With one
        present, ranking picks the right column even if the wrong spelling
        is an alias - so that test passes either way and proves nothing."""
        got = self.resolve("Company LinkedIn URL")
        self.assertNotIn(columns.LINKEDIN, got["chosen"])
        self.assertIn("Company LinkedIn URL", got["unmapped"])

    def test_the_more_specific_spelling_wins_and_the_other_is_reported(self):
        got = self.resolve("Email", "Work Email", "Domain")
        self.assertEqual(got["chosen"][columns.EMAIL], "Work Email")
        self.assertEqual(got["set_aside"][columns.EMAIL], ["Email"])
        self.assertIn("Email", got["unmapped"], "set aside is still kept")

    def test_the_same_header_twice_cannot_be_settled(self):
        """No rule distinguishes them, so neither is used."""
        got = self.resolve("Email", "Email", "Domain")
        self.assertIn(columns.EMAIL, got["ambiguous"])
        self.assertNotIn(columns.EMAIL, got["chosen"])

    def test_a_vague_header_is_not_guessed(self):
        for vague in ("URL", "Link", "ID", "Notes", "Value", "Owner"):
            with self.subTest(vague=vague):
                got = self.resolve(vague)
                self.assertEqual(got["mapping"], {})
                self.assertIn(vague, got["unmapped"])

    def test_missing_reports_what_no_column_supplied(self):
        got = self.resolve("First Name", "Work Email")
        self.assertEqual(columns.missing(got), [columns.DOMAIN])

    def test_every_spelling_belongs_to_one_field(self):
        """The alias lists must not drift into claiming the same word."""
        seen = {}
        for field, spellings in columns.ALIASES.items():
            for spelling in spellings:
                self.assertNotIn(spelling, seen,
                                 f"{spelling} claimed by {seen.get(spelling)} "
                                 f"and {field}")
                seen[spelling] = field


class ApplyingToARow(unittest.TestCase):

    def test_unknown_columns_are_kept_apart_from_canonical_ones(self):
        got = columns.resolve(["Company Website", "Custom Score"])
        canonical, source = columns.apply(
            {"Company Website": "acme.test", "Custom Score": "88"}, got)
        self.assertEqual(canonical, {columns.DOMAIN: "acme.test"})
        self.assertEqual(source, {"Custom Score": "88"})


class RealExports(unittest.TestCase):
    """Representative shapes, with fictional headers and fictional data."""

    def parse(self, data):
        return upload.parse(data, history=None)

    def test_a_sales_tool_export(self):
        report = self.parse(csv_of(
            "First Name,Last Name,Company Name,Company Website,Work Email,"
            "LinkedIn URL,Job Title,Custom Score",
            "Ada,Byrne,Acme Services,https://www.acme.test,ada@acme.test,"
            "https://www.linkedin.com/in/ada-byrne,CFO,88"))
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["contacts"], 1)
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(contact["email"], "ada@acme.test")
        self.assertEqual(contact["title"], "CFO")
        self.assertEqual(contact["source"], {"Custom Score": "88"})

    def test_a_crm_export(self):
        report = self.parse(csv_of(
            "Organization,Website,Email,Full Name,Position",
            "Borealis Ltd,borealis.test,chief@borealis.test,Cy Ray,Head of Ops"))
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(report["rows"][0]["company"], "Borealis Ltd")
        self.assertEqual(contact["name"], "Cy Ray")
        self.assertEqual(contact["title"], "Head of Ops")

    def test_a_hand_maintained_spreadsheet(self):
        report = self.parse(csv_of(
            "company,domain,contact name,role,business email",
            "Meridian,meridian.test,Wren Vale,COO,wren@meridian.test"))
        self.assertEqual(report["contacts"], 1)

    def test_an_account_only_list(self):
        report = self.parse(csv_of("Company Website",
                                   "acme.test", "borealis.test"))
        self.assertEqual(len(report["rows"]), 2)
        self.assertEqual(report["contacts"], 0)

    def test_a_contact_with_linkedin_but_no_email(self):
        report = self.parse(csv_of(
            "Company Website,Full Name,LinkedIn URL",
            "acme.test,Ada Byrne,https://www.linkedin.com/in/ada-byrne"))
        self.assertEqual(report["contacts"], 1)
        self.assertNotIn("email", report["rows"][0]["contacts"][0])

    def test_column_order_carries_no_meaning(self):
        report = self.parse(csv_of(
            "Job Title,Work Email,Company Website,First Name",
            "CFO,ada@acme.test,acme.test,Ada"))
        contact = report["rows"][0]["contacts"][0]
        self.assertEqual(contact["email"], "ada@acme.test")
        self.assertEqual(contact["title"], "CFO")

    def test_many_people_at_one_company_stay_many_people(self):
        """The historical collapse bug, now through a foreign header."""
        report = self.parse(csv_of(
            "Company Website,Work Email,Full Name",
            "acme.test,ada@acme.test,Ada Byrne",
            "acme.test,bo@acme.test,Bo Ng",
            "acme.test,cy@acme.test,Cy Ray"))
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(len(report["rows"][0]["contacts"]), 3)

    def test_the_refusal_names_something_a_person_can_act_on(self):
        with self.assertRaises(upload.UploadRefused) as caught:
            self.parse(csv_of("Name,Notes", "Ada,called them"))
        message = str(caught.exception)
        self.assertIn("no column identifies the company", message)
        self.assertIn("companywebsite", message)
        self.assertIn("Name", message, "it says what the file actually had")


class Adversarial(unittest.TestCase):

    def parse(self, data):
        return upload.parse(data, history=None)

    def test_a_byte_order_mark_does_not_hide_the_first_column(self):
        report = self.parse(
            b"\xef\xbb\xbfCompany Website,Work Email\n"
            b"acme.test,ada@acme.test\n")
        self.assertEqual(len(report["rows"]), 1)

    def test_a_quoted_comma_stays_one_value(self):
        report = self.parse(csv_of(
            "Company Website,Company Name",
            'acme.test,"Acme Services, Inc"'))
        self.assertEqual(report["rows"][0]["company"], "Acme Services, Inc")

    def test_an_embedded_line_break_stays_one_row(self):
        report = self.parse(
            b'Company Website,Company Name\nacme.test,"Acme\nServices"\n')
        self.assertEqual(len(report["rows"]), 1)

    def test_an_empty_row_is_excluded_not_fatal(self):
        report = self.parse(csv_of("Company Website,Work Email",
                                   "acme.test,ada@acme.test", ",", ""))
        self.assertEqual(len(report["rows"]), 1)
        self.assertTrue(report["excluded"])

    def test_a_formula_in_a_mapped_column_is_still_refused(self):
        """The guard reads the raw cell, and mapping must not strip the
        leading character that makes the trick work."""
        report = self.parse(csv_of("Company Website,Work Email",
                                   "=cmd|'/c calc'!A1,ada@acme.test"))
        self.assertEqual(report["rows"], [])
        self.assertTrue(any("formula" in e["reason"]
                            for e in report["excluded"]))

    def test_a_formula_in_an_unmapped_column_cannot_reach_canonical_state(self):
        report = self.parse(csv_of("Company Website,Custom Score",
                                   "acme.test,=IMPORTXML(1)"))
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["rows"][0]["contacts"], [],
                         "an unmapped column never makes a person")

    def test_a_leading_control_character_is_refused(self):
        """The case that distinguishes the raw cell from the stripped one.

        A tab followed by an equals sign is caught either way, because
        `lstrip` removes the tab and the equals sign is still there. A cell
        whose *only* signal is the control character is the one a guard
        reading the stripped value would wave through.
        """
        report = self.parse(
            "Company Website,Work Email\n\tacme.test,ada@acme.test\n"
            .encode("utf-8"))
        self.assertEqual(report["rows"], [])
        self.assertTrue(any("formula" in e["reason"]
                            for e in report["excluded"]))

    def test_foreign_characters_survive(self):
        report = self.parse(
            "Company Website,Company Name,Full Name\n"
            "kraft.test,Kräftig GmbH,Zoë Müller\n".encode("utf-8"))
        self.assertEqual(report["rows"][0]["company"], "Kräftig GmbH")

    def test_a_very_long_cell_is_bounded(self):
        report = self.parse(csv_of("Company Website,Company Name",
                                   "acme.test," + "x" * 5000))
        self.assertLessEqual(len(report["rows"][0]["company"]),
                             upload.MAX_CELL)

    def test_an_oversized_file_is_refused_rather_than_read(self):
        with self.assertRaises(upload.UploadRefused):
            self.parse(b"Company Website\n" + b"acme.test\n" * 900_000)

    def test_a_header_only_file_yields_nothing_and_does_not_raise(self):
        report = self.parse(csv_of("Company Website,Work Email"))
        self.assertEqual(report["rows"], [])
        self.assertEqual(report["uploaded"], 0)


class SourceColumnsCannotBypassSafety(unittest.TestCase):
    """Mission K's rule, and the one worth attacking.

    A file can carry any column at all. None of them may reach a decision:
    an uploaded `verified` column must not make an unverified address
    sendable, and an uploaded `stopped` column must not stop anybody.
    """

    def parse(self, data):
        return upload.parse(data, history=None)

    def test_an_uploaded_verification_column_is_only_provenance(self):
        report = self.parse(csv_of(
            "Company Website,Work Email,Verified,Verification Status,sendable",
            "acme.test,ada@acme.test,TRUE,valid,yes"))
        contact = report["rows"][0]["contacts"][0]
        self.assertNotIn("verification", contact)
        self.assertNotIn("sendable", contact)
        self.assertNotIn("verdict", contact)
        self.assertEqual(
            set(contact["source"]),
            {"Verified", "Verification Status", "sendable"})

    def test_the_contact_carries_only_canonical_fields_beside_source(self):
        report = self.parse(csv_of(
            "Company Website,Work Email,Region,Old Campaign",
            "acme.test,ada@acme.test,EMEA,Q1 blast"))
        contact = report["rows"][0]["contacts"][0]
        allowed = set(columns.CANONICAL) | {"row", "source"}
        self.assertTrue(set(contact) <= allowed, set(contact) - allowed)


if __name__ == "__main__":
    unittest.main()


class ThePreviewShowsTheDecision(unittest.TestCase):
    """A mapping the operator cannot see is a mapping they cannot check.

    Rendered rather than asserted on the report dict, because the report
    already carried this and the screen did not show it - which is the
    difference between a computed value and a consumed one.
    """

    def render(self, data):
        from src.web import pages
        report = upload.parse(data, history=None)
        return pages.upload_form("csrf-token", "demo", result=report)

    def test_it_names_the_column_each_field_came_from(self):
        html = self.render(csv_of(
            "Company Website,Work Email,Job Title",
            "acme.test,ada@acme.test,CFO"))
        self.assertIn("How the columns were read", html)
        self.assertIn("domain &lt;- Company Website", html)
        self.assertIn("email &lt;- Work Email", html)

    def test_it_names_the_columns_it_kept_but_did_not_use(self):
        html = self.render(csv_of(
            "Company Website,Personal Email,Custom Score",
            "acme.test,ada@gmail.test,88"))
        self.assertIn("not used for any decision", html)
        self.assertIn("Personal Email", html)
        self.assertIn("Custom Score", html)

    def test_it_says_when_a_column_could_not_be_settled(self):
        html = self.render(csv_of(
            "Company Website,Work Email,Work Email",
            "acme.test,a@acme.test,b@acme.test"))
        self.assertIn("more than once", html)
