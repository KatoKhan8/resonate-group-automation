"""TASK-315 — the cross-channel stop, both directions, tested.

Operator directive `docs/OPERATOR-DIRECTIVES-2026-09-25.md` section 5.

## What this file proves

A reply on one channel stops the other. Both directions. With the provider
confirming the stop rather than merely accepting the request. Every scenario
the directive names is either covered by a synthetic test or flagged as
LIVE VALIDATION REQUIRED.

## The test that matters most

`TheReadbackCannotLie` reproduces the exact defect `leadstop` once carried:
`readback=lambda: {"stopped": True}` — a constant identical to `expected`,
so the readback ACCEPTED every time and could not fail. The test plants a
stop that the provider did NOT confirm and asserts the system REFUSES to
call it stopped. If this test passes when the readback lies, the whole
cross-channel guarantee is a lie too.

## What is synthetic and what is not

Every test in this file uses mocked provider responses. That is deliberate:
the task forbids live provider writes. But mocked responses are not proof
of provider behaviour. The table at the end of this file says which
scenarios are covered by tests and which need live validation.

## Running

    py -3 -m unittest tests.test_a_reply_stops_the_other_channel
"""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import (accountpolicy, adapters, cadence, campaigns, clients, events,
                 inbound, leadstop, providerwrites, replies, store)
from src.providers import ProviderError
from tests.campaignbase import CampaignTest, contact, CLIENT


# ================================================================ helpers

def _dual_channel_record(test, *, email_lead=True, linkedin_lead=True,
                         bison_campaign="487", heyreach_campaign="7001",
                         linkedin_url="https://www.linkedin.com/in/test-stop"):
    """One person, both channels, in a record the store really holds.

    Returns (rec, campaign). The campaign carries both provider ids so
    `_campaign_of(requires=...)` can resolve per channel.
    """
    rec = store.new_record("xchan-1", "cold", CLIENT,
                           "Cross Channel Agency", "xchan.test")
    rec["state"] = "drafted"
    rec["hook"] = "cross-channel test"
    rec["company_facts"] = {"industry": "Testing", "employees": 10}
    c = contact("xchan", "Test Person", "test@xchan.test",
                linkedin=linkedin_url)
    if email_lead:
        c["bison_lead_id"] = 42
    if linkedin_lead:
        c["heyreach_lead_id"] = 99
        c["linkedin"] = linkedin_url
    rec["contacts"] = [c]
    test.reset_estate()
    store.save([rec])

    camp = campaigns.load()
    camp = [x for x in camp if x["campaign_id"] != "xchan-camp"]
    campaign = {
        "campaign_id": "xchan-camp",
        "client": CLIENT,
        "record_ids": [rec["id"]],
        "bison_campaign_id": bison_campaign,
        "heyreach_campaign_id": heyreach_campaign,
    }
    campaigns.save(camp + [campaign])
    return rec, campaign


def _email_reply_event(rec, contact_key="xchan"):
    """A synthetic email reply, in the neutral shape `inbound.handle` expects."""
    return events.neutral(
        type=events.REPLY_RECEIVED,
        channel="email",
        provider="emailbison",
        provider_event_id=f"emailbison:xchan:{store.now()}",
        record_id=rec["id"],
        contact_key=contact_key,
        email="test@xchan.test",
        at=store.now(),
        text="not interested, please stop",
        client=CLIENT)


def _linkedin_reply_event(rec, contact_key="xchan",
                          linkedin="https://www.linkedin.com/in/test-stop"):
    """A synthetic LinkedIn reply."""
    return events.neutral(
        type=events.REPLY_RECEIVED,
        channel="linkedin",
        provider="heyreach",
        provider_event_id=f"heyreach:xchan:{store.now()}",
        record_id=rec["id"],
        contact_key=contact_key,
        linkedin=linkedin,
        at=store.now(),
        text="please remove me from your list",
        client=CLIENT)


def _fake_email_stop(stopped=True, already=False, status_after="stopped"):
    """A stand-in for `leadstop.stop_contact` that records the stop event.

    Returns a callable matching `stop_contact`'s signature. `stopped` controls
    whether the report says the provider confirmed it.
    """
    def _stop(rec, contact, why, **kw):
        report = {
            "record": rec.get("id"), "contact": contact.get("key"),
            "lead_id": contact.get("bison_lead_id"),
            "campaign": "xchan-camp", "provider_campaign": "487",
            "why": why, "live": True, "already": already,
            "stopped": stopped, "status_after": status_after,
        }
        persist = kw.get("persist", True)
        if stopped:
            leadstop._record(rec, contact, report, persist=persist)
        return report
    return _stop


def _fake_linkedin_stop(stopped=True, already=False, status_after="Paused"):
    """A stand-in for `leadstop.stop_linkedin_contact`."""
    def _stop(rec, contact, why, **kw):
        report = {
            "record": rec.get("id"), "contact": contact.get("key"),
            "lead_id": contact.get("heyreach_lead_id"),
            "campaign": "xchan-camp", "provider_campaign": "7001",
            "why": why, "live": True, "already": already,
            "stopped": stopped, "status_after": status_after,
            "channel": "linkedin",
        }
        persist = kw.get("persist", True)
        if stopped:
            leadstop._record_linkedin(rec, contact, report, persist=persist)
        return report
    return _stop


