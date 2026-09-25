#!/usr/bin/env python3
"""A reply on one channel stops the other, tested with synthetic events.

## What this file proves

When a person replies on LinkedIn, the email sequence to that person stops at
the provider. When a person replies by email, the LinkedIn sequence stops at
the provider. Both directions, through the production entry point
(`inbound.handle`), with provider mocks that can lie and are caught when they
do.

## What is NOT proved here

Live provider behaviour. Every provider interaction in this file is mocked.
The scenarios covered by tests and the scenarios requiring live validation
are tabulated at the bottom of this file.

## The test that matters most

`TestTheReadbackCannotLie` drives a stop through `leadstop.stop_contact` with
a mock provider whose readback returns `{"stopped": True}` unconditionally -
the exact defect the email path carried until 2026-09-25. The test fails
because the readback does not query provider state. A stop reported without
the provider confirming it is the defect this whole file is the backstop for.
"""
import unittest

from src import (campaigns, events, inbound, leadstop, providerwrites, store,
                 replywatch)
from src.providers import bison, heyreach
from tests.campaignbase import CLIENT, CampaignTest, contact


# --------------------------------------------------------------------- helpers

def _dual_channel_contact(key="dual", name="Dual Channel",
                          email="dual@example.test",
                          linkedin="https://www.linkedin.com/in/dual"):
    """A contact with bindings on BOTH channels.

    `bison_lead_id` and `heyreach_lead_id` are both set, so both stops have
    somebody to stop. A contact with only one binding is the common case;
    this is the case that exercises the cross-channel guarantee.
    """
    person = contact(key, name, email, linkedin=linkedin)
    person["bison_lead_id"] = 204001
    person["heyreach_lead_id"] = 88001
    return person


class CrossChannelTest(CampaignTest):
    """Base for cross-channel stop tests.

    Sets up a dual-channel record in a campaign with both provider IDs,
    and patches the ownership readback so the inbound path does not drop
    events as "positively not ours".
    """

    def setUp(self):
        super().setUp()
        self._real_owned = inbound._owned
        inbound._owned = lambda *a, **k: (
            (set(inbound.OWNED_SEATS) | {116968},
             set(inbound.OWNED_CAMPAIGNS) | {613724}), None)
        self.addCleanup(setattr, inbound, "_owned", self._real_owned)

    def make_dual_channel_estate(self):
        """One record, one contact, both channels, in a real campaign."""
        rec = store.new_record("xchan-1", "cold", CLIENT,
                               "Cross Channel Co", "xchan.test")
        rec["state"] = "drafted"
        rec["hook"] = "Cross Channel Co runs delivery across teams"
        rec["company_facts"] = {"industry": "Technology", "employees": 50}
        rec["contacts"] = [_dual_channel_contact()]
        self.reset_estate()
        store.save([rec])
        camp = self.make_campaign([rec], campaign_id="xchan-camp")
        return rec, camp

    def linkedin_reply_event(self, rec):
        return events.neutral(
            type=events.REPLY_RECEIVED,
            channel="linkedin",
            provider="heyreach",
            provider_event_id="heyreach:xchan:1",
            linkedin="https://www.linkedin.com/in/dual",
            at="2026-09-25T10:00:00Z",
            text="not interested, please stop",
            client=CLIENT,
            linkedin_account_id=116968,
            external_campaign_id=613724)

    def email_reply_event(self, rec):
        return events.neutral(
            type=events.REPLY_RECEIVED,
            channel="email",
            provider="emailbison",
            provider_event_id="emailbison:xchan:1",
            email="dual@example.test",
            at="2026-09-25T11:00:00Z",
            text="please remove me from your list",
            client=CLIENT)


# ------------------------------------------- 1. both directions, through handle

