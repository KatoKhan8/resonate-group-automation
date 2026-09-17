"""The ledger is the audit trail, so a row must describe its own event.

Two record-fidelity defects in `actionledger.settle`, both found by GLM's
adversarial review on 2026-09-17 and both confirmed against the source. Neither
lets a second prospect-facing action through - the reservation semantics are
untouched here - so neither is a safety defeat. What they cost is the
truthfulness of the one file that says what happened to a real person, which
is the thing the whole module exists to keep.

**Stale payload inheritance.** `settle` built its new row with `dict(prior)`
and then overwrote `provider_response` only when a caller passed one. So

    settle(k, UNRESOLVED, provider_response={"code": "421"})
    settle(k, FAILED)

produced a FAILED row carrying the deferral's 421 as though the failure had
produced it. Any later count of failures by provider code reads a deferral as
a hard bounce, durably, on every key that transits UNRESOLVED -> FAILED. This
estate has thirteen keys sitting at `unresolved` right now.

**Silent payload drop on same-state replay.** `settle` returned the stored row
whenever the state matched, before doing anything with the arguments. So a
second `settle(k, SENT, readback=...)` - a corrected provider message id, a
delivery readback that arrived after the first settlement - returned SUCCESS
while recording nothing.

The fix for the second keeps the idempotence that matters: an identical replay
still appends nothing, because at-least-once retries are the normal caller and
making those raise would be the more dangerous direction. Only a replay that
DISAGREES with the stored row is recorded, and it is recorded as a further
append, because this file never edits history.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import actionledger, store                              # noqa: E402


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._restore = store.use_directory(self.tmp.name)
        if callable(self._restore):
            self.addCleanup(self._restore)

    def rows(self, key):
        return actionledger.rows_for(key, actionledger.load())

    def reserve(self, contact):
        """One reservation, every required field named.

        `reserve` takes the key positionally and everything else by keyword on
        purpose - "an action whose tenant, campaign, sender or approved
        fingerprint cannot be named is an action nobody can audit afterwards".
        """
        key = f"email:487:{contact}:em1"
        actionledger.reserve(
            key, channel="email", workspace="productive", campaign_id="487",
            sender_id=2736, rec_id="acct-one", contact_key=contact,
            step_key="em1", operation="email_send", fingerprint="fp-1",
            provider_workspace=10)
        return key


class ASettlementDescribesItsOwnEvent(LedgerTest):

    def test_a_failure_does_not_inherit_the_deferrals_provider_response(self):
        key = self.reserve("c1")
        actionledger.settle(key, actionledger.UNRESOLVED,
                            provider_response={"code": "421",
                                               "phase": "deferred"})
        actionledger.settle(key, actionledger.FAILED, why="gave up")
        last = self.rows(key)[-1]
        self.assertEqual(last["state"], actionledger.FAILED)
        self.assertNotIn("provider_response", last,
                         "the failure inherited the deferral's response")

    def test_a_failure_keeps_its_own_provider_response(self):
        key = self.reserve("c2")
        actionledger.settle(key, actionledger.UNRESOLVED,
                            provider_response={"code": "421"})
        actionledger.settle(key, actionledger.FAILED,
                            provider_response={"code": "550"})
        self.assertEqual(self.rows(key)[-1]["provider_response"],
                         {"code": "550"})

    def test_a_readback_is_not_inherited_either(self):
        key = self.reserve("c3")
        actionledger.settle(key, actionledger.UNRESOLVED,
                            readback={"queue_rows": 1})
        actionledger.settle(key, actionledger.ABANDONED, why="operator")
        self.assertNotIn("readback", self.rows(key)[-1])

    def test_history_is_appended_and_never_edited(self):
        """The earlier row keeps its own evidence. Dropping it forward must
        not drop it backward."""
        key = self.reserve("c4")
        actionledger.settle(key, actionledger.UNRESOLVED,
                            provider_response={"code": "421"})
        actionledger.settle(key, actionledger.FAILED)
        rows = self.rows(key)
        unresolved = [r for r in rows
                      if r["state"] == actionledger.UNRESOLVED][-1]
        self.assertEqual(unresolved["provider_response"], {"code": "421"})


class ASameStateReplayIsNotSilentlyDiscarded(LedgerTest):

    def test_an_identical_replay_still_appends_nothing(self):
        """At-least-once retries are the normal caller and must stay cheap."""
        key = self.reserve("c5")
        actionledger.settle(key, actionledger.SENT, why="ok",
                            provider_response={"mid": "M1"})
        before = len(self.rows(key))
        actionledger.settle(key, actionledger.SENT, why="ok",
                            provider_response={"mid": "M1"})
        self.assertEqual(len(self.rows(key)), before)

    def test_a_replay_carrying_a_new_readback_is_recorded(self):
        key = self.reserve("c6")
        actionledger.settle(key, actionledger.SENT,
                            provider_response={"mid": "M1"})
        before = len(self.rows(key))
        actionledger.settle(key, actionledger.SENT,
                            readback={"delivered": True})
        rows = self.rows(key)
        self.assertEqual(len(rows), before + 1)
        self.assertEqual(rows[-1]["readback"], {"delivered": True})
        self.assertTrue(rows[-1].get("correction"))

    def test_a_correction_does_not_change_the_state(self):
        """A corrected message id is not an un-sending."""
        key = self.reserve("c7")
        actionledger.settle(key, actionledger.SENT,
                            provider_response={"mid": "M1"})
        actionledger.settle(key, actionledger.SENT,
                            provider_response={"mid": "M2"})
        self.assertEqual(actionledger.state_of(key), actionledger.SENT)
        self.assertEqual(self.rows(key)[-1]["provider_response"],
                         {"mid": "M2"})

    def test_a_correction_keeps_the_key_unreservable(self):
        """The whole point of TERMINAL: a sent key is never attempted again,
        and an extra row must not create a hole in that."""
        key = self.reserve("c8")
        actionledger.settle(key, actionledger.SENT,
                            provider_response={"mid": "M1"})
        actionledger.settle(key, actionledger.SENT,
                            readback={"delivered": True})
        with self.assertRaises(actionledger.ActionRefused):
            actionledger.require_clear(key)


if __name__ == "__main__":
    unittest.main()
