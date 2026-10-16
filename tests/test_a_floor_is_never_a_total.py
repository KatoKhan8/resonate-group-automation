#!/usr/bin/env python3
"""A partial sum may not dress as a total.

TASK 0074. The sentinel that escaped TASK 0073's fence was not the UNKNOWN
object - that one refuses arithmetic and the persistence seam converts it.
It was the NUMERIC FLOOR. `waterfall.spend()` says `expected: 8,
expected_is: "floor", unpriced_calls: 2`, and two consumers read only the 8:
the simulator's `already_spent` (a rehearsal credit figure summed across
records) and `costs.reconcile`, whose FREE_CONFIRMED verdict asserted
"confirmed free" from an expected of 0 that meant "nothing was priced".
The 2026-09-10 apify case in costs.py's own header - ten correctly-ledgered
calls, $0.66 on the bill - reads FREE_CONFIRMED at any snapshot taken before
the usd counter catches up, for exactly this reason.

This file holds the classifier (TASK 0074 section 2, made executable) and
the per-repaired-site tests (control C1). The classifier's ground truth is
the fixture's own `priced: False` rows. It names every surface that builds a
figure from those rows and hands it on without saying part of it was never
priced - and, the mirror lie, a surface that calls a complete number a floor.

Kill-sets, named (controls C1 and C2):

- Deaden the simulator repair (drop `already_spent_is`/`unpriced_calls`
  from `_credit_estimate`) and these die:
  `test_already_spent_is_a_floor_when_a_price_is_missing`,
  `test_the_classifier_reports_zero_when_a_price_is_missing`,
  `test_the_classifier_reports_zero_when_every_price_is_known`.
- Deaden the verdict guard (`_verdict` ignoring its `unpriced` argument) and
  these die: `test_free_is_never_confirmed_on_a_bucket_that_was_never_priced`,
  `test_the_classifier_reports_zero_when_a_price_is_missing`.
- Drop the unpriced count/`expected_is` from the reconcile rows and these
  die: `test_reconcile_rows_carry_the_count_that_keeps_the_number_a_floor`,
  `test_the_classifier_reports_zero_when_a_price_is_missing`,
  `test_the_classifier_reports_zero_when_every_price_is_known`.
- Drop the report's FLOOR marker and these die:
  `test_the_report_marks_a_floor_as_a_floor`,
  `test_the_classifier_reports_zero_when_a_price_is_missing`.
- Over-refuse instead (mark a priced total as a floor) and these die:
  `test_already_spent_is_a_total_when_every_price_is_known`,
  `test_free_is_confirmed_on_a_priced_zero`,
  `test_the_report_marks_nothing_when_every_price_is_known`,
  `test_the_classifier_reports_zero_when_every_price_is_known`.
"""
import unittest

from src import clients, costs, simulator


def rec(*rows):
    return {"id": "r1", "waterfall": [dict(r) for r in rows]}


def unpriced(provider="apify", call="apify-research"):
    """A row nobody could price: expected_cost 0 BECAUSE it is unpriced."""
    return {"provider": provider, "call": call, "expected_cost": 0,
            "priced": False, "at": "2026-10-16T09:00"}


def priced(provider="contactout", call="people-count", cost=4):
    return {"provider": provider, "call": call, "expected_cost": cost,
            "at": "2026-10-16T09:01"}


def every_price_known():
    """The C2 fixture where nothing is unknown: no surface may lie."""
    return [rec(priced(cost=4), priced(call="people-enrich", cost=4))]


def a_price_is_missing():
    """The C2 fixture with a missing price: apify compute-unit rows."""
    return [rec(unpriced(), unpriced(call="apify-actor"),
                priced(cost=4), priced(call="people-enrich", cost=4))]


def quiet():
    """Both snapshots identical: every authoritative delta is zero."""
    return {"contactout": {"count": 100, "search_count": 10, "phone_count": 5,
                           "quota": 1000, "search_quota": 2000,
                           "phone_quota": 300},
            "apify": {"usd": 1.0}}


_CONFIG = None


def _config():
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = clients.load("demo")
    return _CONFIG


def unpriced_truth(records):
    """Provider -> unpriced row count. The classifier's ground truth."""
    truth = {}
    for r in records or []:
        for row in r.get("waterfall") or []:
            if (row or {}).get("priced") is False:
                name = row.get("provider") or "unknown"
                truth[name] = truth.get(name, 0) + 1
    return truth


def classify_fail_open(records):
    """TASK 0074 section 2, executable. Returns FAIL-OPEN surface names.

    A surface is FAIL-OPEN when the fixture's rows include `priced: False`
    and the surface hands on the figure they produced without saying so -
    or when no row is unpriced and the surface claims one was (the mirror
    lie, which costs a decision the other way). Sorted, deduplicated.
    """
    truth = unpriced_truth(records)
    total_unpriced = sum(truth.values())
    fail = []

    # Surface 1: simulator._credit_estimate -> already_spent, summed across
    # records from waterfall.spend()'s numeric `expected`.
    est = simulator._credit_estimate(records, _config())
    want = "floor" if total_unpriced else "total"
    if (est.get("already_spent_is") != want
            or est.get("unpriced_calls") != total_unpriced):
        fail.append("simulator._credit_estimate/already_spent")

    # Surface 2-4: costs.reconcile rows, _verdict, report.
    out = costs.reconcile(quiet(), dict(quiet()), records)
    rows = {r["provider"]: r for r in out["providers"]}
    for provider, count in sorted(truth.items()):
        row = rows.get(provider)
        if row is None:
            fail.append("costs.reconcile/provider-row-missing")
            continue
        if row.get("unpriced") != count or row.get("expected_is") != "floor":
            fail.append("costs.reconcile/row-drops-unpriced")
        if row["status"] == costs.FREE_CONFIRMED:
            fail.append("costs._verdict/FREE_CONFIRMED-on-floor")
    for provider, row in sorted(rows.items()):
        if provider not in truth and row.get("expected_is") != "total":
            fail.append("costs.reconcile/row-drops-unpriced")
    text = costs.report(out)
    if truth and "FLOOR" not in text:
        fail.append("costs.report/floor-unmarked")
    if not truth and "FLOOR" in text:
        fail.append("costs.report/floor-marked-when-total")
    return sorted(set(fail))


