"""The live-activation grant unseals ONE named campaign, and nothing else.

Both ACTIVATE verbs are prospect-facing, so `providerwrites.perform` refuses
them without an `executionguard.Authorization` - and until this mechanism
existed, `authorize` could not mint one for ANY campaign on EITHER channel.
Gate 7 refused at two layers that both trace back to `push.LiveSendNotEnabled`:
the GLOBAL layer is derived from that exception EXISTING, and the CAMPAIGN
layer requires `running`, which only `orchestrator.launch(live=True)` can set
and which raises that same exception.

So the question this module answers is not "does the grant work". It is
"having opened a door that was welded shut, is anything through it that the
operator did not name". Every test here is an attempt to get an activation
authorized that nobody granted.

THE DEFAULT IS THE MOST IMPORTANT TEST IN THE FILE. `LIVE_ACTIVATION_GRANTS`
ships empty, so the mechanism on its own changes nothing: every activation is
refused exactly as it was before. If `test_the_grant_ships_empty` ever fails
in a way that is not a deliberate, reviewed operator decision, a campaign can
send and nobody decided that it should.
"""
import unittest
from unittest import mock

from src import executionguard, killswitch, providerwrites

from tests.test_no_write_happens_without_every_gate import GuardTest, WS, NOW


LINKEDIN_ACTIVATE = "heyreach.activate"
EMAIL_ACTIVATE = "bison.activate"


class TheGrantIsEmptyUntilSomebodyDecides(unittest.TestCase):
    """No fixture, no estate: these are facts about the shipped module."""

    def test_the_grant_holds_exactly_what_an_operator_decided(self):
        """THE ALARM. Pinned by value, so ANY change fails here first.

        This shipped empty. It now holds one entry, added under the operator's
        2026-09-16 grant: "APPROVE HEYREACH ACTIVATION: campaign 605487, 4
        approved READY leads". If this test fails and the change was not a
        deliberate, reviewed operator decision, a campaign can send and nobody
        decided that it should. Widening it is never a refactor.
        """
        self.assertEqual(
            executionguard.LIVE_ACTIVATION_GRANTS,
            {"productive-linkedin-cohort-v2": frozenset({LINKEDIN_ACTIVATE}),
             "productive-email-control-v3": frozenset({EMAIL_ACTIVATE})})

    def test_each_grant_names_one_channel_only(self):
        """The two channels are approved separately and stay separate.

        A LinkedIn grant must not carry the email verb and vice versa - the
        exposures are different, they were approved at different times, and a
        grant that carried both would let one approval start two campaigns.
        """
        expected = {"productive-linkedin-cohort-v2": LINKEDIN_ACTIVATE,
                    "productive-email-control-v3": EMAIL_ACTIVATE}
        for campaign_id, granted in (
                executionguard.LIVE_ACTIVATION_GRANTS.items()):
            self.assertIn(campaign_id, expected)
            self.assertEqual(granted, frozenset({expected[campaign_id]}))

    def test_the_operations_are_exactly_the_two_activate_verbs(self):
        self.assertEqual(
            executionguard.ACTIVATION_OPERATIONS,
            frozenset({LINKEDIN_ACTIVATE, EMAIL_ACTIVATE}))

    def test_the_names_match_the_write_layer(self):
        """A grant naming a verb the write layer does not know is a grant on
        nothing, and would fail open by being silently inapplicable."""
        self.assertEqual(providerwrites.LINKEDIN_ACTIVATE, LINKEDIN_ACTIVATE)
        self.assertEqual(providerwrites.EMAIL_ACTIVATE, EMAIL_ACTIVATE)

    def test_nothing_is_granted_by_default(self):
        for operation in (LINKEDIN_ACTIVATE, EMAIL_ACTIVATE):
            self.assertFalse(executionguard.activation_is_granted(
                operation, {"campaign_id": "anything-at-all"}))


