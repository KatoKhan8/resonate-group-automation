"""The write layer exists, is complete, and can do nothing. On purpose.

Sending in this repository is BLOCKING BY CONSTRUCTION rather than by a flag:
`push.run(live=True)` raises, `tagsync.send` refuses unconditionally, and
`heyreach._read` rejects any route outside its read allowlist. That is the one
guarantee here that has never been wrong, so adding a write capability is not a
feature - it is the removal of the only property nothing has ever violated.

So the machine ships with nothing to drive. Every brake is built and tested
against fixtures, and `SUPPORTED` is empty. The tests below are the argument
that enabling a route later will be a visible, reviewed diff rather than a quiet
edit: the first one FAILS the moment somebody adds an entry, which is exactly
the alarm that should sound.

The transport is always a spy. No test here needs a provider, and none may have
one.
"""
import contextlib
import unittest
from unittest import mock

from src import approval, actionledger, executionguard, providerwrites, store
from src import campaigns as campaigns_state

from tests.base import QueueTest
from src.providers import heyreach

# TASK-137: `LINKEDIN_ADD_LEAD` is now conditionally supported, so `perform`
# re-reads the destination campaign and refuses unless it is proven unable to
# send. Several classes below use that operation as their vehicle for a
# different question - response classification, token shape, idempotency - so
# they name a DRAFT destination and fake the one provider read the condition
# makes. THE CONDITION ITSELF IS NOT STUBBED: the real predicate runs against
# a real status string, and every one of these tests failed loudly when the
# gate landed, which is how it is known the gate is on this path.
DRAFT_DESTINATION = 599020
CANON = "productive-linkedin-production-v1"
# PAUSED, not DRAFT: the provider answers 400 "You cannot add new leads to a
# draft campaign", so DRAFT is the one state it refuses. See CONDITIONAL in
# providerwrites and docs/DRAFT-CANNOT-TAKE-LEADS-2026-09-15.md.
DRAFT_ROW = {"id": DRAFT_DESTINATION, "status": "PAUSED", "name": "test",
             "organizationUnitId": "174892"}
CANON_ROW = {"campaign_id": CANON, "client": "productive",
             "heyreach_campaign_id": str(DRAFT_DESTINATION),
             "provider_status_expected": "PAUSED",
             "provider_note": "{connection_note}",
             "provider_actions": ["CHECK_IS_CONNECTION", "MESSAGE"]}




# The approved words these tests transport. `perform` compares the payload it
# is handed against the authorization's fingerprint, so the two must agree -
# otherwise the words guard fires first and the behaviour under test never
# runs.
STEP = {"channel": "linkedin", "note": "a note somebody approved"}
APPROVED = {"note": STEP["note"]}

class BoundDestination:
    """Mixin: write `CANON_ROW` to the test's ledger so the write has a NAME.

    WHY THIS EXISTS. `CANON_ROW` was only ever handed back by a
    `mock.patch.object(campaigns_state, "require", ...)` inside `enabled()`,
    and `providerwrites.require_resonate_os_campaign` does not call `require`:
    it calls `campaigns.load()`, deliberately, because the LEDGER is the only
    positive record that a provider campaign is ours and a mock is a claim the
    caller made about itself. So the write named a destination nothing
    resolved, the destination classified `unknown`, and the ownership guard
    refused by default. Correctly - that is the hole an internal Resonate
    campaign would be written through.

    The row is therefore WRITTEN, not mocked. The `require` stub in
    `enabled()` is left exactly where it was: it is what the condition on
    `LINKEDIN_ADD_LEAD` reads, it is a different question, and removing it
    here would change what these tests are about.
    """

    def bind_canonical_destination(self):
        campaigns_state.save([dict(CANON_ROW)])
        on_disk = campaigns_state.get(CANON)
        self.assertIsNotNone(on_disk, "the ledger fixture did not persist")
        self.assertEqual(on_disk.get("heyreach_campaign_id"),
                         str(DRAFT_DESTINATION),
                         "the fixture row does not bind the provider campaign")
        self.assertEqual(
            providerwrites.classify_campaign("linkedin", DRAFT_DESTINATION),
            providerwrites.RESONATE_OS,
            "the bound row does not classify as a Resonate OS campaign, so "
            "these tests would be exercising an ownership refusal instead of "
            "the response handling they are about")


