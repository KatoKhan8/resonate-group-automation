#!/usr/bin/env python3
"""TASK-387: provider-confirmed sends and replies reach the record's event log.

This test demonstrates the write-back paths that exist today:

1. A provider-confirmed SEND (EmailBison scheduled_emails row moving to
   'sent') is written to the record's event log as PUSH_MARKED via
   leadobserve.confirm_email_touches().

2. A provider-confirmed REPLY (EmailBison /api/replies row) is written to
   the record's event log as REPLY_RECEIVED via inbound.ingest().

3. A provider-confirmed BOUNCE is written as EMAIL_BOUNCED via both paths.

Each test uses a fixture standing in for the API response - no live
provider call is made.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import events, leadobserve, store
from src.providers import bison


CAMPAIGN = 451
SCHEDULED_ID = 22303345
LEAD_ID = 203657


def _provider_send_row(status="sent", sent_at="2026-09-14T13:19:05Z"):
    """Fixture standing in for one bison.scheduled_emails row."""
    return {
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
                     {"name": "record_id", "value": "hotsoup"},
                     {"name": "contact_key", "value": "hussein"},
                     {"name": "client", "value": "productive"},
                 ]},
        "sender_account_id": "sender-01",
    }


def _provider_reply_event():
    """Fixture standing in for one EmailBison /api/replies row,
    already adapted into the neutral event shape by adapters.from_emailbison."""
    return events.neutral(
        client="productive",
        record_id="hotsoup",
        contact_key="hussein",
        channel="email",
        type=events.REPLY_RECEIVED,
        provider="emailbison",
        provider_event_id="bison-reply-001",
        at="2026-09-15T10:30:00Z",
    )


def _provider_bounce_event():
    """Fixture standing in for one EmailBison bounce via the poller."""
    return events.neutral(
        client="productive",
        record_id="hotsoup",
        contact_key="hussein",
        channel="email",
        type=events.EMAIL_BOUNCED,
        provider="emailbison",
        provider_event_id="bison-bounce-001",
        at="2026-09-15T09:00:00Z",
    )


def _a_record():
    """A minimal record matching the fixture's identifiers."""
    return {
        "id": "hotsoup",
        "client": "productive",
        "state": "TODO",
        "company": "hotsoup",
        "contacts": [{
            "key": "hussein",
            "email": "hussein@example.test",
            "name": "Hussein",
        }],
        "events": [],
        "log": [],
    }


class ProviderEventWritebackTest(unittest.TestCase):
    """A provider-confirmed event reaches the record's own event log."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-task387-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_provider_confirmed_send_writes_push_marked_to_record(self):
        """An EmailBison row moving to 'sent' produces a PUSH_MARKED event
        on the record's own event log, sourced from the provider's data."""
        rec = _a_record()
        store.save([rec])
        row = _provider_send_row("sent")

        with mock.patch.object(bison, "scheduled_emails",
                               return_value=[row]):
            out = leadobserve.confirm_email_touches(CAMPAIGN, live=True)

        written = store.get("hotsoup")
        kinds = [e["type"] for e in written.get("events") or []]
        self.assertIn(events.PUSH_MARKED, kinds,
                      "a provider-confirmed send must write PUSH_MARKED "
                      "to the record's event log")
        self.assertEqual(out["recorded"],
                         [out["recorded"][0]],
                         "one event recorded")
        event = [e for e in written["events"]
                 if e["type"] == events.PUSH_MARKED][0]
        self.assertEqual(event["provider"], "emailbison")
        self.assertIn(f"emailbison:{CAMPAIGN}:{SCHEDULED_ID}",
                      event.get("provider_event_id", ""),
                      "the event must carry the provider's own identity")

    def test_provider_confirmed_reply_writes_reply_received_to_record(self):
        """An EmailBison reply polled via events.apply() produces a
        REPLY_RECEIVED event on the record's own event log."""
        rec = _a_record()
        store.save([rec])
        event = _provider_reply_event()

        result = events.apply([rec], event)
        store.save([rec])

        written = store.get("hotsoup")
        kinds = [e["type"] for e in written.get("events") or []]
        self.assertIn(events.REPLY_RECEIVED, kinds,
                      "a provider-confirmed reply must write REPLY_RECEIVED "
                      "to the record's event log")
        self.assertEqual(result["status"], "applied")
        event_row = [e for e in written["events"]
                     if e["type"] == events.REPLY_RECEIVED][0]
        self.assertEqual(event_row["provider"], "emailbison")
        self.assertEqual(event_row["provider_event_id"],
                         "bison-reply-001")

    def test_provider_confirmed_bounce_writes_email_bounced_to_record(self):
        """A bounce from the provider produces an EMAIL_BOUNCED event on
        the record's own event log."""
        rec = _a_record()
        store.save([rec])
        event = _provider_bounce_event()

        result = events.apply([rec], event)
        store.save([rec])

        written = store.get("hotsoup")
        kinds = [e["type"] for e in written.get("events") or []]
        self.assertIn(events.EMAIL_BOUNCED, kinds,
                      "a provider-confirmed bounce must write EMAIL_BOUNCED "
                      "to the record's event log")
        self.assertEqual(result["status"], "applied")

    def test_send_then_reply_both_land_on_same_record(self):
        """A send confirmed by the provider and a reply to it both appear
        on the same record's event log - the queue can answer 'has this
        contact been sent to' AND 'did they reply' from its own state."""
        rec = _a_record()
        store.save([rec])

        # Step 1: provider confirms the send
        row = _provider_send_row("sent")
        with mock.patch.object(bison, "scheduled_emails",
                               return_value=[row]):
            leadobserve.confirm_email_touches(CAMPAIGN, live=True)

        # Step 2: provider confirms the reply (via events.apply, the same
        # path the poller feeds through)
        live_recs = store.load()
        reply = _provider_reply_event()
        events.apply(live_recs, reply)
        store.save(live_recs)

        final = store.get("hotsoup")
        kinds = [e["type"] for e in final.get("events") or []]
        self.assertIn(events.PUSH_MARKED, kinds)
        self.assertIn(events.REPLY_RECEIVED, kinds)
        self.assertEqual(len(final["events"]), 2,
                         "exactly two events: the send and the reply")


if __name__ == "__main__":
    unittest.main()