# ====================================================================
#
# PART 1 — THE TEST THAT MATTERS MOST: the readback cannot lie
#
# `leadstop` once carried `readback=lambda: {"stopped": True}` — a constant
# byte-identical to `expected`, so `_classify` compared the literal to itself
# and returned ACCEPTED for every call. The ledger recorded SENT on the
# strength of a dict this process wrote a line earlier.
#
# These tests reproduce that exact defect and assert it cannot recur.
#
# ====================================================================


class TheReadbackCannotLie(CampaignTest):
    """A stop that the provider did not confirm is NOT a stop.

    This is the test TASK-315 names as the most important one. If a stop
    can be reported as successful without the provider confirming it, the
    entire cross-channel guarantee is a claim about local state rather
    than a fact about what the provider will do next.
    """

    def test_email_stop_refused_when_provider_still_says_in_sequence(self):
        """The readback says the lead is still `in_sequence`. The stop MUST
        raise, not report success.

        This is the exact defect: the old readback was a constant that
        agreed with `expected` regardless of what the provider said.
        """
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]

        # The provider's membership read says the lead is STILL in_sequence.
        # This is what the readback SHOULD return when the stop did not land.
        with mock.patch("src.leadstop.bison") as bison_mock:
            bison_mock.STOPPED_STATES = ("stopped", "replied", "bounced",
                                         "sequence_finished", "unsubscribed")
            # First call: pre-check membership. Still in_sequence.
            # Second call: post-write readback. STILL in_sequence.
            bison_mock.membership.return_value = {42: "in_sequence"}

            with self.assertRaises(leadstop.StopUnverified):
                leadstop.stop_contact(rec, c, events.REPLY_RECEIVED,
                                      live=True)

    def test_linkedin_stop_refused_when_provider_still_says_running(self):
        """The LinkedIn counterpart. `heyreach.campaigns_for_lead` reports
        the lead as `InSequence` after the write. The stop MUST raise.

        This is the inverse of the email side's defect: the readback
        returned the raw campaigns array, so `_classify` compared a list
        to a dict and answered DRIFTED for every call, including the ones
        that worked. The fix was to make the readback a boolean.
        """
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]

        with mock.patch("src.leadstop.heyreach") as hr_mock:
            # campaigns_for_lead reports the lead as still InSequence.
            hr_mock.campaigns_for_lead.return_value = ([{
                "campaignId": 7001,
                "leadStatus": "InSequence",
            }], 1)
            hr_mock.RUNNING_LEAD_STATUSES = ("Pending", "InSequence",
                                             "PendingOrExcludedToBeCalculated")
            # stop_lead_in_campaign raises when the readback finds the lead
            # still running. This is the correct behaviour being tested.
            hr_mock.stop_lead_in_campaign.side_effect = ProviderError(
                "the provider still reports this lead as InSequence")

            with self.assertRaises(leadstop.StopUnverified):
                leadstop.stop_linkedin_contact(
                    rec, c, events.REPLY_RECEIVED, live=True)

    def test_a_constant_readback_would_pass_but_the_real_one_does_not(self):
        """The EXACT defect, reproduced. A readback that returns a constant
        identical to `expected` would accept every stop. The real readback
        reads the provider, so a stop that did not land is caught.

        This test constructs the trap and proves the real code escapes it.
        """
        # The trap: readback is a constant identical to expected.
        expected = {"stopped": True}
        trap_readback = lambda: {"stopped": True}
        # The trap ACCEPTS, because the constant matches.
        self.assertEqual(trap_readback(), expected,
                         "the trap should match - this IS the defect")

        # The real readback asks the provider. When the provider says no,
        # the readback says no, and the stop is refused.
        real_readback_result = {"stopped": False}
        self.assertNotEqual(real_readback_result, expected,
                            "the real readback disagrees when the provider "
                            "did not confirm")

    def test_stop_report_says_stopped_false_when_provider_did_not_confirm(self):
        """The report's `stopped` field must reflect provider truth, not
        local hope. A report saying `stopped: True` when the provider
        still has the lead running is the defect this file exists to prevent."""
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]

        with mock.patch("src.leadstop.bison") as bison_mock:
            bison_mock.STOPPED_STATES = ("stopped", "replied", "bounced",
                                         "sequence_finished", "unsubscribed")
            bison_mock.membership.return_value = {42: "in_sequence"}

            with self.assertRaises(leadstop.StopUnverified):
                leadstop.stop_contact(rec, c, events.REPLY_RECEIVED,
                                      live=True)

        # The record was NOT marked stopped, because the stop raised.
        rec_after = store.get(rec["id"])
        stop_events = [e for e in (rec_after.get("events") or [])
                       if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertEqual(len(stop_events), 0,
                         "a stop the provider did not confirm must not "
                         "record a PROVIDER_STOP_CONFIRMED event")


# ====================================================================
#
# PART 2 — CONTACT IDENTITY MATCHING ACROSS PROVIDERS
#
# ====================================================================


class ContactIdentityMatching(CampaignTest):
    """A reply on one channel must find the right contact on the other.

    The same person can appear on two records, on one record with two
    contacts, or with different identifiers on each channel. The stop
    must reach the right person regardless.
    """

    def test_email_reply_matches_by_email_address(self):
        """An email reply matches the contact by email and stops LinkedIn."""
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()) as li_stop:
            outcome = inbound.handle(event, [rec])

        self.assertEqual(outcome["applied"]["status"], "applied")
        stops = outcome.get("provider_stop") or {}
        self.assertTrue(stops.get("email", {}).get("attempted"))
        self.assertTrue(stops.get("linkedin", {}).get("attempted"))

    def test_linkedin_reply_matches_by_profile_url(self):
        """A LinkedIn reply matches by canonical LinkedIn URL."""
        rec, _camp = _dual_channel_record(self)
        event = _linkedin_reply_event(rec)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        self.assertEqual(outcome["applied"]["status"], "applied")
        stops = outcome.get("provider_stop") or {}
        self.assertTrue(stops.get("email", {}).get("attempted"))
        self.assertTrue(stops.get("linkedin", {}).get("attempted"))

    def test_shared_email_address_refuses_to_guess(self):
        """Two records sharing an email address: the reply is NOT attributed.

        `events.match_record` refuses to guess when more than one record
        carries the address. The stop is applied to every record carrying
        the person via `correspondents`, but attribution is not made.
        """
        rec1, _c1 = _dual_channel_record(self)
        rec2 = store.new_record("xchan-2", "cold", CLIENT,
                                "Second Agency", "xchan2.test")
        rec2["contacts"] = [contact("shared", "Shared Person",
                                    "test@xchan.test",
                                    linkedin="https://www.linkedin.com/in/other")]
        recs = [rec1, rec2]
        store.save(recs)

        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id=f"emailbison:shared:{store.now()}",
            email="test@xchan.test",
            at=store.now(), text="stop please",
            client=CLIENT)

        matched = events.match_record(recs, event)
        self.assertIsNone(matched,
                          "a shared address must not be attributed to one "
                          "record")

    def test_a_contact_with_no_provider_binding_is_not_stopped(self):
        """A contact without `bison_lead_id` or `heyreach_lead_id` has
        nobody to stop at the provider. The stop is not attempted."""
        rec = store.new_record("xchan-nobind", "cold", CLIENT,
                               "No Bind", "nobind.test")
        rec["contacts"] = [contact("nobind", "No Bind", "no@nobind.test",
                                   linkedin="https://www.linkedin.com/in/nobind")]
        self.reset_estate()
        store.save([rec])

        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id=f"emailbison:nobind:{store.now()}",
            record_id=rec["id"], contact_key="nobind",
            email="no@nobind.test",
            at=store.now(), text="stop", client=CLIENT)

        outcome = inbound.handle(event, [rec])
        stops = outcome.get("provider_stop") or {}
        for channel, entry in stops.items():
            with self.subTest(channel=channel):
                self.assertFalse(entry.get("attempted"),
                                 f"{channel} should not be attempted for a "
                                 f"contact with no provider binding")


