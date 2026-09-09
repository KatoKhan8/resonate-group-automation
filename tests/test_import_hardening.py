"""What a real client's export looks like, and what the preview owed it.

Three defects, and the first is the one that mattered.

**Only the first person at each company was screened.** The hygiene check
sat after the branch that attaches a second contact to a company already in
the file, so on a list of five people at one account, four were never
compared against previous outreach, replies or the agency suppression
index - and the preview said nothing. The whole point of a preview is to be
told before anybody spends a credit.

**A semicolon export was refused outright.** `csv.DictReader` with the
default dialect read `Company Website;Work Email` as one column, so the file
came back "no column identifies the company" - which is true, and is the
wrong thing to say about the default export format of most of Europe.

**A row wider than its header lost cells silently.** They arrived under
`DictReader`'s restkey and were dropped by a filter that removed falsy keys.
A shifted column is how an email address ends up in a title field.
"""
import unittest

from src import accountpolicy as ap, hygiene, store
from src.web import upload
from tests.test_hygiene import HygieneTest, JOHN, SARAH, WS


class TheDelimiter(unittest.TestCase):
    """Chosen by whether it works, not by counting characters."""

    def test_a_comma_file_stays_a_comma_file(self):
        self.assertEqual(upload.sniff("domain,email,name"), ",")

    def test_a_semicolon_export_is_read(self):
        self.assertEqual(
            upload.sniff("Company Website;Work Email;First Name"), ";")

    def test_a_tab_export_is_read(self):
        self.assertEqual(upload.sniff("Company Website\tWork Email"), "\t")

    def test_a_pipe_export_is_read(self):
        self.assertEqual(upload.sniff("Company Website|Work Email"), "|")

    def test_commas_can_outnumber_the_real_delimiter(self):
        """The discriminator between trying a delimiter and counting one.

        Three commas, two semicolons. Counting characters - which is what
        `csv.Sniffer` does - picks the comma and reads the whole file as
        one column. Trying each one and keeping whichever produces a
        column that identifies the company picks the semicolon.
        """
        header = 'Company Website;"Acme, Inc, and Sons, Ltd";Work Email'
        self.assertGreater(header.count(","), header.count(";"))
        self.assertEqual(upload.sniff(header), ";")

    def test_a_header_nothing_maps_falls_back_to_a_comma(self):
        """Refusing is still the answer, and it should be the same refusal
        it has always been rather than a new one about delimiters."""
        self.assertEqual(upload.sniff("alpha|beta|gamma"), ",")

    def test_an_empty_file_does_not_explode(self):
        self.assertEqual(upload.sniff(""), ",")

    def test_the_whole_file_parses_through_the_chosen_delimiter(self):
        out = upload.parse(
            "Company Website;Work Email;First Name\n"
            "acme.test;john@acme.test;John\n".encode("utf-8"),
            batch="b", client=WS)
        self.assertEqual(out["delimiter"], ";")
        self.assertEqual(len(out["rows"]), 1)
        self.assertEqual(out["rows"][0]["domain"], "acme.test")
        self.assertEqual(out["rows"][0]["contacts"][0]["email"],
                         "john@acme.test")

    def test_the_report_says_which_delimiter_was_used(self):
        out = upload.parse("domain,email\nacme.test,j@acme.test\n"
                           .encode("utf-8"), batch="b", client=WS)
        self.assertEqual(out["delimiter"], ",")


class ARowThatDoesNotMatchItsHeader(unittest.TestCase):

    def parse(self, text):
        return upload.parse(text.encode("utf-8"), batch="b", client=WS)

    def test_extra_cells_are_reported_rather_than_dropped(self):
        out = self.parse("domain,email\n"
                         "acme.test,j@acme.test,stray,cells\n")
        self.assertEqual(out["ragged_rows"], 1)
        self.assertIn("more cells", out["ragged"][0]["reason"])

    def test_missing_cells_are_reported(self):
        out = self.parse("domain,email,title\nacme.test\n")
        self.assertEqual(out["ragged_rows"], 1)
        self.assertIn("fewer cells", out["ragged"][0]["reason"])

    def test_a_ragged_row_is_still_imported(self):
        """It is a warning about shape, not a refusal. Dropping the row
        would lose the company over a trailing comma."""
        out = self.parse("domain,email\nacme.test,j@acme.test,stray\n")
        self.assertEqual(len(out["rows"]), 1)
        self.assertEqual(out["rows"][0]["domain"], "acme.test")

    def test_a_well_formed_file_reports_nothing(self):
        out = self.parse("domain,email\nacme.test,j@acme.test\n"
                         "other.test,k@other.test\n")
        self.assertEqual(out["ragged_rows"], 0)

    def test_the_row_number_is_the_one_in_the_file(self):
        out = self.parse("domain,email\nacme.test,j@acme.test\n"
                         "other.test,k@other.test,stray\n")
        self.assertEqual(out["ragged"][0]["row"], 3)


