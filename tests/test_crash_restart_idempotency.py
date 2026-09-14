#!/usr/bin/env python3
"""Crash the staging path at every seam and prove what survives.

For each point at which a staging run can die, a test that says exactly what
the next run does: recovers, refuses as ambiguous, or silently duplicates.

This has already happened for real: a crash between the POST and the persist
left a provider campaign no local state named, and the next run built a
second one. The fix (a derived `provider_campaign_name`, looked up before
creating) is in. Nothing proves it holds at the OTHER seams until this file
does.

EVERY TEST HERE USES A FAKE TRANSPORT. Nothing reaches the network. The
FakeBison is stateful: it holds campaigns, leads, sequences and memberships,
and a crash mid-pipeline leaves whatever state was built up to that point.
The re-run is against THAT state, not a clean one.
"""
import unittest

from src import bisonfactory, campaigns, store, workspaces
from src import providers
from tests.base import QueueTest
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty
from tests.test_staging_a_campaign_twice_builds_one import (
    FakeBison, CONFIG, CID,
)


class CrashAtSeam(QueueTest):
    """One test per seam in stage(). Each crashes, then re-runs.

    The FakeBison is stateful: a crash after `create_campaign` leaves the
    campaign in `self.campaigns`. The re-run sees that state and must
    recover, refuse, or (defect) duplicate.
    """

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        store.save([self._record("rec-1", "one@example.com", "Ada"),
                    self._record("rec-2", "two@example.com", "Grace")])
        row = campaigns.new_campaign(CID, "productive", "Factory test")
        row["record_ids"] = ["rec-1", "rec-2"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

        self._patches = []

    def tearDown(self):
        for original, method_name in self._patches:
            if method_name == "_remember_lead":
                bisonfactory._remember_lead = original
            else:
                setattr(self.bison, method_name, original)
        self._patches.clear()
        super().tearDown()

    @staticmethod
    def _record(rid, email, first):
        key = f"{rid}-c1"
        return {"id": rid, "client": "productive", "domain": "example.com",
                "company": "Example", "state": "ready",
                "cadence": {key: {"day1": {
                    "channel": "email", "subject": f"Hello {first}",
                    "body": "<p>A real approved body.</p>",
                    "approval": {"by": "operator",
                                 "at": "2026-09-13T00:00:00Z"}}}},
                "contacts": [{"key": key, "email": email,
                              "first_name": first, "last_name": "Tester",
                              "sendable": True, "verified": True}]}

    def _crash_after(self, method_name, after_call=1):
        """Monkey-patch a FakeBison method to raise after N successful calls.

        The original runs first (so state is modified), then the exception
        fires. This simulates a crash AFTER the provider call succeeded but
        BEFORE the caller could persist anything.
        """
        original = getattr(self.bison, method_name)
        state = {"count": 0, "done": False}

        def crashing(*args, **kwargs):
            result = original(*args, **kwargs)
            state["count"] += 1
            if state["count"] >= after_call and not state["done"]:
                state["done"] = True
                raise RuntimeError(
                    f"simulated crash after {method_name} "
                    f"(call #{state['count']})")
            return result

        setattr(self.bison, method_name, crashing)
        self._patches.append((original, method_name))

    def _crash_after_remember_lead(self, after_call=1):
        """Crash after _remember_lead succeeds N times.

        _remember_lead is a module-level function, not a bison method, so it
        needs its own patcher. The original runs first (so the lead id is
        persisted), then the exception fires.
        """
        original = bisonfactory._remember_lead
        state = {"count": 0, "done": False}

        def crashing(*args, **kwargs):
            result = original(*args, **kwargs)
            state["count"] += 1
            if state["count"] >= after_call and not state["done"]:
                state["done"] = True
                raise RuntimeError(
                    f"simulated crash after _remember_lead "
                    f"(call #{state['count']})")
            return result

        bisonfactory._remember_lead = crashing
        self._patches.append((original, "_remember_lead"))

    def _remove_crash(self):
        """Restore every patched method to its original."""
        for original, method_name in self._patches:
            if method_name == "_remember_lead":
                bisonfactory._remember_lead = original
            else:
                setattr(self.bison, method_name, original)
        self._patches.clear()

    def _crash_and_rerun(self):
        """Run stage() expecting a crash, then re-run cleanly.

        Returns the second run's report.
        """
        with self.assertRaises(RuntimeError):
            bisonfactory.stage(CID, config=CONFIG, live=True)
        self._remove_crash()
        return bisonfactory.stage(CID, config=CONFIG, live=True)

    def _assert_clean_recovery(self, report):
        """The re-run reached the same end state as a clean first run."""
        self.assertEqual(self.bison.created_campaigns, 1,
                         "a second provider campaign was built")
        self.assertEqual(self.bison.created_leads, 2,
                         "leads were created more than once")
        self.assertEqual(report["provider"]["readback"]["leads"], 2)
        self.assertEqual(report["provider"]["readback"]["status"], "paused")
        row = campaigns.get(CID, campaigns.load())
        self.assertTrue(row.get("bison_campaign_id"))

    # --------------------------------------------------------- the seams

    def test_crash_after_find_or_create_before_bind(self):
        """Campaign created at provider but bison_campaign_id not persisted.

        The crash happens inside create_campaign: the campaign is in the
        FakeBison's state, but _bind (which writes bison_campaign_id) was
        never called. The re-run must find the orphan by name and bind it.
        """
        self._crash_after("create_campaign")
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)
        self.assertTrue(report["provider"].get("recovered"),
                        "the re-run did not recover the orphan by name")

    def test_crash_after_ensure_limits(self):
        """Campaign created, bound, and capped. Crash before schedule."""
        self._crash_after("set_limits")
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)

    def test_crash_after_ensure_schedule(self):
        """Campaign created, bound, capped, and scheduled. Crash before
        senders."""
        self._crash_after("set_schedule")
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)

    def test_crash_after_ensure_senders(self):
        """Everything through senders is done. Crash before sequence.

        With no senders configured, _ensure_senders returns early. The crash
        is on the first call to sequence_steps (the first bison call in
        _ensure_sequence), which simulates a crash after _ensure_senders
        completed but before _ensure_sequence started.
        """
        self._crash_after("sequence_steps", after_call=1)
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)

    def test_crash_after_ensure_sequence(self):
        """Sequence written at provider. Crash before _ensure_stopped.

        The sequence route APPENDS and has no replace. The re-run must see
        the existing sequence and recognise it as matching, NOT append again.
        """
        self._crash_after("set_sequence")
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)
        # PROOF THE SEQUENCE WAS NOT DUPLICATED.
        cid = int(campaigns.get(CID, campaigns.load())["bison_campaign_id"])
        steps = self.bison.sequence_steps(cid)
        self.assertEqual(len(steps), 1,
                         f"sequence was appended again: {len(steps)} steps "
                         f"instead of 1")

    def test_crash_after_ensure_stopped(self):
        """Campaign paused. Crash before _ensure_leads."""
        self._crash_after("pause_campaign")
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)

    def test_crash_after_create_lead_before_remember(self):
        """Lead created at provider but bison_lead_id not persisted.

        The re-run tries create_lead, gets 'already been taken', looks up by
        email, finds it, and remembers it. This is the reconciliation path.
        """
        self._crash_after("create_lead", after_call=1)
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)
        # The first lead was reconciled (found by email, not created again).
        leads = report["provider"]["leads"]
        self.assertEqual(leads["created"], 1,
                         "expected exactly one fresh create (the second lead)")
        self.assertEqual(leads["reconciled"], 1,
                         "expected one reconciliation (the first lead)")

    def test_crash_between_first_and_second_lead(self):
        """First lead fully done. Crash before second lead is created.

        The crash is after _remember_lead for lead 1: the first lead is
        created at the provider AND remembered locally, but the second lead
        has not been touched. The re-run finds the first lead via
        _known_lead_ids and creates the second normally.
        """
        self._crash_after_remember_lead(after_call=1)
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)
        leads = report["provider"]["leads"]
        self.assertEqual(leads["reused"], 1,
                         "the first lead was not reused from its binding")
        self.assertEqual(leads["created"], 1,
                         "the second lead was not created fresh")

    def test_crash_after_attach_before_readback(self):
        """All leads created and attached. Crash before _readback.

        The readback is a pure read. A crash before it leaves the campaign
        fully staged. The re-run is a complete no-op.
        """
        self._crash_after("attach_leads")
        report = self._crash_and_rerun()
        self._assert_clean_recovery(report)
        # The re-run should have created nothing new.
        leads = report["provider"]["leads"]
        self.assertEqual(leads["created"], 0)
        self.assertEqual(leads["reused"], 2)


if __name__ == "__main__":
    unittest.main()
