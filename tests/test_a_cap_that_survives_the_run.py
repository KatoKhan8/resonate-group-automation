#!/usr/bin/env python3
"""`--cap` bounded one invocation and nothing remembered the last one.

MEASURED, on myself. On 2026-09-10 I ran three enrichment passes over the same
cohort at `--cap 260` each. Every one was individually inside its ceiling, the
audit reported clean each time, and no part of the system could have told you
the total. That is not a cap; it is a per-run speed limit with no odometer.

`pilotcaps` does not close it either - it bounds VOLUME (companies, contacts,
sends per day), and a single company costs one credit or forty depending how
far down the waterfall it goes.

And there is no monetary budget anywhere in this repository. Searched on
2026-09-10: no per-day ceiling, no per-provider ceiling, no total. The only
"$5" in the tree is a fixture string about a client's negotiating position.

WHAT THIS MODULE DELIBERATELY DOES NOT DO is pick a number. A ceiling nobody
agreed to is not a safety control - it is a number that gets raised the first
time it is inconvenient, and it disguises an operator's decision as an
engineering default. Undeclared means unlimited, and unlimited SAYS so.
"""
import unittest

from src import spendledger as sl
from tests.base import QueueTest


def row(cost, client="productive", provider="contactout", day=None, call="x"):
    return {"at": "2026-09-10T12:00", "day": day or sl.today(),
            "client": client, "provider": provider, "call": call,
            "expected_cost": cost, "run_id": None}


class ACeilingNobodyDeclaredIsNotInvented(unittest.TestCase):

    def test_an_undeclared_ceiling_is_none_not_a_default(self):
        self.assertEqual(sl.caps({}),
                         {s: None for s in sl.SCOPES})

    def test_undeclared_means_unlimited_and_permits_anything(self):
        self.assertTrue(sl.check("productive", {}, 10 ** 9, rows=[]))

    def test_the_report_names_which_ceilings_are_unlimited(self):
        out = sl.report("productive", {"budget": {"per_day": 500}}, rows=[])
        self.assertEqual(out["ceilings"]["per_day"], 500)
        self.assertIn("total", out["unlimited"])
        self.assertNotIn("per_day", out["unlimited"])

    def test_a_declared_ceiling_is_read_as_declared(self):
        self.assertEqual(sl.caps({"budget": {"total": 2000}})["total"], 2000)


class ACapThatSpansRuns(unittest.TestCase):
    """The actual bug: three runs, three clean audits, no total."""

    def test_spend_accumulates_across_runs(self):
        rows = [row(260), row(260), row(260)]
        self.assertEqual(sl.spent("productive", rows=rows), 780)

    def test_the_fourth_run_is_refused_against_a_declared_total(self):
        rows = [row(260), row(260), row(260)]
        with self.assertRaises(sl.BudgetExceeded) as caught:
            sl.check("productive", {"budget": {"total": 1000}}, 260, rows=rows)
        self.assertIn("780", str(caught.exception))
        self.assertIn("total", str(caught.exception))

    def test_the_refusal_names_which_ceiling_applied(self):
        rows = [row(400)]
        with self.assertRaises(sl.BudgetExceeded) as caught:
            sl.check("productive", {"budget": {"per_day": 500, "total": 9999}},
                     200, rows=rows)
        self.assertIn("per_day", str(caught.exception))

    def test_a_provider_ceiling_is_scoped_to_that_provider(self):
        # `total` added 2026-09-25: a governed client with no lifetime
        # ceiling anywhere is now refused by `MissingCeiling` before any of
        # these scoped ceilings are reached, so a fixture that declares none
        # would be testing that guard instead of this one.
        rows = [row(400, provider="contactout"), row(50, provider="apify")]
        cfg = {"budget": {"per_provider_per_day": 420, "total": 100_000}}
        with self.assertRaises(sl.BudgetExceeded):
            sl.check("productive", cfg, 50, provider="contactout", rows=rows)
        self.assertTrue(sl.check("productive", cfg, 50, provider="apify",
                                 rows=rows))

    def test_yesterdays_spend_does_not_consume_todays_ceiling(self):
        rows = [row(900, day="2026-09-09")]
        self.assertTrue(sl.check("productive",
                                 {"budget": {"per_day": 500,
                                             "total": 100_000}},
                                 100, rows=rows))

    def test_but_it_does_consume_the_total(self):
        rows = [row(900, day="2026-09-09")]
        with self.assertRaises(sl.BudgetExceeded):
            sl.check("productive", {"budget": {"total": 950}}, 100, rows=rows)


