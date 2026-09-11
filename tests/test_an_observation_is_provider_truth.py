#!/usr/bin/env python3
"""Recording what the provider did, once per real change, and never inferring.

The canary made the distinction concrete on 2026-09-11. An operator unpaused
campaign 594061 and the provider status moved to `IN_PROGRESS` immediately -
while that campaign's one lead still read `Pending / None / lastActionTime
null`. Campaign active, nothing sent. Anything that treated the campaign status
as the action would have recorded a message nobody received.

So an observation is a per-LEAD fact or it is nothing:

  * a row is appended only when the lead's state actually moves, so polling
    every minute for a week leaves one row per real change - which is what
    makes "transition the logical action exactly once" enforceable
  * the provider's own timestamp is kept separately from the moment this system
    looked, because conflating them dates every action to whenever a poll ran
  * `progressStats` is never consulted: it counts a lead that has done nothing
    and goes negative on live campaigns
  * an unrecognised provider value is recorded as UNKNOWN with the raw words
    beside it, never folded into a neighbouring state
"""
import unittest
from unittest import mock

from src import leadobserve, store
from src.providers import heyreach
from tests.base import QueueTest


def a_lead(state=heyreach.REQUEST_PENDING, lead_id=304173736, **over):
    row = {"provider_lead_id": lead_id, "profile_url":
           "https://www.linkedin.com/in/example",
           "provider_profile_id": "ACoAABexample", "sender_id": 116968,
           "created_at": "2026-09-09T18:07:51Z", "state": state,
           "raw": {"leadCampaignStatus": "Pending",
                   "leadConnectionStatus": "None",
                   "leadMessageStatus": "None"},
           "error_code": None, "at": None, "why": None}
    row.update(over)
    return row


class ARowIsAppendedOnlyWhenSomethingMoves(QueueTest):

    def provider(self, leads, status="IN_PROGRESS"):
        return (
            mock.patch.object(heyreach, "campaign_leads",
                              return_value=(leads, len(leads))),
            mock.patch.object(heyreach, "campaign_stats",
                              return_value={"connectionsSent": 0}),
            mock.patch.object(heyreach, "campaign_by_id",
                              return_value={"id": 594061, "status": status}))

    def observe(self, leads, status="IN_PROGRESS"):
        a, b, c = self.provider(leads, status)
        with a, b, c:
            return leadobserve.observe(594061)

    def test_the_first_observation_records_the_state(self):
        appended = self.observe([a_lead()])
        self.assertEqual(len(appended), 1)
        self.assertEqual(appended[0]["state"], heyreach.REQUEST_PENDING)
        self.assertIsNone(appended[0]["was"])

    def test_polling_again_with_no_change_records_nothing(self):
        self.observe([a_lead()])
        self.assertEqual(self.observe([a_lead()]), [])
        self.assertEqual(self.observe([a_lead()]), [])
        self.assertEqual(len(leadobserve.history(594061)), 1)

    def test_a_real_transition_records_once(self):
        self.observe([a_lead()])
        appended = self.observe([a_lead(heyreach.REQUEST_SENT)])
        self.assertEqual(len(appended), 1)
        self.assertEqual(appended[0]["was"], heyreach.REQUEST_PENDING)
        self.assertEqual(appended[0]["state"], heyreach.REQUEST_SENT)
        self.assertEqual(self.observe([a_lead(heyreach.REQUEST_SENT)]), [])

    def test_the_whole_lifecycle_leaves_one_row_each(self):
        for state in (heyreach.REQUEST_PENDING, heyreach.REQUEST_SENT,
                      heyreach.ACCEPTED, heyreach.REPLIED):
            self.observe([a_lead(state)])
            self.observe([a_lead(state)])          # a quiet poll in between
        states = [r["state"] for r in leadobserve.history(594061)]
        self.assertEqual(states, [heyreach.REQUEST_PENDING,
                                  heyreach.REQUEST_SENT,
                                  heyreach.ACCEPTED, heyreach.REPLIED])

    def test_two_leads_are_tracked_apart(self):
        self.observe([a_lead(lead_id=1), a_lead(lead_id=2)])
        appended = self.observe([a_lead(heyreach.REQUEST_SENT, lead_id=1),
                                 a_lead(lead_id=2)])
        self.assertEqual([r["provider_lead_id"] for r in appended], [1])


