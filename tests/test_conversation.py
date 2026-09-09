"""One person, both channels, in the order it happened.

`account.timeline` answers "what happened at this company". Nothing
answered "what happened with this person", and the most important property
of a multichannel cadence is only visible when the two channels are read
together: a reply on LinkedIn is supposed to stop the *email* sequence, and
whether it did is not a question you can ask one channel at a time.

Four things are defended here.

**A confirmed step after a reply is visible.** Stated narrowly - the thread
says a step went out after they answered and leaves the judgement to a
person - and never claimed on a clock that could not be read. Missing
evidence is not positive evidence.

**One reply is one line.** `reply_received`, `reply_classified` and
`positive_reply_detected` are the same message seen three times, and listing
all three would make a person look three times as talkative.

**The same person elsewhere is listed, never merged.** Only on an exact
identifier - a normalised mailbox, a canonical profile, a provider id - and
never across a workspace boundary, whoever the person is.

**It changes nothing.** The thread is read while somebody decides what to do
about a person, and a view that could move state is a view that will.
"""
import copy
import unittest

from tests.campaignbase import CampaignTest, contact as make_contact
from tests.webbase import WebTest

from src import account, conversation, events, store

DAY1 = "2026-09-01T09:00:00+00:00"
DAY2 = "2026-09-02T09:00:00+00:00"
DAY3 = "2026-09-03T09:00:00+00:00"
DAY4 = "2026-09-04T09:00:00+00:00"


class ThreadTest(CampaignTest):
    """Helpers only. Subclassing a class that holds tests would re-run
    every one of them under each subclass's name."""

    def seed(self):
        recs = self.seed_records()
        self.rec = recs[0]
        self.recs = recs
        return recs

    def thread(self, key="acme-champ"):
        return conversation.thread(self.rec, key, workspace="demo")

    def touch(self, channel, at, confirmed=True, contact="acme-champ"):
        kind = (events.PUSH_MARKED if confirmed else events.PUSH_PREPARED)
        events.record(self.rec, kind, contact_key=contact, channel=channel,
                      at=at, sender_id="anna", step="day1")

    def reply(self, channel, at, classification="neutral",
              contact="acme-champ"):
        events.record(self.rec, events.REPLY_RECEIVED, contact_key=contact,
                      channel=channel, at=at)
        if classification:
            events.record(self.rec, events.REPLY_CLASSIFIED,
                          contact_key=contact, channel=channel, at=at,
                          classification=classification, confidence=0.8)

    def setUp(self):
        super().setUp()
        self.seed()


class OnePersonBothChannels(ThreadTest):

    def test_a_contact_nobody_holds_is_none_rather_than_empty(self):
        """"Nobody by that key" and "nothing has happened" are different
        answers, and a screen must not print the second for the first."""
        self.assertIsNone(self.thread("nobody-here"))
        self.assertIsNotNone(self.thread())

    def test_both_channels_arrive_in_one_column(self):
        self.touch("email", DAY1)
        self.touch("linkedin", DAY2)
        found = self.thread()
        channels = [e["channel"] for e in found["entries"]
                    if e["kind"] == conversation.TOUCH]
        self.assertEqual(channels, ["email", "linkedin"])
        self.assertEqual(found["summary"]["channels_used"],
                         ["email", "linkedin"])

    def test_it_is_in_order(self):
        self.touch("email", DAY3)
        self.touch("linkedin", DAY1)
        self.reply("email", DAY2)
        stamps = [e["at"] for e in self.thread()["entries"]]
        self.assertEqual(stamps, sorted(stamps))

    def test_one_reply_is_one_line(self):
        """Three events, one message. Listing all three would make this
        person look three times as talkative."""
        self.reply("email", DAY2, classification="positive")
        events.record(self.rec, events.POSITIVE_REPLY_DETECTED,
                      contact_key="acme-champ", channel="email", at=DAY2)
        replies = [e for e in self.thread()["entries"]
                   if e["kind"] == conversation.REPLY]
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["classification"], "positive")

    def test_an_unclassified_reply_says_so_rather_than_guessing(self):
        self.reply("email", DAY2, classification=None)
        reply = next(e for e in self.thread()["entries"]
                     if e["kind"] == conversation.REPLY)
        self.assertIsNone(reply["classification"])
        self.assertIn("nobody has classified", reply["summary"])
        self.assertIn("never been classified",
                      " ".join(self.thread()["summary"]["flags"]))

    def test_only_this_person(self):
        self.rec["contacts"].append(
            make_contact("acme-ops", "Ops Acme", "ops@acme.test"))
        self.touch("email", DAY1)
        self.touch("email", DAY2, contact="acme-ops")
        self.reply("linkedin", DAY3, contact="acme-ops")
        found = self.thread()
        self.assertEqual(len(found["entries"]), 1)
        self.assertEqual(found["summary"]["replies"], 0)

    def test_a_planned_touch_is_not_a_touch_that_happened(self):
        self.touch("email", DAY1, confirmed=False)
        summary = self.thread()["summary"]
        self.assertEqual(summary["confirmed_touches"], 0)
        self.assertEqual(summary["planned_touches"], 1)
        entry = next(e for e in self.thread()["entries"]
                     if e["kind"] == conversation.TOUCH)
        self.assertIn("not confirmed", entry["summary"])


