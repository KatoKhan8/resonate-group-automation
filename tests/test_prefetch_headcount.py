"""`prefetch_headcount` is the first caller of `gather`.

The acceptance test is LEDGER EQUALITY: run the same fixture cohort serial
and at K=8, and the waterfall ledger must be byte-identical - same steps,
same order, same reasons. Not "same count" - the ORDER is what
`costs.reconcile()` reads.

No network, no real PII, no ContactOut called. Every test uses fake
providers with deterministic answers.
"""
import copy
import json
import time
import unittest
from unittest import mock

from src import enrich, gather as gather_mod, store, waterfall
from src.gather import Outcome, prefetch_headcount
from tests.base import QueueTest


# ---------------------------------------------------------------- helpers

def _make_rec(rec_id, domain, profiles=None):
    """A record in the shape `prefetch_headcount` needs.

    If `profiles` is given, the record already carries a
    `headcount_signal` and the prefetch must skip it.
    """
    rec = {"id": rec_id, "domain": domain, "state": "queued",
           "company_facts": {}}
    if profiles is not None:
        rec["company_facts"] = {"headcount_signal": profiles}
    return rec


def _fake_people_count(domain):
    """Deterministic, distinguishable answers per domain.

    Each domain gets a different count, so a prefetch that puts company
    A's count on company B fails an explicit assertion rather than
    looking correct by coincidence.
    """
    table = {
        "alpha.test": {"profiles": 10},
        "beta.test":  {"profiles": 20},
        "gamma.test": {"profiles": 30},
        "delta.test": {"profiles": 40},
        "epsilon.test": {"profiles": 50},
    }
    return table.get(domain, {"profiles": 0})


def _fake_spend_factory(spend_log=None):
    """A `spend` bridge that records every call and accepts everything.

    Accepts the `rec=` keyword `prefetch_headcount` passes, and ignores
    it - the test fake does not need the record.
    """
    if spend_log is None:
        spend_log = []

    def _spend(call, why, provider="contactout", rec=None, **_kw):
        spend_log.append((call, why, provider))
        return True

    return _spend, spend_log


def _bridge_spend(budget, notes):
    """A `spend` bridge that charges a real Budget and writes the
    waterfall step on the record passed via `rec=`.

    This is the same shape as the production bridge in `enrich.run`.
    """
    def _spend(call, why, provider="contactout", rec=None, **_kw):
        cost = enrich.COSTS.get(call, 0)
        if not budget.charge(cost, f"{rec['id']}:{call}", call=call):
            notes.append(f"{rec['id']}: cap reached, skipped {call}")
            return False
        waterfall.record_step(
            rec, enrich.CALL_STAGE.get(call, "people_discovery"),
            provider, call, reason=why, expected_cost=cost,
        )
        return True
    return _spend


def _ledger(rec):
    """The waterfall ledger, stripped of the `at` timestamp so two runs
    at different wall-clock times still compare byte-identical."""
    return [{k: v for k, v in row.items() if k != "at"}
            for row in (rec.get("waterfall") or [])]