class TheSimulatorsAlreadySpentIsALabelledFloor(unittest.TestCase):
    """C1, repaired site 1: src/simulator.py `_credit_estimate`."""

    def test_already_spent_is_a_floor_when_a_price_is_missing(self):
        est = simulator._credit_estimate(a_price_is_missing(), _config())
        self.assertEqual(est["already_spent_is"], "floor")
        self.assertEqual(est["unpriced_calls"], 2)
        # The number stays numeric on purpose (TASK 0073's choice): screens
        # do arithmetic on it. It is the known part, labelled as a floor.
        self.assertEqual(est["already_spent"], 8)

    def test_already_spent_is_a_total_when_every_price_is_known(self):
        est = simulator._credit_estimate(every_price_known(), _config())
        self.assertEqual(est["already_spent_is"], "total")
        self.assertEqual(est["unpriced_calls"], 0)
        self.assertEqual(est["already_spent"], 8)


class TheVerdictCannotConfirmAFreeItDidNotPrice(unittest.TestCase):
    """C1, repaired site 2: src/costs.py reconcile/_verdict/report."""

    def row_for(self, records, provider):
        out = costs.reconcile(quiet(), dict(quiet()), records)
        return next(r for r in out["providers"] if r["provider"] == provider)

    def test_free_is_never_confirmed_on_a_bucket_that_was_never_priced(self):
        row = self.row_for(a_price_is_missing(), "apify")
        self.assertEqual(row["status"], costs.UNPRICED)
        self.assertEqual(row["unpriced"], 2)
        self.assertEqual(row["expected_is"], "floor")
        self.assertIn("could not be priced", row["why"])
        self.assertIn("no counter moved", row["why"])

    def test_free_is_confirmed_on_a_priced_zero(self):
        """The pinned priced case must keep its verdict: no over-refusal.

        Mirrors test_a_cost_claim_names_its_evidence: a bucket the price
        table genuinely says is free, with quiet counters, is FREE_CONFIRMED.
        """
        records = [rec(priced(cost=0), priced(call="people-enrich", cost=0))]
        row = self.row_for(records, "contactout")
        self.assertEqual(row["status"], costs.FREE_CONFIRMED)
        self.assertEqual(row["expected_is"], "total")
        self.assertEqual(row["unpriced"], 0)

    def test_reconcile_rows_carry_the_count_that_keeps_the_number_a_floor(self):
        floor_row = self.row_for(a_price_is_missing(), "apify")
        total_row = self.row_for(a_price_is_missing(), "contactout")
        self.assertEqual(floor_row["unpriced"], 2)
        self.assertEqual(floor_row["expected_is"], "floor")
        self.assertEqual(total_row["unpriced"], 0)
        self.assertEqual(total_row["expected_is"], "total")

    def test_reconciled_on_a_floor_names_the_floor(self):
        """RECONCILED with an unpriced part must say the agreement is
        partial, not audited."""
        records = [rec(unpriced(), priced(provider="apify",
                                          call="apify-actor", cost=5))]
        after = quiet()
        after["apify"] = {"usd": 1.66}
        out = costs.reconcile(quiet(), after, records)
        row = next(r for r in out["providers"] if r["provider"] == "apify")
        self.assertEqual(row["status"], costs.RECONCILED)
        self.assertEqual(row["expected_is"], "floor")
        self.assertIn("floor", row["why"])

    def test_the_report_marks_a_floor_as_a_floor(self):
        out = costs.reconcile(quiet(), dict(quiet()), a_price_is_missing())
        line = next(l for l in costs.report(out).splitlines()
                    if "apify" in l)
        self.assertIn("FLOOR", line)
        self.assertIn("2", line)

    def test_the_report_marks_nothing_when_every_price_is_known(self):
        out = costs.reconcile(quiet(), dict(quiet()), every_price_known())
        self.assertNotIn("FLOOR", costs.report(out))


class TheClassifier(unittest.TestCase):
    """C2: the classifier must be able to print zero, and must print the
    named sites when a repair is dead - pre-repair, on the unmodified
    module, it printed all four (recorded in LANE-glm.md, TASK 0074)."""

    def test_the_classifier_reports_zero_when_every_price_is_known(self):
        self.assertEqual(classify_fail_open(every_price_known()), [])

    def test_the_classifier_reports_zero_when_a_price_is_missing(self):
        self.assertEqual(classify_fail_open(a_price_is_missing()), [])


if __name__ == "__main__":
    unittest.main()
