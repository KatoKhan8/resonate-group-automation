#!/usr/bin/env python3
"""The first provider write this build has BUILT, and it is a stop.

Built, not enabled. `providerwrites.SUPPORTED` is still empty and every
operation still refuses. The distinction is the point of this file.

WHY A STOP FIRST. The killswitch could refuse to START a campaign and could
not END one, so for a campaign already running in the vendor UI it was a
control this system claimed and did not have. `executionguard`'s
`stoppability` gate exists because of that gap and caps an unstoppable
channel at a single contact.

WHAT IS ESTABLISHED. `/campaign/Pause` exists: probed on 2026-09-10 with an
EMPTY body - no campaign identified, nothing to act on - it answered 400,
where `/campaign/PauseCampaign` answered 404. `/campaign/Resume` and
`/campaign/StartCampaign` exist by the same test and are deliberately not
implemented, because acquiring the ability to start exposure before the
ability to end it is worse than having neither.

WHAT IS NOT ESTABLISHED. That it WORKS. One live attempt returned a non-2xx;
the write layer classified it UNVERIFIED and refused to retry, the campaign
stayed PAUSED throughout, and further live attempts were refused by the
environment. So `SUPPORTED` stays empty - not out of caution, but because
`executionguard` lifts a promotion ceiling on `is_supported`, and a ceiling
must not move on the strength of a call that has never succeeded.

NOTHING HERE CALLS A PROVIDER. The transport and read-back are injected,
which is the whole reason `perform` takes them.
"""
import unittest
from unittest import mock

from src import actionledger as ledger, providerwrites
from src.providers import heyreach
from tests.base import QueueTest


class Spy:
    def __init__(self, status="PAUSED", fails=None):
        self.calls = []
        self.status = status
        self.fails = fails

    def transport(self, payload):
        self.calls.append(payload)
        if self.fails:
            raise self.fails
        return {"ok": True}

    def readback(self):
        return self.status


class ThePauseIsPerformable(QueueTest):

    def perform(self, spy, expected="PAUSED"):
        """Exercised with pause temporarily declared, which is exactly how it
        will run the day one live call has succeeded. The declaration is the
        only thing standing between this test and production."""
        with mock.patch.object(providerwrites, "SUPPORTED",
                               ("heyreach.pause",)):
            return self._perform(spy, expected)

    def _perform(self, spy, expected="PAUSED"):
        return providerwrites.perform(
            "heyreach.pause", tenant="productive", campaign="594061",
            payload={"campaignId": 594061}, transport=spy.transport,
            readback=spy.readback, expected=expected)

    def test_it_is_implemented_but_not_yet_declared_supported(self):
        """The distinction this whole file turns on.

        The transport, the allowlist and the read-back all exist. `SUPPORTED`
        stays empty until one live pause has actually succeeded, because
        `executionguard` lifts a promotion ceiling on `is_supported` and a
        ceiling must not move on the strength of an untried call.
        """
        self.assertFalse(providerwrites.is_supported("heyreach.pause"))
        self.assertTrue(callable(heyreach.pause_campaign))
        self.assertIn("/campaign/Pause", heyreach.WRITE_ROUTES)

    def test_it_performs_and_is_confirmed_by_the_read_back(self):
        spy = Spy(status="PAUSED")
        out = self.perform(spy)
        self.assertEqual(out["class"], providerwrites.ACCEPTED)
        self.assertEqual(spy.calls, [{"campaignId": 594061}])

    def test_a_read_back_that_disagrees_is_not_an_acceptance(self):
        """A 200 is not evidence. What the provider now HOLDS is."""
        spy = Spy(status="ACTIVE")
        with self.assertRaises(providerwrites.WriteUnverified):
            self.perform(spy)

    def test_it_needs_no_authorization_because_it_reaches_nobody(self):
        """Pause is not prospect-facing, and the label is what decides.

        If this ever starts requiring an Authorization it means somebody
        relabelled pausing as prospect-facing, which would be wrong, or
        mislabelled something else as pause, which would be worse.
        """
        _channel, facing, _why = providerwrites.describe("heyreach.pause")
        self.assertFalse(facing)
        self.assertEqual(self.perform(Spy())["key"], None)

    def test_it_is_idempotent_against_an_already_paused_campaign(self):
        """The canary is already PAUSED. Pausing it again must be a no-op that
        still reads back as accepted, or recovery could never re-assert a stop.
        """
        for _ in range(3):
            self.assertEqual(self.perform(Spy())["class"],
                             providerwrites.ACCEPTED)

    def test_a_transport_failure_is_unverified_rather_than_failed(self):
        """The provider may have paused it anyway. Never a retry loop."""
        spy = Spy(fails=RuntimeError("connection reset"))
        with self.assertRaises(providerwrites.WriteUnverified):
            self.perform(spy)

    def test_no_reservation_is_consumed(self):
        """A stop must never be blocked by the ledger. If pausing needed a
        reservation, the one moment you most need to stop is the moment you
        cannot."""
        self.perform(Spy())
        self.assertEqual(ledger.load(), [])


class TheStartIsStillRefused(unittest.TestCase):
    """Both routes exist on the vendor. Only one is enabled, and it is not
    the one that creates exposure."""

    def test_activate_is_not_supported(self):
        self.assertFalse(providerwrites.is_supported("heyreach.activate"))

    def test_activate_refuses_before_touching_a_transport(self):
        spy = Spy()
        with self.assertRaises(providerwrites.WriteUnsupported):
            providerwrites.perform("heyreach.activate", transport=spy.transport,
                                   readback=spy.readback)
        self.assertEqual(spy.calls, [])

    def test_the_module_refuses_to_write_to_any_other_route(self):
        for route in ("/campaign/Resume", "/campaign/StartCampaign",
                      "/campaign/AddLeadsToCampaignV2", "/campaign/Create"):
            with self.subTest(route=route):
                with self.assertRaises(Exception):
                    heyreach._write(route, {"campaignId": 1})

    def test_the_write_allowlist_is_exactly_the_stop(self):
        self.assertEqual(set(heyreach.WRITE_ROUTES), {"/campaign/Pause"})


class TheCapLiftsWhenTheStopIsProven(unittest.TestCase):
    """Why any of this was worth building.

    `executionguard` caps a channel at one contact while its pause operation
    is unsupported. That cap reads `providerwrites.is_supported`, so declaring
    the route is what lifts it - the gate was written to unlock itself rather
    than to be edited. Today neither channel has a proven stop, so both stay
    capped, which is the correct reading of what this build can actually do.
    """

    def test_neither_channel_has_a_proven_stop_yet(self):
        """So the cap still applies to both, which is correct today."""
        from src import executionguard
        for channel in ("linkedin", "email"):
            self.assertFalse(providerwrites.is_supported(
                executionguard.PAUSE_OPERATION[channel]), channel)

    def test_declaring_the_pause_is_what_lifts_the_linkedin_cap(self):
        """The gate was written to unlock itself rather than be edited.

        This is the whole payoff: the day a live pause succeeds, one line in
        `SUPPORTED` lifts the one-contact cap, with no change to the guard.
        """
        from src import executionguard
        with mock.patch.object(providerwrites, "SUPPORTED",
                               ("heyreach.pause",)):
            self.assertTrue(providerwrites.is_supported(
                executionguard.PAUSE_OPERATION["linkedin"]))


if __name__ == "__main__":
    unittest.main()
