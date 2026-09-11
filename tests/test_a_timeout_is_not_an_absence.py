#!/usr/bin/env python3
"""A provider that did not answer has not told us nobody is there.

FOUND IN A REAL RUN, and it cost a real prospect. `e-2.at` - an 87-person
Creative/Branding agency in DACH, QUALIFIED at tier C, score 49, medium
confidence, the best kind of record this funnel produces - was permanently
dropped with the reason "no contact found at this domain" after:

    enrich  decision-makers failed: TimeoutError: The read operation timed out
    enrich  ai ark: 0 kept
    dropped no contact found at this domain

Nothing had been established about that domain. A socket gave up, and the
system recorded a conclusion about somebody's business.

`dropped` is in `run.TERMINAL`, so the record was retired for good - no later
pass would look at it again. The company was not disqualified; it was lost.

`outcome()` already had this exact argument for the BUDGET case, in its own
docstring: "absence is exactly what a cap manufactures". A timeout manufactures
absence identically and there was no branch for it. `mx.py` states the general
rule one provider over: "A temporary resolver failure must never read as no
gateway found."
"""
import unittest
from unittest import mock

from src import dmplan, enrich, providers
from tests.base import QueueTest


def a_record(**over):
    rec = {"id": "e2", "client": "productive", "domain": "e-2.test",
           "company": "E2", "lane": "domains", "contacts": [],
           "company_facts": {"name": "E2", "employees": 87},
           "research": [], "events": [], "log": [], "state": "queued"}
    rec.update(over)
    return rec


class ATimeoutReturnsTheRecordRatherThanRetiringIt(unittest.TestCase):

    def test_a_failed_call_with_no_contacts_holds(self):
        state, reason = enrich.outcome(a_record(), failed=True,
                                       state=dmplan.QUALIFIED)
        self.assertNotEqual(state, "dropped")
        self.assertEqual(reason, enrich.PROVIDER_FAILED)

    def test_it_returns_to_the_state_the_record_arrived_in(self):
        """Which is already in the runner's retry set. No new state machine."""
        state, _ = enrich.outcome(a_record(state="enriched"), failed=True,
                                  state=dmplan.QUALIFIED)
        self.assertEqual(state, "enriched")

    def test_genuine_absence_still_drops(self):
        """The control. If a clean run with nobody there does not drop, this
        fix has turned a real finding into a permanent retry."""
        state, reason = enrich.outcome(a_record(), failed=False,
                                       state=dmplan.QUALIFIED)
        self.assertEqual(state, "dropped")
        self.assertEqual(reason, "no contact found at this domain")

    def test_a_failure_after_somebody_was_found_is_not_the_reason(self):
        """A later call failing does not explain contacts the record HAS.

        Without this the flag would hold every record that had any provider
        hiccup, including ones that succeeded at the thing that mattered.
        """
        rec = a_record(contacts=[{"key": "a", "email": "a@e-2.test",
                                  "verdict": "valid", "sendable": True}])
        state, _ = enrich.outcome(rec, failed=True, state=dmplan.QUALIFIED)
        self.assertEqual(state, "verified")

    def test_a_budget_refusal_still_reports_as_a_budget_refusal(self):
        """Two causes, two reasons. Conflating them would send the reader to
        the wrong fix: one is recoverable by spending, one by retrying."""
        state, reason = enrich.outcome(a_record(), refused=True, failed=True,
                                       state=dmplan.QUALIFIED)
        self.assertNotEqual(state, "dropped")
        self.assertEqual(reason, enrich.BUDGET_REFUSED)

    def test_a_rejected_company_still_drops_even_with_a_failure(self):
        """An ICP rejection is a decision, not an absence, so a coincidental
        provider failure must not rescue it into the retry set."""
        state, reason = enrich.outcome(a_record(), failed=True,
                                       state=dmplan.REJECTED)
        self.assertEqual(state, "dropped")
        self.assertEqual(reason, enrich.ICP_REJECTED)


class TheWaterfallReportsTheFailure(QueueTest):
    """End to end: a raising provider must reach `outcome` as a failure."""

    def test_a_raising_decision_makers_call_reaches_outcome_as_a_failure(self):
        """Asserts the REASON, not merely that the record survived.

        A first version asserted only `state != "dropped"` and passed even with
        the failure-tracking removed - because this fixture's ICP state is not
        what `icp_state` reads, so the record was being held for a completely
        different reason. A test that cannot tell those two apart is not
        testing the fix.
        """
        rec = a_record()
        from src.providers import contactout

        seen = {}
        real_outcome = enrich.outcome

        def spy(record, refused=False, state=None, failed=False):
            seen["failed"] = failed
            return real_outcome(record, refused=refused, state=state,
                                failed=failed)

        # `people_count` answers with a dict, not an int.
        with mock.patch.object(contactout, "people_count",
                               return_value={"profiles": 40}), \
             mock.patch.object(
                 contactout, "decision_makers",
                 side_effect=providers.ProviderError("timed out")), \
             mock.patch.object(enrich, "outcome", spy):
            enrich.enrich_record(rec, enrich.Budget(1000), live=True, log=[],
                                 config={})
        self.assertIs(seen.get("failed"), True,
                      "the timeout never reached the outcome decision")


if __name__ == "__main__":
    unittest.main()
