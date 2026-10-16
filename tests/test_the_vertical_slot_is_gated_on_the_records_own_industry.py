#!/usr/bin/env python3
"""The vertical slot is gated on the record's own industry, and silence is
the default.

TASK 0180 (2026-10-16), from the 0120/0140 proposal the operator approved:
em1's opener may name the client's own segment - one of
`company_types.verticals` - but ONLY when the record's own industry field
names exactly one. In every other case the sentence keeps the bytes the
approved copy already has:

    fire      the industry shares a token with EXACTLY ONE configured
              vertical -> that vertical renders, VERBATIM from the config
    silence   absent, ambiguous (two or more candidates) or matching
              nothing -> the industry itself renders, byte for byte the
              approved words
    refuse    the industry is the wrong SHAPE - a domain, an email address,
              a classifier slug -> the slot renders EMPTY, the sentence
              loses it, and the refusal rides the row visibly

BUILT THE WAY `company_name` WAS BUILT (TASK 0100's derivation, landed
0110). Reused, by shape: the value may come only from the record's own
field; the client's configured vocabulary is the only upgrade; a
domain-shaped value is refused with 0100's own token test
`^[a-z0-9.\\-]+\\.[a-z]{2,}$` rather than rendered; and the refusal is
returned as a REASON, never swapped for a guess and never swallowed. What
has no analogue here, deliberately: there is no precedence chain, because
the slot has one input. NO FALLBACK THAT RENDERS A DOMAIN, SLUG, COMPANY
NAME OR ANYTHING DERIVED FROM THE EMAIL ADDRESS EXISTS - nothing in the
derivation reads those fields, so no code path can produce one.

The vertical is never pluralised, recased or otherwise derived from the
config's words either: "Design Services" renders "Design Studio", not
"design studios", because choosing that transformation is a guess and the
guess is not the renderer's to make.

The 24 approved sheet rows are measured against the REAL config by the
0180 harness in `work/vertical_0180_measure.py`; this file is hermetic and
carries the real vertical list verbatim so the ambiguity structure - three
verticals carry "marketing" - is what the tests exercise.
"""
import unittest

from scripts import stage_s7_copy                              # noqa: E402
from src import cadence, clients                               # noqa: E402

#: `config/clients/productive.yaml`, `icp.structural.company_types
#: .verticals`, verbatim.
VERTICALS = [
    "Creative / Branding Agency", "Digital Marketing Agency",
    "Performance Marketing Agency", "Advertising Agency",
    "Media Agency", "PR Agency", "Design Studio",
    "Software Development Agency", "Web Development Agency",
    "Product Studio", "Digital Agency", "Consultancy",
    "Technology Consultancy", "Marketing Agency",
]

#: Nested exactly as the client file nests it, because the accessor reads
#: that path and a flat copy would silently test nothing.
CONFIG = {"icp": {"structural": {"company_types":
                                 {"verticals": VERTICALS}}}}

#: The row 0100/0130's own tests render with; its title routes to the
#: delivery persona, which has an angle, so a failure below is the slot and
#: never the fixture.
ROW = {
    "First Name": "Jonathan",
    "Company": "Advertise Purple",
    "Industry": None,               # set per scenario
    "Job Title": "Digital Project Manager",
}


class TheSlotFiresOnlyWhenTheIndustryNamesExactlyOneVertical(
        unittest.TestCase):
    """The fire rule: one shared token AND exactly one candidate."""

    def _sector(self, industry, config=CONFIG):
        return cadence.sector_for(industry, config)

    def test_a_matching_industry_renders_the_clients_own_vertical(self):
        for industry, vertical in (
                ("Advertising Services", "Advertising Agency"),
                ("Design Services", "Design Studio"),
                ("branding", "Creative / Branding Agency"),
                ("PR", "PR Agency")):
            with self.subTest(industry=industry):
                sector, refusal = self._sector(industry)
                self.assertIsNone(refusal)
                self.assertEqual(sector, vertical)

    def test_the_vertical_renders_verbatim_not_derived(self):
        """No pluralising, no recasing: the config's words or nothing."""
        sector, refusal = self._sector("Design Services")
        self.assertIsNone(refusal)
        self.assertEqual(sector, "Design Studio")

    def test_an_industry_that_could_be_several_verticals_stays_silent(self):
        for industry, candidates in (
                ("Marketing Services", 3),
                ("Marketing & Advertising", 4),
                ("digital marketing", 4),
                ("software development", 2)):
            with self.subTest(industry=industry):
                sector, refusal = self._sector(industry)
                self.assertIsNone(refusal)
                self.assertEqual(
                    sector, industry,
                    f"{industry!r} names {candidates} verticals; the slot "
                    f"must stay silent, not pick one")

    def test_an_industry_that_names_no_vertical_stays_silent(self):
        sector, refusal = self._sector("Business Consulting and Services")
        self.assertIsNone(refusal)
        self.assertEqual(sector, "Business Consulting and Services")

    def test_a_config_without_verticals_stays_silent(self):
        sector, refusal = self._sector("Advertising Services", {})
        self.assertIsNone(refusal)
        self.assertEqual(sector, "Advertising Services")

    def test_no_industry_at_all_is_silence_not_a_guess(self):
        for absent in ("", "   ", None):
            with self.subTest(industry=absent):
                sector, refusal = self._sector(absent)
                self.assertIsNone(sector)
                self.assertIsNone(refusal)


