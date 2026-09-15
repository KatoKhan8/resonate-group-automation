#!/usr/bin/env python3
"""TASK-125: a lead may be added to a campaign that cannot send.

The predicate `heyreach.campaign_cannot_send` reads the campaign status from
the provider and returns True only when the campaign demonstrably cannot send
(DRAFT or FINISHED). A campaign that can send (IN_PROGRESS or PAUSED) returns
False. An unreadable campaign raises.

PAUSED is the interesting case. A paused campaign can be resumed at any moment
by a human pressing a button, so leads added to it sit waiting for the resume.
That is prospect-facing risk: the sequence acts on those leads the moment
somebody resumes. PAUSED therefore counts as "can send" and adding leads to
a paused campaign is refused.

The predicate is integrated into `ensure_leads` as gate 6, immediately before
the provider write. A campaign that can send refuses the whole push.
"""
import unittest
from unittest import mock

from src.providers import heyreach
from src import providerwrites


class ThePredicateReadsProviderTruth(unittest.TestCase):
    """campaign_cannot_send reads from the provider, not from local state."""

    def test_draft_cannot_send(self):
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "DRAFT",
                                             "startedAt": None}):
            self.assertTrue(heyreach.campaign_cannot_send(599020))

    def test_finished_is_not_proven_safe(self):
        """A campaign that has run once is not proven inert for a new lead."""
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "FINISHED",
                                             "startedAt": "2026-09-01"}):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.campaign_cannot_send(599020)

    def test_in_progress_can_send(self):
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "IN_PROGRESS",
                                             "startedAt": "2026-09-01"}):
            self.assertFalse(heyreach.campaign_cannot_send(599020))

    def test_paused_can_send(self):
        """PAUSED can be resumed, so leads added to it sit waiting.

        This is the argument the task asked for: a paused campaign is not
        sending RIGHT NOW, but it can be resumed at any moment by a human
        pressing a button. Leads added to it are in the queue for that
        resume. The window between adding and resuming is unpredictable,
        and the leads will be acted on immediately when it happens.

        That is prospect-facing risk, the same class as IN_PROGRESS.
        """
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "PAUSED",
                                             "startedAt": "2026-09-01"}):
            self.assertFalse(heyreach.campaign_cannot_send(599020))


class ThePredicateFailsClosed(unittest.TestCase):
    """If the status cannot be read, the answer is refuse, not proceed."""

    def test_missing_campaign_refuses(self):
        with mock.patch.object(heyreach, "campaign_read",
                               return_value=None):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.campaign_cannot_send(599020)

    def test_missing_status_field_refuses(self):
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"id": 599020, "status": ""}):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.campaign_cannot_send(599020)

    def test_none_status_refuses(self):
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"id": 599020, "status": None}):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.campaign_cannot_send(599020)

    def test_unrecognised_status_refuses(self):
        """A status not in the known set is not proven safe."""
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "SCHEDULED"}):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.campaign_cannot_send(599020)

    def test_provider_error_propagates(self):
        """A provider read failure is not caught and defaulted to safe."""
        with mock.patch.object(heyreach, "campaign_read",
                               side_effect=heyreach.ProviderError("timeout")):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.campaign_cannot_send(599020)