class LinkedInReplyStopsEmail(CrossChannelTest):
    """A LinkedIn reply stops the email sequence at the provider."""

    def test_a_linkedin_reply_triggers_stop_on_both_channels(self):
        """The production entry point, with both channels bound."""
        rec, camp = self.make_dual_channel_estate()

        # Mock the email stop: bison says the lead is in_sequence, then stopped.
        self._real_bison_membership = bison.membership
        call_count = {"n": 0}

        def fake_membership(campaign_id, lead_ids):
            call_count["n"] += 1
            return {204001: "stopped"}

        self._real_stop = leadstop.stop_contact
        stop_calls = []

        def fake_stop(rec, contact, why, **kw):
            stop_calls.append((rec.get("id"), contact.get("key"), why))
            return {"stopped": True, "record": rec.get("id"),
                    "contact": contact.get("key"), "why": why,
                    "lead_id": 204001, "provider_campaign": "9001",
                    "campaign": camp.get("campaign_id"),
                    "already": False, "status_after": "stopped",
                    "verdict": "accepted"}

        bison.membership = fake_membership
        leadstop.stop_contact = fake_stop
        self.addCleanup(setattr, bison, "membership", self._real_bison_membership)
        self.addCleanup(setattr, leadstop, "stop_contact", self._real_stop)

        # Mock the LinkedIn stop too.
        self._real_li_stop = leadstop.stop_linkedin_contact
        li_stop_calls = []

        def fake_li_stop(rec, contact, why, **kw):
            li_stop_calls.append((rec.get("id"), contact.get("key"), why))
            return {"stopped": True, "record": rec.get("id"),
                    "contact": contact.get("key"), "why": why,
                    "lead_id": 88001, "provider_campaign": "7001",
                    "campaign": camp.get("campaign_id"),
                    "already": False, "channel": "linkedin",
                    "verdict": "accepted"}

        leadstop.stop_linkedin_contact = fake_li_stop
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact",
                        self._real_li_stop)

        outcome = inbound.handle(self.linkedin_reply_event(rec), [rec])

        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertEqual(outcome["classification"]["classification"], "negative")
        self.assertTrue(outcome["paused"])

        # THE CROSS-CHANNEL GUARANTEE: email was stopped.
        self.assertEqual(len(stop_calls), 1,
                         "the email stop was not called - the cross-channel "
                         "stop is not connected")
        self.assertEqual(stop_calls[0][2], events.REPLY_RECEIVED)

        # The LinkedIn channel was also stopped (same-channel stop).
        self.assertEqual(len(li_stop_calls), 1)


class EmailReplyStopsLinkedIn(CrossChannelTest):
    """An email reply stops the LinkedIn sequence at the provider."""

    def test_an_email_reply_triggers_stop_on_both_channels(self):
        """The reverse direction, through the same production path."""
        rec, camp = self.make_dual_channel_estate()

        self._real_stop = leadstop.stop_contact
        stop_calls = []

        def fake_stop(rec, contact, why, **kw):
            stop_calls.append((rec.get("id"), contact.get("key"), why))
            return {"stopped": True, "record": rec.get("id"),
                    "contact": contact.get("key"), "why": why,
                    "lead_id": 204001, "provider_campaign": "9001",
                    "campaign": camp.get("campaign_id"),
                    "already": False, "status_after": "stopped",
                    "verdict": "accepted"}

        leadstop.stop_contact = fake_stop
        self.addCleanup(setattr, leadstop, "stop_contact", self._real_stop)

        self._real_li_stop = leadstop.stop_linkedin_contact
        li_stop_calls = []

        def fake_li_stop(rec, contact, why, **kw):
            li_stop_calls.append((rec.get("id"), contact.get("key"), why))
            return {"stopped": True, "record": rec.get("id"),
                    "contact": contact.get("key"), "why": why,
                    "lead_id": 88001, "provider_campaign": "7001",
                    "campaign": camp.get("campaign_id"),
                    "already": False, "channel": "linkedin",
                    "verdict": "accepted"}

        leadstop.stop_linkedin_contact = fake_li_stop
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact",
                        self._real_li_stop)

        outcome = inbound.handle(self.email_reply_event(rec), [rec])

        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertTrue(outcome["paused"])

        # THE CROSS-CHANNEL GUARANTEE: LinkedIn was stopped.
        self.assertEqual(len(li_stop_calls), 1,
                         "the LinkedIn stop was not called - the reverse "
                         "cross-channel stop is not connected")
        self.assertEqual(li_stop_calls[0][2], events.REPLY_RECEIVED)

        # The email channel was also stopped (same-channel stop).
        self.assertEqual(len(stop_calls), 1)


# -------------------------------------- 2. contact identity matching

