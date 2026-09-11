#!/usr/bin/env python3
"""Proving a connection request happened, from fields rather than from counters.

Before this, nothing in the system could prove a LinkedIn invitation had gone
out. `touch.CONFIRMING_EVENTS` is writable only by a send path that raises or
by a webhook HeyReach does not expose, so a canary's first touch was
unrecordable by construction - the funnel would have reported zero confirmed
actions forever while a real person sat in a live campaign.

Two free routes answer it and the module had never tried them:
`/campaign/GetLeadsFromCampaign` per lead, `/stats/GetOverallStats` per
campaign. `CONNECTION_STATUS_AVAILABLE = False` remains correct - it is a
statement about the INBOX route, which genuinely carries no invitation state.
What was wrong was reading it as a statement about the provider.

## The dangerous half: `Failed` does not mean nothing happened

Established over 851 real leads across 11 campaigns, and re-confirmed against
live campaigns while writing these tests:

    182   (Finished, ConnectionAccepted, MessageSent)    -> accepted
     10   (Finished, ConnectionAccepted, MessageReply)   -> replied
      3   (Failed,   ConnectionAccepted, None)           -> accepted
      1   (Failed,   ConnectionAccepted, MessageSent)    -> accepted
      1   (Pending,  None,               None)           -> request_pending

Four of those leads carry `leadCampaignStatus: Failed` and had nevertheless
been accepted. Code that read `Failed` as "safe to retry" would send a second
invitation to somebody who accepted the first. So failure is consulted last,
and only when nothing more final is present.

## The other half: counters cannot answer it

`progressStats.totalUsersInProgress` is a residual, not a count. Campaign
594061 reports `totalUsersInProgress: 1, totalUsersPending: 0` while that same
lead reads `Pending / None / lastActionTime null` - nothing sent, already
counted - and three other campaigns report it as -7, -5 and -6. It is never
mapped to a lifecycle state.
"""
import unittest
from unittest import mock

from src import providers
from src.providers import heyreach

ProviderError = providers.ProviderError


def a_row(campaign="Pending", connection="None", message="None", **over):
    """A lead row in the shape the provider actually returns."""
    row = {"id": 304173736, "leadCampaignStatus": campaign,
           "leadConnectionStatus": connection, "leadMessageStatus": message,
           "lastActionTime": None, "failedTime": None, "errorCode": None,
           "linkedInSenderId": 116968,
           "linkedInUserProfileId": "ACoAABcz6IoBsLz5K8VPJ6b7xMoAnKA_d1Fq1EY",
           "linkedInUserProfile": {"profileUrl":
                                   "https://www.linkedin.com/in/example"}}
    row.update(over)
    return row


class EveryObservedCombinationMapsAsMeasured(unittest.TestCase):
    """The table above, asserted. These are real provider shapes, not invented
    ones - each was counted in a live read."""

    OBSERVED = (
        ("Finished", "ConnectionAccepted", "MessageSent", heyreach.ACCEPTED),
        ("Finished", "ConnectionAccepted", "MessageReply", heyreach.REPLIED),
        ("Finished", "ConnectionAccepted", "None", heyreach.ACCEPTED),
        ("Failed", "ConnectionAccepted", "None", heyreach.ACCEPTED),
        ("Failed", "ConnectionAccepted", "MessageSent", heyreach.ACCEPTED),
        ("Failed", "None", "MessageSent", heyreach.FAILED),
        ("InSequence", "ConnectionSent", "None", heyreach.REQUEST_SENT),
        ("Pending", "None", "None", heyreach.REQUEST_PENDING),
        ("Failed", "None", "None", heyreach.FAILED),
        ("Finished", "None", "None", heyreach.ENDED_NO_ACTION),
    )

    def test_each_one(self):
        for campaign, connection, message, expected in self.OBSERVED:
            with self.subTest(combination=(campaign, connection, message)):
                got = heyreach.lead_state(
                    a_row(campaign, connection, message))
                self.assertEqual(got["state"], expected)


class FailureNeverMasksSomethingThatHappened(unittest.TestCase):
    """The one that would re-contact a real person."""

    def test_a_failed_lead_that_was_accepted_reads_as_accepted(self):
        got = heyreach.lead_state(
            a_row("Failed", "ConnectionAccepted", "None",
                  errorCode="TooManyRetries"))
        self.assertEqual(got["state"], heyreach.ACCEPTED)

    def test_a_failed_lead_that_replied_reads_as_replied(self):
        got = heyreach.lead_state(
            a_row("Failed", "ConnectionAccepted", "MessageReply",
                  errorCode="LeadBlockedByRecipient"))
        self.assertEqual(got["state"], heyreach.REPLIED)

    def test_and_those_states_count_as_reached(self):
        """So no caller has to decide it: `FAILED` is deliberately not in the
        set, because a failed lead may already have been contacted."""
        self.assertIn(heyreach.ACCEPTED, heyreach.REACHED)
        self.assertIn(heyreach.REPLIED, heyreach.REACHED)
        self.assertIn(heyreach.REQUEST_SENT, heyreach.REACHED)
        self.assertNotIn(heyreach.FAILED, heyreach.REACHED)
        self.assertNotIn(heyreach.REQUEST_PENDING, heyreach.REACHED)

    def test_a_genuine_failure_with_nothing_behind_it_still_reads_failed(self):
        """The control. If failure never wins, the state is useless."""
        got = heyreach.lead_state(
            a_row("Failed", "None", "None",
                  errorCode="CannotViewProfileDoesnotExist"))
        self.assertEqual(got["state"], heyreach.FAILED)

    def test_the_error_code_is_carried_verbatim(self):
        """15 distinct values in 851 leads, a long tail of singletons, one with
        a vendor typo. An open set is recorded, not interpreted."""
        got = heyreach.lead_state(a_row("Failed", errorCode="SomethingNewIn2027"))
        self.assertEqual(got["error_code"], "SomethingNewIn2027")


