"""Restoring paid verification evidence from a record's own event log.

THE INCIDENT THIS REPAIRS. A batch verification run hit its budget ceiling and
emitted a `verification_result` with `state: unknown`, `reason: "no
verification evidence"` and `contact: null`. That contact-less verdict landed
on contacts that did have evidence: two addresses at `brightpath.test`,
answered by ContactOut and Reoon, came back `state: unknown`, `evidence: []`.

`accept_all_uncleared` means "a catch-all nothing cleared - do not send".
`unknown` means "ask again". So the loss converted a refusal into an
instruction to re-buy, and the ledger shows the re-buy had already happened
once. The whole point of restoring the evidence is that the third purchase
does not happen, which is what `TheRepairPreventsAnotherPurchase` measures.

The rule these tests exist to hold: a reconstruction that cannot be told apart
from evidence is worse than a gap. So every restored row is marked, no
provider field is invented, and the verdict is recomputed rather than copied
from the event that recorded it.
"""
import copy
import os
import shutil
import tempfile
import unittest

from src import events, evidencerepair, store, verification


def contact(key="c1", email="c1@example.test", name="C One"):
    return {"key": key, "name": name, "email": email, "title": "COO",
            "persona": "economic_buyer"}


def completed(key, provider, status, at):
    return {"type": events.PROVIDER_CALL_COMPLETED, "contact": key,
            "operation": "verify", "provider": provider, "status": status,
            "at": at, "estimated_cost": 1,
            "id": f"ev_{provider}_{key}_{at}"}


def record(contacts=None, excluded=None, evts=None):
    return {"id": "rec-1", "lane": "domains", "client": "productive",
            "company": "Example", "domain": "example.test",
            "state": "queued", "contacts": contacts or [],
            "excluded": excluded or [], "events": list(evts or [])}


# The shape of the real loss, reduced to what matters.
CATCH_ALL_HISTORY = [
    completed("c1", "contactout", "accept_all", "2026-09-08T13:27:31+00:00"),
    completed("c1", "deliverable", "error", "2026-09-08T15:17:59+00:00"),
    completed("c1", "reoon", "accept_all", "2026-09-08T15:18:00+00:00"),
]


class TheEvidenceComesBack(unittest.TestCase):
    def setUp(self):
        self.c = contact()
        self.c["verification"] = {"state": "unknown", "sendable": False,
                                  "reason": "no verification evidence",
                                  "evidence": [], "providers": []}
        self.rec = record(contacts=[self.c], evts=CATCH_ALL_HISTORY)

    def test_the_lost_rows_are_restored(self):
        evidencerepair.repair_contact(self.rec, self.c)
        stored = verification.evidence_of(self.c)
        self.assertEqual(len(stored), 3)
        self.assertEqual(sorted(e["provider"] for e in stored),
                         ["contactout", "deliverable", "reoon"])

    def test_the_verdict_is_the_one_the_evidence_supports(self):
        decision = evidencerepair.repair_contact(self.rec, self.c)
        self.assertEqual(decision["state"], verification.ACCEPT_ALL_UNCLEARED)
        self.assertFalse(decision["sendable"])
        self.assertEqual(self.c["verification"]["state"],
                         verification.ACCEPT_ALL_UNCLEARED)
        self.assertFalse(self.c["sendable"])

    def test_the_original_provider_and_moment_survive(self):
        evidencerepair.repair_contact(self.rec, self.c)
        by = {e["provider"]: e for e in verification.evidence_of(self.c)}
        self.assertEqual(by["contactout"]["at"], "2026-09-08T13:27:31+00:00")
        self.assertEqual(by["reoon"]["at"], "2026-09-08T15:18:00+00:00")
        self.assertEqual(by["contactout"]["status"], "accept_all")
        self.assertEqual(by["deliverable"]["status"], "error")

    def test_every_restored_row_says_it_was_reconstructed(self):
        evidencerepair.repair_contact(self.rec, self.c)
        for row in verification.evidence_of(self.c):
            self.assertTrue(row.get("reconstructed"), row)
            self.assertIn("event_id", row.get("reconstructed_from") or {})

    def test_no_provider_field_is_invented(self):
        """The event log records provider, status and moment. Nothing else.

        Inventing `safe_to_send: False` here would produce a more specific
        reason string and a fabricated provider answer, which is the thing a
        reconstruction must never do.
        """
        evidencerepair.repair_contact(self.rec, self.c)
        for row in verification.evidence_of(self.c):
            for field in ("deliverable", "safe_to_send", "catch_all",
                          "disposable", "role_account", "score"):
                self.assertIsNone(row[field], f"{field} was invented")

    def test_the_repair_is_recorded_in_the_log(self):
        evidencerepair.repair_contact(self.rec, self.c)
        kinds = [e["type"] for e in self.rec["events"]]
        self.assertIn(events.EVIDENCE_RECONSTRUCTED, kinds)

    def test_it_is_not_recorded_as_a_fresh_verification(self):
        """`evidence_reconstructed` exists so the log cannot claim a purchase.

        `apply` still writes its own `verification_result` because the stored
        verdict genuinely changed - but a reader can tell the two apart, and
        no `provider_call_started` is written because nothing was called.
        """
        before = len(self.rec["events"])
        evidencerepair.repair_contact(self.rec, self.c)
        added = self.rec["events"][before:]
        self.assertTrue(added)
        self.assertNotIn(events.PROVIDER_CALL_STARTED,
                         [e["type"] for e in added])


