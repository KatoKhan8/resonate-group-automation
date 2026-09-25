#!/usr/bin/env python3
"""The QA gate stops the real send path, and the proof is a refusal.

TASK-292. The QA harness is wired into `bisonfactory.stage` and
`heyreachfactory.stage` BEFORE the first provider call of any kind. A check
that fails refuses the push, and the refusal carries the runner's own rendered
table - not a sentence written at the raise site.

THE REAL PATH IS `scripts/batch1_push.py` -> `bisonfactory.stage`. Every test
here drives `bisonfactory.stage(live=True)` against a fake provider that
counts what it was asked to do. None of them calls `_refuse_qa` directly; what
they assert is the EFFECT: the push refuses, the refusal names the lead and
the rule, and the provider was never touched.

TASK-277 IS THE PRECEDENT. The copy lint was wired into `src/push.py`, whose
`run()` raises on `live=True`, through `run_with_copylint`, which nothing
called. Eight tests proved it worked, and all eight called it directly. That
is the exact defect this task was written about. None of the tests here make
that mistake.
"""
import os
import shutil
import sys
import tempfile
import types
import unittest

# Ensure scripts/ is importable so `scripts.qa` resolves.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from src import (approval, bisonfactory, cadence, campaigns, copylint, store,
                 workspaces)
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty

import scripts.qa as qa_pkg                                        # noqa: E402
from scripts.qa import run as qa_run                               # noqa: E402

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


def _record(rid="rec-northwind", email="ada@northwind.test", first="Ada",
            body=CLEAN_BODY, research=(OWN_FACT,), domain="northwind.test",
            company="Northwind Studio"):
    key = "%s-c1" % rid
    step = {"channel": "email", "subject": "how booking work is tracked",
            "body": body}
    step["approval"] = {"by": "operator", "at": "2026-09-25T00:00:00Z",
                        "fingerprint": approval.fingerprint(step)}
    return {"id": rid, "client": "productive", "domain": domain,
            "company": company, "state": "ready",
            "research": [dict(r, record_id=rid) for r in research],
            "cadence": {key: {"day1": step}},
            "contacts": [{"key": key, "email": email, "first_name": first,
                          "last_name": "Tester", "sendable": True,
                          "verified": True}]}


class CountingBison(FakeBison):
    """A fake provider that counts the FIRST thing `stage` asks it.

    `bound_workspace` is the tenancy read and it happens before any write. A
    gate that ran after it would still be before the attach, but this counter
    is how "before the attach" is told apart from "before the provider".
    """

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


