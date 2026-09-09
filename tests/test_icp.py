"""Qualification: is this a Productive prospect, and what says so?

The tests that matter most here are the ones about not knowing. A system that
turns thin evidence into a confident yes spends money on nobody; one that turns
it into a confident no throws away the market. Both are the same bug, and the
fix is that `unknown` is a real answer with its own bucket.
"""
import unittest

from src import companies, geo, icp, segments
from tests.campaignbase import CampaignTest


def rec(rid="acme", company="Acme", industry=None, specialties=None,
        employees=None, country=None, city=None, state=None, description="",
        offices=None, founded=None, research=None):
    return {
        "id": rid, "domain": f"{rid}.test", "company": company,
        "client": "demo", "state": "enriched",
        "company_facts": {
            "industry": industry, "specialties": specialties or [],
            "employees": employees, "country": country, "city": city,
            "state": state, "description": description,
            "offices": offices or [], "founded": founded,
        },
        "research": research or [],
    }


AGENCY_TEXT = ("We run delivery teams across multiple clients on retainer and "
               "project work. Resource planning, utilisation and project "
               "margin are how we run the studio.")


class TestScoringVersion(CampaignTest):
    def test_every_verdict_carries_the_version_it_was_scored_under(self):
        """A batch scored under an older model must be visible as such."""
        result = icp.score(rec(industry="Marketing", employees=90,
                               specialties=["digital marketing"],
                               description=AGENCY_TEXT))
        self.assertEqual(result["scoring_version"], icp.SCORING_VERSION)

    def test_the_version_is_a_non_empty_string(self):
        self.assertTrue(icp.SCORING_VERSION)
        self.assertIsInstance(icp.SCORING_VERSION, str)


class TestTheEnterpriseCeiling(CampaignTest):
    def big(self, employees):
        return rec(industry="Marketing", employees=employees,
                   specialties=["digital marketing", "content marketing"],
                   country="United Kingdom", description=AGENCY_TEXT,
                   offices=["London", "Manchester"])

    def test_a_company_far_above_the_ceiling_is_penalised(self):
        result = icp.score(self.big(40000))
        kinds = [s["dimension"] for s in result["negative_signals"]]
        self.assertIn("unsuitable_enterprise", kinds)

    def test_a_company_inside_the_ceiling_is_not_penalised(self):
        result = icp.score(self.big(300))
        kinds = [s["dimension"] for s in result["negative_signals"]]
        self.assertNotIn("unsuitable_enterprise", kinds)

    def test_the_ceiling_is_configurable(self):
        config = {"icp": {"thresholds": {"max_employees": 100}}}
        result = icp.score(self.big(300), config)
        kinds = [s["dimension"] for s in result["negative_signals"]]
        self.assertIn("unsuitable_enterprise", kinds)

    def test_the_ceiling_can_be_removed(self):
        config = {"icp": {"thresholds": {"max_employees": 0}}}
        result = icp.score(self.big(40000), config)
        kinds = [s["dimension"] for s in result["negative_signals"]]
        self.assertNotIn("unsuitable_enterprise", kinds)

    def test_an_enterprise_scores_below_the_same_company_at_agency_size(self):
        self.assertLess(icp.score(self.big(40000))["icp_score"],
                        icp.score(self.big(300))["icp_score"])


