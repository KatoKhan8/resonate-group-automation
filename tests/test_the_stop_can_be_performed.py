#!/usr/bin/env python3
"""The first provider write this build has BUILT, and it is a stop.

Built before it was enabled, and the ORDER is the point of this file.
`providerwrites.SUPPORTED` was empty when this was written and every
operation refused; it holds fourteen verbs now, including two that make a
campaign send. That is not a retraction of anything below - it is the
sequence this file argued for, arriving. The stop was built first, validated
first and enabled first, and the starts that came later are each scoped to
one named campaign while neither pause carries a condition at all. A build
that had acquired the ability to start before the ability to end would have
failed the tests here rather than passed them.

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
        # `heyreach.add_lead` joined on 2026-09-15, TASK-137, and it is the
        # first prospect-facing verb ever enabled. It did not arrive by
        # drift: it is enabled CONDITIONALLY, and the condition - the
        # destination campaign must be proven by a provider read, taken at
        # the moment of the write, to be unable to send - is the permission.
        # The test below asserts that property rather than this membership.
        # `heyreach.start_empty_for_staging` joined on 2026-09-15. Not
        # prospect-facing: it starts a campaign the provider says holds ZERO
        # leads, so nothing is sent, and its condition refuses a campaign
        # holding anyone. The provider forced it - DRAFT refuses leads and
        # cannot be paused, so start-then-pause is the only route to a
        # stageable campaign.
        #
        # SIX MORE JOINED ON 2026-09-16 by written operator authorization -
        # see OPERATOR-AUTHORIZATION-2026-09-16.md. This list is NOT a
        # loosening of the property; the property was never "the set is
        # small", it is "every member of the set is named here by somebody
        # who read why". Four of the six are campaign-BUILDING and reach
        # nobody:
        #
        #   heyreach.create_campaign  creates a DRAFT, and a DRAFT sends
        #                             nothing. Conditional on the LIST that
        #                             will be bound to it - ours, unbound,
        #                             holding only approved leads, read live
        #   heyreach.create_list      makes an EMPTY list attached to no
        #                             campaign. Nothing to read and nothing
        #                             to prove, so deliberately unconditional
        #   heyreach.add_lead_to_list adds to a list the provider confirms,
        #                             at the moment of the write, is attached
        #                             to no campaign
        #   bison.assign_sender       attaching a seat is what makes sending
        #                             possible at all, so it shares
        #                             EMAIL_ACTIVATE's condition and refuses
        #                             every canonical row but the named one
        #
        # The other two are the ACTIVATE verbs, and they are the ones that
        # make a campaign send. `heyreach.activate` is no longer sealed and
        # this comment used to say it was. What replaced the seal is
        # NARROWER than membership and is asserted in
        # `test_no_supported_verb_reaches_a_prospect_unconditionally`: each
        # carries a CONDITIONAL naming ONE campaign per channel, and every
        # other id on either channel is refused.
        proven = {"heyreach.pause", "bison.pause", "bison.stop_lead",
                  "bison.create_campaign", "bison.set_sequence",
                  "heyreach.set_sequence", "heyreach.add_lead",
                  "heyreach.start_empty_for_staging",
                  "heyreach.add_lead_to_list", "heyreach.create_campaign",
                  "heyreach.create_list", "heyreach.activate",
                  "bison.assign_sender", "bison.activate"}
        for operation in providerwrites.OPERATIONS:
            if operation in proven:
                continue
            self.assertFalse(providerwrites.is_supported(operation), operation)

        # WHAT DID NOT COME WITH IT, named rather than left to the loop
        # above. The loop is a statement about everything; these four are the
        # ones whose absence the grant was explicitly not a grant of, and a
        # loop that silently had nothing left to check would still pass.
        #
        # `heyreach.assign_sender` and `heyreach.set_limits` are a seat this
        # build could attach and a cap it could raise - which is how a
        # validated one-person canary silently becomes a bigger campaign
        # without any verb in the set above being called again.
        # `bison.add_lead` reaches a person on the channel that is now
        # activatable, and nobody granted it.
        for sealed in ("heyreach.assign_sender", "heyreach.set_limits",
                       "bison.add_lead", "bison.set_limits"):
            self.assertFalse(providerwrites.is_supported(sealed), sealed)

    def test_no_supported_verb_reaches_a_prospect_unconditionally(self):
        """NARROWED, TASK-137. The property that has to survive every
        addition to that set, restated for the first addition that could
        reach a person.

        It used to read: nothing prospect-facing is supported. That was a
        true statement about a system that had never written to a prospect,
        and it could not distinguish staging a lead into a campaign that
        cannot send from sending somebody a message. The property that
        actually has to hold is that no prospect-facing verb is enabled
        WITHOUT a condition deciding, per write, whether it reaches anyone.

        RE-POINTED 2026-09-16. The open list grew from one to three when an
        operator granted both ACTIVATE verbs. The property is unchanged and
        it was never the COUNT - it is that nothing reaches a person on tuple
        membership alone. `add_lead` is conditional on the destination's
        STATE (a campaign the provider says cannot send); the two ACTIVATE
        verbs cannot be, because no campaign state makes an activation reach
        nobody, so they are scoped BY NAME to one campaign per channel
        instead. That scope is asserted below rather than taken on trust,
        because a condition that admits everything is worse than none.
        """
        for operation, (_c, facing, _w) in providerwrites.OPERATIONS.items():
            if not facing:
                continue
            if providerwrites.is_supported(operation):
                self.assertTrue(
                    providerwrites.is_conditional(operation),
                    f"{operation} reaches a prospect and is enabled with no "
                    f"condition on when it may run")
            else:
                self.assertFalse(providerwrites.is_supported(operation),
                                 operation)
        # The ones that are open, named, so a fourth one is a decision.
        facing_and_open = [op for op in providerwrites.PROSPECT_FACING
                           if providerwrites.is_supported(op)]
        self.assertEqual(facing_and_open, [providerwrites.LINKEDIN_ADD_LEAD,
                                           providerwrites.LINKEDIN_ACTIVATE,
                                           providerwrites.EMAIL_ACTIVATE])
        # `bison.add_lead` is the fourth prospect-facing verb and it is
        # sealed outright, so the list above is demonstrably not just
        # "everything that reaches a person".
        self.assertFalse(
            providerwrites.is_supported(providerwrites.EMAIL_ADD_LEAD),
            "bison.add_lead reaches a person and nobody granted it")

        # EXACTLY ONE CAMPAIGN PER CHANNEL. Membership alone would be a
        # channel-wide licence: on LinkedIn over the 83 campaigns in that
        # account, 12 of them the client's own and IN_PROGRESS; on email over
        # 481, which holds 23 people already written to under a sequence
        # nobody approved here.
        require = providerwrites.require_conditional_permission
        self.assertTrue(require(providerwrites.LINKEDIN_ACTIVATE,
                                providerwrites._AUTHORIZED_LINKEDIN_CANARY,
                                None))
        # 594061 is the campaign this file's pause was validated against;
        # 604869 and 605487 are DEAD ENDS rather than merely un-granted, and
        # are asserted refused rather than dropped. "605733" and "60573" are
        # near misses of the granted id, and ""/None prove it fails closed.
        for other in ("594061", "599020", "604869", "605487",
                      "605733", "60573", "", None):
            with self.assertRaises(providerwrites.WriteRefused):
                require(providerwrites.LINKEDIN_ACTIVATE, other, None)
        # Email is checked on the CANONICAL row first, because the provider
        # slot is unpinned and the row supplies the expected provider id. A
        # write naming any other row is refused before a provider id is even
        # resolved, so 481 and 485 cannot be reached through it.
        for other in ("481", "485", "487", "", None):
            with self.assertRaises(providerwrites.WriteRefused):
                require(providerwrites.EMAIL_ACTIVATE, other,
                        "productive-email-control-v2")

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
    """Both routes exist on the vendor. The start is enabled for ONE named
    campaign and refused for every other, and it is still refused outright to
    any caller who has not passed the gate ladder.

    RE-POINTED 2026-09-16. This class asserted that the start did not exist as
    a permission at all, which was right until an operator granted
    `heyreach.activate` scoped to campaign 605732. The class name is still
    accurate for everything this file is about: the start is refused for the
    83 other campaigns in that account, and refused even for 605732 without
    an `executionguard.Authorization`.
    """

    def test_activate_is_supported_only_for_the_named_canary(self):
        """RENAMED from `test_activate_is_not_supported`.

        The old name asserted a blanket seal that an operator deliberately
        narrowed, so leaving it would have pinned the opposite of the truth.
        The property that replaced it is not weaker in any way that matters:
        the verb is enabled, it carries a condition, and the condition admits
        exactly ONE provider campaign and refuses every other id. Widening
        that is a new operator decision, not a refactor.
        """
        self.assertTrue(providerwrites.is_supported("heyreach.activate"))
        self.assertTrue(
            providerwrites.is_conditional("heyreach.activate"),
            "heyreach.activate is supported and unconditional, which is a "
            "licence to start any of the 83 campaigns in that account")
        require = providerwrites.require_conditional_permission
        self.assertTrue(require("heyreach.activate",
                                providerwrites._AUTHORIZED_LINKEDIN_CANARY,
                                None))
        # Every other id, including the two DEAD ENDS (604869's bound list
        # holds a contact whose account `collision.account_policy` holds;
        # 605487's list was staged on the account gate alone) and the
        # campaigns this file's pause was validated against. The near misses
        # and ""/None prove the match is exact and fails closed.
        for other in ("594061", "599020", "604869", "605487",
                      "605733", "60573", "605732x", "", None):
            with self.assertRaises(providerwrites.WriteRefused):
                require("heyreach.activate", other, None)

    def test_activate_refuses_before_touching_a_transport(self):
        """The name is unchanged because the property is: nothing reaches the
        vendor. What changed is WHICH refusal fires.

        It was `WriteUnsupported` - the OFF switch - which was right until the
        operator authorized 605732. Now the refusal comes from the
        requirement that a prospect-facing verb carry a real
        `executionguard.Authorization`, which only `authorize()` mints and
        only after every per-contact gate passes. That is a stronger seal
        than absence in one respect: absence stopped everyone, this stops
        everyone who has not passed the gates, and it fires for the GRANTED
        campaign too. Precedent:
        `test_heyreach_start_is_sealed.ActivateIsSealed.
        test_perform_refuses_activate_without_an_authorization`.
        """
        # The AUTHORIZED campaign, deliberately. If the grant were the whole
        # permission this call would proceed, and the transport would be
        # touched.
        spy = Spy()
        with self.assertRaises(providerwrites.WriteRefused) as ctx:
            providerwrites.perform(
                "heyreach.activate",
                provider_campaign_id=(
                    providerwrites._AUTHORIZED_LINKEDIN_CANARY),
                transport=spy.transport, readback=spy.readback)
        self.assertIn("Authorization", str(ctx.exception))
        self.assertEqual(spy.calls, [])

        # And an UNAUTHORIZED campaign is refused on the same first gate,
        # never reaching the condition that would refuse it second. Two
        # independent refusals stand between this call and the vendor.
        spy = Spy()
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform("heyreach.activate",
                                   provider_campaign_id="599020",
                                   transport=spy.transport,
                                   readback=spy.readback)
        self.assertEqual(spy.calls, [])
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.require_conditional_permission(
                "heyreach.activate", "599020", None)

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
        # NARROWED 2026-09-15. `/campaign/Resume` IS on WRITE_ROUTES now, and
        # the property this test protects is unchanged: a system that can
        # START AN OUTREACH CAMPAIGN before it can reliably stop one has
        # acquired exposure it cannot end.
        #
        # Both halves of that sentence moved. The stop EXISTS - Pause is
        # live-validated, SUPPORTED, and read back as PAUSED against 594061.
        # And starting a campaign that holds ZERO LEADS starts no outreach,
        # because there is nobody for the sequence to act on.
        #
        # The provider left no alternative: AddLeadsToCampaignV2 answers 400
        # on a DRAFT campaign and Pause answers 400 on an inactive one, so
        # DRAFT -> PAUSED is not a transition this vendor has. Start-then-pause
        # is the only route to a stageable campaign.
        #
        # NARROWED AGAIN 2026-09-16. Starting a campaign that HOLDS PEOPLE is
        # `heyreach.activate`, and this said it was absent from SUPPORTED and
        # carried no condition. An operator granted it, SCOPED BY NAME to
        # campaign 605732, so the absence is gone and what is asserted below
        # is the narrowness that replaced it: enabled, conditional, and
        # refusing every other id on the channel.
        #
        # The route list is unaffected by that grant and that is the point of
        # keeping the two assertions in one test. `StartCampaign` was already
        # on WRITE_ROUTES while the permission did not exist, and the two
        # verbs share that route and are told apart by a lead count the
        # provider supplies - so a route being writable never was the
        # permission, and a permission arriving does not widen the routes.
        # `/campaign/StartCampaign` is present too, and Resume was not the
        # verb for a DRAFT campaign after all - it answers 400 "not paused,
        # finished or failed". Resume is ACTIVATION (a paused campaign holds
        # leads); StartCampaign is what moves a never-run campaign, and it is
        # used only against one the provider says holds ZERO leads.
        #
        # What may never be writable is a route that SENDS A MESSAGE
        # directly, which no lead count can make harmless.
        forbidden = ("SendMessage",)
        reaching = [r for r in heyreach.WRITE_ROUTES
                    if any(v.lower() in r.lower() for v in forbidden)]
        self.assertEqual(reaching, [],
                         f"a route that reaches a prospect is writable: {reaching}")
        self.assertIn("/campaign/Resume", heyreach.WRITE_ROUTES)
        self.assertIn("/campaign/StartCampaign", heyreach.WRITE_ROUTES)
        self.assertIn("heyreach.activate", providerwrites.SUPPORTED)
        self.assertIn("heyreach.activate", providerwrites.CONDITIONAL)
        # And the condition is the permission: one campaign, every other
        # id refused.
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.require_conditional_permission(
                "heyreach.activate", "594061", None)
        self.assertIn("heyreach.start_empty_for_staging",
                      providerwrites.CONDITIONAL)
        self.assertIn("/campaign/Pause", heyreach.WRITE_ROUTES)
        # THE STOP IS STILL BROADER THAN THE START, which is the asymmetry
        # this whole file was written to establish. `heyreach.pause` is
        # supported and carries NO condition, so it may stop any campaign;
        # `heyreach.activate` may start exactly one.
        self.assertTrue(providerwrites.is_supported("heyreach.pause"))
        self.assertFalse(providerwrites.is_conditional("heyreach.pause"))



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