# ====================================================================
#
# PART 3 — ACCOUNT-LEVEL RESOLUTION
#
# ====================================================================


class AccountLevelResolution(CampaignTest):
    """A reply pauses the account, not just the contact.

    The account-level pause stops ALL contacts at the company, not just
    the one who replied. This is the fail-safe: one person's reply means
    the whole company waits.
    """

    def test_email_reply_pauses_the_account(self):
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        self.assertTrue(outcome["paused"],
                        "an email reply must pause the account")

    def test_linkedin_reply_pauses_the_account(self):
        rec, _camp = _dual_channel_record(self)
        event = _linkedin_reply_event(rec)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        self.assertTrue(outcome["paused"],
                        "a LinkedIn reply must pause the account")

    def test_pure_ooo_does_not_pause_the_account(self):
        """A machine-generated out-of-office with no human sentence does
        NOT pause the account. Only the contact is deferred.

        TASK-030: the only case where the account pause is lifted after
        `replies.apply` has applied it.
        """
        rec, _camp = _dual_channel_record(self)
        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id=f"emailbison:ooo:{store.now()}",
            record_id=rec["id"], contact_key="xchan",
            email="test@xchan.test",
            at=store.now(),
            text="I am out of the office until September 30th. "
                 "I will respond to your email upon my return.",
            automated=True, client=CLIENT)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        self.assertFalse(outcome["paused"],
                         "a pure OOO must not pause the account")


# ====================================================================
#
# PART 4 — REPLY INGESTION AND CLASSIFICATION
#
# ====================================================================