class Spy:
    """A transport that records and never reaches a network."""

    def __init__(self, response=None, raises=None):
        self.calls = []
        self.response = response if response is not None else {"ok": True}
        self.raises = raises

    def __call__(self, payload):
        self.calls.append(payload)
        if self.raises:
            raise self.raises
        return self.response


class TheLayerIsSealed(unittest.TestCase):
    def test_no_prospect_facing_operation_is_supported(self):
        """THE SAFETY PROPERTY, and the one that must never weaken.

        This used to assert `SUPPORTED == ()`, which was the right test while
        nothing at all was enabled. It is the wrong test now that
        `heyreach.pause` is: emptiness was only ever a proxy for "nothing can
        reach a prospect", and asserting the proxy would make enabling a STOP
        look identical to enabling a SEND.

        So the assertion is now the thing itself. A failure here means
        something that can reach a real person has been enabled, which is a
        different and much larger decision than the one that enabled pausing.

        RE-POINTED 2026-09-16. Both ACTIVATE verbs were granted by written
        operator authorization, each SCOPED BY NAME to a single campaign, so
        the list is three rather than one. The property is unchanged and it
        was never the length of the list: NOTHING reaches a prospect on tuple
        membership alone. The list is still pinned by name, so a fourth cannot
        arrive quietly, and each entry must carry a condition that decides,
        per write, whether this particular write reaches anyone.
        """
        enabled = [op for op in providerwrites.PROSPECT_FACING
                   if providerwrites.is_supported(op)]
        self.assertEqual(
            enabled, [providerwrites.LINKEDIN_ADD_LEAD,
                      providerwrites.LINKEDIN_ACTIVATE,
                      providerwrites.EMAIL_ACTIVATE],
            "a PROSPECT-FACING provider write has been enabled")
        # AND NONE OF THEM IS ENABLED OUTRIGHT. That distinction is the whole
        # of what changed on 2026-09-15 and again on 2026-09-16: `add_lead`
        # may run only against a campaign a provider read proves cannot send,
        # and each ACTIVATE verb may run only against the one campaign its
        # grant names - because no campaign state makes an activation reach
        # nobody, so it is scoped by identity instead.
        for operation in enabled:
            self.assertTrue(
                providerwrites.is_conditional(operation),
                f"{operation} reaches a prospect and nothing decides, per "
                f"write, whether this particular one does")
        # `bison.add_lead` was never granted and is what keeps the list above
        # a real statement rather than an enumeration of everything.
        self.assertNotIn(providerwrites.EMAIL_ADD_LEAD,
                         providerwrites.SUPPORTED)
        # One campaign per channel, and every other id refused. 604869 and
        # 605487 are DEAD ENDS the grant moved away from - a held account on
        # one, a contact gate 4 refused on the other - so they are asserted
        # refused rather than dropped for being un-granted.
        require = providerwrites.require_conditional_permission
        self.assertTrue(require(providerwrites.LINKEDIN_ACTIVATE,
                                providerwrites._AUTHORIZED_LINKEDIN_CANARY,
                                None))
        for other in ("599020", "604869", "605487", "", None):
            with self.subTest(campaign=other):
                with self.assertRaises(providerwrites.WriteRefused):
                    require(providerwrites.LINKEDIN_ACTIVATE, other, None)
        for other in ("481", "485", None):
            with self.subTest(campaign=other):
                with self.assertRaises(providerwrites.WriteRefused):
                    require(providerwrites.EMAIL_ACTIVATE, other,
                            "productive-email-control-v2")

    def test_nothing_is_supported_until_it_has_actually_worked_once(self):
        """Implemented is not the same as established, and the gap matters.

        `/campaign/Pause` was implemented and tested for two days and NOT
        listed, because `executionguard`'s stoppability gate reads
        `is_supported` and LIFTS a promotion ceiling when the answer is yes -
        so listing an unproven route would raise a safety limit on the
        strength of a call that had never succeeded. The condition written
        here was "one successful pause, read back from provider truth".

        It happened on 2026-09-12: POST /campaign/Pause on HeyReach 594061
        returned 200, the campaign read back PAUSED, connectionsSent stayed 0,
        and provider, canonical state, ledger and touches reconciled. Exactly
        one verb moved.
        """
        from src import providerwrites as pw
        self.assertEqual(
            providerwrites.SUPPORTED,
            (pw.LINKEDIN_PAUSE, pw.EMAIL_PAUSE, pw.EMAIL_STOP_LEAD,
             # 2026-09-23, OPERATOR DECISION. The condition this docstring
             # sets is one successful call read back from provider truth, and
             # for a STOP that ordering is impossible: the verb has to be
             # enabled before any stop can be attempted, so there is no way
             # to prove it works first. What licenses it instead is the
             # direction of the blast radius - it can only ever reduce what
             # somebody receives - plus a readback in
             # `heyreach.stop_lead_in_campaign` that RAISES when the provider
             # still reports the lead running, so an unconfirmed stop is
             # never reported as a stop.
             #
             # Asked for because the cross-channel stop was measured live
             # that evening: LinkedIn->email passed at 7.7 minutes, and
             # email->LinkedIn could not run at all while this was sealed.
             pw.LINKEDIN_STOP_LEAD,
             pw.EMAIL_CREATE_CAMPAIGN, pw.EMAIL_SET_SEQUENCE,
             # 2026-09-14. The same condition this docstring sets - one
             # successful call, read back from provider truth - was already
             # met: campaign 599020 carried a sequence written through
             # /campaign/UpdateSequence before it was listed. Not
             # prospect-facing, and the loop below is what actually guards
             # this file.
             pw.LINKEDIN_SET_SEQUENCE,
             # 2026-09-15, TASK-137. The docstring's condition is MET for
             # the readback and NOT for the response body, and that is the
             # honest position: no successful AddLeadsToCampaignV2 reply has
             # ever been read, and none is what settles the verdict.
             # /campaign/GetLeadsFromCampaign is live-validated against
             # campaign 565765 - 1000 leads paged with per-lead status and
             # errorCode - and the readback is what classifies the write.
             # Prospect-facing, so the loop below no longer merely forbids:
             # it requires a CONDITION.
             pw.LINKEDIN_ADD_LEAD,
             # Added 2026-09-15. NOT prospect-facing and NOT activation: it
             # starts a campaign the provider says holds ZERO leads, so it
             # sends nothing, and its condition refuses any campaign holding
             # anyone. The provider leaves no other route - DRAFT refuses
             # leads and cannot be paused - so start-then-pause is the only
             # way to a stageable campaign.
             pw.LINKEDIN_START_EMPTY_FOR_STAGING,
             # 2026-09-16, by written operator authorization. Six verbs, and
             # the docstring's condition - "one successful call, read back
             # from provider truth" - is NOT what admitted them; an operator
             # decision is, which is the honest position and is recorded in
             # `OPERATOR-AUTHORIZATION-2026-09-16.md`. The loop below is what
             # guards this file, and it now has more to guard.
             #
             # Adds a lead to a LIST rather than a campaign. A list attached
             # to no campaign reaches nobody, and the condition reads the list
             # FROM THE PROVIDER at the moment of the write to prove it.
             pw.LINKEDIN_ADD_LEAD_TO_LIST,
             # SCOPED TO ONE CANONICAL CAMPAIGN, both of them. Attaching a
             # sender is what makes sending possible and activation is what
             # makes it happen, so they share a condition that refuses every
             # row but the one the grant names - and, because the provider
             # slot is unpinned, refuses a named row that is not bound.
             pw.EMAIL_ASSIGN_SENDER,
             pw.EMAIL_ACTIVATE,
             # NOT prospect-facing: the provider creates in DRAFT and a DRAFT
             # sends nothing. Conditional on the LIST bound at creation -
             # ours, unbound, holding only approved leads, all read live.
             pw.LINKEDIN_CREATE_CAMPAIGN,
             # SCOPED TO ONE CAMPAIGN, and PROSPECT-FACING. Membership here
             # alone would be a licence over the 83 campaigns in that
             # account, 12 of them the client's own and IN_PROGRESS.
             pw.LINKEDIN_ACTIVATE,
             # NOT prospect-facing and NOT conditional: an EMPTY list bound
             # to no campaign has no destination to read, and a condition
             # that checks nothing reads as a gate without being one. What
             # bounds it is downstream, where both verbs are conditional.
             pw.LINKEDIN_CREATE_LIST),
            "the set of enabled provider writes changed")
        # The condition restated as a property, so it survives the list
        # growing. It used to read "nothing that reaches a prospect is
        # supported". That could not tell staging a lead into a campaign
        # that cannot send apart from sending somebody a message, and the
        # first is how the second ever becomes possible safely. The property
        # that has to hold: no prospect-facing verb is enabled without a
        # condition that decides, per write, whether it reaches anyone.
        for operation, (_c, facing, _w) in providerwrites.OPERATIONS.items():
            if not facing:
                continue
            if providerwrites.is_supported(operation):
                self.assertTrue(providerwrites.is_conditional(operation),
                                operation)
            else:
                self.assertFalse(providerwrites.is_conditional(operation),
                                 operation)

    def test_every_other_declared_operation_refuses(self):
        for operation in providerwrites.OPERATIONS:
            if operation in providerwrites.SUPPORTED:
                continue
            with self.subTest(operation=operation):
                with self.assertRaises(providerwrites.WriteUnsupported):
                    providerwrites.require_supported(operation)

    def test_an_undeclared_operation_refuses_rather_than_passing_through(self):
        for operation in ("heyreach.send_inmail", "bison.blast", "", None):
            with self.subTest(operation=operation):
                with self.assertRaises(providerwrites.WriteUnsupported):
                    providerwrites.perform(operation, transport=Spy(),
                                           readback=lambda: {})

    def test_perform_never_touches_the_transport_for_an_unsupported_op(self):
        """The strong claim: not a refused call, no call."""
        spy = Spy()
        for operation in providerwrites.OPERATIONS:
            if operation in providerwrites.SUPPORTED:
                continue
            with self.subTest(operation=operation):
                with self.assertRaises(providerwrites.WriteUnsupported):
                    providerwrites.perform(operation, transport=spy,
                                           readback=lambda: {})
        self.assertEqual(spy.calls, [])

    def test_the_unsupported_reason_names_why_not_just_that(self):
        """"Unsupported" without a reason invites somebody to try it anyway."""
        for operation, (_c, _f, why) in providerwrites.OPERATIONS.items():
            with self.subTest(operation=operation):
                self.assertTrue(why and len(why) > 20, operation)


