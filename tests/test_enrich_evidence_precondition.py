"""Evidence precondition for person-level enrichment. TASK-205.

The ordering defect: person credits are spent before the evidence that
licenses writing to the person. 20 records reached `verified` with ZERO usable
research - all held icp_pass_with_uncertainty from ContactOut structured data
(industry, offices), enough for ICP but nothing a claim could be traced to.
TASK-197 then tried to generate copy for fifteen of them and all fifteen
failed at persona_angle, refused by check_evidence. ~240 credits spent on
contacts for whom copy cannot be written.

The fix: gate person-level enrichment on evidence availability. research.why()
is the existing computation - it returns None when evidence is sufficient, or
a reason when it is not. A record held by this condition lands in `held` state
with hold_reason enrich:evidence_required, recoverable by a later evidence
pass.

CLAUDE.md: "Company first. No paid person-level call before a company reaches
an explicit ICP verdict." The rule was honoured to the letter - there IS a
verdict - and defeated in substance, because icp_pass_with_uncertainty can be
reached from structured fields that carry no prose, and prose is what the copy
gate needs.
"""
import unittest

from src import enrich, holdreasons, icp, research, store


def company(rid="ev01"):
    rec = store.new_record(rid, "domains", "demo", "Evidence Co", f"{rid}.test")
    rec["state"] = "queued"
    return rec


def with_verdict(rec, status):
    """The minimum a record needs to carry an explicit verdict."""
    rec["qualification"] = {"inputs_fingerprint": "pinned-for-this-test",
                            "at": store.now(),
                            "verdict": {"icp_status": status}}
    return rec


def with_structured_only(rec):
    """ContactOut structured data: industry and offices, enough for ICP.
    For domains lane with no contacts, research.why() returns None (evidence
    is sufficient per the canonical computation). This test uses cold lane
    instead, where research.why() DOES return a reason when notable and
    specialties are both absent."""
    rec["lane"] = "cold"  # Cold lane requires notable or specialties for hook
    rec["company_facts"] = {
        "headcount_signal": 25,
        "industry": "Marketing & Advertising",
        "offices": ["London", "Bristol"],
        "name": "Evidence Co",
        "employees": "25",
    }
    # No notable, no specialties → research.why() returns NEED_HOOK_EVIDENCE
    return rec


def with_research(rec):
    """A record with usable research: a fact string check_evidence can trace
    claims to."""
    rec["lane"] = "cold"
    rec["company_facts"] = {
        "headcount_signal": 25,
        "industry": "Marketing & Advertising",
        "offices": ["London"],
        "name": "Evidence Co",
        "employees": "25",
        "specialties": ["B2B technology marketing"],  # Satisfies research.why()
    }
    rec["research"] = [
        {"fact": "Evidence Co specialises in B2B technology marketing",
         "field": "specialties",
         "source": "apify",
         "retrieved_at": store.now()},
    ]
    return rec


class EvidencePrecondition(unittest.TestCase):
    """A record may not reach a paid person-level call unless it has what
    check_evidence will later need."""

    def spent_on(self, rec, cap=1000):
        budget = enrich.Budget(cap=cap)
        done = enrich.enrich_record(rec, budget, live=False, log=[])
        return [op["call"] for op in done], budget.spent

    def person_calls(self, calls):
        return [c for c in calls if c in enrich.PERSON_LEVEL]

    def test_structured_only_no_person_credit(self):
        """Cold lane record with ICP verdict but no notable/specialties.
        research.why() returns NEED_HOOK_EVIDENCE, so person-level spend is
        refused."""
        rec = with_structured_only(with_verdict(company(), icp.QUALIFIED))
        self.assertIsNotNone(research.why(rec),
                             "test setup: research.why() should say evidence is needed")
        calls, spent = self.spent_on(rec)
        self.assertEqual(self.person_calls(calls), [],
                         "no person-level call should be planned")

    def test_with_research_proceeds(self):
        """A record WITH usable research still is enriched. A gate that
        refuses everything is not a fix."""
        rec = with_research(with_verdict(company(), icp.QUALIFIED))
        self.assertIsNone(research.why(rec),
                          "test setup: research.why() should say evidence is sufficient")
        calls, spent = self.spent_on(rec)
        self.assertIn("decision-makers", calls,
                      "person-level call should be planned")
        self.assertGreater(spent, 0, "credits should be spent")

    def test_outcome_holds_not_drops(self):
        """A record refused by the evidence gate is held, not dropped. It
        needs evidence, not rejection."""
        rec = with_structured_only(with_verdict(company(), icp.QUALIFIED))
        budget = enrich.Budget(cap=1000)
        enrich.enrich_record(rec, budget, live=False, log=[])
        self.assertEqual(rec["state"], "held",
                         "record should be held, not dropped or queued")
        self.assertEqual(rec.get("hold_reason"), "enrich:evidence_required")
        self.assertEqual(rec.get("hold_class"), holdreasons.ACTIONABLE)

    def test_research_why_is_the_gate(self):
        """The gate uses research.why(), the canonical computation. Per
        CLAUDE.md on canonical state."""
        rec = with_structured_only(with_verdict(company(), icp.QUALIFIED))
        need = research.why(rec)
        self.assertIsNotNone(need,
                             "research.why() should return a reason for cold lane without notable/specialties")
        self.assertIn("evidence", need.lower(),
                      "the reason should mention evidence")


class Counterfactual(unittest.TestCase):
    """Prove the counterfactual, both ways."""

    def test_structured_only_would_not_have_been_enriched(self):
        """Cold lane records without notable/specialties would NOT have been
        enriched under the new condition. research.why() returns a reason."""
        for i in range(5):
            rec = with_structured_only(with_verdict(company(f"ev{i:02d}"),
                                                     icp.QUALIFIED))
            budget = enrich.Budget(cap=1000)
            done = enrich.enrich_record(rec, budget, live=False, log=[])
            person_calls = [op["call"] for op in done
                           if op["call"] in enrich.PERSON_LEVEL]
            self.assertEqual(person_calls, [],
                             f"record {i} should not have person-level calls")

    def test_with_research_still_is(self):
        """A record WITH usable research still is enriched."""
        rec = with_research(with_verdict(company(), icp.QUALIFIED))
        budget = enrich.Budget(cap=1000)
        done = enrich.enrich_record(rec, budget, live=False, log=[])
        person_calls = [op["call"] for op in done
                       if op["call"] in enrich.PERSON_LEVEL]
        self.assertIn("decision-makers", person_calls,
                      "record with research should have person-level calls")


class ForecastMatchesExecution(unittest.TestCase):
    """The forecast must match execution. A plan that promises calls the gate
    will refuse is worse than no plan."""

    def test_plan_reflects_evidence_gate(self):
        """enrich.plan() should not promise person-level calls if the
        evidence gate will refuse them."""
        rec = with_structured_only(with_verdict(company(), icp.QUALIFIED))
        ops = enrich.plan(rec)
        calls = [op["call"] for op in ops]
        self.assertNotIn("decision-makers", calls,
                         "plan should not promise decision-makers")
        self.assertNotIn("aiark-people-search", calls,
                         "plan should not promise aiark-people-search")

    def test_plan_with_research_includes_person_calls(self):
        """enrich.plan() should include person-level calls if evidence is
        sufficient."""
        rec = with_research(with_verdict(company(), icp.QUALIFIED))
        ops = enrich.plan(rec)
        calls = [op["call"] for op in ops]
        self.assertIn("decision-makers", calls,
                      "plan should include decision-makers")


if __name__ == "__main__":
    unittest.main()