class EveryPersonIsScreened(HygieneTest):
    """The defect that mattered: four people out of five, unchecked."""

    def parse(self, csv_text, rec=None):
        recs = [rec] if rec is not None else []
        return upload.parse(csv_text.encode("utf-8"), batch="b", client=WS,
                            history=hygiene.index(recs, workspace=WS))

    def three_at_acme(self):
        return ("domain,email,name\n"
                "acme.test,new@acme.test,New Person\n"
                "acme.test,john@acme.test,John Smith\n"
                "acme.test,other@acme.test,Other Person\n")

    def test_a_suppressed_colleague_is_found_on_the_second_row(self):
        """John unsubscribed. He is the second person at this company in
        the file, and before this the preview never looked at him."""
        rec = self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        out = self.parse(self.three_at_acme(), rec)
        verdicts = {s["who"]: s["verdict"]["verdict"] for s in out["screened"]}
        self.assertEqual(verdicts["John Smith"], hygiene.SUPPRESSED_CONTACT)

    def test_the_summary_counts_people_not_company_rows(self):
        rec = self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        out = self.parse(self.three_at_acme(), rec)
        self.assertEqual(out["hygiene"]["total"], 3)
        self.assertEqual(out["hygiene"]["by_verdict"]
                         [hygiene.SUPPRESSED_CONTACT], 1)

    def test_the_verdict_travels_with_the_person(self):
        rec = self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        out = self.parse(self.three_at_acme(), rec)
        people = out["rows"][0]["contacts"]
        found = next(c for c in people if c["email"] == "john@acme.test")
        self.assertEqual(found["hygiene"]["verdict"],
                         hygiene.SUPPRESSED_CONTACT)

    def test_the_first_person_still_gets_one(self):
        rec = self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        out = self.parse("domain,email,name\n"
                         "acme.test,john@acme.test,John Smith\n"
                         "acme.test,new@acme.test,New Person\n", rec)
        first = out["rows"][0]["contacts"][0]
        self.assertEqual(first["hygiene"]["verdict"],
                         hygiene.SUPPRESSED_CONTACT)

    def test_two_engaged_colleagues_are_both_found(self):
        rec = self.record()
        self.replied(rec, JOHN, ap.UNSUBSCRIBE)
        self.replied(rec, SARAH, ap.POSITIVE, at="2026-08-06T09:00:00+00:00")
        out = self.parse("domain,email,name\n"
                         "acme.test,new@acme.test,New Person\n"
                         "acme.test,john@acme.test,John Smith\n"
                         "acme.test,sarah@acme.test,Sarah Jones\n", rec)
        found = {s["who"] for s in out["screened"]
                 if s["verdict"]["action"] != "eligible"}
        self.assertIn("John Smith", found)
        self.assertIn("Sarah Jones", found)

    def test_a_company_row_with_nobody_on_it_still_counts_once(self):
        out = self.parse("domain\nacme.test\nother.test\n", self.record())
        self.assertEqual(out["hygiene"]["total"], 2)

    def test_a_row_dropped_as_already_here_leaves_the_count(self):
        """It is not in the list any more, so it is not in the count of
        what the list contains.

        The row carries nobody, which is what "already here" is about. It
        used to carry an address, and the drop took the person with it -
        see the test below, which is the half that was wrong.
        """
        rec = self.record()
        out = upload.parse("domain\nacme.test\n".encode("utf-8"),
                           batch="b", client=WS,
                           existing_domains={"acme.test"},
                           history=hygiene.index([rec], workspace=WS))
        self.assertEqual(out["rows"], [])
        self.assertEqual(out["hygiene"]["total"], 0)

    def test_a_new_person_at_a_known_company_is_not_dropped_with_it(self):
        """"This client already has this domain" is true of the company
        and false of the person.

        A contact-level list re-uploaded with more people on it had every
        one of those rows dropped under that reason, so the new people
        were discarded and the sentence explaining it described something
        else. `commit` merges on identity, so keeping the row cannot
        duplicate anybody who is already on the record.
        """
        rec = self.record()
        out = upload.parse("domain,email\nacme.test,fresh@acme.test\n"
                           .encode("utf-8"), batch="b", client=WS,
                           existing_domains={"acme.test"},
                           history=hygiene.index([rec], workspace=WS))
        self.assertEqual([r["domain"] for r in out["rows"]], ["acme.test"])
        self.assertEqual(
            [c["email"] for c in out["rows"][0]["contacts"]],
            ["fresh@acme.test"])

    def test_without_history_nobody_is_screened(self):
        """None means the pass did not run, which is not the same
        statement as "it ran and found nothing"."""
        out = upload.parse(self.three_at_acme().encode("utf-8"),
                           batch="b", client=WS)
        self.assertIsNone(out["hygiene"])
        self.assertEqual(out["screened"], [])

    def test_the_screen_reaches_the_page(self):
        """The recurring defect here is a thing computed correctly that
        nothing downstream reads."""
        from src.web import pages

        rec = self.replied(self.record(), JOHN, ap.UNSUBSCRIBE)
        out = self.parse(self.three_at_acme(), rec)
        html = pages.upload_form("csrf", WS, result=out)
        # All three by name. Walking the company rows showed the first
        # person and silently dropped the colleagues, which is the whole
        # defect seen from the screen.
        for who in ("New Person", "John Smith", "Other Person"):
            with self.subTest(who=who):
                self.assertIn(who, html)
        self.assertIn("0 of 3 people are cold-eligible", html)


