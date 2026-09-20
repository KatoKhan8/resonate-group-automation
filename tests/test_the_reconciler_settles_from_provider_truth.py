#!/usr/bin/env python3
"""The reconciler settles from provider truth, not from silence.

TASK-237. `scripts/reconcile_ledger.py` was the only thing that settled an
action-ledger reservation. It declared CHECKABLE = ("heyreach.add_lead",) and
skipped anything else with `continue`. Every stuck key was `bison.activate` or
`heyreach.activate`, so it settled zero, every time, and reported success.

Five requirements, each with a test that FAILS before the change:

1. `bison.activate` and `heyreach.activate` are checkable: the reconciler
   asks the provider what the campaign's status and membership actually are
   and settles the key accordingly.
2. A key it cannot settle is REPORTED, with the reason. The `continue` was
   the whole bug.
3. Settling an activate key writes the confirmed touch.
4. An operation genuinely outside the provider's ability to confirm settles
   to UNCONFIRMABLE, never to success.
5. The reconciler is idempotent: running twice settles the same keys once
   and does not double-write a confirmed touch.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from src import actionledger, campaigns, store
from tests.base import QueueTest


def _script_path():
    """The reconciler, located from this file rather than a module constant."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "reconcile_ledger.py")


def _reserve_activate(key, *, operation, channel, campaign_id="camp-1",
                      rec_id="rec-1", contact_key="k1", step_key="em1",
                      workspace="productive"):
    """Reserve an activate key with the minimum fields the ledger requires."""
    return actionledger.reserve(
        key, channel=channel, workspace=workspace, campaign_id=campaign_id,
        sender_id="sender-1", rec_id=rec_id, contact_key=contact_key,
        step_key=step_key, operation=operation, fingerprint="fp1")


class ReconcilerSettlesHeyreachActivate(QueueTest):
    """Requirement 1a: heyreach.activate is checkable from provider truth."""

    def setUp(self):
        super().setUp()
        self.ledger = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger
        self.camp_path = os.path.join(self.tmp, "work", "campaigns.jsonl")
        os.environ["CAMPAIGNS"] = self.camp_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        os.environ.pop("CAMPAIGNS", None)
        super().tearDown()

    def _write_campaign(self, heyreach_campaign_id="599020"):
        os.makedirs(os.path.dirname(self.camp_path), exist_ok=True)
        row = {"campaign_id": "camp-1", "client": "productive",
               "heyreach_campaign_id": heyreach_campaign_id}
        with open(self.camp_path, "w") as f:
            f.write(json.dumps(row) + "\n")

    def _write_record(self, linkedin="https://linkedin.com/in/test"):
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        rec = {"id": "rec-1", "domain": "example.com",
               "contacts": [{"key": "k1", "linkedin": linkedin,
                             "email": "test@example.com"}]}
        with open(self.queue, "w") as f:
            f.write(json.dumps(rec) + "\n")

    def test_heyreach_activate_settled_sent_when_lead_in_campaign(self):
        _reserve_activate("key-hr-1", operation="heyreach.activate",
                          channel="linkedin")
        self._write_campaign()
        self._write_record()

        fake_membership = {"found": {"https://linkedin.com/in/test"},
                           "missing": set(), "total": 1}
        with mock.patch("src.providers.heyreach.campaign_status",
                        return_value="IN_PROGRESS"), \
             mock.patch("src.providers.heyreach.readback_membership",
                        return_value=fake_membership):
            from scripts import reconcile_ledger
            rc = reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(rc, 0)
        self.assertEqual(actionledger.state_of("key-hr-1"),
                         actionledger.SENT)

    def test_heyreach_activate_settled_failed_when_lead_not_in_campaign(self):
        _reserve_activate("key-hr-2", operation="heyreach.activate",
                          channel="linkedin")
        self._write_campaign()
        self._write_record()

        fake_membership = {"found": set(),
                           "missing": {"https://linkedin.com/in/test"},
                           "total": 1}
        with mock.patch("src.providers.heyreach.campaign_status",
                        return_value="IN_PROGRESS"), \
             mock.patch("src.providers.heyreach.readback_membership",
                        return_value=fake_membership):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-hr-2"),
                         actionledger.FAILED)

    def test_heyreach_activate_failed_when_campaign_is_draft(self):
        _reserve_activate("key-hr-3", operation="heyreach.activate",
                          channel="linkedin")
        self._write_campaign()
        self._write_record()

        with mock.patch("src.providers.heyreach.campaign_status",
                        return_value="DRAFT"):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-hr-3"),
                         actionledger.FAILED)


