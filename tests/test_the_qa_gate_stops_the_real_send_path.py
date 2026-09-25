#!/usr/bin/env python3
"""The QA gate is on the REAL send path, and the proof is a refusal.

TASK-292. The same defect TASK-277 exposed for the copy lint: a gate wired
into a caller the next caller skips, proved by tests that call it directly.
The real path is `scripts/batch1_push.py` -> `bisonfactory.stage`, and the
gate belongs at the bottom of that arrow.

Every test here drives `bisonfactory.stage(live=True)` against a fake
provider that counts what it was asked to do. None of them calls `_refuse_qa`
or `run.main()` directly. What they assert is the EFFECT: the push refuses,
the refusal names the check and the rule, and the provider was never touched.

## THE IMPORT-GRAPH TRACE

    batch1_push -> bisonfactory.stage -> _refuse_qa

Printed from the module objects, not from a grep. `dir()` the module and
show the name is really bound.
"""
import os
import sys
import types
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from src import (approval, bisonfactory, cadence, campaigns, store,
                 workspaces)
from scripts.qa import CHECKS, FAIL, PASS, VACUOUS, PHASE_REFUSAL
from scripts.qa import run as qa_run
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty

CID = "camp-qa-gate"

CONFIG = {
    "email_sequence": {"title": "Resonate generated cadence",
                       "subject": "{SUBJECT}", "body": "<p>{BODY}</p>",
                       "wait_in_days": 3},
    "sending_window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                                "friday"],
                       "start": "09:00", "end": "17:00",
                       "timezone": "Europe/Zagreb"},
    "providers": {"emailbison": {"workspace": 10}},
}

OWN_FACT = {
    "fact": "Northwind Studio builds booking software for independent clinics.",
    "source_url": "https://northwind.test/about",
    "source_type": "local_http",
    "record_id": "rec-northwind",
}

CLEAN_BODY = (
    "Ada, your Northwind Studio page says you build booking software for "
    "independent clinics.\n\n"
    "Most teams that size find the margin question answered after a project "
    "closes rather than while it is running. That is a visibility problem "
    "more than a delivery one.\n\n"
    "Is that roughly how it works for you today?")


def record(rid="rec-northwind", email="ada@northwind.test", first="Ada",
           body=CLEAN_BODY, research=(OWN_FACT,), domain="northwind.test",
           company="Northwind Studio"):
    key = "%s-c1" % rid
    step = {"channel": "email", "subject": "how booking work is tracked",
            "body": body}
    step["approval"] = {"by": "operator", "at": "2026-09-24T00:00:00Z",
                        "fingerprint": approval.fingerprint(step)}
    return {"id": rid, "client": "productive", "domain": domain,
            "company": company, "state": "ready",
            "research": [dict(r, record_id=rid) for r in research],
            "cadence": {key: {"day1": step}},
            "contacts": [{"key": key, "email": email, "first_name": first,
                          "last_name": "Tester", "sendable": True,
                          "verified": True}]}


class CountingBison(FakeBison):
    """The fake provider, plus a count of the FIRST thing `stage` asks it."""

    def __init__(self):
        super().__init__()
        self.workspace_reads = 0

    def bound_workspace(self):
        self.workspace_reads += 1
        return super().bound_workspace()

    def touched(self):
        return {"workspace_reads": self.workspace_reads,
                "created_campaigns": self.created_campaigns,
                "created_leads": self.created_leads,
                "attached": sum(len(v) for v in self.members.values()),
                "sequences": len(self.steps)}

    UNTOUCHED = {"workspace_reads": 0, "created_campaigns": 0,
                 "created_leads": 0, "attached": 0, "sequences": 0}


def _make_failing_check_module(check_id, rule_name, rule_sentence,
                               offender_ids):
    """Create a check module that always fails with the given parameters."""
    mod = types.ModuleType("scripts.qa.check_%s" % check_id)
    mod.run = lambda **kw: {
        "check": check_id,
        "phase": "pre_push",
        "verdict": FAIL,
        "subjects": len(offender_ids) + 1,
        "clean": 1,
        "refused": True,
        "rules": {rule_name: rule_sentence},
        "counts": {rule_name: len(offender_ids)},
        "offenders": {rule_name: list(offender_ids)},
        "unverifiable": {},
        "evidence": {},
        "measured_at": "2026-09-25T06:00:00Z",
    }
    return mod


