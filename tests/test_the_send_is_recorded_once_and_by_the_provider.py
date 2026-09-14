#!/usr/bin/env python3
"""EmailBison's pre-send queue becoming canonical state, exactly once.

The live shape this is written against was read from campaign 451 on
2026-09-13: one scheduled email, id 22303345, to lead 203657, carrying
`record_id`, `contact_key` and `client` back in `lead.custom_variables`.
That round trip is what makes an email observation attributable without a
guess, and it is the opposite of HeyReach, whose custom fields come back
empty.

Four things are pinned here and each of them has a way of going wrong that
looks like success:

  * a quiet poll writes nothing. A poller that appended every tick would
    make a weekend of nothing look like a weekend of activity
  * `sent` is `push_marked`, never `email_delivered`. EmailBison's `sent`
    says it handed the message to SMTP; a mailbox accepting it is a
    different claim and no surface here makes it
  * the canary's first touch was written by hand at staging and carries no
    `provider_event_id`. Idempotency on the provider's id alone would not
    see it, so the moment the row moved to `sent` there would be two
    confirmed touches for one message and every exposure count under every
    rate would be doubled
  * a lead whose `client` variable disagrees with the record it names is
    not applied. Two clients working the same decision maker is the normal
    case for an agency
"""
import os
import unittest
from unittest import mock

from src import events, leadobserve, store, touch
from src.providers import bison
from tests.base import QueueTest

CAMPAIGN = 451
SCHEDULED_ID = 22303345
LEAD_ID = 203657


def a_row(status="scheduled", sent_at=None, variables=None, **over):
    """One scheduled-email row in the provider's own shape."""
    row = {
        "id": SCHEDULED_ID,
        "campaign_id": CAMPAIGN,
        "sequence_step_id": 4707,
        "email_subject": "Profitability visible on Monday",
        "email_body": "<p>One line.<br><br>And a question?</p>",
        "status": status,
        "scheduled_date": "2026-09-14T13:19:00.000000Z",
        "sent_at": sent_at,
        "opens": 0, "clicks": 0, "replies": 0, "unique_opens": 0,
        "unique_replies": 0, "interested": False,
        "raw_message_id": "<abc@fixture.example>",
        "campaign": {"id": CAMPAIGN, "status": "active",
                     "open_tracking": False},
        "lead": {"id": LEAD_ID, "email": "hussein@example.test",
                 "custom_variables": [
                     {"name": name, "value": value}
                     for name, value in (variables if variables is not None
                                         else {"record_id": "hotsoup",
                                               "contact_key": "hussein",
                                               "client": "productive"}).items()]},
        "sender_email": {"id": 3948, "email": "sender@example.test"},
    }
    row.update(over)
    return row


def a_record(with_staging_touch=False):
    rec = {"id": "hotsoup", "client": "productive", "domain": "example.test",
           "company": "Hot Soup", "events": [],
           "contacts": [{"key": "hussein", "name": "Hussein",
                         "email": "hussein@example.test",
                         "persona": "economic_buyer", "angle": "founder"}],
           "cadence": {"hussein": {"day1": {"channel": "email",
                                            "subject": "s", "body": "b"}}}}
    if with_staging_touch:
        # Exactly the shape the operator's staging wrote on 2026-09-13: no
        # `provider_event_id` and no `id`, because it was not written through
        # a provider poll.
        rec["events"].append({
            "type": events.PUSH_MARKED, "contact": "hussein",
            "channel": "email", "step": "day1", "provider": "emailbison",
            "provider_campaign": CAMPAIGN, "lead_id": LEAD_ID,
            "scheduled_email_id": SCHEDULED_ID, "sender_account_id": 3948,
            "at": "2026-09-13T08:48:43+00:00"})
    return rec