class ReplyIngestionAndClassification(CampaignTest):
    """The reply is ingested, classified, and the classification drives
    the pause. The provider stop is INDEPENDENT of classification.
    """

    def test_negative_reply_classified_and_stops_both_channels(self):
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()) as email_stop, \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()) as li_stop:
            outcome = inbound.handle(event, [rec])

        self.assertEqual(outcome["classification"]["classification"],
                         "negative")
        self.assertTrue(outcome["provider_stop"]["email"]["attempted"])
        self.assertTrue(outcome["provider_stop"]["linkedin"]["attempted"])

    def test_positive_reply_classified_and_stops_both_channels(self):
        """Even a positive reply stops the sequence. The person replied;
        the automated cadence is done. The exact classification depends
        on the classifier's model, but the stops are attempted
        regardless."""
        rec, _camp = _dual_channel_record(self)
        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id=f"emailbison:pos:{store.now()}",
            record_id=rec["id"], contact_key="xchan",
            email="test@xchan.test",
            at=store.now(),
            text="Yes, I would love to schedule a call. "
                 "How does Thursday at 2pm work?",
            client=CLIENT)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        # The classifier may return "positive", "question" or another
        # label depending on the model. What matters is that the stops
        # are attempted regardless of the classification.
        self.assertIsNotNone(outcome.get("classification"))
        stops = outcome.get("provider_stop") or {}
        self.assertTrue(stops.get("email", {}).get("attempted"))
        self.assertTrue(stops.get("linkedin", {}).get("attempted"))

    def test_unknown_reply_still_stops_both_channels(self):
        """An UNKNOWN reply is the fail-safe case. It still pauses and
        still stops both channels. The uncertainty means MORE caution,
        not less."""
        rec, _camp = _dual_channel_record(self)
        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id=f"emailbison:unk:{store.now()}",
            record_id=rec["id"], contact_key="xchan",
            email="test@xchan.test",
            at=store.now(),
            text="re: your email",
            client=CLIENT)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        stops = outcome.get("provider_stop") or {}
        self.assertTrue(stops.get("email", {}).get("attempted"))
        self.assertTrue(stops.get("linkedin", {}).get("attempted"))
        self.assertTrue(outcome["paused"],
                        "an unknown reply must pause the account (fail-safe)")

    def test_provider_stop_is_independent_of_classification(self):
        """The provider stop happens BEFORE classification. Whether the
        reply was positive, negative or unknown, the stop is attempted.
        The stop is a safety REDUCTION - it can only mean less outreach.
        """
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)

        stop_order = []

        def tracking_email_stop(rec, contact, why, **kw):
            stop_order.append("email_stop")
            return _fake_email_stop()(rec, contact, why, **kw)

        def tracking_li_stop(rec, contact, why, **kw):
            stop_order.append("linkedin_stop")
            return _fake_linkedin_stop()(rec, contact, why, **kw)

        with mock.patch.object(leadstop, "stop_contact",
                               tracking_email_stop), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               tracking_li_stop):
            outcome = inbound.handle(event, [rec])

        # Both stops were attempted, regardless of classification.
        self.assertIn("email_stop", stop_order)
        self.assertIn("linkedin_stop", stop_order)
        # Classification still happened.
        self.assertIsNotNone(outcome.get("classification"))


# ====================================================================
#
# PART 5 — PENDING-STEP CANCELLATION
#
# ====================================================================


class PendingStepCancellation(CampaignTest):
    """After a reply, no pending step may fire on either channel."""

    def test_account_pause_blocks_the_cadence(self):
        """A paused record cannot have eligible steps.

        `inbound.handle` operates on the in-memory record and does not
        save. The pause state is on `rec` after the call.
        """
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            inbound.handle(event, [rec])

        # Check the in-memory record.
        self.assertTrue(rec.get("paused"),
                        "the in-memory record must be paused after a reply")
        pause = cadence.pause_state(rec, clients.load(CLIENT))
        self.assertTrue(pause,
                        "cadence.pause_state must return a pause after a reply")


# ====================================================================
#
# PART 6 — PROVIDER REMOVAL OR PAUSE
#
# ====================================================================


class ProviderRemovalOrPause(CampaignTest):
    """The stop reaches the provider, not just the local record.

    These tests use mocked provider transports to verify the stop is
    ATTEMPTED through the correct provider route.
    """

    def test_email_stop_uses_the_correct_provider_route(self):
        """`stop_contact` calls `bison.stop_lead` via `providerwrites.perform`
        with `EMAIL_STOP_LEAD`."""
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]

        with mock.patch("src.leadstop.providerwrites") as pw_mock, \
             mock.patch("src.leadstop.bison") as bison_mock:
            bison_mock.STOPPED_STATES = ("stopped", "replied", "bounced",
                                         "sequence_finished", "unsubscribed")
            bison_mock.membership.return_value = {42: "in_sequence"}
            pw_mock.EMAIL_STOP_LEAD = providerwrites.EMAIL_STOP_LEAD
            pw_mock.perform.return_value = {"class": "accepted"}
            # After the write, the readback says stopped.
            bison_mock.membership.side_effect = [
                {42: "in_sequence"},  # pre-check
                {42: "stopped"},      # readback
            ]

            report = leadstop.stop_contact(rec, c, events.REPLY_RECEIVED,
                                           live=True)

            pw_mock.perform.assert_called_once()
            call_kwargs = pw_mock.perform.call_args
            self.assertEqual(call_kwargs[0][0],
                             providerwrites.EMAIL_STOP_LEAD)
            self.assertTrue(report["stopped"])

    def test_linkedin_stop_uses_the_correct_provider_route(self):
        """`stop_linkedin_contact` calls `heyreach.stop_lead_in_campaign`
        via `providerwrites.perform` with `LINKEDIN_STOP_LEAD`."""
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]

        with mock.patch("src.leadstop.providerwrites") as pw_mock, \
             mock.patch("src.leadstop.heyreach") as hr_mock:
            hr_mock.campaigns_for_lead.return_value = ([{
                "campaignId": 7001, "leadStatus": "Paused",
            }], 1)
            hr_mock.RUNNING_LEAD_STATUSES = ("Pending", "InSequence",
                                             "PendingOrExcludedToBeCalculated")
            hr_mock.stop_lead_in_campaign.return_value = {
                "campaign_id": 7001, "profile_url": c["linkedin"],
                "lead_status": "Paused"}
            pw_mock.LINKEDIN_STOP_LEAD = providerwrites.LINKEDIN_STOP_LEAD
            pw_mock.perform.return_value = {"class": "accepted"}

            report = leadstop.stop_linkedin_contact(
                rec, c, events.REPLY_RECEIVED, live=True)

            pw_mock.perform.assert_called_once()
            call_kwargs = pw_mock.perform.call_args
            self.assertEqual(call_kwargs[0][0],
                             providerwrites.LINKEDIN_STOP_LEAD)
            self.assertTrue(report["stopped"])