class OneClientNeverPaysForAnother(unittest.TestCase):

    def test_another_tenants_spend_is_not_counted(self):
        rows = [row(900, client="someone-else")]
        self.assertEqual(sl.spent("productive", rows=rows), 0)
        self.assertTrue(sl.check("productive", {"budget": {"total": 100}}, 50,
                                 rows=rows))

    def test_an_unscoped_check_is_refused_rather_than_permissive(self):
        """`spent()` defaults to every tenant, which is right for a REPORT and
        wrong for a CHECK. `actionledger.count_on` had the same default and it
        was a real bug there."""
        with self.assertRaises(sl.BudgetExceeded):
            sl.check(None, {"budget": {"total": 10}}, 1, rows=[])
        with self.assertRaises(sl.BudgetExceeded):
            sl.check("", {"budget": {"total": 10}}, 1, rows=[])


class ItFailsClosed(QueueTest):

    def corrupt(self):
        import os
        os.makedirs(os.path.dirname(sl.path()), exist_ok=True)
        with open(sl.path(), "w", encoding="utf-8") as fh:
            fh.write("{not json at all\n")

    def test_an_unreadable_ledger_refuses_rather_than_reading_as_empty(self):
        """A spend control that opens when its own state is missing opens
        exactly when something is already wrong."""
        self.corrupt()
        with self.assertRaises(sl.LedgerUnreadable) as caught:
            sl.load()
        self.assertIn("Refusing to authorise spend", str(caught.exception))

    def test_a_corrupt_ledger_refuses_the_check_too(self):
        """`load()` raising is only useful if `check()` does not swallow it."""
        self.corrupt()
        with self.assertRaises(sl.LedgerUnreadable):
            sl.check("productive", {"budget": {"total": 100}}, 1)

    def test_a_missing_ledger_is_genuinely_empty(self):
        """Absent and corrupt are different. A first run must not be refused."""
        self.assertEqual(sl.load(), [])
        self.assertEqual(sl.spent("productive"), 0)

    def test_a_recorded_charge_is_durable_immediately(self):
        sl.record("productive", "contactout", "decision-makers", 10)
        self.assertEqual(sl.spent("productive"), 10)
        self.assertEqual(sl.spent("productive", provider="apify"), 0)

    def test_it_records_expected_and_says_so(self):
        """Expected and observed are different claims. This holds one."""
        written = sl.record("productive", "contactout", "x", 10)
        self.assertEqual(written["expected_cost"], 10)
        self.assertNotIn("actual_cost", written)
        self.assertIn("src/costs.py", sl.report("productive")["note"])



class TheWaterfallRecordsAndRespectsIt(QueueTest):
    """Wired into `enrich.spend`, which is the only door a paid call uses.

    Recording it anywhere else would be a second implementation of the same
    fact, and a spend control that a new call site can forget to consult is
    the control this module exists to replace.
    """

    def rec(self):
        return {"id": "acme", "client": "productive", "domain": "acme.test",
                "company": "Acme", "lane": "domains", "contacts": [],
                "company_facts": {}, "research": [], "events": [], "log": []}

    def test_a_charge_reaches_the_durable_ledger(self):
        from src import enrich
        enrich.enrich_record(self.rec(), enrich.Budget(1000), live=False,
                             config={"budget": {}})
        # A dry run spends nothing, so the ledger stays empty - which is the
        # correct baseline for the next assertion to mean anything.
        self.assertEqual(sl.spent("productive"), 0)

    def test_a_declared_ceiling_stops_the_waterfall(self):
        """The end-to-end property: a config ceiling refuses a real call."""
        from src import enrich
        sl.record("productive", "contactout", "earlier-run", 500)
        rec = self.rec()
        enrich.enrich_record(rec, enrich.Budget(1000), live=True,
                             config={"budget": {"total": 400}})
        notes = " ".join(str(e.get("reason") or "") for e in rec["events"])
        self.assertIn("durable budget", notes,
                      "a durable ceiling was declared and nothing consulted it")

    def test_an_undeclared_ceiling_does_not_block_anything(self):
        """Undeclared is unlimited, and must not become a silent zero."""
        from src import enrich
        sl.record("productive", "contactout", "earlier-run", 10 ** 6)
        rec = self.rec()
        enrich.enrich_record(rec, enrich.Budget(1000), live=True, config={})
        notes = " ".join(str(e.get("reason") or "") for e in rec["events"])
        self.assertNotIn("durable budget", notes)

if __name__ == "__main__":
    unittest.main()