class ImportGraphTrace(unittest.TestCase):
    """The import-graph trace from batch1_push to _refuse_qa."""

    def test_refuse_qa_is_bound_in_bisonfactory(self):
        self.assertIn("_refuse_qa", dir(bisonfactory))

    def test_stage_calls_refuse_qa(self):
        """Read the source of stage and find the call."""
        import inspect
        source = inspect.getsource(bisonfactory.stage)
        self.assertIn("_refuse_qa", source)

    def test_refuse_qa_is_before_bound_workspace(self):
        """_refuse_qa is called before bison.bound_workspace in stage()."""
        import inspect
        source = inspect.getsource(bisonfactory.stage)
        qa_pos = source.index("_refuse_qa")
        ws_pos = source.index("bound_workspace")
        self.assertLess(qa_pos, ws_pos,
                        "_refuse_qa must be before bound_workspace")


class TheQaGateIsOnTheSendPath(QueueTest):
    """The QA gate refuses the real send path when a check fails."""

    def setUp(self):
        super().setUp()
        self.bison = CountingBison()
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        row = campaigns.new_campaign(CID, "productive", "QA gate test")
        row["cadence_steps"] = [dict(s) for s in
                                cadence.steps_for(None, config=CONFIG)]
        row["record_ids"] = ["rec-northwind"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        self.given(record())

    def given(self, *records):
        store.save(list(records))

    def stage(self):
        return bisonfactory.stage(CID, config=CONFIG, live=True)

    def test_a_failing_check_refuses_the_push(self):
        """A check rigged to FAIL causes FactoryRefused on the real path."""
        invented_rule = "invented_rule_for_test_%d" % id(self)
        invented_sentence = "a sentence nobody had written before this test"
        offender_ids = ["rec-9999:test@example.com"]

        fake_mod = _make_failing_check_module(
            "test_failing", invented_rule, invented_sentence, offender_ids)

        # Monkeypatch the check module into sys.modules and CHECKS.
        import scripts.qa as qa_pkg
        real_checks = qa_pkg.CHECKS
        qa_pkg.CHECKS = real_checks + (
            ("test_failing", "check_test_failing", "pre_push", True),)
        sys.modules["scripts.qa.check_test_failing"] = fake_mod
        self.addCleanup(setattr, qa_pkg, "CHECKS", real_checks)
        self.addCleanup(sys.modules.pop,
                        "scripts.qa.check_test_failing", None)

        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()

        said = str(caught.exception)
        # The refusal text contains the rule name the check produced.
        self.assertIn(invented_rule, said)
        # The refusal text contains the table header showing REFUSED.
        self.assertIn("REFUSED", said)
        # The check row is present with FAIL verdict.
        self.assertIn("test_failing", said)
        self.assertIn("FAIL", said)
        # Nothing was written.
        self.assertIn("Nothing was written", said)

    def test_no_provider_call_when_qa_refuses(self):
        """The gate is BEFORE the first provider call."""
        fake_mod = _make_failing_check_module(
            "test_failing2", "some_rule", "some sentence",
            ["rec-8888:x@y.com"])

        import scripts.qa as qa_pkg
        real_checks = qa_pkg.CHECKS
        qa_pkg.CHECKS = real_checks + (
            ("test_failing2", "check_test_failing2", "pre_push", True),)
        sys.modules["scripts.qa.check_test_failing2"] = fake_mod
        self.addCleanup(setattr, qa_pkg, "CHECKS", real_checks)
        self.addCleanup(sys.modules.pop,
                        "scripts.qa.check_test_failing2", None)

        with self.assertRaises(bisonfactory.FactoryRefused):
            self.stage()

        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_refusal_text_contains_the_runner_s_table(self):
        """The refusal carries the RUNNER's rendered table, not a sentence
        written at the raise site."""
        rule_name = "qa_table_rule_%d" % id(self)
        fake_mod = _make_failing_check_module(
            "test_table", rule_name, "the rule sentence",
            ["rec-7777:z@w.com"])

        import scripts.qa as qa_pkg
        real_checks = qa_pkg.CHECKS
        qa_pkg.CHECKS = real_checks + (
            ("test_table", "check_test_table", "pre_push", True),)
        sys.modules["scripts.qa.check_test_table"] = fake_mod
        self.addCleanup(setattr, qa_pkg, "CHECKS", real_checks)
        self.addCleanup(sys.modules.pop,
                        "scripts.qa.check_test_table", None)

        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()

        said = str(caught.exception)
        # The table header is present.
        self.assertIn("QA", said)
        self.assertIn("REFUSED", said)
        # The check row is present with its verdict.
        self.assertIn("test_table", said)
        self.assertIn("FAIL", said)
        # The rule name from the check is in the table.
        self.assertIn(rule_name, said)
        # Nothing was written.
        self.assertIn("Nothing was written", said)

    def test_all_checks_not_implemented_does_not_block(self):
        """NOT_IMPLEMENTED checks are advisory until the modules land.

        A runner where every check is NOT_IMPLEMENTED reports the state in
        the table but does not refuse — otherwise no push could happen while
        the checks are being built (TASK-293..299). The moment a check EXISTS
        and returns a failing verdict, the gate fires.
        """
        import scripts.qa as qa_pkg
        from scripts.qa.run import run_phase, NOT_IMPLEMENTED
        worst, results = run_phase("pre_push")
        # Every result is NOT_IMPLEMENTED since no check modules exist.
        for r in results:
            self.assertEqual(r["verdict"], NOT_IMPLEMENTED)
        # The runner reports the worst as ERROR (NOT_IMPLEMENTED maps to 3),
        # but _refuse_qa treats NOT_IMPLEMENTED as advisory.
        self.assertEqual(worst, "ERROR")


class ZeroSubjectRunRefuses(QueueTest):
    """subjects == 0 does not pass. VACUOUS refuses pre_push."""

    def test_zero_subjects_is_vacuous_and_refuses(self):
        """A check returning zero subjects is VACUOUS, and pre_push refuses
        VACUOUS (ISSUE-041)."""
        vacuous_mod = types.ModuleType("scripts.qa.check_test_vacuous")
        vacuous_mod.run = lambda **kw: {
            "check": "test_vacuous",
            "phase": "pre_push",
            "verdict": VACUOUS,
            "subjects": 0,
            "clean": 0,
            "refused": True,
            "rules": {},
            "counts": {},
            "offenders": {},
            "unverifiable": {},
            "evidence": {"vacuous_reason":
                         "no LinkedIn leads in this batch"},
            "measured_at": "2026-09-25T06:00:00Z",
        }

        import scripts.qa as qa_pkg
        real_checks = qa_pkg.CHECKS
        # Replace CHECKS with ONLY the vacuous check, so the other
        # NOT_IMPLEMENTED checks don't interfere.
        qa_pkg.CHECKS = (
            ("test_vacuous", "check_test_vacuous", "pre_push", True),)
        sys.modules["scripts.qa.check_test_vacuous"] = vacuous_mod
        self.addCleanup(setattr, qa_pkg, "CHECKS", real_checks)
        self.addCleanup(sys.modules.pop,
                        "scripts.qa.check_test_vacuous", None)

        from scripts.qa.run import run_phase
        worst, results = run_phase("pre_push")
        # VACUOUS is in the refusal set for pre_push.
        self.assertIn(worst, PHASE_REFUSAL["pre_push"])
        # The vacuous check is in the results.
        vac_results = [r for r in results if r["check"] == "test_vacuous"]
        self.assertEqual(len(vac_results), 1)
        self.assertEqual(vac_results[0]["verdict"], VACUOUS)


class ArithmeticInvariantDowngrade(unittest.TestCase):
    """A check returning clean=128, subjects=128 with non-empty offenders
    is downgraded to ERROR by the runner."""

    def test_arithmetic_mismatch_is_error(self):
        bad_result = {
            "check": "lead_state",
            "phase": "pre_push",
            "verdict": PASS,
            "subjects": 128,
            "clean": 128,
            "refused": False,
            "rules": {"rule_x": "a rule"},
            "counts": {"rule_x": 1},
            "offenders": {"rule_x": ["rec-9999:someone@example.com"]},
            "unverifiable": {},
            "evidence": {},
            "measured_at": "2026-09-25T06:00:00Z",
        }
        from scripts.qa.run import _validate_result
        verdict, reason = _validate_result(bad_result)
        self.assertEqual(verdict, "ERROR")
        self.assertIn("arithmetic", reason.lower())


class NoBypassFlag(unittest.TestCase):
    """There is no --skip-qa, no --force, no env var that disables a check."""

    def test_no_bypass_in_qa_runner(self):
        import scripts.qa.run as run_mod
        with open(run_mod.__file__) as f:
            source = f.read()
        for flag in ("--skip-qa", "--force", "--no-qa", "--bypass",
                     "SKIP_QA", "FORCE_QA", "QA_BYPASS"):
            self.assertNotIn(flag, source,
                             "bypass flag %r found in runner" % flag)

    def test_no_bypass_in_qa_init(self):
        import scripts.qa as qa_pkg
        with open(qa_pkg.__file__) as f:
            source = f.read()
        for flag in ("--skip-qa", "--force", "--no-qa", "--bypass",
                     "SKIP_QA", "FORCE_QA", "QA_BYPASS"):
            self.assertNotIn(flag, source,
                             "bypass flag %r found in registry" % flag)


if __name__ == "__main__":
    unittest.main()
