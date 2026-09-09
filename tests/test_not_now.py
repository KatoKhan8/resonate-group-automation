"""Somebody who named a later time, and what is kept about it.

"Try me in November" is not a refusal and it is not an absence. Nobody is
away; they have said when, and that date is worth exactly as much as a
return date - it is the difference between a door closing and a door with a
time on it.

The two decisions worth defending:

A refusal with a politeness on the end is still a refusal. "No thanks, maybe
try us in Q1" must not become a future appointment, so NOT_NOW is tested
after NEGATIVE and that ordering has a test.

And the date is read by the same grammar as an out-of-office return, with a
different cue set rather than a second parser. Which means the same
refusals: a month with no day is not a date, a bare number is not a date,
and a date with no cue is not an appointment.
"""
import unittest

from tests.campaignbase import CampaignTest
from src import events, inbound, ooo, oooreturn, replies, tasks

SEP2 = "2026-09-02T09:00:00+00:00"


class Classifying(unittest.TestCase):

    def kind(self, text):
        return replies.classify(text)["classification"]

    def test_a_named_later_time_is_not_now(self):
        for text in ("Not right now, try me in November.",
                     "Reach out again in Q1.",
                     "Ping me next month.",
                     "Circle back after the 15th.",
                     "Bad timing, we are mid-migration.",
                     "Too early for us, revisit in the new year."):
            with self.subTest(text=text):
                self.assertEqual(self.kind(text), replies.NOT_NOW)

    def test_a_refusal_with_a_politeness_on_the_end_is_still_a_refusal(self):
        """The ordering that matters. Reading this as a future appointment
        puts a follow-up in front of somebody who said no."""
        self.assertEqual(self.kind("No thanks, maybe try us in Q1."),
                         replies.NEGATIVE)
        self.assertEqual(self.kind("Not interested, but try again next year."),
                         replies.NEGATIVE)

    def test_an_unsubscribe_still_beats_everything(self):
        self.assertEqual(self.kind("Unsubscribe. Try me next year."),
                         replies.UNSUBSCRIBE)

    def test_an_out_of_office_is_still_an_out_of_office(self):
        self.assertEqual(
            self.kind("I am out of the office, back on the 8th."),
            replies.OUT_OF_OFFICE)

    def test_warmth_alone_is_still_positive(self):
        self.assertEqual(self.kind("Sounds good, happy to chat."),
                         replies.POSITIVE)


class ReadingTheDate(unittest.TestCase):

    def date(self, text, received=SEP2):
        return ooo.return_date(text, received, cue=ooo.NOT_NOW_CUE)

    def test_a_day_of_the_month(self):
        self.assertEqual(self.date("Reach out again after the 15th.")
                         ["return_date"], "2026-09-15")

    def test_a_weekday(self):
        self.assertEqual(self.date("Ping me Monday.")["return_date"],
                         "2026-09-07")

    def test_a_named_month_and_day(self):
        self.assertEqual(self.date("Circle back on 3 December.")
                         ["return_date"], "2026-12-03")

    def test_a_month_with_no_day_is_still_not_a_date(self):
        """The same refusal the return grammar makes. "November" is four
        weeks wide and picking a day inside it is inventing one."""
        got = self.date("Try me in November.")
        self.assertIsNone(got["return_date"])
        self.assertEqual(got["status"], ooo.UNKNOWN_MONTH_WITHOUT_DAY)

    def test_a_vague_period_is_still_not_a_date(self):
        got = self.date("Ping me in a couple of weeks.")
        self.assertIsNone(got["return_date"])

    def test_the_return_cue_set_is_unchanged_by_this(self):
        """`return_date` keeps its own cues. A parser shared by two callers
        must not have quietly become one that answers both questions the
        same way."""
        self.assertEqual(
            ooo.return_date("I am away until September 8.", SEP2)
            ["return_date"], "2026-09-08")
        self.assertIsNone(
            ooo.return_date("We launched on 3 March.", SEP2)["return_date"])