class TheProspectFacingOperationsAreLabelled(unittest.TestCase):
    """The label decides whether an Authorization is required, so it is not
    decoration and a wrong one is a safety bug."""

    def test_adding_a_lead_and_activating_are_prospect_facing(self):
        for operation in (providerwrites.LINKEDIN_ADD_LEAD,
                          providerwrites.LINKEDIN_ACTIVATE,
                          providerwrites.EMAIL_ADD_LEAD,
                          providerwrites.EMAIL_ACTIVATE):
            with self.subTest(operation=operation):
                _channel, facing, _why = providerwrites.describe(operation)
                self.assertTrue(facing, f"{operation} must be prospect-facing")

    def test_configuration_operations_are_not_prospect_facing(self):
        """Building and verifying a campaign must be possible without any risk
        of contacting somebody - that is the whole point of staging."""
        for operation in (providerwrites.LINKEDIN_CREATE_LIST,
                          providerwrites.LINKEDIN_CREATE_CAMPAIGN,
                          providerwrites.LINKEDIN_SET_SEQUENCE,
                          providerwrites.LINKEDIN_SET_LIMITS,
                          providerwrites.LINKEDIN_PAUSE,
                          providerwrites.EMAIL_SET_SEQUENCE,
                          providerwrites.EMAIL_PAUSE):
            with self.subTest(operation=operation):
                _channel, facing, _why = providerwrites.describe(operation)
                self.assertFalse(facing, f"{operation} is not prospect-facing")

    def test_pausing_is_never_prospect_facing_and_activating_always_is(self):
        """A stop button must never need an approval to press."""
        for operation in (providerwrites.LINKEDIN_PAUSE,
                          providerwrites.EMAIL_PAUSE):
            self.assertFalse(providerwrites.describe(operation)[1])
        for operation in (providerwrites.LINKEDIN_ACTIVATE,
                          providerwrites.EMAIL_ACTIVATE):
            self.assertTrue(providerwrites.describe(operation)[1])

    def test_every_operation_names_a_real_channel(self):
        for operation, (channel, _f, _w) in providerwrites.OPERATIONS.items():
            with self.subTest(operation=operation):
                self.assertIn(channel, executionguard.CHANNELS)


