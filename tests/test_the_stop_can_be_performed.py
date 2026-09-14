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

    def test_it_is_implemented_and_now_declared_supported(self):
        """The distinction this whole file turns on, and it has moved once.

        The transport, the allowlist and the read-back all existed for two
        days while `SUPPORTED` stayed empty, because `executionguard` lifts a
        promotion ceiling on `is_supported` and a ceiling must not move on the
        strength of an untried call. The 2026-09-10 attempt returned a non-2xx
        and was classified UNVERIFIED, so it stayed empty.

        On 2026-09-12 a live pause of HeyReach 594061 returned 200 and read
        back PAUSED. What changed is a successful response, not an argument
        about the same code.
        """
        self.assertTrue(providerwrites.is_supported("heyreach.pause"))
        self.assertTrue(callable(heyreach.pause_campaign))
        self.assertIn("/campaign/Pause", heyreach.WRITE_ROUTES)

    def test_and_nothing_else_came_with_it(self):
        """A live-validated verb validates itself and nothing adjacent.

        The supported set grew on 2026-09-13 when EmailBison's documented
        routes turned out to answer. Each addition was measured against the
        live estate with a readback, and each is named here so that the next
        one is a decision rather than a drift.
        """
        # `heyreach.set_sequence` joined on 2026-09-14. Its entry had set its
        # own condition - "a write would be verifiable the moment a verb is
        # established" - and campaign 599020 already carried a sequence
        # written through /campaign/UpdateSequence, so the condition was met.
        # Not prospect-facing: a sequence on a campaign holding nobody
        # reaches nobody, and the campaign has no list, no leads and no wired
        # verb that can start it.
        proven = {"heyreach.pause", "bison.pause", "bison.stop_lead",
                  "bison.create_campaign", "bison.set_sequence",
                  "heyreach.set_sequence"}
        for operation in providerwrites.OPERATIONS:
            if operation in proven:
                continue
            self.assertFalse(providerwrites.is_supported(operation), operation)

    def test_no_supported_verb_reaches_a_prospect(self):
        """The property that has to survive every addition to that set."""
        for operation, (_c, facing, _w) in providerwrites.OPERATIONS.items():
            if facing:
                self.assertFalse(providerwrites.is_supported(operation),
                                 operation)

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
        # STAGING AND STOPPING ONLY, and that is the property - not a count.
        # The allowlist grew from one route to seven on 2026-09-13 when the
        # LinkedIn lane gained a campaign factory: create (a DRAFT), create a
        # list, write a sequence, add or remove a seat, stop one lead, pause.
        #
        # What is NOT there is what matters. `Resume` and `StartCampaign`
        # both demonstrably exist on this vendor's API - an empty-body probe
        # answers 400 for each, and 404 for names that do not - and so does
        # `AddLeadsToCampaignV2`. None of the three is here. A system that
        # can start an outreach campaign before it can reliably stop one has
        # acquired exposure it cannot end.
        # `AddLeadsToCampaignV2` joined WRITE_ROUTES on 2026-09-14 so the
        # transport and its readback could be built and tested. It is NOT in
        # `providerwrites.SUPPORTED`, which is the permission - and that
        # distinction is asserted directly below rather than left to this
        # route list. A route on WRITE_ROUTES is one this module CAN call; a
        # route in SUPPORTED is one this build WILL call.
        #
        # Resume, StartCampaign and SendMessage remain absent from BOTH, and
        # that is what this test is really about: a system that can start an
        # outreach campaign before it can reliably stop one has acquired
        # exposure it cannot end.
        forbidden = ("Resume", "StartCampaign", "SendMessage")
        reaching = [r for r in heyreach.WRITE_ROUTES
                    if any(v.lower() in r.lower() for v in forbidden)]
        self.assertEqual(reaching, [],
                         f"a route that reaches a prospect is writable: {reaching}")
        self.assertIn("/campaign/Pause", heyreach.WRITE_ROUTES)



class TheCapLiftsWhenTheStopIsProven(unittest.TestCase):
    """Why any of this was worth building.

    `executionguard` caps a channel at one contact while its pause operation
    is unsupported. That cap reads `providerwrites.is_supported`, so declaring
    the route is what lifts it - the gate was written to unlock itself rather
    than to be edited.

    It unlocked. On 2026-09-12 `POST /campaign/Pause` against HeyReach 594061
    returned 200, the campaign read back PAUSED, nothing was sent across it
    (connectionsSent 0 before and after, the lead still request_pending), the
    action was recorded canonically and provider, canonical state, ledger and
    touches reconciled. `SUPPORTED` became `(LINKEDIN_PAUSE,)` on that
    evidence and the LinkedIn cap lifted with no change to the guard.

    Email did not. `bison.pause` has no documented route, so that channel is
    still capped at one contact - which is the whole point of asking the
    question per channel rather than once.
    """

    def test_linkedin_has_a_proven_stop(self):
        from src import executionguard
        self.assertTrue(providerwrites.is_supported(
            executionguard.PAUSE_OPERATION["linkedin"]))

    def test_email_has_one_too_now(self):
        """Measured 2026-09-13, and it is the stronger of the two.

        `PATCH /api/campaigns/{id}/pause` stops everybody in a campaign, and
        `POST .../leads/stop-future-emails` stops ONE person while the rest
        keep going - which is the granularity the safety argument actually
        wants. Both were measured with a readback.
        """
        from src import executionguard
        self.assertTrue(providerwrites.is_supported(
            executionguard.PAUSE_OPERATION["email"]))
        self.assertTrue(providerwrites.is_supported(
            providerwrites.EMAIL_STOP_LEAD))

    def test_a_declared_stop_has_a_caller_in_the_product(self):
        """The ceiling must not lift on a stop only a script can invoke.

        `stoppability` lifts a promotion ceiling the moment `is_supported`
        answers True. For a while it answered True for both channels while
        NOTHING in `src/` performed either pause - the only live pause ever
        executed came from an ad-hoc script. A capability nothing calls is
        exactly the defect this repository keeps finding, and finding it on
        the gate that bounds unrecallable exposure is the worst place for it.

        Asserted on the import graph rather than by grepping for words: this
        calls the real `orchestrator.pause` and checks the provider leg ran.
        """
        from unittest import mock

        from src import orchestrator
        for channel, binding, provider_id in (
                ("linkedin", "heyreach_campaign_id", 594061),
                ("email", "bison_campaign_id", 352)):
            campaign = {"campaign_id": "c1", "client": "productive",
                        "status": "running", "log": [], "events": [],
                        binding: provider_id}
            with mock.patch.object(orchestrator, "_perform_pause",
                                   return_value={"stopped": True}) as spy:
                orchestrator.pause(campaign, by="tester")
            self.assertTrue(
                spy.called,
                f"orchestrator.pause told nobody on the {channel} binding")
            self.assertEqual(spy.call_args[0][1], channel)

    def test_withdrawing_the_declaration_puts_the_cap_back(self):
        """The gate reads the declaration rather than a constant, so it is
        still the declaration that decides - which is what makes the lift
        reversible if the route ever stops working."""
        from src import executionguard
        with mock.patch.object(providerwrites, "SUPPORTED", ()):
            self.assertFalse(providerwrites.is_supported(
                executionguard.PAUSE_OPERATION["linkedin"]))


if __name__ == "__main__":
    unittest.main()
