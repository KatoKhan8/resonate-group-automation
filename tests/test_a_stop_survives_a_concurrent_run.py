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
"""
import copy
import unittest

from src import eligibility, replies, store, verification
from tests.base import QueueTest

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

    def test_the_stale_checkpoint_is_refused(self):
        with self.assertRaises(store.HistoryLost):
            store.save(self.snapshot)

    def test_and_the_stop_is_still_there_afterwards(self):
        with self.assertRaises(store.HistoryLost):
            store.save(self.snapshot)
        self.assertTrue(set(self.decide()["reasons"]) & STOP_REASONS,
                        "the refusal did not protect the stop")

    def test_the_refusal_says_what_it_is_protecting(self):
        """An operator reading this has to know which record and what was at
        stake, or the guard is an obstacle rather than a finding."""
        with self.assertRaises(store.HistoryLost) as caught:
            store.save(self.snapshot)
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

    def test_the_stale_write_is_refused(self):
        with self.assertRaises(store.HistoryLost) as caught:
            store.save(self.snapshot)
        self.assertIn("account paused", str(caught.exception))

    def test_the_pause_is_still_set_afterwards(self):
        with self.assertRaises(store.HistoryLost):
            store.save(self.snapshot)
        self.assertTrue(store.load()[0].get("paused"))

    def test_an_account_suppression_is_protected_as_well(self):
        """The permanent form of the same statement."""
        live = store.load()
        live[0]["suppression"] = {"reason": "client_dnc",
                                  "at": "2026-09-11T10:00:00+00:00"}
        store.save(live)
        with self.assertRaises(store.HistoryLost) as caught:
            store.save(self.snapshot)
        self.assertIn("account suppressed", str(caught.exception))


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
