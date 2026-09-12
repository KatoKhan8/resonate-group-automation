#!/usr/bin/env python3
"""A correct evaluator nothing imports decides nothing.

`src/icpstructural.py` answered the client's real question - services
business, right vertical, a geography they sell to, 20+ people - and answered
it correctly, on the 300-domain Productive cohort, while being imported by
NOTHING in `src/`. Every stored verdict was still V1. That is the defect
CLAUDE.md names: a thing computed correctly that nothing downstream reads.

So this file does not test the structural computation.
`tests/test_the_client_icp_is_structural.py` already does, and it passed for
the whole time the evaluator was disconnected - which is exactly why it could
not catch this. What is tested here is CONSUMPTION: that the structural
answer reaches every gate the pipeline actually spends money at.

    icp.score           the verdict the rest of the system reads
    routing.plan        max_contacts_to_enrich - the number that caps spend
    dmplan.for_company  the credits the plan says this company costs
    dmplan.may_enrich   the single gate in front of a paid person call
    qualify.state_of    where a batch reports this company is

Every test below drives one of those with a company whose structural answer
and whose V1 answer DISAGREE, and asserts the consumer followed the
structural one. Each has its counterfactual beside it: the same record scored
under a client with no structural block, so no assertion here can pass by
luck. The disagreement runs in both directions on purpose - a flawless agency
V1 held at `review` is now qualified, and a Singapore agency V1 held at
`review` is now rejected outright. Wiring an evaluator in that could only ever
widen the pool would be a different and worse change.

## The V1 answer is preserved, not overwritten

`icp_score`, `icp_confidence`, `icp_status_v1` and `icp_tier_v1` sit on the
same verdict and reconstruct the twelve-dimension answer exactly. The score is
still computed in full; it has become a priority inside the eligible pool
rather than the gate into it.

## Nothing here is a fixture of the segment classifier

The records are real records and the segments come from `segments.classify`,
so a test that goes green proves the whole chain from stored company facts to
a spend decision - not that a handwritten dict flows through five functions.
"""
import unittest

from src import (dmplan, enrich, icp, icpstructural, qualify, routing,
                 segments, store)

# The client's criteria, in the shape `config/clients/productive.yaml` uses.
# Written out here rather than loaded, so this pins the ENGINE's behaviour and
# not one YAML file's current contents.
CLIENT = {
    "name": "Test Client",
    "icp": {"structural": {
        "geographies": {"include": ["United Kingdom", "Germany"],
                        "exclude": ["India", "Singapore"]},
        "company_types": {"primary": ["marketing_agency"],
                          "verticals": ["Digital Marketing Agency",
                                        "Creative / Branding Agency",
                                        "Software Development Agency"]},
        "services_business_required": True,
        "tracks_time_required": True,
        "employees": {"min": 20, "tolerance": 0.30,
                      "revenue_contradicts_below_millions": 3},
    }},
}

# The same client with the structural block removed and nothing else changed.
# This is the counterfactual every test pairs against.
NO_STRUCTURAL = {"name": "Test Client", "icp": {}}

# A company that satisfies every structural criterion the client has - and
# says nothing anywhere about utilisation, timesheets, margin or resource
# planning. That silence is the point. Seven of `icp.score`'s twelve
# dimensions are that pain language, they sum to 45, and `tier_b` is 60, so a
# flawless agency silent on all of it CANNOT reach `qualified` under V1. The
# client would still call it a prospect, and now so does the engine.
FLAWLESS_AGENCY = {
    "industry": "Marketing and Advertising",
    "description": "A digital marketing agency delivering client campaigns.",
    "employee_range": "51-200 employees",
    "employees": 60,
    "offices": ["1 High Street, London, England, W1, GB"],
    "services": ["digital marketing", "branding"],
}


def a_record(**facts_over):
    rec = store.new_record("acct", "domains", "test", "Acme", "acme.test")
    facts = dict(FLAWLESS_AGENCY)
    facts.update(facts_over)
    rec["company_facts"] = {k: v for k, v in facts.items() if v is not None}
    return rec