class TheStateIsRecomputedNotCopied(unittest.TestCase):
    """The recorded state is checked against, never trusted.

    If the old `verification_result` said `verified` while the surviving
    provider rows say `accept_all`, the evidence wins. Copying the recorded
    state would let a stale or wrong verdict be laundered into canonical state
    by the repair.
    """

    def test_a_recorded_verdict_cannot_override_the_evidence(self):
        c = contact()
        rec = record(contacts=[c], evts=CATCH_ALL_HISTORY + [
            {"type": events.VERIFICATION_RESULT, "contact": "c1",
             "channel": "email", "state": "verified",
             "reason": "a verdict that the evidence does not support",
             "at": "2026-09-08T15:18:01+00:00", "id": "ev_lie"},
        ])
        decision = evidencerepair.repair_contact(rec, c)
        self.assertEqual(decision["state"], verification.ACCEPT_ALL_UNCLEARED)
        self.assertFalse(decision["sendable"])

    def test_prose_is_never_read(self):
        """A result event with no provider call behind it restores nothing."""
        c = contact()
        rec = record(contacts=[c], evts=[
            {"type": events.VERIFICATION_RESULT, "contact": "c1",
             "channel": "email", "state": "accept_all_uncleared",
             "reason": "reoon says the catch-all is not safe to send",
             "at": "2026-09-08T13:27:30+00:00", "id": "ev_prose"},
        ])
        self.assertEqual(evidencerepair.missing_rows(rec, c), [])
        self.assertIsNone(evidencerepair.repair_contact(rec, c))


class EvidenceStaysWithItsOwnPerson(unittest.TestCase):
    def test_two_contacts_keep_their_own_answers(self):
        a = contact("a", "a@example.test", "A")
        b = contact("b", "b@example.test", "B")
        rec = record(contacts=[a], excluded=[b], evts=[
            completed("a", "contactout", "accept_all", "2026-09-08T13:00:00+00:00"),
            completed("b", "contactout", "invalid", "2026-09-08T13:00:01+00:00"),
            completed("b", "reoon", "invalid", "2026-09-08T13:00:02+00:00"),
        ])
        evidencerepair.repair_record(rec)
        self.assertEqual([e["provider"] for e in verification.evidence_of(a)],
                         ["contactout"])
        self.assertEqual(
            {e["email"] for e in verification.evidence_of(a)},
            {"a@example.test"})
        self.assertEqual(
            {e["email"] for e in verification.evidence_of(b)},
            {"b@example.test"})
        self.assertEqual(a["verification"]["state"],
                         verification.ACCEPT_ALL_UNCLEARED)
        self.assertEqual(b["verification"]["state"], verification.INVALID)

    def test_an_excluded_person_is_repaired_too(self):
        """An exclusion does not un-buy what was spent on somebody."""
        b = contact("b", "b@example.test", "B")
        rec = record(excluded=[b], evts=[
            completed("b", "contactout", "accept_all", "2026-09-08T13:00:00+00:00"),
        ])
        self.assertTrue(evidencerepair.repair_record(rec))
        self.assertEqual(len(verification.evidence_of(b)), 1)


class TheRepairIsAppendOnlyAndIdempotent(unittest.TestCase):
    def test_running_twice_does_not_duplicate_a_row(self):
        c = contact()
        rec = record(contacts=[c], evts=CATCH_ALL_HISTORY)
        evidencerepair.repair_contact(rec, c)
        first = len(verification.evidence_of(c))
        self.assertIsNone(evidencerepair.repair_contact(rec, c))
        self.assertEqual(len(verification.evidence_of(c)), first)

    def test_evidence_already_stored_is_kept(self):
        c = contact()
        kept = verification.result("reoon", "valid", email=c["email"],
                                   at="2026-09-01T00:00:00+00:00")
        c["verification"] = {"evidence": [kept]}
        rec = record(contacts=[c], evts=CATCH_ALL_HISTORY)
        evidencerepair.repair_contact(rec, c)
        stored = verification.evidence_of(c)
        self.assertIn(kept, stored)
        self.assertEqual(len(stored), 4)

    def test_a_row_already_stored_is_not_restored_again(self):
        c = contact()
        same = verification.result("contactout", "accept_all",
                                   email=c["email"],
                                   at="2026-09-08T13:27:31+00:00")
        c["verification"] = {"evidence": [same]}
        rec = record(contacts=[c], evts=CATCH_ALL_HISTORY)
        rows = evidencerepair.missing_rows(rec, c)
        self.assertEqual(sorted(r["provider"] for r in rows),
                         ["deliverable", "reoon"])