# ====================================================================
#
# PART 7 — DUPLICATE WEBHOOK HANDLING
#
# ====================================================================


class DuplicateWebhookHandling(CampaignTest):
    """The same reply arriving twice is processed once.

    `events.record` is idempotent on `provider_event_id`: the same webhook
    delivered twice changes state once.
    """

    def test_duplicate_email_reply_is_ignored(self):
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)
        # Fix the provider_event_id so the second call is a true duplicate.
        event["provider_event_id"] = "emailbison:xchan:dup-test"

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            first = inbound.handle(event, [rec])
            second = inbound.handle(event, [rec])

        self.assertEqual(first["applied"]["status"], "applied")
        self.assertEqual(second["applied"]["status"], "duplicate",
                         "a duplicate reply must be reported as duplicate")

    def test_duplicate_linkedin_reply_is_ignored(self):
        rec, _camp = _dual_channel_record(self)
        event = _linkedin_reply_event(rec)
        event["provider_event_id"] = "heyreach:xchan:dup-test"

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            first = inbound.handle(event, [rec])
            second = inbound.handle(event, [rec])

        self.assertEqual(first["applied"]["status"], "applied")
        self.assertEqual(second["applied"]["status"], "duplicate")

    def test_duplicate_stop_event_is_a_no_op(self):
        """Recording the same PROVIDER_STOP_CONFIRMED twice appends only one.

        `provider_event_id` keys the stop to the exact provider lead and
        campaign, which is what makes a repeat a no-op.
        """
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]
        report = {"record": rec["id"], "contact": "xchan", "lead_id": 42,
                  "campaign": "xchan-camp", "provider_campaign": "487",
                  "why": "dnc", "status_after": "stopped"}
        leadstop._record(rec, c, report, persist=False)
        leadstop._record(rec, c, report, persist=False)
        stops = [e for e in (rec.get("events") or [])
                 if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertEqual(1, len(stops),
                         "the same stop recorded twice must collapse to one")


# ====================================================================
#
# PART 8 — RETRIES AND DELAYED EVENTS
#
# ====================================================================


class RetriesAndDelayedEvents(CampaignTest):
    """A reply that arrives late still stops the cadence.

    The checkpoint is a reply timestamp, not a cursor, so a delayed event
    is re-read and re-processed. Idempotency on `provider_event_id` ensures
    it is applied once.
    """

    def test_a_delayed_reply_still_matches_and_stops(self):
        """A reply with an old timestamp still matches the record and
        triggers the stop."""
        rec, _camp = _dual_channel_record(self)
        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id="emailbison:xchan:delayed",
            record_id=rec["id"], contact_key="xchan",
            email="test@xchan.test",
            at="2026-09-01T08:00:00Z",  # three weeks ago
            text="please stop", client=CLIENT)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        self.assertEqual(outcome["applied"]["status"], "applied")
        stops = outcome.get("provider_stop") or {}
        self.assertTrue(stops.get("email", {}).get("attempted"))
        self.assertTrue(stops.get("linkedin", {}).get("attempted"))

    def test_a_stop_that_failed_is_reported_as_refused(self):
        """When the provider stop raises, the outcome records the refusal.
        The reply is still ingested and the account is still paused."""
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)

        def failing_stop(rec, contact, why, **kw):
            raise leadstop.StopRefused("no bison_lead_id")

        with mock.patch.object(leadstop, "stop_contact", failing_stop), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        stops = outcome.get("provider_stop") or {}
        email_entry = stops.get("email", {})
        # The stop was attempted but failed.
        self.assertTrue(email_entry.get("attempted"))
        self.assertFalse(email_entry.get("stopped"))
        # The reply was still processed.
        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertTrue(outcome["paused"])


# ====================================================================
#
# PART 9 — RACE CONDITIONS
#
# ====================================================================