class AnUnseenValueIsUnknownAndNeverNeighbouring(unittest.TestCase):
    """594061's sequence carries `toBeWithdrawnAfterDays: 21`, so a withdrawal
    is a scheduled event in that campaign - and no `Withdrawn` value exists in
    851 observed leads. If one appears it must not read as still-pending."""

    def test_an_unknown_connection_value(self):
        got = heyreach.lead_state(a_row(connection="ConnectionWithdrawn"))
        self.assertEqual(got["state"], heyreach.LIFECYCLE_UNKNOWN)
        self.assertIn("never seen", got["why"])
        self.assertIn("leadConnectionStatus", got["why"])

    def test_an_unknown_campaign_value(self):
        got = heyreach.lead_state(a_row(campaign="ManuallyStopped"))
        self.assertEqual(got["state"], heyreach.LIFECYCLE_UNKNOWN)

    def test_an_unknown_message_value(self):
        got = heyreach.lead_state(a_row(message="MessageBounced"))
        self.assertEqual(got["state"], heyreach.LIFECYCLE_UNKNOWN)

    def test_unknown_does_not_count_as_reached(self):
        got = heyreach.lead_state(a_row(connection="ConnectionWithdrawn"))
        self.assertNotIn(got["state"], heyreach.REACHED)

    def test_the_provider_words_survive_so_a_person_can_read_them(self):
        got = heyreach.lead_state(a_row(connection="ConnectionWithdrawn"))
        self.assertEqual(got["raw"]["leadConnectionStatus"],
                         "ConnectionWithdrawn")

    def test_a_real_none_is_not_an_unknown(self):
        """The provider sends the string "None" and JSON null in the same field
        across campaigns. Both mean the same nothing."""
        for value in ("None", None):
            with self.subTest(value=value):
                got = heyreach.lead_state(a_row(connection=value))
                self.assertEqual(got["state"], heyreach.REQUEST_PENDING)


class AZeroMustComeFromTheProvider(unittest.TestCase):
    """`connectionsSent: 0` is the claim that nothing was sent. A response with
    no counters at all is not that claim - it is a contract violation, and the
    same argument `_collection` already makes for a missing `items` key."""

    def test_a_response_without_the_counters_raises(self):
        with mock.patch.object(heyreach, "_read",
                              return_value={"somethingElse": {}}):
            with self.assertRaises(ProviderError) as caught:
                heyreach.campaign_stats(594061)
        self.assertIn("guess rather than a count", str(caught.exception))

    def test_a_genuine_set_of_zeros_is_returned(self):
        """The control: an all-zero campaign is a real answer and must pass."""
        with mock.patch.object(heyreach, "_read", return_value={
                "overallStats": {"connectionsSent": 0, "connectionsAccepted": 0,
                                 "totalMessageReplies": 0,
                                 "uniqueLeadsContacted": 0}}):
            self.assertEqual(heyreach.campaign_stats(594061)["connectionsSent"],
                             0)

    def test_a_page_without_items_raises_rather_than_reading_as_empty(self):
        with mock.patch.object(heyreach, "_read",
                              return_value={"totalCount": 3}):
            with self.assertRaises(ProviderError):
                heyreach.campaign_leads(594061)


class TheRoutesAreReadsAndNothingElse(unittest.TestCase):

    def test_both_are_on_the_read_allowlist(self):
        self.assertIn(heyreach.LEADS_ROUTE, heyreach.READ_ROUTES_ALL)
        self.assertIn(heyreach.STATS_ROUTE, heyreach.READ_ROUTES_ALL)

    def test_neither_is_on_the_write_allowlist(self):
        self.assertNotIn(heyreach.LEADS_ROUTE, heyreach.WRITE_ROUTES)
        self.assertNotIn(heyreach.STATS_ROUTE, heyreach.WRITE_ROUTES)

    def test_the_inbound_event_contract_set_is_untouched(self):
        """`tests/test_audit.py` pins `READ_ROUTES` exactly; these belong in the
        wider tuple because they answer a different question."""
        self.assertEqual(set(heyreach.READ_ROUTES),
                         {"/campaign/GetAll", "/inbox/GetConversationsV2"})

    def test_every_lifecycle_state_is_declared(self):
        for state in (heyreach.REQUEST_PENDING, heyreach.REQUEST_SENT,
                      heyreach.ACCEPTED, heyreach.REPLIED, heyreach.FAILED,
                      heyreach.ENDED_NO_ACTION, heyreach.LIFECYCLE_UNKNOWN):
            self.assertIn(state, heyreach.LIFECYCLE)


if __name__ == "__main__":
    unittest.main()
