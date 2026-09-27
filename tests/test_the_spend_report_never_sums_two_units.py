"""The spend report never sums two units and always labels its denominators.

TASK-352. A spend report that prints one cost-per-lead without naming its
denominator invites the same confusion the operator flagged: three different
true numbers came out of the same fifty leads, and the handoff quoted one of
them without saying which.

ACCEPTANCE CRITERIA

1. A mixed-unit client gets the tripwire, not a summed integer.
2. All three cost-per-lead denominators appear, each labelled with its
   denominator. A bare "cost per lead" is a FAIL.
3. An unpriced provider reports null, not zero and not a guess.
4. Unattributed _model rows reported separately, with a count.
5. Read-only: the ledger is byte-identical before and after.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import spendledger, store
from scripts import spend_report


class MixedUnitTripwire(unittest.TestCase):
    """Acceptance 1: a mixed-unit client gets the tripwire, not a total."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mixed_units_emit_tripwire_not_summed_integer(self):
        """One cents row and one credits row: the report must emit the
        tripwire string, not a summed integer."""
        spendledger.record("acme", "deliverable", "deliverable-verify", 100)
        spendledger.record("acme", "apify", "company_posts", 447, unit="cents")

        report = spend_report.generate_report(client="acme")
        self.assertEqual(len(report["blocks"]), 1)

        block = report["blocks"][0]
        self.assertTrue(block["mixed_units"])
        self.assertIn("cents", block["units_seen"])
        self.assertIn("credits", block["units_seen"])

        # The decisive assertion: the formatted report contains the tripwire
        formatted = spend_report.format_report(report)
        self.assertIn("MIXED UNITS - a tripwire, not an amount", formatted)

        # And it does NOT contain a summed integer as a total
        # (100 credits + 447 cents = 547 if summed, which is wrong)
        self.assertNotIn("547", formatted)


class ThreeDenominatorsLabelled(unittest.TestCase):
    """Acceptance 2: all three cost-per-lead denominators appear, labelled."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_three_denominators_appear_labelled(self):
        """The report must show cost per cohort lead, per written lead, and
        per approved lead, each with its label."""
        # Write some spend
        spendledger.record("acme", "deliverable", "deliverable-verify", 100,
                          unit="cents")

        # Write some queue records in different states
        # "written" = drafted, approved, or pushed (passed first gate)
        # "approved" = approved or pushed (passed both gates)
        queue_path = os.path.join(self.tmp, "queue.jsonl")
        with open(queue_path, "w", encoding="utf-8") as fh:
            # 5 cohort leads total
            for i in range(5):
                # 2 approved (pass both gates), 1 drafted (passed first gate only), 2 queued
                if i < 2:
                    state = "approved"  # 2 approved leads (pass both gates)
                elif i < 3:
                    state = "drafted"  # 1 drafted (passed first gate, not second)
                else:
                    state = "queued"  # 2 queued (haven't passed first gate)
                fh.write(json.dumps({
                    "id": f"rec-{i}",
                    "client": "acme",
                    "state": state,
                }) + "\n")

        report = spend_report.generate_report(client="acme")
        block = report["blocks"][0]

        # All three denominators must be present
        self.assertIn("cohort_leads", block["lead_counts"])
        self.assertIn("written_leads", block["lead_counts"])
        self.assertIn("approved_leads", block["lead_counts"])

        # And their values must be correct
        self.assertEqual(block["lead_counts"]["cohort_leads"], 5)
        self.assertEqual(block["lead_counts"]["written_leads"], 3)  # 2 approved + 1 drafted
        self.assertEqual(block["lead_counts"]["approved_leads"], 2)  # 2 approved

        # Cost per lead must be calculated for all three
        self.assertIn("per_cohort_lead", block["cost_per_lead"])
        self.assertIn("per_written_lead", block["cost_per_lead"])
        self.assertIn("per_approved_lead", block["cost_per_lead"])

        # The formatted report must label each denominator
        formatted = spend_report.format_report(report)
        self.assertIn("per cohort lead", formatted)
        self.assertIn("per written lead", formatted)
        self.assertIn("per approved lead (both gates)", formatted)

        # A bare "cost per lead" without a label is a FAIL
        # (we check that each DATA line has a specific denominator)
        lines = formatted.split("\n")
        cost_per_lead_lines = [l for l in lines if "per " in l.lower() and "lead" in l.lower() and "$" in l]
        for line in cost_per_lead_lines:
            # Each data line must mention a specific denominator
            self.assertTrue(
                "cohort" in line or "written" in line or "approved" in line or "both gates" in line,
                f"Found unlabeled 'cost per lead' line: {line}")


class UnpricedProviderReportsNull(unittest.TestCase):
    """Acceptance 3: an unpriced provider reports null, not zero or a guess."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_credits_unpriced_reports_null(self):
        """Credits are unpriced (USD_PER_UNIT['credits'] is None). A provider
        whose rows are in credits must report usd_estimate: null."""
        spendledger.record("acme", "deliverable", "deliverable-verify", 100)

        report = spend_report.generate_report(client="acme")
        block = report["blocks"][0]

        provider_summary = block["providers"]["deliverable"]
        self.assertIsNone(provider_summary["usd_estimate"])
        self.assertEqual(provider_summary["rate_source"], "unknown")

        # The formatted report must show "null", not "$0.0000"
        formatted = spend_report.format_report(report)
        self.assertIn("usd_estimate: null", formatted)
        self.assertNotIn("usd_estimate: $0.0000", formatted)

    def test_usd_estimate_function_returns_none_for_credits(self):
        """The underlying function also returns None for credits."""
        u, rate, src = spendledger.usd_estimate(500, "credits")
        self.assertIsNone(u)
        self.assertIsNone(rate)
        self.assertEqual(src, "unknown")


