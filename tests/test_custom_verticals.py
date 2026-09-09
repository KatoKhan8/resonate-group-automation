"""A client may declare the market it actually sells to.

The taxonomy was fourteen categories of agency and professional services -
Productive's market, and nobody else's. `segmentation.extra_keywords` let a
client add words to one of *those* verticals and never declare one of its own,
because `settings` gated every name on `if name in VERTICALS`. So a client
selling to dental practices, clinics or manufacturers had no expressible
vertical: every company they uploaded classified as UNKNOWN, `agency_fit` -
the heaviest dimension at twenty points - scored nothing, and an UNKNOWN
vertical forces confidence to LOW, which forces `review` at any score. The
entire ICP model sat idle for them.

Adding a vertical is not renaming one. The rename protection stays, because a
renamed vertical silently orphans every campaign segment that used the old
name; a declared one orphans nothing.
"""
import unittest

from src import icp, segments, store

DENTAL = {"segmentation": {"verticals": {
    "Dental Clinic": {"keywords": ["dental practice", "orthodontist",
                                   "dental surgery"], "kind": "service"},
    "Munitions": {"keywords": ["munitions", "ordnance"], "kind": "non_icp"},
}}}


def company(text, **facts):
    rec = store.new_record("c1", "domains", "demo", "C", "c.test")
    rec["company_facts"] = dict(
        {"industry": text, "specialties": [text], "employees": 40,
         "offices": [{"city": "A"}, {"city": "B"}]}, **facts)
    return rec


class ADeclaredVerticalIsClassified(unittest.TestCase):

    def test_a_client_can_name_its_own_market(self):
        seg = segments.classify(
            company("dental practice orthodontist"), DENTAL)
        self.assertEqual(seg["vertical"], "Dental Clinic")

    def test_it_appears_in_the_taxonomy_that_is_searched(self):
        names = [v for v, _ in segments.vertical_signals(DENTAL)]
        self.assertIn("Dental Clinic", names)
        self.assertIn(segments.SEO, names)

    def test_the_built_ins_come_first_so_a_tie_does_not_reorder_them(self):
        names = [v for v, _ in segments.vertical_signals(DENTAL)]
        self.assertLess(names.index(segments.SEO), names.index("Dental Clinic"))

    def test_a_client_cannot_redefine_a_built_in(self):
        """A rename orphans every campaign segment using the old name."""
        hijack = {"segmentation": {"verticals": {
            segments.SEO: {"keywords": ["anything"], "kind": "non_icp"}}}}
        self.assertEqual(segments.settings(hijack)["verticals"], {})
        self.assertEqual(segments.kind_of(segments.SEO, hijack),
                         segments.AGENCY_KIND)

    def test_an_unusable_declaration_is_ignored_rather_than_half_applied(self):
        for spec in ({"keywords": [], "kind": "service"},
                     {"keywords": ["x"], "kind": "nonsense"},
                     {"kind": "service"}):
            config = {"segmentation": {"verticals": {"Bad": spec}}}
            self.assertEqual(segments.settings(config)["verticals"], {}, spec)


class ADeclaredVerticalIsScored(unittest.TestCase):

    def test_a_service_kind_scores_like_a_services_business(self):
        """The point of the whole change: `agency_fit` stops being zero."""
        scored = icp.score(company("dental practice orthodontist"), DENTAL)
        agency = [s for s in scored["positive_signals"]
                  if s["dimension"] == "agency_fit"]
        self.assertTrue(agency, "the heaviest dimension still scores nothing")

    def test_without_the_declaration_the_same_company_scores_nothing(self):
        bare = icp.score(company("dental practice orthodontist"), None)
        declared = icp.score(company("dental practice orthodontist"), DENTAL)
        self.assertGreater(declared["icp_score"], bare["icp_score"])

    def test_a_non_icp_kind_is_penalised_rather_than_ignored(self):
        """How a client says "this is not my market" without editing source."""
        scored = icp.score(company("munitions ordnance"), DENTAL)
        against = [s for s in scored["negative_signals"]
                   if s["dimension"] == "agency_fit"]
        self.assertTrue(against)
        self.assertLess(scored["icp_score"],
                        icp.score(company("munitions ordnance"), None)
                        ["icp_score"] + 1)

    def test_kind_of_places_every_built_in(self):
        for vertical in segments.AGENCY_VERTICALS:
            self.assertEqual(segments.kind_of(vertical), segments.AGENCY_KIND)
        for vertical in segments.SERVICE_VERTICALS:
            self.assertIn(segments.kind_of(vertical),
                          (segments.AGENCY_KIND, segments.SERVICE_KIND))

    def test_an_unplaceable_vertical_is_none_rather_than_a_guess(self):
        self.assertIsNone(segments.kind_of("Something Nobody Declared"))


class ProductiveIsUnchanged(unittest.TestCase):
    """The reference implementation must not move because of this."""

    def test_an_agency_still_classifies_the_same_way(self):
        for config in (None, DENTAL):
            seg = segments.classify(company("digital marketing agency"), config)
            self.assertEqual(seg["vertical"], segments.DIGITAL_MARKETING)

    def test_a_client_with_no_declaration_gets_the_built_in_taxonomy(self):
        self.assertEqual([v for v, _ in segments.vertical_signals(None)],
                         [v for v, _ in segments.VERTICAL_SIGNALS])


if __name__ == "__main__":
    unittest.main()
