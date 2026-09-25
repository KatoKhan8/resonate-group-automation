"""Our own identifiers must survive the inbound reply path.

MEASURED 2026-09-25 on a real reply. `GET /api/replies` returns the message
at the top level and the LEAD nested under it, and `adapters._custom` only
ever read the top level:

    row["custom_variables"]          -> None
    row["lead"]["custom_variables"]  -> record_id, contact_key, client, ...

So `record_id`, `contact_key` and `client` were None for EVERY EmailBison
reply this system has ever ingested, and `events.match_record` could never
use its first and only unambiguous branch.

It hid because the fallback works: `match_record` then matches on the
from-address, and for an ordinary prospect that IS the contact's address. It
surfaced only when a reply arrived from an address the contact record did not
carry - unmatched, no stop, no error, no alert.

The row shape here is the real one, with every real value replaced.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import adapters                                       # noqa: E402
from src import events                                         # noqa: E402


def reply_row(nested=True, top=False):
    """One `/api/replies` row, shaped as the provider actually returns it."""
    variables = [
        {"name": "record_id", "value": "rec-1"},
        {"name": "contact_key", "value": "ada-lovelace"},
        {"name": "client", "value": "tenant-a"},
        {"name": "subject_1", "value": "a subject"},
    ]
    row = {
        "id": 1609999, "lead_id": 999001, "campaign_id": 777,
        "folder": "Inbox", "automated_reply": False,
        "from_email_address": "ada@example.invalid",
        "created_at": "2026-09-25T09:45:34.000000Z",
        "html_body": "<p>no thanks</p>",
        "lead": {"id": 999001, "email": "ada@example.invalid",
                 "first_name": "Ada"},
    }
    if nested:
        row["lead"]["custom_variables"] = variables
    if top:
        row["custom_variables"] = variables
    return {"data": [row]}


class TestTheIdentifiersReachTheEvent(unittest.TestCase):

    def test_variables_nested_under_lead_reach_the_event(self):
        """The real shape. This is what was broken."""
        out = adapters.from_emailbison(reply_row(nested=True))
        self.assertEqual(len(out), 1)
        event = out[0]
        self.assertEqual(event.get("record_id"), "rec-1")
        self.assertEqual(event.get("contact_key"), "ada-lovelace")
        self.assertEqual(event.get("client"), "tenant-a")

    def test_variables_at_the_top_level_still_reach_the_event(self):
        """A webhook batch carries them at the top level. Must keep working."""
        event = adapters.from_emailbison(reply_row(nested=False, top=True))[0]
        self.assertEqual(event.get("record_id"), "rec-1")

    def test_the_top_level_wins_when_both_carry_them(self):
        event = adapters.from_emailbison(reply_row(nested=True, top=True))[0]
        self.assertEqual(event.get("record_id"), "rec-1")

    def test_the_event_matches_its_record_BY_ID_not_by_address(self):
        """THE EFFECT, which is the point.

        The record deliberately carries a DIFFERENT address from the one the
        reply came from, so a pass here can only come from `record_id`. That
        is the exact condition the live failure had: the fallback could not
        save it, and without the identifiers nothing matched.
        """
        event = adapters.from_emailbison(reply_row(nested=True))[0]
        recs = [{"id": "rec-1", "client": "tenant-a",
                 "contacts": [{"key": "ada-lovelace",
                               "email": "a.different.address@example.invalid"}]}]
        self.assertIsNotNone(
            events.match_record(recs, event),
            "the reply did not match its own record, so no stop can fire")

    def test_no_variables_anywhere_is_not_an_error(self):
        out = adapters.from_emailbison(reply_row(nested=False, top=False))
        self.assertEqual(len(out), 1)
        self.assertIsNone(out[0].get("record_id"))


if __name__ == "__main__":
    unittest.main()