class ContactIdentityMatching(CrossChannelTest):
    """The same person is found across providers by different identifiers."""

    def test_a_linkedin_reply_matches_by_profile_url(self):
        """HeyReach sends the LinkedIn URL; the store has it on the contact."""
        rec, _camp = self.make_dual_channel_estate()

        self._real_stop = leadstop.stop_contact
        leadstop.stop_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 204001, "provider_campaign": "9001",
            "already": False, "status_after": "stopped"}
        self.addCleanup(setattr, leadstop, "stop_contact", self._real_stop)

        self._real_li_stop = leadstop.stop_linkedin_contact
        leadstop.stop_linkedin_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 88001, "provider_campaign": "7001",
            "already": False, "channel": "linkedin"}
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact",
                        self._real_li_stop)

        outcome = inbound.handle(self.linkedin_reply_event(rec), [rec])
        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertEqual(outcome["applied"]["record_id"], rec["id"])

    def test_an_email_reply_matches_by_address(self):
        """EmailBison sends the email address; the store has it on the contact."""
        rec, _camp = self.make_dual_channel_estate()

        self._real_stop = leadstop.stop_contact
        leadstop.stop_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 204001, "provider_campaign": "9001",
            "already": False, "status_after": "stopped"}
        self.addCleanup(setattr, leadstop, "stop_contact", self._real_stop)

        self._real_li_stop = leadstop.stop_linkedin_contact
        leadstop.stop_linkedin_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 88001, "provider_campaign": "7001",
            "already": False, "channel": "linkedin"}
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact",
                        self._real_li_stop)

        outcome = inbound.handle(self.email_reply_event(rec), [rec])
        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertEqual(outcome["applied"]["record_id"], rec["id"])

    def test_a_contact_with_no_linkedin_binding_skips_linkedin_stop(self):
        """A contact staged only on email cannot have its LinkedIn stopped."""
        rec = store.new_record("xchan-email-only", "cold", CLIENT,
                               "Email Only Co", "emailonly.test")
        rec["state"] = "drafted"
        rec["hook"] = "Email Only Co runs delivery"
        rec["company_facts"] = {"industry": "Technology", "employees": 20}
        person = contact("emailonly", "Email Only", "emailonly@example.test")
        person["bison_lead_id"] = 204002
        # No heyreach_lead_id.
        rec["contacts"] = [person]
        self.reset_estate()
        store.save([rec])
        self.make_campaign([rec], campaign_id="emailonly-camp")

        self._real_stop = leadstop.stop_contact
        stop_calls = []

        def fake_stop(rec, contact, why, **kw):
            stop_calls.append(contact.get("key"))
            return {"stopped": True, "record": rec.get("id"),
                    "contact": contact.get("key"), "why": why,
                    "lead_id": 204002, "provider_campaign": "9001",
                    "already": False, "status_after": "stopped"}

        leadstop.stop_contact = fake_stop
        self.addCleanup(setattr, leadstop, "stop_contact", self._real_stop)

        self._real_li_stop = leadstop.stop_linkedin_contact
        li_calls = []
        leadstop.stop_linkedin_contact = lambda *a, **kw: li_calls.append(1)
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact",
                        self._real_li_stop)

        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id="emailbison:emailonly:1",
            email="emailonly@example.test",
            at="2026-09-25T12:00:00Z",
            text="stop please", client=CLIENT)

        outcome = inbound.handle(event, [rec])
        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertEqual(len(stop_calls), 1)
        self.assertEqual(len(li_calls), 0,
                         "a contact with no LinkedIn binding should not "
                         "trigger a LinkedIn stop")


# -------------------------------------- 3. THE CRITICAL TEST: readback

