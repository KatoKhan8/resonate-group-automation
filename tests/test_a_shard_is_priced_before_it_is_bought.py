#!/usr/bin/env python3
"""Three numbers an operator must have BEFORE a shard starts, and the two
this repository cannot currently produce.

## What a preflight has to answer

    ESTIMATED COST FOR NEXT SHARD   what N records are about to cost
    CURRENT DAILY SPEND             what today has already committed
    REMAINING BUDGET                the ceiling minus that

Every input to the first two already exists. `enrich.plan` decides what a
record needs, `enrich.exposure` separates expected from worst case,
`verification.plan` prices the address work inside it, and
`spendledger.spent` is the durable running total. Nothing composes them, so
the answer is obtainable and nobody can obtain it. `preflight()` below is the
composition, written here rather than as a new module so it can be lifted
into `src/` unchanged once an owner exists.

The third number does not exist at all. `spendledger.caps` reads the client
config's `budget:` block and `config/clients/productive.yaml` has none, so
all four ceilings are `None`, `None` means unlimited, and
`spendledger.check` cannot refuse anything. REMAINING BUDGET is therefore
UNBOUNDED for the only real client, and this file asserts that rather than
reporting a number it cannot support.

## Why the estimate is a floor and says so

Two of the estimate's own line items never reach the durable ledger:

  - Verification. `verification.verify` performs one to three paid calls per
    address and writes the waterfall step, never `spendledger.record`. The
    money is spent, the ledger does not see it, and `check()` therefore
    cannot refuse it. Proven below against a stubbed verifier, so the
    assertion is about execution rather than about the text of the source.

  - Apify research. `enrich.COSTS["apify-research"]` is 0 because Apify bills
    in compute units the credit cap cannot read. Zero in a credit estimate is
    correct and is not free.

So `preflight()` returns `ledgered` and `unledgered` separately. A single
total would present a floor as a forecast, and a ceiling sized against a
floor is not a ceiling.

## And the person-level second pass

`run.STAGES` is enrich, then qualify. A domain arrives with no ICP verdict,
so the first pass is company-level only - one credit - and `decision-makers`
becomes payable on the NEXT pass, after qualification has produced a verdict.
A shard estimate that reported only the first pass would understate the
second by the whole person-level bill, so `preflight()` reports the count of
records whose person-level spend is deferred rather than folding a guessed
qualification rate into the headline number.
"""
import unittest
from unittest import mock

from src import clients, enrich, spendledger, store, verification
from tests.base import QueueTest


# Calls performed by `verification.verify`, in that module's own vocabulary
# rather than by matching on names. Derived from the two tables verification
# publishes, so a fourth verifier added there arrives in this set already.
UNLEDGERED_CALLS = ({f"{p}-verify" for p in verification.COSTS}
                    | set(verification.CALL_NAMES.values()))


def preflight(records, config, client, shard=None, now=None):
    """The three numbers, from existing functions only. Spends nothing.

    `records` is the shard already selected - which records go in a shard is
    the caller's decision and not a spend question.
    """
    shard = records if shard is None else records[:shard]
    expected = maximum = ledgered = unledgered = 0
    unpriced, deferred = [], 0
    for rec in shard:
        ops = enrich.plan(rec, config)
        exposure = enrich.exposure(ops)
        expected += exposure["expected"]
        maximum += exposure["maximum"]
        for op in ops:
            if op.get("conditional"):
                continue
            if op["call"] in UNLEDGERED_CALLS:
                unledgered += op["cost"]
            else:
                ledgered += op["cost"]
        unpriced += [op["call"] for op in ops
                     if op["call"] in enrich.UNPRICED]
        if enrich.person_level_pending(rec):
            deferred += 1

    day = spendledger.today(now)
    ceilings = spendledger.caps(config)
    per_day = ceilings.get("per_day")
    spent_today = spendledger.spent(client, day=day)
    remaining = None if per_day is None else per_day - spent_today

    if remaining is None:
        verdict = "UNBOUNDED"
    elif expected > remaining:
        verdict = "REFUSE"
    else:
        verdict = "WITHIN_CEILING"

    return {
        "client": client,
        "day": day,
        "records": len(shard),
        # ESTIMATED COST FOR NEXT SHARD
        "estimated_expected": expected,
        "estimated_maximum": maximum,
        "estimated_ledgered": ledgered,
        "estimated_unledgered": unledgered,
        "unpriced_calls": sorted(set(unpriced)),
        # CURRENT DAILY SPEND
        "spent_today": spent_today,
        "spent_total": spendledger.spent(client),
        # REMAINING BUDGET
        "ceilings": ceilings,
        "remaining": remaining,
        "bounded": per_day is not None,
        "verdict": verdict,
        "person_level_deferred": deferred,
    }


