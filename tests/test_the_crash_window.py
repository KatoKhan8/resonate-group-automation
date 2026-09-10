#!/usr/bin/env python3
"""The dangerous window: the provider acted, and we died before writing it down.

This is the one failure that cannot be fixed by retrying, because the retry is
the harm. A connection request went out, the process died before the ledger was
settled, and on restart the only honest statement the system can make is "we do
not know whether this person was contacted". Treating that as "not contacted"
sends a second invitation to somebody who already has one.

The ledger is built for exactly this: `reserve` BEFORE the call, `settle` after,
and `ATTEMPTED` meaning "reserved, provider not yet known to have acted". The
tests below kill the process at each point in that sequence and assert what the
next run may and may not do.

NOTHING HERE CONTACTS ANYBODY. The provider is a fake whose only job is to
remember what it was told and to be readable afterwards.
"""
import unittest

from src import actionledger as ledger
from tests.base import QueueTest


class Died(BaseException):
    """The process being killed. Not an Exception - nothing may catch it."""


class FakeProvider:
    """A provider that records what reached it, and can be read back.

    `readable` models the case that makes UNRESOLVED necessary: the action may
    have happened and the provider cannot currently tell us.
    """

    def __init__(self, readable=True):
        self.acted_on = []
        self.readable = readable

    def act(self, key):
        self.acted_on.append(key)

    def read_back(self, key):
        if not self.readable:
            raise RuntimeError("provider truth is unavailable")
        return key in self.acted_on


KEY = "acme:dana:day3:linkedin"
RESERVE = dict(channel="linkedin", workspace="productive", campaign_id="594061",
               sender_id="116968", rec_id="acme", contact_key="dana",
               step_key="day3", operation="heyreach.add_lead",
               fingerprint="037e5c328dad")


class TheProviderActedAndWeDiedBeforeWritingItDown(QueueTest):

    def setUp(self):
        super().setUp()
        self.provider = FakeProvider()

    def crash_after_acting(self):
        """Reserve, act, then die before settling. The real window."""
        ledger.reserve(KEY, **RESERVE)
        self.provider.act(KEY)
        raise Died("killed between the provider call and the settle")

    def test_the_key_is_left_attempted_not_absent(self):
        with self.assertRaises(Died):
            self.crash_after_acting()
        self.assertEqual(ledger.state_of(KEY), ledger.ATTEMPTED)

    def test_a_blind_retry_is_refused(self):
        """The whole point. A second reserve must not succeed."""
        with self.assertRaises(Died):
            self.crash_after_acting()
        with self.assertRaises(ledger.ActionRefused):
            ledger.reserve(KEY, **RESERVE)
        self.assertEqual(self.provider.acted_on, [KEY],
                         "the prospect was contacted twice")

    def test_reading_provider_truth_settles_it_as_sent(self):
        """Recovery is a READ plus a settle, never a re-send."""
        with self.assertRaises(Died):
            self.crash_after_acting()
        self.assertTrue(self.provider.read_back(KEY))
        ledger.settle(KEY, ledger.SENT, why="confirmed by provider read-back")
        self.assertEqual(ledger.state_of(KEY), ledger.SENT)
        self.assertEqual(self.provider.acted_on, [KEY])

    def test_a_settled_sent_key_still_refuses_a_new_reservation(self):
        """Terminal means terminal: recovery must not reopen the key."""
        with self.assertRaises(Died):
            self.crash_after_acting()
        ledger.settle(KEY, ledger.SENT, why="confirmed")
        with self.assertRaises(ledger.ActionRefused):
            ledger.reserve(KEY, **RESERVE)
        self.assertEqual(ledger.state_of(KEY), ledger.SENT,
                         "a refused reservation regressed the durable state")

    def test_provider_truth_that_says_no_settles_as_failed_and_may_retry(self):
        """The other half. If it demonstrably did not happen, retrying is right."""
        ledger.reserve(KEY, **RESERVE)          # reserved, provider never called
        self.assertFalse(self.provider.read_back(KEY))
        ledger.settle(KEY, ledger.FAILED, why="provider has no record of it")
        ledger.reserve(KEY, **RESERVE)          # must not raise
        self.assertEqual(ledger.state_of(KEY), ledger.ATTEMPTED)


class WhenProviderTruthCannotSettleIt(QueueTest):
    """UNRESOLVED exists so "we do not know" is never read as "we did not"."""

    def setUp(self):
        super().setUp()
        self.provider = FakeProvider(readable=False)

    def test_an_unreadable_provider_leaves_it_unresolved(self):
        ledger.reserve(KEY, **RESERVE)
        self.provider.act(KEY)
        with self.assertRaises(RuntimeError):
            self.provider.read_back(KEY)
        ledger.settle(KEY, ledger.UNRESOLVED,
                      why="provider truth unavailable at recovery")
        self.assertEqual(ledger.state_of(KEY), ledger.UNRESOLVED)

    def test_unresolved_blocks_forever_rather_than_ageing_out(self):
        ledger.reserve(KEY, **RESERVE)
        ledger.settle(KEY, ledger.UNRESOLVED, why="unreadable")
        for _ in range(3):
            with self.assertRaises(ledger.ActionRefused):
                ledger.reserve(KEY, **RESERVE)

    def test_unresolved_is_not_counted_as_settled(self):
        """If it were, a sweep looking for open work would close it."""
        self.assertNotIn(ledger.UNRESOLVED, ledger.SETTLED)
        self.assertIn(ledger.UNRESOLVED, ledger.BLOCKING)

    def test_it_still_counts_as_exposure(self):
        """It may have reached somebody, so caps must charge for it."""
        ledger.reserve(KEY, **RESERVE)
        ledger.settle(KEY, ledger.UNRESOLVED, why="unreadable")
        reached = ledger.contacts_reached(channel="linkedin",
                                          workspace="productive")
        self.assertIn("dana", reached,
                      "an unresolved action was treated as no exposure, so the "
                      "cap would permit another person on a channel that "
                      "cannot be stopped")


class TheLedgerSurvivesTheProcess(QueueTest):
    """It is only recovery if it is on disk before the crash."""

    def test_a_reservation_is_durable_immediately(self):
        ledger.reserve(KEY, **RESERVE)
        rows = [r for r in ledger.load() if r.get("key") == KEY]
        self.assertTrue(rows, "the reservation was never written to disk")

    def test_a_fresh_read_sees_the_reservation(self):
        """`state_of` with no rows passed re-reads the file, as recovery does."""
        ledger.reserve(KEY, **RESERVE)
        self.assertEqual(ledger.state_of(KEY), ledger.ATTEMPTED)

    def test_the_reservation_records_who_it_was_for(self):
        """Recovery needs to know what to read back, not merely that something
        was in flight."""
        ledger.reserve(KEY, **RESERVE)
        row = [r for r in ledger.load() if r.get("key") == KEY][-1]
        for field in ("channel", "workspace", "campaign_id", "sender_id",
                      "rec_id", "contact_key", "step_key", "operation",
                      "fingerprint"):
            self.assertEqual(row.get(field), RESERVE[field], field)


if __name__ == "__main__":
    unittest.main()