class ReconcilerSettlesBisonActivate(QueueTest):
    """Requirement 1b: bison.activate is checkable from provider truth."""

    def setUp(self):
        super().setUp()
        self.ledger = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger
        self.camp_path = os.path.join(self.tmp, "work", "campaigns.jsonl")
        os.environ["CAMPAIGNS"] = self.camp_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        os.environ.pop("CAMPAIGNS", None)
        super().tearDown()

    def _write_campaign(self, bison_campaign_id="352"):
        os.makedirs(os.path.dirname(self.camp_path), exist_ok=True)
        row = {"campaign_id": "camp-1", "client": "productive",
               "bison_campaign_id": bison_campaign_id}
        with open(self.camp_path, "w") as f:
            f.write(json.dumps(row) + "\n")

    def _write_record(self, email="test@example.com"):
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        rec = {"id": "rec-1", "domain": "example.com",
               "contacts": [{"key": "k1", "email": email,
                             "linkedin": "https://linkedin.com/in/test"}]}
        with open(self.queue, "w") as f:
            f.write(json.dumps(rec) + "\n")

    def test_bison_activate_settled_sent_when_campaign_active_and_lead_in(self):
        _reserve_activate("key-bi-1", operation="bison.activate",
                          channel="email")
        self._write_campaign()
        self._write_record()

        fake_camp = {"status": "active"}
        fake_lead = {"id": 42, "email": "test@example.com"}
        fake_membership = {42: "in_sequence"}

        with mock.patch("src.providers.bison.campaign",
                        return_value=fake_camp), \
             mock.patch("src.providers.bison.find_lead_by_email",
                        return_value=fake_lead), \
             mock.patch("src.providers.bison.membership",
                        return_value=fake_membership):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-bi-1"),
                         actionledger.SENT)

    def test_bison_activate_failed_when_campaign_paused(self):
        _reserve_activate("key-bi-2", operation="bison.activate",
                          channel="email")
        self._write_campaign()
        self._write_record()

        fake_camp = {"status": "paused"}
        with mock.patch("src.providers.bison.campaign",
                        return_value=fake_camp):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-bi-2"),
                         actionledger.FAILED)

    def test_bison_activate_failed_when_lead_not_in_campaign(self):
        _reserve_activate("key-bi-3", operation="bison.activate",
                          channel="email")
        self._write_campaign()
        self._write_record()

        fake_camp = {"status": "active"}
        fake_lead = {"id": 42, "email": "test@example.com"}
        fake_membership = {}

        with mock.patch("src.providers.bison.campaign",
                        return_value=fake_camp), \
             mock.patch("src.providers.bison.find_lead_by_email",
                        return_value=fake_lead), \
             mock.patch("src.providers.bison.membership",
                        return_value=fake_membership):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-bi-3"),
                         actionledger.FAILED)


class ReconcilerReportsUncheckable(QueueTest):
    """Requirement 2: uncheckable keys are REPORTED, not silently skipped."""

    def setUp(self):
        super().setUp()
        self.ledger = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        super().tearDown()

    def test_unknown_operation_reported_and_not_silently_skipped(self):
        """A key for an unknown operation is NOT left behind silently."""
        _reserve_activate("key-unk-1", operation="some.future_op",
                          channel="email")

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])

        output = buf.getvalue()
        self.assertIn("UNCONFIRMABLE", output)
        self.assertIn("some.future_op", output)

    def test_provider_unreadable_leaves_key_unsettled(self):
        """An unreadable provider is NOT evidence of absence."""
        _reserve_activate("key-unk-2", operation="heyreach.activate",
                          channel="linkedin")

        camp_path = os.path.join(self.tmp, "work", "campaigns.jsonl")
        os.environ["CAMPAIGNS"] = camp_path
        os.makedirs(os.path.dirname(camp_path), exist_ok=True)
        with open(camp_path, "w") as f:
            f.write(json.dumps({"campaign_id": "camp-1", "client": "p",
                                "heyreach_campaign_id": "123"}) + "\n")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        with open(self.queue, "w") as f:
            f.write(json.dumps({"id": "rec-1", "domain": "x.com",
                                "contacts": [{"key": "k1",
                                              "linkedin": "https://li/in/x"}]})
                    + "\n")

        with mock.patch("src.providers.heyreach.campaign_status",
                        side_effect=Exception("timeout")):
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                from scripts import reconcile_ledger
                reconcile_ledger.main(["--live", "--by", "test"])

        output = buf.getvalue()
        self.assertIn("LEFT", output)
        self.assertIn("unreadable", output)
        self.assertEqual(actionledger.state_of("key-unk-2"),
                         actionledger.ATTEMPTED)

    def tearDown(self):
        os.environ.pop("CAMPAIGNS", None)
        super().tearDown()