class AnIdentityIsNeverShortened(unittest.TestCase):
    """A cut address is not a broken address. It is a different one.

    `MAX_CELL` is 200 and RFC allows 254, so the 201-254 range is exactly
    where long real addresses live - and cutting one there does not
    produce a value that fails later. It produces a syntactically valid
    mailbox, at a different domain, which `normalise_email` accepts and
    `contact_identity` then stores as canonical identity. It would be
    counted as an address needing verification and a credit spent
    confirming a mailbox nobody has.

    An existing test reasons that "a truncated address is simply not an
    address". That holds only when the cut lands before the `@`.

    Refused whole rather than kept short, and listed with a reason,
    because a row that vanishes silently is the thing the preview exists
    to prevent.
    """

    def parsed(self, address):
        return upload.parse(
            ("company,domain,email\r\nCairn,cairn.test,%s\r\n" % address)
            .encode("utf-8"), batch="b", client="demo")

    def long_address(self):
        local = "a" * 180
        return local + "@northwind-holdings-europe.test"

    def test_an_over_long_address_is_not_stored(self):
        address = self.long_address()
        self.assertGreater(len(address), upload.MAX_CELL)
        out = self.parsed(address)
        stored = [c.get("email") for r in out["rows"]
                  for c in r.get("contacts") or []]
        self.assertEqual(stored, [])

    def test_it_is_not_stored_as_a_different_address_either(self):
        """The specific harm. The cut value is valid and belongs to
        somebody else's domain."""
        address = self.long_address()
        cut = address[:upload.MAX_CELL]
        self.assertIn("@", cut, "the fixture must cut after the @ to be "
                                "about the defect")
        out = self.parsed(address)
        stored = [c.get("email") for r in out["rows"]
                  for c in r.get("contacts") or []]
        self.assertNotIn(cut, stored)

    def test_the_row_is_listed_with_a_reason(self):
        out = self.parsed(self.long_address())
        reasons = " ".join(e["reason"] for e in out["excluded"])
        self.assertIn("email", reasons)
        self.assertIn("longer than", reasons)

    def test_an_ordinary_address_is_untouched(self):
        out = self.parsed("ada@cairn.test")
        stored = [c.get("email") for r in out["rows"]
                  for c in r.get("contacts") or []]
        self.assertEqual(stored, ["ada@cairn.test"])

    def test_a_long_free_text_field_is_still_capped(self):
        """The cap still exists where cutting is harmless. Only identity
        is refused rather than shortened."""
        title = "H" * 400
        out = upload.parse(
            ("company,domain,email,title\r\n"
             "Cairn,cairn.test,ada@cairn.test,%s\r\n" % title)
            .encode("utf-8"), batch="b", client="demo")
        kept = out["rows"][0]["contacts"][0]["title"]
        self.assertEqual(len(kept), upload.MAX_CELL)