def scored(rec=None, config=CLIENT, **facts_over):
    """One record, classified and scored the way the pipeline does it."""
    rec = a_record(**facts_over) if rec is None else rec
    segment = segments.classify(rec, config)
    return rec, segment, icp.score(rec, config, segment=segment)


def planned(rec, segment, verdict, config=CLIENT):
    """One company all the way to the spend plan, spending nothing."""
    persona_plan = routing.plan(rec, segment, verdict, config)
    return persona_plan, dmplan.for_company(rec, persona_plan, verdict, config)


def an_approved_batch(rec, segment, verdict, config=CLIENT):
    """A batch whose person-enrichment plan a human has approved.

    So that `may_enrich` is refusing or allowing on the ICP status rather than
    on a missing approval, which would make every assertion below pass for the
    wrong reason.
    """
    persona_plan, _ = planned(rec, segment, verdict, config)
    companies = [{"record": rec, "verdict": verdict,
                  "persona_plan": persona_plan, "segment_key": "k"}]
    batch = {}
    dmplan.approve(batch, companies, "a.human", config)
    return batch, companies


# --------------------------------------------------------------- the setup

class TheTwoModelsDisagreeAboutTheseCompanies(unittest.TestCase):
    """Stated once, because every test below depends on it."""

    def test_a_flawless_agency_v1_would_not_qualify(self):
        _, _, verdict = scored()
        self.assertEqual(verdict["icp_status"], icp.QUALIFIED)
        self.assertNotEqual(verdict["icp_status_v1"], icp.QUALIFIED)

    def test_an_excluded_geography_v1_would_not_reject(self):
        """The disagreement runs the strict way too."""
        _, _, verdict = scored(offices=["10 Raffles Place, Singapore, SG"])
        self.assertEqual(verdict["icp_status"], icp.REJECTED)
        self.assertNotEqual(verdict["icp_status_v1"], icp.REJECTED)


class TheV1AnswerIsPreservedRatherThanOverwritten(unittest.TestCase):

    def test_both_answers_are_on_the_verdict(self):
        _, _, verdict = scored()
        self.assertIn(verdict["icp_status_v1"], icp.STATUSES)
        self.assertIn(verdict["icp_tier_v1"], icp.TIERS)
        self.assertEqual(verdict["v1_scoring_version"], icp.SCORING_VERSION)

    def test_the_preserved_answer_is_the_one_v1_would_have_given(self):
        """Not merely present: equal to what the unconfigured path returns."""
        rec, segment, verdict = scored()
        v1 = icp.score(rec, NO_STRUCTURAL, segment=segment)
        self.assertEqual(verdict["icp_status_v1"], v1["icp_status"])
        self.assertEqual(verdict["icp_tier_v1"], v1["icp_tier"])

    def test_the_number_under_it_is_untouched(self):
        rec, segment, verdict = scored()
        v1 = icp.score(rec, NO_STRUCTURAL, segment=segment)
        self.assertEqual(verdict["icp_score"], v1["icp_score"])
        self.assertEqual(verdict["icp_raw_score"], v1["icp_raw_score"])
        self.assertEqual(verdict["icp_confidence"], v1["icp_confidence"])
        self.assertEqual(verdict["dimensions_scored"], v1["dimensions_scored"])

    def test_the_verdict_says_which_model_decided_it(self):
        _, _, verdict = scored()
        self.assertEqual(verdict["scoring_version"],
                         icp.STRUCTURAL_SCORING_VERSION)
        self.assertNotEqual(verdict["scoring_version"], icp.SCORING_VERSION)

    def test_the_structural_answer_is_carried_with_its_reasons(self):
        _, _, verdict = scored()
        self.assertIn(verdict["structural"]["verdict"], icpstructural.ELIGIBLE)
        self.assertEqual(sorted(verdict["structural"]["criteria"]),
                         sorted(icpstructural.CRITERIA))


# ------------------------------------------------------------ the consumers