class TheQueueIsReadAndNothingIsInvented(QueueTest):

    def observe(self, *rows, now=None):
        with mock.patch.object(bison, "scheduled_emails",
                               return_value=list(rows)):
            return leadobserve.observe_emails(CAMPAIGN, now=now)

    def test_the_first_read_records_the_state_it_found(self):
        appended = self.observe(a_row())
        self.assertEqual(len(appended), 1)
        self.assertEqual(appended[0]["state"], leadobserve.SCHEDULED)
        self.assertIsNone(appended[0]["was"])
        self.assertEqual(appended[0]["provider"], leadobserve.EMAILBISON)

    def test_a_quiet_poll_writes_nothing(self):
        self.observe(a_row())
        self.assertEqual(self.observe(a_row()), [])
        self.assertEqual(self.observe(a_row()), [])
        self.assertEqual(len(leadobserve.history(CAMPAIGN,
                                                 leadobserve.EMAILBISON)), 1)

    def test_a_real_transition_records_once(self):
        self.observe(a_row())
        appended = self.observe(a_row("sent", sent_at="2026-09-14T13:19:05Z"))
        self.assertEqual(len(appended), 1)
        self.assertEqual(appended[0]["was"], leadobserve.SCHEDULED)
        self.assertEqual(appended[0]["state"], leadobserve.SENT)
        self.assertEqual(self.observe(a_row("sent",
                                            sent_at="2026-09-14T13:19:05Z")),
                         [])

    def test_the_provider_clock_is_kept_apart_from_ours(self):
        self.observe(a_row("sent", sent_at="2026-09-14T13:19:05Z"),
                     now="2026-09-16T11:00:00+00:00")
        row = leadobserve.history(CAMPAIGN, leadobserve.EMAILBISON)[0]
        self.assertEqual(row["sent_at"], "2026-09-14T13:19:05Z")
        self.assertEqual(row["at"], "2026-09-16T11:00:00+00:00")

    def test_an_unknown_status_is_recorded_not_resolved(self):
        appended = self.observe(a_row("queued_for_warmup"))
        self.assertEqual(appended[0]["state"], leadobserve.EMAIL_STATE_UNKNOWN)
        self.assertEqual(appended[0]["raw_status"], "queued_for_warmup")
        self.assertNotIn(appended[0]["state"], leadobserve.EMAIL_REACHED)

    def test_nothing_of_the_body_is_stored_but_its_length_is(self):
        """Length is one of the questions. The copy already lives on the
        record and a second copy here would be free to drift from it."""
        appended = self.observe(a_row())
        row = appended[0]
        self.assertNotIn("email_body", row)
        self.assertNotIn("email_subject", row)
        self.assertEqual(row["body_words"], 5)
        self.assertGreater(row["body_chars"], 0)

    def test_the_open_counter_carries_whether_it_means_anything(self):
        row = self.observe(a_row())[0]
        self.assertEqual(row["opens"], 0)
        self.assertIs(row["open_tracking"], False)

    def test_two_providers_numbering_a_campaign_the_same_do_not_collide(self):
        """Campaign 451 at EmailBison and campaign 451 at HeyReach are two
        campaigns. A match on the number alone lets one answer for the
        other."""
        self.observe(a_row())
        with store.file_transaction(leadobserve.path()) as rows:
            rows.append({"at": "2026-09-11T16:26:44+00:00",
                         "provider": leadobserve.HEYREACH,
                         "campaign_id": str(CAMPAIGN),
                         "provider_lead_id": SCHEDULED_ID,
                         "state": "accepted"})
        # The HeyReach row names the same two numbers and must not be read as
        # this scheduled email's last state.
        self.assertEqual(self.observe(a_row()), [])
        self.assertEqual(
            [r["state"] for r in leadobserve.history(CAMPAIGN,
                                                     leadobserve.HEYREACH)],
            ["accepted"])


