#!/usr/bin/env python3
"""Being known twice must not make somebody harder to stop.

REPRODUCED on 2026-09-12 in an isolated estate. The same decision maker was
held on two queue records - the ordinary shape when an account is uploaded
under two domains, or a parent and a subsidiary both appear in a list - and
they replied:

    "please stop, we are not interested"

`events.match_record` found two records carrying the address, refused to
guess which one the reply answered, and returned `None`. `events.apply`
reported `unmatched`. `inbound.handle` fired a Slack notice that nothing was
delivering and returned. Both records stayed unpaused, and
`eligibility.decide` answered `eligible` on both, so the cadence kept running
to somebody who had just asked it to stop.

The identical reply from the identical person, held on ONE record, paused
correctly. Being known twice made the person less safe, which is backwards.

## What was wrong, precisely

Not the refusal to guess. Attributing a reply to the wrong company pauses the
wrong company, writes the wrong log and alerts the wrong operator, and
`match_record`'s comment says so. The mistake was treating a STOP as though
it were an ATTRIBUTION. They are different questions:

    whose reply is this          - refused, correctly, for a person to answer
    who did this person say it to - answerable, and every one of them stops

So `events.correspondents` answers the second, `accountpolicy.
hold_for_unattributed_reply` applies a hold to each, and nothing claims any
record received anything: no reply event, no classification, no attribution.

## Why a hold and not a stop

The reply has not been classified - nobody has read it. It could be "please
remove us" or "sure, Thursday works". Treating an unread reply as an
unsubscribe throws away the good ones; treating it as nothing is the defect
above. A hold is what a person can reverse in the time it takes to read it.
"""
import os
import unittest

from src import accountpolicy, eligibility, events, inbound, store
from tests.base import QueueTest

ADDRESS = "dana@acme.test"
PROFILE = "https://www.linkedin.com/in/dana-marsh"


def a_record(rid, domain, email=ADDRESS, linkedin=PROFILE, key="dana-marsh"):
    rec = store.new_record(rid, "domains", "productive", f"Co {rid}", domain)
    rec["state"] = "verified"
    rec["contacts"] = [{
        "key": key, "name": "Dana Marsh", "title": "Head of Operations",
        "email": email, "linkedin": linkedin, "selected": True,
        "verdict": "valid", "sendable": True, "persona": "champion",
    }]
    return rec


def a_reply(at="2026-09-12T10:00:00+00:00", email=ADDRESS, **over):
    event = {"type": events.REPLY_RECEIVED, "provider": "emailbison",
             "email": email, "at": at, "channel": "email",
             "provider_event_id": "evt-1",
             "text": "please stop, we are not interested"}
    event.update(over)
    return event


class OneRecordIsTheBaseline(QueueTest):
    """Without this the rest proves nothing: the single-record case works."""

    def setUp(self):
        super().setUp()
        self._pinned = {k: os.environ.pop(k, None)
                        for k in ("CAMPAIGNS", "ACTION_LEDGER", "NOTIFICATIONS")}
        store.append([a_record("only-one", "one.test")])

    def tearDown(self):
        for key, value in self._pinned.items():
            if value is not None:
                os.environ[key] = value
        super().tearDown()

    def test_the_reply_is_attributed_and_stops_the_cadence(self):
        recs = store.load()
        out = inbound.handle(a_reply(), recs)
        self.assertEqual(out["applied"]["status"], "applied")
        rec = recs[0]
        self.assertTrue(rec.get("paused") or rec["contacts"][0].get("paused"),
                        "the single-record case does not stop either")