class TheContactCapFollowsTheStructuralVerdict(unittest.TestCase):
    """`max_contacts_to_enrich` is the number that decides the spend.

    A verdict of `qualified` that leaves the cap at zero is the V1 gate
    re-imposed one layer down, and the wiring would be theatre.
    """

    def test_an_eligible_company_may_have_contacts_looked_for(self):
        rec, segment, verdict = scored()
        persona_plan, _ = planned(rec, segment, verdict)
        self.assertGreater(persona_plan["max_contacts_to_enrich"], 0)

    def test_the_same_record_under_v1_is_capped_at_zero(self):
        rec, segment, _ = scored()
        v1 = icp.score(rec, NO_STRUCTURAL, segment=segment)
        persona_plan = routing.plan(rec, segment, v1, NO_STRUCTURAL)
        self.assertEqual(persona_plan["max_contacts_to_enrich"], 0)

    def test_a_structural_fail_caps_it_at_zero(self):
        rec, segment, verdict = scored(
            offices=["10 Raffles Place, Singapore, SG"])
        self.assertEqual(verdict["icp_status"], icp.REJECTED)
        persona_plan, _ = planned(rec, segment, verdict)
        self.assertEqual(persona_plan["max_contacts_to_enrich"], 0)

    def test_a_company_below_the_derived_floor_caps_it_at_zero(self):
        rec, segment, verdict = scored(employee_range="2-10 employees",
                                       employees=4)
        self.assertEqual(verdict["structural"]["primary_reason"], "employees")
        persona_plan, _ = planned(rec, segment, verdict)
        self.assertEqual(persona_plan["max_contacts_to_enrich"], 0)

    def test_a_structural_review_caps_it_at_zero(self):
        """Neither defining criterion established: ignorance, not uncertainty."""
        rec, segment, verdict = scored(industry=None, description=None,
                                       employee_range=None, employees=None,
                                       offices=None, services=None)
        self.assertEqual(verdict["structural"]["verdict"],
                         icpstructural.ICP_REVIEW)
        self.assertEqual(verdict["icp_status"], icp.REVIEW)
        persona_plan, _ = planned(rec, segment, verdict)
        self.assertEqual(persona_plan["max_contacts_to_enrich"], 0)


class TheSpendPlanFollowsTheStructuralVerdict(unittest.TestCase):
    """What `dmplan` says finding this company's people would cost."""

    def test_an_eligible_company_is_planned_for(self):
        rec, segment, verdict = scored()
        _, cost = planned(rec, segment, verdict)
        self.assertTrue(cost["enrichment_required"])
        self.assertGreater(cost["maximum_credits"], 0)

    def test_the_same_record_under_v1_costs_nothing(self):
        rec, segment, _ = scored()
        v1 = icp.score(rec, NO_STRUCTURAL, segment=segment)
        _, cost = planned(rec, segment, v1, NO_STRUCTURAL)
        self.assertFalse(cost["enrichment_required"])
        self.assertEqual(cost["maximum_credits"], 0)

    def test_a_structurally_failed_company_costs_nothing(self):
        rec, segment, verdict = scored(
            description="We sell our products online through our shop. Buy "
                        "now, free shipping on every order in our online "
                        "store.",
            industry="Retail", services=["online store"])
        self.assertEqual(verdict["icp_status"], icp.REJECTED)
        _, cost = planned(rec, segment, verdict)
        self.assertFalse(cost["enrichment_required"])
        self.assertEqual(cost["maximum_credits"], 0)


class TheSpendGateFollowsTheStructuralVerdict(unittest.TestCase):
    """`may_enrich` is the last thing between a verdict and a paid call."""

    def test_an_eligible_company_is_allowed_through(self):
        rec, segment, verdict = scored()
        batch, companies = an_approved_batch(rec, segment, verdict)
        allowed, why = dmplan.may_enrich(batch, companies, rec, verdict,
                                         CLIENT)
        self.assertTrue(allowed, why)

    def test_the_same_record_under_v1_is_refused(self):
        rec, segment, _ = scored()
        v1 = icp.score(rec, NO_STRUCTURAL, segment=segment)
        batch, companies = an_approved_batch(rec, segment, v1, NO_STRUCTURAL)
        allowed, _ = dmplan.may_enrich(batch, companies, rec, v1,
                                       NO_STRUCTURAL)
        self.assertFalse(allowed)

    def test_a_structural_fail_is_refused_even_with_a_current_approval(self):
        rec, segment, verdict = scored(
            offices=["10 Raffles Place, Singapore, SG"])
        batch, companies = an_approved_batch(rec, segment, verdict)
        allowed, _ = dmplan.may_enrich(batch, companies, rec, verdict, CLIENT)
        self.assertFalse(allowed)

    def test_a_structural_review_waits_for_a_human(self):
        rec, segment, verdict = scored(industry=None, description=None,
                                       employee_range=None, employees=None,
                                       offices=None, services=None)
        batch, companies = an_approved_batch(rec, segment, verdict)
        allowed, _ = dmplan.may_enrich(batch, companies, rec, verdict, CLIENT)
        self.assertFalse(allowed)

    def test_require_raises_on_a_structural_fail(self):
        rec, segment, verdict = scored(
            offices=["10 Raffles Place, Singapore, SG"])
        batch, companies = an_approved_batch(rec, segment, verdict)
        with self.assertRaises(dmplan.NotApproved):
            dmplan.require(batch, companies, rec, verdict, CLIENT)


