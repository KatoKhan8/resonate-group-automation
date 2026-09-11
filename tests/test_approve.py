"""Human approval. Nothing ships because a machine thought it was fine.

Lint clean is a precondition for approval, never a substitute for it.
"""
import contextlib
import os
import shutil
import tempfile
import unittest

from src import approval, approve, cadence, clients, lint, push, store
from tests.base import FIXTURES


@contextlib.contextmanager
def degraded_fixture():
    """Construct a record that was never fully verified.

    NOT a write under test. `store.transaction()` now runs the same loss
    guards as `save` - `refuse_evidence_loss` and `refuse_history_loss` - so
    the path that used to let a fixture delete paid verification evidence
    correctly refuses. These tests need a HALF-confirmed contact, and they
    were building one by degrading a fully-confirmed one, which is exactly
    the write the guard exists to stop.

    Writing the state directly keeps the fixture honest about what it is: a
    starting condition, not an operation the product performs.
    """
    recs = store.load()
    yield recs
    store._write(recs)


PARA = chr(10) * 2


class ApproveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-approve-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = clients.load("productive")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid="meridian"):
        return store.get(rid)

    def approve(self, rid="meridian", contact="ivana-saric", step="day1", by="zb"):
        with store.transaction() as recs:
            rec = store.get(rid, recs)
            return approve.approve_step(rec, contact, step, by=by, config=self.config)

    def status(self, rid="meridian", contact="ivana-saric", step="day1"):
        timeline = cadence.build(self.rec(rid), self.config)
        return timeline["contacts"][contact][step]["status"]

    def prepared_ids(self, day=30):
        return {i["push_id"] for i in push.run(day=day)["ready"]}


class TestUnapprovedWork(ApproveTest):
    def test_a_lint_clean_draft_is_not_eligible_until_approved(self):
        rec = self.rec()
        step = cadence.build(rec, self.config)["contacts"]["ivana-saric"]["day1"]
        self.assertEqual(lint.check(rec, "ivana-saric", step), [])
        self.assertEqual(step["status"], "unapproved")

    def test_nothing_unapproved_reaches_a_push_payload(self):
        result = push.run(day=30)
        self.assertEqual(result["ready"], [])
        self.assertEqual(result["counts"]["email"], 0)
        self.assertEqual(result["counts"]["linkedin"], 0)

    def test_the_reason_is_reported_rather_than_silently_skipped(self):
        skipped = push.run(day=30)["skipped"]
        self.assertTrue(any(s.get("why") == "unapproved" for s in skipped))

    def test_pending_lists_what_a_human_has_to_look_at(self):
        result = approve.pending()
        self.assertTrue(result["waiting"])
        waiting = {(w["id"], w["contact"], w["step"]) for w in result["waiting"]}
        self.assertIn(("meridian", "ivana-saric", "day1"), waiting)


class TestApproving(ApproveTest):
    def test_an_approved_step_becomes_eligible(self):
        self.approve()
        self.assertEqual(self.status(), "eligible")

    def test_an_approved_step_reaches_the_push_payload(self):
        self.approve()
        self.assertIn("meridian:ivana-saric:day1:email", self.prepared_ids())

    def test_only_the_approved_step_becomes_eligible(self):
        self.approve()
        self.assertEqual(self.status(step="day5"), "unapproved")
        prepared = self.prepared_ids()
        self.assertNotIn("meridian:ivana-saric:day5:email", prepared)

    def test_approval_records_who_and_when_and_what(self):
        stamp = self.approve(by="operator")
        stored = approval.approval_of(self.rec(), "ivana-saric", "day1")
        self.assertEqual(stored["by"], "operator")
        self.assertTrue(stored["at"])
        self.assertEqual(stored["fingerprint"], stamp["fingerprint"])

    def test_approval_is_auditable_in_the_log_and_the_events(self):
        self.approve(by="operator")
        rec = self.rec()
        self.assertTrue(any(e["step"] == "approved" and "operator" in e["note"]
                            for e in rec["log"]))
        self.assertTrue(any(e["type"] == "draft_approved" for e in rec["events"]))

    def test_approving_a_whole_record_approves_every_approvable_step(self):
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            result = approve.approve_record(rec, by="zb", config=self.config)
        self.assertTrue(result["approved"])
        self.assertEqual(self.status(), "eligible")
        self.assertEqual(self.status(step="day5"), "eligible")

    def test_approval_survives_a_reload_and_a_rerun(self):
        self.approve()
        first = self.prepared_ids()
        self.assertEqual(self.prepared_ids(), first)
        self.assertIn("meridian:ivana-saric:day1:email", first)


