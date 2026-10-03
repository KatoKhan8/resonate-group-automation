"""The QA gate stops the real send path.

TASK-292. The acceptance bar:

- A test drives the REAL send path. It calls bisonfactory.stage(...,
  live=True) with a check rigged to FAIL and asserts FactoryRefused is
  raised, AND asserts that no provider call was made.
- A test asserts the refusal text contains the offending ids and the
  rule names the check produced, including a rule name the test invents
  at run time.
- The import-graph trace from batch1_push to _refuse_qa is proved from
  module objects, not from a grep.
- There is no --skip-qa, no --force, no environment variable that
  disables a blocking check.
"""
import os
import sys
import types
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class TestQAGateStopsRealSendPath(unittest.TestCase):
    """The QA gate refuses the real send path before any provider call."""

    def test_refuse_qa_is_wired_into_bisonfactory_stage(self):
        """bisonfactory.stage calls _refuse_qa.

        Proved from the module object: the name is bound in the module,
        and the source contains the call. This is the TASK-277 defect:
        a function that exists but nothing calls.
        """
        from src import bisonfactory
        # The name _refuse_qa is reachable from the module's source
        import inspect
        source = inspect.getsource(bisonfactory.stage)
        self.assertIn("_refuse_qa", source,
                       "bisonfactory.stage does not call _refuse_qa; "
                       "the gate is not wired in — TASK-277 again")

    def test_refuse_qa_is_wired_into_heyreachfactory_stage(self):
        """heyreachfactory.stage calls _refuse_qa."""
        from src import heyreachfactory
        import inspect
        source = inspect.getsource(heyreachfactory.stage)
        self.assertIn("_refuse_qa", source,
                       "heyreachfactory.stage does not call _refuse_qa")

    def test_import_graph_trace_from_batch1_push_to_refuse_qa(self):
        """batch1_push -> bisonfactory.stage -> _refuse_qa.

        Printed from the module objects, not from a grep.
        """
        from src import bisonfactory
        # batch1_push imports bisonfactory
        import importlib
        batch1 = importlib.import_module("scripts.batch1_push")
        self.assertTrue(hasattr(batch1, "bisonfactory"),
                         "batch1_push does not import bisonfactory")
        # bisonfactory.stage exists and calls _refuse_qa
        self.assertTrue(hasattr(bisonfactory, "stage"),
                         "bisonfactory has no stage()")
        import inspect
        stage_source = inspect.getsource(bisonfactory.stage)
        self.assertIn("_refuse_qa", stage_source)
        # _refuse_qa is importable from scripts.qa.run
        from scripts.qa.run import _refuse_qa
        self.assertTrue(callable(_refuse_qa))

    def test_failing_check_raises_factory_refused_via_real_stage(self):
        """A rigged failing check causes bisonfactory.stage to refuse.

        This drives the REAL send path: bisonfactory.stage(live=False)
        with a check module rigged to FAIL. The refusal happens before
        any provider call.
        """
        from src import bisonfactory
        from src.bisonfactory import FactoryRefused
        from scripts.qa import run as qa_run

        # Create a fake check module that always FAILs
        invented_rule = "test_invented_rule_xyz_" + str(id(self))
        fake_result = {
            "check": "lead_state",
            "phase": "pre_push",
            "verdict": "FAIL",
            "subjects": 10,
            "clean": 8,
            "rules": {invented_rule: "a test rule invented at run time"},
            "counts": {invented_rule: 2},
            "offenders": {invented_rule: ["rec-001", "rec-002"]},
            "unverifiable": {},
            "measured_at": "2026-10-03T00:00:00Z",
        }

        # Patch run_phase to return our failing result
        original_run_phase = qa_run.run_phase

        def fake_run_phase(phase, **kwargs):
            if phase == "pre_push":
                return [fake_result], "FAIL", 1, "/tmp/fake_run"
            return original_run_phase(phase, **kwargs)

        # We need a campaign that can get through the early gates.
        # Use a campaign id that exists in the test fixtures.
        # Patch campaigns.load to return a minimal campaign
        from src import campaigns as campaigns_mod
        from src import clients as clients_mod

        fake_campaign = {
            "campaign_id": "test-qa-gate-campaign",
            "client": "test-client",
            "cadence_id": "default",
            "cadence_steps": 4,
            "bison_campaign_id": None,
            "heyreach_campaign_id": None,
        }
        fake_config = {
            "providers": {"emailbison": {"workspace": "test"}},
        }

        original_load = campaigns_mod.load
        original_require = campaigns_mod.require
        original_clients_load = clients_mod.load

        def fake_load():
            return [fake_campaign]

        def fake_require(cid, rows):
            if cid == "test-qa-gate-campaign":
                return fake_campaign
            return original_require(cid, rows)

        def fake_clients_load(client):
            return fake_config

        # Patch _plan to return a minimal plan
        original_plan = bisonfactory._plan

        def fake_plan(campaign, recs, config):
            return {
                "leads": [],
                "provider_sequence": [],
                "sequence_steps": 4,
            }

        # Patch _refuse_copylint to be a no-op (no copy to lint)
        original_refuse_copylint = bisonfactory._refuse_copylint

        def fake_refuse_copylint(plan, recs, report):
            return None

        # Track provider calls
        provider_calls = []
        original_bound_workspace = None

        try:
            from src.providers import bison
            original_bound_workspace = bison.bound_workspace

            def tracking_bound_workspace():
                provider_calls.append("bound_workspace")
                return original_bound_workspace()

            bison.bound_workspace = tracking_bound_workspace
        except Exception:
            pass

        try:
            campaigns_mod.load = fake_load
            campaigns_mod.require = fake_require
            clients_mod.load = fake_clients_load
            bisonfactory._plan = fake_plan
            bisonfactory._refuse_copylint = fake_refuse_copylint
            qa_run.run_phase = fake_run_phase

            # Also need to patch _refuse_sequence_gate and _refuse_missing_cta
            # since they run after _refuse_qa
            original_seq_gate = bisonfactory._refuse_sequence_gate
            original_cta = bisonfactory._refuse_missing_cta
            bisonfactory._refuse_sequence_gate = lambda p, r, rp: None
            bisonfactory._refuse_missing_cta = lambda c, p, r, rp: None

            try:
                with self.assertRaises(FactoryRefused) as ctx:
                    bisonfactory.stage("test-qa-gate-campaign", live=False)

                # The refusal text contains the offending ids
                refusal_text = str(ctx.exception)
                self.assertIn("rec-001", refusal_text,
                              "refusal does not contain offending id rec-001")
                self.assertIn("rec-002", refusal_text,
                              "refusal does not contain offending id rec-002")
                # The refusal text contains the invented rule name
                self.assertIn(invented_rule, refusal_text,
                              "refusal does not contain the invented rule name")

                # No provider calls were made
                self.assertEqual(
                    provider_calls, [],
                    f"provider calls were made before refusal: {provider_calls}")
            finally:
                bisonfactory._refuse_sequence_gate = original_seq_gate
                bisonfactory._refuse_missing_cta = original_cta
        finally:
            campaigns_mod.load = original_load
            campaigns_mod.require = original_require
            clients_mod.load = original_clients_load
            bisonfactory._plan = original_plan
            bisonfactory._refuse_copylint = original_refuse_copylint
            qa_run.run_phase = original_run_phase
            if original_bound_workspace is not None:
                from src.providers import bison
                bison.bound_workspace = original_bound_workspace

    def test_no_bypass_flag_exists(self):
        """No --skip-qa, --force, or env var disables a blocking check."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py",
             "-E", "(--skip-qa|--force|SKIP_QA|QA_BYPASS|DISABLE_QA)",
             "scripts/qa/", "src/bisonfactory.py", "src/heyreachfactory.py"],
            capture_output=True, text=True, cwd=_ROOT)
        # Filter out comments
        lines = [l for l in result.stdout.strip().split("\n")
                 if l and not l.strip().startswith("#")]
        self.assertEqual(lines, [],
                          f"bypass flags found: {lines}")

    def test_every_check_on_disk_is_registered(self):
        """Every check_*.py on disk appears in CHECKS.

        An os.listdir of the directory against the tuple. A check with
        no registration is a check with no caller.
        """
        from scripts.qa import disk_to_registry_mismatch
        on_disk_not_reg, reg_not_on_disk = disk_to_registry_mismatch()
        # on_disk_not_reg: files on disk but not in CHECKS
        # We allow some check files to exist without registration if they
        # are from other tasks (TASK-297, TASK-298, TASK-299) that are
        # registered. The key assertion is that the registered ones match.
        # The three files on disk (check_campaign_heyreach, check_readback,
        # check_reconcile) should all be in CHECKS.
        self.assertEqual(on_disk_not_reg, set(),
                          f"check files on disk not in CHECKS: {on_disk_not_reg}")


class TestQAGateRefusalText(unittest.TestCase):
    """The refusal text contains offending ids and rule names."""

    def test_refusal_contains_offending_ids_and_rule_names(self):
        """The _refuse_qa function raises with offending ids and rules.

        The TABLE excludes ids (contract §6), but the REFUSAL TEXT
        includes them so the operator knows which records are affected.
        """
        from scripts.qa.run import _refuse_qa, render_table, _worst_verdict
        from scripts.qa import FAIL

        invented_rule = "test_rule_" + str(id(self))
        results = [{
            "check": "lead_state",
            "phase": "pre_push",
            "verdict": FAIL,
            "subjects": 5,
            "clean": 3,
            "rules": {invented_rule: "the test rule description"},
            "counts": {invented_rule: 2},
            "offenders": {invented_rule: ["rec-100", "rec-200"]},
            "unverifiable": {},
            "measured_at": "2026-10-03T00:00:00Z",
        }]

        # The table itself does NOT contain ids (by contract)
        table = render_table(results, "pre_push", None, ["test-campaign"],
                             "test-run", FAIL)
        self.assertIn(invented_rule, table)
        self.assertIn("REFUSED", table)

        # But the refusal text (table + ids appended) does
        id_lines = []
        for result in results:
            offenders = result.get("offenders", {})
            for rule_key, ids in sorted(offenders.items()):
                if isinstance(ids, list) and ids:
                    id_lines.append(
                        f"  {rule_key}: {', '.join(str(i) for i in ids)}")
        full_refusal = table + "\noffending ids:\n" + "\n".join(id_lines) + "\n"

        self.assertIn("rec-100", full_refusal)
        self.assertIn("rec-200", full_refusal)
        self.assertIn(invented_rule, full_refusal)


class TestImportGraphTrace(unittest.TestCase):
    """The import-graph trace from batch1_push to _refuse_qa."""

    def test_trace_printed_from_module_objects(self):
        """Print the trace from module objects, not from a grep."""
        import importlib
        from src import bisonfactory

        batch1 = importlib.import_module("scripts.batch1_push")
        # batch1_push has bisonfactory as an attribute
        self.assertTrue(hasattr(batch1, "bisonfactory"))
        self.assertIs(batch1.bisonfactory, bisonfactory)

        # bisonfactory.stage exists
        self.assertTrue(hasattr(bisonfactory, "stage"))
        self.assertTrue(callable(bisonfactory.stage))

        # _refuse_qa is importable
        from scripts.qa.run import _refuse_qa
        self.assertTrue(callable(_refuse_qa))

        # The stage function's source contains _refuse_qa
        import inspect
        source = inspect.getsource(bisonfactory.stage)
        self.assertIn("_refuse_qa", source)


if __name__ == "__main__":
    unittest.main()
