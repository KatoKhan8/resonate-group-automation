"""TASK-234: the stop button refuses itself on the second press.

`scripts/nudge_487_scheduler.py` performed a pause on 2026-09-17T10:33:18Z
with payload ``{'campaign_id': 487}``. That recorded fingerprint
``c879dc1ddd133e34`` on the canonical row.

``material_fingerprint({'campaign_id': 487})`` recomputes to exactly that
value. So the NEXT pause of campaign 487 is refused as a repeat BEFORE the
transport is called, by ``providerwrites.perform``'s staging-repeat guard.

``orchestrator._perform_pause`` catches that into
``{'stopped': False, 'error': 'WriteRefused'}`` while ``pause()`` has
ALREADY set ``campaign['pause']`` and canonical status PAUSED.

So the emergency stop reports stopped and does not stop. Canonical state
says PAUSED, the provider is still sending, and the audit row's reason
string is stale and wrong.

The fix: declare ``repeatable`` in OPERATIONS so the staging-repeat guard
applies only to creating verbs.
"""
import unittest
from unittest import mock

from src import campaigns, orchestrator, providerwrites, store
from src.providers import bison
from tests.campaignbase import CampaignTest


class CallRecorder:
    """Records calls to a fake transport."""

    def __init__(self, status_after_pause="paused"):
        self.calls = []
        self.status_after_pause = status_after_pause

    def pause_campaign(self, provider_id):
        self.calls.append({"provider_id": provider_id})
        return {"ok": True}

    def campaign(self, provider_id):
        return {"status": self.status_after_pause, "id": provider_id}

    def readback_paused(self):
        return {"status": self.status_after_pause}