class TestWhatCannotBeApproved(ApproveTest):
    def refuse(self, rid="meridian", contact="ivana-saric", step="day1"):
        with store.transaction() as recs:
            rec = store.get(rid, recs)
            with self.assertRaises(approve.NotApprovable) as e:
                approve.approve_step(rec, contact, step, by="zb", config=self.config)
            return str(e.exception)

    def test_a_dropped_record_cannot_be_approved(self):
        store.drop("meridian", "suppressed (live account)")
        self.assertIn("record is dropped", self.refuse())

    def test_a_held_record_cannot_have_its_email_approved(self):
        with store.transaction() as recs:
            store.get("meridian", recs)["state"] = "held"
        self.assertIn("record is held", self.refuse())

    def test_a_held_record_can_still_have_its_linkedin_approved(self):
        """`held` is an email judgement, and it used to refuse every channel.

        `enrich.outcome` sets it when no address cleared verification. Refusing
        the LinkedIn steps too silently takes the surviving channel away from a
        contact whose profile is perfectly usable - which is exactly the
        failure `channels.py` exists to prevent, undone one module later.
        `lint.UNSHIPPABLE` has always drawn this line in the right place, which
        is why `eligibility.decide` never had the bug and only the approver did.
        """
        with store.transaction() as recs:
            store.get("meridian", recs)["state"] = "held"
            rec = store.get("meridian", recs)
            stamp = approve.approve_step(rec, "ivana-saric", "day3",
                                         by="zb", config=self.config)
        self.assertTrue(stamp["fingerprint"])

    def test_a_dropped_record_still_refuses_both_channels(self):
        store.drop("meridian", "suppressed (live account)")
        for step in ("day1", "day3"):
            self.assertIn("record is dropped",
                          self.refuse(step=step), step)

    def test_an_unverified_recipient_cannot_be_approved(self):
        from src import verification
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            contact = rec["contacts"][0]
            evidence = [verification.result("contactout", verification.S_UNKNOWN,
                                            contact["email"])]
            verification.apply(contact, verification.decide(evidence), evidence)
        self.assertIn("not sendable", self.refuse())

    def test_a_draft_that_fails_lint_cannot_be_approved(self):
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["cadence"]["ivana-saric"]["day1"]["body"] = "far too short"
        self.assertIn("fails lint", self.refuse())

    def test_a_paused_company_cannot_be_approved(self):
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            cadence.record_event(rec, "email_reply", "ivana-saric")
        self.assertIn("company is paused", self.refuse())

    def test_an_unknown_contact_cannot_be_approved(self):
        self.assertIn("no such contact", self.refuse(contact="nobody-here"))

    def test_a_refusal_writes_no_approval(self):
        store.drop("meridian", "suppressed (live account)")
        self.refuse()
        self.assertIsNone(approval.approval_of(self.rec(), "ivana-saric", "day1"))

    def test_blocked_steps_are_reported_with_their_reason(self):
        result = approve.pending()
        blocked = {(b["id"], b["contact"], b["step"]): b["why"]
                   for b in result["blocked"]}
        self.assertTrue(blocked)
        self.assertTrue(any("not sendable" in why or "fails lint" in why
                            or "no LinkedIn" in why for why in blocked.values()))