class TheGateRefusesACampaignThatCanSend(unittest.TestCase):
    """ensure_leads refuses when the campaign can send, immediately before
    the write. Not at planning time - at the moment of the push."""

    def _campaign_row(self, heyreach_campaign_id=599020):
        return {
            "campaign_id": "test-1",
            "client": "productive",
            "heyreach_campaign_id": heyreach_campaign_id,
            "senders": {"linkedin": [{"provider_account_id": "116968"}]},
            "cadence": "productive_balanced_v1",
            "provider_staged": {},
        }

    @staticmethod
    def _mock_early_gates(declared=True):
        """Mock gates 1-5 so the test reaches gate 6.

        Provides one pushable contact so the function reaches the write path
        where gate 6 lives.
        """
        from src import campaigns as _campaigns, killswitch, collision
        from src import heyreachfactory
        from src.providers import bison as _bison

        pushable = [{"record_id": "rec-1", "contact_key": "rec-1-c1",
                      "custom_fields": {}}]

        return [
            # Gate 6 asks the write door's condition, which is
            # RESEALED in production - the vendor activates a campaign
            # the moment a lead is added. These tests are about the
            # gates underneath that, and `TheResealHolds` pins what
            # production does.
            mock.patch.object(providerwrites,
                              "CAMPAIGN_LEVEL_STAGING_IS_PROVEN",
                              True),
            mock.patch.object(_campaigns, "load", return_value=[]),
            mock.patch.object(_campaigns, "require",
                              return_value={
                                  "campaign_id": "test-1",
                                  "client": "productive",
                                  "heyreach_campaign_id": 599020,
                                  # THE STAGING DECLARATION. Gate 6 asks the
                                  # same condition the write door asks: our
                                  # declared campaign, PAUSED at the provider,
                                  # read live. `declared=False` strips it, to
                                  # make a campaign nobody declared - which is
                                  # what the client's own 83 look like.
                                  **({"provider_status_expected": "PAUSED",
                                      "provider_note": "{connection_note}",
                                      "provider_actions":
                                          ["CHECK_IS_CONNECTION",
                                           "MESSAGE"]} if declared else {}),
                                  "senders": {"linkedin": [
                                      {"provider_account_id": "116968"}]},
                                  "cadence": "productive_balanced_v1",
                                  "provider_staged": {},
                              }),
            mock.patch.object(killswitch, "workspace_state",
                              return_value={"sending": True,
                                            "why": "test override"}),
            mock.patch.object(heyreachfactory, "_plan",
                              return_value={"pushable": pushable,
                                            "sequence": {}}),
            mock.patch.object(_bison, "bound_workspace",
                              return_value={"id": 10}),
            mock.patch.object(collision, "check_account",
                              return_value={"domain": "example.com",
                                            "verdict": "clear"}),
            mock.patch.object(heyreach, "readback_membership",
                              return_value={"found": set(), "missing": set(),
                                            "total": 0, "per_lead": []}),
        ]

    @staticmethod
    def _recs():
        """One record with a LinkedIn URL, matching the pushable contact."""
        return [{"id": "rec-1", "client": "productive",
                 "domain": "example.com", "company": "Example",
                 "state": "ready",
                 "contacts": [{"key": "rec-1-c1",
                               "linkedin": "https://linkedin.com/in/test"}]}]

    def test_in_progress_campaign_refuses_the_push(self):
        """A campaign that is IN_PROGRESS cannot receive leads safely."""
        from src import eligibility
        from src.heyreachfactory import ensure_leads, FactoryRefused

        patches = self._mock_early_gates()
        patches.append(mock.patch.object(
            heyreach, "campaign_read",
            return_value={"id": 599020, "status": "IN_PROGRESS",
                          "campaignAccountIds": [174892],
                          "organizationUnitId": "174892"}))
        patches.append(mock.patch.object(eligibility, "must_not_contact",
                                         return_value=[]))
        for p in patches:
            p.start()
        try:
            with self.assertRaises(FactoryRefused) as ctx:
                ensure_leads("test-1", recs=self._recs(), live=True)
            self.assertIn("not PAUSED", str(ctx.exception))
        finally:
            for p in patches:
                p.stop()

    def test_a_paused_campaign_nobody_declared_refuses_the_push(self):
        """INVERTED 2026-09-15, and the inversion is the point.

        This read "a PAUSED campaign can be resumed, so it refuses too" -
        correct while DRAFT was the staging state, and unsatisfiable the
        moment the provider proved otherwise: AddLeadsToCampaignV2 answers 400
        on a DRAFT campaign, so a stageable campaign is necessarily one that
        has been started and paused.

        PAUSED is admitted now - but ONLY for a campaign this deployment
        declared, bound to this exact provider id. The client's account holds
        83 campaigns and paused is a common state among them; being paused is
        not a permission. So the counterfactual moves rather than disappearing.
        """
        from src import eligibility
        from src.heyreachfactory import ensure_leads, FactoryRefused

        patches = self._mock_early_gates(declared=False)
        patches.append(mock.patch.object(
            heyreach, "campaign_read",
            return_value={"id": 599020, "status": "PAUSED",
                          "campaignAccountIds": [174892],
                          "organizationUnitId": "174892"}))
        patches.append(mock.patch.object(eligibility, "must_not_contact",
                                         return_value=[]))
        for p in patches:
            p.start()
        try:
            with self.assertRaises(FactoryRefused) as ctx:
                ensure_leads("test-1", recs=self._recs(), live=True)
            self.assertIn("declares provider_status_expected",
                          str(ctx.exception))
        finally:
            for p in patches:
                p.stop()

    def test_unreadable_campaign_refuses_the_push(self):
        """A campaign whose status cannot be read is not proven safe."""
        from src import eligibility
        from src.heyreachfactory import ensure_leads

        from src.heyreachfactory import FactoryRefused

        patches = self._mock_early_gates()
        # The READ is what fails now, not the predicate: gate 6 asks the write
        # door's condition, which reads the campaign from the provider. An
        # unreadable campaign is not a paused one, and a timeout is not a
        # permission - so it refuses rather than propagating, and the refusal
        # names the read.
        patches.append(mock.patch.object(heyreach, "campaign_read",
                                         side_effect=heyreach.ProviderError(
                                             "timeout")))
        patches.append(mock.patch.object(eligibility, "must_not_contact",
                                         return_value=[]))
        for p in patches:
            p.start()
        try:
            with self.assertRaises(FactoryRefused) as ctx:
                ensure_leads("test-1", recs=self._recs(), live=True)
            self.assertIn("could not be established", str(ctx.exception))
        finally:
            for p in patches:
                p.stop()


