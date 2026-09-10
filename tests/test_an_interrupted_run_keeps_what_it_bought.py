#!/usr/bin/env python3
"""A run that dies mid-stage used to discard every call it had paid for.

MEASURED, NOT HYPOTHESISED. On 2026-09-10 a 50-record enrichment run was
interrupted after ten minutes. `run.run` called `store.save(recs)` exactly
once, after every per-record stage had finished, so nothing had been written:
zero records differed from the pre-run backup. Apify's own monthly counter
showed $0.386 of compute had been spent producing that nothing, and the next
run would have spent it again because the records still looked untouched.

The cost of a checkpoint is one file write. The cost of not having one is
every provider call since the stage began. Those are not close.

This tests BEHAVIOUR - that work survives - rather than that a particular
function is called, so a different persistence strategy that also survives
would pass.
"""
import json
import os
import unittest
from unittest import mock

from src import run, store
from tests.base import QueueTest


class Interrupted(BaseException):
    """Stands in for the process being killed.

    A BaseException on purpose. The per-record handler is `except Exception`,
    which is correct - one bad record must not take the batch down - and it
    means an ordinary error is already survivable: the stage continues and
    reaches its final save. The loss this pins is the case that handler cannot
    catch, which is the case that actually happened: SIGTERM at ten minutes.
    """


def a_record(n):
    return {"id": "rec-%d" % n, "client": "productive", "domain": "d%d.test" % n,
            "company": "Co %d" % n, "lane": "domains", "contacts": [],
            "company_facts": {}, "research": [], "events": [], "log": [],
            "state": "queued", "stages": {}}


class WorkSurvivesAnInterruption(QueueTest):

    def setUp(self):
        super().setUp()
        store.save([a_record(n) for n in range(12)])

    def on_disk(self):
        return {r["id"]: r for r in store.load()}

    def enriched(self, rec, *a, **kw):
        """Stand-in for the waterfall: marks the record and costs 'money'."""
        self.paid.append(rec["id"])
        rec["company_facts"] = {"employees": 40}
        return []

    def test_records_enriched_before_the_crash_are_on_disk(self):
        self.paid = []

        def blow_up_on_the_eighth(rec, *a, **kw):
            if len(self.paid) >= 8:
                raise Interrupted("process died")
            return self.enriched(rec, *a, **kw)

        with mock.patch.object(run.enrich, "enrich_record",
                               blow_up_on_the_eighth):
            with self.assertRaises(Interrupted):
                run.run(stages=("enrich",), spend=True, cap=100)

        kept = [r for r in self.on_disk().values() if r.get("company_facts")]
        self.assertGreaterEqual(
            len(kept), 5,
            "a run that paid for 8 records persisted %d of them; every "
            "provider call before the crash was discarded" % len(kept))

    def test_nothing_is_lost_when_the_run_completes(self):
        """The checkpoint must not become the only save."""
        self.paid = []
        with mock.patch.object(run.enrich, "enrich_record", self.enriched):
            run.run(stages=("enrich",), spend=True, cap=100)
        kept = [r for r in self.on_disk().values() if r.get("company_facts")]
        self.assertEqual(len(kept), 12,
                         "the final save no longer covers the tail of the batch")

    def test_a_record_that_failed_still_keeps_what_it_bought(self):
        """The expensive case: half a waterfall, then an exception.

        The checkpoint runs after the per-record `except`, so a record that
        raised mid-enrichment still has its partial results written down.
        """
        self.paid = []

        def half_then_fail(rec, *a, **kw):
            self.paid.append(rec["id"])
            rec["company_facts"] = {"employees": 40}   # bought
            raise ValueError("provider returned nonsense")

        with mock.patch.object(run.enrich, "enrich_record", half_then_fail):
            run.run(stages=("enrich",), spend=True, cap=100)

        kept = [r for r in self.on_disk().values() if r.get("company_facts")]
        self.assertEqual(len(kept), 12)

    def test_the_facts_bought_before_the_crash_are_there_to_be_reused(self):
        """What the checkpoint is FOR, stated as the property it guarantees.

        NOT "the second run skips those records". It does not, and should not:
        they are marked `partial` because person-level work is still pending,
        so the stage correctly picks them up again. An earlier version of this
        test asserted the skip, and was wrong about which layer protects the
        money.

        The protection is that the FACTS are on disk, so `enrich_record` reuses
        a stored result instead of buying it again - "a stored result beats a
        call" is the first line of its own docstring. The checkpoint's job is
        to make sure there is a stored result to beat the call with.
        """
        self.paid = []

        def blow_up_on_the_eighth(rec, *a, **kw):
            if len(self.paid) >= 8:
                raise Interrupted("process died")
            return self.enriched(rec, *a, **kw)

        with mock.patch.object(run.enrich, "enrich_record",
                               blow_up_on_the_eighth):
            with self.assertRaises(Interrupted):
                run.run(stages=("enrich",), spend=True, cap=100)

        kept = {rid: r for rid, r in self.on_disk().items()
                if r.get("company_facts")}
        self.assertTrue(kept, "nothing survived the crash at all")
        for rid, rec in kept.items():
            self.assertEqual(rec["company_facts"], {"employees": 40},
                             "%s was persisted without what it bought" % rid)

    def test_the_checkpoint_interval_bounds_the_loss(self):
        """At most CHECKPOINT_EVERY records of work can be lost."""
        self.paid = []

        def blow_up_on_the_eleventh(rec, *a, **kw):
            if len(self.paid) >= 11:
                raise Interrupted("process died")
            return self.enriched(rec, *a, **kw)

        with mock.patch.object(run.enrich, "enrich_record",
                               blow_up_on_the_eleventh):
            with self.assertRaises(Interrupted):
                run.run(stages=("enrich",), spend=True, cap=100)

        kept = [r for r in self.on_disk().values() if r.get("company_facts")]
        lost = len(self.paid) - len(kept)
        self.assertLess(lost, run.CHECKPOINT_EVERY,
                        "paid for %d, kept %d: lost %d, which is more than "
                        "one checkpoint interval"
                        % (len(self.paid), len(kept), lost))


if __name__ == "__main__":
    unittest.main()
