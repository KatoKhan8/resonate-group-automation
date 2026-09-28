#!/usr/bin/env python3
"""TASK-387: demonstrate that provider-confirmed sends are written to records.

This test shows a record's event log gaining a real entry after a
provider-confirmed send, sourced from a fixture standing in for the API
response. No live provider call is made.

The test demonstrates the write-back path that already exists:
  leadobserve.confirm_email_touches() -> events.record() -> store.transaction()
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import events, store


class TestProviderWriteback(unittest.TestCase):
    """Demonstrate that provider-confirmed events are written to records."""

    def setUp(self):
        """Set up a temp directory for the queue."""
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))

    def test_emailbison_send_is_written_to_record(self):
        """A provider-confirmed EmailBison send is recorded to the event log.

        This demonstrates the write-back path:
        1. A fixture scheduled email row stands in for the API response
        2. confirm_email_touches() reads it and matches it to a record
        3. events.record() appends a PUSH_MARKED event to rec["events"]
        4. The event carries provider_event_id for idempotency
        """
        # Create a minimal record with a contact
        rec = {
            "id": "test-record-1",
            "client": "test-client",
            "state": "pushed",
            "lane": "cold",
            "company": "Example Corp",
            "domain": "example.com",
            "drop_reason": "",
            "contacts": [
                {
                    "key": "jennifer-bagley",
                    "email": "jennifer@example.com",
                    "domain": "example.com",
                }
            ],
            "events": [],
            "log": [],
        }
        store.append([rec])

        # Fixture: a scheduled email row standing in for the API response.
        # This is what bison.scheduled_emails() would return after a send.
        fixture_scheduled_row = {
            "scheduled_email_id": "sched-12345",
            "provider_lead_id": "lead-67890",
            "state": "sent",  # Provider confirmed: sent
            "sent_at": "2026-09-28T10:30:00Z",
            "scheduled_at": "2026-09-28T10:00:00Z",
            "sender_account_id": "sender-1",
            "provider_message_id": "msg-abc123",
        }

        # Mock the provider read to return our fixture
        with mock.patch("src.leadobserve.scheduled_rows") as mock_rows, \
             mock.patch("src.leadobserve.match_scheduled") as mock_match:
            mock_rows.return_value = [fixture_scheduled_row]
            # match_scheduled returns the record and contact_key
            mock_match.return_value = {
                "rec": store.get("test-record-1"),
                "contact_key": "jennifer-bagley",
                "why": None,
            }

            # Import after mocking to ensure the patch takes effect
            from src import leadobserve

            # Run the write-back with live=True to actually write
            result = leadobserve.confirm_email_touches(
                campaign_id=487,
                recs=store.load(),
                live=True,
            )

        # Verify the write-back happened
        self.assertEqual(len(result["recorded"]), 1,
                        "one send should be recorded")
        self.assertEqual(result["campaign_id"], "487")

        # Verify the record's event log gained the entry
        updated_rec = store.get("test-record-1")
        self.assertIsNotNone(updated_rec)
        self.assertGreater(len(updated_rec["events"]), 0,
                          "event log should have at least one entry")

        # Find the PUSH_MARKED event
        push_events = [e for e in updated_rec["events"]
                      if e.get("type") == events.PUSH_MARKED]
        self.assertEqual(len(push_events), 1,
                        "exactly one PUSH_MARKED event should be recorded")

        push_event = push_events[0]
        # Verify the event carries the provider evidence
        self.assertEqual(push_event["contact"], "jennifer-bagley")
        self.assertEqual(push_event["channel"], "email")
        self.assertEqual(push_event["provider"], "emailbison")
        self.assertEqual(push_event["campaign_id"], "487")
        self.assertEqual(push_event["scheduled_email_id"], "sched-12345")
        self.assertIn("emailbison:487:sched-12345:sent",
                     push_event["provider_event_id"])
        self.assertEqual(push_event["at"], "2026-09-28T10:30:00Z")

    def test_reply_is_written_to_record(self):
        """A provider-confirmed reply is recorded to the event log.

        This demonstrates the inbound write-back path:
        1. A fixture neutral event stands in for a provider webhook
        2. events.apply() matches it to a record
        3. events.record() appends a REPLY_RECEIVED event to rec["events"]
        """
        # Create a minimal record with a contact
        rec = {
            "id": "test-record-2",
            "client": "test-client",
            "state": "pushed",
            "lane": "cold",
            "company": "Example Corp",
            "domain": "example.com",
            "drop_reason": "",
            "contacts": [
                {
                    "key": "john-doe",
                    "email": "john@example.com",
                    "domain": "example.com",
                }
            ],
            "events": [],
            "log": [],
        }
        store.append([rec])

        # Fixture: a neutral event standing in for a provider webhook payload
        fixture_reply_event = events.neutral(
            type=events.REPLY_RECEIVED,
            channel="email",
            provider="emailbison",
            provider_event_id="emailbison:reply-999",
            record_id="test-record-2",
            contact_key="john-doe",
            client="test-client",
            email="john@example.com",
            at="2026-09-28T11:00:00Z",
            text="Thanks for reaching out, let's schedule a call.",
        )

        # Apply the event through the canonical path
        recs = store.load()
        result = events.apply(recs, fixture_reply_event)

        # Verify the event was applied
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["record_id"], "test-record-2")
        self.assertEqual(result["contact"], "john-doe")

        # Save the changes to disk
        store.save(recs)

        # Verify the record's event log gained the entry
        updated_rec = store.get("test-record-2")
        self.assertIsNotNone(updated_rec)
        self.assertGreater(len(updated_rec["events"]), 0,
                          "event log should have at least one entry")

        # Find the REPLY_RECEIVED event
        reply_events = [e for e in updated_rec["events"]
                       if e.get("type") == events.REPLY_RECEIVED]
        self.assertEqual(len(reply_events), 1,
                        "exactly one REPLY_RECEIVED event should be recorded")

        reply_event = reply_events[0]
        # Verify the event carries the provider evidence
        self.assertEqual(reply_event["contact"], "john-doe")
        self.assertEqual(reply_event["channel"], "email")
        self.assertEqual(reply_event["provider"], "emailbison")
        self.assertEqual(reply_event["provider_event_id"],
                        "emailbison:reply-999")
        self.assertEqual(reply_event["at"], "2026-09-28T11:00:00Z")

    def test_idempotency_same_event_not_recorded_twice(self):
        """The same provider event is not recorded twice.

        This demonstrates the idempotency guard on provider_event_id.
        """
        rec = {
            "id": "test-record-3",
            "client": "test-client",
            "state": "pushed",
            "lane": "cold",
            "company": "Example Corp",
            "domain": "example.com",
            "drop_reason": "",
            "contacts": [
                {
                    "key": "jane-smith",
                    "email": "jane@example.com",
                    "domain": "example.com",
                }
            ],
            "events": [],
            "log": [],
        }
        store.append([rec])

        # Apply the same event twice
        fixture_event = events.neutral(
            type=events.REPLY_RECEIVED,
            channel="email",
            provider="emailbison",
            provider_event_id="emailbison:reply-777",
            record_id="test-record-3",
            contact_key="jane-smith",
            client="test-client",
            email="jane@example.com",
            at="2026-09-28T12:00:00Z",
            text="Not interested, thanks.",
        )

        recs = store.load()
        result1 = events.apply(recs, fixture_event)
        self.assertEqual(result1["status"], "applied")
        # Save to persist the first application
        store.save(recs)

        # Apply again - should be duplicate
        recs = store.load()
        result2 = events.apply(recs, fixture_event)
        self.assertEqual(result2["status"], "duplicate")

        # Verify only one event was recorded
        updated_rec = store.get("test-record-3")
        reply_events = [e for e in updated_rec["events"]
                       if e.get("type") == events.REPLY_RECEIVED]
        self.assertEqual(len(reply_events), 1,
                        "idempotency: same event recorded only once")


if __name__ == "__main__":
    unittest.main()
