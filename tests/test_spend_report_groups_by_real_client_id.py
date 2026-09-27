"""Spend report groups by the now-real client ids, not folded into unattributed.

TASK-414. The ledger's client-attribution work now writes real client ids on
every row (TASK-346 moved model spend from "_model" to the calling client).
The report consumers must honour those ids: a row attributed to "acme" must
appear in acme's total, not in "unattributed" or in another client's.

This test proves:

1. spendledger.spent() filters by client correctly - acme rows do not count
   for globex, and unattributed rows do not count for either.
2. spendledger.report() for a specific client reflects only that client's
   rows, with the correct expected_total.
3. web/api.py spend_ledger() groups records by their real client field, and
   records with no client land under "unknown", not under a real client.
4. A mixed fixture (acme, globex, unattributed) produces three separate
   buckets with correct totals - nothing is folded in.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store                        # noqa: E402


class IsolatedLedger(unittest.TestCase):
    """A disposable ledger per test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-task414-")
        self.addCleanup(store.use_directory(self.tmp))
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        self.run_id = spendledger.new_run(f"test-{id(self)}")


class SpendReportGroupsByRealClientId(IsolatedLedger):
    """The report separates real client ids from each other and from
    unattributed."""

    def _write_mixed_fixture(self):
        """Three acme rows, two globex rows, one unattributed. All credits."""
        spendledger.record("acme", "deliverable", "verify", 100)
        spendledger.record("acme", "contactout", "lookup", 200)
        spendledger.record("acme", "reoon", "verify", 50)
        spendledger.record("globex", "deliverable", "verify", 300)
        spendledger.record("globex", "cheapverifier", "verify", 400)
        spendledger.record("unattributed", "glm", "complete:glm-5.3", 500,
                           unit="microusd")

    def test_spent_filters_by_client(self):
        """spent(acme) != spent(globex) != spent(unattributed)."""
        self._write_mixed_fixture()
        self.assertEqual(350, spendledger.spent("acme"))
        self.assertEqual(700, spendledger.spent("globex"))
        self.assertEqual(500, spendledger.spent("unattributed"))

    def test_spent_none_counts_everything(self):
        """spent(None) sums all clients together."""
        self._write_mixed_fixture()
        # 100+200+50+300+400+500 = 1550
        self.assertEqual(1550, spendledger.spent(None))

    def test_report_for_acme_reflects_only_acme_rows(self):
        """report(client='acme') total matches acme rows only."""
        self._write_mixed_fixture()
        rpt = spendledger.report(client="acme")
        # acme rows are all credits: 100+200+50 = 350
        self.assertEqual(350, rpt["expected_total"])
        self.assertIn("deliverable", rpt["by_provider"])
        self.assertEqual(100, rpt["by_provider"]["deliverable"])
        self.assertIn("contactout", rpt["by_provider"])
        self.assertEqual(200, rpt["by_provider"]["contactout"])
        # globex's provider must NOT appear
        self.assertNotIn("cheapverifier", rpt["by_provider"])

    def test_report_for_globex_reflects_only_globex_rows(self):
        """report(client='globex') total matches globex rows only."""
        self._write_mixed_fixture()
        rpt = spendledger.report(client="globex")
        self.assertEqual(700, rpt["expected_total"])
        self.assertIn("cheapverifier", rpt["by_provider"])
        self.assertEqual(400, rpt["by_provider"]["cheapverifier"])
        # acme's contactout must NOT appear
        self.assertNotIn("contactout", rpt["by_provider"])

    def test_report_unattributed_does_not_fold_into_acme(self):
        """The unattributed microusd row stays separate from acme's credits."""
        self._write_mixed_fixture()
        acme_rpt = spendledger.report(client="acme")
        unattr_rpt = spendledger.report(client="unattributed")
        # acme total is 350, NOT 350+500=850
        self.assertEqual(350, acme_rpt["expected_total"])
        # unattributed total is 500
        self.assertEqual(500, unattr_rpt["expected_total"])

    def test_report_no_client_shows_all_providers(self):
        """report(client=None) sees every provider across all clients."""
        self._write_mixed_fixture()
        rpt = spendledger.report(client=None)
        # All providers present
        self.assertIn("deliverable", rpt["by_provider"])
        self.assertIn("contactout", rpt["by_provider"])
        self.assertIn("cheapverifier", rpt["by_provider"])
        self.assertIn("glm", rpt["by_provider"])
        # deliverable: acme 100 + globex 300 = 400
        self.assertEqual(400, rpt["by_provider"]["deliverable"])


class WebApiSpendLedgerGroupsByRealClientId(IsolatedLedger):
    """web/api.py spend_ledger() groups records by their real client field."""

    def _fixture_records(self):
        """Three records: two with real clients, one with none."""
        return [
            {"id": "r1", "client": "acme", "contacts": [],
             "waterfall": [{"provider": "deliverable", "call": "verify",
                            "expected_cost": 100, "stage": "completed"}]},
            {"id": "r2", "client": "acme", "contacts": [],
             "waterfall": [{"provider": "contactout", "call": "lookup",
                            "expected_cost": 200, "stage": "completed"}]},
            {"id": "r3", "client": "globex", "contacts": [],
             "waterfall": [{"provider": "deliverable", "call": "verify",
                            "expected_cost": 300, "stage": "completed"}]},
            {"id": "r4", "contacts": [],
             "waterfall": [{"provider": "reoon", "call": "verify",
                            "expected_cost": 50, "stage": "completed"}]},
        ]

    def test_by_client_separates_real_clients(self):
        """by_client has acme and globex as separate keys."""
        from src.web.api import spend_ledger
        recs = self._fixture_records()
        result = spend_ledger(recs)
        by_client = result["by_client"]
        self.assertIn("acme", by_client)
        self.assertIn("globex", by_client)
        self.assertEqual(300, by_client["acme"])     # 100 + 200
        self.assertEqual(300, by_client["globex"])

    def test_missing_client_lands_under_unknown_not_under_real_client(self):
        """A record with no client field goes to 'unknown', not to acme."""
        from src.web.api import spend_ledger
        recs = self._fixture_records()
        result = spend_ledger(recs)
        by_client = result["by_client"]
        self.assertIn("unknown", by_client)
        self.assertEqual(50, by_client["unknown"])
        # acme is still 300, not 350
        self.assertEqual(300, by_client["acme"])

    def test_total_credits_sums_all_clients(self):
        """total_credits is the sum across every client including unknown."""
        from src.web.api import spend_ledger
        recs = self._fixture_records()
        result = spend_ledger(recs)
        # 100+200+300+50 = 650
        self.assertEqual(650, result["total_credits"])


if __name__ == "__main__":
    unittest.main()
