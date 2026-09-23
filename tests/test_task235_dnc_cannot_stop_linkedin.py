#!/usr/bin/env python3
"""TASK-235: a DNC or unsubscribe cannot stop a running HeyReach sequence.

Five requirements, each proven by a test that FAILS before the change and
PASSES after:

1. leadstop.sweep counts LinkedIn-staged contacts (heyreach_lead_id)
2. LINKEDIN_STOP_LEAD verb exists with the same shape as EMAIL_STOP_LEAD
3. heyreach_lead_id is WRITTEN on the staging path
4. A DNC on a dual-channel contact produces a stop attempt on BOTH channels
5. A LinkedIn stop whose readback does not confirm is reported as FAILED

NO PROVIDER WRITE. Every test uses a fake transport.
"""
import unittest
from unittest import mock

from src import (campaigns, eligibility, events, leadstop, providerwrites,
                 store)
from src import providers
from tests.base import QueueTest


class FakeHeyReach:
    """HeyReach's measured behaviour for stop_lead_in_campaign.

    The real function reads back per lead and refuses when the provider still
    reports the lead as running. This fake replicates that: a stop that does
    not land raises, and a stop that lands changes the lead's status.
    """

    RUNNING = ("Pending", "InSequence", "PendingOrExcludedToBeCalculated")

    def __init__(self):
        self.leads = {}  # {campaign_id: {member_id: status}}
        self.writes = 0
        self.stop_calls = []

    def add_lead(self, campaign_id, member_id, status="InSequence"):
        self.leads.setdefault(int(campaign_id), {})[str(member_id)] = status

    def stop_lead_in_campaign(self, campaign_id, member_id, profile_url):
        self.stop_calls.append((campaign_id, member_id, profile_url))
        held = self.leads.get(int(campaign_id), {})
        mid = str(member_id)
        if mid not in held:
            raise providers.ProviderError(
                f"heyreach stop_lead_in_campaign: lead {mid} not in "
                f"campaign {campaign_id}")
        self.writes += 1
        held[mid] = "Stopped"
        return {"campaign_id": campaign_id, "profile_url": profile_url,
                "lead_status": "Stopped"}

    def campaigns_for_lead(self, profile_url=None, **_kw):
        found = []
        for cid, leads in self.leads.items():
            for mid, status in leads.items():
                found.append({"campaignId": cid, "leadStatus": status,
                              "campaignName": f"campaign-{cid}",
                              "campaignStatus": "active",
                              "creationTime": "2026-09-20T00:00:00Z"})
        return found, len(found)


class FakeBison:
    """Minimal EmailBison fake for the dual-channel test."""

    STOPPED_STATES = ("stopped", "replied", "bounced", "sequence_finished",
                      "unsubscribed")

    def __init__(self):
        self.members = {}
        self.writes = 0

    def add_member(self, campaign_id, lead_id, status="in_sequence"):
        self.members.setdefault(int(campaign_id), {})[int(lead_id)] = status

    def membership(self, campaign_id, lead_ids=None, per_page=200):
        rows = dict(self.members.get(int(campaign_id), {}))
        if lead_ids is None:
            return rows
        wanted = {int(i) for i in lead_ids}
        return {k: v for k, v in rows.items() if k in wanted}

    def stop_lead(self, campaign_id, lead_ids, attempts=8, interval=0):
        held = self.members[int(campaign_id)]
        self.writes += 1
        for i in lead_ids:
            held[int(i)] = "stopped"
        return {"stopped": {int(i): "stopped" for i in lead_ids},
                "untouched": {}}