class TwoColumnsWithOneName(unittest.TestCase):
    """The one ambiguity ranking cannot settle, and why no picker exists.

    Two headers that mean the same field but are spelled differently -
    `Email` and `Work Email` - are settled by rank, and the loser is
    reported as set aside. Two headers spelled *identically* are not: both
    are equally the field, and choosing between them is a coin flip over
    whose values are real.

    A screen offering that choice would be asking a question only the file
    can answer, so what was built is a refusal that says which columns and
    what to do about them. Picking the first is the one thing that must
    not happen, and the first test says so.
    """

    def parse(self, text):
        return upload.parse(text.encode("utf-8"), batch="b", client=WS)

    def duplicated(self):
        return self.parse("domain,Email,Email\n"
                          "acme.test,real@x.test,stale@x.test\n")

    def test_neither_copy_is_used(self):
        out = self.duplicated()
        self.assertEqual(out["mapping"]["ambiguous"], ["email"])
        self.assertEqual(out["rows"][0]["contacts"], [])

    def test_the_rest_of_the_file_is_read_normally(self):
        self.assertEqual(self.duplicated()["rows"][0]["domain"], "acme.test")

    def test_two_different_headers_for_one_field_are_settled_by_rank(self):
        """The common case, and it is not ambiguous."""
        out = self.parse("domain,Work Email\nacme.test,a@x.test\n")
        self.assertEqual(out["mapping"]["ambiguous"], [])
        self.assertEqual(out["rows"][0]["contacts"][0]["email"], "a@x.test")

    def test_the_screen_says_which_columns_and_what_to_do(self):
        from src.web import pages

        html = pages.upload_form("csrf", WS, result=self.duplicated())
        self.assertIn("more than one column called Email", html)
        self.assertIn("delete or rename", html)
        self.assertIn("nothing has been committed", html)


class WhatCouldBeWrittenTo(HygieneTest):
    """The number an operator wants before committing anything: how many of
    these can I email, and what does finding out about the rest cost."""

    def parse(self, csv_text, recs=(), policy=None):
        return upload.parse(csv_text.encode("utf-8"), batch="b", client=WS,
                            history=hygiene.index(list(recs), workspace=WS),
                            policy=policy)

    def test_a_new_address_is_new(self):
        found = self.parse(
            "domain,email\nacme.test,nobody@acme.test\n")["verification"]
        self.assertEqual(found["new"], 1)
        self.assertEqual(found["sendable"], 0)
        self.assertEqual(found["needs_verification"], 1)

    def test_an_address_we_hold_and_cannot_send_to_is_not_new(self):
        found = self.parse("domain,email\nacme.test,john@acme.test\n",
                           [self.record()])["verification"]
        self.assertEqual(found["new"], 0)
        self.assertEqual(found["known"], 1)

    def test_a_cleared_address_is_counted_as_cleared(self):
        """The one number that means no bill for this row."""
        from src import verification

        rec = self.record()
        contact = rec["contacts"][0]
        evidence = [
            verification.result("contactout", verification.S_VALID,
                                contact["email"]),
            verification.result("deliverable", verification.S_VALID,
                                contact["email"])]
        verification.apply(contact, verification.decide(evidence), evidence)
        store.save([rec])
        found = self.parse("domain,email\nacme.test,john@acme.test\n",
                           [rec])["verification"]
        self.assertEqual(found["sendable"], 1)
        self.assertEqual(found["needs_verification"], 0)

    def test_a_stored_verdict_with_no_evidence_under_it_is_not_cleared(self):
        """The drift `lint.sendable` exists to catch.

        A contact carrying `state: verified` over an empty evidence list is
        something this repository has actually had - in its own fixtures -
        and it works right up until sendability is read from the flag
        instead of recomputed from the evidence. The preview must not count
        it as an address it can write to.
        """
        rec = self.record()
        rec["contacts"][0]["verification"] = {"state": "verified",
                                              "results": {}, "providers": []}
        store.save([rec])
        found = self.parse("domain,email\nacme.test,john@acme.test\n",
                           [rec])["verification"]
        self.assertEqual(found["sendable"], 0)
        self.assertEqual(found["known"], 1)

    def test_a_person_with_no_address_is_not_an_address_that_failed(self):
        found = self.parse(
            "domain,linkedin\nacme.test,https://linkedin.com/in/dana\n"
        )["verification"]
        self.assertEqual(found["no_address"], 1)
        self.assertEqual(found["with_address"], 0)

    def test_the_estimate_is_a_plan_and_says_so(self):
        found = self.parse("domain,email\nacme.test,a@acme.test\n"
                           "other.test,b@other.test\n")["verification"]
        self.assertEqual(found["needs_verification"], 2)
        self.assertGreaterEqual(found["max_calls"], found["planned_calls"])
        self.assertIn("not a spend", found["note"])

    def test_the_estimate_is_arithmetic_rather_than_a_call(self):
        """One plan for the whole file. Pricing each address separately
        would be the same number arrived at slowly - and it is the kind of
        loop that turns into a provider call when somebody changes it."""
        from src import verification

        called = []
        original = verification.plan

        def counted(*a, **kw):
            called.append(1)
            return original(*a, **kw)

        verification.plan = counted
        try:
            self.parse("domain,email\nacme.test,a@acme.test\n"
                       "b.test,b@b.test\nc.test,c@c.test\n")
        finally:
            verification.plan = original
        self.assertEqual(len(called), 1)

    def test_without_history_nothing_is_claimed(self):
        out = upload.parse("domain,email\nacme.test,a@acme.test\n"
                           .encode("utf-8"), batch="b", client=WS)
        self.assertIsNone(out["verification"])

    def test_it_reaches_the_page(self):
        from src.web import pages

        out = self.parse("domain,email\nacme.test,nobody@acme.test\n")
        html = pages.upload_form("csrf", WS, result=out)
        self.assertIn("What could be written to", html)
        self.assertIn("New to this workspace", html)
        self.assertIn("not a spend", html)


