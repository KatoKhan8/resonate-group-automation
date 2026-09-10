#!/usr/bin/env python3
"""Re-running a stage over work already done must buy nothing again.

WHY THIS TEST EXISTS, and it is not a hypothetical. The 250-domain run on
2026-09-10 was killed at roughly forty-five records and restarted over all two
hundred. The waterfall shows 200 `company-information-from-domain` calls for
200 records and **zero records billed twice** - the restart reused the stored
facts rather than re-buying them.

That property held by construction and nothing asserted it. It is the property
an external reference implementation of the same idea gets wrong: that project
enqueues jobs with no identity, so two starts run concurrently, and its retry
path re-scrapes and leans on a database `skipDuplicates` whose unique index the
migrations never create. Correct-looking code, consumed by nothing, duplicating
paid work on every retry.

The cheapest way to not have that bug is to have a test that would notice it.

Two layers are checked, because they fail differently:

  - the RECORD layer, where `enrich_record` reuses a stored result. This is
    what actually saves the money.
  - the LEDGER layer, where a second pass must not append a second charge.
    A ledger that double-counts turns a real ceiling into half a ceiling.
"""
import unittest
from unittest import mock

from src import enrich, spendledger as sl
from tests.base import QueueTest


def a_record(**over):
    rec = {"id": "acme", "client": "productive", "domain": "acme.test",
           "company": "Acme", "lane": "domains", "contacts": [],
           "company_facts": {}, "research": [], "events": [], "log": []}
    rec.update(over)
    return rec


class TheSecondPassBuysNothingAgain(QueueTest):

    def calls_made(self, rec, cap=1000, config=None):
        """One enrichment pass. Returns the paid calls it decided to make."""
        budget = enrich.Budget(cap)
        done = enrich.enrich_record(rec, budget, live=True, log=[],
                                    config=config or {})
        return [op["call"] for op in done if op.get("cost")]

    def test_a_record_that_already_has_facts_is_not_looked_up_again(self):
        """The behaviour the killed-and-restarted run demonstrated.

        `company_facts` must carry EVERY field this call fills - which is
        `linkedin` and the profile fields, per `fieldplan.FIELDS` - because
        the guard is "would this call still tell us anything", not "does the
        record have some facts". A first version of this fixture set name,
        employees and industry, left `linkedin` unknown, and the call was
        correctly still owed. The system was right and the test was wrong.
        """
        enriched = a_record(company_facts={
            "name": "Acme", "employees": 40, "industry": "Design Services",
            "linkedin": "https://www.linkedin.com/company/acme",
            "description": "A design services studio.",
            "tagline": "Design, delivered."})
        second = self.calls_made(enriched)
        self.assertNotIn("company-information-from-domain", second,
                         "a company already enriched was bought again")

    def test_a_record_with_no_facts_is_looked_up(self):
        """The control. If this passes trivially the test above proves nothing."""
        with mock.patch.object(enrich, "COSTS", dict(enrich.COSTS)):
            first = self.calls_made(a_record())
        self.assertIn("company-information-from-domain", first)

    def test_the_ledger_does_not_double_charge_across_passes(self):
        """A durable ceiling is only a ceiling if it counts each charge once."""
        rec = a_record()
        self.calls_made(rec)
        after_first = sl.spent("productive")
        self.calls_made(rec)                      # same record, second pass
        after_second = sl.spent("productive")
        self.assertEqual(
            after_second, after_first,
            "the second pass charged the durable ledger again for work the "
            "first pass had already paid for")

    def test_a_dry_pass_never_charges_the_ledger_at_all(self):
        """Planning must not consume a ceiling. Checked here as well as in
        `test_a_cap_that_survives_the_run`, because this is the file somebody
        reads when they are asking about repeated runs."""
        rec = a_record()
        enrich.enrich_record(rec, enrich.Budget(1000), live=False, log=[],
                             config={})
        self.assertEqual(sl.spent("productive"), 0)


class TheLedgerCanAnswerWhoWasBoughtFor(QueueTest):
    """A ledger that cannot name the record cannot prove it did not re-buy.

    `waterfall` records per record and answers this today, which is how the
    250-run was audited. The spend ledger deliberately does not - it answers
    "what has this CLIENT spent", and a per-record column would invite it to
    become a second copy of the waterfall. This test pins that division so a
    future change makes it deliberately.
    """

    def test_the_spend_ledger_is_client_scoped_not_record_scoped(self):
        sl.record("productive", "contactout", "decision-makers", 10)
        row = sl.load()[-1]
        self.assertIn("client", row)
        self.assertNotIn("record_id", row)

    def test_the_waterfall_is_what_answers_per_record(self):
        rec = a_record()
        enrich.enrich_record(rec, enrich.Budget(1000), live=True, log=[],
                             config={})
        charged = [w for w in (rec.get("waterfall") or [])
                   if int((w or {}).get("expected_cost") or 0) > 0]
        self.assertTrue(charged, "nothing recorded what this record cost")
        for row in charged:
            self.assertIn("call", row)
            self.assertIn("provider", row)


if __name__ == "__main__":
    unittest.main()
