#!/usr/bin/env python3
"""A reply that stopped somebody must not be erased by a run that never saw it.

REPRODUCED on 2026-09-11, with nothing crashing and no race to lose - just two
writers and a stale snapshot:

  1. a pipeline run loads the queue and spends minutes in provider I/O
  2. a prospect replies "please remove us from your list"; the reply is
     persisted correctly and `eligibility.decide` answers
     `blocked:contact_paused`
  3. the run reaches its next checkpoint and saves the snapshot it loaded in
     step 1

After step 3 the events and the pause are gone, and `eligibility.decide`
answers `held:draft_not_approved` - an APPROVAL gate, not a stop. Approve that
copy and the next step goes to somebody who asked to be removed.

`refuse_evidence_loss` had nothing to object to, because the paid verification
evidence was present in both copies. That is the whole shape of it: the guard
that existed protected the credits and not the person.

## The remedy already existed and was not used

`store.save`'s own docstring described this defect and prescribed the fix - a
caller that cannot hold the lock throughout passes `expect_digest`. Exactly one
caller does (`inbound.ingest`). The three that hold a whole-queue snapshot
across minutes of provider I/O - `run.checkpoint`, `run`'s final save and
`enrich.run` - do not, and they are precisely the callers the docstring warns
about. So the guard moved to the boundary every writer already crosses, which
also covers the next caller to be written.

## Why it can be strict

Nothing in `src/` clears a pause or removes an event. `accountpolicy` sets
them; `resume_campaign` lifts a CAMPAIGN pause, which lives in the campaign
file. So there is no legitimate production caller to accommodate, and
`tests/test_invariants.py` asserts that no `src/` module reaches for the
test-cleanup escape hatch.

## And then the refusal stopped being the whole answer

Refusing protected the stop by throwing the write away, which is the right
trade only if the write is worthless. It is not: the same snapshot carries
every record the run has already paid a provider for, and the refusal left
`run.checkpoint` - which had no handler - aborting the batch outright. The
stop was safe and the run's work was gone.

`store.Snapshot` closes it from the other side. A reader records what each
row was when it read it, so a write-back can tell a field this caller
actually changed from a field it is merely holding a stale copy of. A record
the run never touched keeps whatever is on disk; a record it did touch is
merged field by field. The reply, the events, the contact pause and the
account pause all live in fields a pipeline run never writes, so they survive
either way - and now the run's own work survives with them.

The guard did not move and did not soften. It still runs, on the merged
result, and still refuses a writer that genuinely deletes history - which is
any caller holding rows that did not come from `load`, because that caller
has no baseline and nothing can distinguish its edit from its ignorance.
Those are the tests below that still assert `HistoryLost`, and they are there
so that the day somebody deletes the merge, this file says so.
"""
import copy
import unittest

from src import eligibility, replies, store, verification
from tests.base import QueueTest, pin_client_config

STOP_REASONS = {"blocked:contact_paused", "blocked:replied",
                "blocked:contact_stopped", "blocked:suppressed",
                "blocked:unsubscribed", "blocked:company_paused"}


def a_verified_contact(email="dana@acme.test"):
    """Fully verified on purpose: with evidence in both copies of the record,
    `refuse_evidence_loss` passes and only the history guard can refuse."""
    return {"key": "acme-1", "name": "Dana Reed", "email": email,
            "selected": True, "verdict": "valid", "sendable": True,
            "persona": "champion", "angle": "operations",
            "verification": {"evidence": [
                verification.result("contactout", "valid", email),
                verification.result("reoon", "valid", email)]}}


class TheStopSurvives(QueueTest):
    """`QueueTest` rather than a bare `TestCase` with `use_directory`: that
    call redirects the whole process and does not put it back, so a later
    module in the same run reads this test's temp directory as its own. Done
    once here and caught by an unrelated invariant two modules away."""

    def setUp(self):
        super().setUp()
        # Pinned, not loaded. This module is not about which cadence
        # Productive currently runs, and the modules under test load
        # the client file themselves.
        pin_client_config(self)
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["state"] = "verified"
        rec["contacts"] = [a_verified_contact()]
        rec["cadence"] = {"acme-1": {"day5": {
            "channel": "email", "subject": "resourcing at Acme",
            "body": "I work with design teams on resourcing visibility. " * 4}}}
        store.save([rec])
        # What a long run holds: everything, loaded before the reply arrives.
        self.snapshot = copy.deepcopy(store.load())
        live = store.load()
        replies.apply(live[0], "acme-1", "please remove us from your list",
                      at="2026-09-11T10:00:00+00:00", channel="email")
        store.save(live)

    def decide(self):
        rec = store.load()[0]
        return eligibility.decide(rec, rec["contacts"][0], "day5",
                                  channel="email", recs=[rec])

    def test_the_reply_stops_it_to_begin_with(self):
        """The baseline. Without this the rest proves nothing."""
        self.assertTrue(set(self.decide()["reasons"]) & STOP_REASONS)

    def test_the_stale_checkpoint_no_longer_has_anything_to_refuse(self):
        """The write SUCCEEDS, and that is the improvement rather than a hole.

        `store.Snapshot` merges the checkpoint onto what is on disk, and this
        run never touched the record, so the reply, its events and its pause
        are kept and there is nothing left for the guard to object to. The
        refusal that used to fire here protected the stop by discarding the
        whole write, which cost the run every record it had already paid for.
        Now the stop survives AND the work persists. The guard is untouched
        and still fires for a writer that really does destroy history - see
        `test_a_writer_with_no_baseline_is_still_refused`.
        """
        store.save(self.snapshot)
        self.assertTrue(set(self.decide()["reasons"]) & STOP_REASONS)

    def test_and_the_stop_is_still_there_afterwards(self):
        store.save(self.snapshot)
        self.assertTrue(set(self.decide()["reasons"]) & STOP_REASONS,
                        "the merge did not protect the stop")

    def test_a_run_that_did_edit_the_record_still_cannot_lift_the_stop(self):
        """The adversarial half. An untouched record is the easy case - the
        merge keeps the disk row whole. This one was edited by the run, so it
        goes through the field-by-field merge, where the run must win only the
        field it actually changed."""
        mine = copy.deepcopy(self.snapshot)
        mine[0]["company_facts"] = {"probed": True}
        store.save(mine)
        self.assertTrue(store.load()[0]["company_facts"]["probed"],
                        "the run's own work was dropped")
        self.assertTrue(set(self.decide()["reasons"]) & STOP_REASONS,
                        "an editing run lifted the stop")

    def test_a_writer_with_no_baseline_is_still_refused(self):
        """THE GUARD IS STILL ARMED, and this is what proves it.

        A plain list is a caller that built its rows somewhere other than
        `load`, so there is no baseline and no way to tell its edit from its
        ignorance. That write is refused exactly as it was before.
        """
        with self.assertRaises(store.HistoryLost):
            store.save(list(self.snapshot))
        self.assertTrue(set(self.decide()["reasons"]) & STOP_REASONS)

    def test_the_refusal_says_what_it_is_protecting(self):
        """An operator reading this has to know which record and what was at
        stake, or the guard is an obstacle rather than a finding."""
        with self.assertRaises(store.HistoryLost) as caught:
            store.save(list(self.snapshot))
        said = str(caught.exception)
        self.assertIn("acme", said)
        self.assertIn("event", said)
        self.assertIn("stop lifted", said)