class TheGateIsCheckedImmediatelyBeforeTheWrite(unittest.TestCase):
    """The check is not cached from planning time. It fires at the write."""

    def test_the_gate_fires_after_the_dry_run_check(self):
        """A dry run does not trigger the gate; only live=True does.

        The gate is between the dry-run return and the provider write. A dry
        run reports what WOULD happen; it does not need the campaign status.
        """
        from src import campaigns as _campaigns, killswitch, eligibility
        from src import collision, heyreachfactory
        from src.providers import bison as _bison
        from src.heyreachfactory import ensure_leads

        pushable = [{"record_id": "rec-1", "contact_key": "rec-1-c1",
                      "custom_fields": {}}]
        recs = [{"id": "rec-1", "client": "productive",
                 "domain": "example.com", "company": "Example",
                 "state": "ready",
                 "contacts": [{"key": "rec-1-c1",
                               "linkedin": "https://linkedin.com/in/test"}]}]

        campaign_read_called = []

        def tracking(*a, **kw):
            campaign_read_called.append(True)
            return True

        with mock.patch.object(_campaigns, "load", return_value=[]), \
             mock.patch.object(_campaigns, "require",
                               return_value={
                                   "campaign_id": "test-1",
                                   "client": "productive",
                                   "heyreach_campaign_id": 599020,
                                   # The staging declaration, which gate 6
                                   # reads through the write door's own
                                   # condition.
                                   "provider_status_expected": "PAUSED",
                                   "provider_note": "{connection_note}",
                                   "provider_actions": [
                                       "CHECK_IS_CONNECTION", "MESSAGE"],
                                   "senders": {"linkedin": [
                                       {"provider_account_id": "116968"}]},
                                   "cadence": "productive_balanced_v1",
                                   "provider_staged": {},
                               }), \
             mock.patch.object(killswitch, "workspace_state",
                               return_value={"sending": True,
                                             "why": "test override"}), \
             mock.patch.object(heyreachfactory, "_plan",
                               return_value={"pushable": pushable,
                                             "sequence": {}}), \
             mock.patch.object(_bison, "bound_workspace",
                               return_value={"id": 10}), \
             mock.patch.object(collision, "check_account",
                               return_value={"domain": "example.com",
                                             "verdict": "clear"}), \
             mock.patch.object(heyreach, "readback_membership",
                               return_value={"found": set(), "missing": set(),
                                             "total": 0, "per_lead": []}), \
             mock.patch.object(eligibility, "must_not_contact",
                               return_value=[]), \
             mock.patch.object(heyreach, "campaign_cannot_send", tracking):
            ensure_leads("test-1", recs=recs, live=False)
        self.assertEqual(campaign_read_called, [],
                         "the campaign status was read during a dry run; "
                         "the gate should only fire for live=True")