class TestContradictoryEvidence(CampaignTest):
    def base(self, **extra):
        fields = dict(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"],
                      country="United Kingdom", description=AGENCY_TEXT,
                      offices=["London", "Manchester"])
        fields.update(extra)
        return rec(**fields)

    def test_more_offices_than_people_is_a_contradiction(self):
        company = self.base(employees=2,
                            offices=["London", "Berlin", "Paris", "Oslo"])
        self.assertTrue(icp.score(company)["contradictions"])

    def test_an_implausible_founding_year_is_a_contradiction(self):
        kinds = [c["kind"]
                 for c in icp.score(self.base(founded=3040))["contradictions"]]
        self.assertIn("implausible_founding_year", kinds)

    def test_two_sources_disagreeing_on_headcount_is_a_contradiction(self):
        company = self.base()
        company["company_facts"]["headcount_signal"] = 4000
        kinds = [c["kind"] for c in icp.score(company)["contradictions"]]
        self.assertIn("headcount_sources_disagree", kinds)

    def test_headcount_sources_that_roughly_agree_are_not_a_contradiction(self):
        company = self.base(employees=90)
        company["company_facts"]["headcount_signal"] = 105
        kinds = [c["kind"] for c in icp.score(company)["contradictions"]]
        self.assertNotIn("headcount_sources_disagree", kinds)

    def test_a_clean_company_has_no_contradictions(self):
        self.assertEqual(icp.score(self.base())["contradictions"], [])

    def test_a_contradiction_is_a_scored_negative_signal(self):
        company = self.base(founded=3040)
        kinds = [s["dimension"] for s in icp.score(company)["negative_signals"]]
        self.assertIn("contradictory_evidence", kinds)

    def test_a_contradiction_never_leaves_confidence_high(self):
        """Fit looks fine, the evidence disagrees with itself, and a human
        should be the one to look at it."""
        self.assertEqual(icp.score(self.base())["icp_confidence"], icp.HIGH)
        conflicted = icp.score(self.base(founded=3040))
        self.assertNotEqual(conflicted["icp_confidence"], icp.HIGH)

    def test_a_contradiction_costs_confidence_more_than_score(self):
        """A contradiction is a reason to look, not a reason to reject."""
        clean = icp.score(self.base())
        conflicted = icp.score(self.base(founded=3040))
        self.assertLess(clean["icp_score"] - conflicted["icp_score"], 25)


class TestScoreAndConfidenceAreDifferentQuestions(CampaignTest):
    """Section 4: a 90/100 on two weak facts is not a 90/100 on ten good ones."""

    def test_the_same_fit_on_thinner_evidence_has_lower_confidence(self):
        rich = rec(industry="Marketing", employees=90,
                   specialties=["digital marketing", "content marketing"],
                   country="United Kingdom", description=AGENCY_TEXT,
                   offices=["London", "Manchester"])
        thin = rec(industry="Marketing", employees=90,
                   specialties=["digital marketing"],
                   description="We are a digital marketing agency.")
        order = {icp.LOW: 0, icp.MEDIUM: 1, icp.HIGH: 2}
        self.assertGreater(order[icp.score(rich)["icp_confidence"]],
                           order[icp.score(thin)["icp_confidence"]])

    def test_every_component_is_reported_with_a_reason(self):
        result = icp.score(rec(industry="Marketing", employees=90,
                               specialties=["digital marketing"],
                               description=AGENCY_TEXT))
        components = result["confidence_components"]
        for name in icp.CONFIDENCE_COMPONENTS:
            self.assertIn(name, components, name)
            self.assertIn("score", components[name], name)
            self.assertTrue(components[name]["why"], name)

    def test_every_component_score_is_a_fraction(self):
        result = icp.score(rec(industry="Marketing", employees=90,
                               specialties=["digital marketing"],
                               description=AGENCY_TEXT))
        for name in icp.CONFIDENCE_COMPONENTS:
            score = result["confidence_components"][name]["score"]
            self.assertGreaterEqual(score, 0.0, name)
            self.assertLessEqual(score, 1.0, name)

    def test_a_high_score_on_too_few_dimensions_is_never_high_confidence(self):
        thin = rec(industry="Marketing", employees=90,
                   specialties=["digital marketing"])
        self.assertNotEqual(icp.score(thin)["icp_confidence"], icp.HIGH)

    def test_confidence_does_not_move_the_score(self):
        """They must be independent, or the separation is cosmetic."""
        company = rec(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"],
                      country="United Kingdom", description=AGENCY_TEXT,
                      offices=["London", "Manchester"])
        before = icp.score(company)["icp_score"]
        company["research"] = [
            {"provider": "apify", "source_type": "website",
             "quality": "strong", "freshness_score": 1.0},
            {"provider": "contactout", "source_type": "profile",
             "quality": "strong", "freshness_score": 0.9},
        ]
        after = icp.score(company)
        self.assertEqual(after["icp_score"], before)
        self.assertGreater(
            after["confidence_components"]["source_diversity"]["score"], 0)