def a_domain(n, **over):
    """A record as ingest leaves it: a domain, no facts, no verdict."""
    rec = {"id": f"d{n}", "client": "productive", "domain": f"d{n}.invalid",
           "company": f"Company {n}", "lane": "domains", "contacts": [],
           "company_facts": {}, "research": [], "events": [], "log": [],
           "state": "queued", "waterfall": []}
    rec.update(over)
    return rec


def a_qualified_domain(n, addresses=1):
    """A record past the ICP gate with addresses waiting on verification."""
    return a_domain(
        n,
        company_facts={"headcount_signal": 12},
        qualification={"verdict": {"icp_status": "qualified"},
                       "persona_plan": {"max_contacts_to_enrich": addresses,
                                        "target_titles": ["founder"]}},
        contacts=[{"key": f"p{i}", "email": f"p{i}@d{n}.invalid",
                   "title": "Founder", "name": f"Person {i}"}
                  for i in range(addresses)])


class ThePreflightProducesTheThreeNumbers(QueueTest):

    def setUp(self):
        super().setUp()
        self.config = {}                   # no budget block, like the real one

    def test_a_shard_of_fresh_domains_is_priced_before_anything_is_called(self):
        """One company-information credit each. people-count is free."""
        out = preflight([a_domain(i) for i in range(250)], self.config,
                        "productive")
        self.assertEqual(out["records"], 250)
        self.assertEqual(out["estimated_expected"], 250)
        self.assertEqual(out["estimated_ledgered"], 250)
        self.assertEqual(out["estimated_unledgered"], 0)

    def test_the_estimate_is_produced_without_a_provider_call(self):
        """The whole point: this runs before any paid work starts."""
        with mock.patch("src.providers.contactout.call") as called:
            preflight([a_domain(i) for i in range(10)], self.config,
                      "productive")
        called.assert_not_called()

    def test_a_shard_size_bounds_the_estimate(self):
        records = [a_domain(i) for i in range(250)]
        self.assertEqual(
            preflight(records, self.config, "productive", shard=50)
            ["estimated_expected"], 50)

    def test_current_daily_spend_comes_from_the_durable_ledger(self):
        spendledger.record("productive", "contactout",
                           "company-information-from-domain", 40)
        spendledger.record("productive", "contactout", "decision-makers", 10)
        out = preflight([a_domain(1)], self.config, "productive")
        self.assertEqual(out["spent_today"], 50)
        self.assertEqual(out["spent_total"], 50)

    def test_another_clients_spend_is_not_this_clients_daily_total(self):
        spendledger.record("someone-else", "contactout", "decision-makers", 90)
        self.assertEqual(
            preflight([a_domain(1)], self.config, "productive")["spent_today"],
            0)

    def test_expected_and_maximum_are_not_reported_as_one_number(self):
        """A conditional call is exposure, not forecast."""
        out = preflight([a_qualified_domain(1)], self.config, "productive")
        self.assertGreater(out["estimated_maximum"], out["estimated_expected"])


class RemainingBudgetIsUnobtainableForTheRealClient(QueueTest):
    """Not an estimate problem. There is no ceiling to subtract from."""

    def test_the_shipped_client_config_declares_no_ceiling(self):
        caps = spendledger.caps(clients.load("productive"))
        self.assertEqual(caps, dict.fromkeys(spendledger.SCOPES),
                         "productive.yaml has grown a budget: block - update "
                         "this test and the preflight can report a real "
                         "remaining budget")

    def test_so_the_preflight_reports_unbounded_rather_than_a_number(self):
        out = preflight([a_domain(i) for i in range(250)],
                        clients.load("productive"), "productive")
        self.assertIsNone(out["remaining"])
        self.assertFalse(out["bounded"])
        self.assertEqual(out["verdict"], "UNBOUNDED")

    def test_the_durable_check_cannot_refuse_anything_without_a_block(self):
        """`check()` is the guard. With no ceiling it is a pass-through."""
        self.assertTrue(spendledger.check("productive",
                                          clients.load("productive"),
                                          10 ** 9))

    def test_one_declared_ceiling_is_all_it_takes_to_get_a_refusal(self):
        """The minimal fix, proven: a per_day key turns the guard on."""
        config = {"budget": {"per_day": 300}}
        spendledger.record("productive", "contactout", "decision-makers", 280)
        out = preflight([a_domain(i) for i in range(250)], config,
                        "productive")
        self.assertEqual(out["remaining"], 20)
        self.assertEqual(out["verdict"], "REFUSE")
        with self.assertRaises(spendledger.BudgetExceeded):
            spendledger.check("productive", config, 250)


