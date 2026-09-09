"""Reading a company's website must not manufacture a contradiction about it.

Two defects, both found by running the real pipeline over fifty real domains
rather than by reading it.

`contradictions` judged "this agency is really a product business" from
`segments.text_of`, which folds in every retained research page. So once the
free crawler started collecting website copy, an ordinary agency saying "our
platform", "pricing plans" or "free trial" contradicted its own vertical.
Measured: reading fifty sites took the batch from one contradiction to nine.
A contradiction demotes confidence to LOW, LOW forces `review` whatever the
score is, and `contradictory_evidence` also docks ten points - so collecting
more true evidence made companies score worse and qualify less. The research
made the picture worse by being read.

And `headcount_sources_disagree` compared `employees` against
`headcount_signal` in both directions, calling any factor of two a
disagreement. They are not two claims about one quantity: `headcount_signal`
is how many LinkedIn profiles `people-count` can see at the domain. A firm of
seventy-eight with twenty-nine profiles has ordinary LinkedIn adoption. The
asymmetry is the signal - substantially *more* profiles than staff says the
domain is shared or the headcount is understated; fewer says nothing at all.
"""
import unittest

from src import icp, segments, store

AGENCY = {"industry": "Marketing and Advertising",
          "specialties": ["digital marketing agency", "brand strategy"],
          "employees": 78, "offices": [{"city": "Leeds"}, {"city": "London"}]}

# The kind of sentence an agency puts on its own homepage.
OWN_COPY = ("We built our platform to give clients pricing plans and a free "
            "trial of the reporting dashboard we run for them.")


def company(facts=None, research=None):
    rec = store.new_record("c1", "domains", "demo", "Agency", "agency.test")
    rec["company_facts"] = dict(facts if facts is not None else AGENCY)
    if research:
        rec["research"] = list(research)
    return rec


def kinds(rec, config=None):
    return {c["kind"] for c in icp.contradictions(
        rec, segments.classify(rec, config))}


class WebsiteCopyIsNotAClaimAboutCompanyType(unittest.TestCase):

    def test_an_agency_saying_platform_on_its_own_site_is_not_a_contradiction(self):
        rec = company(research=[{"fact": OWN_COPY, "provider": "local_http",
                                 "source_type": "local_http",
                                 "source_url": "https://agency.test/"}])
        self.assertNotIn("vertical_vs_non_icp", kinds(rec))

    def test_the_same_words_in_the_stated_industry_still_are(self):
        """The signal survives where it means something: a provider saying the
        company's industry is SaaS is a claim about the business."""
        rec = company(dict(AGENCY, industry="Software as a Service",
                           specialties=["saas", "digital marketing agency"]))
        self.assertIn("vertical_vs_non_icp", kinds(rec))

    def test_collecting_research_never_adds_a_contradiction(self):
        """The property that broke. More evidence may change a score; it may
        not invent a disagreement the record did not already have."""
        bare = company()
        read = company(research=[
            {"fact": OWN_COPY, "provider": "local_http",
             "source_type": "local_http", "source_url": "https://agency.test/"},
            {"fact": "Our ecommerce store has an add to cart button.",
             "provider": "apify", "source_type": "apify",
             "source_url": "https://agency.test/shop"}])
        self.assertEqual(kinds(read) - kinds(bare), set())

    def test_structured_text_does_not_read_research(self):
        rec = company(research=[{"fact": "saas platform free trial",
                                 "provider": "local_http"}])
        self.assertNotIn("saas", icp._structured_text(rec))
        self.assertIn("digital marketing agency", icp._structured_text(rec))


class ProfilesAreNotHeadcount(unittest.TestCase):

    def test_fewer_profiles_than_staff_is_ordinary(self):
        """78 people, 29 of them on LinkedIn. Nothing disagrees."""
        rec = company(dict(AGENCY, employees=78, headcount_signal=29))
        self.assertNotIn("headcount_sources_disagree", kinds(rec))

    def test_far_more_profiles_than_staff_still_is_a_contradiction(self):
        """A shared domain, or a headcount that is not the whole company."""
        rec = company(dict(AGENCY, employees=10, headcount_signal=90))
        self.assertIn("headcount_sources_disagree", kinds(rec))

    def test_a_close_count_either_way_says_nothing(self):
        rec = company(dict(AGENCY, employees=73, headcount_signal=70))
        self.assertNotIn("headcount_sources_disagree", kinds(rec))

    def test_the_other_contradictions_still_fire(self):
        """The narrowing must not have made the check unreachable."""
        rec = company(dict(AGENCY, employees=1, offices=[{"c": 1}, {"c": 2}],
                           founded=3000))
        found = kinds(rec)
        self.assertIn("size_vs_offices", found)
        self.assertIn("implausible_founding_year", found)


class TheCostOfAFalseContradiction(unittest.TestCase):
    """Why this matters beyond tidiness: it is worth ten points and a band."""

    def test_the_contradiction_penalty_is_not_applied_to_website_copy(self):
        """`contradictory_evidence` is worth ten points, and it was being
        charged for the company's own marketing language.

        The score may still move for other reasons - `segments.business_model`
        reads the same text and may reasonably call an agency that sells a
        product `hybrid` - so this asserts the penalty, not the total.
        """
        read = icp.score(company(research=[
            {"fact": OWN_COPY, "provider": "local_http",
             "source_type": "local_http",
             "source_url": "https://agency.test/"}]), None)
        self.assertEqual(read["contradictions"], [])
        docked = [s for s in read["negative_signals"]
                  if s.get("dimension") == "contradictory_evidence"]
        self.assertEqual(docked, [])

    def test_and_it_is_still_applied_to_a_real_contradiction(self):
        """Otherwise the penalty has been removed rather than aimed."""
        rec = company(dict(AGENCY, employees=10, headcount_signal=90))
        scored = icp.score(rec, None)
        self.assertTrue(scored["contradictions"])
        self.assertTrue([s for s in scored["negative_signals"]
                         if s.get("dimension") == "contradictory_evidence"])


if __name__ == "__main__":
    unittest.main()