class AStepAfterTheyAnswered(ThreadTest):

    def flagged(self):
        return [e for e in self.thread()["entries"]
                if e.get("after_a_reply")]

    def test_a_confirmed_step_after_a_reply_is_visible(self):
        self.reply("email", DAY1)
        self.touch("email", DAY2)
        self.assertEqual(len(self.flagged()), 1)
        self.assertIn("after they replied",
                      " ".join(self.thread()["summary"]["flags"]))

    def test_the_other_channel_is_the_interesting_case(self):
        """A LinkedIn reply is meant to stop the email sequence too."""
        self.reply("linkedin", DAY1)
        self.touch("email", DAY2)
        self.assertTrue(self.flagged()[0]["crossed_channels"])

    def test_the_same_channel_is_flagged_without_that_claim(self):
        self.reply("email", DAY1)
        self.touch("email", DAY2)
        self.assertFalse(self.flagged()[0]["crossed_channels"])

    def test_a_step_before_the_reply_is_ordinary(self):
        self.touch("email", DAY1)
        self.reply("email", DAY2)
        self.assertEqual(self.flagged(), [])
        self.assertEqual(self.thread()["summary"]["flags"], [])

    def test_a_planned_step_after_a_reply_is_not_claimed(self):
        """Nothing was sent. A payload that was built and never left is
        not a message somebody received."""
        self.reply("email", DAY1)
        self.touch("email", DAY2, confirmed=False)
        self.assertEqual(self.flagged(), [])

    def test_an_unreadable_clock_claims_nothing(self):
        """A confident "a step went out after they replied" built on a
        timestamp nobody could parse is worse than the silence."""
        self.reply("email", "not a time")
        self.touch("email", DAY2)
        self.assertEqual(self.flagged(), [])

    def test_a_naive_timestamp_claims_nothing(self):
        """Assuming UTC would move an event by hours and then assert on it."""
        self.reply("email", "2026-09-01T09:00:00")
        self.touch("email", DAY2)
        self.assertEqual(self.flagged(), [])


class WhatItSaysAboutThem(ThreadTest):

    def test_a_date_they_named_is_carried(self):
        self.reply("email", DAY1, classification="not_now")
        events.record(self.rec, events.NOT_NOW_RECORDED,
                      contact_key="acme-champ", at=DAY1,
                      return_date="2026-11-02", return_status="resolved")
        found = self.thread()
        self.assertEqual(found["summary"]["return_date"], "2026-11-02")
        intent = next(e for e in found["entries"]
                      if e["kind"] == conversation.INTENT)
        self.assertIn("2026-11-02", intent["summary"])

    def test_an_absence_with_no_readable_date_says_that(self):
        events.record(self.rec, events.OUT_OF_OFFICE_RECORDED,
                      contact_key="acme-champ", at=DAY1,
                      return_status="unknown:month_without_day")
        intent = next(e for e in self.thread()["entries"]
                      if e["kind"] == conversation.INTENT)
        self.assertIn("no date we could read", intent["summary"])
        self.assertIsNone(self.thread()["summary"]["return_date"])

    def test_what_we_did_about_a_reply_is_in_the_same_column(self):
        self.reply("email", DAY1, classification="negative")
        events.record(self.rec, events.CONTACT_STOPPED,
                      contact_key="acme-champ", at=DAY1, outcome="negative")
        decisions = [e for e in self.thread()["entries"]
                     if e["kind"] == conversation.DECISION]
        self.assertEqual(len(decisions), 1)
        self.assertIn("stopped", decisions[0]["summary"])
        self.assertIsNone(decisions[0]["direction"])

    def test_a_referral_they_made_appears(self):
        events.record(self.rec, events.REFERRAL_MENTIONED,
                      contact_key="acme-champ", channel="email", at=DAY1,
                      referral_status="unknown", named="Priya Nair",
                      reason="a name with no address")
        entry = next(e for e in self.thread()["entries"]
                     if e["kind"] == conversation.REFERRAL)
        self.assertIn("Priya Nair", entry["summary"])
        self.assertEqual(entry["direction"], conversation.IN)

    def test_a_positive_nobody_read_is_flagged(self):
        self.reply("email", DAY1, classification="positive")
        self.assertIn("nobody has marked it read",
                      " ".join(self.thread()["summary"]["flags"]))

    def test_reading_it_clears_that_flag(self):
        self.reply("email", DAY1, classification="positive")
        for entry in self.rec["events"]:
            if entry.get("type") == events.REPLY_RECEIVED:
                entry["handled"] = {"by": "ops@demo.test", "at": DAY2}
        self.assertEqual(
            [f for f in self.thread()["summary"]["flags"]
             if "marked it read" in f], [])

    def test_the_message_text_is_absent_and_says_so(self):
        """No reply body is stored on a record. A thread that showed empty
        quotes would imply one was."""
        self.reply("email", DAY1)
        found = self.thread()
        self.assertIn("not stored", found["text_note"])
        for entry in found["entries"]:
            with self.subTest(kind=entry["kind"]):
                self.assertNotIn("body", entry)
                self.assertNotIn("text", entry)