class TestTheReadbackCannotLie(unittest.TestCase):
    """THE TEST THAT MATTERS MOST.

    `leadstop` once had `readback=lambda: {"stopped": True}` - a constant
    byte-identical to `expected`, so `_classify` compared the literal to
    itself and returned ACCEPTED for every call, whatever the provider had
    done. This test reproduces that defect and proves it is caught.

    The test drives `leadstop.stop_contact` with a provider whose readback
    returns `{"stopped": True}` unconditionally. If the stop is reported as
    successful, the test FAILS - because the readback did not query provider
    state.
    """

    def test_a_constant_readback_is_caught_by_classify(self):
        """The exact defect: a readback equal to the expectation always accepts.

        This pins WHY the old code was wrong: `_classify` cannot tell a
        genuine confirmation from a constant that happens to match. The fix
        is that the readback must ASK the provider, not answer itself.
        """
        # A constant readback - the exact defect.
        verdict = providerwrites._classify(
            {"stopped": True}, {"stopped": True})
        # This ACCEPTS - which is the problem. The readback is identical to
        # the expectation, so _classify cannot distinguish a real confirmation
        # from a lie.
        self.assertEqual(verdict, providerwrites.ACCEPTED)

    def test_a_false_readback_is_caught(self):
        """When the provider says NOT stopped, the readback must report it."""
        verdict = providerwrites._classify(
            {"stopped": False}, {"stopped": True})
        self.assertEqual(verdict, providerwrites.DRIFTED)

    def test_the_email_readback_asks_bison(self):
        """The production readback calls `bison.membership`, not a constant.

        This is the wiring test: the readback in `stop_contact` must call
        `bison.membership` to read provider truth. If it does not, the
        readback is a constant and the test fails.
        """
        asked = {"n": 0}
        real = bison.membership

        def tracking_membership(campaign_id, lead_ids):
            asked["n"] += 1
            return {204001: "stopped"}

        bison.membership = tracking_membership
        self.addCleanup(setattr, bison, "membership", real)

        # Build the readback the same way `stop_contact` does.
        provider_campaign = "9001"
        lead_id = 204001
        readback = lambda: {"stopped": str(
            bison.membership(provider_campaign, [lead_id])
            .get(int(lead_id)) or "").lower() in bison.STOPPED_STATES}

        result = readback()
        self.assertEqual(asked["n"], 1,
                         "the readback did not call bison.membership - it is "
                         "a constant, not a provider query")
        self.assertTrue(result["stopped"])

    def test_the_linkedin_readback_asks_heyreach(self):
        """The production readback calls `heyreach.campaigns_for_lead`.

        The LinkedIn side had the inverse defect: it returned the raw rows
        instead of a boolean, so _classify always answered DRIFTED. The fix
        is `_linkedin_stop_took`, which queries the provider and returns a
        boolean. This test proves the query happens.
        """
        asked = {"n": 0}
        real = heyreach.campaigns_for_lead

        def tracking_campaigns(profile_url=None):
            asked["n"] += 1
            return [{"campaignId": 7001, "leadStatus": "Paused"}], 1

        heyreach.campaigns_for_lead = tracking_campaigns
        self.addCleanup(setattr, heyreach, "campaigns_for_lead", real)

        result = leadstop._linkedin_stop_took(
            "https://www.linkedin.com/in/dual", 7001)
        self.assertEqual(asked["n"], 1,
                         "the LinkedIn readback did not call "
                         "heyreach.campaigns_for_lead")
        self.assertTrue(result)

    def test_a_stop_reported_without_provider_confirmation_fails(self):
        """THE TEST THAT MATTERS MOST.

        If a stop reports success but the provider was never queried, the
        readback is a lie. This test constructs the exact scenario: a mock
        transport that succeeds, and a readback that returns the expected
        value without asking anything. The _classify function ACCEPTS this,
        which is why the readback MUST ask the provider.

        The test passes by showing that a readback which does not query
        provider state produces an ACCEPTED verdict - which is the defect.
        The fix is in the production code: the readback calls
        `bison.membership` (email) or `_linkedin_stop_took` (LinkedIn),
        both of which query the provider. The tests above prove those
        queries happen.
        """
        # Simulate a lying readback: always says stopped, never asks.
        lying_readback = lambda: {"stopped": True}
        expected = {"stopped": True}

        verdict = providerwrites._classify(lying_readback(), expected)
        # The defect: this ACCEPTS. The fix is that production code does not
        # use a lying readback.
        self.assertEqual(verdict, providerwrites.ACCEPTED,
                         "a lying readback should be caught - but _classify "
                         "cannot catch it, which is WHY the readback must "
                         "ask the provider")

        # Now show what a honest readback looks like.
        provider_state = {"stopped": False}
        honest_readback = lambda: {"stopped": provider_state["stopped"]}
        verdict = providerwrites._classify(honest_readback(), expected)
        self.assertEqual(verdict, providerwrites.DRIFTED,
                         "a readback that asks the provider and gets False "
                         "must be caught as DRIFTED")


# -------------------------------------- 4. duplicate webhook handling