class TheGrantFailsClosed(unittest.TestCase):
    """`activation_is_granted` refuses everything it was not told about."""

    def setUp(self):
        self.original = dict(executionguard.LIVE_ACTIVATION_GRANTS)
        executionguard.LIVE_ACTIVATION_GRANTS.clear()
        executionguard.LIVE_ACTIVATION_GRANTS["granted-campaign"] = frozenset(
            {LINKEDIN_ACTIVATE})
        self.addCleanup(self._restore)

    def _restore(self):
        executionguard.LIVE_ACTIVATION_GRANTS.clear()
        executionguard.LIVE_ACTIVATION_GRANTS.update(self.original)

    def test_the_granted_pair_is_granted(self):
        self.assertTrue(executionguard.activation_is_granted(
            LINKEDIN_ACTIVATE, {"campaign_id": "granted-campaign"}))

    def test_a_different_campaign_is_not(self):
        """THE POINT OF NAMING A CAMPAIGN. One grant is one campaign."""
        self.assertFalse(executionguard.activation_is_granted(
            LINKEDIN_ACTIVATE, {"campaign_id": "some-other-campaign"}))

    def test_the_other_channel_is_not(self):
        """A grant to start a LinkedIn campaign is not a grant to start
        emailing. Same campaign row, different verb, different exposure."""
        self.assertFalse(executionguard.activation_is_granted(
            EMAIL_ACTIVATE, {"campaign_id": "granted-campaign"}))

    def test_a_non_activation_verb_is_never_granted(self):
        """The grant must not become a general-purpose bypass: a verb that is
        not an activation can never be admitted by it, however it is named."""
        for operation in ("linkedin_connection_request", "linkedin_message",
                          "email_send", "heyreach.add_lead_to_list", ""):
            self.assertFalse(executionguard.activation_is_granted(
                operation, {"campaign_id": "granted-campaign"}))

    def test_an_unnamed_campaign_is_not_granted(self):
        for campaign in (None, {}, {"campaign_id": None}, {"campaign_id": ""}):
            self.assertFalse(executionguard.activation_is_granted(
                LINKEDIN_ACTIVATE, campaign))


class AnUngrantedActivationIsStillRefused(GuardTest):
    """With the shipped empty grant, gate 7 refuses exactly as before."""

    def test_the_killswitch_still_refuses_an_activation(self):
        """This is the state the repository ships in. An activation that
        nobody granted is refused by the GLOBAL layer, and the refusal names
        the killswitch rather than something incidental."""
        self.assertFalse(executionguard.activation_is_granted(
            LINKEDIN_ACTIVATE, self.campaign))
        with self.allow_collision():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(operation=LINKEDIN_ACTIVATE)
        self.assertEqual(caught.exception.gate, "killswitch")
        self.assertIn("killswitch", str(caught.exception))

    def test_the_refusal_is_the_global_layer_and_says_so(self):
        """Refused for being an unimplemented send path, not for a stale
        readback or a missing approval - so that the day the grant is used,
        the reason it was refused before is known."""
        with self.allow_collision():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(operation=LINKEDIN_ACTIVATE)
        self.assertIn("global", str(caught.exception).lower())


