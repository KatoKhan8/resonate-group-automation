#!/usr/bin/env python3
"""`{company}` must be a company's name, not the URL we found them at.

FOUND on 2026-09-11 across the real estate. `rec["company"]` is whatever the
input file said, and for three of the five fully verified contacts it held a
bare hostname while `company_facts["name"]` on the SAME record held the real
name. The shapes, with the prospects' own values replaced by fictional ones of
the same form - this file is tracked, and `test_fixture_hygiene` refuses a real
client's domain or name in tracked source:

    rec["company"]                company_facts["name"]
    thirdwave.test             Thirdwave Studio   (a full name)
    hotsoup.test                  HSG                       (an initialism)
    e-9.test                      E9 Communications         (unrelated)

Every template interpolates `{company}` two or three times - the day-3
connection note, the day-5 subject and body, the day-10 body, the day-21 body -
so the first thing those prospects would have read is their own hostname. It is
the cheapest possible signal that nobody looked, and it is worse than a missing
name because it looks automated rather than brief.

So the provider's name wins, the input column is the fallback, and a value that
is still hostname-shaped raises. Raising is the conservative direction:
`expand_step` already treats a `CadenceError` as a step that cannot render, so
the step is held and a person is told why, rather than a prospect being sent a
URL.

## The first version of this guard was wrong, and it is worth saying how

It rejected any name whose letters matched the domain's first label. That
refused a correct one-word company name at its matching domain, on the one
contact in the live estate that is ready to send - so it would have held the
canary and every ordinary record with it. Most companies are named after their
domain or the other way round. The defect is a value carrying a TLD, not a
value agreeing with the domain, and the tests below pin both halves so the
stricter rule cannot come back.
"""
import unittest

from src import cadence


def a_record(company, domain="acme.test", name=None):
    return {"id": "rec-1", "client": "productive", "domain": domain,
            "company": company,
            "company_facts": {"name": name} if name else {}}


class TheProviderNameWins(unittest.TestCase):

    def test_the_real_name_is_preferred_over_a_hostname_column(self):
        rec = a_record("thirdwave.test", "thirdwave.test",
                       name="Thirdwave Studio")
        self.assertEqual(cadence.company_name(rec), "Thirdwave Studio")

    def test_an_initialism_is_a_name(self):
        rec = a_record("hotsoup.test", "hotsoup.test", name="HSG")
        self.assertEqual(cadence.company_name(rec), "HSG")

    def test_a_name_unrelated_to_the_domain_is_a_name(self):
        rec = a_record("e-9.test", "e-9.test", name="E9 Communications")
        self.assertEqual(cadence.company_name(rec), "E9 Communications")

    def test_the_input_column_is_used_when_it_is_a_real_name(self):
        self.assertEqual(cadence.company_name(a_record("Borealis")), "Borealis")

    def test_the_provider_name_wins_even_when_both_are_usable(self):
        """The order, pinned. When the input column is hostname-shaped the
        order cannot matter - the check skips it either way - so a mutation
        that swapped the candidates survived every other test here. It matters
        exactly when both are real names and they disagree, and then the
        provider's is the fresher of the two: a CSV column was typed once by
        somebody, `company_facts.name` came back from a lookup on the domain.
        """
        rec = a_record("Acme", "acme.test", name="Acme Studios")
        self.assertEqual(cadence.company_name(rec), "Acme Studios")

    def test_and_the_input_column_still_covers_a_missing_lookup(self):
        rec = a_record("Acme Studios", "acme.test")
        self.assertEqual(cadence.company_name(rec), "Acme Studios")


class ANameThatMatchesItsDomainIsStillAName(unittest.TestCase):
    """The false positive my first guard produced, pinned so it cannot return.

    A company called Ninefields at ninefields.test is the ordinary case, not a
    defect - and refusing it would have held the only live-ready step in the
    estate.
    """

    def test_a_bare_name_matching_the_domain_label(self):
        rec = a_record("Ninefields", "ninefields.test")
        self.assertEqual(cadence.company_name(rec), "Ninefields")

    def test_a_two_word_name_matching_the_domain_label(self):
        rec = a_record("Hot Soup Group", "hotsoup.test")
        self.assertEqual(cadence.company_name(rec), "Hot Soup Group")

    def test_case_differences_do_not_make_it_a_hostname(self):
        rec = a_record("ACME", "acme.test")
        self.assertEqual(cadence.company_name(rec), "ACME")


class AHostnameIsRefusedRatherThanSent(unittest.TestCase):

    def test_a_bare_domain_with_no_provider_name_refuses(self):
        rec = a_record("thirdwave.test", "thirdwave.test")
        with self.assertRaises(cadence.CompanyNameUnusable):
            cadence.company_name(rec)

    def test_a_domain_that_is_not_this_record_s_domain_also_refuses(self):
        """It is a hostname whoever it belongs to."""
        with self.assertRaises(cadence.CompanyNameUnusable):
            cadence.company_name(a_record("someoneelse.co.uk"))

    def test_a_trailing_hostname_token_refuses(self):
        with self.assertRaises(cadence.CompanyNameUnusable):
            cadence.company_name(a_record("Acme acme.com"))

    def test_nothing_at_all_refuses(self):
        with self.assertRaises(cadence.CompanyNameUnusable):
            cadence.company_name(a_record(None))

    def test_the_refusal_names_the_record_and_says_what_to_do(self):
        with self.assertRaises(cadence.CompanyNameUnusable) as caught:
            cadence.company_name(a_record("e-9.test", "e-9.test"))
        said = str(caught.exception)
        self.assertIn("rec-1", said)
        self.assertIn("company_facts.name", said)

    def test_a_provider_name_that_is_also_a_hostname_falls_through(self):
        """Both candidates hostname-shaped is still a refusal, not a choice
        between two bad answers."""
        rec = a_record("acme.test", "acme.test", name="acme.test")
        with self.assertRaises(cadence.CompanyNameUnusable):
            cadence.company_name(rec)


class TheRenderedCopyUsesIt(unittest.TestCase):
    """The link that makes this more than a helper nobody reads."""

    def test_template_vars_carries_the_resolved_name(self):
        rec = a_record("thirdwave.test", "thirdwave.test",
                       name="Thirdwave Studio")
        contact = {"key": "c1", "name": "Dana Reed", "persona": "champion",
                   "angle": "operations"}
        found = cadence.template_vars(rec, contact, {})
        self.assertEqual(found["company"], "Thirdwave Studio")
        self.assertNotIn(".com", found["company"])

    def test_and_the_fallback_line_does_too(self):
        rec = a_record("e-9.test", "e-9.test", name="E9 Communications")
        contact = {"key": "c1", "name": "Dana Reed", "persona": "champion",
                   "angle": "operations"}
        found = cadence.template_vars(rec, contact, {})
        self.assertIn("E9 Communications", found["line"])
        self.assertNotIn("e-9.test", found["line"])


if __name__ == "__main__":
    unittest.main()
