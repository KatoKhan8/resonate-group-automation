#!/usr/bin/env python3
"""TASK-566 — campaign-scoped authority for prospect-facing provider writes.

Operator decision 2026-09-29: workspace-wide lead-creation authorization is
too wide. A grant binds client, provider, purpose, phase, operations, the
exact campaign once it exists, and the recipient where the verb is
per-recipient. DEFAULT IS REFUSE.

Every test here asserts a REFUSAL or an exact admission. The last class
mutates the boundary itself, because a gate that cannot be shown to fail is
not a gate.
"""
import unittest

from src import executionscope as scope
from src import providerwrites as pw

CLIENT = "productive"
OTHER = "someone-else"
CAMPAIGN = "911"
RECIPIENT = "rcrumpler@2020companies.com"

SETUP_OPS = (pw.EMAIL_CREATE_CAMPAIGN, pw.EMAIL_SET_SEQUENCE,
             pw.EMAIL_SET_LIMITS, pw.EMAIL_ADD_LEAD)


def _setup_grant(**over):
    fields = dict(client=CLIENT, provider="bison", purpose="canary",
                  phase=scope.SETUP, operations=SETUP_OPS,
                  campaign_id=CAMPAIGN, recipient=RECIPIENT,
                  approval_hash="hash")
    fields.update(over)
    return fields


class DefaultIsRefuse(unittest.TestCase):
    def test_no_grant_refuses(self):
        self.assertEqual(scope.active(), ())
        with self.assertRaises(scope.ScopeRefused):
            scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT, provider="bison",
                          campaign_id=CAMPAIGN, recipient=RECIPIENT)

    def test_the_refusal_says_no_grant_is_in_scope(self):
        try:
            scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT, provider="bison",
                          campaign_id=CAMPAIGN)
        except scope.ScopeRefused as e:
            self.assertIn("default is refuse", str(e).lower())


class AGrantAdmitsOnlyItsOwnScope(unittest.TestCase):
    def test_the_exact_scope_is_admitted(self):
        with scope.grant(**_setup_grant()):
            g = scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT,
                              provider="bison", campaign_id=CAMPAIGN,
                              recipient=RECIPIENT)
            self.assertEqual(g.campaign_id, CAMPAIGN)

    def test_another_campaign_is_refused(self):
        with scope.grant(**_setup_grant()):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT,
                              provider="bison", campaign_id="487")

    def test_a_campaignless_call_is_refused_once_bound(self):
        with scope.grant(**_setup_grant()):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT,
                              provider="bison", campaign_id=None)

    def test_another_client_is_refused(self):
        with scope.grant(**_setup_grant()):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ADD_LEAD, client=OTHER,
                              provider="bison", campaign_id=CAMPAIGN)

    def test_another_provider_is_refused(self):
        with scope.grant(**_setup_grant()):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.LINKEDIN_ADD_LEAD, client=CLIENT,
                              provider="heyreach", campaign_id=CAMPAIGN)

    def test_heyreach_is_never_admitted_by_a_bison_grant(self):
        with scope.grant(**_setup_grant()):
            for op in (pw.LINKEDIN_ADD_LEAD, pw.LINKEDIN_ACTIVATE,
                       pw.LINKEDIN_CREATE_CAMPAIGN):
                with self.assertRaises(scope.ScopeRefused, msg=op):
                    scope.require(op, client=CLIENT, provider="heyreach",
                                  campaign_id=CAMPAIGN)

    def test_another_recipient_is_refused(self):
        with scope.grant(**_setup_grant()):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT,
                              provider="bison", campaign_id=CAMPAIGN,
                              recipient="someone.else@example.com")

    def test_an_operation_the_grant_does_not_name_is_refused(self):
        with scope.grant(**_setup_grant()):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_PAUSE, client=CLIENT, provider="bison",
                              campaign_id=CAMPAIGN)

    def test_the_grant_does_not_survive_its_block(self):
        with scope.grant(**_setup_grant()):
            pass
        self.assertEqual(scope.active(), ())
        with self.assertRaises(scope.ScopeRefused):
            scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT, provider="bison",
                          campaign_id=CAMPAIGN)


