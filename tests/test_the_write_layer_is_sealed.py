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
import unittest
from unittest import mock

from src import actionledger, executionguard, providerwrites

from tests.base import QueueTest


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
    def test_no_operation_is_supported(self):
        """If this fails, somebody enabled a provider write. That is a
        deliberate act and it should be argued for in the diff that does it -
        not discovered later by reading logs."""
        self.assertEqual(providerwrites.SUPPORTED, (),
                         "a provider write route has been enabled")
        self.assertTrue(providerwrites.report()["sealed"])

    def test_every_declared_operation_refuses(self):
        for operation in providerwrites.OPERATIONS:
            with self.subTest(operation=operation):
                with self.assertRaises(providerwrites.WriteUnsupported):
                    providerwrites.require_supported(operation)

    def test_an_undeclared_operation_refuses_rather_than_passing_through(self):
        for operation in ("heyreach.send_inmail", "bison.blast", "", None):
            with self.subTest(operation=operation):
                with self.assertRaises(providerwrites.WriteUnsupported):
                    providerwrites.perform(operation, transport=Spy(),
                                           readback=lambda: {})

    def test_perform_never_touches_the_transport_while_sealed(self):
        """The strong claim: not a refused call, no call."""
        spy = Spy()
        for operation in providerwrites.OPERATIONS:
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


class TheGuardsHoldWhenARouteIsEnabled(QueueTest):
    """Enable one route inside the test only, and prove the brakes work.

    This is the part that has to be right BEFORE a real route is enabled, and
    the only honest way to test it is to enable one here and nowhere else.
    """

    OP = providerwrites.LINKEDIN_ADD_LEAD

    def enabled(self):
        return mock.patch.object(providerwrites, "SUPPORTED", (self.OP,))

    def test_a_prospect_facing_write_refuses_without_an_authorization(self):
        spy = Spy()
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP, transport=spy,
                                       readback=lambda: {})
        self.assertEqual(spy.calls, [])

    def test_a_dict_pretending_to_be_an_authorization_refuses(self):
        spy = Spy()
        fake = {"key": "rec:contact:day3:linkedin", "channel": "linkedin",
                "gates": ("tenancy", "approval", "killswitch")}
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP, authorization=fake,
                                       transport=spy, readback=lambda: {})
        self.assertEqual(spy.calls, [])

    def test_an_authorization_for_the_wrong_channel_refuses(self):
        spy = Spy()
        auth = executionguard.Authorization(
            key="rec:contact:day5:email", channel="email",
            operation="email_first_touch")
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP, authorization=auth,
                                       transport=spy, readback=lambda: {})
        self.assertEqual(spy.calls, [])

    def test_a_missing_readback_refuses_before_the_transport(self):
        """A write whose effect is never read cannot be classified."""
        spy = Spy()
        auth = executionguard.Authorization(
            key="rec:contact:day3:linkedin", channel="linkedin",
            operation="linkedin_connection_request")
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP, authorization=auth,
                                       transport=spy, readback=None)
        self.assertEqual(spy.calls, [])

    def test_a_missing_transport_refuses(self):
        auth = executionguard.Authorization(
            key="rec:contact:day3:linkedin", channel="linkedin",
            operation="linkedin_connection_request")
        with self.enabled():
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(self.OP, authorization=auth,
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
                providerwrites.perform(self.OP, authorization=auth,
                                       transport=spy,
                                       readback=lambda: {"leads": 1},
                                       expected={"leads": 1})
        self.assertEqual(spy.calls, [])

    def test_one_authorization_cannot_drive_two_writes(self):
        auth = executionguard.Authorization(
            key="rec:contact:day3:linkedin", channel="linkedin",
            operation="linkedin_connection_request")
        actionledger.reserve(
            auth.key, channel="linkedin", workspace="productive",
            campaign_id="canary", sender_id=116968, rec_id="rec",
            contact_key="contact", step_key="day3",
            operation="linkedin_connection_request", fingerprint="fp")
        spy = Spy()
        with self.enabled():
            providerwrites.perform(self.OP, authorization=auth, transport=spy,
                                   readback=lambda: {"leads": 1},
                                   expected={"leads": 1})
            with self.assertRaises(executionguard.NotAuthorized):
                providerwrites.perform(self.OP, authorization=auth,
                                       transport=spy,
                                       readback=lambda: {"leads": 1},
                                       expected={"leads": 1})
        self.assertEqual(len(spy.calls), 1)


class AFailedWriteIsClassifiedNotRetried(QueueTest):
    """The rule the whole module exists for: read back before deciding."""

    OP = providerwrites.LINKEDIN_ADD_LEAD

    def setUp(self):
        super().setUp()
        self.auth = executionguard.Authorization(
            key="rec-1:dana:day3:linkedin", channel="linkedin",
            operation="linkedin_connection_request")
        actionledger.reserve(
            self.auth.key, channel="linkedin", workspace="productive",
            campaign_id="canary", sender_id=116968, rec_id="rec-1",
            contact_key="dana", step_key="day3",
            operation="linkedin_connection_request", fingerprint="abc123",
            provider_workspace=10)

    def enabled(self):
        return mock.patch.object(providerwrites, "SUPPORTED", (self.OP,))

    def test_a_transport_exception_leaves_the_key_unresolved(self):
        """A timeout says nothing about whether the provider acted."""
        spy = Spy(raises=TimeoutError("read timed out"))
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP, authorization=self.auth,
                                       transport=spy, readback=lambda: {},
                                       expected={"leads": 1})
        self.assertEqual(actionledger.state_of(self.auth.key),
                         actionledger.UNRESOLVED)

    def test_an_unresolved_key_can_never_be_retried(self):
        spy = Spy(raises=TimeoutError("read timed out"))
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP, authorization=self.auth,
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
                providerwrites.perform(self.OP, authorization=self.auth,
                                       transport=Spy(), readback=boom,
                                       expected={"leads": 1})
        self.assertEqual(actionledger.state_of(self.auth.key),
                         actionledger.UNRESOLVED)

    def test_drift_between_asked_and_observed_is_not_success(self):
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP, authorization=self.auth,
                                       transport=Spy(),
                                       readback=lambda: {"leads": 2},
                                       expected={"leads": 1})
        self.assertEqual(actionledger.state_of(self.auth.key),
                         actionledger.UNRESOLVED)

    def test_no_expectation_is_never_accepted(self):
        """A write with nothing to compare against cannot be called a success."""
        with self.enabled():
            with self.assertRaises(providerwrites.WriteUnverified):
                providerwrites.perform(self.OP, authorization=self.auth,
                                       transport=Spy(),
                                       readback=lambda: {"leads": 1},
                                       expected=None)

    def test_a_matching_readback_settles_the_key_as_sent(self):
        with self.enabled():
            found = providerwrites.perform(
                self.OP, authorization=self.auth, transport=Spy(),
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


if __name__ == "__main__":
    unittest.main()