class SentIsNotDelivered(QueueTest):

    def confirm(self, row, rec=None, live=True):
        rec = a_record() if rec is None else rec
        # A fresh queue each time. `store.save` refuses to write a snapshot
        # that drops events - correctly - and this class re-stages the same
        # record id for each state it exercises.
        if os.path.exists(self.queue):
            os.remove(self.queue)
        store.save([rec])
        with mock.patch.object(bison, "scheduled_emails", return_value=[row]):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=live)
        return out, store.get("hotsoup")

    def test_scheduled_is_not_an_action_at_all(self):
        out, rec = self.confirm(a_row())
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["waiting"]), 1)
        self.assertEqual(rec["events"], [])

    def test_sent_records_push_marked_and_never_email_delivered(self):
        out, rec = self.confirm(a_row("sent", sent_at="2026-09-14T13:19:05Z"))
        kinds = [e["type"] for e in rec["events"]]
        self.assertEqual(kinds, [events.PUSH_MARKED])
        self.assertNotIn(events.EMAIL_DELIVERED, kinds)
        self.assertEqual(out["recorded"][0]["step"], None)

    def test_the_touch_is_dated_by_the_provider(self):
        _out, rec = self.confirm(a_row("sent", sent_at="2026-09-14T13:19:05Z"))
        self.assertEqual(rec["events"][0]["at"], "2026-09-14T13:19:05Z")

    def test_a_bounce_is_recorded_and_is_not_a_confirmed_touch(self):
        _out, rec = self.confirm(a_row("bounced",
                                       sent_at="2026-09-14T13:19:05Z"))
        self.assertEqual(rec["events"][0]["type"], events.EMAIL_BOUNCED)
        self.assertNotIn(events.EMAIL_BOUNCED, touch.CONFIRMING_EVENTS)

    def test_a_stop_the_provider_confirms_maps_to_the_stop_event(self):
        self.assertEqual(leadobserve.EVENT_FOR[leadobserve.STOPPED],
                         events.PROVIDER_STOP_CONFIRMED)

    def test_an_event_the_vocabulary_cannot_hold_is_refused_out_loud(self):
        """`provider_stop_confirmed` is defined in events.py and is in
        neither INTERNAL nor EXTERNAL, so `events.record` raises on it.
        Nothing noticed because `leadstop._record` appends the dict itself.

        This asserts the shape of the answer, not the defect: whatever the
        vocabulary holds, a state the writer refuses is reported rather than
        dropped, and nothing here writes around the canonical writer."""
        out, rec = self.confirm(a_row("stopped"))
        recordable = events.PROVIDER_STOP_CONFIRMED in events.KNOWN
        if recordable:
            self.assertEqual(rec["events"][0]["type"],
                             events.PROVIDER_STOP_CONFIRMED)
            self.assertEqual(out["refused"], [])
        else:
            self.assertEqual(rec["events"], [])
            self.assertEqual(len(out["refused"]), 1)
            self.assertIn("events.KNOWN", out["refused"][0]["why"])
            self.assertEqual(out["recorded"], [])
            self.assertEqual(out["waiting"], [])

    def test_every_state_this_module_maps_is_a_state_it_can_explain(self):
        """No silent third category: a mapped state is recordable or it is
        named in `refused`, and an unmapped one is `waiting`."""
        for state in leadobserve.EMAIL_STATES:
            out, _rec = self.confirm(a_row(state,
                                           sent_at="2026-09-14T13:19:05Z"))
            total = (len(out["recorded"]) + len(out["already"])
                     + len(out["waiting"]) + len(out["refused"])
                     + len(out["unmatched"]))
            self.assertEqual(total, 1, state)

    def test_an_unknown_status_produces_no_event(self):
        out, rec = self.confirm(a_row("queued_for_warmup"))
        self.assertEqual(rec["events"], [])
        self.assertEqual(out["waiting"][0]["state"],
                         leadobserve.EMAIL_STATE_UNKNOWN)

    def test_dry_is_the_default_and_writes_nothing(self):
        out, rec = self.confirm(a_row("sent", sent_at="2026-09-14T13:19:05Z"),
                                live=False)
        self.assertEqual(len(out["recorded"]), 1)
        self.assertFalse(out["live"])
        self.assertEqual(rec["events"], [])