class TheBatchReportsWhereTheStructuralVerdictPutIt(unittest.TestCase):
    """`qualify.state_of` is what an operator sees a batch as being."""

    def test_an_eligible_company_reports_qualified(self):
        rec = a_record()
        qualify.company(rec, CLIENT)
        self.assertEqual(qualify.state_of(rec), dmplan.QUALIFIED)

    def test_the_eligible_record_under_v1_reports_review_required(self):
        rec = a_record()
        qualify.company(rec, NO_STRUCTURAL)
        self.assertEqual(qualify.state_of(rec), dmplan.REVIEW_REQUIRED)

    def test_an_excluded_geography_reports_rejected(self):
        rec = a_record(offices=["10 Raffles Place, Singapore, SG"])
        qualify.company(rec, CLIENT)
        self.assertEqual(qualify.state_of(rec), dmplan.REJECTED)

    def test_the_excluded_record_under_v1_reports_review_required(self):
        """The strict direction is a consumption change too."""
        rec = a_record(offices=["10 Raffles Place, Singapore, SG"])
        qualify.company(rec, NO_STRUCTURAL)
        self.assertEqual(qualify.state_of(rec), dmplan.REVIEW_REQUIRED)

    def test_the_stored_verdict_carries_both_answers(self):
        rec = a_record()
        qualify.company(rec, CLIENT)
        stored = (rec["qualification"] or {}).get("verdict") or {}
        self.assertEqual(stored["scoring_version"],
                         icp.STRUCTURAL_SCORING_VERSION)
        self.assertEqual(stored["icp_status"], icp.QUALIFIED)
        self.assertNotEqual(stored["icp_status_v1"], icp.QUALIFIED)