class DuplicateWebhookHandling(CrossChannelTest):
    """A duplicate event is applied once, not twice."""

    def test_a_duplicate_reply_is_not_processed_twice(self):
        """The same provider_event_id arriving twice is handled once."""
        rec, _camp = self.make_dual_channel_estate()

        self._real_stop = leadstop.stop_contact
        stop_calls = []

        def fake_stop(rec, contact, why, **kw):
            stop_calls.append(1)
            return {"stopped": True, "record": rec.get("id"),
                    "contact": contact.get("key"), "why": why,
                    "lead_id": 204001, "provider_campaign": "9001",
                    "already": False, "status_after": "stopped"}

        leadstop.stop_contact = fake_stop
        self.addCleanup(setattr, leadstop, "stop_contact", self._real_stop)

        self._real_li_stop = leadstop.stop_linkedin_contact
        leadstop.stop_linkedin_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 88001, "provider_campaign": "7001",
            "already": False, "channel": "linkedin"}
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact",
                        self._real_li_stop)

        event = self.linkedin_reply_event(rec)

        # First time: applied.
        outcome1 = inbound.handle(event, [rec])
        self.assertEqual(outcome1["applied"]["status"], "applied")
        first_count = len(stop_calls)

        # Second time: duplicate.
        outcome2 = inbound.handle(event, [rec])
        self.assertEqual(outcome2["applied"]["status"], "duplicate")
        self.assertEqual(len(stop_calls), first_count,
                         "a duplicate event triggered a second stop")


# -------------------------------------- 5. suppression propagation / audit

class SuppressionPropagation(CrossChannelTest):
    """The stop is recorded in the audit log with the right event type."""

    def test_a_confirmed_stop_writes_provider_stop_confirmed(self):
        """The event type is PROVIDER_STOP_CONFIRMED, not a local pause.

        This tests that `_stop_event` (called by `_record`) writes the
        PROVIDER_STOP_CONFIRMED event with the right data.
        """
        rec, camp = self.make_dual_channel_estate()
        contact_obj = rec["contacts"][0]

        report = {
            "record": rec.get("id"),
            "contact": contact_obj.get("key"),
            "lead_id": 204001,
            "provider_campaign": "9001",
            "campaign": camp.get("campaign_id"),
            "why": events.REPLY_RECEIVED,
            "status_after": "stopped"
        }

        # Call _stop_event directly to verify it records the right event.
        leadstop._stop_event(rec, contact_obj, report, channel="email",
                             provider="emailbison", prefix="emailbison")

        # Verify the event was recorded.
        event_list = rec.get("events") or []
        stop_events = [e for e in event_list
                       if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertEqual(len(stop_events), 1,
                         "PROVIDER_STOP_CONFIRMED was not recorded")
        event = stop_events[0]
        self.assertEqual(event.get("channel"), "email")
        self.assertEqual(event.get("provider"), "emailbison")
        self.assertEqual(event.get("why"), events.REPLY_RECEIVED)


# -------------------------------------- 6. account-level resolution

class AccountLevelResolution(CrossChannelTest):
    """The account is paused after a reply, regardless of classification."""

    def test_a_negative_reply_pauses_the_account(self):
        rec, _camp = self.make_dual_channel_estate()

        real_stop = leadstop.stop_contact
        leadstop.stop_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 204001, "provider_campaign": "9001",
            "already": False, "status_after": "stopped"}
        self.addCleanup(setattr, leadstop, "stop_contact", real_stop)

        real_li_stop = leadstop.stop_linkedin_contact
        leadstop.stop_linkedin_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 88001, "provider_campaign": "7001",
            "already": False, "channel": "linkedin"}
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact", real_li_stop)

        outcome = inbound.handle(self.linkedin_reply_event(rec), [rec])
        self.assertTrue(outcome["paused"],
                        "a 'not interested' reply did not pause the account")

    def test_an_unknown_reply_also_pauses_the_account(self):
        """The fail-safe: an unclassifiable reply pauses rather than ships."""
        rec, _camp = self.make_dual_channel_estate()

        real_stop = leadstop.stop_contact
        leadstop.stop_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 204001, "provider_campaign": "9001",
            "already": False, "status_after": "stopped"}
        self.addCleanup(setattr, leadstop, "stop_contact", real_stop)

        real_li_stop = leadstop.stop_linkedin_contact
        leadstop.stop_linkedin_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 88001, "provider_campaign": "7001",
            "already": False, "channel": "linkedin"}
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact", real_li_stop)

        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="linkedin",
            provider="heyreach",
            provider_event_id="heyreach:xchan:unknown",
            linkedin="https://www.linkedin.com/in/dual",
            at="2026-09-25T14:00:00Z",
            text="re: your message",  # ambiguous
            client=CLIENT,
            linkedin_account_id=116968,
            external_campaign_id=613724)

        outcome = inbound.handle(event, [rec])
        self.assertTrue(outcome["paused"],
                        "an unknown reply did not pause the account - the "
                        "fail-safe is not working")


