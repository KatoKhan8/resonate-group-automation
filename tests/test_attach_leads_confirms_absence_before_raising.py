"""ISSUE-016: a readback that is exact but not immediately consistent.

`attach_leads` posts, then reads the named leads back. The provider accepts
the attach and then takes a moment to show it on the membership route, so the
first read reported leads absent that were present. Measured three times in
one batch on 2026-09-22: campaign 493 raised "2 of 22", 494 raised "60 of 77"
and 492 raised "157 of 206" - and all three writes had succeeded, holding 22,
76 and 206 leads respectively when read again seconds later.

The failure direction is the expensive one. A refusal on a write that worked
invites a re-run and reports zero enrolled for a campaign that has just taken
176 leads. So absence is confirmed rather than assumed on first read.
"""
import unittest
from unittest import mock

from src import providers
from src.providers import bison


class AbsenceIsConfirmedNotAssumed(unittest.TestCase):

    WANTED = [1, 2, 3]

    def test_a_lead_visible_on_the_second_read_does_not_raise(self):
        """The defect itself: present, just not yet."""
        with mock.patch.object(bison, "membership",
                               side_effect=[[], [], self.WANTED]), \
             mock.patch.object(bison, "_post", return_value=(200, {})), \
             mock.patch.object(bison, "campaign_lead_count", return_value=3), \
             mock.patch("time.sleep", return_value=None):
            out = bison.attach_leads(7, self.WANTED)
        self.assertEqual(sorted(out["members"]), self.WANTED)

    def test_a_lead_that_never_appears_still_raises(self):
        """The guard is not weakened - it just asks more than once."""
        never = [[] for _ in range(bison.ATTACH_READBACK_ATTEMPTS + 1)]
        with mock.patch.object(bison, "membership", side_effect=never), \
             mock.patch.object(bison, "_post", return_value=(200, {})), \
             mock.patch.object(bison, "campaign_lead_count", return_value=0), \
             mock.patch("time.sleep", return_value=None):
            with self.assertRaises(providers.ProviderError) as caught:
                bison.attach_leads(7, self.WANTED)
        self.assertIn("are not in campaign 7", str(caught.exception))
        self.assertIn("readbacks", str(caught.exception))

    def test_it_stops_reading_as_soon_as_they_are_all_there(self):
        """A write that is visible at once costs exactly one extra read."""
        reads = []

        def _membership(campaign_id, lead_ids=None):
            reads.append(1)
            return [] if len(reads) == 1 else list(self.WANTED)

        with mock.patch.object(bison, "membership", side_effect=_membership), \
             mock.patch.object(bison, "_post", return_value=(200, {})), \
             mock.patch.object(bison, "campaign_lead_count", return_value=3), \
             mock.patch("time.sleep", return_value=None):
            bison.attach_leads(7, self.WANTED)
        # one `before` read, one `after` read: no polling needed
        self.assertEqual(len(reads), 2)

    def test_nothing_is_posted_when_every_lead_is_already_there(self):
        """Unchanged: idempotent, and it writes nothing on a repeat."""
        with mock.patch.object(bison, "membership",
                               return_value=list(self.WANTED)), \
             mock.patch.object(bison, "_post") as post, \
             mock.patch.object(bison, "campaign_lead_count", return_value=3):
            out = bison.attach_leads(7, self.WANTED)
        post.assert_not_called()
        self.assertEqual(out["already"], self.WANTED)


if __name__ == "__main__":
    unittest.main()
