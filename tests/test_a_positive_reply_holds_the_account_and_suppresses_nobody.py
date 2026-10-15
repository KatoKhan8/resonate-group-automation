"""A positive reply holds the account and suppresses nobody.

`accountpolicy`'s row for a positive reply is HOLD + ACCOUNT: another
decision maker said yes, so the whole company is paused for a person to
take the conversation, and nobody is suppressed. Suppression is the
permanent state - `unsubscribed`, the field every eligibility gate reads -
while a hold is reversible by whichever person reads the reply. A positive
reply is the one outcome where suppressing would throw away the best thing
the system exists for: somebody asked to talk.

What exists already does not hold this. `test_account_saturation` proves a
positive reply stops the ACCOUNT as far as the planner is concerned - but a
suppressed account also stops the planner, so that assertion passes under
a suppression policy too. Nobody asserts the policy's own state markers:
that no contact is left unsubscribed or suppressed, and that the record is
paused rather than suppressed.

Two properties, two tests, two mutations (the same policy row broken in
two directions): turning the outcome to STOP suppresses the account, and
narrowing the scope to the contact alone leaves the account unheld.
"""
import unittest

from src import accountpolicy as ap
from src import events
from tests.base import QueueTest

AT = "2026-10-15T00:00:00Z"


def _record():
    return {
        "id": "rec-1", "client": "productive", "domain": "example.com",
        "company": "Example", "state": "ready",
        "contacts": [
            {"key": "alice", "name": "Alice Example",
             "email": "alice@example.com", "sendable": True},
            {"key": "bob", "name": "Bob Example",
             "email": "bob@example.com", "sendable": True},
        ],
    }


class APositiveReplyHoldsTheAccountAndSuppressesNobody(QueueTest):

    def _replied(self):
        rec = _record()
        ap.apply_reply(rec, "alice", ap.POSITIVE, at=AT, channel="email")
        return rec

    def test_nobody_is_suppressed(self):
        rec = self._replied()
        self.assertIsNone(
            rec.get("suppression"),
            "a positive reply suppressed the whole account")
        for contact in rec["contacts"]:
            which = contact["key"]
            self.assertFalse(
                contact.get("unsubscribed"),
                f"contact {which} was unsubscribed by a positive reply")
            self.assertFalse(
                contact.get("suppressed"),
                f"contact {which} was suppressed by a positive reply")
        markers = [e.get("type") for e in rec.get("events") or []]
        self.assertNotIn(
            events.CONTACT_SUPPRESSED, markers,
            "a CONTACT_SUPPRESSED event was written for a positive reply")

    def test_the_account_is_held_for_a_person(self):
        rec = self._replied()
        self.assertTrue(
            rec.get("paused"),
            "a positive reply did not hold the account")
        alice = rec["contacts"][0]
        self.assertTrue(
            alice.get("paused"),
            "the replier was not held")
        self.assertFalse(
            alice.get("stopped"),
            "the replier was stopped outright rather than held")


if __name__ == "__main__":
    unittest.main()
