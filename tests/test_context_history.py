"""What an account has already heard, carried into the campaign brief.

The pack answered "why these companies, why now, and what may we say" and
said nothing about what had already been said. `account.graph` knew and
`outreachclaims` knew; the pack read neither, so a brief for an account
somebody emailed twice last month read exactly like a brief for a cold one.

Two failures are worth more than the rest of this file.

**A planned touch becoming history.** A step that was built, approved, and
never left is not outreach that happened. If it reaches a history block it
becomes "we reached out" in the next message, to somebody who never heard
from us.

**The Anna/Mark mismatch.** Mark sent the email; the message says "my
colleague Anna emailed you". The prospect can forward that sentence to
Anna and get an immediate denial. The actor is read off the event, which
is why `push.mark_pushed` writes it there.
"""
import unittest

from src import account, contextpack, events, touch
from tests.campaignbase import CampaignTest

WS = "productive"
MARK = "mark"
ANNA = "anna"

ROSTER = [
    {"workspace": WS, "sender_id": MARK, "display_name": "Mark Weber"},
    {"workspace": WS, "sender_id": ANNA, "display_name": "Anna Fischer"},
]


def sent(contact="john", at="2026-08-01T09:00:00+00:00", sender=MARK,
         channel="email", kind=None):
    return {"type": kind or events.PUSH_MARKED, "contact": contact,
            "channel": channel, "step": "day1", "at": at,
            "sender_id": sender}


def prepared(contact="sarah", at="2026-08-02T09:00:00+00:00", sender=ANNA):
    """Built and never sent. `push_prepared` is absent from
    `touch.CONFIRMING_EVENTS` by name, and this is why."""
    return sent(contact, at, sender, kind=events.PUSH_PREPARED)


def replied(contact="john", at="2026-08-03T09:00:00+00:00", positive=False):
    return {"type": (events.POSITIVE_REPLY_DETECTED if positive
                     else events.REPLY_RECEIVED),
            "contact": contact, "channel": "email", "at": at}


def a_record(events_=(), **kw):
    rec = {"id": "acme", "company": "Acme Services", "domain": "acme.test",
           "client": WS, "events": list(events_),
           "contacts": [
               {"key": "john", "name": "John Doe", "title": "COO",
                "selected": True, "email": "john@acme.test"},
               {"key": "sarah", "name": "Sarah Ling", "title": "VP Ops",
                "selected": True, "email": "sarah@acme.test"}]}
    rec.update(kw)
    return rec


def history(rec, rows=ROSTER):
    return contextpack.account_history(rec, WS, rows=rows)


