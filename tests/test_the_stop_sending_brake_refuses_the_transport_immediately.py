#!/usr/bin/env python3
"""The STOP-SENDING brake refuses the transport immediately - TASK 0210.

PROPERTY UNDER TEST (the first of four, tested alone):

    Checked immediately before the transport call, inside the same
    function, not at the top of a loop or a cycle.

`src/haltfile.py` is the brake: a zero-byte file at one absolute path
outside every checkout. This module pins what "immediately before" means
at the write door, `providerwrites._perform`:

  1. the file present -> OperatorStop, the transport unreached, and the
     refusal recorded in the action ledger as REFUSED - not as "failed",
     which reads as the machine's fault rather than the operator's hand;
  2. the check is not at entry. `staged_already` is the last
     module-global call before the brake on the non-facing branch (the
     staging-repeat guard; between it and the brake there is nothing but
     two `callable()` attribute checks); a wrapper around it that pulls
     the brake MID-CALL still refuses, so the brake sits after every
     permission question and before the transport, not at the top of
     `_perform` where a whole gate could run after it;
  3. no file -> the transport is reached. The harness reaches the
     transport at all; a refusal that cannot fire is not a brake;
  4. the four REPEATABLE verbs are exempt, so PULLING THE BRAKE NEVER
     DISABLES A BRAKE. `scripts/bison_watch_loop.py` re-applies
     `bison.pause` to campaign 481 every 180 seconds through this same
     door; with the file present that pause MUST still land, or the
     operator's one-handed stop would silence the machine's own
     blank-content halt (the 76-blank-emails lesson).

NO TEST IN THIS MODULE CREATES THE REAL FILE. `haltfile.STOP_SENDING_PATH`
is patched at a temp path for every test; the real path
`C:\\Users\\Zvonimir\\Desktop\\resonate-ops\\STOP-SENDING` is only ever
read by production code, and the day the operator pulls it these tests
must not flip.

THE VERB UNDER TEST is `heyreach.create_list` (LINKEDIN_CREATE_LIST):
SUPPORTED, not in CONDITIONAL, not facing, NOT repeatable - so it is NOT
exempt from the brake - and CREATING, so it passes the ownership gate
without a provider id, which is exactly the production shape of
`scripts/stage_linkedin_cohort_b.py`'s create-list write. The first
draft of this module used `bison.pause` for all four tests and could
never go red on the first three, because a pause is exempt from the
brake by design; the exemption it proved was real, but it proved
nothing about the refusal. `bison.pause` now appears only in test 4,
where exemption IS the property.

Born-red at HEAD (pre-0210): this module imports `src.haltfile`, which
did not exist, so the red was ImportError. The mutation proof (TASK
0210's lane entry) re-derives the true born-red: with `haltfile`
present and the door's `2c` check byte-reverted, test 1 and test 2
fail on REACH - the transport is called with the file present.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import haltfile, providerwrites, store
from src.providers import bison                      # noqa: F401 (tripwire)
from tests.campaignbase import CampaignTest


class _BrakeTestCase(CampaignTest):
    """Campaign fixture + a brake file at a THROWAWAY path + ledger redirect.

    The action ledger is pointed at a temp file (the 0200 mixin pattern):
    the brake's refusal is a ledger event, and no test may write the real
    `work/` ledger. The CampaignTest fixture stays because the CONTROL
    call succeeds, and a successful non-repeatable write records itself
    as staged against the campaign - in the temp `work/`, never the real
    one.
    """

    CAMP = "camp-stop-brake"

    def setUp(self):
        super().setUp()
        self.brake_tmp = tempfile.mkdtemp(prefix="rga-brake-door-")
        self.addCleanup(shutil.rmtree, self.brake_tmp, ignore_errors=True)
        self.brake_path = os.path.join(self.brake_tmp, "STOP-SENDING")

        self.ledger_tmp = tempfile.mkdtemp(prefix="rga-brake-ledger-")
        ledger = os.path.join(self.ledger_tmp, "provider-writes.jsonl")
        self._old_ledger = os.environ.get(
            providerwrites.PROVIDER_WRITES_LEDGER)
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = ledger
        self.ledger_path = ledger
        self.addCleanup(self._restore_ledger)
        self.addCleanup(shutil.rmtree, self.ledger_tmp, ignore_errors=True)

    def _restore_ledger(self):
        if self._old_ledger is None:
            os.environ.pop(providerwrites.PROVIDER_WRITES_LEDGER, None)
        else:
            os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = (
                self._old_ledger)

    def _pull_brake(self):
        with open(self.brake_path, "wb") as handle:
            handle.write(b"")

    def _create_list(self):
        """perform(heyreach.create_list) against a recording transport -
        the production shape of scripts/stage_linkedin_cohort_b.py's
        create-list write: CREATING verb, no provider id, campaign in the
        fixture store, `expected` read back after the transport.

        THE `gate=` IS PART OF THE PRODUCTION SHAPE, not a way past a check.
        A non-facing provider write requires a `GateToken`, and every real
        caller mints one the same way - see `src/liststaging.py:329`, which
        passes `gate=providerwrites.grant(OP, by=..., why=...)` beside the
        payload. Without it `perform` refuses at the grant rung with
        `WriteRefused` and the brake is never consulted, so these tests would
        be asserting about a door they never reached. Supplying the token
        moves the test PAST the gate rung and up to the brake rung, which is
        the rung under test; it weakens nothing, because the brake check is
        downstream of the grant check and every assertion below is about the
        brake.
        """
        recorder = _Recorder()
        providerwrites.perform(
            providerwrites.LINKEDIN_CREATE_LIST,
            gate=providerwrites.grant(
                providerwrites.LINKEDIN_CREATE_LIST, by="brake-test",
                why="exercising the STOP-SENDING brake at the write door"),
            campaign=self.CAMP,
            payload={"name": "brake-test-list"},
            transport=recorder.create_list,
            readback=recorder.readback_list,
            expected={"campaignIds": []})
        return recorder


class _Recorder:
    """A transport that records the fact it was reached. Nothing else."""

    def __init__(self):
        self.calls = []

    def create_list(self, payload):
        self.calls.append(("create_list", payload))
        return {"ok": True}

    def readback_list(self):
        return {"campaignIds": []}

    def pause_campaign(self, provider_id):
        self.calls.append(("pause_campaign", provider_id))
        return {"ok": True}

    def readback_paused(self):
        return {"status": "paused"}


class TheBrakeRefusesTheTransport(_BrakeTestCase):

    def test_the_file_present_refuses_and_the_transport_is_unreached(self):
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=self.CAMP)
        self._pull_brake()

        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.brake_path), \
                self.assertRaises(haltfile.OperatorStop) as raised:
            self._create_list()

        self.assertIn("STOP-SENDING is present", str(raised.exception))
        self.assertIn("delete the file", str(raised.exception).lower())

    def test_the_refusal_is_ledgered_as_refused_not_failed(self):
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=self.CAMP)
        self._pull_brake()

        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.brake_path), \
                self.assertRaises(haltfile.OperatorStop):
            self._create_list()

        self.assertTrue(os.path.exists(self.ledger_path),
                        "a brake refusal is a ledger event; the operator's "
                        "stop must be in the audit trail, not only on stdout")
        with open(self.ledger_path, encoding="utf-8") as handle:
            rows = [line for line in handle.read().splitlines() if line]
        self.assertEqual(len(rows), 1, f"expected one ledger row: {rows!r}")
        self.assertIn('"refused"', rows[0])
        self.assertNotIn('"failed"', rows[0])
        self.assertIn("OperatorStop", rows[0])
        self.assertIn("STOP-SENDING is present", rows[0])

    def test_no_file_and_the_transport_is_reached(self):
        """The control. A brake that refuses everything proves nothing.

        This is the same call with no brake file: the transport fires, so
        the refusals above are the brake and not the fixture.
        """
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=self.CAMP)

        recorder = self._create_list()

        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(recorder.calls[0][0], "create_list")
        # The transport is called with the payload; the production script
        # pins the same reach by the fact of the call.
        self.assertEqual(recorder.calls[0][1].get("name"), "brake-test-list")


class TheCheckIsImmediatelyBeforeTheTransport(_BrakeTestCase):

    def test_the_brake_pulled_after_the_last_gate_still_refuses(self):
        """Not at entry: `staged_already` is the last module-global call
        before the brake on the non-facing branch - after it come only two
        `callable()` attribute checks, which ask no permission. Pull the
        brake INSIDE it - after every permission question has already
        answered - and the transport must still be refused. A brake
        consulted at the top of `_perform` would pass this test's premise
        and fail its assertion.
        """
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=self.CAMP)

        real_guard = providerwrites.staged_already

        def guard_then_pull(campaign_id, operation, payload):
            real_guard(campaign_id, operation, payload)
            self._pull_brake()        # the operator's hand, mid-call

        recorder = _Recorder()
        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.brake_path), \
                mock.patch.object(providerwrites, "staged_already",
                                  guard_then_pull), \
                self.assertRaises(haltfile.OperatorStop):
            providerwrites.perform(
                providerwrites.LINKEDIN_CREATE_LIST,
                # Minted BEFORE the brake is pulled mid-call, which is the
                # point of this test: the grant rung has already passed, so a
                # refusal here can only be the brake.
                gate=providerwrites.grant(
                    providerwrites.LINKEDIN_CREATE_LIST, by="brake-test",
                    why="the brake pulled after the last gate must refuse"),
                campaign=self.CAMP,
                payload={"name": "brake-test-list"},
                transport=recorder.create_list,
                readback=recorder.readback_list,
                expected={"campaignIds": []})

        self.assertEqual(
            recorder.calls, [],
            "the brake was pulled after the staging guard answered and "
            "the transport still fired: the check is not immediately "
            "before the transport")


class PullingTheBrakeNeverDisablesABrake(_BrakeTestCase):

    def test_the_repeatable_pause_is_exempt_and_still_lands(self):
        """The 481 watch case. `scripts/bison_watch_loop.py` pauses campaign
        481 through this door every 180 seconds when it sees blank content,
        and it must keep doing so with STOP-SENDING present - the operator's
        brake must never silence the machine's own halt."""
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=self.CAMP)
        self._pull_brake()

        recorder = _Recorder()
        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.brake_path):
            providerwrites.perform(
                providerwrites.EMAIL_PAUSE,
                campaign=self.CAMP,
                payload={"campaign_id": "9001"},
                transport=recorder.pause_campaign,
                readback=recorder.readback_paused,
                expected={"status": "paused"})

        self.assertEqual(
            len(recorder.calls), 1,
            "bison.pause is itself a brake and is exempt from STOP-SENDING; "
            "the 481 blank-content watch flows through this door and must "
            "keep pausing with the file present")


if __name__ == "__main__":
    unittest.main()