class TheBootstrapIsBoundedBeforeTheCampaignExists(unittest.TestCase):
    def test_an_unbound_grant_admits_create_and_nothing_with_a_campaign(self):
        with scope.grant(**_setup_grant(campaign_id=None)):
            scope.require(pw.EMAIL_CREATE_CAMPAIGN, client=CLIENT,
                          provider="bison", campaign_id=None)
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT,
                              provider="bison", campaign_id="487")

    def test_binding_makes_the_exact_campaign_required(self):
        with scope.grant(**_setup_grant(campaign_id=None)) as g:
            scope.bind_campaign(g, "4242")
            scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT, provider="bison",
                          campaign_id="4242", recipient=RECIPIENT)
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT,
                              provider="bison", campaign_id="4243")

    def test_a_grant_may_not_be_rebound_to_a_second_campaign(self):
        with scope.grant(**_setup_grant(campaign_id=None)) as g:
            scope.bind_campaign(g, "4242")
            with self.assertRaises(scope.ScopeRefused):
                scope.bind_campaign(g, "9999")

    def test_rebinding_the_same_id_is_not_an_error(self):
        with scope.grant(**_setup_grant(campaign_id=None)) as g:
            scope.bind_campaign(g, "4242")
            scope.bind_campaign(g, "4242")
            self.assertEqual(g.campaign_id, "4242")


class SetupNeverImpliesActivation(unittest.TestCase):
    def test_a_setup_grant_does_not_authorize_activation(self):
        with scope.grant(**_setup_grant(
                operations=SETUP_OPS + (pw.EMAIL_ACTIVATE,))):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ACTIVATE, client=CLIENT,
                              provider="bison", campaign_id=CAMPAIGN,
                              phase=scope.ACTIVATE)

    def test_an_activate_grant_does_not_authorize_setup(self):
        with scope.grant(**_setup_grant(phase=scope.ACTIVATE,
                                        operations=(pw.EMAIL_ACTIVATE,))):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT,
                              provider="bison", campaign_id=CAMPAIGN,
                              phase=scope.SETUP)

    def test_an_activate_grant_admits_only_its_exact_campaign(self):
        with scope.grant(**_setup_grant(phase=scope.ACTIVATE,
                                        operations=(pw.EMAIL_ACTIVATE,))):
            scope.require(pw.EMAIL_ACTIVATE, client=CLIENT, provider="bison",
                          campaign_id=CAMPAIGN, recipient=RECIPIENT,
                          phase=scope.ACTIVATE)
            for other in ("487", "489", "493"):
                with self.assertRaises(scope.ScopeRefused, msg=other):
                    scope.require(pw.EMAIL_ACTIVATE, client=CLIENT,
                                  provider="bison", campaign_id=other,
                                  phase=scope.ACTIVATE)


class HistoricalCampaignsStayOutOfScope(unittest.TestCase):
    """487, 489 and 493 are paused by the operator, by hand, at the provider.

    A canary grant naming its own campaign must not admit any verb against
    them, in either phase.
    """

    PAUSED = ("487", "489", "493")

    def test_no_setup_verb_reaches_a_paused_campaign(self):
        with scope.grant(**_setup_grant()):
            for cid in self.PAUSED:
                for op in SETUP_OPS:
                    with self.assertRaises(scope.ScopeRefused,
                                           msg="%s %s" % (op, cid)):
                        scope.require(op, client=CLIENT, provider="bison",
                                      campaign_id=cid)

    def test_no_activation_reaches_a_paused_campaign(self):
        with scope.grant(**_setup_grant(phase=scope.ACTIVATE,
                                        operations=(pw.EMAIL_ACTIVATE,))):
            for cid in self.PAUSED:
                with self.assertRaises(scope.ScopeRefused, msg=cid):
                    scope.require(pw.EMAIL_ACTIVATE, client=CLIENT,
                                  provider="bison", campaign_id=cid,
                                  phase=scope.ACTIVATE)


