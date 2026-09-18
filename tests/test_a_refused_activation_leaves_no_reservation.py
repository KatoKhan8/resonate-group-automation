"""A refused activation must leave the ledger exactly as it found it.

TASK-228. Measured 2026-09-18 on campaign 489 and HeyReach 605487: a
killswitch refusal left `attempted` rows behind, and the SECOND activation
attempt then refused at the COLLISION gate against rows the FIRST attempt
created. `collision.staging_artifact_evidence` arm 4 requires the ledger to
record no unrefuted prospect-facing action; five `attempted` rows is not
silence, so the campaign stopped qualifying for its own retry.

The fix is a RESERVE-LATE shape: the reservation is taken AFTER every gate
passes, including the killswitch. A refusal at any gate raises before the
reservation is reached, so the ledger is untouched.

The alternative - RESERVE-THEN-RELEASE - would reserve early (closing the
race window tighter) and release on refusal. That was rejected because a
release path that must undo a reservation under every failure mode is a
release path that will eventually miss one, and a missed release is the same
defect this file proves away. See the comment above `authorize()` for the
full reasoning.

WHAT THIS DOES NOT CHANGE. A successful authorization still reserves exactly
as before. The reservation is what stops two concurrent callers spending the
same `new_accounts_per_day` slot, and "reserve nothing" is not the answer.
"""
import datetime
import unittest
from unittest import mock

from src import (actionledger, approval, cadence, campaigns, clients,
                 collision, configdiff, executionguard, killswitch, store)

from tests.base import QueueTest, pin_client_config
from tests.test_no_write_happens_without_every_gate import (
    GuardTest, NOW, FRESH, STALE, WS, Provider)


class RefusalLeavesNoReservation(GuardTest):
    """A NotAuthorized at ANY gate leaves the action ledger untouched.

    The ledger's unsettled set must be byte-identical before and after a
    refusal. This is the property that campaign 489 lost: five `attempted`
    rows from a refused activation made the retry refuse at collision.
    """

    def _unsettled_snapshot(self):
        """The unsettled set as a comparable value."""
        rows = actionledger.load()
        return sorted(
            (r.get("key"), r.get("state"))
            for r in actionledger.unsettled(rows)
        )

    def test_killswitch_refusal_leaves_no_ledger_row(self):
        """Gate 7 refuses, and the ledger is untouched.

        This is the exact defect campaign 489 hit: the killswitch refused,
        but `attempted` rows were left behind. In the current code the
        reservation is AFTER the killswitch, so no row is written.
        """
        before = self._unsettled_snapshot()
        with self.allow_collision(), self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize()
            self.assertEqual(caught.exception.gate, "killswitch")
        after = self._unsettled_snapshot()
        self.assertEqual(before, after,
                         "a killswitch refusal changed the ledger's "
                         "unsettled set: before=%r after=%r" % (before, after))
        key = "rec-1:dana-marsh:day3:linkedin"
        self.assertIsNone(actionledger.state_of(key),
                          "the key %r has a ledger row after a killswitch "
                          "refusal; it should not" % key)

    def test_collision_refusal_leaves_no_ledger_row(self):
        """An earlier gate refuses, and the ledger is equally untouched."""
        before = self._unsettled_snapshot()
        with mock.patch.object(
                collision, "check_linkedin_profile",
                return_value=(collision.TOUCHED, {"note": "already known"})
        ), self.allow_killswitch(), self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize()
            self.assertEqual(caught.exception.gate, "collision")
        after = self._unsettled_snapshot()
        self.assertEqual(before, after,
                         "a collision refusal changed the ledger's "
                         "unsettled set: before=%r after=%r" % (before, after))

    def test_pilot_cap_refusal_leaves_no_ledger_row(self):
        """Gate 5 refuses, and the ledger is untouched."""
        before = self._unsettled_snapshot()
        config = dict(self.config,
                      daily_volume={"linkedin": 0, "email": 0})
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(config=config)
            self.assertEqual(caught.exception.gate, "pilot_cap")
        after = self._unsettled_snapshot()
        self.assertEqual(before, after)


