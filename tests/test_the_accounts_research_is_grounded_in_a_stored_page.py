#!/usr/bin/env python3
"""Every specific this account can license is verbatim on a stored page.

`TASK-425` / `P0-C`. The operator's rule: a fact needs a source URL and a
stored page, or it is not admitted, and a fabricated source row is worse than
no fixture. The selected account is a REAL company, so that stops being a
slogan and becomes checkable - and this is the check.

## THE TWO RULES, AND WHY THE STRICT ONE IS THE LOAD-BEARING ONE

  STRICT   every `copylint.specifics_in` value in a committed research row
           appears VERBATIM in the stored excerpts of the page that row cites.

           These are exactly the tokens that can license a prospect-facing
           claim. A figure or a capitalised name in a row is a licence for the
           same figure or name in an email, so an unsourced one is a licence to
           assert something nobody read anywhere.

  WEAK     every content word of five characters or more appears on the same
           page. The committed rows are built by JOINING stored excerpts, so
           this one has no exceptions at all: a word that is not on the page
           cannot get into a row without somebody retyping a sentence, which is
           the thing that must not happen.

## AND THE REDACTION, WHICH IS THE HALF A LIST CANNOT DO

The about page carries a schema.org leadership block naming four real people,
and the estate's own research row for that page carries all four, because the
extractor took the whole page. **That row is not committed**: the module builds
its rows from chosen, name-free excerpts, and the choice was self-tested at
build time against every one of those names. **That list of names is not in
this repository and must never be**: a guard that has to name real people in
order to protect them has retired itself.

So the committed check is a PROPERTY instead: every multi-word capitalised
phrase in every stored value has to be one of an enumerated set of
organisation, award and product names. A person's name is exactly that shape,
so a new one cannot arrive silently - it fails here and becomes a human
decision, which is the same trade `tests/test_fixture_hygiene.py` makes for
phone numbers.
"""
import re
import unittest

from src import copylint, packfacts
from tests import task425fixture as fixture

WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\+\d[\d ().-]{7,}\d")
PROFILE = re.compile(r"linkedin\.com/(in|company)/|facebook\.com/|twitter\.com/",
                     re.I)
CAPITALISED_PHRASE = re.compile(r"\b[A-Z][a-z]{1,}(?:[ -][A-Z][a-z]{1,})+\b")

#: Multi-word capitalised phrases allowed in a stored value. Every one is an
#: organisation, an award or a product. NONE is a person, and that is what this
#: set is for. Classified by hand, 2026-09-28.
KNOWN_CAPITALISED = frozenset({
    "Brand IQ",
    "Western Europe",
    "United States",
    "Best Programmatic Solutions Provider",
    "Martech Outlook Magazine",
    "Ada Tester",                      # the declared placeholder, not a person
})

#: RFC 2606 / RFC 6761 reserved suffixes.
RESERVED = (".test", ".example", ".invalid", ".localhost")

ROWS = tuple(fixture.RESEARCH) + (fixture.FACT_CHANGED_B,)


def excerpt_text(url):
    return " ".join(fixture.excerpts_for(url)).lower()


def every_stored_value():
    """`(where, value)` for every string this fixture commits from a page."""
    out = []
    for page in fixture.stored_evidence().get("pages") or ():
        for excerpt in page.get("excerpt") or ():
            out.append((page.get("url"), excerpt))
    for row in ROWS:
        out.append((row["source_url"], row["fact"]))
    for contact in fixture.CONTACTS:
        out.append(("placeholder", contact["name"]))
    return out


class TestTheStoredEvidenceIsReal(unittest.TestCase):

    def test_every_cited_page_has_stored_evidence(self):
        for row in ROWS:
            self.assertTrue(
                fixture.excerpts_for(row["source_url"]),
                "%s has no stored page, so its fact is not admitted evidence"
                % row["source_url"])

    def test_every_stored_page_records_what_was_read_and_when(self):
        pages = fixture.stored_evidence().get("pages") or ()
        self.assertTrue(pages)
        for page in pages:
            with self.subTest(url=page.get("url")):
                self.assertEqual(page.get("http_status"), 200)
                self.assertEqual(page.get("outcome"), "HTTP_SUCCESS")
                self.assertRegex(str(page.get("retrieved_at")),
                                 r"^\d{4}-\d{2}-\d{2}T")
                self.assertRegex(str(page.get("sha256_extracted_text")),
                                 r"^[0-9a-f]{64}$")
                self.assertGreater(page.get("extracted_chars") or 0, 500)
                self.assertTrue(page.get("excerpt"))

    def test_every_page_is_on_the_accounts_own_domain(self):
        for page in fixture.stored_evidence().get("pages") or ():
            with self.subTest(url=page.get("url")):
                self.assertTrue(
                    packfacts.same_site(page.get("url"), fixture.DOMAIN),
                    "not this account's own site, so a row citing it could "
                    "not be identity-admitted")

    def test_the_evidence_names_the_account_that_was_selected(self):
        stored = fixture.stored_evidence()
        self.assertEqual(stored.get("domain"), fixture.DOMAIN)
        self.assertEqual(stored.get("record_id"), fixture.RECORD_ID)