class OneMessageIsOneTouch(QueueTest):
    """The duplication law, on the read side."""

    def confirm(self, row, rec, live=True):
        store.save([rec])
        with mock.patch.object(bison, "scheduled_emails", return_value=[row]):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=live)
        return out, store.get("hotsoup")

    def test_a_hand_written_staging_touch_is_reconciled_not_duplicated(self):
        out, rec = self.confirm(a_row("sent", sent_at="2026-09-14T13:19:05Z"),
                                a_record(with_staging_touch=True))
        # The harm first: two confirmed touches for one message doubles every
        # exposure count underneath every rate.
        self.assertEqual([e["type"] for e in rec["events"]],
                         [events.PUSH_MARKED])
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["already"]), 1)

    def test_the_reconciled_touch_keeps_the_step_the_staging_recorded(self):
        out, _rec = self.confirm(a_row("sent", sent_at="2026-09-14T13:19:05Z"),
                                 a_record(with_staging_touch=True))
        self.assertEqual(out["already"][0]["step"], "day1")

    def test_polling_a_sent_row_twice_records_one_event(self):
        rec = a_record()
        row = a_row("sent", sent_at="2026-09-14T13:19:05Z")
        self.confirm(row, rec)
        _out, rec = self.confirm(row, store.get("hotsoup"))
        self.assertEqual(len(rec["events"]), 1)

    def test_a_second_scheduled_email_on_another_step_is_its_own_touch(self):
        """The rule is one touch per message, not one touch per person."""
        rec = a_record(with_staging_touch=True)
        second = a_row("sent", sent_at="2026-09-28T13:19:05Z",
                       id=22999999, sequence_step_id=4708)
        store.save([rec])
        with mock.patch.object(bison, "scheduled_emails",
                               return_value=[second]):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)
        rec = store.get("hotsoup")
        self.assertEqual(len(rec["events"]), 2)
        self.assertEqual(
            [e.get("scheduled_email_id") for e in rec["events"]],
            [SCHEDULED_ID, 22999999])


class NobodyIsGuessedAt(QueueTest):

    def confirm(self, row, rec):
        store.save([rec])
        with mock.patch.object(bison, "scheduled_emails", return_value=[row]):
            return leadobserve.confirm_email_touches(CAMPAIGN, live=True)

    def test_a_disagreeing_client_is_refused(self):
        out = self.confirm(
            a_row("sent", sent_at="2026-09-14T13:19:05Z",
                  variables={"record_id": "hotsoup", "contact_key": "hussein",
                             "client": "another-agency"}),
            a_record())
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["unmatched"]), 1)
        self.assertIn("another-agency", out["unmatched"][0]["why"])
        self.assertEqual(store.get("hotsoup")["events"], [])

    def test_a_lead_naming_no_record_we_hold_is_reported_not_applied(self):
        out = self.confirm(
            a_row("sent", sent_at="2026-09-14T13:19:05Z",
                  variables={"record_id": "somebody-else"},
                  lead={"id": LEAD_ID, "email": "nobody@nowhere.test",
                        "custom_variables": [
                            {"name": "record_id", "value": "somebody-else"}]}),
            a_record())
        self.assertEqual(out["recorded"], [])
        self.assertEqual(len(out["unmatched"]), 1)

    def test_the_address_matches_when_the_variables_are_missing(self):
        """A lead staged before the custom variables existed is still
        placeable, and the canonical matcher is the one that does it."""
        out = self.confirm(
            a_row("sent", sent_at="2026-09-14T13:19:05Z",
                  lead={"id": LEAD_ID, "email": "hussein@example.test",
                        "custom_variables": []}),
            a_record())
        self.assertEqual(len(out["recorded"]), 1)
        self.assertEqual(out["recorded"][0]["contact_key"], "hussein")


if __name__ == "__main__":
    unittest.main()
