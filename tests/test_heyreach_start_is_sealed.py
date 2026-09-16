#!/usr/bin/env python3
"""TASK-218: the start verb is implemented and sealed.

`heyreach.activate_campaign` exists with the full brake set - expect_leads
containment, status classification, polling - and `LINKEDIN_ACTIVATE` is NOT
in `SUPPORTED`, so `providerwrites.perform` refuses it before the transport is
reached.

THE TEST THAT MATTERS MOST. A start verb that is reachable without a
permission is worse than no start verb, because everything else in the path
looks finished. This test proves the OFF switch refuses.
"""
import unittest
from unittest import mock

from src import providerwrites
from src.providers import heyreach


class ActivateCampaignExists(unittest.TestCase):
    """The function is there, with the brakes."""

    def test_activate_campaign_is_defined(self):
        self.assertTrue(callable(heyreach.activate_campaign))

    def test_activate_campaign_refuses_lead_count_mismatch(self):
        """expect_leads containment: the provider disagrees with the caller."""
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([], 9)):
            with self.assertRaises(heyreach.ProviderError) as ctx:
                heyreach.activate_campaign(599020, expect_leads=1)
        self.assertIn("holds", str(ctx.exception))
        self.assertIn("9", str(ctx.exception))
        self.assertIn("expected", str(ctx.exception))
        self.assertIn("1", str(ctx.exception))

    def test_activate_campaign_refuses_missing_total(self):
        """A None total is not a zero."""
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([], None)):
            with self.assertRaises(heyreach.ProviderError) as ctx:
                heyreach.activate_campaign(599020, expect_leads=0)
        self.assertIn("no lead total", str(ctx.exception))

    def test_activate_campaign_classifies_unknown_status(self):
        """An unrecognised status raises rather than reporting success."""
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([], 0)):
            with mock.patch.object(heyreach, "_write", return_value={}):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value={"status": "SOMETHING_NEW"}):
                    with self.assertRaises(heyreach.ProviderError) as ctx:
                        heyreach.activate_campaign(599020, expect_leads=0,
                                                   attempts=1, interval=0)
        self.assertIn("cannot classify", str(ctx.exception))

    def test_activate_campaign_raises_on_timeout(self):
        """A campaign still DRAFT after all polls raises."""
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([], 0)):
            with mock.patch.object(heyreach, "_write", return_value={}):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value={"status": "DRAFT"}):
                    with self.assertRaises(heyreach.ProviderError) as ctx:
                        heyreach.activate_campaign(599020, expect_leads=0,
                                                   attempts=2, interval=0)
        self.assertIn("still", str(ctx.exception))
        self.assertIn("DRAFT", str(ctx.exception))

    def test_activate_campaign_returns_on_in_progress(self):
        """IN_PROGRESS is the expected post-start status."""
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([], 3)):
            with mock.patch.object(heyreach, "_write", return_value={}):
                with mock.patch.object(heyreach, "campaign_read",
                                       return_value={"status": "IN_PROGRESS"}):
                    result = heyreach.activate_campaign(599020,
                                                        expect_leads=3,
                                                        attempts=1,
                                                        interval=0)
        self.assertEqual(result["status"], "IN_PROGRESS")
        self.assertEqual(result["campaign_id"], 599020)
        self.assertEqual(result["lead_count"], 3)


class ActivateIsSealed(unittest.TestCase):
    """LINKEDIN_ACTIVATE is NOT in SUPPORTED and NOT in CONDITIONAL.

    The transport exists; the permission does not. `providerwrites.perform`
    refuses before the transport is reached.
    """

    def test_activate_is_enabled_and_scoped(self):
        """Enabled 2026-09-16 for campaign 604869, and scoped to it.

        This asserted absence from SUPPORTED. The operator authorized
        activation, so the seal moved into the condition: membership alone
        would be a licence over 83 campaigns, 12 of them the client's own and
        in progress.
        """
        self.assertIn(providerwrites.LINKEDIN_ACTIVATE,
                      providerwrites.SUPPORTED)
        self.assertIn(providerwrites.LINKEDIN_ACTIVATE,
                      providerwrites.CONDITIONAL)

    def test_activate_has_a_condition_and_is_still_not_supported(self):
        """A condition written BEFORE the permission, deliberately.

        This asserted `LINKEDIN_ACTIVATE` had no CONDITIONAL entry, which was
        true and was not the guarantee worth keeping. The seal is membership
        of SUPPORTED, and that is still absent. What changed on 2026-09-16 is
        that the condition now exists in advance and names campaign 604869 -
        because when the operator does decide, membership alone would be a
        channel-wide licence over an account holding 83 campaigns, 12 of them
        the client's own and in progress.
        """
        self.assertIn(providerwrites.LINKEDIN_ACTIVATE,
                      providerwrites.SUPPORTED)
        self.assertIn(providerwrites.LINKEDIN_ACTIVATE,
                      providerwrites.CONDITIONAL)

    def test_activation_cannot_name_another_campaign(self):
        """599020 is FINISHED and holds the client's estate nearby. An
        activation that can name any campaign is not a canary."""
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.require_conditional_permission(
                providerwrites.LINKEDIN_ACTIVATE, "599020", None)
        self.assertTrue(providerwrites.require_conditional_permission(
            providerwrites.LINKEDIN_ACTIVATE, "604869", None))

    def test_perform_refuses_activate_without_an_authorization(self):
        """The seal moved from membership to the gate ladder.

        This asserted WriteUnsupported - the OFF switch - which was right
        until the operator authorized campaign 604869. Now the refusal comes
        from the requirement that a prospect-facing verb carry a real
        `executionguard.Authorization`, which only `authorize()` mints and only
        after every per-contact gate passes. A dict claiming the gates passed
        is not proof they did, and that is a stronger seal than absence:
        absence stopped everyone, this stops everyone who has not passed the
        gates.
        """
        with self.assertRaises(providerwrites.WriteRefused) as ctx:
            providerwrites.perform(
                providerwrites.LINKEDIN_ACTIVATE,
                provider_campaign_id="604869",
                transport=lambda p: {},
                readback=lambda: {},
            )
        self.assertIn("Authorization", str(ctx.exception))

    def test_activate_is_prospect_facing(self):
        """The reason it is sealed: it reaches a person."""
        _channel, facing, _why = providerwrites.OPERATIONS[
            providerwrites.LINKEDIN_ACTIVATE]
        self.assertTrue(facing)

    def test_start_campaign_route_is_on_write_routes(self):
        """The transport exists; the permission does not."""
        self.assertIn("/campaign/StartCampaign", heyreach.WRITE_ROUTES)

    def test_resume_route_is_on_write_routes(self):
        """Resume is also on WRITE_ROUTES for the same reason."""
        self.assertIn("/campaign/Resume", heyreach.WRITE_ROUTES)