class ADropDerivedFromTheOldVerdictDoesNotSurviveIt(unittest.TestCase):
    """The last link in the chain, and the one that would have been missed.

    `enrich.outcome` retires a company with no contacts and a rejected verdict
    as `dropped`, with the reason `enrich.ICP_REJECTED`. That is a decision,
    and it is DERIVED from the verdict - so when the verdict stops saying
    rejected, nothing holds it up any more.

    Measured on the Productive estate at the moment the client's structural
    criteria became the gate: 11 companies the client's own criteria qualify
    sat `dropped` under exactly that reason. `dropped` is terminal in
    `run.TERMINAL`, outside `enrich.run`'s states, and blocked outright by
    `eligibility._record_state` - so a better verdict would have been
    computed, stored and reported, and could not have reached one of them.

    Only in the safe direction: nothing here drops anything, and a drop for
    any other reason is left exactly where it is.
    """

    def dropped_record(self, reason, **facts):
        rec = a_record(**facts)
        rec["state"] = "dropped"
        rec["drop_reason"] = reason
        return rec

    def test_a_now_eligible_company_returns_to_the_queue(self):
        rec = self.dropped_record(enrich.ICP_REJECTED)
        qualify.company(rec, CLIENT)
        self.assertEqual(rec["state"], "queued")
        self.assertIsNone(rec["drop_reason"])

    def test_a_company_the_criteria_still_reject_stays_dropped(self):
        rec = self.dropped_record(enrich.ICP_REJECTED,
                                  offices=["10 Raffles Place, Singapore, SG"])
        qualify.company(rec, CLIENT)
        self.assertEqual(rec["state"], "dropped")
        self.assertEqual(rec["drop_reason"], enrich.ICP_REJECTED)

    def test_a_drop_for_any_other_reason_is_untouched(self):
        rec = self.dropped_record("suppressed: the client asked us not to")
        qualify.company(rec, CLIENT)
        self.assertEqual(rec["state"], "dropped")
        self.assertEqual(rec["drop_reason"],
                         "suppressed: the client asked us not to")

    def test_a_human_who_said_no_is_not_overruled(self):
        """A model changing its mind does not reopen a person's rejection."""
        rec = a_record()
        qualify.company(rec, CLIENT)
        qualify.record_review(rec, qualify.REJECT, "a.human")
        rec["state"] = "dropped"
        rec["drop_reason"] = enrich.ICP_REJECTED
        qualify.company(rec, CLIENT)
        self.assertEqual(rec["state"], "dropped")

    def test_the_release_is_written_into_the_record_log(self):
        rec = self.dropped_record(enrich.ICP_REJECTED)
        qualify.company(rec, CLIENT)
        self.assertTrue(any("no longer stands" in (row.get("note") or "")
                            for row in rec.get("log") or []))

    def test_a_record_that_was_never_dropped_is_not_touched(self):
        rec = a_record()
        qualify.company(rec, CLIENT)
        self.assertEqual(rec["state"], "queued")
        self.assertIsNone(rec["drop_reason"])


class AClientWithoutStructuralCriteriaIsUntouched(unittest.TestCase):
    """Wiring this in must not silently re-decide anybody else's ICP.

    `demo.yaml` and every client that has not written the block keep the
    twelve-dimension answer, and say so in the version they store.
    """

    def test_the_answer_is_the_v1_answer(self):
        _, _, verdict = scored(config=NO_STRUCTURAL)
        self.assertEqual(verdict["icp_status"], verdict["icp_status_v1"])
        self.assertEqual(verdict["icp_tier"], verdict["icp_tier_v1"])

    def test_the_version_says_v1_decided_it(self):
        _, _, verdict = scored(config=NO_STRUCTURAL)
        self.assertEqual(verdict["scoring_version"], icp.SCORING_VERSION)

    def test_an_empty_config_is_not_a_structural_client(self):
        _, _, verdict = scored(config={})
        self.assertEqual(verdict["scoring_version"], icp.SCORING_VERSION)

    def test_no_config_at_all_does_not_go_looking_for_one(self):
        """`config=None` means none was handed in, not "go find one on disk"."""
        _, _, verdict = scored(config=None)
        self.assertEqual(verdict["scoring_version"], icp.SCORING_VERSION)


class TheScoreBecameAPriorityRatherThanAGate(unittest.TestCase):
    """It is still computed, in full, and it ranks instead of excluding."""

    def test_a_better_scoring_eligible_company_outranks_a_quieter_one(self):
        _, _, quiet = scored()
        _, _, loud = scored(
            description="A digital marketing agency. We track billable "
                        "utilisation across projects with timesheets, project "
                        "margin, resource planning and capacity planning for "
                        "our delivery teams and multiple clients on retainer.")
        self.assertGreater(loud["icp_score"], quiet["icp_score"])
        order = {icp.TIER_A: 0, icp.TIER_B: 1, icp.TIER_C: 2}
        self.assertLess(order[loud["icp_tier"]], order[quiet["icp_tier"]])
        self.assertEqual(quiet["icp_status"], icp.QUALIFIED)
        self.assertEqual(loud["icp_status"], icp.QUALIFIED)

    def test_a_low_score_is_never_an_exclusion_for_an_eligible_company(self):
        """Whatever it scores, an eligible company is worth one contact."""
        _, _, verdict = scored()
        self.assertIn(verdict["icp_tier"],
                      (icp.TIER_A, icp.TIER_B, icp.TIER_C))
        caps = routing.settings(CLIENT)["caps"]
        self.assertGreater(caps[verdict["icp_tier"]], 0)


if __name__ == "__main__":
    unittest.main()