class TheNarrowedSeals(unittest.TestCase):
    """The seals now assert that add_lead is refused for a campaign that CAN
    send, and permitted only for one proven not to.

    These replace the old seals that asserted add_lead is NEVER supported.
    The new seals assert something STRONGER: that the permission is
    conditional on the campaign's status, and that the condition is checked.
    """

    def test_add_lead_is_refused_for_an_in_progress_campaign(self):
        """The predicate returns False for IN_PROGRESS."""
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "IN_PROGRESS"}):
            self.assertFalse(heyreach.campaign_cannot_send(1))

    def test_add_lead_is_refused_for_a_paused_campaign(self):
        """The predicate returns False for PAUSED.

        Counterfactual: if this returned True, leads would sit in a paused
        campaign waiting for the resume button. Break the guard (change
        PAUSED to return True) and this test fails - proving the guard is
        connected to the outcome.
        """
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "PAUSED"}):
            self.assertFalse(heyreach.campaign_cannot_send(1))

    def test_add_lead_is_permitted_only_for_a_proven_draft(self):
        """The predicate returns True for DRAFT."""
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "DRAFT",
                                             "startedAt": None}):
            self.assertTrue(heyreach.campaign_cannot_send(1))

    def test_add_lead_is_refused_for_finished(self):
        """NARROWED BY CLAUDE 2026-09-15. This asserted FINISHED was safe.

        "Finished" describes the leads already in the campaign - they have
        completed the sequence. It says nothing about what the campaign does
        with a lead added AFTERWARDS, and nothing readable from this provider
        proves it would sit inert. The same argument that correctly excluded
        PAUSED excludes FINISHED, and the first version applied it to only
        one of them.
        """
        # It REFUSES rather than returning False, which is louder and is the
        # fail-closed design: an unproven status raises instead of quietly
        # answering "not safe" somewhere a caller might ignore.
        with mock.patch.object(heyreach, "campaign_read",
                               return_value={"status": "FINISHED"}):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.campaign_cannot_send(1)

    def test_the_refusal_fires_when_the_status_read_fails(self):
        """A timeout is not a DRAFT. The refusal fires."""
        with mock.patch.object(heyreach, "campaign_read",
                               side_effect=heyreach.ProviderError("timeout")):
            with self.assertRaises(heyreach.ProviderError):
                heyreach.campaign_cannot_send(1)


class CounterfactualEvidence(unittest.TestCase):
    """Break the guard, confirm the intended test fails for the intended
    reason. Each test here demonstrates that the predicate is load-bearing."""

    def test_removing_the_paused_check_would_allow_paused_campaigns(self):
        """If PAUSED were in _STATUSES_THAT_CANNOT_SEND, a paused campaign
        would pass the gate. This test proves the guard is connected."""
        self.assertNotIn("PAUSED", heyreach._STATUSES_THAT_CANNOT_SEND,
                         "PAUSED must not be in the cannot-send set; "
                         "a paused campaign can be resumed")

    def test_the_known_statuses_are_exhaustive(self):
        """Every status the provider uses is accounted for.

        If the provider adds a new status, the predicate refuses it rather
        than silently treating it as safe. The unrecognised-status test
        above proves this; this test names the set.
        """
        known = {heyreach.DRAFT, heyreach.IN_PROGRESS,
                 heyreach.PAUSED, heyreach.FINISHED}
        cannot = set(heyreach._STATUSES_THAT_CANNOT_SEND)
        can = known - cannot
        # DRAFT alone, and the shortness of that list is the point: it is the
        # only status that proves the campaign has never acted on anything.
        self.assertEqual(cannot, {heyreach.DRAFT})
        self.assertEqual(
            can, {heyreach.IN_PROGRESS, heyreach.PAUSED, heyreach.FINISHED})


if __name__ == "__main__":
    unittest.main()