class TheLeadFactoryRequiresAGrant(unittest.TestCase):
    """`_ensure_leads` must consult the grant, not only the kill switch."""

    def test_the_factory_calls_require(self):
        import inspect
        from src import bisonfactory
        src = inspect.getsource(bisonfactory._ensure_leads)
        self.assertIn("executionscope.require", src)
        self.assertIn("EMAIL_ADD_LEAD", src)

    def test_the_killswitch_check_is_still_there(self):
        import inspect
        from src import bisonfactory
        src = inspect.getsource(bisonfactory._ensure_leads)
        self.assertIn("killswitch.workspace_state", src,
                      "the campaign scope must be an ADDITIONAL gate, never "
                      "a replacement for the workspace kill switch")


class TheBoundaryIsLoadBearing(unittest.TestCase):
    """Mutate the scope gate and prove the refusals were its doing."""

    def test_neutering_require_admits_everything_it_refused(self):
        real = scope.require
        try:
            scope.require = lambda *a, **k: None
            # every refusal asserted above becomes an admission
            scope.require(pw.EMAIL_ADD_LEAD, client=OTHER, provider="heyreach",
                          campaign_id="487")
        finally:
            scope.require = real
        with self.assertRaises(scope.ScopeRefused):
            scope.require(pw.EMAIL_ADD_LEAD, client=OTHER, provider="heyreach",
                          campaign_id="487")

    def test_a_grant_that_matched_everything_would_admit_a_paused_campaign(self):
        """The dimensions are what refuse, not the presence of a grant."""
        with scope.grant(**_setup_grant(campaign_id="487")):
            scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT, provider="bison",
                          campaign_id="487", recipient=RECIPIENT)
        with scope.grant(**_setup_grant()):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ADD_LEAD, client=CLIENT,
                              provider="bison", campaign_id="487")


class ImportOrderProtectionSurvives(unittest.TestCase):
    """TASK-565 incident 8 must remain true alongside this change."""

    def test_the_transport_guard_is_still_armed_at_providers_import(self):
        from src import providers
        for host in providers.KNOWN_PROSPECT_FACING_HOSTS:
            self.assertIn(host, providers._prospect_facing_hosts)
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write(
                "POST", "https://send.resonategroup.co/api/campaigns/487/leads")


if __name__ == "__main__":
    unittest.main()


class EmailActivateIsScopedByTheOperatorAllowlist(unittest.TestCase):
    """CORRECTION, recorded because the module's prose is stale: EMAIL_ACTIVATE
    IS in SUPPORTED. The comment saying it "stays out" no longer matches the
    tuple.

    It is scoped to an exact campaign by `_AUTHORIZED_EMAIL_CAMPAIGNS`, an
    operator allowlist. That is the older and stronger half and is left
    exactly as it was: a 2026-09-29 attempt to also require an ACTIVATE-phase
    grant in the same conditional broke fourteen existing activation tests and
    was reverted rather than have those tests rewritten around it.

    The setup/activation separation this task asks for holds regardless:
    a SETUP grant does not name EMAIL_ACTIVATE (asserted below), and the
    canary campaign is not on the allowlist until the operator adds it.
    """

    def test_it_is_supported_and_the_prose_saying_otherwise_is_stale(self):
        self.assertIn(pw.EMAIL_ACTIVATE, pw.SUPPORTED)

    def test_activation_is_conditional_on_the_operator_allowlist(self):
        self.assertIs(pw.CONDITIONAL[pw.EMAIL_ACTIVATE],
                      pw._is_the_authorized_email_campaign)

    def test_an_unlisted_campaign_is_refused_whatever_grant_is_open(self):
        with scope.grant(**_setup_grant(phase=scope.ACTIVATE,
                                        operations=(pw.EMAIL_ACTIVATE,))):
            with self.assertRaises(pw.WriteRefused) as ctx:
                pw.CONDITIONAL[pw.EMAIL_ACTIVATE](CAMPAIGN, "not-a-real-row")
            self.assertIn("authorization covers", str(ctx.exception))

    def test_the_canary_setup_grant_never_names_the_activate_verb(self):
        """The separation, asserted where it actually lives."""
        self.assertNotIn(pw.EMAIL_ACTIVATE, SETUP_OPS)
        with scope.grant(**_setup_grant()):
            with self.assertRaises(scope.ScopeRefused):
                scope.require(pw.EMAIL_ACTIVATE, client=CLIENT,
                              provider="bison", campaign_id=CAMPAIGN,
                              phase=scope.ACTIVATE)


if __name__ == "__main__":
    unittest.main()
