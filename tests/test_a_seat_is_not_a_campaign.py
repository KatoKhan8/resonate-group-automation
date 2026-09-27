#!/usr/bin/env python3
"""TASK-297: a seat is not a campaign, and the inbox is mostly the client's.

~27,000 conversations at HeyReach. `campaigns_for_lead` returns the client's
campaigns alongside ours. A check that calls a reply or an enrollment ours
because it is on a seat we use is wrong. A seat is not a campaign.

THE CONSTRUCTED FAILURE: a lead found in two campaigns via campaigns_for_lead
- one ours (IN_PROGRESS) and one the client's (FINISHED). The check must
report WHICH campaign and WHOSE it is, with the evidence that decided ours
vs the client's.

`campaign_stats` is the evidence for ours-vs-client: a campaign with
connectionsSent > 0 that matches our naming pattern is ours.
"""
import unittest
from unittest import mock

from scripts.qa import check_campaign_heyreach


class SeatIsNotACampaign(unittest.TestCase):
    """A seat is shared. The campaigns on it are not all ours."""

    def test_our_campaign_detected_by_name(self):
        row = {"name": "Resonate ABM Cohort C", "id": 605732}
        is_ours, evidence = check_campaign_heyreach._is_our_campaign(row, None)
        self.assertTrue(is_ours)
        self.assertIn("name=", evidence)

    def test_client_campaign_not_detected_as_ours(self):
        row = {"name": "Q3 Enterprise Outreach", "id": 555001}
        is_ours, evidence = check_campaign_heyreach._is_our_campaign(row, None)
        self.assertFalse(is_ours)

    def test_none_row_is_not_ours(self):
        is_ours, evidence = check_campaign_heyreach._is_our_campaign(None, None)
        self.assertFalse(is_ours)
        self.assertIn("no campaign row", evidence)

    def test_canary_detected_as_ours(self):
        row = {"name": "linkedin-canary-v2", "id": 604869}
        is_ours, _ = check_campaign_heyreach._is_our_campaign(row, None)
        self.assertTrue(is_ours)

    def test_cohort_detected_as_ours(self):
        row = {"name": "cohort-b-linkedin", "id": 613744}
        is_ours, _ = check_campaign_heyreach._is_our_campaign(row, None)
        self.assertTrue(is_ours)


class CollisionReportsWhoseCampaign(unittest.TestCase):
    """A lead in another campaign must say WHICH and WHOSE."""

    def test_ours_vs_client_evidence_is_stated(self):
        """The evidence for ours vs client must be stated per collision."""
        our_row = {"name": "Resonate cohort A", "id": 605732}
        client_row = {"name": "Sales Pipeline Q3", "id": 555001}
        is_ours_1, ev1 = check_campaign_heyreach._is_our_campaign(
            our_row, None)
        is_ours_2, ev2 = check_campaign_heyreach._is_our_campaign(
            client_row, None)
        self.assertTrue(is_ours_1)
        self.assertFalse(is_ours_2)
        self.assertIn("Resonate", ev1)
        self.assertIn("Sales Pipeline", ev2)


class SeatTimezoneIsNotGuessed(unittest.TestCase):
    """A guessed timezone is worse than a missing one - CLAUDE.md."""

    def test_missing_timezone_returns_none(self):
        seat = {"id": 116968, "authIsValid": True}
        tz = check_campaign_heyreach._seat_timezone(seat)
        self.assertIsNone(tz)

    def test_empty_timezone_returns_none(self):
        seat = {"id": 116968, "timeZone": ""}
        tz = check_campaign_heyreach._seat_timezone(seat)
        self.assertIsNone(tz)

    def test_present_timezone_is_returned(self):
        seat = {"id": 116968, "timeZone": "Europe/Zagreb"}
        tz = check_campaign_heyreach._seat_timezone(seat)
        self.assertEqual(tz, "Europe/Zagreb")

    def test_none_seat_returns_none(self):
        tz = check_campaign_heyreach._seat_timezone(None)
        self.assertIsNone(tz)


class HeyreachLeadIdPresenceIsReported(unittest.TestCase):
    """ISSUE-041: zero contacts carry heyreach_lead_id.

    Any rule gated on that field will report 'nothing to check' on 100% of
    subjects and read as a clean pass. If a rule keys on it, report the
    key-presence count first, and report VACUOUS.
    """

    def test_zero_leads_is_vacuous_not_pass(self):
        """A campaign with zero leads is VACUOUS for the lead rules."""
        result = check_campaign_heyreach._vacuous_result(
            "zero leads in campaign",
            "pre_push", [605732],
            {"path": "queue.jsonl", "mtime": "2026-09-25T06:00:00Z",
             "rows": 100},
            "2026-09-25T06:01:00Z")
        self.assertEqual(result["verdict"], "VACUOUS")
        self.assertEqual(result["subjects"], 0)
        self.assertEqual(result["vacuous_reason"],
                         "zero leads in campaign")


class VacuousIsNotPass(unittest.TestCase):
    """subjects == 0 exits 2 with a stated reason."""

    def test_vacuous_result_carries_reason(self):
        result = check_campaign_heyreach._vacuous_result(
            "no HeyReach campaigns found",
            "pre_push", [],
            {"path": "queue.jsonl", "mtime": "2026-09-25T06:00:00Z",
             "rows": 0},
            "2026-09-25T06:01:00Z")
        self.assertEqual(result["verdict"], "VACUOUS")
        self.assertIn("vacuous_reason", result)
        self.assertTrue(len(result["vacuous_reason"]) > 0)

    def test_error_result_carries_reason(self):
        result = check_campaign_heyreach._error_result(
            "--workspaces is required",
            "pre_push", [], "2026-09-25T06:01:00Z")
        self.assertEqual(result["verdict"], "ERROR")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