class AGrantedActivationPassesGateSevenAndNothingElse(GuardTest):
    """The grant admits the named campaign - and only by the stated route."""

    def setUp(self):
        super().setUp()
        self.original = dict(executionguard.LIVE_ACTIVATION_GRANTS)
        executionguard.LIVE_ACTIVATION_GRANTS.clear()
        self.addCleanup(self._restore)

    def _restore(self):
        executionguard.LIVE_ACTIVATION_GRANTS.clear()
        executionguard.LIVE_ACTIVATION_GRANTS.update(self.original)

    def allow_workspace(self):
        """The tenant switch reports ON.

        Stubbed only where the test is about the GRANT. The isolated estate
        registers no `productive` workspace, so the real layer refuses - which
        is correct behaviour and is asserted on its own in
        `test_the_workspace_killswitch_still_refuses`. Stubbing it there too
        would have made that test vacuous.
        """
        return mock.patch.object(
            killswitch, "workspace_state",
            return_value={"sending": True, "why": "on for productive"})

    def grant(self, operation=LINKEDIN_ACTIVATE, campaign_id=None):
        campaign_id = campaign_id or self.campaign["campaign_id"]
        executionguard.LIVE_ACTIVATION_GRANTS[campaign_id] = frozenset(
            {operation})

    def test_a_granted_activation_is_authorized(self):
        self.grant()
        with self.allow_collision(), self.allow_workspace():
            auth = self.authorize(operation=LINKEDIN_ACTIVATE)
        self.assertIsInstance(auth, executionguard.Authorization)
        self.assertEqual(auth.operation, LINKEDIN_ACTIVATE)

    def test_the_grant_is_recorded_in_the_gate_trace(self):
        """An audit must be able to see WHICH route admitted this. A grant
        that leaves no trace is a permission nobody can find afterwards."""
        self.grant()
        with self.allow_collision(), self.allow_workspace():
            auth = self.authorize(operation=LINKEDIN_ACTIVATE)
        gates = list(getattr(auth, "gates", ()) or ())
        self.assertIn("killswitch:activation-grant", gates)
        self.assertIn("killswitch:workspace", gates)
        self.assertNotIn("killswitch", gates)

    def test_granting_one_campaign_does_not_admit_another(self):
        """The escalation this mechanism exists to prevent."""
        self.grant(campaign_id="a-completely-different-campaign")
        with self.allow_collision():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(operation=LINKEDIN_ACTIVATE)
        self.assertEqual(caught.exception.gate, "killswitch")

    def test_granting_one_verb_does_not_admit_the_other(self):
        """Approving a LinkedIn launch must not start an email campaign.

        Asserted on the grant rather than through `authorize`: an email
        authorize in an isolated estate is refused at TENANCY for having no
        EmailBison key, which would pass this test without ever reaching the
        gate it is about.
        """
        self.grant(operation=LINKEDIN_ACTIVATE)
        self.assertFalse(executionguard.activation_is_granted(
            EMAIL_ACTIVATE, self.campaign))
        self.assertTrue(executionguard.activation_is_granted(
            LINKEDIN_ACTIVATE, self.campaign))

    def test_the_workspace_killswitch_still_refuses(self):
        """The tenant's own switch is NOT skipped by the grant. A workspace
        that was never switched on gets nothing activated for it, however
        loudly the grant names the campaign."""
        self.grant()
        with self.allow_collision(), mock.patch.object(
                killswitch, "workspace_state",
                return_value={"sending": False, "why": "switched off"}):
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(operation=LINKEDIN_ACTIVATE)
        self.assertEqual(caught.exception.gate, "killswitch")
        self.assertIn("switched off", str(caught.exception))

    def test_a_granted_activation_still_meets_every_earlier_gate(self):
        """THE GRANT IS GATE 7 ONLY. It must not become a way past the
        approval, the readback, the collision check or the rest. A stale
        readback is used here as the representative of gates 1-6: if the grant
        short-circuited them, this would be authorized."""
        from tests.test_no_write_happens_without_every_gate import STALE
        self.grant()
        with self.allow_collision():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(operation=LINKEDIN_ACTIVATE,
                               readback=self.readback(verified_at=STALE))
        self.assertNotEqual(caught.exception.gate, "killswitch")

    def test_a_granted_activation_is_still_refused_without_approval(self):
        """The campaign-level approval binds the LEAD SET by fingerprint. A
        grant is permission to start a campaign, not permission to start an
        unapproved one."""
        self.grant()
        self.campaign["approval"] = None
        self.campaign["fingerprint"] = None
        with self.allow_collision():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(operation=LINKEDIN_ACTIVATE)
        self.assertNotEqual(caught.exception.gate, "killswitch")

    def test_the_grant_does_not_touch_ordinary_sending_verbs(self):
        """A per-message send is not an activation and must still meet the
        FULL stack, GLOBAL included - otherwise granting an activation would
        quietly enable sending through this build."""
        self.grant()
        with self.allow_collision():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self.authorize(operation="linkedin_connection_request")
        self.assertEqual(caught.exception.gate, "killswitch")
        self.assertIn("global", str(caught.exception).lower())


class ThePushRefusalIsUntouched(unittest.TestCase):
    """The grant's whole argument is that activation is not a push send.

    If `push.run`'s refusal were ever removed to make an activation work, the
    argument would be gone and this build really would be able to send. So the
    refusal is asserted here, next to the mechanism that relies on it.
    """

    def test_push_still_refuses_to_send(self):
        from src import push
        self.assertTrue(hasattr(push, "LiveSendNotEnabled"))

    def test_the_global_layer_still_reports_refused(self):
        state = killswitch.global_state()
        self.assertFalse(state["sending"])
        self.assertTrue(state.get("refused_in_code"))


if __name__ == "__main__":
    unittest.main()