class TestStrongFit(CampaignTest):
    def strong(self, **extra):
        fields = dict(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"],
                      country="United Kingdom", description=AGENCY_TEXT,
                      offices=["London", "Manchester"])
        fields.update(extra)
        return rec(**fields)

    def test_a_strong_agency_qualifies(self):
        result = icp.score(self.strong())
        self.assertEqual(result["icp_status"], icp.QUALIFIED)
        self.assertIn(result["icp_tier"], (icp.TIER_A, icp.TIER_B))

    def test_it_says_which_dimensions_fired(self):
        result = icp.score(self.strong())
        fired = {s["dimension"] for s in result["positive_signals"]}
        for name in ("agency_fit", "employee_count", "resource_planning_need",
                     "utilization_need"):
            self.assertIn(name, fired, name)

    def test_every_signal_carries_a_reason(self):
        result = icp.score(self.strong())
        for signal in result["positive_signals"] + result["negative_signals"]:
            self.assertTrue(signal["why"], signal)
            self.assertIn(signal["dimension"], icp.DIMENSIONS)

    def test_good_evidence_produces_high_confidence(self):
        self.assertEqual(icp.score(self.strong())["icp_confidence"], icp.HIGH)

    def test_the_score_is_bounded(self):
        result = icp.score(self.strong(employees=900,
                                       offices=["a", "b", "c", "d"]))
        self.assertLessEqual(result["icp_score"], 100)
        self.assertGreaterEqual(result["icp_score"], 0)


class TestObviousNonICP(CampaignTest):
    def test_a_saas_product_company_is_rejected(self):
        result = icp.score(rec(
            industry="Software", employees=120, country="United States",
            description=("Our platform is software as a service with pricing "
                         "plans and a free trial")))
        self.assertEqual(result["icp_status"], icp.REJECTED)
        self.assertEqual(result["icp_tier"], icp.TIER_NOT_ICP)

    def test_an_ecommerce_retailer_is_rejected(self):
        result = icp.score(rec(
            industry="Retail", employees=60, country="Netherlands",
            description="Our online store, free shipping, add to cart"))
        self.assertEqual(result["icp_status"], icp.REJECTED)

    def test_a_holding_entity_is_rejected(self):
        result = icp.score(rec(
            industry="Financial Services", employees=8, country="Switzerland",
            description="An investment holding company and family office"))
        self.assertEqual(result["icp_status"], icp.REJECTED)

    def test_a_four_person_agency_is_rejected_for_size(self):
        result = icp.score(rec(
            industry="Marketing", specialties=["digital marketing"],
            employees=4, country="Ireland", description="A small studio."))
        self.assertEqual(result["icp_status"], icp.REJECTED)
        self.assertTrue(any(s["dimension"] == "employee_count"
                            for s in result["negative_signals"]))

    def test_a_rejection_still_explains_itself(self):
        result = icp.score(rec(
            industry="Software", employees=120,
            description="software as a service with pricing plans"))
        self.assertTrue(result["classification_reasons"][0])
        self.assertTrue(result["negative_signals"])

    def test_certainty_outranks_how_much_else_we_know(self):
        """A SaaS company with no other data is still a SaaS company.

        Before this ordering existed, an obvious rejection arrived as
        `unknown` because too few *other* dimensions could be scored, and a
        human was asked to re-read what the system already knew.
        """
        result = icp.score(rec(description=("software as a service with "
                                            "pricing plans and a free trial")))
        self.assertEqual(result["icp_status"], icp.REJECTED)
        self.assertLess(result["dimensions_scored"],
                        icp.DEFAULT_THRESHOLDS["min_dimensions_for_a_verdict"])