class TheGuardsHoldWhenARouteIsEnabled(BoundDestination, QueueTest):
    """Enable one route inside the test only, and prove the brakes work.

    This is the part that has to be right BEFORE a real route is enabled, and
    the only honest way to test it is to enable one here and nowhere else.
    """

    OP = providerwrites.LINKEDIN_ADD_LEAD

    def setUp(self):
        super().setUp()
        self.bind_canonical_destination()

    @contextlib.contextmanager
    def enabled(self):
        """The route on, and the door's freshness re-check stubbed out.

        `perform` now calls `executionguard.revalidate`, which re-reads the
        record from disk and re-runs the stops - the fix for a write going
        through after a prospect had unsubscribed. It needs a whole approved
        estate, and these tests are about what the write layer does with a
        provider RESPONSE, which is a different question.

        Stubbing it here is safe precisely because it is asserted elsewhere:
        `test_a_stop_beats_an_authorization` pins that `perform` consults it
        before the transport, by call order, so this stub cannot hide the call
        being deleted.
        """
        with mock.patch.object(providerwrites, "SUPPORTED", (self.OP,)),              mock.patch.object(providerwrites,
                               "CAMPAIGN_LEVEL_STAGING_IS_PROVEN",
                               True), mock.patch.object(heyreach, "campaign_read",
                               return_value=dict(DRAFT_ROW)),              mock.patch.object(campaigns_state, "require",
                               return_value=dict(CANON_ROW)),              mock.patch.object(executionguard, "revalidate",
                               lambda *a, **kw: True):
            yield

    def test_a_prospect_facing_write_refuses_without_an_authorization(self):
        spy = Spy()
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       transport=spy,
                                       readback=lambda: {})
        self.assertEqual(spy.calls, [])

    def test_a_dict_pretending_to_be_an_authorization_refuses(self):
        spy = Spy()
        fake = {"key": "rec:contact:day3:linkedin", "channel": "linkedin",
                "gates": ("tenancy", "approval", "killswitch")}
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=fake,
                                       transport=spy, readback=lambda: {})
        self.assertEqual(spy.calls, [])

    def test_an_authorization_for_the_wrong_channel_refuses(self):
        spy = Spy()
        auth = executionguard.Authorization(
            key="rec:contact:day5:email", channel="email",
            operation="email_first_touch")
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=auth,
                                       step=STEP, payload=APPROVED,
                                       transport=spy, readback=lambda: {})
        self.assertEqual(spy.calls, [])

    def test_a_missing_readback_refuses_before_the_transport(self):
        """A write whose effect is never read cannot be classified."""
        spy = Spy()
        auth = executionguard.Authorization(
            key="rec:contact:day3:linkedin", channel="linkedin",
            operation=providerwrites.LINKEDIN_ADD_LEAD,
            fingerprint=approval.fingerprint(STEP))
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=auth,
                                       step=STEP, payload=APPROVED,
                                       transport=spy, readback=None)
        self.assertEqual(spy.calls, [])

    def test_a_missing_transport_refuses(self):
        auth = executionguard.Authorization(
            key="rec:contact:day3:linkedin", channel="linkedin",
            operation=providerwrites.LINKEDIN_ADD_LEAD,
            fingerprint=approval.fingerprint(STEP))
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=auth,
                                       step=STEP, payload=APPROVED,
                                       transport=None, readback=lambda: {})

    def test_an_authorization_with_no_reservation_is_refused(self):
        """`Authorization` is a plain object and can be constructed directly.
        A prospect-facing write with no durable row before it is
        unreconcilable after it, so the reservation is required rather than
        assumed."""
        spy = Spy()
        auth = executionguard.Authorization(
            key="unreserved:contact:day3:linkedin", channel="linkedin",
            operation="linkedin_connection_request")
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=auth,
                                       step=STEP, payload=APPROVED,
                                       transport=spy,
                                       readback=lambda: {"leads": 1},
                                       expected={"leads": 1})
        self.assertEqual(spy.calls, [])

    def test_one_authorization_cannot_drive_two_writes(self):
        store.save([dict(store.new_record("rec", "cold", "productive",
                                          "Kestrel Wharf Studio",
                                          "kestrelwharf.test"),
                         contacts=[{"key": "contact", "name": "Dana"}])])
        auth = executionguard.Authorization(
            key="rec:contact:day3:linkedin", channel="linkedin",
            operation=providerwrites.LINKEDIN_ADD_LEAD,
            rec_id="rec", contact_key="contact", step_key="day3",
            fingerprint=approval.fingerprint(STEP))
        actionledger.reserve(
            auth.key, channel="linkedin", workspace="productive",
            campaign_id="canary", sender_id=116968, rec_id="rec",
            contact_key="contact", step_key="day3",
            operation="linkedin_connection_request", fingerprint="fp")
        spy = Spy()
        with self.enabled():
            providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=auth,
                                       step=STEP, payload=APPROVED, transport=spy,
                                   readback=lambda: {"leads": 1},
                                   expected={"leads": 1})
            with self.assertRaises(executionguard.NotAuthorized):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=auth,
                                       step=STEP, payload=APPROVED,
                                       transport=spy,
                                       readback=lambda: {"leads": 1},
                                       expected={"leads": 1})
        self.assertEqual(len(spy.calls), 1)


