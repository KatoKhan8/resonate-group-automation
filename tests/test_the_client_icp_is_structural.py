#!/usr/bin/env python3
"""The client's ICP is its own criteria, and pain evidence is not one of them.

## The defect, in one number

`icp.score` weighs twelve dimensions. Five are structural - agency fit,
project delivery, employee count, geography, service not product - summing to
55. Seven are PAIN - does the website mention utilisation, profitability,
resource planning, timesheets - summing to 45. `tier_b` is 60.

So a flawless marketing agency, the right size, in a country the client
sells to, whose website happens never to say "utilisation", could not be
qualified. Not unlikely to be: could not be. Measured on the 300-domain
Productive cohort: 16 qualified, and 300 of 300 records carried "no evidence
for time tracking need".

Pain evidence decides WHAT WE SAY. The client's criteria decide WHOM WE
TARGET. This file pins that separation.

## UNKNOWN is not FAIL

    FAIL     we know this company does not fit
    UNKNOWN  we could not establish it

Every test below that asserts UNKNOWN is asserting the difference. Collapsing
them is how a cohort hand-picked as a client's market comes back 5%
qualified.
"""
import unittest

from src import icpstructural as st
from src import store

CLIENT = {
    "name": "Test Client",
    "icp": {"structural": {
        "geographies": {"include": ["United Kingdom", "Germany",
                                    "United States", "Australia"],
                        "exclude": ["India", "Pakistan",
                                    "United Arab Emirates"]},
        "company_types": {"primary": ["marketing_agency", "software_agency"],
                          "verticals": ["Digital Marketing Agency",
                                        "Software Development Agency",
                                        "Creative / Branding Agency"]},
        "services_business_required": True,
        "tracks_time_required": True,
        "employees": {"min": 20, "tolerance": 0.30,
                      "revenue_contradicts_below_millions": 3},
    }},
}


def a_record(**facts):
    rec = store.new_record("acct", "domains", "test", "Acme", "acme.test")
    rec["company_facts"] = facts
    return rec


def a_segment(vertical="Digital Marketing Agency", country="United Kingdom",
              employees=60, business_model="agency", region=None):
    return {"vertical": vertical, "country": country, "region": region,
            "employees": employees, "business_model": business_model,
            "vertical_matched": [], "non_icp_signals": []}


def verdict(rec=None, **segment_over):
    return st.structural(rec if rec is not None else a_record(), CLIENT,
                         a_segment(**segment_over))


class TheDerivedFloorComesFromConfig(unittest.TestCase):
    """20 x (1 - 0.30) = 14, and 14 appears nowhere in the engine."""

    def test_the_floor_is_derived_not_written(self):
        rules = st.settings(CLIENT)
        self.assertEqual(rules["min_employees"], 20)
        self.assertEqual(rules["employee_tolerance"], 0.30)
        self.assertEqual(rules["effective_min_employees"], 14)

    def test_a_different_client_gets_a_different_floor(self):
        other = {"icp": {"structural": {"employees": {"min": 50,
                                                      "tolerance": 0.10}}}}
        self.assertEqual(st.settings(other)["effective_min_employees"], 45)

    def test_the_answer_follows_the_config_not_the_client_name(self):
        """Asserted on behaviour, not by grepping the source for a client
        name - the docstrings cite the cohort the defect was measured on, and
        a test that fails when somebody writes a comment is the trap this
        repository keeps falling into.

        The same company, two configs, two answers. Nothing in the module can
        be branching on who the client is if that holds.
        """
        rec = a_record()
        segment = a_segment(employees=30, country="Germany")

        buyer_of_agencies = st.structural(rec, CLIENT, segment)
        self.assertIn(buyer_of_agencies["verdict"], st.ELIGIBLE)

        wants_bigger = {"icp": {"structural": dict(
            CLIENT["icp"]["structural"],
            employees={"min": 500, "tolerance": 0.0})}}
        self.assertEqual(
            st.structural(rec, wants_bigger, segment)["primary_reason"],
            "employees")

        wants_elsewhere = {"icp": {"structural": dict(
            CLIENT["icp"]["structural"],
            geographies={"include": ["Japan"], "exclude": ["Germany"]})}}
        self.assertEqual(
            st.structural(rec, wants_elsewhere, segment)["primary_reason"],
            "geography")

    def test_a_client_declaring_no_rule_is_not_judged_on_it(self):
        """`not_required` rather than a silent pass, so a client with no size
        policy is visibly not being size-checked."""
        no_size = {"icp": {"structural": {"employees": {}}}}
        got = st.structural(a_record(), no_size, a_segment(employees=2))
        self.assertEqual(got["criteria"]["employees"]["status"],
                         st.NOT_REQUIRED)