class TheColumnsAnImportKept(HygieneTest):
    """A file arrives with a phone number, a CRM id and an owner.

    None of them means anything to this system - there is no phone channel
    and no CRM - so they are kept as provenance and never read to decide
    anything. That part was right. What was missing is that nothing could
    hand them back: the upload screen said the columns were kept, the
    contact carried them, and no screen, no export and no channel could
    reach them. Kept and unreachable is the same as lost, with a sentence
    claiming otherwise.

    A canonical `phone` column would have been the wrong fix. There is
    nothing that would read it, so it would be a field computed correctly
    and consumed by nobody - this codebase's own recurring defect, added on
    purpose.
    """

    def imported(self, csv_text):
        from src import repo as repo_module
        from src.web import upload

        parsed = upload.parse(csv_text.encode("utf-8"), batch="b",
                              client=WS)
        repo = repo_module.Repo.for_client(WS)
        upload.commit(repo, parsed)
        return repo

    def test_an_unknown_column_is_kept_on_the_contact(self):
        repo = self.imported(
            "domain,email,Phone,CRM ID\n"
            "acme.test,a@acme.test,+385 1 555 0100,CRM-42\n")
        contact = repo.records()[0]["contacts"][0]
        self.assertEqual(contact["source"]["Phone"], "+385 1 555 0100")
        self.assertEqual(contact["source"]["CRM ID"], "CRM-42")

    def test_the_export_hands_it_back(self):
        from src.web import api

        repo = self.imported(
            "domain,email,Phone\nacme.test,a@acme.test,+385 1 555 0100\n")
        csv_text = api.export_contacts(repo)
        self.assertIn("source:Phone", csv_text)
        self.assertIn("+385 1 555 0100", csv_text)

    def test_a_file_with_no_extra_columns_exports_no_extra_columns(self):
        from src.web import api

        repo = self.imported("domain,email\nacme.test,a@acme.test\n")
        header = api.export_contacts(repo).splitlines()[0]
        self.assertNotIn("source:", header)

    def test_it_is_still_never_read_to_decide_anything(self):
        """The reason it is safe to hand back. A column nobody recognises
        must not be able to make somebody contactable."""
        from src import lint

        repo = self.imported(
            "domain,email,Verified,Sendable\n"
            "acme.test,a@acme.test,yes,yes\n")
        contact = repo.records()[0]["contacts"][0]
        self.assertFalse(lint.sendable(contact))
        self.assertIn("Verified", contact["source"])

    def test_a_flood_of_columns_is_capped_and_says_so(self):
        from src.web import api

        many = [f"X{n}" for n in range(30)]
        header = "domain,email," + ",".join(many)
        row = "acme.test,a@acme.test," + ",".join(str(n) for n in range(30))
        repo = self.imported(header + "\n" + row + "\n")
        line = api.export_contacts(repo).splitlines()[0]
        self.assertEqual(line.count("source:X"), api.MAX_SOURCE_COLUMNS)
        self.assertIn("more columns not exported", line)


if __name__ == "__main__":
    unittest.main()