class ItChangesNothing(ThreadTest):

    def test_reading_a_thread_writes_nothing(self):
        self.touch("email", DAY1)
        self.reply("linkedin", DAY2)
        before = copy.deepcopy(self.rec)
        conversation.thread(self.rec, "acme-champ", workspace="demo")
        self.assertEqual(self.rec, before)

    def test_it_does_not_reach_the_stored_estate(self):
        self.touch("email", DAY1)
        store.save(self.recs)
        conversation.thread(self.rec, "acme-champ", workspace="demo")
        stored = store.load()
        self.assertEqual(len(stored[0]["events"]),
                         len(self.rec["events"]))


class TheSamePersonElsewhere(CampaignTest):

    def estate(self):
        recs = self.seed_records()
        for rec in recs:
            rec["contacts"] = [
                make_contact(f"{rec['id']}-champ", "Champ Person",
                             "champ@acme.test")]
        return recs

    def contact(self, rec):
        return rec["contacts"][0]

    def test_an_exact_address_match_is_listed(self):
        recs = self.estate()
        found = conversation.also_known(recs, recs[0], self.contact(recs[0]))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["record_id"], "borealis")
        self.assertIn("email:champ@acme.test", found[0]["matched_on"])

    def test_a_shared_name_is_not_a_match(self):
        recs = self.estate()
        recs[1]["contacts"][0]["email"] = "someone.else@borealis.test"
        recs[1]["contacts"][0]["linkedin"] = (
            "https://www.linkedin.com/in/someone-else")
        self.assertEqual(
            conversation.also_known(recs, recs[0], self.contact(recs[0])), [])

    def test_a_canonical_profile_is_enough_on_its_own(self):
        recs = self.estate()
        recs[1]["contacts"][0]["email"] = "someone.else@borealis.test"
        recs[1]["contacts"][0]["linkedin"] = (
            "https://linkedin.com/in/acme-champ/?trk=x")
        recs[0]["contacts"][0]["linkedin"] = (
            "https://www.linkedin.com/in/acme-champ")
        found = conversation.also_known(recs, recs[0], self.contact(recs[0]))
        self.assertEqual(len(found), 1)
        self.assertTrue(any(m.startswith("linkedin:")
                            for m in found[0]["matched_on"]))

    def test_another_workspace_is_never_the_same_thread(self):
        """Whoever the person is. Another tenant's activity is not this
        tenant's history."""
        recs = self.estate()
        recs[1]["client"] = "somebody-else"
        self.assertEqual(
            conversation.also_known(recs, recs[0], self.contact(recs[0])), [])

    def test_a_contact_with_no_strong_identifier_matches_nobody(self):
        recs = self.estate()
        weak = {"key": "ghost", "name": "Champ Person"}
        recs[0]["contacts"].append(weak)
        self.assertEqual(conversation.also_known(recs, recs[0], weak), [])

    def test_it_lists_rather_than_merges(self):
        """The other record's events stay on the other record."""
        recs = self.estate()
        events.record(recs[1], events.REPLY_RECEIVED,
                      contact_key="borealis-champ", channel="email", at=DAY1)
        found = conversation.thread(recs[0], "acme-champ", workspace="demo")
        self.assertEqual(found["entries"], [])
        self.assertEqual(
            conversation.also_known(recs, recs[0],
                                    self.contact(recs[0]))[0]["events"], 1)


class OnTheScreen(WebTest):

    def open(self, email="ops@productive.test"):
        from src import repo as repo_module
        from src.web import api
        repo = repo_module.Repo.for_user(email, "productive")
        for rec in repo.records():
            for contact in rec.get("contacts") or []:
                view = api.contact_view(repo, rec["id"], contact["key"])
                if view and view["conversation"]["entries"]:
                    return repo, rec, contact, view
        self.fail("the demo estate has no contact with any history")

    def test_the_contact_view_carries_the_thread(self):
        _, _, _, view = self.open()
        self.assertIn("conversation", view)
        self.assertTrue(view["conversation"]["entries"])
        self.assertIn("channels_used", view["conversation"]["summary"])

    def test_the_page_renders_it(self):
        _, rec, contact, _ = self.open()
        session = self.signin("ops@productive.test")
        status, body, _ = session.get(
            f"/contacts/{rec['id']}/{contact['key']}")
        self.assertEqual(status, 200)
        self.assertIn("Conversation", body)
        self.assertIn("Channels they answered on", body)

    def test_a_viewer_still_cannot_read_a_contact(self):
        session = self.signin("client@productive.test")
        from src import repo as repo_module
        repo = repo_module.Repo.for_user("ops@productive.test", "productive")
        rec = repo.records()[0]
        contact = (rec.get("contacts") or [{}])[0]
        status, _, _ = session.get(
            f"/contacts/{rec['id']}/{contact.get('key')}")
        self.assertIn(status, (403, 404))


if __name__ == "__main__":
    unittest.main()