class TheAccountWidePauseIsProtectedToo(QueueTest):
    """`rec["paused"]` is the wider stop and the one worth more.

    A contact pause stops one person; an account pause is what
    `accountpolicy.apply_reply` writes when a reply holds the WHOLE company, so
    losing it re-opens colleagues who never replied to anybody. The first
    version of these tests exercised only the contact flag, and a mutation that
    stopped indexing the account pause survived every one of them.
    """

    def setUp(self):
        super().setUp()
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [a_verified_contact()]
        store.save([rec])
        self.snapshot = copy.deepcopy(store.load())
        live = store.load()
        live[0]["paused"] = {"since": "2026-09-11T10:00:00+00:00",
                             "reason": "reply_received",
                             "why": "somebody at this company replied"}
        store.save(live)

    def test_the_stale_write_with_no_baseline_is_refused(self):
        with self.assertRaises(store.HistoryLost) as caught:
            store.save(list(self.snapshot))
        self.assertIn("account paused", str(caught.exception))

    def test_the_pause_is_still_set_afterwards(self):
        store.save(self.snapshot)
        self.assertTrue(store.load()[0].get("paused"),
                        "the merge dropped the account pause")

    def test_an_editing_run_keeps_the_account_pause_too(self):
        mine = copy.deepcopy(self.snapshot)
        mine[0]["company_facts"] = {"probed": True}
        store.save(mine)
        self.assertTrue(store.load()[0].get("paused"),
                        "an editing run lifted the account pause")
        self.assertTrue(store.load()[0]["company_facts"]["probed"])

    def test_an_account_suppression_is_protected_as_well(self):
        """The permanent form of the same statement."""
        live = store.load()
        live[0]["suppression"] = {"reason": "client_dnc",
                                  "at": "2026-09-11T10:00:00+00:00"}
        store.save(live)
        with self.assertRaises(store.HistoryLost) as caught:
            store.save(list(self.snapshot))
        self.assertIn("account suppressed", str(caught.exception))
        store.save(self.snapshot)                    # and the merge keeps it
        self.assertTrue(store.load()[0].get("suppression"))


class TheGuardDoesNotStopOrdinaryWork(QueueTest):
    """A guard that refuses legitimate writes is one somebody deletes."""

    def setUp(self):
        super().setUp()
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [a_verified_contact()]
        store.save([rec])

    def test_an_ordinary_save_passes(self):
        recs = store.load()
        recs[0]["state"] = "enriched"
        store.save(recs)
        self.assertEqual(store.load()[0]["state"], "enriched")

    def test_appending_an_event_passes(self):
        recs = store.load()
        replies.apply(recs[0], "acme-1", "not interested, thanks",
                      at="2026-09-11T11:00:00+00:00", channel="email")
        store.save(recs)
        self.assertTrue(store.load()[0]["events"])

    def test_a_second_reply_on_top_of_the_first_passes(self):
        """Two stops are more stop, not less. The guard counts losses only."""
        recs = store.load()
        replies.apply(recs[0], "acme-1", "not interested",
                      at="2026-09-11T11:00:00+00:00", channel="email")
        store.save(recs)
        recs = store.load()
        replies.apply(recs[0], "acme-1", "please remove us",
                      at="2026-09-11T12:00:00+00:00", channel="email")
        store.save(recs)
        self.assertGreaterEqual(len(store.load()[0]["events"]), 2)

    def test_adding_a_record_passes(self):
        recs = store.load()
        recs.append(store.new_record("borealis", "domains", "productive",
                                     "Borealis", "borealis.test"))
        store.save(recs)
        self.assertEqual(len(store.load()), 2)

    def test_a_record_absent_from_the_write_is_not_flagged(self):
        """Removal is governed by "never delete a record, drop it with a
        reason" - a different rule with its own guard, as the evidence guard
        already documents for itself."""
        recs = store.load()
        store.save([r for r in recs if r["id"] != "acme"])


if __name__ == "__main__":
    unittest.main()
