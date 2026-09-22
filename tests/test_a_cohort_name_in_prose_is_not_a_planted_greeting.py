"""ISSUE-015: the planted-name check reads a GREETING, not the whole body.

It used to flag any occurrence of another cohort member's first name anywhere
in the body. Measured 2026-09-22 across the five campaigns carrying batch 3:
275 flags, every one a false positive, and three of five campaigns blocked.

  269 of them on the single name 'Will' - a first name AND an ordinary English
    auxiliary verb, so one cohort member named Will made every body containing
    the word "will" a defect
  the rest were company names carrying a person's name: russellherder.com,
    terrisandy.com, bigstarbranding.com, wearerichlifestyle.com, sobepromos.com

The defect it names - HeyReach 599020's "hi jacob" going to fourteen people -
is a MIS-PERSONALISED GREETING. These tests fix both halves: the prose cases
pass, and every real planted greeting still refuses.
"""
import unittest

from src import bisonfactory
from tests.test_emailbison_no_empty_greeting import _lead, _plan_with_leads


def _cohort(*pairs):
    """A plan whose cohort contains every (key, name) given.

    The other member's body is deliberately clean; only the first lead's body
    is under test, and the second exists to put its name in `cohort_names`.
    """
    leads = [_lead(key, name, body) for key, name, body in pairs]
    return _plan_with_leads(leads)


class ProseIsNotAGreeting(unittest.TestCase):
    """Each of these is a real body that the old check refused."""

    def _passes(self, body, other_name):
        plan = _cohort(
            ("michael", "Michael", body),
            ("other", other_name, f"{other_name}, I work with agencies."))
        bisonfactory._refuse_bad_greetings(plan)          # must not raise

    def test_the_verb_will(self):
        """269 of the 275. 'Will' is a name and an auxiliary verb."""
        self._passes("Michael, you will see margin monthly.", "Will")

    def test_the_verb_will_capitalised_mid_sentence(self):
        self._passes("Michael, margin visibility. Will that help?", "Will")

    def test_a_company_name_carrying_a_first_name(self):
        """bigstarbranding.com against a cohort member named Star."""
        self._passes("Michael, Big Star Branding tracks time.", "Star")

    def test_another_company_name(self):
        """russellherder.com against a cohort member named Russell."""
        self._passes("Michael, we worked with Russell Herder.", "Russell")

    def test_two_names_in_one_company(self):
        """terrisandy.com carries both Terri and Sandy."""
        self._passes("Michael, Terri and Sandy run the studio.", "Terri")

    def test_a_name_that_is_an_adjective(self):
        """wearerichlifestyle.com against a cohort member named Rich."""
        self._passes("Michael, a rich picture of utilisation.", "Rich")


class EveryRealPlantedGreetingStillRefuses(unittest.TestCase):
    """The guard is narrowed to the defect, not past it."""

    def _refuses(self, body, other_name="Jacob"):
        plan = _cohort(
            ("michael", "Michael", body),
            ("jacob", other_name, f"{other_name}, I work with agencies."))
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_bad_greetings(plan)
        self.assertIn("hi-jacob", str(caught.exception))
        self.assertIn(other_name, str(caught.exception))

    def test_the_bare_vocative_the_approved_copy_uses(self):
        """"Janie, I work with ..." is the real Productive opener shape."""
        self._refuses("Jacob, I work with agencies on utilisation.")

    def test_a_salutation_word(self):
        self._refuses("Hi Jacob, quick one.")

    def test_every_salutation_word(self):
        for word in ("Hi", "Hey", "Hello", "Dear"):
            with self.subTest(word=word):
                self._refuses(f"{word} Jacob, quick one.")

    def test_a_planted_greeting_on_a_later_line_of_a_follow_up(self):
        """Not only the first line. A second step opens further down."""
        self._refuses("Thanks,\nMatija\n\nJacob, following up on this.")

    def test_a_planted_greeting_after_a_quote_marker(self):
        self._refuses("Michael, see below.\n\nJacob, following up.")

    def test_case_is_ignored(self):
        self._refuses("jacob, following up on this.")


if __name__ == "__main__":
    unittest.main()
