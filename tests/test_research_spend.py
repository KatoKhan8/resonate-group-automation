"""An Apify run is real money and the spend audit could not see it.

`CLAUDE.md`: "Every paid call goes through enrich's `spend()`, which writes
the waterfall ledger. A provider call that skips it is invisible to the
spend audit, and an audit that reports clean because it watched nothing is
worse than none."

`research.run` skipped it. It took a `budget` parameter, the one caller
passed one, and the function never read it - so an actor run started with
no `PROVIDER_CALL_PLANNED` event, no ledger step and no charge. The
parameter is the tell: it made the call look bounded to anyone reading the
call site, which is why it survived.

Two things are asserted here and they are different questions. That the
run is *recorded* - it is, now, through the same closure every other paid
call uses. And that it is *bounded* - it is not, and this file says so
rather than leaving a reader to assume it. `COSTS["apify-research"]` is
zero because Apify bills compute units rather than credits, and a zero
charge is affordable at every cap. What limits a run is upstream and per
record: a stated need, the client's own `enabled`, `--live`, and
`max_items_per_run`.
"""
import unittest

from src import enrich, events, research, store, waterfall
from src.providers import apify

# `ProviderError` is deliberately not imported here. `tests/test_audit.py`
# reloads `src.providers` to prove no module reads a credential at import,
# and a reload mints a fresh exception class - so a name bound at module
# scope stops matching what the reloaded module raises. Go through the
# module (`providers.ProviderError`) if this file ever needs it, the way
# `src/poller.py` does.
from tests.base import QueueTest

CONFIG = {"research": {"apify": {"enabled": True}}}


class ResearchSpend(QueueTest):

    def seeded(self):
        """A record with a stated need and nothing structured to answer it."""
        rec = store.new_record("meridian", "cold", "demo", "Meridian",
                               "meridian.test")
        rec["hook"] = None
        rec["company_facts"] = {}
        store.save([rec])
        self.assertEqual(research.why(rec), research.NEED_HOOK_EVIDENCE,
                         "the fixture must actually need evidence")
        return rec

    def ledger(self, rec):
        return [s for s in waterfall.ledger(rec)
                if s.get("provider") == "apify"]

    def planned(self, rec):
        return [e for e in rec.get("events") or []
                if e.get("type") == events.PROVIDER_CALL_PLANNED
                and e.get("provider") == "apify"]


