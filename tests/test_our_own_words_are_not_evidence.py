#!/usr/bin/env python3
"""What we decided to sell is not a fact about the person we are selling to.

Two ways `claims.py` was counting its own inputs as evidence, both found on
2026-09-11 by attacking the gate rather than reading it, and both reproduced
before being changed.

## The angle was support for itself

`support_text` appended `contact["angle"]` and `contact["persona"]`. An angle
is the thing WE chose to open with and a persona is the routing family WE filed
somebody under; neither is something a provider told us about them. Counting
them made the gate's answer depend on our own sales choice:

    "You run delivery for the studio."   angle=operations -> REFUSED
    "You run delivery for the studio."   angle=delivery   -> PASSED

Same sentence, same empty evidence, opposite verdicts. Not theoretical: one of
the five fully verified contacts in this estate carries `angle: delivery`, so
the passing branch was the live one.

`title` stays in support, and the line between them is the whole point. A
title is a fact a provider returned about this person. An angle is a word we
picked.

## Padding bought coverage for a fabrication

The event-word branch forgives a paraphrase, because "you opened a Vienna
office" against stored evidence saying exactly that should pass on its content
words. But a sentence is mostly the recipient's own name and company, and
those are in support by construction - so adding more of them lowered the
missing-token ratio without adding one supported assertion:

    "Congratulations on the Series B."                            REFUSED
    "Congratulations, <name> of <company> in <industry> with
     <headcount> employees, on the Series B."                     PASSED

Nothing behind the Series B either time. This defeated the example in the
module's own opening docstring.

## What these tests are not

They do not make `claims.py` a semantics gate. It reads keywords, and a
deterministic template still has to be safe by construction rather than by
being waved through here. These two holes were worth closing because in both
of them the gate was answering a question about ITSELF.
"""
import unittest

from src import claims


def a_contact(**over):
    contact = {"key": "vesna", "name": "Vesna Pallant",
               "title": "Operations Director", "persona": "operations",
               "angle": "operations", "email": "vesna@fernwick.test",
               "linkedin": "https://www.linkedin.com/in/vesna-p"}
    contact.update(over)
    return contact


def a_record(contact=None, **over):
    contact = contact or a_contact()
    rec = {"id": "fernwick", "client": "productive", "lane": "domains",
           "company": "Fernwick Studio", "domain": "fernwick.test",
           "company_facts": {"industry": "design", "employees": 48},
           "contacts": [contact]}
    rec.update(over)
    return rec


class TheAngleIsNotEvidenceAboutThem(unittest.TestCase):

    SENTENCE = "You run delivery for the studio."

    def verdict(self, angle):
        contact = a_contact(angle=angle)
        return claims.check(self.SENTENCE, a_record(contact), contact)

    def test_the_same_sentence_gets_the_same_answer_either_way(self):
        """The reproduction. A verdict that moves with our own sales choice is
        not a verdict about the evidence."""
        self.assertTrue(self.verdict("operations"))
        self.assertTrue(self.verdict("delivery"),
                        "the angle licensed an assertion about their business")

    def test_the_angle_does_not_reach_the_support_blob(self):
        contact = a_contact(angle="delivery", persona="delivery")
        support = claims.support_text(a_record(contact), contact)
        self.assertNotIn("delivery", support)

    def test_a_title_still_does(self):
        """A provider said this about this person, so it is evidence."""
        contact = a_contact(title="Head of Resourcing")
        support = claims.support_text(a_record(contact), contact)
        self.assertIn("resourcing", support)

    def test_and_a_title_still_licenses_what_it_says(self):
        """The control that stops this being a blunt fix: a claim the title
        genuinely supports must still pass."""
        contact = a_contact(title="Head of Resourcing")
        self.assertEqual(
            claims.check("You are responsible for resourcing.",
                         a_record(contact), contact), [])


class PaddingDoesNotBuyCoverage(unittest.TestCase):

    BARE = "Congratulations on the Series B."
    PADDED = ("Congratulations, Vesna Pallant of Fernwick Studio in design "
              "with 48 employees, on the Series B.")

    def check(self, text):
        contact = a_contact()
        return claims.check(text, a_record(contact), contact)

    def test_the_bare_fabrication_is_refused(self):
        """The baseline, and the module's own docstring example."""
        self.assertTrue(self.check(self.BARE))

    def test_padding_it_with_their_own_details_changes_nothing(self):
        self.assertTrue(self.check(self.PADDED),
                        "identity tokens bought coverage for the Series B")

    def test_the_identity_tokens_are_named_rather_than_guessed(self):
        contact = a_contact()
        tokens = claims.identity_tokens(a_record(contact), contact)
        for expected in ("fernwick", "studio", "design", "vesna", "pallant"):
            self.assertIn(expected, tokens, expected)

    def test_a_real_paraphrase_still_passes(self):
        """The control. If a supported event can no longer be paraphrased, this
        fix has traded a false pass for a false refusal - and a guard that
        refuses honest copy is one somebody deletes."""
        contact = a_contact()
        rec = a_record(contact, research=[
            {"fact": "Fernwick Studio opened a second office in Vienna"}])
        self.assertEqual(
            claims.check("You opened an office in Vienna.", rec, contact), [])


class TheUnchangedRulesStillHold(unittest.TestCase):
    """Neither change may widen what is assertable."""

    def check(self, text):
        contact = a_contact()
        return claims.check(text, a_record(contact), contact)

    def test_an_unsupported_operational_assertion_is_still_refused(self):
        self.assertTrue(self.check("You are running utilisation by hand."))

    def test_an_unsupported_figure_is_still_refused(self):
        self.assertTrue(self.check("With 400 people you must feel the strain."))

    def test_a_statement_about_us_is_still_not_a_claim(self):
        self.assertEqual(
            self.check("I work with design teams on resourcing visibility."),
            [])

    def test_a_supported_fact_still_passes(self):
        self.assertEqual(self.check("You have 48 people."), [])


if __name__ == "__main__":
    unittest.main()