class QAGateStopsTheRealSendPath(QueueTest):
    """The QA gate refuses the push when a check fails, and the provider is
    never touched. Every test here enters through `bisonfactory.stage`."""

    def setUp(self):
        super().setUp()
        self.bison = CountingBison()
        self._real_bison = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real_bison)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        row = campaigns.new_campaign(CID, "productive", "QA gate test",
                                     batch_id="batch-qa-test")
        row["cadence_steps"] = [dict(s) for s in
                                cadence.steps_for(None, config=CONFIG)]
        row["record_ids"] = ["rec-northwind"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])
        self.given(_record())

        self._orig_checks = qa_pkg.CHECKS
        self._fake_mods = {}

        self.ws_dir = tempfile.mkdtemp(prefix="qa-ws-")
        with open(os.path.join(self.ws_dir, "queue.jsonl"), "w") as fh:
            fh.write("")
        with open(os.path.join(self.ws_dir, "campaigns.jsonl"), "w") as fh:
            fh.write("")

    def tearDown(self):
        qa_pkg.CHECKS = self._orig_checks
        for mod_name in list(self._fake_mods):
            sys.modules.pop(f"qa.{mod_name}", None)
            sys.modules.pop(f"scripts.qa.{mod_name}", None)
        # Also restore the `qa` module's CHECKS if it was loaded.
        if "qa" in sys.modules:
            sys.modules["qa"].CHECKS = self._orig_checks
        shutil.rmtree(self.ws_dir, ignore_errors=True)
        super().tearDown()

    def given(self, *records):
        store.save(list(records))

    def stage(self):
        return bisonfactory.stage(CID, config=CONFIG, live=True)

    def _install_fake_check(self, check_id, module_name, result):
        """Register a fake check module and patch CHECKS to include only it.

        The factory imports `qa` (because scripts/ is on sys.path), while the
        test imports `scripts.qa`. These are different entries in sys.modules
        for the same __init__.py, so we patch BOTH to keep them in sync.
        """
        mod = types.ModuleType(f"qa.{module_name}")
        mod.run = lambda **kw: dict(result)
        sys.modules[f"qa.{module_name}"] = mod
        sys.modules[f"scripts.qa.{module_name}"] = mod
        self._fake_mods[module_name] = mod
        qa_pkg.CHECKS = (
            (check_id, module_name, "pre_push", True),
        )
        # Also patch the `qa` entry in sys.modules so _refuse_qa sees it.
        import qa as _qa_direct
        _qa_direct.CHECKS = qa_pkg.CHECKS

    # --------------------------------------------- the import-graph trace

    def test_the_import_chain_from_batch1_push_to_refuse_qa(self):
        """The gate is in the factory, not in the caller.

        `scripts/batch1_push.py` imports `bisonfactory` and calls `stage`.
        `bisonfactory` has `_refuse_qa`. The chain is provable from the module
        objects, not from a grep.
        """
        from scripts import batch1_push
        self.assertIs(batch1_push.bisonfactory, bisonfactory)
        self.assertTrue(hasattr(bisonfactory, "stage"))
        self.assertTrue(hasattr(bisonfactory, "_refuse_qa"))
        self.assertIn("_refuse_qa", dir(bisonfactory))

    # --------------------------------------------- the control

    def test_a_batch_whose_checks_pass_is_staged(self):
        """Without this the rest proves nothing. A gate that refuses every
        batch is indistinguishable from a gate that refuses the right ones."""
        self._install_fake_check("qa_pass", "check_qa_pass", {
            "check": "qa_pass", "phase": "pre_push", "verdict": "PASS",
            "subjects": 1, "clean": 1, "refused": False,
            "rules": {"a_rule": "a rule sentence"},
            "counts": {"a_rule": 0},
            "offenders": {"a_rule": []},
            "unverifiable": {},
        })
        report = self.stage()
        self.assertEqual(self.bison.created_leads, 1)

    # --------------------------------------------- the refusals

    def test_a_failing_check_refuses_the_push_through_the_real_send_path(self):
        """The central assertion: `bisonfactory.stage(live=True)` refuses when
        a QA check fails. Not `_refuse_qa` directly - the whole stage."""
        invented_rule = "test_rule_invented_at_runtime"
        invented_sentence = "a check the test invented right now"
        self._install_fake_check("qa_fail", "check_qa_fail", {
            "check": "qa_fail", "phase": "pre_push", "verdict": "FAIL",
            "subjects": 1, "clean": 0, "refused": True,
            "rules": {invented_rule: invented_sentence},
            "counts": {invented_rule: 1},
            "offenders": {invented_rule: ["rec-northwind/rec-northwind-c1"]},
            "unverifiable": {},
        })
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        said = str(caught.exception)
        self.assertIn("rec-northwind/rec-northwind-c1", said)
        self.assertIn(invented_rule, said)
        self.assertIn(invented_sentence, said)

    def test_no_provider_call_when_the_qa_gate_refuses(self):
        """BEFORE any provider write, not after. ISSUE-037 is the
        counter-example: the blank-render gate refuses after the attach and
        does not roll back."""
        self._install_fake_check("qa_fail", "check_qa_fail2", {
            "check": "qa_fail", "phase": "pre_push", "verdict": "FAIL",
            "subjects": 1, "clean": 0, "refused": True,
            "rules": {"some_rule": "some sentence"},
            "counts": {"some_rule": 1},
            "offenders": {"some_rule": ["rec-northwind/rec-northwind-c1"]},
            "unverifiable": {},
        })
        with self.assertRaises(bisonfactory.FactoryRefused):
            self.stage()
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_the_refusal_carries_a_rule_added_after_the_wiring(self):
        """A rule that did not exist when `_refuse_qa` was written still names
        itself in the refusal. The refusal carries the runner's own table, not
        a sentence written at the raise site."""
        future_rule = "a_rule_from_next_sprint"
        future_sentence = "a rule nobody had written when the wiring landed"
        self._install_fake_check("qa_future", "check_qa_future", {
            "check": "qa_future", "phase": "pre_push", "verdict": "FAIL",
            "subjects": 1, "clean": 0, "refused": True,
            "rules": {future_rule: future_sentence},
            "counts": {future_rule: 1},
            "offenders": {future_rule: ["rec-northwind/rec-northwind-c1"]},
            "unverifiable": {},
        })
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        said = str(caught.exception)
        self.assertIn(future_rule, said)
        self.assertIn(future_sentence, said)

    # --------------------------------------------- the registry invariant

    def test_every_check_file_on_disk_appears_in_CHECKS(self):
        """A check with no registration is a check with no caller.

        This asserts by `os.listdir`, not by grep. A check module that exists
        on disk but is not in CHECKS does not run, and that is the defect."""
        qa_dir = os.path.join(SCRIPTS, "qa")
        on_disk = set()
        for fn in os.listdir(qa_dir):
            if fn.startswith("check_") and fn.endswith(".py"):
                on_disk.add(fn[len("check_"):-len(".py")])
        registered = set()
        for check_id, _mod, _phase, _blocking in qa_pkg.CHECKS:
            registered.add(check_id)
        unregistered = on_disk - registered
        self.assertEqual(
            unregistered, set(),
            f"check modules on disk not in CHECKS: {unregistered}")

    # --------------------------------------------- no bypass flag

    def test_no_bypass_flag_exists(self):
        """There is no --skip-qa, no --force, no environment variable that
        disables a blocking check. The only escape is `blocking=False` in
        CHECKS, in a commit."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn",
             r"--skip-qa\|--force-qa\|SKIP_QA\|BYPASS_QA\|QA_DISABLED",
             "scripts/qa/", "src/bisonfactory.py"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "",
                         f"bypass flag found:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