# ------------------------------------------------ requirement 1: sweep counts
class SweepCountsLinkedInContacts(QueueTest):
    """Requirement 1: sweep counts every contact it examines.

    A LinkedIn-staged contact was previously skipped without incrementing
    report['checked']. That is why a missing capability looked like a working
    sweep.
    """

    def setUp(self):
        super().setUp()
        self.heyreach = FakeHeyReach()
        self.bison = FakeBison()
        self._real_bison = leadstop.bison
        self._real_heyreach = leadstop.heyreach
        leadstop.bison = self.bison
        leadstop.heyreach = self.heyreach
        self.addCleanup(setattr, leadstop, "bison", self._real_bison)
        self.addCleanup(setattr, leadstop, "heyreach", self._real_heyreach)

    def test_a_linkedin_staged_contact_is_counted(self):
        """A contact with heyreach_lead_id but no bison_lead_id is examined."""
        rec = {"id": "rec-1", "client": "productive",
               "domain": "example.com", "company": "Example", "state": "ready",
               "contacts": [{"key": "ck-1", "email": "a@example.com",
                             "first_name": "Test", "last_name": "Person",
                             "sendable": True,
                             "heyreach_lead_id": "lead-42",
                             "linkedin_url": "test-person"}]}
        store.save([rec])
        row = campaigns.new_campaign("camp-li", "productive", "LI sweep")
        row["record_ids"] = ["rec-1"]
        row["heyreach_campaign_id"] = "605732"
        campaigns.save([row])
        self.heyreach.add_lead(605732, "lead-42")

        report = leadstop.sweep(live=False)
        self.assertGreaterEqual(report["checked"], 1,
                                "a LinkedIn-staged contact was not counted; "
                                "the sweep silently skipped it")


# ---------------------------------------------- requirement 2: verb exists
class LinkedInStopLeadVerbExists(QueueTest):
    """Requirement 2: LINKEDIN_STOP_LEAD exists with the correct shape.

    Reserved on the ledger, gated by executionguard, performed through
    providerwrites, refusing unless the provider readback confirms.
    """

    def test_the_constant_exists_and_is_in_operations(self):
        self.assertEqual(providerwrites.LINKEDIN_STOP_LEAD,
                         "heyreach.stop_lead")
        self.assertIn(providerwrites.LINKEDIN_STOP_LEAD,
                      providerwrites.OPERATIONS)

    def test_it_is_in_supported(self):
        """ENABLED 2026-09-23 BY OPERATOR DECISION.

        This asserted the opposite - "the door is shut, enabling is Claude's
        decision" - which was correct for TASK-235 and is the condition the
        OPERATIONS entry set for itself.

        It was enabled the evening the cross-channel stop was measured. The
        LinkedIn->email direction passed at 7.7 minutes; the email->LinkedIn
        direction could not run AT ALL, because this verb was sealed, and
        enrolling 33 seats with only one direction working means a prospect
        who says no by email keeps receiving LinkedIn messages.

        The safety argument is unchanged and is below: not prospect-facing,
        repeatable, and a readback that raises rather than believing a stop
        the provider has not confirmed.
        """
        self.assertIn(providerwrites.LINKEDIN_STOP_LEAD,
                      providerwrites.SUPPORTED)

    def test_enabling_it_moved_nothing_else(self):
        """One verb, not a channel-wide licence.

        The register's standing lesson is that a gate opened for one reason
        gets read as opened generally. LINKEDIN_ADD_LEAD is the prospect-
        facing one next to it and it stays conditional.
        """
        self.assertEqual(len(providerwrites.SUPPORTED), 15)
        self.assertFalse(providerwrites.CAMPAIGN_LEVEL_STAGING_IS_PROVEN)
        self.assertIn(providerwrites.LINKEDIN_ADD_LEAD,
                      providerwrites.CONDITIONAL)

    def test_it_is_in_repeatable(self):
        """A repeat stop can only mean somebody receives less."""
        self.assertIn(providerwrites.LINKEDIN_STOP_LEAD,
                      providerwrites.REPEATABLE)

    def test_it_is_not_prospect_facing(self):
        """It can only ever reduce what somebody receives."""
        _channel, facing, _why = providerwrites.OPERATIONS[
            providerwrites.LINKEDIN_STOP_LEAD]
        self.assertFalse(facing)

    def test_the_channel_is_linkedin(self):
        channel, _facing, _why = providerwrites.OPERATIONS[
            providerwrites.LINKEDIN_STOP_LEAD]
        self.assertEqual(channel, "linkedin")

    def test_perform_refuses_without_supported(self):
        """The REFUSAL MECHANISM, still pinned now that the verb is enabled.

        This used to rest on the real `SUPPORTED` not containing the verb, so
        enabling it would have deleted the test's meaning while leaving it
        green. It now removes the verb explicitly, which tests the door
        rather than the current setting of the door.
        """
        without = tuple(v for v in providerwrites.SUPPORTED
                        if v != providerwrites.LINKEDIN_STOP_LEAD)
        spy_calls = []
        with mock.patch.object(providerwrites, "SUPPORTED", without):
            with self.assertRaises(providerwrites.WriteRefused):
                providerwrites.perform(
                    providerwrites.LINKEDIN_STOP_LEAD,
                    campaign="camp-1", tenant="productive",
                    payload={"lead_id": "42"},
                    transport=lambda p: spy_calls.append(p) or {"ok": True},
                    readback=lambda: {"stopped": True},
                    expected={"stopped": True})
        self.assertEqual(spy_calls, [],
                         "the transport was reached despite the verb being "
                         "unsupported")

    def test_perform_accepts_when_supported(self):
        """When temporarily enabled, the verb works through perform."""
        heyreach = FakeHeyReach()
        heyreach.add_lead(605732, "lead-42")
        with mock.patch.object(providerwrites, "SUPPORTED",
                               providerwrites.SUPPORTED + (
                                   providerwrites.LINKEDIN_STOP_LEAD,)):
            outcome = providerwrites.perform(
                providerwrites.LINKEDIN_STOP_LEAD,
                campaign="camp-1", tenant="productive",
                payload={"lead_id": "lead-42", "why": "dnc"},
                transport=lambda p: heyreach.stop_lead_in_campaign(
                    605732, "lead-42", "test-url"),
                readback=lambda: {"stopped": True},
                expected={"stopped": True})
        self.assertEqual(outcome["class"], providerwrites.ACCEPTED)


