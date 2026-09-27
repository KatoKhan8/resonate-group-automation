"""Absent within the window is UNCONFIRMED, not FAIL.

TASK-298. ISSUE-043: the campaign-membership index took ~30 seconds while
the readback window was ~15s. A lead that answered 200 to attach and then
read absent at t+15s was present at t+30s. A check that called that FAIL
would make somebody re-push a good push, and a re-push against a lead that
is now in_sequence cannot be attached anywhere at all.

Three things these tests pin:

1. A lead absent at the first readback produces UNCONFIRMED, not FAIL.
2. The retry ladder runs at t+60s, t+180s, t+600s and records every attempt.
3. A lead absent at t+60 and present at t+180 produces UNCONFIRMED then PASS,
   and the result shows both.
4. A lead absent at t+600 produces FAIL with its id.
5. The lead id sets are diffed BOTH directions — pushed_and_absent AND
   present_and_not_pushed.
"""
import datetime
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa.check_readback import (
    check_exactly_the_pushed_leads,
    _apply_retry_ladder,
    RETRY_SCHEDULE_SECONDS,
    PASS,
    FAIL,
    UNCONFIRMED,
)


class TestAbsentWithinTheWindowIsUnconfirmed(unittest.TestCase):
    """ISSUE-043: absent within the window is UNCONFIRMED."""

    def test_absent_on_first_read_is_unconfirmed_not_fail(self):
        """A lead absent on the first read is UNCONFIRMED, not FAIL."""
        pushed = {101: "rec-001", 102: "rec-002"}

        def provider_ids(cid):
            return [101]

        result = check_exactly_the_pushed_leads(
            491, pushed, provider_campaign_lead_ids=provider_ids)
        self.assertEqual(result["verdict"], UNCONFIRMED)
        self.assertEqual(len(result["pushed_and_absent"]), 1)
        self.assertEqual(result["pushed_and_absent"][0]["lead_id"], 102)

    def test_present_and_not_pushed_detected(self):
        """The other direction: a lead present but not pushed is reported."""
        pushed = {101: "rec-001"}

        def provider_ids(cid):
            return [101, 999]

        result = check_exactly_the_pushed_leads(
            491, pushed, provider_campaign_lead_ids=provider_ids)
        self.assertEqual(result["verdict"], UNCONFIRMED)
        self.assertIn(999, result["present_and_not_pushed"])
        self.assertEqual(len(result["pushed_and_absent"]), 0)

    def test_both_directions_at_once(self):
        """Both directions of the diff fire at once."""
        pushed = {101: "rec-001", 102: "rec-002"}

        def provider_ids(cid):
            return [101, 999]

        result = check_exactly_the_pushed_leads(
            491, pushed, provider_campaign_lead_ids=provider_ids)
        self.assertEqual(result["verdict"], UNCONFIRMED)
        absent_ids = [a["lead_id"] for a in result["pushed_and_absent"]]
        self.assertIn(102, absent_ids)
        self.assertIn(999, result["present_and_not_pushed"])

    def test_exact_match_is_pass(self):
        """When the sets match exactly, the verdict is PASS."""
        pushed = {101: "rec-001", 102: "rec-002"}

        def provider_ids(cid):
            return [101, 102]

        result = check_exactly_the_pushed_leads(
            491, pushed, provider_campaign_lead_ids=provider_ids)
        self.assertEqual(result["verdict"], PASS)
        self.assertEqual(len(result["pushed_and_absent"]), 0)
        self.assertEqual(len(result["present_and_not_pushed"]), 0)

    def test_provider_error_is_unconfirmed(self):
        """A provider read error is UNCONFIRMED, not FAIL."""
        pushed = {101: "rec-001"}

        def provider_ids(cid):
            raise RuntimeError("connection timeout")

        result = check_exactly_the_pushed_leads(
            491, pushed, provider_campaign_lead_ids=provider_ids)
        self.assertEqual(result["verdict"], UNCONFIRMED)
        self.assertIn("connection timeout", result["error"])