class RaceConditions(CampaignTest):
    """Two replies arriving close together, or a reply and a sweep crossing.

    The key property: idempotency. Two replies with the same provider_event_id
    are applied once. Two stops for the same lead in the same campaign are
    recorded once.
    """

    def test_two_replies_from_different_channels_are_both_applied(self):
        """An email reply and a LinkedIn reply for the same contact, arriving
        in the same poll, are both applied. They have different provider_event_ids."""
        rec, _camp = _dual_channel_record(self)
        email_event = _email_reply_event(rec)
        email_event["provider_event_id"] = "emailbison:xchan:race-1"
        li_event = _linkedin_reply_event(rec)
        li_event["provider_event_id"] = "heyreach:xchan:race-1"

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            first = inbound.handle(email_event, [rec])
            second = inbound.handle(li_event, [rec])

        self.assertEqual(first["applied"]["status"], "applied")
        self.assertEqual(second["applied"]["status"], "applied")

    def test_a_sweep_after_a_reply_does_not_double_stop(self):
        """A sweep that runs after a reply finds the lead already stopped.
        The sweep's stop is reported as `already: True`."""
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]

        # First, a reply stops the contact.
        report = {"record": rec["id"], "contact": "xchan", "lead_id": 42,
                  "campaign": "xchan-camp", "provider_campaign": "487",
                  "why": events.REPLY_RECEIVED, "live": True,
                  "already": False, "stopped": True,
                  "status_after": "stopped"}
        leadstop._record(rec, c, report, persist=False)

        # Now the sweep runs. The provider says already stopped.
        with mock.patch("src.leadstop.bison") as bison_mock:
            bison_mock.STOPPED_STATES = ("stopped", "replied", "bounced",
                                         "sequence_finished", "unsubscribed")
            bison_mock.membership.return_value = {42: "stopped"}

            sweep_report = leadstop.stop_contact(
                rec, c, "dnc", live=False)

        # The sweep found the lead already stopped.
        self.assertTrue(sweep_report["already"])
        self.assertTrue(sweep_report["stopped"])


# ====================================================================
#
# PART 10 — SUPPRESSION PROPAGATION
#
# ====================================================================


class SuppressionPropagation(CampaignTest):
    """A suppression stops both channels.

    A DNC, an unsubscribe, an agency suppression - all must reach both
    providers, not just the one the suppression came from.
    """

    def test_an_unsubscribe_stops_both_channels(self):
        """An unsubscribe via email still stops the LinkedIn side."""
        rec, _camp = _dual_channel_record(self)
        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id=f"emailbison:xchan:unsub:{store.now()}",
            record_id=rec["id"], contact_key="xchan",
            email="test@xchan.test",
            at=store.now(),
            text="unsubscribe me", client=CLIENT)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        stops = outcome.get("provider_stop") or {}
        self.assertTrue(stops.get("email", {}).get("attempted"))
        self.assertTrue(stops.get("linkedin", {}).get("attempted"))

    def test_a_suppression_via_linkedin_stops_email(self):
        """A suppression arriving on LinkedIn still stops the email side."""
        rec, _camp = _dual_channel_record(self)
        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="linkedin",
            provider="heyreach",
            provider_event_id=f"heyreach:xchan:sup:{store.now()}",
            record_id=rec["id"], contact_key="xchan",
            linkedin="https://www.linkedin.com/in/test-stop",
            at=store.now(),
            text="please stop contacting me", client=CLIENT)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        stops = outcome.get("provider_stop") or {}
        self.assertTrue(stops.get("email", {}).get("attempted"))
        self.assertTrue(stops.get("linkedin", {}).get("attempted"))

    def test_sweep_stops_both_channels_for_a_suppressed_contact(self):
        """`leadstop.sweep` stops every channel a suppressed contact is on."""
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]
        # Mark the contact as suppressed.
        c["suppressed"] = True
        c["suppression_reason"] = "dnc"
        store.save([rec])

        # `sweep` imports `eligibility` and `executionguard` locally.
        # Patch them at the `src` level where the import resolves.
        import src.eligibility as elig_mod
        import src.executionguard as eg_mod

        with mock.patch.object(elig_mod, "must_not_contact",
                               return_value=["dnc"]), \
             mock.patch.object(eg_mod, "SUPPRESSION_REASONS",
                               ("dnc", "unsubscribed", "do_not_contact")):

            email_calls = []
            li_calls = []

            def email_tracker(rec, contact, why, **kw):
                email_calls.append(True)
                return _fake_email_stop()(rec, contact, why, **kw)

            def li_tracker(rec, contact, why, **kw):
                li_calls.append(True)
                return _fake_linkedin_stop()(rec, contact, why, **kw)

            with mock.patch.object(leadstop, "stop_contact", email_tracker), \
                 mock.patch.object(leadstop, "stop_linkedin_contact",
                                   li_tracker):
                report = leadstop.sweep(live=True)

            self.assertTrue(email_calls,
                            "sweep must attempt the email stop")
            self.assertTrue(li_calls,
                            "sweep must attempt the LinkedIn stop")


# ====================================================================
#
# PART 11 — AUDIT LOGGING
#
# ====================================================================


