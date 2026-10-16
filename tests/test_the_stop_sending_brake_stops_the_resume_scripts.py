#!/usr/bin/env python3
"""The STOP-SENDING brake stops the scripts that write - TASK 0210.

TASK 0210 wired twelve `haltfile.require_released()` consults into the
scripts that call providers directly (the paths the write door cannot
see, per pilotcaps/0160). The call-graph test proves the consults exist;
this module proves two representative ENTRY POINTS behave, driven
end-to-end through their own `main(["--live"])`, offline:

    scripts/batch_activate.py  gated_resume (:107-111): suppression,
                               then the killswitch, then the brake,
                               then the verb. A brake refusal prints
                               "REFUSED OperatorStop" per campaign.

    scripts/resume_487.py      the same gate pair before the window
                               (:279), then the brake inside the write
                               window (:304), one line before the verb.
                               A brake refusal gets its own words:
                               "BRAKE REFUSED", the file named, and
                               "delete the file to release it", exit 1.

WHY THE KILLSWITCH IS PATCHED PERMISSIVE HERE. The property under test
is the OPERATOR's brake, and a brake must fire when every machine gate
says yes - not only in the frozen world where the machine refuses first.
In this build the freeze refuses everything (`push.LiveSendNotEnabled`
refuses in code; the workspace has never been switched on - measured by
the premise test below), so `killswitch.require` is patched aside to
stand in for an approval that has never existed. Nothing else is
patched aside: suppression runs for real against the fixture store (a
clean campaign, so it passes), the transports are recorders, and
ProviderTest's network tripwire stays armed behind them. Delete the
brake file in the same harness and the verb IS reached - that control
is what makes the refusal the brake and not the fixture.

Born-red at HEAD (pre-0210): ImportError on `src.haltfile`. The
mutation proof re-derives the true born-red: with `haltfile` present
and the script wiring byte-reverted, the two refusal tests fail on
REACH - the verb is called with the file present.

NO TEST CREATES THE REAL FILE. `haltfile.STOP_SENDING_PATH` is patched
to a throwaway for every test.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import haltfile, killswitch, providerwrites  # noqa: E402
from src.providers import bison                       # noqa: E402
from tests.campaignbase import CampaignTest           # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import batch_activate as activate                     # noqa: E402
import resume_487 as recover                          # noqa: E402

WORKSPACE = "productive"
PREFIX = "productive-email-batch1-"
CANONICAL_ID = "productive-email-control-v3"


class _ResumeLedgerMixin:
    """Point the action ledger at a throwaway file. Never the real work/."""

    def _setup_ledger(self):
        self.ledger_tmp = tempfile.mkdtemp(prefix="rga-resume-ledger-")
        self.ledger_path = os.path.join(self.ledger_tmp,
                                        "provider-writes.jsonl")
        self._old_ledger = os.environ.get(
            providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.ledger_path
        self.addCleanup(self._restore_ledger)
        self.addCleanup(shutil.rmtree, self.ledger_tmp, ignore_errors=True)

    def _restore_ledger(self):
        if self._old_ledger is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = (
                self._old_ledger)


class _BrakeScriptBase(_ResumeLedgerMixin, CampaignTest):
    """Campaign fixture + a brake file at a THROWAWAY path + the freeze
    measured, not assumed. Both script harnesses below patch
    `killswitch.require` permissive for the reason the module docstring
    gives; this base is where that decision is pinned to a measurement."""

    def setUp(self):
        super().setUp()
        self._setup_ledger()
        self.brake_tmp = tempfile.mkdtemp(prefix="rga-brake-scripts-")
        self.addCleanup(shutil.rmtree, self.brake_tmp, ignore_errors=True)
        self.brake_path = os.path.join(self.brake_tmp, "STOP-SENDING")

    def _pull_brake(self):
        with open(self.brake_path, "wb") as handle:
            handle.write(b"")

    def _permissive_killswitch(self):
        """The freeze said yes: the stand-in for an approval that has never
        existed, so the brake is the only thing that can refuse."""
        return mock.patch("src.killswitch.require",
                          lambda **kwargs: None)


class BatchActivateBrake(_BrakeScriptBase):
    """scripts/batch_activate.py driven through main(["--live"])."""

    def _run_activate(self):
        reached = []

        def record_resume(provider_id, expect_leads=None):
            reached.append((provider_id, expect_leads))
            return {"status": "in_sequence"}

        provider_row = {"status": "paused", "total_leads": 2,
                        "emails_sent": 0, "bounced": 0, "unsubscribed": 0}
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(haltfile, "STOP_SENDING_PATH",
                                  self.brake_path), \
                self._permissive_killswitch(), \
                mock.patch.object(activate, "load_env", lambda: None), \
                mock.patch.object(activate, "mailbox_health", lambda: {}), \
                mock.patch.object(activate, "ROOT", self.tmp), \
                mock.patch.object(activate.time, "sleep",
                                  lambda seconds: None), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: dict(provider_row)), \
                mock.patch.object(bison, "scheduled_emails",
                                  lambda pid: []), \
                mock.patch.object(bison, "resume_campaign", record_resume):
            code = activate.main(["--live"])
        return code, out.getvalue(), reached

    def test_the_brake_refuses_every_resume_in_the_batch(self):
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=PREFIX + "alpha")
        self._pull_brake()

        _code, out, reached = self._run_activate()

        self.assertEqual(
            reached, [],
            "the operator's brake was pulled and batch_activate still "
            "called bison.resume_campaign")
        self.assertIn("REFUSED OperatorStop", out,
                      "a brake refusal is surfaced and NAMED as the "
                      "operator's stop, not as a provider error")
        self.assertIn("STOP-SENDING is present", out,
                      "the refusal carries the brake's own words")

    def test_without_the_file_the_same_run_reaches_the_verb(self):
        """The control, same harness, no brake file: the verb is reached,
        so the refusal above was the brake and not the fixture."""
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=PREFIX + "alpha")

        _code, _out, reached = self._run_activate()

        self.assertEqual(reached, [("9001", 2)],
                         "the control must reach the verb exactly once; "
                         "if it does not, the fixture or the patches "
                         "changed and the refusal test above is vacuous")


class Resume487Brake(_BrakeScriptBase):
    """scripts/resume_487.py driven through main(["--live"])."""

    def _run_recover(self):
        reached = []

        def record_resume(provider_id, expect_leads=None):
            reached.append((provider_id, expect_leads))
            return {"status": "in_sequence"}

        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(haltfile, "STOP_SENDING_PATH",
                                  self.brake_path), \
                self._permissive_killswitch(), \
                mock.patch.object(recover, "_setup_data_access",
                                  lambda: None), \
                mock.patch.object(recover, "window_gate", lambda: True), \
                mock.patch.object(recover, "truth_gate",
                                  lambda b: ({"status": "paused"},
                                             {"sending_paused": 10},
                                             {"timezone": "Europe/Zagreb"})), \
                mock.patch.object(recover, "copy_gate", lambda: True), \
                mock.patch.object(bison, "campaign",
                                  lambda pid: {"status": "in_sequence"}), \
                mock.patch.object(bison, "membership", lambda cid: {}), \
                mock.patch.object(bison, "resume_campaign", record_resume):
            code = recover.main(["--live"])
        return code, out.getvalue(), reached

    def test_the_brake_refuses_the_authorized_write(self):
        """The 2026-09-20 authorization names this exact write. The brake
        outranks it: the file present, the verb is not called - and the
        script says so in the operator's own words, exit 1."""
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=CANONICAL_ID)
        self._pull_brake()

        code, out, reached = self._run_recover()

        self.assertEqual(
            reached, [],
            "the operator's brake was pulled and resume_487 still called "
            "bison.resume_campaign")
        self.assertEqual(code, 1, "a brake refusal is a failed run")
        self.assertIn("BRAKE REFUSED", out,
                      "the brake gets its own wording, deliberately not "
                      "the PROVIDER REFUSED handler: the provider was "
                      "never reached")
        self.assertIn("STOP-SENDING is present", out)
        self.assertIn("delete the file to release it", out,
                      "the operator is told how to un-pull it")

    def test_without_the_file_the_same_run_reaches_the_verb(self):
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=CANONICAL_ID)

        _code, _out, reached = self._run_recover()

        self.assertEqual(reached, [(487, 10)],
                         "the control must reach the verb exactly once; "
                         "if it does not, the fixture or the patches "
                         "changed and the refusal test above is vacuous")


class TheFreezeIsMeasuredNotAssumed(_BrakeScriptBase):
    """The premise behind the permissive killswitch patch: this build
    refuses everything in code, so without the patch every test above
    would be refused by the freeze before the brake was ever consulted -
    green for the wrong reason, which is worse than red."""

    def test_this_build_refuses_sends_in_code(self):
        from src import push
        self.assertTrue(
            hasattr(push, "LiveSendNotEnabled"),
            "the global layer refuses IN CODE. If this premise breaks, "
            "sending was enabled in push and this module must be re-read "
            "in that new world, not deleted.")
        state = killswitch.workspace_state(WORKSPACE)
        self.assertFalse(
            state["sending"],
            f"workspace {WORKSPACE!r} must read off in this build; it "
            f"reads {state!r}")


if __name__ == "__main__":
    unittest.main()