class AWrongShapedIndustryIsRefusedVisibly(unittest.TestCase):
    """The refuse rule: the wrong shape never renders and never vanishes."""

    def _sector(self, industry):
        return cadence.sector_for(industry, CONFIG)

    def test_the_refusal_is_visible_not_swallowed(self):
        """0100's visibility test, rebuilt for this slot: a wrong-shaped
        industry must come back as (None, reason) with the reason NAMING
        the shape. (None, None) would read to a caller as "nothing to say"
        and the value would be gone from the record with no trace."""
        for industry, shape in (
                ("advertisepurple.com", "domain"),
                ("twenty-north.co.uk", "domain"),
                ("digital-marketing-agency", "slug"),
                ("austin@20north.com", "email")):
            with self.subTest(industry=industry):
                sector, refusal = self._sector(industry)
                self.assertIsNone(
                    sector, f"{industry!r} must not occupy the sector slot")
                self.assertIsNotNone(
                    refusal, f"{industry!r} vanished silently; the refusal "
                    f"must come back as a reason")
                self.assertIn(shape, refusal.lower())

    def test_the_render_drops_the_slot_and_keeps_the_reason(self):
        """Render-level: the sentence ships WITHOUT the slot, the bad value
        appears nowhere in it, the gap it leaves is collapsed, and the
        returned variables carry the refusal so the journal shows it."""
        row = dict(ROW, Industry="advertisepurple.com")
        variables, hold = stage_s7_copy.render(row, clients.load("productive"))
        self.assertIsNone(hold, "a refused slot must not hold the render")
        self.assertIsNotNone(variables)
        self.assertNotIn("advertisepurple.com", variables["body_1"])
        self.assertIn("I work with teams on", variables["body_1"])
        self.assertNotIn("with  teams", variables["body_1"])
        self.assertIn("refuses to render",
                      variables.get("sector_refusal", ""))


class SilenceKeepsTheApprovedBytes(unittest.TestCase):
    """The bytes contract: silence is not a change and fire is only a swap."""

    @classmethod
    def setUpClass(cls):
        cls.config = clients.load("productive")

    def _render(self, industry):
        return stage_s7_copy.render(dict(ROW, Industry=industry),
                                    self.config)

    def test_a_silent_row_renders_the_industry_through_the_slot(self):
        variables, hold = self._render("Marketing Services")
        self.assertIsNone(hold)
        self.assertIn("I work with Marketing Services teams on",
                      variables["body_1"])
        self.assertEqual(variables["sector"], "Marketing Services")
        self.assertNotIn("sector_refusal", variables)

    def test_a_firing_row_swaps_only_the_slot(self):
        variables, hold = self._render("Advertising Services")
        self.assertIsNone(hold)
        self.assertIn("I work with Advertising Agency teams on",
                      variables["body_1"])
        self.assertEqual(variables["sector"], "Advertising Agency")
        self.assertNotIn("sector_refusal", variables)

    def test_0130s_own_fixture_industry_is_silent_here(self):
        """`digital marketing` is 4-way ambiguous under the gate, so the
        company-name tests' fixture renders verbatim and those tests keep
        measuring what they measured."""
        variables, hold = self._render("digital marketing")
        self.assertIsNone(hold)
        self.assertIn("I work with digital marketing teams on",
                      variables["body_1"])


if __name__ == "__main__":
    unittest.main()