class ReconcilerSettlesUnconfirmable(QueueTest):
    """Requirement 4: uncheckable operations settle to UNCONFIRMABLE."""

    def setUp(self):
        super().setUp()
        self.ledger = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        super().tearDown()

    def test_unconfirmable_is_a_terminal_state(self):
        """UNCONFIRMABLE is terminal and unreservable, never success."""
        self.assertIn(actionledger.UNCONFIRMABLE, actionledger.TERMINAL)
        self.assertIn(actionledger.UNCONFIRMABLE, actionledger.SETTLED)
        self.assertNotIn(actionledger.UNCONFIRMABLE, actionledger.BLOCKING)

    def test_unconfirmable_settled_in_ledger(self):
        """An unknown operation settles to UNCONFIRMABLE, not SENT."""
        _reserve_activate("key-uc-1", operation="mystery.op",
                          channel="email")

        from scripts import reconcile_ledger
        reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-uc-1"),
                         actionledger.UNCONFIRMABLE)

    def test_unconfirmable_cannot_be_settled_to_sent(self):
        """UNCONFIRMABLE is terminal: settling it to SENT is refused."""
        _reserve_activate("key-uc-2", operation="mystery.op",
                          channel="email")
        actionledger.settle("key-uc-2", actionledger.UNCONFIRMABLE,
                            why="cannot check")

        with self.assertRaises(actionledger.ActionRefused):
            actionledger.settle("key-uc-2", actionledger.SENT, why="later")


class ReconcilerWritesConfirmedTouch(QueueTest):
    """Requirement 3: settling an activate key writes the confirmed touch."""

    def setUp(self):
        super().setUp()
        self.ledger = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger
        self.camp_path = os.path.join(self.tmp, "work", "campaigns.jsonl")
        os.environ["CAMPAIGNS"] = self.camp_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        os.environ.pop("CAMPAIGNS", None)
        super().tearDown()

    def test_settling_heyreach_activate_writes_confirmed_touch(self):
        """A SENT settlement for heyreach.activate records the touch."""
        _reserve_activate("key-t-1", operation="heyreach.activate",
                          channel="linkedin", step_key="li1")

        os.makedirs(os.path.dirname(self.camp_path), exist_ok=True)
        with open(self.camp_path, "w") as f:
            f.write(json.dumps({"campaign_id": "camp-1", "client": "p",
                                "heyreach_campaign_id": "123"}) + "\n")

        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        rec = {"id": "rec-1", "domain": "example.com",
               "contacts": [{"key": "k1",
                             "linkedin": "https://linkedin.com/in/test",
                             "email": "t@x.com"}],
               "events": []}
        with open(self.queue, "w") as f:
            f.write(json.dumps(rec) + "\n")

        fake_membership = {"found": {"https://linkedin.com/in/test"},
                           "missing": set(), "total": 1}

        touch_written = []

        def fake_touch(row, recs):
            touch_written.append(row.get("key"))

        with mock.patch("src.providers.heyreach.campaign_status",
                        return_value="IN_PROGRESS"), \
             mock.patch("src.providers.heyreach.readback_membership",
                        return_value=fake_membership), \
             mock.patch("scripts.reconcile_ledger._record_touch_for",
                        side_effect=fake_touch):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-t-1"),
                         actionledger.SENT)
        self.assertIn("key-t-1", touch_written)

    def test_failed_settlement_does_not_write_touch(self):
        """A FAILED settlement does NOT record a confirmed touch."""
        _reserve_activate("key-t-2", operation="heyreach.activate",
                          channel="linkedin")

        os.makedirs(os.path.dirname(self.camp_path), exist_ok=True)
        with open(self.camp_path, "w") as f:
            f.write(json.dumps({"campaign_id": "camp-1", "client": "p",
                                "heyreach_campaign_id": "123"}) + "\n")

        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        rec = {"id": "rec-1", "domain": "example.com",
               "contacts": [{"key": "k1",
                             "linkedin": "https://linkedin.com/in/test"}]}
        with open(self.queue, "w") as f:
            f.write(json.dumps(rec) + "\n")

        fake_membership = {"found": set(),
                           "missing": {"https://linkedin.com/in/test"},
                           "total": 1}

        touch_written = []

        def fake_touch(row, recs):
            touch_written.append(row.get("key"))

        with mock.patch("src.providers.heyreach.campaign_status",
                        return_value="IN_PROGRESS"), \
             mock.patch("src.providers.heyreach.readback_membership",
                        return_value=fake_membership), \
             mock.patch("scripts.reconcile_ledger._record_touch_for",
                        side_effect=fake_touch):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-t-2"),
                         actionledger.FAILED)
        self.assertEqual(touch_written, [])


