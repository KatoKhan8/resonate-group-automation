#!/usr/bin/env python3
"""Research for the ICP dimensions could never fire, and nothing said so.

THE ORDERING DEFECT. `research.why` returns NEED_ICP_EVIDENCE only when
`icp_status` is "review" or "unknown". That status is written by the QUALIFY
stage. `research.run` is called from `enrich_record`, and `STAGES` is
("enrich", "qualify", ...) - so at the moment research is offered the verdict
it depends on has not been computed, the status is None, the need is never
stated, and no scrape for that reason has ever happened in this build.

Measured on the 50-domain Productive pilot: 30 records for which `why` returns
NEED_ICP_EVIDENCE once a verdict exists, and zero scrape events on any of them.

It matters because six of the twelve ICP dimensions match phrases against prose
that structured providers do not return. Those companies could not score them
however good they were; `_confidence` lands in its LOW band; and LOW forces
`review` whatever the score. A pilot returns zero campaign-ready with nothing
visibly broken.

The fix threads a COMPUTED verdict rather than a STORED one. Computing is free.
Storing is not neutral: a first attempt persisted it mid-enrichment, which held
the record and stopped verification running at all.
"""
import unittest
from unittest import mock

from src import enrich, research


def a_company(**over):
    """A record shaped like the ones the pilot held: firmographics, no prose."""
    rec = {
        "id": "acme-test", "client": "productive", "domain": "acme.test",
        "company": "Acme", "lane": "domains", "contacts": [],
        "company_facts": {"name": "Acme", "employees": 60,
                          "industry": "Design Services"},
        "research": [], "events": [], "log": [],
    }
    rec.update(over)
    return rec


OPEN_VERDICT = {"icp_status": "unknown", "icp_tier": "REVIEW"}

CLOSED_VERDICT = {"icp_status": "rejected", "icp_tier": "NOT_ICP"}

# The client config shape `apify.settings` actually reads.
RESEARCH_ON = {"research": {"apify": {"enabled": True}}}


class TheNeedCannotBeStatedWithoutAVerdict(unittest.TestCase):

    def test_no_verdict_means_no_stated_need(self):
        """The defect itself, as a fact about the function."""
        self.assertIsNone(research.why(a_company()))

    def test_an_open_verdict_states_the_need(self):
        self.assertEqual(research.why(a_company(), verdict=OPEN_VERDICT),
                         research.NEED_ICP_EVIDENCE)

    def test_a_rejected_company_is_a_decision_not_a_gap(self):
        """Company-first: never spend on a company already ruled out."""
        self.assertIsNone(research.why(a_company(), verdict=CLOSED_VERDICT))

    def test_a_stored_verdict_still_works(self):
        """The parameter must not have replaced the original path."""
        rec = a_company(qualification={"verdict": OPEN_VERDICT})
        self.assertEqual(research.why(rec), research.NEED_ICP_EVIDENCE)

    def test_evidence_already_held_ends_the_question(self):
        rec = a_company(research=[{"fact": "x" * 80}])
        self.assertIsNone(research.why(rec, verdict=OPEN_VERDICT))

    def test_the_need_reaches_plan_and_run(self):
        """`plan` asks `why` again, so the verdict has to travel with it.

        Threading it into `why` alone would state a need that `plan` then
        immediately denied - the same disconnection one layer down.
        """
        planned = research.plan(a_company(), RESEARCH_ON,
                                verdict=OPEN_VERDICT)
        self.assertTrue(planned["planned"])
        self.assertEqual(planned["reason"], research.NEED_ICP_EVIDENCE)


class EnrichmentAsksTheFreeQuestionFirst(unittest.TestCase):
    """`qualify.company` spends nothing, which is what makes this legitimate."""

    def enrich(self, rec, cap=None, config=None):
        calls = {}

        def fake_company(record, conf, store_result=True):
            calls["store_result"] = store_result
            return {"verdict": OPEN_VERDICT}

        with mock.patch("src.qualify.company", fake_company), \
             mock.patch.object(research, "run") as ran:
            enrich.enrich_record(rec, enrich.Budget(cap), live=True,
                                 config=config or RESEARCH_ON)
        return calls, ran

    def test_the_verdict_is_computed_and_not_stored(self):
        """Storing it holds the record and verification never runs."""
        calls, _ = self.enrich(a_company())
        self.assertIs(calls.get("store_result"), False)

    def test_research_is_offered_with_that_verdict(self):
        _, ran = self.enrich(a_company())
        self.assertTrue(ran.called, "research was never offered")
        self.assertEqual(ran.call_args.kwargs.get("verdict"), OPEN_VERDICT)

    def test_a_company_that_already_states_a_need_is_not_re_qualified(self):
        """Don't pay the free question when the answer is already known."""
        rec = a_company(qualification={"verdict": OPEN_VERDICT})
        calls, ran = self.enrich(rec)
        self.assertEqual(calls, {}, "qualify ran when the need was already clear")
        self.assertTrue(ran.called)


class AZeroCapStartsNothingBillable(unittest.TestCase):
    """Making research reachable made the unpriced-call hole reachable too."""

    def test_a_cap_of_zero_refuses_the_actor(self):
        rec = a_company()
        with mock.patch("src.qualify.company",
                        return_value={"verdict": OPEN_VERDICT}), \
             mock.patch("src.providers.apify.start_run") as started:
            enrich.enrich_record(rec, enrich.Budget(0), live=True,
                                 config=RESEARCH_ON)
        self.assertFalse(started.called,
                         "a cap of zero started a billable Apify actor")


if __name__ == "__main__":
    unittest.main()