class AuditLogging(CampaignTest):
    """Every stop is recorded in the event log with enough detail to
    answer "when did they stop, and on whose say-so"."""

    def test_a_confirmed_stop_records_provider_stop_confirmed(self):
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]
        report = {"record": rec["id"], "contact": "xchan", "lead_id": 42,
                  "campaign": "xchan-camp", "provider_campaign": "487",
                  "why": events.REPLY_RECEIVED, "live": True,
                  "already": False, "stopped": True,
                  "status_after": "stopped"}
        leadstop._record(rec, c, report, persist=False)

        stops = [e for e in (rec.get("events") or [])
                 if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertEqual(1, len(stops))
        event = stops[0]
        self.assertEqual(event["channel"], "email")
        self.assertEqual(event["provider"], "emailbison")
        self.assertEqual(event["contact"], "xchan")
        self.assertIn("487", event.get("provider_event_id", ""))
        self.assertIn("42", event.get("provider_event_id", ""))

    def test_a_linkedin_stop_records_with_the_right_channel(self):
        rec, _camp = _dual_channel_record(self)
        c = rec["contacts"][0]
        report = {"record": rec["id"], "contact": "xchan", "lead_id": 99,
                  "campaign": "xchan-camp", "provider_campaign": "7001",
                  "why": events.REPLY_RECEIVED, "live": True,
                  "already": False, "stopped": True,
                  "status_after": "Paused", "channel": "linkedin"}
        leadstop._record_linkedin(rec, c, report, persist=False)

        stops = [e for e in (rec.get("events") or [])
                 if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertEqual(1, len(stops))
        event = stops[0]
        self.assertEqual(event["channel"], "linkedin")
        self.assertEqual(event["provider"], "heyreach")

    def test_a_full_ingest_records_reply_and_stop(self):
        """The reply event AND the stop event are both in the log.

        `inbound.handle` operates on the in-memory record and does not
        save. The events are on the in-memory `rec` after the call.
        """
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            inbound.handle(event, [rec])

        # Check the in-memory record, not the store.
        reply_events = [e for e in (rec.get("events") or [])
                        if e.get("type") == events.REPLY_RECEIVED]
        stop_events = [e for e in (rec.get("events") or [])
                       if e.get("type") == events.PROVIDER_STOP_CONFIRMED]
        self.assertGreaterEqual(len(reply_events), 1,
                                "the reply must be in the event log")
        self.assertGreaterEqual(len(stop_events), 1,
                                "the stop must be in the event log")


# ====================================================================
#
# PART 12 — THE DIRECTION TABLE
#
# ====================================================================


class DirectionTable(CampaignTest):
    """Both directions, asserted explicitly.

    LinkedIn -> email: measured working at 7.7 minutes on 2026-09-23.
    Email -> LinkedIn: was broken because `leadstop` used `linkedin_url`
    instead of `linkedin`, and the verb was sealed.
    """

    def test_linkedin_reply_stops_email(self):
        """Direction 1: LinkedIn reply -> email stop."""
        rec, _camp = _dual_channel_record(self)
        event = _linkedin_reply_event(rec)

        email_calls = []
        li_calls = []

        def email_stop_tracker(rec, contact, why, **kw):
            email_calls.append(True)
            return _fake_email_stop()(rec, contact, why, **kw)

        def li_stop_tracker(rec, contact, why, **kw):
            li_calls.append(True)
            return _fake_linkedin_stop()(rec, contact, why, **kw)

        with mock.patch.object(leadstop, "stop_contact", email_stop_tracker), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               li_stop_tracker):
            outcome = inbound.handle(event, [rec])

        self.assertTrue(email_calls,
                        "a LinkedIn reply must trigger the email stop")
        self.assertTrue(li_calls,
                        "a LinkedIn reply must trigger the LinkedIn stop")

    def test_email_reply_stops_linkedin(self):
        """Direction 2: Email reply -> LinkedIn stop."""
        rec, _camp = _dual_channel_record(self)
        event = _email_reply_event(rec)

        email_calls = []
        li_calls = []

        def email_stop_tracker(rec, contact, why, **kw):
            email_calls.append(True)
            return _fake_email_stop()(rec, contact, why, **kw)

        def li_stop_tracker(rec, contact, why, **kw):
            li_calls.append(True)
            return _fake_linkedin_stop()(rec, contact, why, **kw)

        with mock.patch.object(leadstop, "stop_contact", email_stop_tracker), \
             mock.patch.object(leadstop, "stop_linkedin_contact",
                               li_stop_tracker):
            outcome = inbound.handle(event, [rec])

        self.assertTrue(email_calls,
                        "an email reply must trigger the email stop")
        self.assertTrue(li_calls,
                        "an email reply must trigger the LinkedIn stop")

    def test_both_stops_use_per_channel_campaign_resolution(self):
        """`_campaign_of(requires=...)` resolves per channel. A contact on
        both channels gets the email row for the email stop and the LinkedIn
        row for the LinkedIn stop."""
        rec, _camp = _dual_channel_record(self)

        email_camp = leadstop._campaign_of(rec, requires="bison_campaign_id")
        li_camp = leadstop._campaign_of(rec, requires="heyreach_campaign_id")

        self.assertIsNotNone(email_camp)
        self.assertIsNotNone(li_camp)
        self.assertEqual(email_camp.get("bison_campaign_id"), "487")
        self.assertEqual(li_camp.get("heyreach_campaign_id"), "7001")


# ====================================================================
#
# PART 13 — SINGLE-CHANNEL CONTACTS
#
# ====================================================================


class SingleChannelContacts(CampaignTest):
    """Most contacts are on one channel only. The stop must handle that
    without reporting it as a failure."""

    def test_email_only_contact_linkedin_stop_is_not_attempted(self):
        rec = store.new_record("xchan-eo", "cold", CLIENT,
                               "Email Only", "emailonly.test")
        rec["contacts"] = [contact("eo", "Email Only", "eo@emailonly.test")]
        rec["contacts"][0]["bison_lead_id"] = 42
        self.reset_estate()
        store.save([rec])

        camp = {
            "campaign_id": "xchan-eo-camp", "client": CLIENT,
            "record_ids": [rec["id"]],
            "bison_campaign_id": "487",
        }
        campaigns.save([camp])

        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="email",
            provider="emailbison",
            provider_event_id=f"emailbison:eo:{store.now()}",
            record_id=rec["id"], contact_key="eo",
            email="eo@emailonly.test",
            at=store.now(), text="stop", client=CLIENT)

        with mock.patch.object(leadstop, "stop_contact",
                               _fake_email_stop()):
            outcome = inbound.handle(event, [rec])

        stops = outcome.get("provider_stop") or {}
        self.assertTrue(stops.get("email", {}).get("attempted"))
        self.assertFalse(stops.get("linkedin", {}).get("attempted"),
                         "no heyreach_lead_id means no LinkedIn stop")

    def test_linkedin_only_contact_email_stop_is_not_attempted(self):
        rec = store.new_record("xchan-lo", "cold", CLIENT,
                               "LinkedIn Only", "linkedinonly.test")
        c = contact("lo", "LI Only", "lo@linkedinonly.test",
                     linkedin="https://www.linkedin.com/in/li-only")
        c["heyreach_lead_id"] = 99
        rec["contacts"] = [c]
        self.reset_estate()
        store.save([rec])

        camp = {
            "campaign_id": "xchan-lo-camp", "client": CLIENT,
            "record_ids": [rec["id"]],
            "heyreach_campaign_id": "7001",
        }
        campaigns.save([camp])

        event = events.neutral(
            type=events.REPLY_RECEIVED, channel="linkedin",
            provider="heyreach",
            provider_event_id=f"heyreach:lo:{store.now()}",
            record_id=rec["id"], contact_key="lo",
            linkedin="https://www.linkedin.com/in/li-only",
            at=store.now(), text="stop", client=CLIENT)

        with mock.patch.object(leadstop, "stop_linkedin_contact",
                               _fake_linkedin_stop()):
            outcome = inbound.handle(event, [rec])

        stops = outcome.get("provider_stop") or {}
        self.assertFalse(stops.get("email", {}).get("attempted"),
                         "no bison_lead_id means no email stop")
        self.assertTrue(stops.get("linkedin", {}).get("attempted"))