class TestInsufficientEvidence(CampaignTest):
    def test_a_company_with_nothing_is_unknown_not_rejected(self):
        result = icp.score(rec(company="Mystery Ltd"))
        self.assertEqual(result["icp_status"], icp.UNKNOWN)
        self.assertEqual(result["icp_tier"], icp.TIER_REVIEW)

    def test_one_weak_keyword_is_not_a_classification(self):
        result = icp.score(rec(specialties=["seo"], country="Poland"))
        self.assertEqual(result["icp_status"], icp.UNKNOWN)

    def test_missing_evidence_is_listed_rather_than_assumed(self):
        result = icp.score(rec(company="Mystery Ltd"))
        self.assertTrue(result["missing_evidence"])

    def test_a_missing_employee_count_never_becomes_a_positive_signal(self):
        """The rule the whole module is built on."""
        result = icp.score(rec(
            industry="Marketing", specialties=["digital marketing"],
            country="United Kingdom", description=AGENCY_TEXT))
        fired = {s["dimension"] for s in result["positive_signals"]}
        self.assertNotIn("employee_count", fired)
        self.assertTrue(any("employee count" in gap
                            for gap in result["missing_evidence"]))

    def test_thin_evidence_lowers_confidence_rather_than_the_score(self):
        thin = icp.score(rec(industry="Marketing",
                             specialties=["digital marketing",
                                          "content marketing"]))
        self.assertEqual(thin["icp_confidence"], icp.LOW)

    def test_a_partly_known_company_is_unknown_rather_than_borderline(self):
        """The distinction between the two review buckets.

        `unknown` means we could not score enough of the picture to judge.
        `review` means we did judge and the answer landed between the
        thresholds. Both go to a human and both cost nothing, so the label is
        the only difference - which is exactly why it should be accurate.
        """
        result = icp.score(rec(
            industry="Consulting", employees=60, country="Sweden",
            specialties=["management consulting", "advisory"],
            description="Practice areas with concurrent projects."))
        self.assertEqual(result["icp_status"], icp.UNKNOWN)
        self.assertLess(result["dimensions_scored"],
                        icp.DEFAULT_THRESHOLDS["min_dimensions_for_a_verdict"])

    def test_a_fully_scored_borderline_company_is_review_not_unknown(self):
        result = icp.score(rec(
            industry="Consulting", employees=60, country="Sweden",
            specialties=["management consulting", "advisory"],
            offices=["Stockholm", "Oslo"],
            description=("Practice areas with concurrent projects, timesheets "
                         "and budget tracking across the client portfolio.")))
        self.assertGreaterEqual(
            result["dimensions_scored"],
            icp.DEFAULT_THRESHOLDS["min_dimensions_for_a_verdict"])
        self.assertIn(result["icp_status"], (icp.REVIEW, icp.QUALIFIED))

    def test_unknown_and_rejected_are_different_buckets(self):
        nothing = icp.score(rec(company="Mystery Ltd"))
        saas = icp.score(rec(description="software as a service pricing plans"))
        self.assertNotEqual(nothing["icp_status"], saas["icp_status"])


class TestNothingIsHallucinated(CampaignTest):
    def test_no_positive_signal_appears_without_matched_evidence(self):
        result = icp.score(rec(company="Mystery Ltd"))
        self.assertEqual(result["positive_signals"], [])

    def test_a_need_signal_requires_the_words_to_be_there(self):
        without = icp.score(rec(industry="Marketing", employees=90,
                                specialties=["digital marketing",
                                             "content marketing"],
                                country="United Kingdom"))
        fired = {s["dimension"] for s in without["positive_signals"]}
        self.assertNotIn("utilization_need", fired)

    def test_evidence_used_lists_only_what_the_record_carries(self):
        result = icp.score(rec(company="Mystery Ltd"))
        self.assertEqual(result["evidence_used"], [])


class TestTheModelIsConfigurable(CampaignTest):
    def config_with(self, **icp_block):
        return {"icp": icp_block}

    def test_weights_can_be_changed_without_touching_code(self):
        company = rec(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"],
                      country="United Kingdom", description=AGENCY_TEXT)
        default = icp.score(company)["icp_score"]
        heavier = icp.score(company,
                            self.config_with(weights={"agency_fit": 40}))
        self.assertGreater(heavier["icp_score"], default)

    def test_thresholds_can_be_changed(self):
        company = rec(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"],
                      country="United Kingdom", description=AGENCY_TEXT)
        strict = icp.score(company, self.config_with(thresholds={"tier_a": 99}))
        self.assertNotEqual(strict["icp_tier"], icp.TIER_A)

    def test_an_unknown_weight_name_is_ignored_rather_than_added(self):
        policy = icp.settings(self.config_with(weights={"vibes": 100}))
        self.assertNotIn("vibes", policy["weights"])

    def test_a_non_numeric_weight_is_ignored(self):
        policy = icp.settings(self.config_with(weights={"agency_fit": "lots"}))
        self.assertEqual(policy["weights"]["agency_fit"],
                         icp.DEFAULT_WEIGHTS["agency_fit"])

    def test_markets_can_be_stated_and_penalise_outside_them(self):
        company = rec(industry="Marketing", employees=90,
                      specialties=["digital marketing", "content marketing"],
                      country="Australia", description=AGENCY_TEXT)
        inside = icp.score(company, self.config_with(markets=["Australia / New Zealand"]))
        outside = icp.score(company, self.config_with(markets=["UK"]))
        self.assertGreater(inside["icp_score"], outside["icp_score"])

    def test_the_model_can_be_described_for_a_reviewer(self):
        described = icp.describe()
        self.assertEqual(sorted(described["dimensions"]),
                         sorted(icp.DIMENSIONS))
        self.assertEqual(described["statuses"], list(icp.STATUSES))