class TestEditingInvalidatesApproval(ApproveTest):
    def test_changing_the_body_after_approval_requires_re_approval(self):
        self.approve()
        self.assertEqual(self.status(), "eligible")

        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["cadence"]["ivana-saric"]["day1"]["body"] += "\n\nOne more thought for you here."

        self.assertEqual(self.status(), "unapproved")
        self.assertNotIn("meridian:ivana-saric:day1:email", self.prepared_ids())

    def test_changing_the_subject_after_approval_requires_re_approval(self):
        self.approve()
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["cadence"]["ivana-saric"]["day1"]["subject"] = "a different subject"
        self.assertEqual(self.status(), "unapproved")

    def test_re_approving_the_edited_draft_makes_it_eligible_again(self):
        self.approve()
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["cadence"]["ivana-saric"]["day1"]["subject"] = "a different subject"
        self.assertEqual(self.status(), "unapproved")
        self.approve()
        self.assertEqual(self.status(), "eligible")

    def test_a_template_change_invalidates_an_approved_template_step(self):
        """Templates are expanded on read, so the evidence behind one matters."""
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            approve.approve_step(rec, "ivana-saric", "day5", by="zb", config=self.config)
        self.assertEqual(self.status(step="day5"), "eligible")

        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["evidence"] = {"ivana-saric": ["a different opening line entirely"]}
        self.assertEqual(self.status(step="day5"), "unapproved")

    def test_revoking_an_approval_removes_eligibility(self):
        self.approve()
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            approve.revoke(rec, "ivana-saric", "day1", why="a second look")
        self.assertEqual(self.status(), "unapproved")
        self.assertTrue(any(e["step"] == "approval_revoked" for e in self.rec()["log"]))

    def test_the_fingerprint_covers_every_field_a_human_reads(self):
        base = {"channel": "email", "subject": "s", "body": "b", "note": None}
        self.assertNotEqual(approval.fingerprint(base),
                            approval.fingerprint({**base, "subject": "s2"}))
        self.assertNotEqual(approval.fingerprint(base),
                            approval.fingerprint({**base, "body": "b2"}))
        self.assertNotEqual(approval.fingerprint({"channel": "linkedin", "note": "a"}),
                            approval.fingerprint({"channel": "linkedin", "note": "b"}))

    def test_the_fingerprint_is_deterministic_across_runs(self):
        step = {"channel": "email", "subject": "s", "body": "b"}
        self.assertEqual(approval.fingerprint(step), approval.fingerprint(dict(step)))


class TestApprovalIsResumable(ApproveTest):
    def test_approving_twice_is_harmless(self):
        first = self.approve()
        second = self.approve()
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(self.status(), "eligible")

    def test_an_approved_step_that_was_pushed_is_not_offered_again(self):
        self.approve()
        item = next(i for i in push.run(day=30)["ready"]
                    if i["step_key"] == "day1" and i["record"]["id"] == "meridian")
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            push.mark_pushed(rec, "ivana-saric", "day1", item["push_id"])
        self.assertNotIn(item["push_id"], self.prepared_ids())

    def test_approval_state_lives_in_the_queue_and_nowhere_else(self):
        self.approve()
        with open(self.queue, encoding="utf-8") as f:
            self.assertIn("approval", f.read())
        work = os.path.dirname(self.queue)
        self.assertEqual(sorted(os.listdir(work)), ["queue.jsonl"])