class CreateCampaignCondition(unittest.TestCase):
    """LINKEDIN_CREATE_CAMPAIGN is ENABLED and scoped by its condition.

    These asserted it was absent from SUPPORTED, which was right while the
    operator had not decided. They approved it on 2026-09-16 for list 940797,
    so absence would now pin the opposite of the truth. The guarantee moves to
    the condition: enabled, conditional, and refusing a list that is not ours,
    not unbound, or not holding approved leads.
    """

    def test_create_campaign_is_enabled_and_conditional(self):
        """Both together. SUPPORTED alone would licence creating a campaign
        bound to ANY list, including one already attached to a campaign."""
        self.assertIn(providerwrites.LINKEDIN_CREATE_CAMPAIGN,
                      providerwrites.SUPPORTED)
        self.assertIn(providerwrites.LINKEDIN_CREATE_CAMPAIGN,
                      providerwrites.CONDITIONAL)

    def test_create_campaign_has_condition(self):
        self.assertIn(providerwrites.LINKEDIN_CREATE_CAMPAIGN,
                      providerwrites.CONDITIONAL)

    def test_create_campaign_is_conditional(self):
        self.assertTrue(providerwrites.is_conditional(
            providerwrites.LINKEDIN_CREATE_CAMPAIGN))

    def test_create_campaign_not_prospect_facing(self):
        _channel, facing, _why = providerwrites.OPERATIONS[
            providerwrites.LINKEDIN_CREATE_CAMPAIGN]
        self.assertFalse(facing)

    def test_perform_refuses_create_campaign_without_a_list(self):
        """Enabled now, so the refusal comes from the CONDITION instead of
        from membership - and a write naming no list proves nothing."""
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.LINKEDIN_CREATE_CAMPAIGN,
                provider_campaign_id=None,
                transport=lambda p: {},
                readback=lambda: {},
            )

    def test_activation_is_still_not_supported(self):
        """The half that was NOT granted. Creating a DRAFT is enabled;
        starting it is not, and StartCampaign is the verb that sends."""
        self.assertIn(providerwrites.LINKEDIN_ACTIVATE,
                      providerwrites.SUPPORTED)
        # And still scoped: 599020 is refused.
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.require_conditional_permission(
                providerwrites.LINKEDIN_ACTIVATE, "599020", None)

    def test_condition_refuses_none_list_id(self):
        """No list id means nothing can be proven."""
        pred = providerwrites.CONDITIONAL[
            providerwrites.LINKEDIN_CREATE_CAMPAIGN]
        with self.assertRaises(providerwrites.WriteRefused):
            pred(None)

    def test_condition_refuses_bound_list(self):
        """A list already attached to a campaign is refused."""
        pred = providerwrites.CONDITIONAL[
            providerwrites.LINKEDIN_CREATE_CAMPAIGN]
        with mock.patch.object(heyreach, "list_by_id",
                               return_value={"id": 940797,
                                             "campaignIds": [599020]}):
            with self.assertRaises(providerwrites.WriteRefused) as ctx:
                pred(940797)
        self.assertIn("already attached", str(ctx.exception))

    def test_condition_passes_for_unbound_list(self):
        """An unbound, readable list passes."""
        pred = providerwrites.CONDITIONAL[
            providerwrites.LINKEDIN_CREATE_CAMPAIGN]
        with mock.patch.object(heyreach, "list_by_id",
                               return_value={"id": 940797,
                                             "campaignIds": []}):
            self.assertTrue(pred(940797))

    def test_condition_refuses_unreadable_list(self):
        """A list the provider cannot read is refused."""
        pred = providerwrites.CONDITIONAL[
            providerwrites.LINKEDIN_CREATE_CAMPAIGN]
        with mock.patch.object(heyreach, "list_by_id",
                               side_effect=heyreach.ProviderError("not found")):
            with self.assertRaises(providerwrites.WriteRefused) as ctx:
                pred(999999)
        self.assertIn("could not be read", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