class StopButtonIsNotRefusedByItsOwnHistory(CampaignTest):
    """Requirement 1: an authorized emergency stop of a currently ACTIVE
    campaign must reach the provider, however many times the campaign has
    been paused before."""

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        self.campaign = self.make_campaign(recs, campaign_id="camp-stop")
        # Set status to running so pause is meaningful
        rows = campaigns.load()
        row = campaigns.get("camp-stop", rows)
        row["status"] = campaigns.RUNNING
        campaigns.save(rows)
        self.campaign = row
        self.recorder = CallRecorder()

    def _seed_fingerprint(self, operation, payload):
        """Simulate a prior pause having been recorded on the canonical row."""
        fp = providerwrites.material_fingerprint(payload)
        rows = campaigns.load()
        row = campaigns.get("camp-stop", rows)
        row.setdefault("provider_staged", {})[operation] = {
            "operation": operation,
            "fingerprint": fp,
            "at": "2026-09-17T10:33:18Z",
            "observed": {"status": "paused"},
        }
        campaigns.save(rows)

    def _get_provider_stop(self, campaign):
        """Extract provider_stop from the campaign's last pause event."""
        events = campaign.get("events") or []
        for entry in reversed(events):
            if entry.get("type") == "campaign_paused":
                return entry.get("provider_stop")
        return None

    @mock.patch.object(bison, "pause_campaign")
    @mock.patch.object(bison, "campaign")
    def test_a_pause_after_a_prior_pause_reaches_the_provider(
            self, mock_campaign, mock_pause):
        """The core defect: a pause whose payload fingerprints to the same
        value as a previously recorded pause must still reach the transport."""
        mock_pause.side_effect = self.recorder.pause_campaign
        mock_campaign.side_effect = self.recorder.campaign

        payload = {"campaign_id": self.campaign["bison_campaign_id"]}
        self._seed_fingerprint(providerwrites.EMAIL_PAUSE, payload)

        # Reload the campaign after seeding
        rows = campaigns.load()
        row = campaigns.get("camp-stop", rows)

        result = orchestrator.pause(row, why="emergency", by="U0DEMOADMIN1",
                                    provider=True)

        provider_stop = self._get_provider_stop(result) or {}
        email_stop = provider_stop.get("email", {})
        self.assertTrue(
            email_stop.get("stopped"),
            f"pause reported stopped=False: {email_stop}")
        self.assertGreater(
            len(self.recorder.calls), 0,
            "the transport was never called; the staging-repeat guard "
            "refused the pause before it reached the provider")

    @mock.patch.object(bison, "pause_campaign")
    @mock.patch.object(bison, "campaign")
    def test_repeated_pause_both_reach_the_provider(
            self, mock_campaign, mock_pause):
        """Requirement 2: two pauses in a row both reach the provider and
        both report truthfully. The second is a no-op at the provider and
        must NOT be reported as a refusal."""
        mock_pause.side_effect = self.recorder.pause_campaign
        mock_campaign.side_effect = self.recorder.campaign

        # First pause
        rows = campaigns.load()
        row = campaigns.get("camp-stop", rows)
        result1 = orchestrator.pause(row, why="first",
                                     by="U0DEMOADMIN1", provider=True)
        stop1 = self._get_provider_stop(result1) or {}
        email1 = stop1.get("email", {})
        self.assertTrue(email1.get("stopped"),
                        f"first pause failed: {email1}")
        first_call_count = len(self.recorder.calls)
        self.assertGreater(first_call_count, 0,
                           "first pause did not reach the provider")

        # Reset to running so the second pause is meaningful
        rows = campaigns.load()
        row = campaigns.get("camp-stop", rows)
        row["status"] = campaigns.RUNNING
        row["pause"] = None
        campaigns.save(rows)

        # Second pause - same payload, must NOT be refused
        rows = campaigns.load()
        row = campaigns.get("camp-stop", rows)
        result2 = orchestrator.pause(row, why="second",
                                     by="U0DEMOADMIN1", provider=True)
        stop2 = self._get_provider_stop(result2) or {}
        email2 = stop2.get("email", {})
        self.assertTrue(email2.get("stopped"),
                        f"second pause was refused: {email2}")
        self.assertGreater(
            len(self.recorder.calls), first_call_count,
            "second pause did not reach the provider; the staging-repeat "
            "guard refused it")

    @mock.patch.object(bison, "pause_campaign")
    @mock.patch.object(bison, "campaign")
    def test_pause_after_resume_reaches_the_provider(
            self, mock_campaign, mock_pause):
        """Requirement 3: pause, resume, pause again. The third act reaches
        the provider.

        This test drives through perform() directly because orchestrator.resume
        requires campaign validation that is orthogonal to the defect."""
        mock_pause.side_effect = self.recorder.pause_campaign
        mock_campaign.side_effect = self.recorder.campaign

        payload = {"campaign_id": self.campaign["bison_campaign_id"]}

        # First pause via perform directly
        providerwrites.perform(
            providerwrites.EMAIL_PAUSE,
            campaign="camp-stop",
            payload=payload,
            transport=self.recorder.pause_campaign,
            readback=self.recorder.readback_paused,
            expected={"status": "paused"})
        first_call_count = len(self.recorder.calls)
        self.assertEqual(first_call_count, 1)

        # Second pause with same payload - simulates pause after resume
        # because the payload is identical
        rows = campaigns.load()
        row = campaigns.get("camp-stop", rows)
        row["status"] = campaigns.RUNNING
        campaigns.save(rows)

        providerwrites.perform(
            providerwrites.EMAIL_PAUSE,
            campaign="camp-stop",
            payload=payload,
            transport=self.recorder.pause_campaign,
            readback=self.recorder.readback_paused,
            expected={"status": "paused"})
        self.assertGreater(
            len(self.recorder.calls), first_call_count,
            "second pause did not reach the provider")

    def test_ambiguous_provider_response_not_recorded_as_stopped(self):
        """Requirement 5: a 200 whose readback does not confirm paused must
        NOT be recorded as stopped. Fail closed."""
        observed = {"status": "active"}
        expected = {"status": "paused"}
        verdict = providerwrites._classify(observed, expected)
        self.assertNotEqual(verdict, providerwrites.ACCEPTED,
                            "a readback that disagrees with expected was "
                            "classified as ACCEPTED")

    def test_provider_disagreement_is_detectable(self):
        """Requirement 7: canonical says PAUSED, provider says active - must
        be detectable. A function that answers it is enough."""
        observed = {"status": "active"}
        expected = {"status": "paused"}
        verdict = providerwrites._classify(observed, expected)
        self.assertEqual(verdict, providerwrites.DRIFTED)


class CreatingVerbsAreNotRepeatable(CampaignTest):
    """The staging-repeat guard must still protect creating verbs.

    A create-campaign whose payload fingerprints to the same value as a
    previously recorded create must still be refused - creating the same
    campaign twice builds a second provider campaign.
    """

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        self.campaign = self.make_campaign(recs, campaign_id="camp-create")
        self._restore = providerwrites.SUPPORTED
        self.addCleanup(setattr, providerwrites, "SUPPORTED", self._restore)
        providerwrites.SUPPORTED = (providerwrites.EMAIL_CREATE_CAMPAIGN,)

    def test_a_second_create_with_the_same_payload_is_refused(self):
        """Creating verbs must still be deduplicated by the staging guard."""
        payload = {"name": "test-campaign"}
        calls = []

        def transport(p):
            calls.append(p)
            return {"id": "9001", "name": "test-campaign"}

        def readback():
            return {"name": "test-campaign"}

        # First create succeeds
        providerwrites.perform(
            providerwrites.EMAIL_CREATE_CAMPAIGN,
            campaign="camp-create",
            payload=payload,
            transport=transport,
            readback=readback,
            expected={"name": "test-campaign"})
        self.assertEqual(len(calls), 1)

        # Second create with same payload is refused
        with self.assertRaises(providerwrites.WriteRefused):
            providerwrites.perform(
                providerwrites.EMAIL_CREATE_CAMPAIGN,
                campaign="camp-create",
                payload=payload,
                transport=transport,
                readback=readback,
                expected={"name": "test-campaign"})


if __name__ == "__main__":
    unittest.main()