class TestEverySpecificIsVerbatimOnItsPage(unittest.TestCase):

    def test_strict_rule_every_licensable_token_is_sourced(self):
        for row in ROWS:
            page = excerpt_text(row["source_url"])
            for specific in copylint.specifics_in(row["fact"]):
                with self.subTest(url=row["source_url"], specific=specific):
                    self.assertIn(
                        specific.lower(), page,
                        "this token can license a claim in an email and "
                        "appears in no stored excerpt of the page cited")

    def test_weak_rule_every_content_word_is_sourced(self):
        for row in ROWS:
            page = excerpt_text(row["source_url"])
            unsourced = sorted({w.lower() for w in WORD.findall(row["fact"])
                                if len(w) >= 5 and w.lower() not in page})
            with self.subTest(url=row["source_url"]):
                self.assertEqual(unsourced, [],
                                 "not on the cited page. A committed row is "
                                 "stored excerpts joined, never retyped")

    def test_the_claim_sentence_asserts_nothing_off_the_page(self):
        page = excerpt_text(fixture.EVIDENCE_UNDER_TEST)
        for specific in copylint.specifics_in(fixture.CLAIM_SENTENCE):
            with self.subTest(specific=specific):
                self.assertIn(specific.lower(), page)


class TestNoRealPersonalDataIsCommitted(unittest.TestCase):
    """ABSOLUTE rules over every value, plus the KNOWN-SET name check."""

    def test_no_value_carries_an_email_address(self):
        hits = ["%s: %s" % (w, EMAIL.findall(v))
                for w, v in every_stored_value() if EMAIL.search(v)]
        self.assertEqual(hits, [])

    def test_no_value_carries_a_phone_number(self):
        hits = ["%s: %s" % (w, PHONE.findall(v))
                for w, v in every_stored_value() if PHONE.search(v)]
        self.assertEqual(hits, [])

    def test_no_value_carries_a_profile_url(self):
        hits = [w for w, v in every_stored_value() if PROFILE.search(v)]
        self.assertEqual(hits, [])

    def test_every_name_shaped_phrase_is_a_known_organisation_or_award(self):
        unknown = set()
        for where, value in every_stored_value():
            for phrase in CAPITALISED_PHRASE.findall(value):
                if phrase not in KNOWN_CAPITALISED:
                    unknown.add("%s: %s" % (where, phrase))
        self.assertEqual(
            sorted(unknown), [],
            "a multi-word capitalised phrase that is not a known "
            "organisation, award or product. A person's name has this shape. "
            "Classify it: if it is a real person, it must not be stored.")

    def test_the_real_contact_is_not_in_this_module(self):
        """The account has one contact and they are a real person.

        The committed contact is a declared placeholder. If the real one were
        ever pasted in, its surname would not be `Tester` and its address
        would not be on a reserved suffix.
        """
        for contact in fixture.CONTACTS:
            with self.subTest(key=contact["key"]):
                self.assertEqual(contact["last_name"], "Tester")
                self.assertTrue(
                    any(contact["email"].lower().endswith(s)
                        for s in RESERVED), contact["email"])

    def test_no_placeholder_address_is_the_real_domain_altered(self):
        """A reserved suffix is enough for the repository-wide guard. It is
        not enough here: `ada@brandiq.test` becomes a plausible real address
        the moment somebody edits the suffix, and this account's real mailboxes
        exist."""
        stem = fixture.DOMAIN.split(".")[0]
        for contact in fixture.CONTACTS:
            with self.subTest(key=contact["key"]):
                self.assertNotIn(stem, contact["email"].lower())
                self.assertNotIn(stem, contact["key"].lower())


if __name__ == "__main__":
    unittest.main()