class TestVerticalClassification(CampaignTest):
    def vertical(self, **kw):
        return segments.classify(rec(**kw))["vertical"]

    def test_a_digital_agency_is_classified(self):
        self.assertEqual(self.vertical(
            industry="Marketing",
            specialties=["digital marketing", "content marketing"]),
            segments.DIGITAL_MARKETING)

    def test_a_software_agency_is_classified(self):
        self.assertEqual(self.vertical(
            industry="Software",
            specialties=["software development", "custom software"]),
            segments.SOFTWARE_DEV)

    def test_a_consultancy_is_classified(self):
        self.assertEqual(self.vertical(
            industry="Consulting",
            specialties=["management consulting", "advisory"]),
            segments.CONSULTING)

    def test_an_seo_agency_is_classified(self):
        self.assertEqual(self.vertical(
            specialties=["seo", "technical seo", "link building"]),
            segments.SEO)

    def test_a_creative_agency_is_classified(self):
        self.assertEqual(self.vertical(
            specialties=["branding", "brand strategy", "creative studio"]),
            segments.CREATIVE)

    def test_an_ambiguous_company_is_unknown_rather_than_other_agency(self):
        """UNKNOWN and "Other Agency" are different claims."""
        self.assertEqual(self.vertical(specialties=["seo"]), segments.UNKNOWN)

    def test_a_product_company_beats_a_stray_service_word(self):
        result = segments.classify(rec(
            description=("Our platform is software as a service with pricing "
                         "plans. We also offer consulting.")))
        self.assertNotEqual(result["vertical"], segments.CONSULTING)

    def test_the_classification_says_what_matched(self):
        result = segments.classify(rec(
            specialties=["software development", "custom software"]))
        self.assertTrue(result["vertical_matched"])
        self.assertIn("software development", result["vertical_matched"])

    def test_a_subvertical_is_only_claimed_when_supported(self):
        result = segments.classify(rec(specialties=["digital marketing",
                                                    "content marketing"]))
        self.assertEqual(result["subvertical"], segments.UNKNOWN)

    def test_every_vertical_in_the_taxonomy_is_reachable_or_named(self):
        for vertical in segments.VERTICALS:
            self.assertIsInstance(vertical, str)
        self.assertIn(segments.NON_ICP, segments.VERTICALS)


