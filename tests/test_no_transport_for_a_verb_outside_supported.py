"""The single door: no transport for a verb outside SUPPORTED.

`providerwrites.perform` is the only route to a provider write, and
`require_supported` is its cheapest and most decisive refusal: a verb not in
`SUPPORTED` never reaches the transport. Nothing else in `perform` re-asks
that question - the ownership, condition and staging guards all ASSUME the
verb is admitted and only narrow which campaign it may touch - so this one
membership check is what keeps every sealed verb out of the world, most
urgently `EMAIL_ACTIVATE`, which starts real sends and is out of `SUPPORTED`
for exactly that reason.

The property is not "an exception is raised". It is that the transport is
never CALLED: a door that refuses after touching the provider would be no
door. The witness is an injected recorder, so a broken guard is caught at
the call rather than by whichever refusal might have fired afterwards.

`LINKEDIN_RESUME` is the honest probe. It is declared in `OPERATIONS` (so
`describe` passes), not prospect-facing (so the Authorization branch cannot
fire first), carries no `CONDITIONAL` entry, is not `REPEATABLE`, and is not
in `SUPPORTED` - sealed with no route at all ("Pause is what lifts it.
Resume comes after, or not at all"). The fixture campaign binds
`heyreach_campaign_id` in its canonical row, so under a broken guard the
flow runs past ownership to the recorder instead of being stopped by a
different guard first.
"""
import unittest

from src import providerwrites
from tests.campaignbase import CampaignTest


class Recorder:
    """The transport witness. If the door opens, this records it."""

    def __init__(self):
        self.calls = []

    def __call__(self, payload):
        self.calls.append(payload)
        return {"ok": True}


class NoTransportForAVerbOutsideSupported(CampaignTest):

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        # external=True binds heyreach_campaign_id=7001 on the canonical row,
        # so ownership classifies the destination as resonate_os and a broken
        # SUPPORTED guard - not the ownership guard - is what lets the call
        # through.
        self.make_campaign(recs, campaign_id="camp-door")

    def test_the_transport_is_never_called(self):
        recorder = Recorder()
        refusal = None
        try:
            providerwrites.perform(
                providerwrites.LINKEDIN_RESUME,
                campaign="camp-door",
                provider_campaign_id="7001",
                payload={"campaign_id": 7001},
                transport=recorder,
                readback=lambda: {"status": "IN_PROGRESS"},
                expected={"status": "IN_PROGRESS"})
        except providerwrites.WriteUnsupported as e:
            refusal = str(e)
        self.assertIsNotNone(
            refusal,
            "perform() returned for a verb outside SUPPORTED instead of "
            "refusing")
        self.assertIn("heyreach.resume", refusal)
        self.assertIn("is not supported in this build", refusal)
        self.assertEqual(
            recorder.calls, [],
            "a verb outside SUPPORTED reached the transport: "
            f"{recorder.calls}")


if __name__ == "__main__":
    unittest.main()
