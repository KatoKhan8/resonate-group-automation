#!/usr/bin/env python3
"""A legacy /pub/ URL identifies one member, and not by its name segment.

`canonical()` kept only the first path segment, on the reasoning that
everything after the vanity is a sub-page - true for `/in/jan-novak/detail/
contact-info`, and false for the legacy public form:

    https://www.linkedin.com/pub/jan-novak/1a/2b3/4c5
    https://www.linkedin.com/pub/jan-novak/9f/0c1/2d3

Those are two members. The trailing triplet is precisely what tells them
apart, and dropping it canonicalised both - and anybody at `/in/jan-novak`,
who may be a third person entirely - onto one identity.

`linkedin.py` opens by refusing exactly this trade: "There is no fuzzy
matching anywhere in this module, and there never should be. A near-miss is
an unmatched event, which is safe; a wrong match pauses somebody else's
campaign." A canonical form that asserts an equivalence the URL does not
support is a wrong match with extra steps - and this module's answers decide
suppression, collision and whose campaign gets paused.

LATENT when found on 2026-09-11: the estate held no /pub/ URL at all, and
every profile on it was stored as a bare vanity slug. Fixed because identity
is the wrong place to carry a known-false equivalence, not because it had
fired.
"""
import unittest

from src import linkedin


class TwoLegacyProfilesAreTwoPeople(unittest.TestCase):

    ONE = "https://www.linkedin.com/pub/jan-novak/1a/2b3/4c5"
    TWO = "https://www.linkedin.com/pub/jan-novak/9f/0c1/2d3"

    def test_they_do_not_canonicalise_together(self):
        self.assertNotEqual(linkedin.canonical(self.ONE),
                            linkedin.canonical(self.TWO))

    def test_same_profile_says_no(self):
        self.assertFalse(linkedin.same_profile(self.ONE, self.TWO))

    def test_neither_becomes_the_in_form_of_that_vanity(self):
        """Which may belong to a third person. The vanity segment is shared;
        that is the whole reason the trailing segments exist."""
        theirs = linkedin.canonical("https://www.linkedin.com/in/jan-novak")
        self.assertNotEqual(linkedin.canonical(self.ONE), theirs)
        self.assertNotEqual(linkedin.canonical(self.TWO), theirs)

    def test_one_of_them_still_matches_itself(self):
        """A guard that refused every legacy URL would lose a real profile.
        The forms below differ in every way this module DOES normalise."""
        self.assertTrue(linkedin.same_profile(
            self.ONE,
            "HTTP://de.LinkedIn.com/pub/Jan-Novak/1A/2B3/4C5/?trk=x"))

    def test_every_segment_counts_not_just_the_first(self):
        """The triplet is derived from the member id, so two members can share
        its leading segments and differ only in the last. Keeping one of the
        three is the same bug with a smaller blast radius."""
        shares_a_prefix = "https://www.linkedin.com/pub/jan-novak/1a/2b3/9f0"
        self.assertNotEqual(linkedin.canonical(self.ONE),
                            linkedin.canonical(shares_a_prefix))
        self.assertFalse(linkedin.same_profile(self.ONE, shares_a_prefix))

    def test_the_short_key_tells_them_apart_too(self):
        """`key()` took the text after the last slash, which for these is the
        final segment alone - `4c5` and `2d3`. Two people, one character
        apart, in the form meant for looking somebody up."""
        self.assertNotEqual(linkedin.key(self.ONE), linkedin.key(self.TWO))
        self.assertTrue(linkedin.key(self.ONE).startswith("jan-novak/"))

    def test_the_short_key_of_an_ordinary_profile_is_the_vanity(self):
        self.assertEqual(
            linkedin.key("https://www.linkedin.com/in/jan-novak/?trk=x"),
            "jan-novak")

    def test_it_survives_a_round_trip(self):
        """Canonicalising the canonical form must not change it again, or a
        stored value and a fresh lookup would stop matching."""
        once = linkedin.canonical(self.ONE)
        self.assertEqual(linkedin.canonical(once), once)


class TheOrdinaryFormsAreUnchanged(unittest.TestCase):
    """The control. This module is load-bearing for suppression and collision,
    so a change to its parser has to leave every other reading alone."""

    def test_a_bare_pub_vanity_still_reads_as_the_in_form(self):
        """Nothing disambiguates it, so there is nothing new to preserve and
        the existing reading stands."""
        self.assertEqual(linkedin.canonical("https://www.linkedin.com/pub/jan-novak"),
                         "https://www.linkedin.com/in/jan-novak")

    def test_an_in_sub_page_is_still_stripped(self):
        self.assertEqual(
            linkedin.canonical("https://www.linkedin.com/in/jan-novak/detail/"
                               "contact-info"),
            "https://www.linkedin.com/in/jan-novak")

    def test_a_bare_vanity_name_still_works(self):
        """How this estate actually stores a profile: no scheme, no path."""
        self.assertEqual(linkedin.canonical("jan-novak"),
                         "https://www.linkedin.com/in/jan-novak")

    def test_a_company_page_is_still_not_a_profile(self):
        self.assertIsNone(
            linkedin.canonical("https://www.linkedin.com/company/acme"))


if __name__ == "__main__":
    unittest.main()