class AFailedWriteIsClassifiedNotRetried(BoundDestination, QueueTest):
    """The rule the whole module exists for: read back before deciding."""

    OP = providerwrites.LINKEDIN_ADD_LEAD

    def setUp(self):
        super().setUp()
        self.bind_canonical_destination()
        # A REAL AUTHORIZATION NAMES ITS RECORD. This one named only a key,
        # which no `executionguard.authorize` could ever produce - `reserve`
        # below already requires rec_id, contact_key and step_key, and the
        # object claiming the gates passed was missing all three. `perform`
        # now records the canonical confirmed touch on that record after the
        # read-back accepts, so a partial authorization no longer half-works:
        # it fails closed, which is the point.
        store.save([dict(store.new_record("rec-1", "cold", "productive",
                                          "Kestrel Wharf Studio",
                                          "kestrelwharf.test"),
                         contacts=[{"key": "dana", "name": "Dana Oyelaran"}])])
        self.auth = executionguard.Authorization(
            key="rec-1:dana:day3:linkedin", channel="linkedin",
            operation=self.OP,
            rec_id="rec-1", contact_key="dana", step_key="day3",
            fingerprint=approval.fingerprint(STEP))
        actionledger.reserve(
            self.auth.key, channel="linkedin", workspace="productive",
            campaign_id="canary", sender_id=116968, rec_id="rec-1",
            contact_key="dana", step_key="day3",
            operation="linkedin_connection_request", fingerprint="abc123",
            provider_workspace=10)

    @contextlib.contextmanager
    def enabled(self):
        """The route on, and the door's freshness re-check stubbed out.

        `perform` now calls `executionguard.revalidate`, which re-reads the
        record from disk and re-runs the stops - the fix for a write going
        through after a prospect had unsubscribed. It needs a whole approved
        estate, and these tests are about what the write layer does with a
        provider RESPONSE, which is a different question.

        Stubbing it here is safe precisely because it is asserted elsewhere:
        `test_a_stop_beats_an_authorization` pins that `perform` consults it
        before the transport, by call order, so this stub cannot hide the call
        being deleted.
        """
        with mock.patch.object(providerwrites, "SUPPORTED", (self.OP,)),              mock.patch.object(providerwrites,
                               "CAMPAIGN_LEVEL_STAGING_IS_PROVEN",
                               True), mock.patch.object(heyreach, "campaign_read",
                               return_value=dict(DRAFT_ROW)),              mock.patch.object(campaigns_state, "require",
                               return_value=dict(CANON_ROW)),              mock.patch.object(executionguard, "revalidate",
                               lambda *a, **kw: True):
            yield

    def test_a_transport_exception_leaves_the_key_unresolved(self):
        """A timeout says nothing about whether the provider acted."""
        spy = Spy(raises=TimeoutError("read timed out"))
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=self.auth,
                                       step=STEP, payload=APPROVED,
                                       transport=spy, readback=lambda: {},
                                       expected={"leads": 1})
        self.assertEqual(actionledger.state_of(self.auth.key),
                         actionledger.UNRESOLVED)

    def test_an_unresolved_key_can_never_be_retried(self):
        spy = Spy(raises=TimeoutError("read timed out"))
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=self.auth,
                                       step=STEP, payload=APPROVED,
                                       transport=spy, readback=lambda: {},
                                       expected={"leads": 1})
        with self.assertRaises(actionledger.Unsettled):
            actionledger.require_clear(self.auth.key)

    def test_a_failing_readback_leaves_the_key_unresolved(self):
        """It answered, then we could not see what it did. Worse, not better."""
        def boom():
            raise ConnectionError("read-back failed")
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=self.auth,
                                       step=STEP, payload=APPROVED,
                                       transport=Spy(), readback=boom,
                                       expected={"leads": 1})
        self.assertEqual(actionledger.state_of(self.auth.key),
                         actionledger.UNRESOLVED)

    def test_drift_between_asked_and_observed_is_not_success(self):
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=self.auth,
                                       step=STEP, payload=APPROVED,
                                       transport=Spy(),
                                       readback=lambda: {"leads": 2},
                                       expected={"leads": 1})
        self.assertEqual(actionledger.state_of(self.auth.key),
                         actionledger.UNRESOLVED)

    def test_no_expectation_is_never_accepted(self):
        """A write with nothing to compare against cannot be called a success."""
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP,
                                       provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                                       authorization=self.auth,
                                       step=STEP, payload=APPROVED,
                                       transport=Spy(),
                                       readback=lambda: {"leads": 1},
                                       expected=None)

    def test_a_matching_readback_settles_the_key_as_sent(self):
        with self.enabled():
            found = providerwrites.perform(
                self.OP, provider_campaign_id=DRAFT_DESTINATION, campaign=CANON,
                authorization=self.auth, transport=Spy(),
                step=STEP, payload=APPROVED,
                readback=lambda: {"leads": 1}, expected={"leads": 1})
        self.assertEqual(found["class"], providerwrites.ACCEPTED)
        self.assertEqual(actionledger.state_of(self.auth.key),
                         actionledger.SENT)