class UnattributedModelRows(unittest.TestCase):
    """Acceptance 4: unattributed _model rows reported separately."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_model_rows_reported_separately(self):
        """Rows with client='_model' are unattributed and must be reported
        separately, with a count."""
        # Normal row
        spendledger.record("acme", "deliverable", "deliverable-verify", 100)
        # Model row (unattributed)
        spendledger.record("_model", "anthropic", "sonnet", 2560, unit="microusd")
        spendledger.record("_model", "anthropic", "sonnet", 1280, unit="microusd")

        report = spend_report.generate_report(all_clients=True)

        # Find the block for client "acme"
        acme_block = next(b for b in report["blocks"] if b["client"] == "acme")
        self.assertEqual(acme_block["unattributed_model_rows"]["count"], 0)

        # Find the block for client "_model"
        model_block = next(b for b in report["blocks"] if b["client"] == "_model")
        self.assertEqual(model_block["unattributed_model_rows"]["count"], 2)
        self.assertEqual(model_block["unattributed_model_rows"]["total_cost"], 3840)

        # The formatted report must mention unattributed model rows
        formatted = spend_report.format_report(report)
        self.assertIn("UNATTRIBUTED MODEL ROWS", formatted)
        self.assertIn("count: 2", formatted)


class ReadOnlyLedger(unittest.TestCase):
    """Acceptance 5: the ledger is byte-identical before and after."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ledger_unchanged_after_report(self):
        """The report is read-only. The ledger must be byte-identical before
        and after generating the report."""
        # Write some rows
        spendledger.record("acme", "deliverable", "deliverable-verify", 100)
        spendledger.record("acme", "apify", "company_posts", 447, unit="cents")

        # Read the ledger before
        ledger_path = spendledger.path()
        with open(ledger_path, "rb") as fh:
            before = fh.read()

        # Generate the report
        report = spend_report.generate_report(client="acme")
        formatted = spend_report.format_report(report)

        # Read the ledger after
        with open(ledger_path, "rb") as fh:
            after = fh.read()

        # The decisive assertion: byte-identical
        self.assertEqual(before, after,
                        "The ledger changed after generating the report. "
                        "A report must be read-only.")


class CostPerLeadCalculation(unittest.TestCase):
    """The cost-per-lead calculation is correct on all three denominators."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))
        store.use_directory(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cost_per_lead_on_three_denominators(self):
        """From the task: 50 cohort leads, 31 written, 13 passing both gates.
        Total cost $3.1464. The three cost-per-lead figures must be:
          per cohort lead:            6.29c
          per written lead:          10.15c
          per lead passing both gates: 24.20c
        """
        # Write spend totaling $3.1464 (3,146,400 microusd)
        spendledger.record("acme", "anthropic", "sonnet", 3_146_400, unit="microusd")

        # Write queue records: 50 cohort, 31 written, 13 approved
        # "written" = drafted, approved, or pushed (passed first gate)
        # "approved" = approved or pushed (passed both gates)
        queue_path = os.path.join(self.tmp, "queue.jsonl")
        with open(queue_path, "w", encoding="utf-8") as fh:
            for i in range(50):
                # 13 approved (pass both gates), 18 drafted (passed first gate only), 19 queued
                if i < 13:
                    state = "approved"
                elif i < 31:
                    state = "drafted"
                else:
                    state = "queued"
                fh.write(json.dumps({
                    "id": f"rec-{i}",
                    "client": "acme",
                    "state": state,
                }) + "\n")

        report = spend_report.generate_report(client="acme")
        block = report["blocks"][0]

        # Check lead counts
        self.assertEqual(block["lead_counts"]["cohort_leads"], 50)
        self.assertEqual(block["lead_counts"]["written_leads"], 31)
        self.assertEqual(block["lead_counts"]["approved_leads"], 13)

        # Check cost per lead (in USD)
        # $3.1464 / 50 = $0.062928
        self.assertAlmostEqual(block["cost_per_lead"]["per_cohort_lead"],
                              0.062928, places=5)
        # $3.1464 / 31 = $0.101497
        self.assertAlmostEqual(block["cost_per_lead"]["per_written_lead"],
                              0.101497, places=5)
        # $3.1464 / 13 = $0.242031
        self.assertAlmostEqual(block["cost_per_lead"]["per_approved_lead"],
                              0.242031, places=5)


if __name__ == "__main__":
    unittest.main()
