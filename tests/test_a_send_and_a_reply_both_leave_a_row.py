#!/usr/bin/env python3
"""A provider send and a reply each leave exactly one row in the action ledger.

TASK-349. The action ledger recorded reservations and their settlements, but
nothing the provider observed on its own. A send the provider confirmed and a
reply that arrived were facts about production with no durable row, so when
the question "who did this, and when?" was asked, the ledger's silence was
mistaken for evidence of absence.

Five requirements:

1. A fixture send (EMAIL_DELIVERED) writes exactly one row with state
   PROVIDER_SENT; replaying the same event writes none.
2. A fixture reply (REPLY_RECEIVED) writes a row carrying its contact key,
   its provider timestamp and our observation time, and they are
   distinguishable fields.
3. The guard is seen to fail: removing the write-back call makes the test
   fail and names the missing row.
4. A reply row carries the provider event id as its key, so two different
   replies to the same contact produce two distinct rows.
5. An event without a provider_event_id writes nothing rather than deriving
   a key that might collide.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import actionledger, events, inbound, store
from tests.base import QueueTest


def _make_record(rec_id="rec-1", domain="example.com",
                 email="prospect@example.com", contact_key="k1",
                 client="productive"):
    return {
        "id": rec_id, "domain": domain, "client": client,
        "contacts": [{"key": contact_key, "email": email}],
        "events": [],
    }


def _send_event(provider_event_id="emailbison:abc-123",
                campaign_id=42, contact_key="k1",
                at="2026-09-26T10:00:00+00:00"):
    """A neutral EMAIL_DELIVERED event, the shape the EmailBison adapter emits."""
    return events.neutral(
        type=events.EMAIL_DELIVERED,
        channel="email",
        provider="emailbison",
        provider_event_id=provider_event_id,
        record_id="rec-1",
        contact_key=contact_key,
        client="productive",
        email="prospect@example.com",
        at=at,
        external_campaign_id=campaign_id,
    )


def _reply_event(provider_event_id="heyreach:thread-1:2026-09-26T11:00:00",
                 campaign_id=99, contact_key="k1",
                 at="2026-09-26T11:00:00+00:00"):
    """A neutral REPLY_RECEIVED event, the shape both adapters emit."""
    return events.neutral(
        type=events.REPLY_RECEIVED,
        channel="email",
        provider="emailbison",
        provider_event_id=provider_event_id,
        record_id="rec-1",
        contact_key=contact_key,
        client="productive",
        email="prospect@example.com",
        at=at,
        text="Not interested, thanks",
        external_campaign_id=campaign_id,
    )


class SendLeavesOneRow(QueueTest):
    """Acceptance 1: a fixture send writes exactly one row; replay writes none."""

    def setUp(self):
        super().setUp()
        self.ledger_path = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        super().tearDown()

    def test_send_writes_exactly_one_row(self):
        rec = _make_record()
        recs = [rec]
        event = _send_event()

        outcome = inbound.handle(event, recs)

        rows = actionledger.load()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["state"], actionledger.PROVIDER_SENT)
        self.assertEqual(row["provider"], "emailbison")
        self.assertEqual(row["channel"], "email")
        self.assertEqual(row["contact_key"], "k1")
        self.assertEqual(row["rec_id"], "rec-1")
        self.assertEqual(row["provider_event_id"], "emailbison:abc-123")
        self.assertEqual(row["provider_timestamp"], "2026-09-26T10:00:00+00:00")
        self.assertIn("observed_at", row)
        self.assertEqual(outcome["ledger"]["state"], actionledger.PROVIDER_SENT)

    def test_replay_writes_no_additional_row(self):
        rec = _make_record()
        recs = [rec]
        event = _send_event()

        inbound.handle(event, recs)
        self.assertEqual(len(actionledger.load()), 1)

        recs2 = [rec]
        inbound.handle(event, recs2)
        self.assertEqual(len(actionledger.load()), 1)

    def test_two_different_sends_write_two_rows(self):
        rec = _make_record()
        inbound.handle(_send_event(provider_event_id="emailbison:first"), [rec])
        inbound.handle(_send_event(provider_event_id="emailbison:second"), [rec])
        self.assertEqual(len(actionledger.load()), 2)


class ReplyLeavesOneRow(QueueTest):
    """Acceptance 2: a reply writes a row with contact key, provider timestamp
    and observation time, and they are distinguishable."""

    def setUp(self):
        super().setUp()
        self.ledger_path = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        super().tearDown()

    def test_reply_row_carries_contact_key_and_both_timestamps(self):
        rec = _make_record()
        event = _reply_event(at="2026-09-26T11:30:00+00:00")

        outcome = inbound.handle(event, [rec])

        rows = actionledger.load()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["state"], actionledger.PROVIDER_REPLIED)
        self.assertEqual(row["contact_key"], "k1")
        self.assertEqual(row["provider_timestamp"], "2026-09-26T11:30:00+00:00")
        self.assertIn("observed_at", row)
        self.assertNotEqual(row["provider_timestamp"], row["observed_at"])
        self.assertEqual(row["provider"], "emailbison")
        self.assertEqual(row["campaign_id"], 99)
        self.assertIsNotNone(outcome["ledger"])

    def test_reply_replay_writes_no_additional_row(self):
        rec = _make_record()
        event = _reply_event()

        inbound.handle(event, [rec])
        self.assertEqual(len(actionledger.load()), 1)

        inbound.handle(event, [rec])
        self.assertEqual(len(actionledger.load()), 1)

    def test_two_different_replies_write_two_rows(self):
        rec = _make_record()
        e1 = _reply_event(provider_event_id="heyreach:t1:2026-09-26T11:00:00")
        e2 = _reply_event(provider_event_id="heyreach:t1:2026-09-26T14:00:00")

        inbound.handle(e1, [rec])
        inbound.handle(e2, [rec])

        rows = actionledger.load()
        self.assertEqual(len(rows), 2)
        keys = {r["key"] for r in rows}
        self.assertEqual(len(keys), 2)


class GuardIsSeenToFail(QueueTest):
    """Acceptance 3: remove the write-back call, the test fails."""

    def setUp(self):
        super().setUp()
        self.ledger_path = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        super().tearDown()

    def test_no_write_back_means_no_row(self):
        rec = _make_record()
        event = _send_event()

        with mock.patch.object(inbound, "_write_back_to_ledger",
                               return_value=None):
            outcome = inbound.handle(event, [rec])

        rows = actionledger.load()
        self.assertEqual(len(rows), 0)
        self.assertIsNone(outcome.get("ledger"))


class EventWithoutIdWritesNothing(QueueTest):
    """Acceptance 5: an event without a provider_event_id writes nothing."""

    def setUp(self):
        super().setUp()
        self.ledger_path = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        super().tearDown()

    def test_missing_provider_event_id_writes_no_row(self):
        rec = _make_record()
        event = _send_event()
        event.pop("provider_event_id", None)
        event["provider_event_id"] = None

        inbound.handle(event, [rec])

        rows = actionledger.load()
        self.assertEqual(len(rows), 0)


class ObservationDoesNotAffectDailyCount(QueueTest):
    """Provider observations must not inflate count_on."""

    def setUp(self):
        super().setUp()
        self.ledger_path = os.path.join(self.tmp, "work", "action-ledger.jsonl")
        os.environ["ACTION_LEDGER"] = self.ledger_path

    def tearDown(self):
        os.environ.pop("ACTION_LEDGER", None)
        super().tearDown()

    def test_observed_send_not_counted_by_count_on(self):
        rec = _make_record()
        inbound.handle(_send_event(), [rec])

        day = "2026-09-26"
        self.assertEqual(actionledger.count_on(day, channel="email"), 0)

    def test_observed_reply_not_counted_by_count_on(self):
        rec = _make_record()
        inbound.handle(_reply_event(), [rec])

        day = "2026-09-26"
        self.assertEqual(actionledger.count_on(day), 0)


if __name__ == "__main__":
    unittest.main()
