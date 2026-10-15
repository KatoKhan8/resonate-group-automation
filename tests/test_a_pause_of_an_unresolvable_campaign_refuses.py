"""The pause executor does not route around the write guard.

`orchestrator._perform_pause` is what actually stops a provider campaign:
it wraps `bison.pause_campaign` in the transport contract and hands it to
`providerwrites.perform`, whose ownership guard refuses any write to a
campaign nothing positively records as ours. The property here is that
the executor propagates that refusal: for a campaign whose canonical row
binds no provider campaign, `_perform_pause` raises rather than catching,
retrying, or falling back to calling the provider directly.

`_pause_at_provider` deliberately catches everything and classifies it
into the pause outcome precisely so a provider failure cannot block the
local stop - which means nothing else on this path would notice an
executor that swallowed refusals. A swallowed refusal would read as
`{"stopped": True}` in the campaign's event log while the vendor campaign
ran on.

The fixture campaign binds nothing (`external=False`) and the executor is
asked to pause provider campaign 555, which no ledger row records. The
refusal happens before any transport - its text says so, and this
inherits the provider test base whose recorder would witness a real call.
"""
import unittest

from src import orchestrator, providerwrites
from tests.campaignbase import CampaignTest


class APauseOfAnUnresolvableCampaignRefuses(CampaignTest):

    def setUp(self):
        super().setUp()
        recs = self.seed_records()
        # external=False: the canonical row binds no provider campaign, so
        # the ledger cannot resolve a destination for any pause of it.
        self.campaign = self.make_campaign(recs, campaign_id="camp-none",
                                           external=False)

    def test_the_refusal_propagates_before_any_transport(self):
        with self.assertRaises(providerwrites.WriteRefused) as raised:
            orchestrator._perform_pause(
                providerwrites.EMAIL_PAUSE, "email", self.campaign,
                "555", "glm-test")
        refusal = str(raised.exception)
        self.assertIn(
            "names no provider campaign this guard can resolve", refusal,
            "the guard must say it cannot resolve the destination, not a "
            f"generic refusal: {refusal}")
        self.assertIn(
            "The transport was not reached", refusal,
            "the refusal must state the transport was never reached, so a "
            "reader can tell refusal from provider failure")


if __name__ == "__main__":
    unittest.main()