class CampaignStatusIsNotAnAction(QueueTest):
    """The canary's own lesson, pinned."""

    def test_an_active_campaign_with_a_pending_lead_records_pending(self):
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([a_lead()], 1)), \
             mock.patch.object(heyreach, "campaign_stats",
                               return_value={"connectionsSent": 0}), \
             mock.patch.object(heyreach, "campaign_by_id",
                               return_value={"id": 594061,
                                             "status": "IN_PROGRESS"}):
            appended = leadobserve.observe(594061)
        self.assertEqual(appended[0]["state"], heyreach.REQUEST_PENDING)
        self.assertEqual(appended[0]["campaign_status"], "IN_PROGRESS")
        self.assertNotIn(appended[0]["state"], heyreach.REACHED)

    def test_nothing_counts_as_reached_until_the_lead_says_so(self):
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([a_lead()], 1)), \
             mock.patch.object(heyreach, "campaign_stats",
                               return_value={"connectionsSent": 0}), \
             mock.patch.object(heyreach, "campaign_by_id",
                               return_value={"id": 594061,
                                             "status": "IN_PROGRESS"}):
            leadobserve.observe(594061)
        self.assertEqual(leadobserve.reached(594061), set())

    def test_a_sent_request_does_count(self):
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([a_lead(heyreach.REQUEST_SENT)], 1)), \
             mock.patch.object(heyreach, "campaign_stats", return_value={}), \
             mock.patch.object(heyreach, "campaign_by_id",
                               return_value={"id": 594061, "status": "X"}):
            leadobserve.observe(594061)
        self.assertEqual(leadobserve.reached(594061), {304173736})


class TheProviderTimestampIsKeptApart(QueueTest):

    def test_provider_at_is_not_the_moment_we_looked(self):
        """Dating an action to whenever a poll happened to run would make the
        whole record useless for anything measured in hours."""
        with mock.patch.object(
                heyreach, "campaign_leads",
                return_value=([a_lead(heyreach.REQUEST_SENT,
                                      at="2026-09-11T09:00:00Z")], 1)), \
             mock.patch.object(heyreach, "campaign_stats", return_value={}), \
             mock.patch.object(heyreach, "campaign_by_id",
                               return_value={"id": 594061, "status": "X"}):
            appended = leadobserve.observe(594061, now="2026-09-11T17:00:00Z")
        self.assertEqual(appended[0]["provider_at"], "2026-09-11T09:00:00Z")
        self.assertEqual(appended[0]["at"], "2026-09-11T17:00:00Z")


class AnUnknownStateIsRecordedNotResolved(QueueTest):

    def test_the_raw_words_survive(self):
        raw = {"leadCampaignStatus": "Pending",
               "leadConnectionStatus": "ConnectionWithdrawn",
               "leadMessageStatus": "None"}
        with mock.patch.object(
                heyreach, "campaign_leads",
                return_value=([a_lead(heyreach.LIFECYCLE_UNKNOWN, raw=raw,
                                      why="never seen")], 1)), \
             mock.patch.object(heyreach, "campaign_stats", return_value={}), \
             mock.patch.object(heyreach, "campaign_by_id",
                               return_value={"id": 594061, "status": "X"}):
            appended = leadobserve.observe(594061)
        self.assertEqual(appended[0]["state"], heyreach.LIFECYCLE_UNKNOWN)
        self.assertEqual(appended[0]["raw"]["leadConnectionStatus"],
                         "ConnectionWithdrawn")
        self.assertNotIn(appended[0]["state"], heyreach.REACHED)


class ReconcileSaysWhichSideHasWhat(QueueTest):

    def test_it_names_a_provider_action_this_system_never_reserved(self):
        """The hand-staged canary's real shape: the provider acted and the
        ledger is empty, because a person staged the lead in the vendor UI."""
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([a_lead(heyreach.ACCEPTED)], 1)), \
             mock.patch.object(heyreach, "campaign_stats", return_value={}), \
             mock.patch.object(heyreach, "campaign_by_id",
                               return_value={"id": 594061, "status": "X"}):
            leadobserve.observe(594061)
        found = leadobserve.reconcile(594061)
        self.assertEqual(found["provider_reached"], ["304173736"])
        self.assertEqual(found["ledger_keys"], [])
        self.assertIn("never reserved", found["note"])

    def test_it_says_so_when_nothing_has_been_observed(self):
        self.assertIn("nothing observed", leadobserve.reconcile(594061)["note"])

    def test_it_distinguishes_waiting_from_reached(self):
        with mock.patch.object(heyreach, "campaign_leads",
                               return_value=([a_lead()], 1)), \
             mock.patch.object(heyreach, "campaign_stats", return_value={}), \
             mock.patch.object(heyreach, "campaign_by_id",
                               return_value={"id": 594061, "status": "X"}):
            leadobserve.observe(594061)
        note = leadobserve.reconcile(594061)["note"]
        self.assertIn("has not contacted anybody yet", note)


class TheLedgerFileIsRedirectable(unittest.TestCase):
    """A stray row would claim a real prospect had been contacted, so the file
    moves with every other piece of state when a test redirects it."""

    def test_it_is_registered_with_the_other_state_files(self):
        self.assertIn("LEAD_OBSERVATIONS", store.STATE_OVERRIDES)

    def test_the_path_honours_the_override(self):
        import os
        previous = os.environ.get("LEAD_OBSERVATIONS")
        os.environ["LEAD_OBSERVATIONS"] = os.path.join("x", "y.jsonl")
        try:
            self.assertTrue(leadobserve.path().endswith("y.jsonl"))
        finally:
            if previous is None:
                os.environ.pop("LEAD_OBSERVATIONS", None)
            else:
                os.environ["LEAD_OBSERVATIONS"] = previous


if __name__ == "__main__":
    unittest.main()