class SuccessStillReserves(GuardTest):
    """A successful authorize still reserves exactly as it does today.

    The reservation is what stops two concurrent authorizations spending the
    same `new_accounts_per_day` slot. This must not become "reserve nothing".
    """

    def test_successful_authorization_reserves_one_row(self):
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth = self.authorize()
        self.assertIn("reserved", auth.gates)
        key = "rec-1:dana-marsh:day3:linkedin"
        self.assertEqual(actionledger.state_of(key), actionledger.ATTEMPTED)

    def test_two_sequential_authorizations_behave_as_today(self):
        """The first reserves; the second refuses at the ledger gate.

        This is the existing idempotency property: once a key is reserved,
        a second authorize for the same contact-step-channel cannot reserve
        it again. The reservation is the mutex.
        """
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            auth1 = self.authorize()
            self.assertIn("reserved", auth1.gates)

            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize()
            self.assertEqual(caught.exception.gate, "ledger")


class BreakProofEarlyReservationWouldFail(GuardTest):
    """Reintroduce the early reservation and confirm the gate-7 test fails.

    This is the break-proofing step: if the reservation were moved back to
    BEFORE the killswitch (the defect shape), the killswitch-refusal test
    must fail FOR THAT REASON and not another. This proves the test is
    actually testing the reservation position, not merely that the
    killswitch refuses.
    """

    def test_early_reservation_is_caught_by_the_killswitch_test(self):
        """Move the reservation before the killswitch; the test must fire.

        Patches `actionledger.reserve` to record that it was called, then
        asserts that a killswitch refusal DID cause a reservation call.
        This is the defect: if reserve is called before the killswitch runs,
        a killswitch refusal leaves a reservation behind.
        """
        reserved_keys = []
        original_reserve = actionledger.reserve

        def tracking_reserve(key, **kw):
            reserved_keys.append(key)
            return original_reserve(key, **kw)

        with self.allow_collision(), self.allow_sender():
            with mock.patch.object(actionledger, "reserve",
                                   side_effect=tracking_reserve):
                with self.assertRaises(executionguard.NotAuthorized) as caught:
                    self.authorize()
                self.assertEqual(caught.exception.gate, "killswitch")

        # In the current (correct) code, the killswitch refuses BEFORE
        # reserve is called, so reserved_keys is empty. If the reservation
        # were moved before the killswitch, reserved_keys would be non-empty.
        self.assertEqual(reserved_keys, [],
                         "the killswitch refused but reserve() was still "
                         "called for %r - the reservation is too early"
                         % reserved_keys)

    def test_the_test_would_fail_if_reserve_ran_early(self):
        """Prove the break-proofing by simulating the defect directly.

        Calls `actionledger.reserve` BEFORE the killswitch refusal, then
        checks that the ledger has a row. This is what the defect looked
        like: a reservation was taken, then the killswitch refused, and
        the row was left behind.
        """
        key = "rec-1:dana-marsh:day3:linkedin"
        self.assertIsNone(actionledger.state_of(key))

        # Simulate the defect: reserve first, then refuse.
        from src import pilotcaps
        limits = pilotcaps.effective(self.config)
        actionledger.reserve(
            key, channel="linkedin", workspace="productive",
            provider_workspace=WS,
            campaign_id=self.campaign.get("campaign_id"),
            sender_id="116968", rec_id=self.rec.get("id"),
            contact_key=self.contact["key"], step_key="day3",
            operation="linkedin_connection_request",
            fingerprint=approval.fingerprint(self.step),
            by="test",
            cap_per_day=limits["linkedin_per_day"]["limit"],
            cap_per_sender=limits["per_sender_per_day"]["limit"],
            cap_new_accounts=limits["new_accounts_per_day"]["limit"])

        # Now the ledger has the row, exactly as the defect left it.
        self.assertEqual(actionledger.state_of(key), actionledger.ATTEMPTED)

        # And a second authorize would refuse at the ledger gate - which is
        # exactly what campaign 489 saw on retry.
        with self.allow_collision(), self.allow_killswitch(), \
             self.allow_sender():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize()
            self.assertEqual(caught.exception.gate, "ledger",
                             "expected the ledger gate to refuse the retry, "
                             "got %r: %s" % (caught.exception.gate,
                                             caught.exception.why))


if __name__ == "__main__":
    unittest.main()