class OnlyConfirmedEventsAreFacts(unittest.TestCase):

    def test_a_confirmed_touch_is_a_fact(self):
        found = history(a_record([sent()]))
        self.assertEqual(len(found["confirmed_touches"]), 1)
        fact = found["confirmed_touches"][0]
        self.assertEqual(fact["contact"], "John Doe")
        self.assertEqual(fact["channel"], "email")
        self.assertEqual(fact["actor"], "Mark Weber")
        self.assertEqual(fact["state"], touch.SENT)
        self.assertEqual(fact["account"], "Acme Services")
        self.assertEqual(fact["workspace"], WS)
        self.assertTrue(fact["at"])
        self.assertTrue(fact["event"])

    def test_a_prepared_touch_is_not_in_the_facts_at_all(self):
        """Not present with a flag. Absent. A caller iterating a mixed list
        and writing "we contacted" gets it wrong on the first planned row,
        and a boolean is what a template forgets to read."""
        found = history(a_record([prepared()]))
        self.assertEqual(found["confirmed_touches"], [])
        self.assertTrue(found["cold"])

    def test_but_it_is_counted_rather_than_hidden(self):
        found = history(a_record([prepared()]))
        self.assertEqual(found["planned_not_sent"], 1)

    def test_a_planned_touch_never_names_its_sender_anywhere(self):
        """The sender on a planned step is the one most likely to be
        wrongly claimed: it is assigned, it is real, and nothing happened.
        """
        found = history(a_record([prepared(sender=ANNA)]))
        blob = repr(found)
        self.assertNotIn("Anna", blob)
        self.assertNotIn(ANNA, blob)

    def test_the_boundary_raises_rather_than_filters(self):
        """A planned touch silently dropped from a list is a list that is
        quietly wrong. One that stops the build is one somebody fixes."""
        for state in (touch.PLANNED, touch.APPROVED, touch.PAYLOAD_READY,
                      touch.BLOCKED, touch.FAILED, touch.SKIPPED):
            with self.assertRaises(contextpack.NotAFact, msg=state):
                contextpack._fact(
                    {"state": state, "confirmed": False, "channel": "email"},
                    "John Doe", "Acme", "acme", WS)

    def test_every_confirmed_state_is_accepted(self):
        for state in touch.CONFIRMED_STATES:
            fact = contextpack._fact(
                {"state": state, "confirmed": True, "channel": "email",
                 "sender_id": MARK, "actor": "Mark Weber"},
                "John Doe", "Acme", "acme", WS)
            self.assertEqual(fact["state"], state)

    def test_a_row_claiming_confirmed_with_a_planned_state_is_refused(self):
        """Both halves are checked. A caller that sets the flag and not the
        state, or the state and not the flag, is refused either way."""
        with self.assertRaises(contextpack.NotAFact):
            contextpack._fact(
                {"state": touch.PLANNED, "confirmed": True}, "J", "A", "a", WS)
        with self.assertRaises(contextpack.NotAFact):
            contextpack._fact(
                {"state": touch.SENT, "confirmed": False}, "J", "A", "a", WS)


class TheActorIsWhoeverActuallySentIt(CampaignTest):
    """The Anna/Mark mismatch, permanently.

    A message that says "my colleague Anna emailed you" when Mark sent it
    is the worst kind of error this system can make: the prospect can
    forward the sentence to Anna and get a denial. `push.mark_pushed`
    writes the sender onto the event at the moment of sending for exactly
    this reason.
    """

    def test_the_history_names_the_sender_on_the_event(self):
        found = history(a_record([sent(sender=MARK)]))
        self.assertEqual(found["heard_from"], {"email": ["Mark Weber"]})

    def test_it_does_not_name_anna_when_mark_sent_it(self):
        found = history(a_record([sent(sender=MARK)]))
        self.assertNotIn("Anna Fischer", repr(found))

    def test_a_reassignment_after_the_send_does_not_rewrite_history(self):
        """Reading the *current* assignment instead would let somebody
        reassign an account and change who a past message came from."""
        rec = a_record([sent(sender=MARK)])
        rec["contacts"][0]["sender_assignment"] = {
            "email": {"sender_id": ANNA, "display_name": "Anna Fischer",
                      "account_id": "inbox-anna"},
            "at": "2026-08-05T09:00:00+00:00", "by": "operator"}
        found = history(rec)
        self.assertEqual(found["heard_from"], {"email": ["Mark Weber"]})
        self.assertEqual(found["confirmed_touches"][0]["actor"], "Mark Weber")

    def test_two_senders_on_two_channels_are_both_named(self):
        rec = a_record([sent(sender=MARK, channel="email"),
                        sent(contact="john", sender=ANNA, channel="linkedin",
                             at="2026-08-04T09:00:00+00:00")])
        found = history(rec)
        self.assertEqual(found["heard_from"],
                         {"email": ["Mark Weber"],
                          "linkedin": ["Anna Fischer"]})

    def test_an_unknown_sender_id_is_carried_rather_than_invented(self):
        """A roster that does not name them is a gap to see, not a blank."""
        found = history(a_record([sent(sender="ghost")]), rows=[])
        self.assertEqual(found["confirmed_touches"][0]["actor"], "ghost")