class TestEmployeeBands(unittest.TestCase):
    def test_the_bands_cover_every_size(self):
        for employees, expected in ((1, "1_9"), (9, "1_9"), (10, "10_19"),
                                    (19, "10_19"), (20, "20_49"), (49, "20_49"),
                                    (50, "50_99"), (99, "50_99"),
                                    (100, "100_199"), (199, "100_199"),
                                    (200, "200_499"), (499, "200_499"),
                                    (500, "500_999"), (999, "500_999"),
                                    (1000, "1000_PLUS"), (12000, "1000_PLUS")):
            self.assertEqual(segments.employee_band(employees), expected,
                             employees)

    def test_a_missing_count_is_unknown_not_the_smallest_band(self):
        for value in (None, 0, -5, "lots"):
            self.assertEqual(segments.employee_band(value), segments.UNKNOWN,
                             repr(value))

    def test_the_bands_are_contiguous_with_no_gap_or_overlap(self):
        """A gap silently sends a company to UNKNOWN; an overlap misroutes it."""
        table = segments.bands()
        for (_, _, high), (name, low, _) in zip(table, table[1:]):
            self.assertEqual(high + 1, low, f"discontinuity before {name}")

    def test_only_the_last_band_is_open_ended(self):
        table = segments.bands()
        for name, _, high in table[:-1]:
            self.assertIsNotNone(high, name)
        self.assertIsNone(table[-1][2])

    def test_a_client_may_redraw_the_bands(self):
        config = {"segmentation": {"employee_bands": [
            {"name": "under_100", "min": 1, "max": 99},
            {"name": "100_PLUS", "min": 100, "max": None},
        ]}}
        self.assertEqual(segments.employee_band(40, config), "under_100")
        self.assertEqual(segments.employee_band(4000, config), "100_PLUS")

    def test_a_redrawn_table_reorders_correctly(self):
        config = {"segmentation": {"employee_bands": [
            {"name": "under_100", "min": 1, "max": 99},
            {"name": "100_PLUS", "min": 100, "max": None},
        ]}}
        self.assertLess(segments.band_order("under_100", config),
                        segments.band_order("100_PLUS", config))

    def test_a_band_table_with_a_gap_is_refused(self):
        config = {"segmentation": {"employee_bands": [
            {"name": "a", "min": 1, "max": 9},
            {"name": "b", "min": 20, "max": None},
        ]}}
        with self.assertRaises(ValueError):
            segments.bands(config)

    def test_a_band_table_with_an_overlap_is_refused(self):
        config = {"segmentation": {"employee_bands": [
            {"name": "a", "min": 1, "max": 50},
            {"name": "b", "min": 20, "max": None},
        ]}}
        with self.assertRaises(ValueError):
            segments.bands(config)

    def test_a_band_table_that_does_not_end_open_is_refused(self):
        """Otherwise the largest companies in the batch silently become UNKNOWN."""
        config = {"segmentation": {"employee_bands": [
            {"name": "a", "min": 1, "max": 9},
            {"name": "b", "min": 10, "max": 99},
        ]}}
        with self.assertRaises(ValueError):
            segments.bands(config)

    def test_a_malformed_band_is_refused_rather_than_repaired(self):
        for bad in ([{"name": "a"}],
                    [{"name": "a", "min": "many", "max": 9}],
                    [{"name": "a", "min": 0, "max": None}]):
            with self.assertRaises(ValueError):
                segments.bands({"segmentation": {"employee_bands": bad}})

    def test_no_config_means_the_default_table(self):
        for config in (None, {}, {"segmentation": {}},
                       {"segmentation": {"employee_bands": []}}):
            self.assertEqual(segments.bands(config), segments.DEFAULT_BANDS)

    def test_bands_are_ordered_for_merging(self):
        self.assertLess(segments.band_order("1_9"),
                        segments.band_order("1000_PLUS"))


class TestRegionMapping(unittest.TestCase):
    def test_countries_map_to_the_expected_regions(self):
        for country, region in (("United Kingdom", geo.UK),
                                ("Germany", geo.DACH),
                                ("Sweden", geo.NORDICS),
                                ("Netherlands", geo.BENELUX),
                                ("Poland", geo.CEE),
                                ("Italy", geo.SOUTHERN_EUROPE),
                                ("Canada", geo.CANADA),
                                ("New Zealand", geo.ANZ)):
            self.assertEqual(geo.resolve(country=country)["region"], region,
                             country)

    def test_us_states_map_to_us_regions(self):
        for state, region in (("New York", geo.US_EAST),
                              ("Texas", geo.US_CENTRAL),
                              ("California", geo.US_WEST)):
            result = geo.resolve(country="United States", state=state)
            self.assertEqual(result["region"], region, state)

    def test_an_unknown_country_is_other_rather_than_a_guess(self):
        result = geo.resolve(country="Ruritania")
        self.assertEqual(result["region"], geo.OTHER)
        self.assertEqual(result["region_confidence"], geo.UNKNOWN)

    def test_the_region_map_is_configurable(self):
        config = {"segmentation": {"regions": {"croatia": geo.SOUTHERN_EUROPE}}}
        self.assertEqual(geo.resolve(country="Croatia", config=config)["region"],
                         geo.SOUTHERN_EUROPE)

    def test_an_invalid_region_override_is_dropped(self):
        config = {"segmentation": {"regions": {"croatia": "Atlantis"}}}
        self.assertEqual(geo.resolve(country="Croatia", config=config)["region"],
                         geo.CEE)

    def test_the_country_is_kept_separately_from_the_region(self):
        result = geo.resolve(country="Germany")
        self.assertEqual(result["country_code"], "DE")
        self.assertEqual(result["region"], geo.DACH)