class TheEstimateSaysWhichPartTheLedgerWillNotSee(QueueTest):

    def test_verification_is_estimated_and_flagged_as_unledgered(self):
        out = preflight([a_qualified_domain(1, addresses=2)], {},
                        "productive")
        self.assertGreater(out["estimated_unledgered"], 0)
        self.assertEqual(out["estimated_expected"],
                         out["estimated_ledgered"] + out["estimated_unledgered"])

    def test_verification_really_does_not_reach_the_durable_ledger(self):
        """Execution, not source text. A live verify with a stubbed verifier
        writes its waterfall step and nothing to the spend ledger."""
        rec = a_qualified_domain(1, addresses=1)
        contact = rec["contacts"][0]
        before = len(spendledger.load())
        answer = verification.result("contactout", verification.S_VALID,
                                     contact["email"])
        with mock.patch.object(verification, "call", return_value=answer):
            verification.verify(contact, verification.DEFAULT_POLICY,
                                live=True, rec=rec,
                                budget=enrich.Budget(100))
        self.assertEqual(len(spendledger.load()), before,
                         "verification now reaches spendledger - delete "
                         "UNLEDGERED_CALLS and fold it into the headline")
        self.assertTrue([s for s in rec.get("waterfall") or []
                         if s.get("call") in UNLEDGERED_CALLS],
                        "the waterfall step is the only place this spend is "
                        "recorded at all")

    def test_an_unpriced_call_is_named_rather_than_counted_as_free(self):
        self.assertIn("apify-research", enrich.UNPRICED)
        self.assertEqual(enrich.COSTS["apify-research"], 0)


class ThePersonLevelBillIsDeferredNotAbsent(QueueTest):

    def test_a_fresh_domain_defers_its_person_level_spend_to_a_later_pass(self):
        """No verdict yet, so `decision-makers` is not in this estimate."""
        out = preflight([a_domain(i) for i in range(100)], {}, "productive")
        self.assertEqual(out["person_level_deferred"], 100)
        self.assertEqual(out["estimated_expected"], 100)

    def test_a_qualified_domain_with_no_address_prices_decision_makers(self):
        rec = a_domain(1, company_facts={"headcount_signal": 12},
                       qualification={"verdict":
                                      {"icp_status": "qualified"}})
        out = preflight([rec], {}, "productive")
        self.assertEqual(out["person_level_deferred"], 0)
        self.assertGreaterEqual(out["estimated_expected"],
                                enrich.COSTS["decision-makers"])

    def test_a_rejected_domain_is_not_reported_as_deferred_work(self):
        """Rejected is final. Counting it as pending is a queue that never
        empties and a forecast that never comes true."""
        rec = a_domain(1, company_facts={"headcount_signal": 12},
                       qualification={"verdict":
                                      {"icp_status": "rejected"}})
        self.assertEqual(preflight([rec], {}, "productive")
                         ["person_level_deferred"], 0)


class TheEstimateMatchesWhatALiveRunActuallyCommits(QueueTest):
    """The estimator is worthless if it disagrees with execution. Same
    records, same config: what `preflight()` promised is what the run charged.
    """

    def one_pass(self, records, cap):
        budget = enrich.Budget(cap)
        answer = {"companies": {}, "profiles": 0}
        with mock.patch("src.providers.contactout.people_count",
                        return_value={"profiles": 7}), \
             mock.patch("src.providers.contactout.company_info",
                        return_value=answer):
            for rec in records:
                enrich.enrich_record(rec, budget, live=True, log=[], config={})
        return budget.spent

    def test_the_estimate_equals_the_in_memory_charge_for_the_same_shard(self):
        records = [a_domain(i) for i in range(25)]
        estimate = preflight(records, {}, "productive")["estimated_expected"]
        self.assertEqual(self.one_pass(records, cap=10 ** 6), estimate)

    def test_the_estimate_equals_the_durable_ledger_for_the_same_shard(self):
        """The ledgered half of the estimate, against what the run appended."""
        records = [a_domain(i) for i in range(25)]
        out = preflight(records, {}, "productive")
        self.one_pass(records, cap=10 ** 6)
        self.assertEqual(spendledger.spent("productive"),
                         out["estimated_ledgered"])


if __name__ == "__main__":
    unittest.main()