# ----------------------------------------- requirement 4: dual-channel stop
class DualChannelStop(QueueTest):
    """Requirement 4: a DNC on a dual-channel contact stops BOTH.

    A contact live on both EmailBison and HeyReach gets a stop attempt on
    each channel when a suppression reason applies.
    """

    def setUp(self):
        super().setUp()
        self.heyreach = FakeHeyReach()
        self.bison = FakeBison()
        self._real_bison = leadstop.bison
        self._real_heyreach = leadstop.heyreach
        leadstop.bison = self.bison
        leadstop.heyreach = self.heyreach
        self.addCleanup(setattr, leadstop, "bison", self._real_bison)
        self.addCleanup(setattr, leadstop, "heyreach", self._real_heyreach)

    def test_a_dnc_stops_both_channels(self):
        """A contact with both bison_lead_id and heyreach_lead_id is stopped
        on both when a suppression reason applies."""
        rec = {"id": "rec-1", "client": "productive",
               "domain": "example.com", "company": "Example", "state": "ready",
               "contacts": [{"key": "ck-1", "email": "a@example.com",
                             "first_name": "Test", "last_name": "Person",
                             "sendable": True,
                             "bison_lead_id": 11,
                             "heyreach_lead_id": "lead-42",
                             "linkedin_url": "test-person",
                             "unsubscribed": True}]}
        store.save([rec])
        row = campaigns.new_campaign("camp-both", "productive",
                                     "Dual channel test")
        row["record_ids"] = ["rec-1"]
        row["bison_campaign_id"] = 77
        row["heyreach_campaign_id"] = "605732"
        campaigns.save([row])
        self.bison.add_member(77, 11)
        self.heyreach.add_lead(605732, "lead-42")

        # Enable LINKEDIN_STOP_LEAD temporarily so the sweep can use it
        with mock.patch.object(providerwrites, "SUPPORTED",
                               providerwrites.SUPPORTED + (
                                   providerwrites.LINKEDIN_STOP_LEAD,)):
            report = leadstop.sweep(live=True)

        # Both channels were checked
        self.assertGreaterEqual(report["checked"], 2,
                                "both channels should be counted")
        # Both channels were stopped (or at least attempted)
        stopped_channels = {e.get("channel") for e in report["stopped"]}
        failed_channels = {e.get("channel") for e in report["failed"]}
        attempted = stopped_channels | failed_channels
        self.assertIn("email", attempted,
                       "the email channel was not attempted")
        self.assertIn("linkedin", attempted,
                       "the LinkedIn channel was not attempted")