class Headcount(unittest.TestCase):
    """The exact table the client's correction asked for."""

    def status(self, employees, **facts):
        return verdict(a_record(**facts),
                       employees=employees)["criteria"]["employees"]["status"]

    def test_20_passes(self):
        self.assertEqual(self.status(20), st.PASS)

    def test_19_passes_on_tolerance(self):
        self.assertEqual(self.status(19), st.PASS_WITH_TOLERANCE)

    def test_14_passes_on_tolerance(self):
        self.assertEqual(self.status(14), st.PASS_WITH_TOLERANCE)

    def test_13_fails(self):
        self.assertEqual(self.status(13), st.FAIL)

    def test_unknown_is_unknown_not_fail(self):
        self.assertEqual(self.status(None), st.UNKNOWN)


class ABandIsNotAHeadcount(unittest.TestCase):
    """`employees: 11` beside `employee_range: "11-50 employees"` means
    somewhere between eleven and fifty. Reading it as eleven rejected 151 of
    300 companies on this cohort, and the records say so themselves -
    `recovered_from.confidence` states that `employees` is the band's lower
    bound and not a measured headcount."""

    def test_a_band_straddling_the_floor_is_unknown(self):
        got = verdict(a_record(employees=11, employee_range="11-50 employees"),
                      employees=11)
        self.assertEqual(got["criteria"]["employees"]["status"], st.UNKNOWN)
        self.assertIn("straddles", got["criteria"]["employees"]["why"])

    def test_a_band_wholly_below_the_floor_still_fails(self):
        got = verdict(a_record(employees=2, employee_range="2-10 employees"),
                      employees=2)
        self.assertEqual(got["criteria"]["employees"]["status"], st.FAIL)

    def test_a_band_starting_at_the_minimum_passes(self):
        got = verdict(a_record(employees=51, employee_range="51-200 employees"),
                      employees=51)
        self.assertEqual(got["criteria"]["employees"]["status"], st.PASS)

    def test_a_free_people_count_can_raise_the_lower_bound(self):
        """`headcount_signal` is how many people a provider actually found,
        which is a floor. 46 records on the cohort carry one larger than the
        estimate and it was discarded."""
        got = verdict(a_record(employees=11, headcount_signal=48), employees=11)
        self.assertEqual(got["criteria"]["employees"]["status"], st.PASS)


class RevenueThatContradictsTheHeadcount(unittest.TestCase):
    """28 companies on the cohort report under the floor while also reporting
    $3M or more, one of them four people against $172.7M."""

    def test_it_becomes_unknown_rather_than_fail(self):
        got = verdict(a_record(employees=4, revenue="$21.1M"), employees=4)
        self.assertEqual(got["criteria"]["employees"]["status"], st.UNKNOWN)

    def test_it_does_not_become_a_pass(self):
        """Revenue is not a headcount. It removes a rejection; it does not
        establish size, so the company cannot reach `icp_pass` on it."""
        got = verdict(a_record(employees=4, revenue="$21.1M"), employees=4)
        self.assertNotEqual(got["verdict"], st.ICP_PASS)
        self.assertIn("employees", got["unknown_criteria"])

    def test_a_small_revenue_does_not_rescue_a_small_company(self):
        got = verdict(a_record(employees=4, revenue="$463.0K"), employees=4)
        self.assertEqual(got["criteria"]["employees"]["status"], st.FAIL)


class PainEvidenceIsNotAnIcpCriterion(unittest.TestCase):
    """The heart of it. A structurally perfect company with no pain evidence
    anywhere must remain eligible."""

    def test_a_marketing_agency_with_no_signals_at_all_is_eligible(self):
        got = verdict()
        self.assertIn(got["verdict"], st.ELIGIBLE)
        self.assertTrue(got["eligible"])

    def test_a_software_agency_likewise(self):
        got = verdict(vertical="Software Development Agency",
                      country="Germany", employees=72)
        self.assertIn(got["verdict"], st.ELIGIBLE)

    def test_utilization_is_not_consulted(self):
        """There is no utilization criterion. Asserted on the criteria set
        rather than on a score, because the defect was a criterion existing
        at all."""
        for absent in ("utilization", "profitability", "resource_planning",
                       "operational_complexity", "delivery_complexity"):
            self.assertNotIn(absent, st.CRITERIA)

    def test_the_criteria_are_exactly_the_clients(self):
        self.assertEqual(set(st.CRITERIA),
                         {"geography", "company_type", "services_business",
                          "employees", "tracks_time"})


