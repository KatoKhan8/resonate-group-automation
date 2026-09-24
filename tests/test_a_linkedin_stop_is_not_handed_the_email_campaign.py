"""A contact on both channels must not have its LinkedIn stop resolved to the
email campaign.

`_campaign_of` returned the FIRST campaign row holding the record, whatever
channel that row was for. A record in an email row and a HeyReach row would
hand `stop_linkedin_contact` the email row, which names no
`heyreach_campaign_id`, and the stop raised StopRefused about a lead that was
perfectly stoppable through the row sitting later in the same list.

Latent on 2026-09-24 - zero of 1,582 records sat in both - and the 825
enrollment across 33 seats is the plan that creates the first ones. It is
also the plan gated on the cross-channel stop working, which is why this is
pinned now rather than after.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import leadstop                                        # noqa: E402


REC = {"id": "r1", "client": "productive",
       "contacts": [{"key": "c1", "email": "c@example.com",
                     "linkedin": "https://www.linkedin.com/in/c",
                     "bison_lead_id": 1, "heyreach_lead_id": 2}]}

# The email row comes FIRST, which is the ordering that produced the defect.
ROWS = [
    {"campaign_id": "email-row", "client": "productive",
     "bison_campaign_id": 491, "record_ids": ["r1"]},
    {"campaign_id": "linkedin-row", "client": "productive",
     "heyreach_campaign_id": 613744, "record_ids": ["r1"]},
]


class TestTheChannelDecidesTheCampaign(unittest.TestCase):

    def test_the_linkedin_stop_resolves_the_heyreach_row(self):
        got = leadstop._campaign_of(REC, ROWS,
                                    requires="heyreach_campaign_id")
        self.assertIsNotNone(
            got, "no row resolved for the LinkedIn channel at all")
        # THE EFFECT, NOT THE NAME: what the caller needs is a usable
        # heyreach_campaign_id. Asserting on campaign_id would still pass if
        # the field it is fetched for were absent.
        self.assertEqual(got.get("heyreach_campaign_id"), 613744)

    def test_the_email_stop_still_resolves_the_bison_row(self):
        got = leadstop._campaign_of(REC, ROWS, requires="bison_campaign_id")
        self.assertIsNotNone(got)
        self.assertEqual(got.get("bison_campaign_id"), 491)

    def test_the_linkedin_row_is_found_even_when_the_email_row_is_first(self):
        """The ordering guard. ROWS is deliberately email-first; reversing it
        must not change the answer, or the pass is an accident of order."""
        forward = leadstop._campaign_of(REC, ROWS,
                                        requires="heyreach_campaign_id")
        backward = leadstop._campaign_of(REC, list(reversed(ROWS)),
                                         requires="heyreach_campaign_id")
        self.assertEqual(forward.get("heyreach_campaign_id"),
                         backward.get("heyreach_campaign_id"))

    def test_no_usable_row_still_refuses(self):
        """Skipping must not invent a campaign. With no HeyReach row at all
        the answer is still None, so the caller refuses exactly as before."""
        self.assertIsNone(
            leadstop._campaign_of(REC, ROWS[:1],
                                  requires="heyreach_campaign_id"))

    def test_requires_none_keeps_the_old_channel_blind_behaviour(self):
        """Callers that genuinely want any row are unchanged."""
        self.assertEqual(
            leadstop._campaign_of(REC, ROWS).get("campaign_id"), "email-row")


if __name__ == "__main__":
    unittest.main()