class ALiveRunIsRecorded(ResearchSpend):

    def spender(self, budget=None):
        """The real closure, taken from `enrich` rather than imitated.

        A stub here would prove the call happened and nothing about what it
        writes, and what it writes is the entire point.
        """
        rec = self.rec
        done = []
        budget = budget or enrich.Budget()

        def spend(call, why, provider="contactout", reason_code=None):
            cost = enrich.COSTS.get(call, 0)
            events.record(rec, events.PROVIDER_CALL_PLANNED, provider=provider,
                          operation=call, reason=reason_code or why[:80],
                          estimated_cost=cost)
            if not budget.charge(cost, f"{rec['id']}:{call}"):
                return False
            done.append(call)
            waterfall.record_step(rec, enrich.CALL_STAGE.get(call, "x"),
                                  provider, call, reason=reason_code or why,
                                  expected_cost=cost)
            return True

        self.done = done
        return spend

    def stub_apify(self, started=None):
        """Nothing reaches Apify. A live run in a test would be a real run."""
        calls = []

        def start_run(actor, urls, conf):
            calls.append(actor)
            return {"id": "run-1", "status": "RUNNING", "dataset_id": None}

        self.addCleanup(setattr, apify, "start_run", apify.start_run)
        self.addCleanup(setattr, apify, "wait_for", apify.wait_for)
        self.addCleanup(setattr, apify, "dataset_items", apify.dataset_items)
        apify.start_run = start_run
        apify.wait_for = lambda run_id, **kw: {
            "id": run_id, "status": "SUCCEEDED", "dataset_id": "ds-1"}
        apify.dataset_items = lambda dataset_id, limit: []
        self.started = calls
        return calls

    def setUp(self):
        super().setUp()
        self.rec = self.seeded()

    def test_a_live_run_writes_the_planned_event(self):
        self.stub_apify()
        research.run(self.rec, CONFIG, live=True, spend=self.spender())
        self.assertEqual(len(self.planned(self.rec)), 1)

    def test_a_live_run_writes_the_waterfall_step_the_audit_reads(self):
        """The defect. The ledger is what `spend audit` walks, and an actor
        run left no trace in it at all."""
        self.stub_apify()
        research.run(self.rec, CONFIG, live=True, spend=self.spender())
        steps = self.ledger(self.rec)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["call"], "apify-research")
        self.assertEqual(steps[0]["stage"], "company_research")
        # The ledger's own vocabulary, not `why`'s. `waterfall.require`
        # accepts only these words, and the specific need is carried on the
        # PROVIDER_CALL_PLANNED event beside it.
        self.assertEqual(steps[0]["reason"], enrich.PUBLIC_EVIDENCE_REQUIRED)
        self.assertEqual(self.planned(self.rec)[0]["reason"],
                         enrich.PUBLIC_EVIDENCE_REQUIRED)

    def test_the_specific_need_is_still_recorded_somewhere(self):
        """Generalising the reason for the ledger must not lose which step
        actually blocked - "we read their website" without "because there
        was no hook" is the kind of entry that answers nothing."""
        self.stub_apify()
        research.run(self.rec, CONFIG, live=True, spend=self.spender())
        scrapes = [e for e in self.rec["events"]
                   if e.get("type") == events.SCRAPE_PLANNED]
        self.assertEqual([e["reason"] for e in scrapes],
                         [research.NEED_HOOK_EVIDENCE])

    def test_the_actor_really_was_started(self):
        """So the two assertions above are about a run that happened."""
        self.stub_apify()
        research.run(self.rec, CONFIG, live=True, spend=self.spender())
        self.assertEqual(len(self.started), 1)

    def test_the_run_id_is_written_down_before_we_wait_on_it(self):
        """An actor nobody can reclaim is an actor that bills forever.

        The id lived in a local variable and nowhere else, and `wait_for`
        polls for as long as `POLL_ATTEMPTS` allows - so a process that
        died in there left a run billing compute units with its id held
        nowhere, an empty `rec["research"]`, and therefore the same stated
        need next run, which started a second one. `COSTS` prices this at
        zero because it is compute units rather than credits, so `--cap`
        could not have bounded the duplication either.
        """
        self.stub_apify()
        research.run(self.rec, CONFIG, live=True, spend=self.spender())
        started = [e for e in self.rec["events"]
                   if e.get("type") == events.SCRAPE_STARTED
                   and e.get("run_id")]
        self.assertTrue(started, "no event carries the actor run id")
        self.assertEqual(started[-1]["run_id"], "run-1")

    def test_a_dry_run_starts_nothing_and_charges_nothing(self):
        self.stub_apify()
        research.run(self.rec, CONFIG, live=False, spend=self.spender())
        self.assertEqual(self.started, [])
        self.assertEqual(self.ledger(self.rec), [])

    def test_a_run_with_no_ledger_is_refused_rather_than_run(self):
        """Fail closed. The one caller threads the closure through; a second
        caller that forgot would otherwise put the run back out of sight,
        and invisible spend is the failure this guards."""
        self.stub_apify()
        out = research.run(self.rec, CONFIG, live=True)
        self.assertEqual(out, [])
        self.assertEqual(self.started, [],
                         "an unledgered run reached the provider")
        failures = [e for e in self.rec["events"]
                    if e.get("type") == events.SCRAPE_FAILED]
        self.assertTrue(failures, "it must say why, not fail silently")
        self.assertIn("ledger", failures[-1]["reason"])

    def test_a_refusal_upstream_still_starts_nothing(self):
        """`spend` returning False stops the run before the provider."""
        self.stub_apify()
        research.run(self.rec, CONFIG, live=True,
                     spend=lambda *a, **kw: False)
        self.assertEqual(self.started, [])


class WhatDoesNotBoundIt(ResearchSpend):
    """Stated, because a ledger entry looks like a limit and is not one."""

    def test_an_actor_run_costs_zero_credits_by_construction(self):
        self.assertEqual(enrich.COSTS["apify-research"], 0)

    def test_so_the_credit_cap_never_refuses_one(self):
        budget = enrich.Budget(cap=1)
        budget.charge(1, "something else")
        self.assertEqual(budget.remaining(), 0)
        self.assertTrue(budget.affordable(enrich.COSTS["apify-research"]),
                        "a zero charge is affordable at an exhausted cap - "
                        "the ledger records the run, it does not bound it")

    def test_what_does_bound_it_is_the_client_switch(self):
        rec = self.seeded()
        proposal = research.plan(rec, {})
        self.assertFalse(proposal["planned"])
        self.assertIn("not enabled", proposal["why_not"])

    def test_and_a_stated_need(self):
        rec = self.seeded()
        rec["company_facts"] = {"specialties": ["SEO"], "notable": "x"}
        self.assertIsNone(research.why(rec))
        self.assertFalse(research.plan(rec, CONFIG)["planned"])


if __name__ == "__main__":
    unittest.main()