class TheSamePersonOnTwoRecords(QueueTest):

    def setUp(self):
        super().setUp()
        self._pinned = {k: os.environ.pop(k, None)
                        for k in ("CAMPAIGNS", "ACTION_LEDGER", "NOTIFICATIONS")}
        store.append([a_record("acct-one", "one.test"),
                      a_record("acct-two", "two.test")])

    def tearDown(self):
        for key, value in self._pinned.items():
            if value is not None:
                os.environ[key] = value
        super().tearDown()

    def test_attribution_is_still_refused(self):
        """The half that was already right, and must stay right."""
        recs = store.load()
        out = inbound.handle(a_reply(), recs)
        self.assertEqual(out["applied"]["status"], "unmatched")

    def test_but_every_record_holding_that_person_stops(self):
        """REWRITTEN 2026-09-24, because the outcome got STRONGER.

        The fixture reply is `"please stop, we are not interested"` - the
        exact words of the 2026-09-12 reproduction - and until today that read
        NEGATIVE, so this branch gave it the reversible ambiguous-reply hold.

        The operator's 2026-09-24 decision removed the unsubscribe link and
        made the reply the whole opt-out mechanism, and `please stop` as a
        complete clause is now an unsubscribe. So the person who said it is
        SUPPRESSED on both records rather than held on both, and is on the
        agency-wide list besides.

        The assertion moved; the thing this file is about did not. Being known
        twice still must not make somebody harder to stop, and the hold path
        is still exercised - by `test_an_unclassifiable_reply_is_only_held`
        below, which is what that path is for.
        """
        recs = store.load()
        out = inbound.handle(a_reply(), recs)
        self.assertEqual(len(out["suppressed_unattributed"]), 2,
                         "the reply stopped nothing on either record")
        for rec in recs:
            contact = rec["contacts"][0]
            self.assertTrue(contact.get("unsubscribed"),
                            f"{rec['id']} kept running to somebody who "
                            f"asked it to stop")
            self.assertEqual(contact["suppressed"]["reason"],
                             accountpolicy.UNSUBSCRIBE)

    def test_an_unclassifiable_reply_is_only_held(self):
        """The guard this branch was built for, kept under its own name.

        An unread reply is not an unsubscribe. Only a classified removal
        request suppresses; everything else takes the reversible hold, which
        is what a person can undo in the time it takes to read the reply.
        """
        recs = store.load()
        out = inbound.handle(
            a_reply(text="Thanks - could you resend the deck?"), recs)
        self.assertEqual(out["suppressed_unattributed"], [])
        self.assertEqual(len(out["held_unattributed"]), 2)
        for rec in recs:
            contact = rec["contacts"][0]
            self.assertFalse(contact.get("unsubscribed"))
            self.assertEqual(contact["paused"]["reason"],
                             accountpolicy.AMBIGUOUS_REPLY)

    def test_the_send_gate_now_refuses_both(self):
        """The link that matters. A flag nothing reads would be the same
        defect wearing a different field name."""
        recs = store.load()
        inbound.handle(a_reply(), recs)
        with store.transaction() as rows:
            rows[:] = recs
        for rec in store.load():
            decided = eligibility.decide(rec, rec["contacts"][0], "day3",
                                         channel="email", recs=[rec])
            self.assertNotEqual(decided.get("verdict"), "eligible",
                                f"{rec['id']} is still eligible to send")

    def test_nothing_was_attributed_to_either_record(self):
        """A hold is not a claim that this record received the reply."""
        recs = store.load()
        inbound.handle(a_reply(), recs)
        for rec in recs:
            replies_on_it = [e for e in rec.get("events") or []
                             if events.is_reply(e)]
            self.assertEqual(replies_on_it, [],
                             f"{rec['id']} was told it received a reply that "
                             f"nobody could attribute")

    def test_a_linkedin_reply_with_no_address_holds_them_too(self):
        """HeyReach replies carry a profile and no address, which is the
        channel where one person on two records is most likely."""
        recs = store.load()
        out = inbound.handle(
            a_reply(email=None, linkedin=PROFILE, channel="linkedin",
                    provider="heyreach"), recs)
        # Suppressed rather than held since 2026-09-24 - see
        # `test_but_every_record_holding_that_person_stops`. What this case
        # is about is the CORRELATION KEY: a HeyReach reply carries a profile
        # and no address, and both records still have to be reached.
        self.assertEqual(len(out["suppressed_unattributed"]), 2)

    def test_a_reply_from_a_stranger_holds_nobody(self):
        """The other half: a guard that held everybody would be deleted."""
        recs = store.load()
        out = inbound.handle(a_reply(email="nobody@elsewhere.test"), recs)
        self.assertEqual(out["held_unattributed"], [])
        for rec in recs:
            self.assertFalse(rec["contacts"][0].get("paused"))

    def test_a_second_copy_of_the_same_reply_changes_nothing_again(self):
        """Idempotent: the transition refuses to re-apply, so a provider
        redelivering an event does not rewrite the reason or the timestamp.

        Renamed from `..._holds_nothing_again` when the fixture reply became
        an unsubscribe on 2026-09-24. The property is the same one.
        """
        recs = store.load()
        inbound.handle(a_reply(), recs)
        first = recs[0]["contacts"][0]["suppressed"]["since"]
        out = inbound.handle(a_reply(at="2026-09-12T11:00:00+00:00"), recs)
        self.assertEqual(out["held_unattributed"], [])
        self.assertEqual(out["suppressed_unattributed"], [])
        self.assertEqual(recs[0]["contacts"][0]["suppressed"]["since"], first)


if __name__ == "__main__":
    unittest.main()