class ReconcilerIsIdempotent(QueueTest):
    """Requirement 5: running twice settles the same keys once."""

    def setUp(self):
        super().setUp()
        self.ledger = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger
        self.camp_path = os.path.join(self.tmp, "work", "campaigns.jsonl")
        os.environ["CAMPAIGNS"] = self.camp_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        os.environ.pop("CAMPAIGNS", None)
        super().tearDown()

    def test_running_twice_does_not_double_settle(self):
        """A second run on an already-settled key is a no-op."""
        _reserve_activate("key-id-1", operation="heyreach.activate",
                          channel="linkedin")

        os.makedirs(os.path.dirname(self.camp_path), exist_ok=True)
        with open(self.camp_path, "w") as f:
            f.write(json.dumps({"campaign_id": "camp-1", "client": "p",
                                "heyreach_campaign_id": "123"}) + "\n")

        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        rec = {"id": "rec-1", "domain": "example.com",
               "contacts": [{"key": "k1",
                             "linkedin": "https://linkedin.com/in/test"}]}
        with open(self.queue, "w") as f:
            f.write(json.dumps(rec) + "\n")

        fake_membership = {"found": {"https://linkedin.com/in/test"},
                           "missing": set(), "total": 1}

        touch_count = []

        def fake_touch(row, recs):
            touch_count.append(row.get("key"))

        with mock.patch("src.providers.heyreach.campaign_status",
                        return_value="IN_PROGRESS"), \
             mock.patch("src.providers.heyreach.readback_membership",
                        return_value=fake_membership), \
             mock.patch("scripts.reconcile_ledger._record_touch_for",
                        side_effect=fake_touch):
            from scripts import reconcile_ledger
            reconcile_ledger.main(["--live", "--by", "test"])
            reconcile_ledger.main(["--live", "--by", "test"])

        self.assertEqual(actionledger.state_of("key-id-1"),
                         actionledger.SENT)
        settled_rows = actionledger.rows_for("key-id-1")
        sent_rows = [r for r in settled_rows
                     if r.get("state") == actionledger.SENT]
        self.assertEqual(len(sent_rows), 1,
                         "settling twice should not append a second SENT row")
        self.assertEqual(len(touch_count), 1,
                         "touch should be written exactly once")