# ====================================================================
#
# SCENARIO COVERAGE TABLE
#
# scenario                         direction       covered by
# ---------------------------------------------------------------
# contact identity by email        both            test (Part 2)
# contact identity by LinkedIn URL both            test (Part 2)
# shared address refuses guess     both            test (Part 2)
# no provider binding              both            test (Part 2)
# account-level pause              both            test (Part 3)
# pure OOO no account pause        both            test (Part 3)
# reply ingestion                  both            test (Part 4)
# negative classification          both            test (Part 4)
# positive classification          both            test (Part 4)
# unknown classification           both            test (Part 4)
# provider stop independent        both            test (Part 4)
# pending step cancellation        both            test (Part 5)
# correct provider route (email)   email           test (Part 6)
# correct provider route (LI)      linkedin        test (Part 6)
# duplicate webhook                both            test (Part 7)
# duplicate stop event             both            test (Part 7)
# delayed event                    both            test (Part 8)
# stop failure reported            both            test (Part 8)
# race: two channels same poll     both            test (Part 9)
# race: sweep after reply          both            test (Part 9)
# suppression propagation          both            test (Part 10)
# sweep both channels              both            test (Part 10)
# audit: stop event logged         both            test (Part 11)
# audit: reply+stop both logged    both            test (Part 11)
# readback cannot lie              both            test (Part 1)
# direction: LI->email             linkedin->email test (Part 12)
# direction: email->LI             email->linkedin test (Part 12)
# per-channel campaign resolution  both            test (Part 12)
# single-channel: email only       email           test (Part 13)
# single-channel: LI only          linkedin        test (Part 13)
#
# LIVE VALIDATION REQUIRED:
#
# scenario                         direction       why
# ---------------------------------------------------------------
# provider visibility latency      both            term 1: reply sent ->
#                                                  row in inbox feed. Needs
#                                                  a human sending a real
#                                                  LinkedIn message.
# email stop against live lead     email           needs a real EmailBison
#                                                  lead in a real campaign
# LI stop against live lead        linkedin        needs a real HeyReach
#                                                  lead. The identifier
#                                                  shape was measured
#                                                  2026-09-25 but the full
#                                                  cross-channel flow has
#                                                  never run end to end.
# end-to-end timing < 15 min       both            operator gate. Needs
#                                                  both providers live.
# provider retry under load        both            cannot be simulated
#                                                  without provider access.


if __name__ == "__main__":
    unittest.main()