def _run_serial(records, people_count, budget, notes, timeout=None):
    """Walk one record at a time, as `enrich_record` does for the
    people-count step. Same spend bridge, same waterfall writer, no
    concurrency - the baseline the prefetch must match.

    `timeout` is honoured with a per-call deadline, so a slow call in
    the serial baseline produces the same `timed_out` outcome the
    concurrent path would. Without this, a 1-second sleep in the
    baseline would succeed while the concurrent path (with a 50ms
    timeout) would time out, and the two runs would disagree for the
    wrong reason.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    spend = _bridge_spend(budget, notes)
    for rec in records:
        facts = rec.get("company_facts") or {}
        if "headcount_signal" in facts:
            continue
        approved = spend("people-count",
                         "confirm the domain is staffed",
                         "contactout", rec=rec)
        if not approved:
            continue
        if timeout is not None:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(people_count, domain=rec["domain"])
                try:
                    count = fut.result(timeout=timeout)
                except TimeoutError:
                    continue
                except Exception:
                    rec.setdefault("failures", []).append("people-count")
                    continue
        else:
            try:
                count = people_count(domain=rec["domain"])
            except Exception:
                rec.setdefault("failures", []).append("people-count")
                continue
        facts = dict(facts)
        facts["headcount_signal"] = count.get("profiles")
        rec["company_facts"] = facts


# ---------------------------------------------------------------- tests

class LedgerEquality(QueueTest):
    """The acceptance test: serial vs K=8, byte-identical ledger."""

    def test_ledger_is_byte_identical_serial_vs_k8(self):
        """Same steps, same order, same reasons. Not 'same count'."""
        # Two cohorts that are equal in every way, including the wall-
        # clock timestamp the waterfall writes on each step.
        with mock.patch.object(waterfall.store, "now",
                               return_value="2026-09-18T00:00:00+00:00"):
            serial_recs = [
                _make_rec("r1", "alpha.test"),
                _make_rec("r2", "beta.test"),
                _make_rec("r3", "gamma.test"),
                _make_rec("r4", "delta.test"),
            ]
            serial_budget = enrich.Budget(cap=None)
            _run_serial(serial_recs, _fake_people_count,
                        serial_budget, [])

            concurrent_recs = [
                _make_rec("r1", "alpha.test"),
                _make_rec("r2", "beta.test"),
                _make_rec("r3", "gamma.test"),
                _make_rec("r4", "delta.test"),
            ]
            concurrent_budget = enrich.Budget(cap=None)
            prefetch_headcount(
                concurrent_recs, _fake_people_count,
                _bridge_spend(concurrent_budget, []),
                k=8,
            )

        serial_ledgers = [_ledger(r) for r in serial_recs]
        concurrent_ledgers = [_ledger(r) for r in concurrent_recs]

        # The whole shape, serialised, byte-identical.
        self.assertEqual(
            json.dumps(serial_ledgers, sort_keys=True),
            json.dumps(concurrent_ledgers, sort_keys=True),
        )

        # And per-record: same number of steps, same call, same reason.
        for s, c in zip(serial_recs, concurrent_recs):
            self.assertEqual(_ledger(s), _ledger(c))
            self.assertEqual(
                (s.get("company_facts") or {}).get("headcount_signal"),
                (c.get("company_facts") or {}).get("headcount_signal"),
            )

    def test_ledger_equality_holds_at_k1(self):
        """k=1 goes through the same gather path as k=8. The ledger must
        still match a pure serial run."""
        with mock.patch.object(waterfall.store, "now",
                               return_value="2026-09-18T00:00:00+00:00"):
            serial_recs = [_make_rec(f"r{i}", f"d{i}.test")
                           for i in range(5)]
            serial_budget = enrich.Budget(cap=None)
            _run_serial(serial_recs, _fake_people_count,
                        serial_budget, [])

            concurrent_recs = [_make_rec(f"r{i}", f"d{i}.test")
                               for i in range(5)]
            concurrent_budget = enrich.Budget(cap=None)
            prefetch_headcount(
                concurrent_recs, _fake_people_count,
                _bridge_spend(concurrent_budget, []),
                k=1,
            )

        for s, c in zip(serial_recs, concurrent_recs):
            self.assertEqual(_ledger(s), _ledger(c))

    def test_ledger_equality_holds_across_twenty_runs(self):
        """Twenty concurrent runs at K=8, every one byte-identical to the
        serial baseline. Determinism under scheduling variance."""
        with mock.patch.object(waterfall.store, "now",
                               return_value="2026-09-18T00:00:00+00:00"):
            serial_recs = [
                _make_rec("r1", "alpha.test"),
                _make_rec("r2", "beta.test"),
                _make_rec("r3", "gamma.test"),
            ]
            serial_budget = enrich.Budget(cap=None)
            _run_serial(serial_recs, _fake_people_count,
                        serial_budget, [])
            baseline = [json.dumps(_ledger(r), sort_keys=True)
                        for r in serial_recs]

            for run in range(20):
                concurrent_recs = [
                    _make_rec("r1", "alpha.test"),
                    _make_rec("r2", "beta.test"),
                    _make_rec("r3", "gamma.test"),
                ]
                concurrent_budget = enrich.Budget(cap=None)
                prefetch_headcount(
                    concurrent_recs, _fake_people_count,
                    _bridge_spend(concurrent_budget, []),
                    k=8,
                )
                this_run = [json.dumps(_ledger(r), sort_keys=True)
                            for r in concurrent_recs]
                self.assertEqual(this_run, baseline,
                                 f"run {run + 1} differed from baseline")


class ResultsLandOnTheRightRecords(QueueTest):
    """A prefetch that puts company A's count on company B is the worst
    possible outcome. Input-order apply is what prevents it."""

    def test_each_domains_count_lands_on_that_domain(self):
        recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
            _make_rec("r4", "delta.test"),
            _make_rec("r5", "epsilon.test"),
        ]
        budget = enrich.Budget(cap=None)
        prefetch_headcount(
            recs, _fake_people_count,
            _bridge_spend(budget, []),
            k=8,
        )

        self.assertEqual(
            [r["company_facts"]["headcount_signal"] for r in recs],
            [10, 20, 30, 40, 50],
        )

    def test_even_when_completion_order_differs_from_input_order(self):
        """The gather returns results in INPUT order regardless of
        completion order. Assert that the apply sees them in input order
        even when the calls complete in reverse."""
        call_order = []

        def slow_first(domain):
            # Reverse sleep: alpha sleeps longest, epsilon does not sleep.
            # Completion order is epsilon, delta, gamma, beta, alpha.
            delays = {"alpha.test": 0.10, "beta.test": 0.08,
                      "gamma.test": 0.05, "delta.test": 0.02,
                      "epsilon.test": 0.0}
            time.sleep(delays.get(domain, 0))
            call_order.append(domain)
            return _fake_people_count(domain)

        recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
            _make_rec("r4", "delta.test"),
            _make_rec("r5", "epsilon.test"),
        ]
        budget = enrich.Budget(cap=None)
        prefetch_headcount(
            recs, slow_first, _bridge_spend(budget, []), k=8,
        )

        # Completion order was reverse of input.
        self.assertEqual(call_order,
                         ["epsilon.test", "delta.test", "gamma.test",
                          "beta.test", "alpha.test"])
        # But results landed in input order.
        self.assertEqual(
            [r["company_facts"]["headcount_signal"] for r in recs],
            [10, 20, 30, 40, 50],
        )


class BreakProof(QueueTest):
    """Shuffle the apply order deliberately and confirm the ledger
    equality test fails, and fails for that reason."""

    def test_shuffled_apply_breaks_ledger_equality(self):
        """A gather that returns results in the wrong order produces
        headcount_signal values on the wrong records. The equality test
        reads the aggregate of (record, headcount_signal) pairs; a
        scramble changes that aggregate even when every per-record
        waterfall looks structurally identical."""
        real_gather = gather_mod.gather

        def reversed_gather(items, call, **kw):
            outcomes = real_gather(items, call, **kw)
            return list(reversed(outcomes))

        serial_recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
            _make_rec("r4", "delta.test"),
        ]
        serial_budget = enrich.Budget(cap=None)
        _run_serial(serial_recs, _fake_people_count, serial_budget, [])

        scrambled_recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
            _make_rec("r4", "delta.test"),
        ]
        scrambled_budget = enrich.Budget(cap=None)
        with mock.patch.object(gather_mod, "gather", reversed_gather):
            prefetch_headcount(
                scrambled_recs, _fake_people_count,
                _bridge_spend(scrambled_budget, []),
                k=8,
            )

        # The acceptance test: the aggregate of (record id, headcount
        # signal) pairs. Serial is the baseline; scramble must differ.
        serial_pairs = [(r["id"], r["company_facts"]["headcount_signal"])
                        for r in serial_recs]
        scrambled_pairs = [(r["id"], r["company_facts"]["headcount_signal"])
                           for r in scrambled_recs]
        self.assertNotEqual(
            serial_pairs, scrambled_pairs,
            "ledger equality must fail when the apply order is wrong",
        )

        # And it fails for the right reason: the headcount_signal values
        # are on the wrong records, not just in a different order.
        expected = [10, 20, 30, 40]
        scrambled_values = [r["company_facts"]["headcount_signal"]
                            for r in scrambled_recs]
        self.assertNotEqual(scrambled_values, expected,
                            "scrambled apply must put the wrong count on "
                            "at least one record")

    def test_shuffled_apply_breaks_equality_even_when_ok_values_collide(self):
        """Even when every SUCCESSFUL call returns the same value, a
        shuffled apply is caught because the TIMEOUT lands on a
        different record. The equality test reads the aggregate of
        (record, outcome) pairs: a timeout on r2 vs a timeout on r3
        produces different aggregates even when the ok values are
        indistinguishable.

        This is the same property that catches a scramble on a paid
        route: the pattern of successes and failures across records is
        part of the ledger, not just the values that landed.
        """
        real_gather = gather_mod.gather

        def reversed_gather(items, call, **kw):
            return list(reversed(real_gather(items, call, **kw)))

        # r2's call times out; the others succeed with the SAME value.
        # Reversed, the timeout lands on r3 instead of r2.
        def mixed(domain):
            if domain == "beta.test":
                time.sleep(1.0)
            return {"profiles": 7}

        serial_recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
            _make_rec("r4", "delta.test"),
        ]
        serial_budget = enrich.Budget(cap=None)
        _run_serial(serial_recs, mixed, serial_budget, [], timeout=0.05)

        scrambled_recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
            _make_rec("r4", "delta.test"),
        ]
        scrambled_budget = enrich.Budget(cap=None)
        with mock.patch.object(gather_mod, "gather", reversed_gather):
            prefetch_headcount(
                scrambled_recs, mixed,
                _bridge_spend(scrambled_budget, []),
                k=8, timeout=0.05,
            )

        # The ok values are all 7 - indistinguishable.
        for r in serial_recs:
            if "headcount_signal" in r["company_facts"]:
                self.assertEqual(r["company_facts"]["headcount_signal"], 7)
        for r in scrambled_recs:
            if "headcount_signal" in r["company_facts"]:
                self.assertEqual(r["company_facts"]["headcount_signal"], 7)

        # But the PATTERN of which record got the timeout differs.
        # Serial: r2 timed out (no headcount_signal).
        # Scrambled: r3 timed out (no headcount_signal).
        serial_missing = [r["id"] for r in serial_recs
                          if "headcount_signal" not in r["company_facts"]]
        scrambled_missing = [r["id"] for r in scrambled_recs
                             if "headcount_signal"
                             not in r["company_facts"]]
        self.assertNotEqual(
            serial_missing, scrambled_missing,
            "a shuffled apply must move the timeout onto a different "
            "record, even when the ok values collide",
        )
        self.assertEqual(serial_missing, ["r2"])
        self.assertEqual(scrambled_missing, ["r3"])


class FailureIsolation(QueueTest):
    """One record's failure leaves the others intact and appends its own
    failure."""

    def test_one_failure_preserves_neighbours(self):
        def fail_on_beta(domain):
            if domain == "beta.test":
                raise RuntimeError("beta is down")
            return _fake_people_count(domain)

        recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
        ]
        budget = enrich.Budget(cap=None)
        result = prefetch_headcount(
            recs, fail_on_beta, _bridge_spend(budget, []), k=4,
        )

        # The failing record got no headcount_signal and carries the
        # failure marker.
        self.assertNotIn("headcount_signal", recs[1]["company_facts"])
        self.assertIn("people-count", recs[1].get("failures", []))

        # Neighbours are intact.
        self.assertEqual(recs[0]["company_facts"]["headcount_signal"], 10)
        self.assertEqual(recs[2]["company_facts"]["headcount_signal"], 30)

        # The report counts are right.
        self.assertEqual(result["attempted"], 3)
        self.assertEqual(result["ok"], 2)
        self.assertEqual(result["failed"], 1)

    def test_a_timeout_leaves_neighbours_intact(self):
        def slow_on_beta(domain):
            if domain == "beta.test":
                time.sleep(1.0)
            return _fake_people_count(domain)

        recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
        ]
        budget = enrich.Budget(cap=None)
        result = prefetch_headcount(
            recs, slow_on_beta, _bridge_spend(budget, []),
            k=4, timeout=0.05,
        )

        self.assertEqual(recs[0]["company_facts"]["headcount_signal"], 10)
        self.assertNotIn("headcount_signal", recs[1]["company_facts"])
        self.assertEqual(recs[2]["company_facts"]["headcount_signal"], 30)
        self.assertEqual(result["timed_out"], 1)
        self.assertEqual(result["ok"], 2)


class SpendIsCalledCorrectly(QueueTest):
    """`spend()` is called once per record that needs the call, and NOT
    called for a record that already has `headcount_signal`."""

    def test_spend_called_once_per_record_that_needs_it(self):
        spend_log = []

        def spend(call, why, provider="contactout", rec=None, **_kw):
            spend_log.append(rec["id"] if rec else None)
            return True

        recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test"),
        ]
        prefetch_headcount(recs, _fake_people_count, spend, k=4)

        self.assertEqual(spend_log, ["r1", "r2", "r3"])

    def test_spend_not_called_for_record_already_carrying_headcount(self):
        spend_log = []

        def spend(call, why, provider="contactout", rec=None, **_kw):
            spend_log.append(rec["id"] if rec else None)
            return True

        recs = [
            _make_rec("r1", "alpha.test", profiles=10),
            _make_rec("r2", "beta.test"),
            _make_rec("r3", "gamma.test", profiles=30),
        ]
        result = prefetch_headcount(recs, _fake_people_count, spend, k=4)

        self.assertEqual(spend_log, ["r2"])
        self.assertEqual(result["skipped_already_present"], 2)
        self.assertEqual(result["ok"], 1)

    def test_spend_not_called_when_budget_refuses(self):
        """A budget that refuses leaves the record untouched and reports
        the refusal."""
        refused = []

        def spend(call, why, provider="contactout", rec=None, **_kw):
            refused.append(rec["id"] if rec else None)
            return False

        recs = [
            _make_rec("r1", "alpha.test"),
            _make_rec("r2", "beta.test"),
        ]
        result = prefetch_headcount(recs, _fake_people_count, spend, k=4)

        self.assertEqual(refused, ["r1", "r2"])
        self.assertEqual(result["ok"], 0)
        self.assertEqual(result["skipped_budget_refused"], 2)
        # Records are untouched: no headcount_signal, no waterfall.
        for r in recs:
            self.assertNotIn("headcount_signal", r.get("company_facts") or {})
            self.assertEqual(r.get("waterfall"), None)


class BudgetCapIsSerial(QueueTest):
    """The shared Budget cap is NOT made concurrent. Two concurrent
    charges must not read the same `spent` and both pass."""

    def test_a_tight_cap_refuses_in_order(self):
        """people-count costs 0, so a credit cap cannot refuse it. But
        the bridge's `budget.charge(0, ...)` is still the serial gate,
        and a cap of 0 with a non-zero call would refuse in order. Use
        a non-zero call to prove the gate is serial."""
        # Replace people-count's cost for this test only.
        original_cost = enrich.COSTS.get("people-count")
        enrich.COSTS["people-count"] = 1
        try:
            recs = [_make_rec(f"r{i}", f"d{i}.test") for i in range(5)]
            budget = enrich.Budget(cap=3)
            notes = []
            result = prefetch_headcount(
                recs, _fake_people_count,
                _bridge_spend(budget, notes),
                k=8,
            )
            # Three approved, then the cap refuses.
            self.assertEqual(budget.spent, 3)
            self.assertEqual(result["ok"], 3)
            self.assertEqual(result["skipped_budget_refused"], 2)
            # The first three records got the value; the last two did not.
            for r in recs[:3]:
                self.assertIn("headcount_signal", r["company_facts"])
            for r in recs[3:]:
                self.assertNotIn("headcount_signal",
                                 r.get("company_facts") or {})
        finally:
            if original_cost is None:
                enrich.COSTS.pop("people-count", None)
            else:
                enrich.COSTS["people-count"] = original_cost


class DefaultK(QueueTest):
    """The default K is 8, the measurement's operating point."""

    def test_default_k_is_eight(self):
        self.assertEqual(gather_mod.DEFAULT_HEADCOUNT_K, 8)

    def test_default_k_is_used_when_not_specified(self):
        """A call that does not pass k uses K=8."""
        seen_k = []

        def capturing_gather(items, call, k=None, **kw):
            seen_k.append(k)
            return [Outcome.ok(call(item)) for item in items]

        recs = [_make_rec(f"r{i}", f"d{i}.test") for i in range(3)]
        with mock.patch.object(gather_mod, "gather", capturing_gather):
            prefetch_headcount(recs, _fake_people_count,
                               lambda *a, **kw: True)
        self.assertEqual(seen_k, [8])


if __name__ == "__main__":
    unittest.main()