class ReconcilerDryRunWritesNothing(QueueTest):
    """Acceptance: dry run reports what it WOULD settle and writes nothing."""

    def setUp(self):
        super().setUp()
        self.ledger = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        os.environ.pop("CAMPAIGNS", None)
        super().tearDown()

    def test_dry_run_leaves_keys_unsettled(self):
        """Without --live, nothing is written to the ledger."""
        _reserve_activate("key-dry-1", operation="bison.activate",
                          channel="email")

        camp_path = os.path.join(self.tmp, "work", "campaigns.jsonl")
        os.environ["CAMPAIGNS"] = camp_path
        os.makedirs(os.path.dirname(camp_path), exist_ok=True)
        with open(camp_path, "w") as f:
            f.write(json.dumps({"campaign_id": "camp-1", "client": "p",
                                "bison_campaign_id": "352"}) + "\n")

        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        with open(self.queue, "w") as f:
            f.write(json.dumps({"id": "rec-1", "domain": "x.com",
                                "contacts": [{"key": "k1",
                                              "email": "t@x.com"}]}) + "\n")

        fake_camp = {"status": "active"}
        fake_lead = {"id": 42, "email": "t@x.com"}
        fake_membership = {42: "in_sequence"}

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with mock.patch("src.providers.bison.campaign",
                        return_value=fake_camp), \
             mock.patch("src.providers.bison.find_lead_by_email",
                        return_value=fake_lead), \
             mock.patch("src.providers.bison.membership",
                        return_value=fake_membership), \
             redirect_stdout(buf):
            from scripts import reconcile_ledger
            reconcile_ledger.main([])

        output = buf.getvalue()
        self.assertIn("WOULD SETTLE", output)
        self.assertIn("DRY RUN", output)
        self.assertEqual(actionledger.state_of("key-dry-1"),
                         actionledger.ATTEMPTED)


if __name__ == "__main__":
    unittest.main()


class AnUnresolvedKeyIsNeverMadeReservableAgain(unittest.TestCase):
    """Added in Claude's review of TASK-237, before it reached master.

    The settlement loop walks `unsettled()`, which is ATTEMPTED **and**
    UNRESOLVED, and applied one rule to both. For an ATTEMPTED key, "the lead
    is not at the provider" is good evidence the write never landed and
    FAILED - which is reservable - is right.

    For an UNRESOLVED key it is not. UNRESOLVED means nobody could determine
    whether the person was contacted, and `actionledger` puts it in BLOCKING
    so the key is refused forever until a human looks. A lead ABSENT from a
    campaign is not proof nobody was emailed: a lead added, emailed and then
    stopped reads identically. Settling that FAILED returns the key to
    reservable and re-opens the duplicate-send path Buggie attacked and
    confirmed closed.

    Positive evidence is allowed through - the lead IS there, so the action
    landed, so SENT is a fact rather than an inference from absence.
    """

    def _run(self, verdict, why):
        """Drive the settlement loop with one UNRESOLVED key.

        Every patch goes through `mock.patch.object` so it is restored.
        Assigning to `recon.actionledger.settle` directly mutates the SHARED
        `src.actionledger` module and leaks into every other test in this
        file - which is exactly what the first version of this did.
        """
        import io as _io
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "recon_under_test", _script_path())
        recon = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recon)

        settled = []
        row = {"key": "k1", "operation": "bison.activate",
               "state": actionledger.UNRESOLVED,
               "at": "2026-09-18T00:00:00+00:00"}
        out = _io.StringIO()
        with mock.patch.object(actionledger, "settle",
                               lambda *a, **k: settled.append(a)),              mock.patch.object(actionledger, "unsettled", lambda: [row]),              mock.patch.object(recon.store, "load", lambda *a, **k: []),              mock.patch.object(recon.campaigns, "load", lambda *a, **k: []),              mock.patch.object(recon, "_record_touch_for",
                               lambda *a, **k: None, create=True),              mock.patch.object(recon, "_CHECKERS",
                               {"bison.activate":
                                lambda r, recs, camps: (verdict, why, {})}):
            stdout, sys.stdout = sys.stdout, out
            try:
                recon.main(["--live"])
            finally:
                sys.stdout = stdout
        return settled, out.getvalue()

    def test_an_unresolved_key_is_never_settled_failed(self):
        settled, text = self._run(actionledger.FAILED, "the lead is not there")
        self.assertEqual([], settled, "an UNRESOLVED key was settled FAILED")
        self.assertIn("Absence is not proof", text)
        self.assertIn("1 left for a person", text)

    def test_an_unresolved_key_proven_sent_is_still_settled(self):
        settled, _ = self._run(actionledger.SENT, "the lead IS in it")
        self.assertEqual(1, len(settled),
                         "positive provider evidence must still settle")
        self.assertEqual(actionledger.SENT, settled[0][1])

    def test_the_states_this_rests_on_have_not_moved(self):
        self.assertIn(actionledger.UNRESOLVED, actionledger.BLOCKING)
        self.assertIn(actionledger.UNRESOLVED, actionledger.UNRESERVABLE)
        self.assertNotIn(actionledger.FAILED, actionledger.UNRESERVABLE)