class TheRepairPreventsAnotherPurchase(unittest.TestCase):
    """The reason the repair is worth doing at all.

    Without the evidence, `verify` walks the whole waterfall again and buys
    ContactOut and Reoon a third time. With it, the `already have this one`
    guard in `verify` skips both, and only Deliverable is re-attempted -
    correctly, because an error is not an answer, and freely, because
    `require_contract` refuses before any HTTP call while
    `DELIVERABLE_RESULT_SHAPE` is unset.
    """

    def setUp(self):
        # ISOLATED BECAUSE THESE VERIFY WITH A REC AND `live=True`. That is a
        # paid call, and a paid call writes the spend ledger, which lives
        # beside the queue - so without this the ledger written is the
        # operator's own. It was: nineteen rows of fabricated spend landed in
        # the real `work/spend-ledger.jsonl` the hour verification was wired
        # into it. `spendledger.record` asks `refuse_production_write` now, so
        # this class is refused rather than silently believed, and the fix is
        # the one that refusal names - isolate the store.
        self.tmp = tempfile.mkdtemp(prefix="rga-evidence-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._prev_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = os.path.join(self.tmp, "work", "queue.jsonl")
        self.addCleanup(self._restore_queue)

        self.attempted = []
        self._real_call = verification.call

        def spy(provider, email):
            self.attempted.append(provider)
            return verification.result(provider, verification.S_UNKNOWN,
                                       email=email)

        verification.call = spy
        self.addCleanup(setattr, verification, "call", self._real_call)

    def _restore_queue(self):
        if self._prev_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev_queue

    def _verify(self, c, rec):
        self.attempted = []
        verification.verify(c, live=True, rec=rec)
        return list(self.attempted)

    def test_without_the_evidence_the_paid_providers_are_called_again(self):
        c = contact()
        c["verification"] = {"state": "unknown", "sendable": False,
                             "evidence": []}
        rec = record(contacts=[c], evts=CATCH_ALL_HISTORY)
        attempted = self._verify(c, rec)
        self.assertIn("contactout", attempted)
        self.assertIn("reoon", attempted)

    def test_after_the_repair_neither_chargeable_provider_is_called(self):
        c = contact()
        c["verification"] = {"state": "unknown", "sendable": False,
                             "evidence": []}
        rec = record(contacts=[c], evts=CATCH_ALL_HISTORY)
        evidencerepair.repair_contact(rec, c)
        attempted = self._verify(c, rec)
        self.assertNotIn("contactout", attempted)
        self.assertNotIn("reoon", attempted)

    def test_deliverable_alone_is_retried_because_an_error_is_not_an_answer(self):
        c = contact()
        c["verification"] = {"state": "unknown", "sendable": False,
                             "evidence": []}
        rec = record(contacts=[c], evts=CATCH_ALL_HISTORY)
        evidencerepair.repair_contact(rec, c)
        self.assertEqual(self._verify(c, rec), ["deliverable"])

    def test_selection_churn_does_not_reopen_the_purchase(self):
        """Moving somebody between `contacts` and `excluded` keeps the guard.

        Re-running selection is what wiped the evidence the first time, so the
        repair has to survive the same movement.
        """
        c = contact()
        rec = record(contacts=[c], evts=CATCH_ALL_HISTORY)
        evidencerepair.repair_contact(rec, c)
        moved = copy.deepcopy(c)
        rec["contacts"], rec["excluded"] = [], [moved]
        self.assertNotIn("contactout", self._verify(moved, rec))


class TheRepairRunsOverTheStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-repair-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        saved = {n: os.environ.get(n)
                 for n in ("QUEUE",) + store.STATE_OVERRIDES}
        self.addCleanup(self._restore, saved)
        store.use_directory(os.path.join(self.tmp, "work"))

    @staticmethod
    def _restore(saved):
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_a_dry_run_writes_nothing(self):
        c = contact()
        store.save([record(contacts=[c], evts=CATCH_ALL_HISTORY)])
        out = evidencerepair.run(live=False)
        self.assertEqual(len(out["found"]), 1)
        after = store.load()[0]["contacts"][0]
        self.assertEqual(verification.evidence_of(after), [])

    def test_a_live_run_writes_the_evidence(self):
        c = contact()
        store.save([record(contacts=[c], evts=CATCH_ALL_HISTORY)])
        out = evidencerepair.run(live=True)
        self.assertEqual(len(out["repaired"]), 1)
        after = store.load()[0]["contacts"][0]
        self.assertEqual(len(verification.evidence_of(after)), 3)
        self.assertEqual(after["verification"]["state"],
                         verification.ACCEPT_ALL_UNCLEARED)

    def test_the_evidence_guard_permits_the_repair(self):
        """The repair adds rows, so `refuse_evidence_loss` must not fire."""
        c = contact()
        store.save([record(contacts=[c], evts=CATCH_ALL_HISTORY)])
        evidencerepair.run(live=True)
        evidencerepair.run(live=True)          # second pass: nothing to add
        after = store.load()[0]["contacts"][0]
        self.assertEqual(len(verification.evidence_of(after)), 3)


if __name__ == "__main__":
    unittest.main()
