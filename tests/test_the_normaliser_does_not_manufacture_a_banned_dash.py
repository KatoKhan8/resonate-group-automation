#!/usr/bin/env python3
"""The punctuation normaliser produced the exact pattern the copy lint bans.

`lint.normalise_punctuation` mapped an em dash to `" - "` as its plain-ASCII
equivalent. That was right until the operator banned a dash used as
punctuation on 2026-09-25. `copylint.DASH_RE` matches `\\s-\\s`, and the
campaign writer runs the normaliser over every body, subject and note
IMMEDIATELY BEFORE `copylint.check_batch`.

So the pipeline manufactured its own refusal. A model writing ordinary
typography had it converted into a banned pattern and was then told the draft
contained "a dash used as punctuation".

MEASURED 2026-09-30: that was the single most recurrent writer refusal,
surviving twenty attempts across `openai/gpt-4.1-mini` and `openai/gpt-4.1`,
an explicit prompt rule naming the characters, and a final checklist telling
the writer to sweep all eleven messages for it. The writer looked at its own
output, found no dash it had typed, and wrote the em dash again. It was never
disobeying.

The pair of rules is what makes this a bug rather than a preference: one
canonical helper produced what another canonical helper refused, and neither
was wrong on its own.
"""
import unittest

from src import copylint, lint


class TheNormaliserOutputSurvivesTheLint(unittest.TestCase):
    def test_an_em_dash_does_not_become_a_banned_dash(self):
        out = lint.normalise_punctuation("Margin—the real one—moves late.")
        self.assertFalse(copylint.DASH_RE.search(out),
                         "the normaliser produced what the copy lint bans")

    def test_the_clauses_survive_as_words(self):
        """A comma is what the em dash meant. The words are untouched."""
        self.assertEqual("Margin, the real one, moves late.",
                         lint.normalise_punctuation(
                             "Margin—the real one—moves late."))

    def test_no_substituted_character_output_is_ever_refused(self):
        """Every character the normaliser rewrites, checked as a class.

        A table this small is easy to extend with a new mapping that
        reintroduces the bug, so the property is asserted over the table
        rather than over one example.
        """
        for bad in lint.SUBSTITUTED_PUNCTUATION:
            text = "Budgets and resourcing%sjoined up in one view." % bad
            out = lint.normalise_punctuation(text)
            with self.subTest(character=repr(bad)):
                self.assertNotIn(bad, out, "the character survived")
                self.assertFalse(
                    copylint.DASH_RE.search(out),
                    "normalising %r produced a banned dash: %r" % (bad, out))


class TheDashRuleStillRefusesARealDash(unittest.TestCase):
    """THE CONTROL. The fix must not have disarmed the rule it fed."""

    def test_a_typed_spaced_hyphen_is_still_refused(self):
        self.assertTrue(
            copylint.DASH_RE.search("Margin - the real one - moves late."))

    def test_an_unspaced_hyphen_is_still_allowed(self):
        self.assertFalse(copylint.DASH_RE.search("A full-service agency."))

    def test_the_normaliser_does_not_touch_a_typed_dash(self):
        """It normalises ENCODING, not style. A writer who types " - " is
        still refused, and is told so, which is the case the rule is for."""
        typed = "Margin - the real one - moves late."
        self.assertEqual(typed, lint.normalise_punctuation(typed))
        self.assertTrue(copylint.DASH_RE.search(
            lint.normalise_punctuation(typed)))


if __name__ == "__main__":
    unittest.main()
