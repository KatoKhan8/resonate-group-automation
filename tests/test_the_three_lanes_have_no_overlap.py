#!/usr/bin/env python3
"""NEVER, REENGAGE, REVIVE: three lanes, by rule, no overlap.

TASK-247.  The classifier is TOTAL: every lead lands in exactly one of
NEVER, REENGAGE, REVIVE, ACTIVE or UNKNOWN.  No lead falls through.  No
lead lands in two.

Required tests:
- totality over a fixture estate (every lead gets exactly one lane)
- precedence, one test per pair that can collide
- a lead in an active sequence is untouched by every rule
- the 20/day cap queues rather than drops
- the same lead is never posted twice
- UNKNOWN holds and is counted
"""
import unittest

from src.reengagement import (
    ACTIVE, LANES, NEVER, REENGAGE, REVIVE, UNKNOWN,
    ReviveQueue, classify, classify_all, lane_counts,
)


def _lead(**overrides):
    """A lead fixture with sensible defaults.  Override anything."""
    base = {
        "lead_id": overrides.pop("lead_id", "lead-001"),
        "has_unsubscribe": False,
        "has_bounce": False,
        "has_negative_reply": False,
        "stop_reason": None,
        "in_active_sequence": False,
        "has_reply": False,
        "reply_kind": None,
        "reply_at": None,
        "sequence_finished": False,
        "last_touch_days": None,
        "connected_linkedin": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------- totality

class TotalityTests(unittest.TestCase):
    """Every lead gets exactly one lane.  No lead falls through."""

    def test_every_lead_gets_exactly_one_lane(self):
        """A fixture estate of twelve leads, every one classified once."""
        estate = [
            _lead(lead_id="unsub", has_unsubscribe=True),
            _lead(lead_id="bounced", has_bounce=True),
            _lead(lead_id="neg-reply", has_negative_reply=True),
            _lead(lead_id="unknown-stop", stop_reason="still_unknown"),
            _lead(lead_id="active", in_active_sequence=True),
            _lead(lead_id="revive-pos", has_reply=True,
                  reply_kind="positive", reply_at="2026-01-15T10:00:00Z"),
            _lead(lead_id="revive-neu", has_reply=True,
                  reply_kind="neutral", reply_at="2026-02-20T10:00:00Z"),
            _lead(lead_id="reengage", sequence_finished=True,
                  last_touch_days=120),
            _lead(lead_id="unknown-young", sequence_finished=True,
                  last_touch_days=30),
            _lead(lead_id="unknown-no-seq"),
            _lead(lead_id="unknown-no-touch", sequence_finished=True),
            _lead(lead_id="clean-slate"),
        ]
        results = classify_all(estate)
        self.assertEqual(len(results), 12)
        for lid, entry in results.items():
            self.assertIn(entry["lane"], LANES,
                          f"{lid} got unknown lane {entry['lane']!r}")

    def test_no_lead_falls_through(self):
        """Every input lead_id appears in the output."""
        estate = [
            _lead(lead_id="a"),
            _lead(lead_id="b", has_reply=True, reply_at="2026-01-01T00:00:00Z"),
            _lead(lead_id="c", sequence_finished=True, last_touch_days=200),
        ]
        results = classify_all(estate)
        self.assertEqual(set(results.keys()), {"a", "b", "c"})

    def test_no_lead_lands_in_two_lanes(self):
        """Classifying the same lead twice gives the same answer."""
        lead = _lead(has_reply=True, reply_kind="positive",
                     reply_at="2026-03-01T00:00:00Z")
        first = classify(lead)
        second = classify(lead)
        self.assertEqual(first, second)


# ---------------------------------------------------------- precedence

class PrecedenceTests(unittest.TestCase):
    """One test per pair that can collide.  The precedence is the design."""

    def test_never_beats_active(self):
        """An unsubscribed lead in an active sequence is NEVER, not ACTIVE."""
        lead = _lead(has_unsubscribe=True, in_active_sequence=True)
        self.assertEqual(classify(lead)["lane"], NEVER)

    def test_never_beats_revive(self):
        """A bounced lead that replied is NEVER, not REVIVE."""
        lead = _lead(has_bounce=True, has_reply=True,
                     reply_kind="positive", reply_at="2026-01-01T00:00:00Z")
        self.assertEqual(classify(lead)["lane"], NEVER)

    def test_never_beats_reengage(self):
        """An unsubscribed lead with a finished sequence is NEVER."""
        lead = _lead(has_unsubscribe=True, sequence_finished=True,
                     last_touch_days=200)
        self.assertEqual(classify(lead)["lane"], NEVER)

    def test_active_beats_revive(self):
        """A replying lead still in sequence is ACTIVE, not REVIVE."""
        lead = _lead(has_reply=True, reply_kind="positive",
                     reply_at="2026-06-01T00:00:00Z",
                     in_active_sequence=True)
        self.assertEqual(classify(lead)["lane"], ACTIVE)

    def test_active_beats_reengage(self):
        """A lead in an active sequence with a finished older one is ACTIVE."""
        lead = _lead(in_active_sequence=True, sequence_finished=True,
                     last_touch_days=200)
        self.assertEqual(classify(lead)["lane"], ACTIVE)

    def test_revive_beats_reengage(self):
        """A lead that replied, even long ago, is REVIVE not REENGAGE.

        `has_reply` excludes REGARDLESS of recency - the standing collision
        rule.  Re-engagement copy that pretends a reply did not happen
        would be a lie.
        """
        lead = _lead(has_reply=True, reply_kind="neutral",
                     reply_at="2024-01-01T00:00:00Z",
                     sequence_finished=True, last_touch_days=500)
        self.assertEqual(classify(lead)["lane"], REVIVE)

    def test_negative_reply_is_never_not_revive(self):
        """A negative reply is NEVER even though has_reply could be true."""
        lead = _lead(has_negative_reply=True, has_reply=True,
                     reply_kind="negative",
                     reply_at="2026-01-01T00:00:00Z")
        self.assertEqual(classify(lead)["lane"], NEVER)


# ---------------------------------------------------------- active shield

class ActiveSequenceTests(unittest.TestCase):
    """A lead in an active sequence is untouched by every rule."""

    def test_active_with_unsubscribe_is_still_never(self):
        """NEVER beats ACTIVE - the precedence is fixed."""
        lead = _lead(in_active_sequence=True, has_unsubscribe=True)
        self.assertEqual(classify(lead)["lane"], NEVER)

    def test_active_with_reply_stays_active(self):
        """A replying lead in sequence is ACTIVE, not REVIVE."""
        lead = _lead(in_active_sequence=True, has_reply=True,
                     reply_kind="positive", reply_at="2026-06-01T00:00:00Z")
        self.assertEqual(classify(lead)["lane"], ACTIVE)

    def test_active_with_finished_sequence_stays_active(self):
        """Active beats finished - the active one is what matters."""
        lead = _lead(in_active_sequence=True, sequence_finished=True,
                     last_touch_days=200)
        self.assertEqual(classify(lead)["lane"], ACTIVE)

    def test_active_with_old_touch_stays_active(self):
        """Age does not override active."""
        lead = _lead(in_active_sequence=True, last_touch_days=365)
        self.assertEqual(classify(lead)["lane"], ACTIVE)

    def test_active_alone_is_sufficient(self):
        """No other signal needed.  Active is the lane."""
        lead = _lead(in_active_sequence=True)
        self.assertEqual(classify(lead)["lane"], ACTIVE)


# ---------------------------------------------------------- revive queue

class ReviveQueueTests(unittest.TestCase):
    """20/day cap, oldest-reply-first, no duplicates."""

    def test_daily_cap_is_twenty(self):
        """25 leads in, 20 out today, 5 wait for tomorrow."""
        queue = ReviveQueue()
        leads = [
            {"lead_id": f"lead-{i:03d}",
             "reply_at": f"2026-01-{i+1:02d}T10:00:00Z"}
            for i in range(25)
        ]
        queue.enqueue(leads)
        batch = queue.todays_batch()
        self.assertEqual(len(batch), 20)
        self.assertEqual(queue.pending_count, 25)
        self.assertEqual(len(queue.overflow()), 5)

    def test_cap_queues_not_drops(self):
        """Leads beyond the cap are queued, not lost."""
        queue = ReviveQueue()
        leads = [
            {"lead_id": f"lead-{i:03d}",
             "reply_at": f"2026-01-{i+1:02d}T10:00:00Z"}
            for i in range(25)
        ]
        queue.enqueue(leads)
        batch = queue.todays_batch()
        queue.mark_posted([b["lead_id"] for b in batch])
        # Tomorrow's batch: the remaining 5
        tomorrow = queue.todays_batch()
        self.assertEqual(len(tomorrow), 5)

    def test_oldest_reply_first(self):
        """The queue orders by oldest reply first."""
        queue = ReviveQueue()
        leads = [
            {"lead_id": "recent", "reply_at": "2026-09-01T10:00:00Z"},
            {"lead_id": "oldest", "reply_at": "2026-01-01T10:00:00Z"},
            {"lead_id": "middle", "reply_at": "2026-05-01T10:00:00Z"},
        ]
        queue.enqueue(leads)
        batch = queue.todays_batch()
        ids = [b["lead_id"] for b in batch]
        self.assertEqual(ids, ["oldest", "middle", "recent"])

    def test_same_lead_never_posted_twice(self):
        """A lead already posted is never enqueued again."""
        queue = ReviveQueue(posted_ids={"lead-001"})
        leads = [
            {"lead_id": "lead-001", "reply_at": "2026-01-01T10:00:00Z"},
            {"lead_id": "lead-002", "reply_at": "2026-02-01T10:00:00Z"},
        ]
        queue.enqueue(leads)
        ids = [b["lead_id"] for b in queue.todays_batch()]
        self.assertNotIn("lead-001", ids)
        self.assertIn("lead-002", ids)

    def test_same_lead_not_enqueued_twice(self):
        """Enqueueing the same lead twice does not duplicate it."""
        queue = ReviveQueue()
        lead = {"lead_id": "lead-001", "reply_at": "2026-01-01T10:00:00Z"}
        queue.enqueue([lead])
        queue.enqueue([lead])
        self.assertEqual(queue.pending_count, 1)

    def test_mark_posted_removes_from_pending(self):
        """After marking posted, the lead leaves the pending queue."""
        queue = ReviveQueue()
        queue.enqueue([
            {"lead_id": "a", "reply_at": "2026-01-01T00:00:00Z"},
            {"lead_id": "b", "reply_at": "2026-02-01T00:00:00Z"},
        ])
        queue.mark_posted(["a"])
        self.assertEqual(queue.pending_count, 1)
        self.assertEqual(queue.posted_count, 1)
        batch = queue.todays_batch()
        self.assertEqual(batch[0]["lead_id"], "b")


# ---------------------------------------------------------- unknown holds

class UnknownHoldsTests(unittest.TestCase):
    """UNKNOWN holds.  It is not drained by a looser rule."""

    def test_young_sequence_finished_is_unknown(self):
        """Sequence finished but last touch < 90 days: UNKNOWN."""
        lead = _lead(sequence_finished=True, last_touch_days=30)
        self.assertEqual(classify(lead)["lane"], UNKNOWN)

    def test_no_sequence_no_touch_is_unknown(self):
        """No sequence, no touch data: UNKNOWN."""
        lead = _lead()
        self.assertEqual(classify(lead)["lane"], UNKNOWN)

    def test_sequence_finished_no_touch_data_is_unknown(self):
        """Sequence finished but unknown last touch: UNKNOWN."""
        lead = _lead(sequence_finished=True, last_touch_days=None)
        self.assertEqual(classify(lead)["lane"], UNKNOWN)

    def test_unknown_is_counted_loudly(self):
        """lane_counts reports UNKNOWN size explicitly."""
        estate = [
            _lead(lead_id="a"),
            _lead(lead_id="b"),
            _lead(lead_id="c", has_unsubscribe=True),
        ]
        results = classify_all(estate)
        counts = lane_counts(results)
        self.assertEqual(counts[UNKNOWN], 2)
        self.assertEqual(counts[NEVER], 1)

    def test_exactly_ninety_is_not_reengage(self):
        """90 days exactly is NOT > 90.  The boundary is strict."""
        lead = _lead(sequence_finished=True, last_touch_days=90)
        self.assertEqual(classify(lead)["lane"], UNKNOWN)

    def test_ninety_one_is_reengage(self):
        """91 days, no reply, sequence finished: REENGAGE."""
        lead = _lead(sequence_finished=True, last_touch_days=91)
        self.assertEqual(classify(lead)["lane"], REENGAGE)


# ---------------------------------------------------------- lane identity

class LaneIdentityTests(unittest.TestCase):
    """Each lane's defining conditions, tested in isolation."""

    def test_never_unsubscribe(self):
        self.assertEqual(classify(_lead(has_unsubscribe=True))["lane"], NEVER)

    def test_never_bounce(self):
        self.assertEqual(classify(_lead(has_bounce=True))["lane"], NEVER)

    def test_never_negative_reply(self):
        self.assertEqual(
            classify(_lead(has_negative_reply=True))["lane"], NEVER)

    def test_never_unknown_stop_reason(self):
        self.assertEqual(
            classify(_lead(stop_reason="still_unknown"))["lane"], NEVER)

    def test_never_we_stopped_it_is_not_never(self):
        """`we_stopped_it` is our own action, not a prospect signal.

        It is not in _NEVER_STOP_REASONS because it does not say the
        prospect refused.  Without other signals, it falls to UNKNOWN.
        """
        self.assertEqual(
            classify(_lead(stop_reason="we_stopped_it"))["lane"], UNKNOWN)

    def test_reengage_basic(self):
        lead = _lead(sequence_finished=True, last_touch_days=100)
        self.assertEqual(classify(lead)["lane"], REENGAGE)

    def test_revive_positive_reply(self):
        lead = _lead(has_reply=True, reply_kind="positive",
                     reply_at="2026-01-01T00:00:00Z")
        self.assertEqual(classify(lead)["lane"], REVIVE)

    def test_revive_neutral_reply(self):
        lead = _lead(has_reply=True, reply_kind="neutral",
                     reply_at="2026-06-15T00:00:00Z")
        self.assertEqual(classify(lead)["lane"], REVIVE)

    def test_active_basic(self):
        self.assertEqual(
            classify(_lead(in_active_sequence=True))["lane"], ACTIVE)


if __name__ == "__main__":
    unittest.main()