class TheHistoryIsCrossChannelAndPerPerson(unittest.TestCase):

    def test_it_carries_who_heard_what_on_which_channel(self):
        rec = a_record([
            sent(contact="john", sender=MARK, channel="email"),
            sent(contact="john", sender=ANNA, channel="linkedin",
                 at="2026-08-02T09:00:00+00:00"),
            sent(contact="sarah", sender=MARK, channel="email",
                 at="2026-08-05T09:00:00+00:00")])
        found = history(rec)
        pairs = {(t["contact"], t["channel"]) for t in found["confirmed_touches"]}
        self.assertEqual(pairs, {("John Doe", "email"),
                                 ("John Doe", "linkedin"),
                                 ("Sarah Ling", "email")})
        self.assertEqual(found["contacts_reached"], 2)
        self.assertEqual(sorted(found["channels"]), ["email", "linkedin"])

    def test_it_is_in_time_order(self):
        rec = a_record([sent(at="2026-08-05T09:00:00+00:00"),
                        sent(at="2026-08-01T09:00:00+00:00")])
        found = history(rec)
        stamps = [t["at"] for t in found["confirmed_touches"]]
        self.assertEqual(stamps, sorted(stamps))

    def test_replies_are_carried_with_their_classification(self):
        rec = a_record([sent(), replied(positive=True)])
        found = history(rec)
        self.assertEqual(len(found["replies"]), 1)
        self.assertTrue(found["replies"][0]["positive"])
        self.assertEqual(found["replies"][0]["contact"], "John Doe")

    def test_referrals_are_carried_with_both_ends_named(self):
        rec = a_record([sent(), {
            "type": events.REFERRAL_RECORDED, "contact": "john",
            "referred_to": "sarah", "at": "2026-08-04T09:00:00+00:00",
            "channel": "email"}])
        found = history(rec)
        self.assertEqual(len(found["referrals"]), 1)
        edge = found["referrals"][0]
        self.assertEqual(edge["from"], "John Doe")
        self.assertEqual(edge["to"], "Sarah Ling")

    def test_an_account_nobody_has_written_to_is_cold(self):
        found = history(a_record([]))
        self.assertTrue(found["cold"])
        self.assertEqual(found["confirmed_touches"], [])
        self.assertEqual(found["heard_from"], {})

    def test_a_long_history_is_capped_and_says_so(self):
        rec = a_record([sent(at=f"2026-08-{day:02d}T09:00:00+00:00")
                        for day in range(1, 21)])
        found = history(rec)
        self.assertEqual(found["confirmed_total"], 20)
        self.assertTrue(found["capped"])
        self.assertLessEqual(len(found["confirmed_touches"]),
                             contextpack.TOUCHES_PER_ACCOUNT)

    def test_every_row_names_its_workspace(self):
        found = history(a_record([sent(), replied(), {
            "type": events.REFERRAL_RECORDED, "contact": "john",
            "referred_to": "sarah", "at": "2026-08-04T09:00:00+00:00"}]))
        for block in ("confirmed_touches", "replies", "referrals"):
            for row in found[block]:
                self.assertEqual(row["workspace"], WS, block)