class TimeTrackingIsAMustHaveAndStillNotAFail(unittest.TestCase):
    """The client's must-have, and the criterion most at risk of a false FAIL.
    A homepage that does not mention timesheets is not a company that does not
    keep them."""

    def test_silence_is_unknown(self):
        got = verdict()
        self.assertEqual(got["criteria"]["tracks_time"]["status"], st.UNKNOWN)
        self.assertIn(got["verdict"], st.ELIGIBLE)

    def test_billing_language_establishes_it(self):
        rec = a_record(specialties=["retainer and billable project work"])
        got = verdict(rec)
        self.assertEqual(got["criteria"]["tracks_time"]["status"], st.PASS)

    def test_a_product_company_fails_it(self):
        """Affirmative evidence of selling something other than time."""
        got = verdict(business_model="product")
        self.assertEqual(got["criteria"]["tracks_time"]["status"], st.FAIL)
        self.assertEqual(got["verdict"], st.ICP_FAIL)


class WhatActuallyFails(unittest.TestCase):
    """FAIL means we know the company does not fit."""

    def test_an_excluded_geography_fails(self):
        got = verdict(country="India")
        self.assertEqual(got["criteria"]["geography"]["status"], st.FAIL)
        self.assertEqual(got["verdict"], st.ICP_FAIL)
        self.assertEqual(got["primary_reason"], "geography")

    def test_a_classified_wrong_vertical_fails(self):
        got = verdict(vertical="Plumbing Contractor")
        self.assertEqual(got["criteria"]["company_type"]["status"], st.FAIL)
        self.assertEqual(got["primary_reason"], "company_type")

    def test_an_ecommerce_business_fails(self):
        got = verdict(business_model="ecommerce")
        self.assertEqual(got["verdict"], st.ICP_FAIL)


class WhatIsUnknownRatherThanFailed(unittest.TestCase):

    def test_an_unresolvable_country_is_unknown(self):
        got = verdict(country=None, region=None)
        self.assertEqual(got["criteria"]["geography"]["status"], st.UNKNOWN)
        self.assertNotEqual(got["verdict"], st.ICP_FAIL)

    def test_a_country_on_neither_list_is_unknown(self):
        """Canada is not on the exclude list. It was being rejected."""
        got = verdict(country="Canada")
        self.assertEqual(got["criteria"]["geography"]["status"], st.UNKNOWN)
        self.assertNotEqual(got["verdict"], st.ICP_FAIL)

    def test_an_unclassifiable_vertical_is_unknown(self):
        got = verdict(vertical="UNKNOWN")
        self.assertEqual(got["criteria"]["company_type"]["status"], st.UNKNOWN)
        self.assertNotEqual(got["verdict"], st.ICP_FAIL)

    def test_a_research_timeout_is_not_a_rejection(self):
        """28 scrapes timed out on this cohort. A run that did not finish is
        not a fact about the company."""
        rec = a_record(research_outcome="TIMEOUT")
        got = verdict(rec, vertical="UNKNOWN", country=None, employees=None)
        self.assertNotEqual(got["verdict"], st.ICP_FAIL)
        self.assertIsNone(got["primary_reason"])


class TheEvidenceIsResolvedFromTheWholeRecord(unittest.TestCase):
    """`segments.classify` reads a narrower slice than the record holds, and
    it was the only witness being asked."""

    def test_a_country_code_in_the_office_lines_is_found(self):
        rec = a_record(offices=["Islands Brygge 79A , Kobenhavn S, 2300, DK"])
        name, source = st.resolve_country(rec, a_segment(country=None))
        self.assertEqual(name, "Denmark")
        self.assertEqual(source, "company_facts.offices")

    def test_an_agency_industry_stands_in_for_an_unclassified_vertical(self):
        """116 records carry an agency industry while the vertical classifier
        reports "only 1 weak signal, not enough to classify"."""
        rec = a_record(industry="Advertising Services")
        got = verdict(rec, vertical="UNKNOWN")
        self.assertEqual(got["criteria"]["company_type"]["status"], st.PASS)

    def test_a_non_agency_industry_does_not(self):
        rec = a_record(industry="Government Administration")
        got = verdict(rec, vertical="UNKNOWN")
        self.assertEqual(got["criteria"]["company_type"]["status"], st.UNKNOWN)


class OneReasonPerRejection(unittest.TestCase):
    """A rejection audit has to reconcile, so every FAIL names exactly one
    primary reason and it is the first in the client's own sequence."""

    def test_a_failing_company_names_one_reason(self):
        got = verdict(country="India", vertical="Plumbing Contractor")
        self.assertEqual(got["primary_reason"], "geography")

    def test_a_passing_company_names_none(self):
        self.assertIsNone(verdict()["primary_reason"])

    def test_the_summary_reconciles(self):
        results = [verdict(), verdict(country="India"),
                   verdict(vertical="Plumbing Contractor"), verdict()]
        out = st.summarise(results)
        self.assertEqual(out["total"], 4)
        self.assertEqual(sum(out["verdicts"].values()), 4)
        self.assertEqual(sum(out["fail_reasons"].values()),
                         out["verdicts"].get(st.ICP_FAIL, 0))


if __name__ == "__main__":
    unittest.main()