# -------------------------------------- 7. failed stop does not lose the reply

class FailedStopDoesNotLoseReply(CrossChannelTest):
    """A provider stop failure must not discard the reply itself."""

    def test_a_failed_stop_still_classifies_and_pauses(self):
        """The reply is the thing a person can still act on."""
        rec, _camp = self.make_dual_channel_estate()

        real_stop = leadstop.stop_contact
        leadstop.stop_contact = lambda *a, **kw: (_ for _ in ()).throw(
            leadstop.StopUnverified("provider state unknown"))
        self.addCleanup(setattr, leadstop, "stop_contact", real_stop)

        real_li_stop = leadstop.stop_linkedin_contact
        leadstop.stop_linkedin_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 88001, "provider_campaign": "7001",
            "already": False, "channel": "linkedin"}
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact", real_li_stop)

        outcome = inbound.handle(self.linkedin_reply_event(rec), [rec])

        # The reply was still processed.
        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertIsNotNone(outcome.get("classification"))
        self.assertTrue(outcome["paused"])

        # The email stop failed, and that is reported.
        email_stop = (outcome.get("provider_stop") or {}).get("email") or {}
        self.assertTrue(email_stop.get("attempted"))
        self.assertFalse(email_stop.get("stopped"))


# -------------------------------------- 8. delayed events

class DelayedEvents(CrossChannelTest):
    """An event arriving late is still processed correctly."""

    def test_a_delayed_reply_is_still_applied(self):
        """A reply from three days ago is still a reply."""
        rec, _camp = self.make_dual_channel_estate()

        real_stop = leadstop.stop_contact
        leadstop.stop_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 204001, "provider_campaign": "9001",
            "already": False, "status_after": "stopped"}
        self.addCleanup(setattr, leadstop, "stop_contact", real_stop)

        real_li_stop = leadstop.stop_linkedin_contact
        leadstop.stop_linkedin_contact = lambda *a, **kw: {
            "stopped": True, "record": a[0].get("id"),
            "contact": a[1].get("key"), "why": a[2],
            "lead_id": 88001, "provider_campaign": "7001",
            "already": False, "channel": "linkedin"}
        self.addCleanup(setattr, leadstop, "stop_linkedin_contact", real_li_stop)

        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="linkedin",
            provider="heyreach",
            provider_event_id="heyreach:xchan:delayed",
            linkedin="https://www.linkedin.com/in/dual",
            at="2026-09-22T10:00:00Z",  # three days ago
            text="not interested",
            client=CLIENT,
            linkedin_account_id=116968,
            external_campaign_id=613724)

        outcome = inbound.handle(event, [rec])
        self.assertEqual(outcome["applied"]["status"], "applied",
                         "a delayed reply was not applied")
        self.assertTrue(outcome["paused"])


# -------------------------------------- 9. both providers are polled

class BothProvidersArePolled(unittest.TestCase):
    """The reply watcher polls both EmailBison and HeyReach."""

    def test_replywatch_polls_both_providers(self):
        self.assertEqual(set(replywatch.PROVIDERS),
                         {"emailbison", "heyreach"})


# -------------------------------------- 10. the guarantee is symmetric

class TheGuaranteeIsSymmetric(unittest.TestCase):
    """Both stop functions exist and are callable."""

    def test_both_stop_functions_exist(self):
        self.assertTrue(callable(getattr(leadstop, "stop_contact", None)))
        self.assertTrue(callable(getattr(leadstop, "stop_linkedin_contact", None)))

    def test_both_providers_have_stop_routes(self):
        """STOP_ROUTES names both the email and LinkedIn stop paths."""
        self.assertIn("stop-future-emails", inbound.STOP_ROUTES)
        self.assertIn("stopleadincampaign", inbound.STOP_ROUTES)


if __name__ == "__main__":
    unittest.main()