class TheClassifierIsStrict(unittest.TestCase):
    def test_a_missing_expected_field_is_drift(self):
        self.assertEqual(
            providerwrites._classify({"leads": 1}, {"leads": 1, "status": "ok"}),
            providerwrites.DRIFTED)

    def test_an_extra_observed_field_is_not_drift_on_its_own(self):
        """The differ owns "unexpected". This only asks: did we get what we
        asked for."""
        self.assertEqual(
            providerwrites._classify({"leads": 1, "id": 9}, {"leads": 1}),
            providerwrites.ACCEPTED)

    def test_none_observed_is_never_accepted(self):
        self.assertNotEqual(providerwrites._classify(None, {"leads": 1}),
                            providerwrites.ACCEPTED)

    def test_every_class_is_declared(self):
        for name in (providerwrites.ACCEPTED, providerwrites.REFUSED,
                     providerwrites.UNKNOWN, providerwrites.DRIFTED):
            self.assertIn(name, providerwrites.CLASSES)


class ADestinationThatCannotBeNamedIsRefused(QueueTest):
    """THE PROPERTY FIFTEEN FIXTURES IN THIS REPOSITORY WERE RELYING ON.

    Before `providerwrites.require_resonate_os_campaign` existed, a `perform`
    could be handed a `campaign=` string that no canonical row resolved and no
    `provider_campaign_id` beside it, and it would still reach the transport.
    Fifteen tests across five modules were written that way - they named a
    destination nothing could identify, and they passed. When the ownership
    guard landed they all went red at once with a message about internal
    Resonate campaigns, which reads like four separate bugs and is one missing
    assertion.

    This is that assertion. It is written as an EFFECT: `transport` and
    `readback` append to `self.reached`, so "refused" means the write never got
    to the provider boundary rather than that a log line said so.

    THE LAST TEST IS THE POSITIVE CONTROL and it is not optional. Without it
    the three refusals would pass just as well against a guard that refused
    every write in the system, which would prove nothing about this one.
    """

    OP = providerwrites.LINKEDIN_PAUSE

    #: A canonical row that EXISTS and binds nothing. The subtle half of the
    #: hole: `campaigns.get` answers, so a fixture mocking `require` looks
    #: healthy, while the write still has no destination.
    UNBOUND = "productive-a-row-that-binds-no-provider-campaign"

    #: A real HeyReach campaign of ours, used only by the positive control.
    PROVIDER = 605487

    #: A provider campaign id nothing in this system has ever recorded, and
    #: that the operator has not declared internal either. `unknown`.
    NOBODYS = 777777

    def setUp(self):
        super().setUp()
        self.reached = []

    def transport(self, payload=None):
        self.reached.append(payload)
        return {"ok": True}

    def readback(self):
        self.reached.append("readback")
        return {"status": "PAUSED"}

    def row(self, campaign_id, heyreach_id=None):
        row = campaigns_state.new_campaign(campaign_id, "productive",
                                           campaign_id, created_by="test")
        if heyreach_id is not None:
            row["heyreach_campaign_id"] = str(heyreach_id)
        campaigns_state.save([row])
        self.assertIsNotNone(campaigns_state.get(campaign_id),
                             "the ledger fixture did not persist")
        return row

    def pause(self, **kw):
        kw.setdefault("payload", {"campaignId": self.PROVIDER})
        kw.setdefault("transport", self.transport)
        kw.setdefault("readback", self.readback)
        kw.setdefault("expected", {"status": "PAUSED"})
        return providerwrites.perform(self.OP, tenant="productive", **kw)

    def test_the_verb_is_enabled_so_a_refusal_below_is_about_ownership(self):
        """Otherwise every assertion here would pass on the sealed door."""
        self.assertTrue(providerwrites.is_supported(self.OP))
        _channel, facing, _why = providerwrites.describe(self.OP)
        self.assertFalse(facing, "this fixture carries no Authorization")

    def test_a_row_that_binds_no_provider_campaign_is_refused(self):
        self.row(self.UNBOUND)
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            self.pause(campaign=self.UNBOUND)
        self.assertEqual(self.reached, [],
                         "THE TRANSPORT WAS REACHED by a write whose "
                         "destination nothing resolves")
        self.assertIn("names no provider campaign", str(caught.exception))

    def test_a_campaign_no_row_mentions_at_all_is_refused(self):
        with self.assertRaises(providerwrites.WriteRefused):
            self.pause(campaign="productive-nothing-has-ever-recorded-this")
        self.assertEqual(self.reached, [], "THE TRANSPORT WAS REACHED")

    def test_a_provider_id_nothing_records_is_refused_not_admitted(self):
        """Naming a number is not naming a destination. Absence is a refusal."""
        self.row(self.UNBOUND)
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            self.pause(campaign=self.UNBOUND,
                       provider_campaign_id=self.NOBODYS)
        self.assertEqual(self.reached, [], "THE TRANSPORT WAS REACHED")
        self.assertIn(providerwrites.UNKNOWN_OWNER, str(caught.exception))

    def test_the_same_write_performs_once_the_row_names_the_destination(self):
        """THE POSITIVE CONTROL. One line of fixture apart from the first
        test, and the opposite outcome - so the refusals above are about the
        destination being nameless and not about the write being a pause."""
        self.row(self.UNBOUND, heyreach_id=self.PROVIDER)
        self.assertEqual(
            providerwrites.classify_campaign("linkedin", self.PROVIDER),
            providerwrites.RESONATE_OS)
        outcome = self.pause(campaign=self.UNBOUND)
        self.assertEqual(outcome["class"], providerwrites.ACCEPTED)
        self.assertEqual(self.reached,
                         [{"campaignId": self.PROVIDER}, "readback"],
                         "the transport and the read-back were not both "
                         "reached, so the positive control proves nothing")


if __name__ == "__main__":
    unittest.main()
