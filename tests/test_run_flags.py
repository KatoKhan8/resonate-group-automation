"""Tests for --limit, --lane and --cap flag semantics. TASK-181.

Three flags that an operator reads as bounding the run, and two of them did
not. `--limit 20` processed nine records because it bounded the scan window,
not the work done. `--lane domains` did not scope enrich or qualify at all.
`--cap` is the one that carries money and deserved a test proving it refuses.

Every test here runs against a fake queue and a fake provider. No credits are
spent, no provider is called.
"""
import os
import tempfile
import shutil
import unittest
from unittest import mock

from src import store, run as run_mod, clients


def _fake_config(client="test", **over):
    """A minimal client config that satisfies the stages' expectations."""
    config = {
        "cadence": "productive_balanced_v1",
        "verification": {"policy": "standard"},
        "icp": {"segments": {}, "default_segment": "tier_c"},
    }
    config.update(over)
    return config


class FlagTest(unittest.TestCase):
    """Isolated store for each test. No provider calls."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-flags-")
        self._prev_queue = os.environ.get("QUEUE")
        self._prev_out = os.environ.get("OUT")
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        # Mock clients.load so stages don't fail on missing config files
        self._clients_patch = mock.patch.object(
            clients, "load",
            lambda name, *a, **kw: _fake_config(name))
        self._clients_patch.start()

    def tearDown(self):
        self._clients_patch.stop()
        if self._prev_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev_queue
        if self._prev_out is None:
            os.environ.pop("OUT", None)
        else:
            os.environ["OUT"] = self._prev_out
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_record(self, rid, lane="domains", client="test",
                     company="Acme", domain="acme.test",
                     state="queued", stages=None):
        rec = store.new_record(rid, lane, client, company, domain)
        rec["state"] = state
        if stages:
            rec["stages"] = stages
        return rec

    def _seed_queue(self, records):
        store.append(records, note="test seed")


class LimitBoundsProcessing(FlagTest):
    """`--limit N` bounds the records that have work done on them.

    The old behaviour sliced the first N from the queue and let each stage
    skip the ones already done. A limit of 20 processed nine because 11 of
    the first 20 were already enriched. The fix filters to records that need
    work first, then takes the first N of those.
    """

    def test_limit_skips_already_done_records(self):
        """10 records, 7 already enriched. --limit 5 should process 3 new ones.

        There are only 3 active records (the 3 without enrich done), so even
        though the limit is 5, only 3 can be processed. The limit bounds the
        maximum, not the exact count.
        """
        records = []
        for i in range(10):
            rid = f"rec-{i:03d}"
            if i < 7:
                stages = {"enrich": {"status": "done", "at": "2026-09-16T00:00:00+00:00"}}
            else:
                stages = {}
            records.append(self._make_record(rid, stages=stages))
        self._seed_queue(records)

        # Run enrich only, with limit=5
        report = run_mod.run(limit=5, stages=("enrich",))

        # Only 3 records need work; limit is 5; all 3 are processed
        self.assertEqual(report["enrich"]["records"], 3)

    def test_limit_bounds_when_more_active_than_limit(self):
        """10 active records, --limit 3 should process exactly 3."""
        records = []
        for i in range(10):
            rid = f"rec-{i:03d}"
            records.append(self._make_record(rid))
        self._seed_queue(records)

        report = run_mod.run(limit=3, stages=("enrich",))
        self.assertEqual(report["enrich"]["records"], 3)

    def test_limit_with_all_done_returns_zero(self):
        """All records already done. --limit 5 should process 0."""
        records = []
        for i in range(10):
            rid = f"rec-{i:03d}"
            stages = {"enrich": {"status": "done", "at": "2026-09-16T00:00:00+00:00"}}
            records.append(self._make_record(rid, stages=stages))
        self._seed_queue(records)

        report = run_mod.run(limit=5, stages=("enrich",))
        self.assertEqual(report["enrich"]["records"], 0)

    def test_limit_without_flag_processes_all_active(self):
        """No limit: all active records are processed."""
        records = []
        for i in range(5):
            rid = f"rec-{i:03d}"
            records.append(self._make_record(rid))
        self._seed_queue(records)

        report = run_mod.run(stages=("enrich",))
        self.assertEqual(report["enrich"]["records"], 5)

    def test_limit_counts_qualify_rework(self):
        """A record whose qualify is done but facts changed needs work.

        `qualify.needs_work` compares an inputs fingerprint. A record with
        a stale fingerprint counts against the limit even though its stage
        is marked done.
        """
        records = []
        for i in range(5):
            rid = f"rec-{i:03d}"
            stages = {"enrich": {"status": "done", "at": "2026-09-16T00:00:00+00:00"}}
            rec = self._make_record(rid, stages=stages)
            # Give it company facts so qualify has something to fingerprint,
            # and a qualification with a STALE fingerprint so needs_work
            # returns True.
            rec["company_facts"] = {"headcount_signal": 50, "name": "Acme"}
            rec["qualification"] = {
                "inputs_fingerprint": "stale-fingerprint-that-does-not-match",
            }
            # Mark qualify as done - the stage ran, but the facts changed
            rec["stages"]["qualify"] = {"status": "done",
                                        "at": "2026-09-16T00:00:00+00:00"}
            records.append(rec)
        self._seed_queue(records)

        # Mock qualify.company and qualify.needs_work so the test doesn't
        # need a full config. needs_work is the real function; company is
        # the expensive one.
        from src import qualify
        with mock.patch.object(qualify, "company", return_value={"record": {}}):
            report = run_mod.run(limit=3, stages=("qualify",))
        # All 5 need rework, but limit is 3
        self.assertEqual(report["qualify"]["records"], 3)


class LaneScopesEveryStage(FlagTest):
    """`--lane` scopes every stage, not just ingest.

    The old behaviour passed lane only to `ingest.run()`, so enrich, qualify,
    personas and generate worked on every record in the queue regardless of
    lane. An operator who passed `--lane domains` expected only domains-lane
    records to be processed.
    """

    def test_lane_filters_targets_for_enrich(self):
        """Records in other lanes are not enriched when --lane is set."""
        records = [
            self._make_record("dom-001", lane="domains"),
            self._make_record("dom-002", lane="domains"),
            self._make_record("cold-001", lane="cold"),
            self._make_record("rev-001", lane="revive"),
        ]
        self._seed_queue(records)

        report = run_mod.run(lane="domains", stages=("enrich",))
        # Only the 2 domains-lane records should be enriched
        self.assertEqual(report["enrich"]["records"], 2)

    def test_lane_filters_targets_for_qualify(self):
        """Records in other lanes are not qualified when --lane is set."""
        records = [
            self._make_record("dom-001", lane="domains"),
            self._make_record("cold-001", lane="cold"),
            self._make_record("cold-002", lane="cold"),
        ]
        self._seed_queue(records)

        # Mock qualify.company so it doesn't need a full config
        from src import qualify
        with mock.patch.object(qualify, "company", return_value={"record": {}}):
            report = run_mod.run(lane="domains", stages=("qualify",))
        self.assertEqual(report["qualify"]["records"], 1)

    def test_no_lane_processes_all(self):
        """Without --lane, every record is processed."""
        records = [
            self._make_record("dom-001", lane="domains"),
            self._make_record("cold-001", lane="cold"),
            self._make_record("rev-001", lane="revive"),
        ]
        self._seed_queue(records)

        report = run_mod.run(stages=("enrich",))
        self.assertEqual(report["enrich"]["records"], 3)

    def test_lane_combined_with_limit(self):
        """--lane and --limit compose: lane filters first, then limit."""
        records = [
            self._make_record("dom-001", lane="domains"),
            self._make_record("dom-002", lane="domains"),
            self._make_record("dom-003", lane="domains"),
            self._make_record("cold-001", lane="cold"),
            self._make_record("cold-002", lane="cold"),
        ]
        self._seed_queue(records)

        report = run_mod.run(lane="domains", limit=2, stages=("enrich",))
        # 3 domains records, limit 2 -> 2 processed
        self.assertEqual(report["enrich"]["records"], 2)


class CapBoundsSpend(FlagTest):
    """`--cap` bounds the credit spend.

    This is the one flag with money behind it. `enrich.require_cap` refuses
    a spend run with no cap. `enrich.Budget` refuses calls that would exceed
    it. This test proves the refusal against a fake provider.
    """

    def test_require_cap_refuses_spend_without_cap(self):
        """--spend without --cap is refused."""
        from src import enrich
        with self.assertRaises(enrich.NoBudget):
            enrich.require_cap(live=True, cap=None)

    def test_require_cap_accepts_spend_with_cap(self):
        """--spend with --cap is accepted."""
        from src import enrich
        self.assertTrue(enrich.require_cap(live=True, cap=100))

    def test_require_cap_accepts_cap_zero(self):
        """--cap 0 is accepted and means plan without spending."""
        from src import enrich
        self.assertTrue(enrich.require_cap(live=True, cap=0))

    def test_require_cap_accepts_dry_run_without_cap(self):
        """Dry run (spend=False) without cap is accepted."""
        from src import enrich
        self.assertTrue(enrich.require_cap(live=False, cap=None))

    def test_budget_refuses_call_over_cap(self):
        """Budget refuses a call that would exceed the cap."""
        from src import enrich
        budget = enrich.Budget(cap=5)
        # First call: 3 credits, affordable
        self.assertTrue(budget.charge(3, "rec1:decision-makers"))
        self.assertEqual(budget.spent, 3)
        # Second call: 3 more credits, would exceed cap of 5
        self.assertFalse(budget.charge(3, "rec2:decision-makers"))
        self.assertEqual(budget.spent, 3)
        self.assertEqual(len(budget.refused), 1)

    def test_budget_allows_call_within_cap(self):
        """Budget allows a call that fits within the cap."""
        from src import enrich
        budget = enrich.Budget(cap=10)
        self.assertTrue(budget.charge(3, "rec1:decision-makers"))
        self.assertTrue(budget.charge(3, "rec2:decision-makers"))
        self.assertEqual(budget.spent, 6)
        self.assertEqual(len(budget.refused), 0)

    def test_budget_exact_cap(self):
        """A call that exactly reaches the cap is allowed."""
        from src import enrich
        budget = enrich.Budget(cap=5)
        self.assertTrue(budget.charge(5, "rec1:company-info"))
        self.assertEqual(budget.spent, 5)
        # Next call is refused
        self.assertFalse(budget.charge(1, "rec2:email-verifier"))

    def test_budget_zero_cap_refuses_priced_calls(self):
        """--cap 0 refuses every priced call."""
        from src import enrich
        budget = enrich.Budget(cap=0)
        self.assertFalse(budget.charge(1, "rec1:email-verifier"))
        self.assertEqual(budget.spent, 0)

    def test_budget_zero_cap_refuses_unpriced_calls(self):
        """--cap 0 also refuses unpriced calls (Apify research).

        A cap of zero means 'spend nothing'. An unpriced call costs 0 credits
        by arithmetic but burns real Apify compute. Without this check,
        --cap 0 would start billable actor runs while reporting clean.
        """
        from src import enrich
        budget = enrich.Budget(cap=0)
        self.assertFalse(budget.affordable(0, call="apify-research"))

    def test_budget_refund_returns_credits(self):
        """A provider that declines to charge gets a refund."""
        from src import enrich
        budget = enrich.Budget(cap=10)
        budget.charge(5, "rec1:decision-makers")
        self.assertEqual(budget.spent, 5)
        budget.refund(5)
        self.assertEqual(budget.spent, 0)
        # Now the full cap is available again
        self.assertTrue(budget.charge(10, "rec2:decision-makers"))

    def test_stage_enrich_stops_at_cap(self):
        """The enrich stage stops spending when the cap is reached.

        This drives through the real stage_enrich entry point with a fake
        budget, proving the cap is enforced at the stage level, not just
        in the Budget class.
        """
        from src import enrich

        records = []
        for i in range(5):
            rid = f"rec-{i:03d}"
            rec = self._make_record(rid, domain=f"acme{i}.test")
            records.append(rec)
        self._seed_queue(records)

        # Run enrich in dry-run mode (spend=False) with a low cap.
        # In dry-run mode, the stage plans calls and charges the budget
        # without actually calling providers.
        notes = []
        result = run_mod.stage_enrich(records, spend=False, cap=2, notes=notes)
        # The stage should have planned calls and charged the budget
        # The exact number depends on the plan, but the budget should
        # not exceed the cap
        self.assertLessEqual(result["spent"], 2)


class RecordHasWork(unittest.TestCase):
    """Unit tests for the `record_has_work` predicate.

    This is the function that decides which records count against `--limit`.
    It must agree with what the stages themselves decide.
    """

    def _rec(self, stages=None, state="queued"):
        rec = {"id": "test", "state": state, "contacts": []}
        if stages:
            rec["stages"] = stages
        return rec

    def test_fresh_record_has_work(self):
        rec = self._rec()
        self.assertTrue(run_mod.record_has_work(rec, ("enrich",)))

    def test_done_record_has_no_work(self):
        rec = self._rec(stages={"enrich": {"status": "done"}})
        self.assertFalse(run_mod.record_has_work(rec, ("enrich",)))

    def test_terminal_record_has_no_work(self):
        rec = self._rec(state="dropped")
        self.assertFalse(run_mod.record_has_work(rec, ("enrich",)))

    def test_pushed_record_has_no_work(self):
        rec = self._rec(state="pushed")
        self.assertFalse(run_mod.record_has_work(rec, ("enrich",)))

    def test_partial_record_has_work(self):
        rec = self._rec(stages={"enrich": {"status": "partial"}})
        self.assertTrue(run_mod.record_has_work(rec, ("enrich",)))

    def test_failed_record_has_work(self):
        rec = self._rec(stages={"enrich": {"status": "failed"}})
        self.assertTrue(run_mod.record_has_work(rec, ("enrich",)))

    def test_batch_stage_ignored(self):
        """render and push are batch-level; they don't make a record active."""
        rec = self._rec(stages={"enrich": {"status": "done"}})
        # Only render in stages - no per-record stage needs work
        self.assertFalse(run_mod.record_has_work(rec, ("render",)))

    def test_multiple_stages_any_active(self):
        """Record is active if ANY per-record stage needs work."""
        rec = self._rec(stages={"enrich": {"status": "done"}})
        # enrich is done, but qualify is not
        self.assertTrue(run_mod.record_has_work(rec, ("enrich", "qualify")))

    def test_qualify_rework_via_fingerprint(self):
        """Qualify done but fingerprint changed -> has work."""
        rec = self._rec(stages={
            "enrich": {"status": "done"},
            "qualify": {"status": "done"},
        })
        rec["company_facts"] = {"headcount_signal": 50}
        rec["qualification"] = {
            "inputs_fingerprint": "stale-fingerprint",
        }
        # The current facts produce a different fingerprint than what's stored
        self.assertTrue(run_mod.record_has_work(rec, ("qualify",)))

    def test_personas_unkeyed_contacts(self):
        """Personas done but contacts lack keys -> has work."""
        rec = self._rec(stages={
            "enrich": {"status": "done"},
            "personas": {"status": "done"},
        })
        rec["contacts"] = [{"email": "test@example.test"}]  # no key
        self.assertTrue(run_mod.record_has_work(rec, ("personas",)))


if __name__ == "__main__":
    unittest.main()
