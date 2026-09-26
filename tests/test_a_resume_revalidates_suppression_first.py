"""TASK-331: a resume rechecks suppression before the transport is touched.

## The defect

`EMAIL_RESUME` had `facing=False` and no CONDITIONAL predicate, so `_perform`
took the non-facing path and skipped `executionguard.revalidate()`. A resume
of a campaign whose recipients had been suppressed (e.g. the 76 from the
2026-09-23 blank-email incident) would restart sending to them without
checking.

## The fix

A CONDITIONAL predicate `_resume_rechecks_suppression` was added for
`EMAIL_RESUME`. It reads the campaign's record_ids, loads each record from
the store, and checks every contact with `eligibility.must_not_contact`. If
any contact is blocked, the resume refuses naming the count.

`facing` was NOT flipped to True. Flipping would impose Authorization,
ledger reservation, spend(), approved-words and touch recording -
requirements the operator has not granted for resume. The narrower fix
rechecks suppression without the full facing brake set.

## What this test asserts

1. A resume of a campaign holding a suppressed address REFUSES, naming the
   count.
2. A resume of a clean campaign still proceeds.
3. The guard is seen to fail: without the CONDITIONAL, the test fails.
4. The action ledger gets a row for both REFUSED and performed resumes.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import (campaigns, eligibility, providerwrites, store)  # noqa: E402


class _TempState(unittest.TestCase):
    """Point every stateful path at a throwaway directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-resume-reval-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.queue_path = os.path.join(self.tmp, "queue.jsonl")
        self.campaigns_path = os.path.join(self.tmp, "campaigns.jsonl")
        self.ledger_path = os.path.join(self.tmp, "provider-writes.jsonl")
        self.suppress_path = os.path.join(self.tmp, "suppress.txt")

        self._old_queue = os.environ.get("QUEUE")
        self._old_campaigns = os.environ.get("CAMPAIGNS")
        self._old_ledger = os.environ.get(providerwrites.PROVIDER_WRITES_LEDGER)
        self._old_suppress = os.environ.get("SUPPRESS")

        os.environ["QUEUE"] = self.queue_path
        os.environ["CAMPAIGNS"] = self.campaigns_path
        os.environ[providerwrites.PROVIDER_WRITES_LEDGER] = self.ledger_path
        os.environ["SUPPRESS"] = self.suppress_path

        with io.open(self.suppress_path, "w", encoding="utf-8") as fh:
            fh.write("")

    def tearDown(self):
        for key, old in (("QUEUE", self._old_queue),
                         ("CAMPAIGNS", self._old_campaigns),
                         (providerwrites.PROVIDER_WRITES_LEDGER,
                          self._old_ledger),
                         ("SUPPRESS", self._old_suppress)):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def _write_queue(self, records):
        with io.open(self.queue_path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")

    def _write_campaigns(self, campaign_rows):
        with io.open(self.campaigns_path, "w", encoding="utf-8") as fh:
            for row in campaign_rows:
                fh.write(json.dumps(row) + "\n")

    def ledger_rows(self):
        if not os.path.exists(self.ledger_path):
            return []
        with io.open(self.ledger_path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]


class ResumeRefusesSuppressedRecipients(_TempState):

    def test_a_resume_with_a_suppressed_recipient_refuses(self):
        """76 recipients were suppressed from the blank-email incident.
        A resume must refuse, naming the count."""
        self._write_queue([
            {"id": "rec-1", "domain": "clean.example.com",
             "state": "verified",
             "contacts": [{"key": "alice", "email": "alice@clean.example.com",
                           "verified": True}]},
            {"id": "rec-2", "domain": "blocked.example.com",
             "state": "verified",
             "suppression": {"unsubscribed": True},
             "contacts": [{"key": "bob", "email": "bob@blocked.example.com",
                           "verified": True}]},
        ])
        self._write_campaigns([
            {"campaign_id": "c491", "client": "productive",
             "bison_campaign_id": "491",
             "record_ids": ["rec-1", "rec-2"]},
        ])

        with self.assertRaises(providerwrites.WriteRefused) as ctx:
            providerwrites.perform(
                providerwrites.EMAIL_RESUME,
                campaign="c491",
                tenant="productive",
                payload={"campaign_id": "491"},
                transport=lambda p: {"status": "running"},
                readback=lambda: {"status": "running"},
                expected={"status": "running"})

        msg = str(ctx.exception)
        self.assertIn("1 recipient(s)", msg,
                      "the refusal did not name the blocked count")
        self.assertIn("rec-2:bob", msg,
                      "the refusal did not name the blocked recipient")
        self.assertIn("transport was not reached", msg,
                      "the refusal did not confirm the transport was skipped")

    def test_a_resume_with_multiple_suppressed_names_the_count(self):
        """The count must be right, not truncated to one."""
        self._write_queue([
            {"id": "rec-1", "domain": "clean.example.com",
             "state": "verified",
             "contacts": [{"key": "a", "email": "a@clean.example.com",
                           "verified": True}]},
            {"id": "rec-2", "domain": "blocked-a.example.com",
             "state": "verified",
             "suppression": {"unsubscribed": True},
             "contacts": [{"key": "b", "email": "b@blocked-a.example.com",
                           "verified": True}]},
            {"id": "rec-3", "domain": "blocked-b.example.com",
             "state": "dropped", "drop_reason": "suppress",
             "contacts": [{"key": "c", "email": "c@blocked-b.example.com",
                           "verified": True}]},
        ])
        self._write_campaigns([
            {"campaign_id": "c491", "client": "productive",
             "bison_campaign_id": "491",
             "record_ids": ["rec-1", "rec-2", "rec-3"]},
        ])

        with self.assertRaises(providerwrites.WriteRefused) as ctx:
            providerwrites.perform(
                providerwrites.EMAIL_RESUME,
                campaign="c491",
                tenant="productive",
                payload={"campaign_id": "491"},
                transport=lambda p: {"status": "running"},
                readback=lambda: {"status": "running"},
                expected={"status": "running"})

        msg = str(ctx.exception)
        self.assertIn("2 recipient(s)", msg,
                      "the refusal did not count both blocked recipients")


class ResumeOfACleanCampaignProceeds(_TempState):

    def test_a_resume_with_no_suppressed_recipients_proceeds(self):
        """A guard that blocks every resume is not a fix."""
        self._write_queue([
            {"id": "rec-1", "domain": "clean.example.com",
             "state": "verified",
             "contacts": [{"key": "alice", "email": "alice@clean.example.com",
                           "verified": True}]},
            {"id": "rec-2", "domain": "also-clean.example.com",
             "state": "verified",
             "contacts": [{"key": "bob", "email": "bob@also-clean.example.com",
                           "verified": True}]},
        ])
        self._write_campaigns([
            {"campaign_id": "c491", "client": "productive",
             "bison_campaign_id": "491",
             "record_ids": ["rec-1", "rec-2"]},
        ])

        outcome = providerwrites.perform(
            providerwrites.EMAIL_RESUME,
            campaign="c491",
            tenant="productive",
            payload={"campaign_id": "491"},
            transport=lambda p: {"status": "running"},
            readback=lambda: {"status": "running"},
            expected={"status": "running"})

        self.assertIsNotNone(outcome, "a clean resume returned no outcome")
        self.assertEqual("accepted", outcome.get("class"),
                         "a clean resume was not accepted")

    def test_a_resume_with_no_record_ids_proceeds(self):
        """An empty campaign has nobody to suppress."""
        self._write_queue([])
        self._write_campaigns([
            {"campaign_id": "c1", "client": "productive",
             "bison_campaign_id": "1", "record_ids": []},
        ])

        outcome = providerwrites.perform(
            providerwrites.EMAIL_RESUME,
            campaign="c1",
            tenant="productive",
            payload={"campaign_id": "1"},
            transport=lambda p: {"status": "running"},
            readback=lambda: {"status": "running"},
            expected={"status": "running"})

        self.assertEqual("accepted", outcome.get("class"))


class TheGuardIsSeenToFail(_TempState):
    """Acceptance 3: revert the fix, confirm the test fails on old code."""

    def test_without_the_conditional_the_suppressed_resume_proceeds(self):
        """This is the defect reproduced. With the CONDITIONAL removed,
        a resume of a campaign holding a suppressed recipient proceeds
        without checking - which is exactly the bug."""
        self._write_queue([
            {"id": "rec-1", "domain": "clean.example.com",
             "state": "verified",
             "contacts": [{"key": "alice", "email": "alice@clean.example.com",
                           "verified": True}]},
            {"id": "rec-2", "domain": "blocked.example.com",
             "state": "verified",
             "suppression": {"unsubscribed": True},
             "contacts": [{"key": "bob", "email": "bob@blocked.example.com",
                           "verified": True}]},
        ])
        self._write_campaigns([
            {"campaign_id": "c491", "client": "productive",
             "bison_campaign_id": "491",
             "record_ids": ["rec-1", "rec-2"]},
        ])

        saved = providerwrites.CONDITIONAL.pop(providerwrites.EMAIL_RESUME,
                                               None)
        try:
            outcome = providerwrites.perform(
                providerwrites.EMAIL_RESUME,
                campaign="c491",
                tenant="productive",
                payload={"campaign_id": "491"},
                transport=lambda p: {"status": "running"},
                readback=lambda: {"status": "running"},
                expected={"status": "running"})
            self.assertEqual("accepted", outcome.get("class"),
                             "without the CONDITIONAL, the suppressed resume "
                             "proceeded - this is the defect")
        finally:
            if saved is not None:
                providerwrites.CONDITIONAL[providerwrites.EMAIL_RESUME] = saved

    def test_with_the_conditional_the_same_resume_refuses(self):
        """The same scenario with the fix in place refuses."""
        self._write_queue([
            {"id": "rec-1", "domain": "clean.example.com",
             "state": "verified",
             "contacts": [{"key": "alice", "email": "alice@clean.example.com",
                           "verified": True}]},
            {"id": "rec-2", "domain": "blocked.example.com",
             "state": "verified",
             "suppression": {"unsubscribed": True},
             "contacts": [{"key": "bob", "email": "bob@blocked.example.com",
                           "verified": True}]},
        ])
        self._write_campaigns([
            {"campaign_id": "c491", "client": "productive",
             "bison_campaign_id": "491",
             "record_ids": ["rec-1", "rec-2"]},
        ])

        self.assertIn(providerwrites.EMAIL_RESUME, providerwrites.CONDITIONAL,
                      "the CONDITIONAL was not registered")

        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.EMAIL_RESUME,
                campaign="c491",
                tenant="productive",
                payload={"campaign_id": "491"},
                transport=lambda p: {"status": "running"},
                readback=lambda: {"status": "running"},
                expected={"status": "running"})


