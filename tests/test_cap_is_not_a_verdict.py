"""A cap is a fact about the wallet, not a finding about the company.

`enrich_record` ran to the end whether or not the budget had let it do
anything. With the cap reached it made no calls, found no contacts, and
`outcome` read that absence as a result: `("dropped", "no contact found at
this domain")`. `dropped` is in `run.TERMINAL` and outside `run()`'s default
states, so every record in the tail of a capped batch was retired for ever,
carrying a stated reason that nobody had checked and that was not true.

The tail of a batch is not a worse set of companies. It is the same set,
processed later, and the only thing that happened to it was arithmetic.
"""
import unittest

from src import enrich, icp, run, store


def company(rid="cap0001", qualified=False):
    rec = store.new_record(rid, "domains", "demo", "Capped Co",
                           f"{rid}.test")
    rec["state"] = "queued"
    if qualified:
        # Person-level enrichment is gated on a verdict. Where a test is about
        # what happens *after* the provider was allowed to look, the company
        # has to have been allowed to be looked at - otherwise the ICP gate
        # answers first and the cap never gets a turn.
        rec["qualification"] = {"inputs_fingerprint": "pinned-for-this-test",
                                "at": store.now(),
                                "verdict": {"icp_status": icp.QUALIFIED}}
    return rec


class ARefusedCallIsNotAResult(unittest.TestCase):

    def enriched_under(self, cap, qualified=False):
        rec = company(qualified=qualified)
        budget = enrich.Budget(cap=cap)
        enrich.enrich_record(rec, budget, live=False, log=[])
        return rec, budget

    def test_the_cap_refused_something(self):
        """Otherwise the rest of this file proves nothing."""
        _, budget = self.enriched_under(0)
        self.assertTrue(budget.refused, "no refusal, so nothing is under test")

    def test_a_capped_record_is_not_dropped(self):
        rec, _ = self.enriched_under(0)
        self.assertNotEqual(rec["state"], "dropped")

    def test_a_capped_record_carries_no_invented_reason(self):
        rec, _ = self.enriched_under(0)
        # `store.new_record` seeds the key as None, so the question is whether
        # anything filled it in, not whether it is present.
        self.assertIsNone(rec.get("drop_reason"))

    def test_a_capped_record_stays_where_the_runner_looks(self):
        rec, _ = self.enriched_under(0)
        self.assertIn(rec["state"], ("queued", "enriched"))
        self.assertTrue(run.needs(rec, "enrich"),
                        "the runner would never come back to this record")

    def test_the_record_says_the_cap_stopped_it(self):
        rec, _ = self.enriched_under(0)
        self.assertTrue(
            any(enrich.BUDGET_REFUSED in str(line) for line in rec.get("log") or []),
            "a record stopped by the cap must say so: %r" % (rec.get("log"),))

    # ------------------------------------------------- and still concludes

    def test_a_real_empty_result_is_still_a_drop(self):
        """The guard must not have made `dropped` unreachable.

        Nothing was refused here, so the absence of contacts is genuine and
        the old conclusion is the right one.
        """
        rec, budget = self.enriched_under(None, qualified=True)
        self.assertFalse(budget.refused)
        self.assertEqual(rec["state"], "dropped")
        self.assertEqual(rec["drop_reason"], "no contact found at this domain")


class TheStageDoesNotClaimItFinished(unittest.TestCase):
    """The second link. A record can be correct and still never be revisited
    if the stage says `done`, because `needs()` reads that and nothing else."""

    def setUp(self):
        self.real = enrich.enrich_record

        def spends_more_than_it_has(rec, budget, live=False, log=None,
                                    config=None, **kw):
            budget.charge(10 ** 6, f"{rec['id']}:decision-makers")
            return []

        enrich.enrich_record = spends_more_than_it_has
        self.addCleanup(setattr, enrich, "enrich_record", self.real)

    def test_a_cut_short_record_is_marked_partial(self):
        rec = company()
        run.stage_enrich([rec], spend=True, cap=1, notes=[])
        self.assertEqual(run.stages_of(rec)["enrich"]["status"], "partial")
        self.assertTrue(run.needs(rec, "enrich"))

    def test_a_finished_record_is_still_marked_done(self):
        enrich.enrich_record = lambda rec, budget, **kw: []
        rec = company(qualified=True)
        run.stage_enrich([rec], spend=True, cap=1000, notes=[])
        self.assertEqual(run.stages_of(rec)["enrich"]["status"], "done")
        self.assertFalse(run.needs(rec, "enrich"))


if __name__ == "__main__":
    unittest.main()
