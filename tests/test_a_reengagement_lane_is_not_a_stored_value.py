"""ISSUE-017: the lane is a function of the row AND the campaign's status.

A stopped lead inside a RUNNING campaign is NEVER - "an unknown stop is a
NEVER by the rule". The same lead is REENGAGE once that campaign is archived,
because then the stop is the campaign's rather than the lead's.

So a lane written at walk time goes stale the moment a campaign archives. On
2026-09-22 the stored field read REENGAGE 0 / NEVER 1360 while the live answer
was REENGAGE 985 / NEVER 89, and a session trusting the stored value reported
the largest untouched supply in the estate as missing.

`report()` never trusted it. Everything else did, which is the defect.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import reengagement_inventory as ri                             # noqa: E402


LIVE = "active"
ARCHIVED = "archived"


def _row(**kw):
    row = {"provider": "emailbison", "campaign_id": 262, "lead_id": "1",
           "state": "sending_paused",
           "last_touch": "2026-05-01T00:00:00.000000Z"}
    row.update(kw)
    return row


class TheSameRowChangesLaneWithItsCampaign(unittest.TestCase):

    def test_stopped_inside_a_running_campaign_is_never(self):
        lane, why = ri.lane_for(_row(), campaign_status=LIVE)
        self.assertEqual(lane, ri.NEVER)
        self.assertIn("still running", why)

    def test_the_identical_row_is_reengage_once_archived(self):
        """The defect, in one assertion: same row, different answer."""
        lane, why = ri.lane_for(_row(), campaign_status=ARCHIVED)
        self.assertEqual(lane, ri.REENGAGE)
        self.assertIn("the stop is the campaign's", why)

    def test_no_status_reads_as_not_running_and_that_is_why_it_must_be_passed(self):
        """`lane_for(row)` with no status silently assumes the campaign is
        NOT live, which is how walk() wrote a lane it had no basis for."""
        self.assertEqual(ri.lane_for(_row())[0], ri.REENGAGE)
        self.assertEqual(ri.lane_for(_row(), campaign_status=LIVE)[0],
                         ri.NEVER)


class LanesNowIgnoresWhatWasStored(unittest.TestCase):

    def _inventory(self, rows):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", delete=False, encoding="utf-8", newline="\n")
        for row in rows:
            handle.write(json.dumps(row) + "\n")
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_a_stored_lane_that_disagrees_is_not_believed(self):
        path = self._inventory([
            _row(lane="NEVER", lane_at_walk="NEVER",
                 campaign_status_at_walk=LIVE)])
        rows, lanes = ri.lanes_now(statuses={"262": ARCHIVED}, path=path)
        self.assertEqual(lanes[ri.REENGAGE], 1)
        self.assertEqual(lanes[ri.NEVER], 0)
        self.assertEqual(rows[0]["lane"], ri.REENGAGE)

    def test_it_recomputes_the_other_way_too(self):
        """Not a rule that always says REENGAGE - the status decides."""
        path = self._inventory([_row(lane="REENGAGE")])
        _rows, lanes = ri.lanes_now(statuses={"262": LIVE}, path=path)
        self.assertEqual(lanes[ri.NEVER], 1)

    def test_a_campaign_missing_from_the_map_is_not_quietly_live(self):
        """A status map that does not name the campaign yields no status,
        which is the same as an archived read - and is exactly why an
        INCOMPLETE map must never be used. See the refusal below."""
        path = self._inventory([_row()])
        _rows, lanes = ri.lanes_now(statuses={}, path=path)
        self.assertEqual(lanes[ri.REENGAGE], 1)

    def test_unreadable_statuses_refuse_rather_than_over_count(self):
        """The old behaviour printed a warning and carried on. Its own
        warning said what that costs: every stop becomes the lead's own,
        which OVER-counts NEVER. A count nobody can trust is worse than a
        refusal because it looks like an answer."""
        path = self._inventory([_row()])
        original = ri.live_statuses
        ri.live_statuses = lambda: (_ for _ in ()).throw(
            RuntimeError("provider down"))
        self.addCleanup(setattr, ri, "live_statuses", original)
        with self.assertRaises(ri.StatusesUnreadable) as caught:
            ri.lanes_now(path=path)
        self.assertIn("over-counting", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