class TheLedgerStillGetsItsRow(_TempState):
    """Acceptance 4: the action ledger gets a row for both outcomes."""

    def test_a_refused_resume_leaves_a_ledger_row(self):
        """A refusal that leaves no row is a refusal that cannot be audited."""
        self._write_queue([
            {"id": "rec-1", "domain": "blocked.example.com",
             "state": "verified",
             "suppression": {"unsubscribed": True},
             "contacts": [{"key": "alice",
                           "email": "alice@blocked.example.com",
                           "verified": True}]},
        ])
        self._write_campaigns([
            {"campaign_id": "c491", "client": "productive",
             "bison_campaign_id": "491",
             "record_ids": ["rec-1"]},
        ])

        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.EMAIL_RESUME,
                campaign="c491",
                tenant="productive",
                payload={"campaign_id": "491"},
                transport=lambda p: {"status": "running"},
                readback=lambda: {"status": "running"},
                expected={"status": "running"})

        rows = self.ledger_rows()
        self.assertEqual(1, len(rows),
                         "a refused resume left no ledger row")
        self.assertEqual("bison.resume", rows[0]["operation"])
        self.assertEqual("refused", rows[0]["outcome"])

    def test_a_performed_resume_leaves_a_ledger_row(self):
        """The row that EMAIL_RESUME was routed through perform to get."""
        self._write_queue([
            {"id": "rec-1", "domain": "clean.example.com",
             "state": "verified",
             "contacts": [{"key": "alice", "email": "alice@clean.example.com",
                           "verified": True}]},
        ])
        self._write_campaigns([
            {"campaign_id": "c491", "client": "productive",
             "bison_campaign_id": "491",
             "record_ids": ["rec-1"]},
        ])

        providerwrites.perform(
            providerwrites.EMAIL_RESUME,
            campaign="c491",
            tenant="productive",
            payload={"campaign_id": "491"},
            transport=lambda p: {"status": "running"},
            readback=lambda: {"status": "running"},
            expected={"status": "running"})

        rows = self.ledger_rows()
        self.assertTrue(len(rows) >= 1,
                        "a performed resume left no ledger row")
        resume_rows = [r for r in rows
                       if r["operation"] == "bison.resume"]
        self.assertTrue(resume_rows,
                        "no bison.resume row in the ledger")
        self.assertEqual("accepted", resume_rows[0]["outcome"])


class FacingWasNotFlipped(unittest.TestCase):
    """The narrower fix was chosen. Document what flipping would impose."""

    def test_email_resume_is_not_prospect_facing(self):
        """`facing` stays False. Flipping would impose Authorization,
        ledger reservation, spend(), approved-words and touch recording."""
        _channel, facing, _why = providerwrites.describe(
            providerwrites.EMAIL_RESUME)
        self.assertFalse(facing,
                         "EMAIL_RESUME was flipped to facing=True; the "
                         "narrower fix was declined")

    def test_email_resume_is_in_supported(self):
        """The stale 'NOT in SUPPORTED' comment was corrected."""
        self.assertIn(providerwrites.EMAIL_RESUME, providerwrites.SUPPORTED)

    def test_email_resume_has_a_conditional(self):
        """The CONDITIONAL predicate was registered."""
        self.assertIn(providerwrites.EMAIL_RESUME,
                      providerwrites.CONDITIONAL)


if __name__ == "__main__":
    unittest.main()