class ThePackCarriesIt(CampaignTest):

    def test_the_pack_has_a_history_block(self):
        recs = self.seed_records()
        pack = contextpack.build(recs, workspace=WS, config=self.config)
        self.assertIn("history", pack)
        self.assertIn("accounts", pack["history"])

    def test_a_cold_campaign_says_so_rather_than_showing_nothing(self):
        recs = self.seed_records()
        pack = contextpack.build(recs, workspace=WS, config=self.config)
        found = pack["history"]
        self.assertEqual(found["companies"], len(recs))
        self.assertEqual(found["with_history"] + found["cold"], len(recs))

    def test_a_touched_account_reaches_the_pack(self):
        recs = self.seed_records()
        recs[0].setdefault("events", []).append(
            sent(contact=recs[0]["contacts"][0]["key"], sender=MARK))
        pack = contextpack.build(recs, workspace=WS, config=self.config)
        found = pack["history"]
        self.assertGreaterEqual(found["with_history"], 1)
        self.assertGreaterEqual(found["touches"], 1)

    def test_accounts_with_history_come_first(self):
        recs = self.seed_records()
        self.assertGreater(len(recs), 1)
        recs[-1].setdefault("events", []).append(
            sent(contact=recs[-1]["contacts"][0]["key"], sender=MARK))
        pack = contextpack.build(recs, workspace=WS, config=self.config)
        shown = pack["history"]["accounts"]
        self.assertTrue(shown)
        self.assertEqual(shown[0]["record_id"], recs[-1]["id"])

    def test_the_block_says_what_it_counts(self):
        recs = self.seed_records()
        pack = contextpack.build(recs, workspace=WS, config=self.config)
        self.assertIn("confirmed", pack["history"]["note"].lower())


class ItAssertsNothingOfItsOwn(unittest.TestCase):
    """The pack's own rule. History is evidence a claim resolver checks; it
    is not a licence, and it must not write one."""

    def test_a_fact_carries_fields_and_never_a_sentence(self):
        """`account.timeline` has a `summary` string because it feeds a
        screen. This does not, deliberately: a prose summary in a structure
        a generator reads is a sentence somebody will paste.

        Asserted on the shape rather than by searching the source for
        phrases - the module quotes the phrases it must not produce, in
        order to explain why, and a test that reads prose fails when
        somebody writes some.
        """
        found = history(a_record([sent()]))
        self.assertEqual(
            set(found["confirmed_touches"][0]),
            {"workspace", "record_id", "account", "contact_key", "contact",
             "channel", "actor_id", "actor", "at", "event", "state", "step"})

    def test_it_reads_the_canonical_graph_rather_than_the_event_log(self):
        """A second walk of the event log with its own idea of what counts
        is a second definition of "confirmed"."""
        import inspect

        source = inspect.getsource(contextpack.account_history)
        self.assertIn("account.graph", source)
        self.assertNotIn('rec.get("events")', source)


if __name__ == "__main__":
    unittest.main()


class TheScreenShowsIt(CampaignTest):
    """The pack block reaches the campaign screen, and says the same thing
    the module does: planned is counted, never described."""

    def render(self, pack):
        from src.web import pages

        return pages._context_pack(pack)

    def pack(self, recs):
        return contextpack.build(recs, workspace=WS, config=self.config)

    def test_a_cold_campaign_says_every_step_is_a_first_touch(self):
        html = self.render(self.pack(self.seed_records()))
        self.assertIn("What these accounts have already heard", html)
        self.assertIn("first touch", html)

    def test_a_touched_account_names_who_they_heard_from(self):
        from src import senderidentity as si

        recs = self.seed_records()
        recs[0].setdefault("events", []).append(
            sent(contact=recs[0]["contacts"][0]["key"], sender=MARK))
        html = self.render(self.pack(recs))
        self.assertIn("email:", html)

    def test_prepared_steps_are_called_out_as_not_history(self):
        recs = self.seed_records()
        recs[0].setdefault("events", []).append(
            prepared(contact=recs[0]["contacts"][0]["key"], sender=ANNA))
        html = self.render(self.pack(recs))
        self.assertIn("prepared and", html)
        self.assertIn("not history", html)

    def test_the_screen_never_names_the_sender_of_a_planned_step(self):
        """The one on the screen is the one somebody reads aloud."""
        recs = self.seed_records()
        recs[0].setdefault("events", []).append(
            prepared(contact=recs[0]["contacts"][0]["key"], sender=ANNA))
        html = self.render(self.pack(recs))
        self.assertNotIn("Anna", html)