# ---------------------------------------- requirement 5: unconfirmed fails
class UnconfirmedLinkedInStopFails(QueueTest):
    """Requirement 5: an unconfirmed readback is FAILED, never stopped.

    A LinkedIn stop whose readback does not confirm the lead stopped must be
    reported as failed.
    """

    def setUp(self):
        super().setUp()
        self.heyreach = FakeHeyReach()
        self._real_heyreach = leadstop.heyreach
        leadstop.heyreach = self.heyreach
        self.addCleanup(setattr, leadstop, "heyreach", self._real_heyreach)

    def test_an_unconfirmed_stop_is_reported_as_failed(self):
        """When the provider still reports the lead as running after the
        write, the stop is FAILED and never recorded as stopped."""
        rec = {"id": "rec-1", "client": "productive",
               "domain": "example.com", "company": "Example", "state": "ready",
               "contacts": [{"key": "ck-1", "email": "a@example.com",
                             "first_name": "Test", "last_name": "Person",
                             "sendable": True,
                             "heyreach_lead_id": "lead-42",
                             "linkedin_url": "test-person",
                             "unsubscribed": True}]}
        store.save([rec])
        row = campaigns.new_campaign("camp-fail", "productive",
                                     "Fail test")
        row["record_ids"] = ["rec-1"]
        row["heyreach_campaign_id"] = "605732"
        campaigns.save([row])
        self.heyreach.add_lead(605732, "lead-42")

        # Make the transport raise to simulate an unconfirmed stop
        original_stop = self.heyreach.stop_lead_in_campaign

        def _failing_stop(campaign_id, member_id, profile_url):
            raise providers.ProviderError(
                "heyreach stop_lead_in_campaign: the write returned 2xx and "
                "the provider still reports this lead as InSequence")

        self.heyreach.stop_lead_in_campaign = _failing_stop

        with mock.patch.object(providerwrites, "SUPPORTED",
                               providerwrites.SUPPORTED + (
                                   providerwrites.LINKEDIN_STOP_LEAD,)):
            report = leadstop.sweep(live=True)

        # The failure is reported, not silently swallowed
        self.assertEqual(len(report["failed"]), 1,
                         "an unconfirmed stop was not reported as failed")
        self.assertEqual(report["failed"][0]["channel"], "linkedin")
        self.assertEqual(len(report["stopped"]), 0,
                         "an unconfirmed stop was recorded as stopped")


# ------------------------------------ requirement 3: heyreach_lead_id written
class HeyreachLeadIdPersisted(QueueTest):
    """Requirement 3: heyreach_lead_id is written on the staging path.

    The provider lead id from the readback is persisted onto the contact so
    a later stop can name the exact person at HeyReach.
    """

    def test_remember_linkedin_lead_writes_the_id(self):
        """_remember_linkedin_lead persists the id onto the contact."""
        from src.heyreachfactory import _remember_linkedin_lead

        rec = {"id": "rec-1", "client": "productive",
               "domain": "example.com", "company": "Example", "state": "ready",
               "contacts": [{"key": "ck-1", "email": "a@example.com",
                             "first_name": "Test", "last_name": "Person",
                             "sendable": True}]}
        store.save([rec])

        row = {"record_id": "rec-1", "contact_key": "ck-1"}
        _remember_linkedin_lead(row, "provider-lead-99")

        saved = store.load()
        contact = saved[0]["contacts"][0]
        self.assertEqual(contact.get("heyreach_lead_id"), "provider-lead-99",
                         "heyreach_lead_id was not persisted on the contact")


if __name__ == "__main__":
    unittest.main()