class TestRetryLadder(unittest.TestCase):
    """The retry ladder records every attempt with its timestamp."""

    def test_initial_pass_skips_retries(self):
        """When the initial attempt passes, the retry ladder is not run."""
        pushed = {101: "rec-001"}
        push_time = "2026-09-25T06:00:00Z"

        def provider_ids(cid):
            return [101]

        attempts, final = _apply_retry_ladder(
            491, pushed, push_time, provider_campaign_lead_ids=provider_ids)

        self.assertEqual(final, PASS)
        self.assertEqual(len(attempts), 4)
        self.assertEqual(attempts[0]["verdict"], PASS)
        for a in attempts[1:]:
            self.assertEqual(a["verdict"], "NOT_RUN")

    def test_delayed_index_unconfirmed_then_pass(self):
        """ISSUE-043: absent at t+60, present at t+180 -> UNCONFIRMED then PASS.

        This is the constructed delayed-index sequence the task requires.
        """
        pushed = {101: "rec-001", 102: "rec-002"}
        push_time = "2026-09-25T06:00:00Z"

        call_count = [0]

        def provider_ids(cid):
            call_count[0] += 1
            if call_count[0] <= 2:
                return [101]
            return [101, 102]

        attempts, final = _apply_retry_ladder(
            491, pushed, push_time, provider_campaign_lead_ids=provider_ids)

        self.assertEqual(final, PASS)
        self.assertEqual(attempts[0]["verdict"], UNCONFIRMED)
        self.assertEqual(attempts[1]["label"], "t+60s")
        self.assertEqual(attempts[1]["verdict"], UNCONFIRMED)
        self.assertEqual(attempts[2]["label"], "t+180s")
        self.assertEqual(attempts[2]["verdict"], PASS)
        self.assertIn("06:01", attempts[1]["scheduled_at"])

    def test_still_absent_at_600_is_fail(self):
        """A lead absent at t+600 produces FAIL with its id."""
        pushed = {101: "rec-001", 102: "rec-002"}
        push_time = "2026-09-25T06:00:00Z"

        def provider_ids(cid):
            return [101]

        attempts, final = _apply_retry_ladder(
            491, pushed, push_time, provider_campaign_lead_ids=provider_ids)

        self.assertEqual(final, FAIL)
        last_with_result = None
        for a in reversed(attempts):
            if a.get("result") is not None:
                last_with_result = a
                break
        self.assertIsNotNone(last_with_result)
        self.assertEqual(last_with_result["label"], "t+600s")
        absent_ids = [x["lead_id"] for x in
                      last_with_result["result"]["pushed_and_absent"]]
        self.assertIn(102, absent_ids)

    def test_retry_schedule_is_60_180_600(self):
        """The retry schedule is exactly t+60, t+180, t+600."""
        self.assertEqual(RETRY_SCHEDULE_SECONDS, (60, 180, 600))

    def test_all_attempts_recorded_with_timestamps(self):
        """Every attempt carries its label and scheduled_at."""
        pushed = {101: "rec-001"}
        push_time = "2026-09-25T06:00:00Z"

        def provider_ids(cid):
            return []

        attempts, final = _apply_retry_ladder(
            491, pushed, push_time, provider_campaign_lead_ids=provider_ids)

        self.assertEqual(len(attempts), 4)
        self.assertEqual(attempts[0]["label"], "initial")
        self.assertEqual(attempts[1]["label"], "t+60s")
        self.assertEqual(attempts[2]["label"], "t+180s")
        self.assertEqual(attempts[3]["label"], "t+600s")
        for a in attempts[1:]:
            self.assertIn("scheduled_at", a)
            self.assertIn("2026-09-25", a["scheduled_at"])

    def test_counts_not_set_equality_rejected(self):
        """Comparing counts instead of id sets is rejected.

        332 -> 333 is consistent with the wrong lead arriving. The check
        must diff the id sets, not compare counts.
        """
        pushed = {101: "rec-001", 102: "rec-002"}

        def provider_ids(cid):
            return [101, 999]

        result = check_exactly_the_pushed_leads(
            491, pushed, provider_campaign_lead_ids=provider_ids)
        self.assertEqual(result["verdict"], UNCONFIRMED)
        self.assertEqual(result["pushed_count"], 2)
        self.assertEqual(result["provider_count"], 2)
        self.assertEqual(len(result["pushed_and_absent"]), 1)
        self.assertEqual(len(result["present_and_not_pushed"]), 1)


if __name__ == "__main__":
    unittest.main()
