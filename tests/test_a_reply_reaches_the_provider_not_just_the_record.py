#!/usr/bin/env python3
"""A reply pauses the record AND stops the queue. Both, or it is not a stop.

`leadstop.stop_contact` being correct proves nothing on its own - the
recurring defect in this repository is a thing computed correctly that nothing
downstream calls. This drives `inbound.handle`, which is what actually runs
when a reply arrives, and asserts the provider was told.

The distinction being tested is the one that was missing: pausing the record
stops US planning another step, while the provider keeps its own scheduler and
its own queue. A person can be "paused" here and still receive the next three
emails.
"""
import unittest

from src import events, inbound, leadstop, store
from tests.base import QueueTest


class Recorder:
    """Stands in for the provider, and remembers who was stopped."""

    def __init__(self, fail=False):
        self.stopped = []
        self.fail = fail

    def __call__(self, rec, contact, why, **kwargs):
        if self.fail:
            raise leadstop.StopUnverified("provider state is unknown")
        self.stopped.append((rec.get("id"), contact.get("key"), why))
        return {"stopped": True, "record": rec.get("id"),
                "contact": contact.get("key"), "why": why}


def record(rid="rec-1", lead_id=11):
    contact = {"key": "ck-1", "email": "person@example.com",
               "first_name": "Test", "last_name": "Person", "sendable": True}
    if lead_id is not None:
        contact["bison_lead_id"] = lead_id
    return {"id": rid, "client": "productive", "domain": "example.com",
            "company": "Example", "state": "ready", "contacts": [contact]}


def reply_event(rid="rec-1"):
    return {"type": events.REPLY_RECEIVED, "channel": "email",
            "provider": "emailbison",
            "provider_event_id": f"probe:{rid}:1",
            "record_id": rid, "contact_key": "ck-1", "client": "productive",
            "at": store.now(), "text": "please take me off your list"}


class AReplyReachesTheProvider(QueueTest):

    def setUp(self):
        super().setUp()
        self.recorder = Recorder()
        self._real = leadstop.stop_contact
        leadstop.stop_contact = self.recorder
        self.addCleanup(setattr, leadstop, "stop_contact", self._real)

    def test_the_provider_is_told_to_stop_this_person(self):
        recs = [record()]
        store.save(recs)
        outcome = inbound.handle(reply_event(), store.load())
        self.assertEqual(len(self.recorder.stopped), 1,
                         "the reply paused the record and told nobody")
        rid, key, why = self.recorder.stopped[0]
        self.assertEqual((rid, key), ("rec-1", "ck-1"))
        self.assertEqual(why, events.REPLY_RECEIVED)
        # PER CHANNEL since 2026-09-23. `provider_stop` is keyed by channel
        # so a reader can tell "stopped on email, no LinkedIn lead" from
        # "stopped on both" - the distinction the watcher line was eliding.
        self.assertTrue(
            ((outcome.get("provider_stop") or {}).get("email") or {})
            .get("stopped"))

    def test_a_contact_with_no_provider_binding_is_a_no_op(self):
        """Every record staged before this existed has no lead id.

        It now returns an entry PER CHANNEL saying it was not attempted,
        rather than a bare None. "there was nothing to stop" and "we did not
        look" used to print the same, and the second is a defect.
        """
        store.save([record(lead_id=None)])
        outcome = inbound.handle(reply_event(), store.load())
        self.assertEqual(self.recorder.stopped, [])
        stops = outcome.get("provider_stop") or {}
        self.assertEqual(set(stops), {"email", "linkedin"})
        for channel, entry in stops.items():
            with self.subTest(channel=channel):
                self.assertFalse(entry["attempted"])
                self.assertFalse(entry["stopped"])

    def test_a_failed_stop_does_not_lose_the_reply(self):
        """The reply is the thing a person can still act on.

        Losing it because the stop failed trades a queued email for a lost
        one, and only the queued email can still be apologised for.
        """
        self.recorder.fail = True
        store.save([record()])
        outcome = inbound.handle(reply_event(), store.load())
        self.assertEqual(outcome["applied"]["status"], "applied")
        self.assertIsNotNone(outcome.get("classification"))
        stop = (outcome.get("provider_stop") or {}).get("email") or {}
        self.assertFalse(stop.get("stopped"))
        self.assertTrue(stop.get("attempted"),
                        "a stop that was tried and failed must not read the "
                        "same as one that was never tried")
        self.assertEqual(stop.get("error"), "StopUnverified",
                         "a failed stop was swallowed instead of reported")

    def test_the_record_is_still_paused(self):
        """The local pause is not replaced by the provider stop."""
        store.save([record()])
        outcome = inbound.handle(reply_event(), store.load())
        self.assertTrue(outcome["paused"])


if __name__ == "__main__":
    unittest.main()