class TestTimezone(unittest.TestCase):
    def test_a_single_zone_country_resolves_with_high_confidence(self):
        result = geo.resolve(country="United Kingdom")
        self.assertEqual(result["timezone"], "Europe/London")
        self.assertEqual(result["timezone_confidence"], geo.HIGH)
        self.assertEqual(result["timezone_source"], geo.FROM_COUNTRY_SINGLE)

    def test_a_city_resolves_a_multi_zone_country(self):
        result = geo.resolve(city="Chicago")
        self.assertEqual(result["timezone"], "America/Chicago")
        self.assertEqual(result["timezone_source"], geo.FROM_CITY)

    def test_an_ambiguous_country_holds_rather_than_guessing(self):
        for country in ("United States", "Australia"):
            result = geo.resolve(country=country)
            self.assertIsNone(result["timezone"], country)
            self.assertEqual(result["timezone_confidence"], geo.UNKNOWN)
            self.assertIn("several time zones", result["why"])

    def test_an_ambiguous_company_is_not_schedulable(self):
        ok, why = geo.schedulable(geo.resolve(country="United States"))
        self.assertFalse(ok)
        self.assertIn("several time zones", why)

    def test_a_resolved_company_is_schedulable(self):
        ok, _ = geo.schedulable(geo.resolve(country="Germany"))
        self.assertEqual(ok, geo.available())

    def test_every_stored_timezone_is_an_iana_name(self):
        """Checked across the whole table, not one country.

        An offset is right for half the year. One entry typed as "UTC+1" would
        be correct all winter and silently an hour out every summer, which is
        exactly the failure that is hardest to notice.
        """
        for name, (_, _, zone, _) in geo.COUNTRIES.items():
            if zone is None:
                continue
            self.assertIn("/", zone, name)
            self.assertNotIn("UTC", zone, name)
            self.assertFalse(zone.startswith(("+", "-")), name)
        for city, (_, _, zone) in geo.CITIES.items():
            self.assertIn("/", zone, city)
            self.assertNotIn("UTC", zone, city)

    def test_every_stored_timezone_actually_resolves(self):
        """A typo in the table is a company that can never be scheduled."""
        if not geo.available():
            self.skipTest("no IANA timezone database on this machine")
        zones = {z for _, _, z, _ in geo.COUNTRIES.values() if z}
        zones |= {z for _, _, z in geo.CITIES.values()}
        zones |= {z for _, z in geo.US_STATES.values()}
        for zone in sorted(zones):
            geo.zone(zone)

    def test_whole_token_matching_stops_a_false_city_match(self):
        result = geo.resolve(places="Newcastle upon Tyne")
        self.assertIsNone(result["timezone"])


