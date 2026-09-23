r"""Every sending domain read "no sends in the last 7 days" on a day with 316.

MEASURED LIVE, 2026-09-22, running the client probes against the bound
channel. Asked a question that reaches `sending_domains`, the agent listed
all 69 of Productive's sending domains and marked **every single one** `no
sends in the last 7 days` - while campaigns 491-495 had sent 316 emails
that day from those very mailboxes.

## THE SHAPE

`scheduled_emails()` returns the provider's rows untrimmed, and
`sender_email` on them is an OBJECT, not an address:

    {"id": 3392,
     "name": "Sender One",
     "email": "sender.one@sending-domain-a.example.test",
     "email_signature": "<p>...VP of Business Development @ExampleCo</p>",
     "daily_limit": 15, ...}

`_recent_send_domains` and `_week_for_domain` both did:

    address = str(row.get("sender_email") or "")
    if not stamp or "@" not in address:
        continue
    ... address.rsplit("@", 1)[-1].lower()

## AND THE GUARD IS WHAT MADE IT SILENT

`str(a_dict)` is the whole repr, and the repr CONTAINS an `@` - from
`@ExampleCo` inside the HTML signature. So `"@" not in address` was False,
the row was not skipped, and `rsplit("@", 1)[-1]` returned the tail of a
mangled signature. Never a domain, never a match, never an error.

A row with no sender at all would have been skipped honestly. A row with a
sender was silently misread. The guard that existed to catch a missing
address passed *because* of the field it was meant to validate.

## WHY THE SUITE DID NOT CATCH IT

`tests/test_the_question_is_one_domain_not_the_list.py` mocks
`_week_for_domain` itself, and the `sending_domains` tests mock
`_recent_send_domains`. Both mock the function that had the bug, so no test
in this repository has ever handed either of them a provider row. This file
does, and it uses the real shape - dict, `email` key, and a signature
carrying the `@` that defeated the guard.

`src/leadobserve.py:435` reads the same field correctly and has all along:
`row.get("sender_email") if isinstance(..., dict) else {}`, then
`.get("email")`. The shape was known here. Two functions did not ask.
"""
import datetime
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackagenttools as tools                         # noqa: E402
from src.providers import bison                                  # noqa: E402

PACK = {"workspaces": {"alpha": {"provider_campaign_ids": ["491"]}}}

#: A signature with an `@` in it, because that is the character that made
#: the guard pass. Trimmed from the live row.
SIGNATURE = ("<p>Sender One</p><p>VP of Business Development "
             "@ExampleCo</p>")


def _now_iso(minutes_ago=30):
    when = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(minutes=minutes_ago)
    return when.strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def row(domain="sending-domain-a.example.test", local="sender.one",
        lead_id=1, minutes_ago=30, status="sent"):
    """One queue row in the provider's real shape."""
    return {"id": lead_id, "status": status, "sent_at": _now_iso(minutes_ago),
            "lead": {"id": lead_id},
            "sender_email": {"id": 3392, "name": "Sender One",
                             "email": "%s@%s" % (local, domain),
                             "email_signature": SIGNATURE,
                             "daily_limit": 15}}


class TheDomainIsReadOffTheSenderObject(unittest.TestCase):

    def setUp(self):
        self._pack = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: PACK
        self.addCleanup(setattr, tools.knowledge, "pack", self._pack)

    def queue(self, rows):
        return mock.patch.object(bison, "scheduled_emails",
                                 lambda cid: list(rows))

    # ------------------------------------------- _recent_send_domains

    def test_a_domain_that_sent_today_is_reported_as_recent(self):
        """The live finding, as one assertion."""
        with self.queue([row()]):
            found, unreadable, capped = tools._recent_send_domains("alpha")
        self.assertEqual(found, {"sending-domain-a.example.test"})
        self.assertEqual(unreadable, 0)

    def test_the_signature_does_not_become_a_domain(self):
        """`str(dict)` carries an `@` from the signature. Nothing derived
        from that text may reach the answer."""
        with self.queue([row()]):
            found, _unreadable, _capped = tools._recent_send_domains("alpha")
        for domain in found:
            self.assertNotIn("exampleco", domain)
            self.assertNotIn("</p>", domain)
            self.assertNotIn("<", domain)
            self.assertNotIn(" ", domain)
            self.assertNotIn("'", domain)

    def test_several_senders_give_several_domains(self):
        rows = [row(domain="sending-domain-a.example.test"),
                row(domain="sending-domain-b.example.test", local="sender.two",
                    lead_id=2)]
        with self.queue(rows):
            found, _u, _c = tools._recent_send_domains("alpha")
        self.assertEqual(found, {"sending-domain-a.example.test", "sending-domain-b.example.test"})

    def test_a_sender_that_is_a_plain_string_still_works(self):
        """The provider is not the only caller shape, and a string address
        was what this code was written against."""
        plain = row()
        plain["sender_email"] = "sender.one@sending-domain-a.example.test"
        with self.queue([plain]):
            found, _u, _c = tools._recent_send_domains("alpha")
        self.assertEqual(found, {"sending-domain-a.example.test"})

    def test_a_row_with_no_sender_is_skipped_not_guessed(self):
        blank = row()
        blank["sender_email"] = None
        with self.queue([blank]):
            found, _u, _c = tools._recent_send_domains("alpha")
        self.assertEqual(found, set())

    def test_a_sender_object_with_no_email_key_is_skipped(self):
        broken = row()
        broken["sender_email"] = {"id": 7, "name": "Nobody",
                                  "email_signature": SIGNATURE}
        with self.queue([broken]):
            found, _u, _c = tools._recent_send_domains("alpha")
        self.assertEqual(found, set())

    def test_a_send_outside_the_window_is_not_recent(self):
        with self.queue([row(minutes_ago=60 * 24 * 9)]):
            found, _u, _c = tools._recent_send_domains("alpha")
        self.assertEqual(found, set())

    # ------------------------------------------------ _week_for_domain

    def test_the_week_counts_emails_and_people_for_the_domain(self):
        rows = [row(lead_id=1), row(lead_id=2), row(lead_id=2, minutes_ago=90)]
        with self.queue(rows):
            emails, people, unreadable, capped = tools._week_for_domain(
                "alpha", "sending-domain-a.example.test")
        self.assertEqual(emails, 3)
        self.assertEqual(people, 2)
        self.assertEqual(unreadable, 0)

    def test_another_domains_sends_are_not_counted_for_this_one(self):
        rows = [row(domain="sending-domain-a.example.test"),
                row(domain="sending-domain-b.example.test", lead_id=2)]
        with self.queue(rows):
            emails, people, _u, _c = tools._week_for_domain(
                "alpha", "sending-domain-a.example.test")
        self.assertEqual(emails, 1)
        self.assertEqual(people, 1)

    def test_the_week_is_zero_rather_than_wrong_for_an_unknown_domain(self):
        with self.queue([row()]):
            emails, people, _u, _c = tools._week_for_domain(
                "alpha", "not-ours.example.test")
        self.assertEqual((emails, people), (0, 0))

    # --------------------------------------------- and end to end

    def test_sending_domains_does_not_call_a_sending_domain_quiet(self):
        """The whole defect from the answer's side: the recency flag on a
        domain that sent thirty minutes ago."""
        with self.queue([row()]):
            found, _u, _c = tools._recent_send_domains("alpha")
        self.assertIn("sending-domain-a.example.test", found,
                      "a domain that sent today read as quiet")


if __name__ == "__main__":
    unittest.main()