class TestTheRecordLevelState(ApproveTest):
    """`approved` in store.STATES was declared and never written.

    BUILD-SPEC section 3 documents `drafted -> approved -> pushed`, and for the
    whole build nothing moved a record into `approved`. These tests are the
    contract that keeps it written, and - more importantly - that keeps it
    *derived*, so an edited draft cannot leave a stale blessing behind.
    """

    def approve_all(self, rid="meridian"):
        with store.transaction() as recs:
            rec = store.get(rid, recs)
            return approve.approve_record(rec, by="zb", config=self.config)

    def test_a_record_with_unapproved_steps_stays_drafted(self):
        self.assertEqual(self.rec()["state"], "drafted")

    def test_approving_one_step_of_several_does_not_approve_the_record(self):
        self.approve()
        self.assertEqual(self.rec()["state"], "drafted")

    def test_approving_every_step_moves_the_record_to_approved(self):
        result = self.approve_all()
        self.assertTrue(result["approved"])
        self.assertEqual(self.rec()["state"], "approved")

    def test_the_state_is_a_declared_one(self):
        self.approve_all()
        self.assertIn(self.rec()["state"], store.STATES)

    def test_revoking_one_step_takes_the_record_back_to_drafted(self):
        self.approve_all()
        self.assertEqual(self.rec()["state"], "approved")
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            contact_key = next(iter(rec["cadence"]))
            step_key = next(iter(rec["cadence"][contact_key]))
            approve.revoke(rec, contact_key, step_key, why="test")
        self.assertEqual(self.rec()["state"], "drafted")

    def test_editing_an_approved_draft_drops_the_record_out_of_approved(self):
        """The invalidation WEB-READINESS promises, at record level.

        The step-level fingerprint already goes stale on an edit. This asserts
        the record-level state follows it rather than latching.
        """
        self.approve_all()
        self.assertEqual(self.rec()["state"], "approved")
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            contact_key = next(iter(rec["cadence"]))
            for step_key, slot in rec["cadence"][contact_key].items():
                if slot.get("body"):
                    slot["body"] = slot["body"] + PARA + "One more line."
                    break
            approve.sync_state(rec, self.config)
        self.assertEqual(self.rec()["state"], "drafted")

    def test_a_dropped_record_is_never_moved_by_the_sync(self):
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["state"] = "dropped"
            approve.sync_state(rec, self.config)
        self.assertEqual(self.rec()["state"], "dropped")

    def test_a_held_record_is_never_moved_by_the_sync(self):
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["state"] = "held"
            approve.sync_state(rec, self.config)
        self.assertEqual(self.rec()["state"], "held")

    def test_a_pushed_record_is_never_moved_back_by_the_sync(self):
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["state"] = "pushed"
            approve.sync_state(rec, self.config)
        self.assertEqual(self.rec()["state"], "pushed")

    def test_bulk_approval_builds_the_cadence_twice_not_once_per_step(self):
        """Deriving the record state rebuilds the whole cadence.

        Doing that inside `approve_step` turned one timeline build into one per
        step - 23 for a 21-step record - and cadence is the most expensive
        thing in this codebase at batch size. `approve_record` syncs once.
        """
        calls = []
        real = cadence.build

        def counting(*args, **kwargs):
            calls.append(1)
            return real(*args, **kwargs)

        cadence.build = counting
        try:
            with store.transaction() as recs:
                rec = store.get("meridian", recs)
                result = approve.approve_record(rec, by="zb", config=self.config)
        finally:
            cadence.build = real
        self.assertGreater(len(result["approved"]), 5)
        self.assertLessEqual(len(calls), 2)

    def test_a_single_approval_still_syncs_by_default(self):
        """The bulk optimisation must not silently disarm the single path."""
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            for contact_key, steps in cadence.build(rec, self.config)["contacts"].items():
                for step_key in steps:
                    try:
                        approve.approve_step(rec, contact_key, step_key,
                                             by="zb", config=self.config)
                    except approve.NotApprovable:
                        pass
        self.assertEqual(self.rec()["state"], "approved")

    def test_a_record_with_nothing_approvable_is_not_called_approved(self):
        """Vacuous truth is the trap: all() over an empty list is True."""
        with degraded_fixture() as recs:
            rec = store.get("meridian", recs)
            rec["contacts"] = []
            rec["cadence"] = {}
            self.assertFalse(approve.fully_approved(rec, self.config))
            approve.sync_state(rec, self.config)
        self.assertEqual(self.rec()["state"], "drafted")


if __name__ == "__main__":
    unittest.main()