@unittest.skipUnless(geo.available(), "no IANA timezone database on this machine")
class TestDaylightSaving(unittest.TestCase):
    """The reason the timezone is stored as a name and not an offset."""

    import datetime as _dt
    WINTER = _dt.date(2026, 1, 15)
    SUMMER = _dt.date(2026, 7, 15)

    def test_the_same_local_time_is_a_different_utc_time_across_dst(self):
        winter = geo.send_window("Europe/Zagreb", self.WINTER)
        summer = geo.send_window("Europe/Zagreb", self.SUMMER)
        self.assertEqual(winter["local_start"][11:16], "09:00")
        self.assertEqual(summer["local_start"][11:16], "09:00")
        self.assertNotEqual(winter["utc_start"][11:16],
                            summer["utc_start"][11:16])

    def test_the_offset_moves_by_exactly_one_hour(self):
        winter = geo.send_window("Europe/Zagreb", self.WINTER)
        summer = geo.send_window("Europe/Zagreb", self.SUMMER)
        self.assertEqual(summer["utc_offset_hours"] -
                         winter["utc_offset_hours"], 1.0)

    def test_dst_is_reported_rather_than_inferred(self):
        self.assertFalse(geo.send_window("Europe/London",
                                         self.WINTER)["is_dst"])
        self.assertTrue(geo.send_window("Europe/London",
                                        self.SUMMER)["is_dst"])

    def test_the_southern_hemisphere_runs_the_other_way(self):
        winter = geo.send_window("Australia/Sydney", self.WINTER)
        summer = geo.send_window("Australia/Sydney", self.SUMMER)
        self.assertTrue(winter["is_dst"])
        self.assertFalse(summer["is_dst"])

    def test_a_zone_without_dst_never_moves(self):
        winter = geo.send_window("America/Phoenix", self.WINTER)
        summer = geo.send_window("America/Phoenix", self.SUMMER)
        self.assertEqual(winter["utc_offset_hours"],
                         summer["utc_offset_hours"])

    def test_the_window_is_the_local_window_the_client_configured(self):
        config = {"scheduling": {"windows": {"email": {"start": "08:00",
                                                       "end": "10:00"}}}}
        result = geo.send_window("Europe/Berlin", self.SUMMER, config)
        self.assertEqual(result["local_start"][11:16], "08:00")
        self.assertEqual(result["local_end"][11:16], "10:00")

    def test_the_linkedin_window_is_wider_than_the_email_one(self):
        email = geo.send_window("Europe/London", self.SUMMER, channel="email")
        linkedin = geo.send_window("Europe/London", self.SUMMER,
                                   channel="linkedin")
        self.assertLess(email["local_end"], linkedin["local_end"])

    def test_a_weekend_is_marked_as_not_a_sending_day(self):
        import datetime
        saturday = datetime.date(2026, 7, 18)
        self.assertEqual(saturday.isoweekday(), 6)
        self.assertFalse(geo.send_window("Europe/London", saturday)["sending_day"])

    def test_no_timezone_means_no_window(self):
        result = geo.send_window(None, self.SUMMER)
        self.assertFalse(result["ok"])
        self.assertIn("held", result["reason"])


class TestTheSyntheticCompanies(CampaignTest):
    def test_every_archetype_appears(self):
        described = companies.describe(len(companies.ARCHETYPES) * 3)
        for name in companies.ARCHETYPE_NAMES:
            self.assertGreater(described["per_archetype"][name]["count"], 0)

    def test_the_dataset_is_deterministic(self):
        self.assertEqual(companies.record(41), companies.record(41))

    def test_each_archetype_reaches_its_intended_verdict(self):
        size = len(companies.ARCHETYPES) * 2
        batch = companies.dataset(size)
        expected = {
            "strong_digital_agency": icp.QUALIFIED,
            "strong_software_agency": icp.QUALIFIED,
            "large_consultancy": icp.QUALIFIED,
            "saas_product": icp.REJECTED,
            "ecommerce_retailer": icp.REJECTED,
            "holding_company": icp.REJECTED,
            "manufacturer": icp.REJECTED,
            "tiny_studio": icp.REJECTED,
            "unknown_thin": icp.UNKNOWN,
        }
        for archetype, status in expected.items():
            index = companies.indices_of(archetype, size)[0]
            result = icp.score(batch[index])
            self.assertEqual(result["icp_status"], status,
                             f"{archetype}: {result['classification_reasons']}")

    def test_the_contradictory_archetype_is_never_a_confident_answer(self):
        """A company whose own facts disagree must reach a human."""
        size = len(companies.ARCHETYPES) * 2
        batch = companies.dataset(size)
        index = companies.indices_of("contradictory_evidence", size)[0]
        result = icp.score(batch[index])
        self.assertTrue(result["contradictions"])
        self.assertNotEqual(result["icp_confidence"], icp.HIGH)

    def test_the_mix_contains_contradictory_evidence(self):
        """Otherwise three of the four detectors are only ever unit-tested."""
        size = len(companies.ARCHETYPES) * 2
        batch = companies.dataset(size)
        kinds = set()
        for rec in batch:
            for found in icp.contradictions(rec, segments.classify(rec)):
                kinds.add(found["kind"])
        for kind in ("vertical_vs_non_icp", "size_vs_offices",
                     "headcount_sources_disagree",
                     "implausible_founding_year"):
            self.assertIn(kind, kinds, kind)

    def test_the_mix_contains_every_status(self):
        batch = companies.dataset(len(companies.ARCHETYPES) * 2)
        seen = {icp.score(rec)["icp_status"] for rec in batch}
        self.assertEqual(seen, set(icp.STATUSES))

    def test_it_calls_no_provider(self):
        companies.dataset(40)
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