class TheWholeChain(CampaignTest):

    def ingest(self, text, ident=6001):
        recs = self.seed_records()
        row = {"id": ident, "uuid": f"u{ident}", "type": "Tracked Reply",
               "folder": "Inbox", "from_email_address": "champ@acme.test",
               "created_at": SEP2, "date_received": SEP2, "text_body": text,
               "automated_reply": False,
               "custom_variables": {"record_id": "acme",
                                    "contact_key": "acme-champ",
                                    "client": "demo"}}
        inbound.ingest({"data": [row]}, "emailbison", recs=recs,
                       config=self.config, post=lambda p, c=None: {"ok": True})
        return recs[0]

    def recorded(self, rec):
        return [e for e in rec.get("events") or []
                if e.get("type") == events.NOT_NOW_RECORDED]

    def test_the_date_is_recorded_against_the_person(self):
        rec = self.ingest("Not right now - reach out again after the 15th.")
        found = self.recorded(rec)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["return_date"], "2026-09-15")

    def test_an_unreadable_date_records_why(self):
        rec = self.ingest("Try me in November.")
        found = self.recorded(rec)
        self.assertEqual(found[0]["return_status"],
                         ooo.UNKNOWN_MONTH_WITHOUT_DAY)
        self.assertNotIn("return_date", found[0])

    def test_the_cadence_stops_exactly_as_it_would_for_a_refusal(self):
        """A date is not permission to keep going in the meantime."""
        rec = self.ingest("Not right now, ping me next Monday.")
        contact = next(c for c in rec["contacts"] if c["key"] == "acme-champ")
        self.assertTrue(contact.get("stopped"))

    def test_before_the_date_they_are_not_due(self):
        rec = self.ingest("Reach out again after the 15th.")
        got = oooreturn.assess(rec, "acme-champ", today="2026-09-10",
                               config=self.config)
        self.assertEqual(got["verdict"], oooreturn.NOT_YET)

    def test_on_the_date_they_are_due_and_say_which_kind(self):
        rec = self.ingest("Reach out again after the 15th.")
        got = oooreturn.assess(rec, "acme-champ", today="2026-09-15",
                               config=self.config)
        self.assertEqual(got["verdict"], oooreturn.DUE)
        self.assertEqual(got["source"], events.NOT_NOW_RECORDED)
        self.assertIn("come back later", got["source_label"])

    def test_a_later_not_now_supersedes_an_earlier_absence(self):
        """Both are dated intentions from the same person. The newer one is
        what they actually asked for."""
        rec = self.ingest("I am out of the office until the 8th.", ident=6100)
        events.record(rec, events.NOT_NOW_RECORDED, contact_key="acme-champ",
                      at="2026-09-05T09:00:00+00:00",
                      return_date="2026-11-02", return_status="resolved")
        got = oooreturn.assess(rec, "acme-champ", today="2026-09-20",
                               config=self.config)
        self.assertEqual(got["return_date"], "2026-11-02")
        self.assertEqual(got["verdict"], oooreturn.NOT_YET)

    def test_it_reaches_the_work_queue_as_its_own_kind(self):
        """Somebody back from leave and somebody who asked to be approached
        in November are both due, and calling one the other tells an
        operator something untrue about a person."""
        rec = self.ingest("Reach out again after the 15th.")
        rows = tasks.collect("demo", recs=[rec], config=self.config,
                             today="2026-09-20")
        kinds = [r["kind"] for r in rows]
        self.assertIn(tasks.NOT_NOW_RETURN, kinds)
        self.assertNotIn(tasks.OOO_RETURN, kinds)

    def test_an_absence_still_reaches_it_as_a_return(self):
        rec = self.ingest("Automatic reply: out of office until the 8th.")
        rows = tasks.collect("demo", recs=[rec], config=self.config,
                             today="2026-09-20")
        self.assertIn(tasks.OOO_RETURN, [r["kind"] for r in rows])


if __name__ == "__main__":
    unittest.main()
