"""Out of office: is it one, who wrote it, and when are they back.

The date half is the part with teeth. A missing return date holds the account
and asks a person; a *wrong* one schedules a follow-up into somebody's leave,
which is the exact discourtesy the out-of-office was warning us about. So
every case below either resolves deterministically or refuses with a reason,
and the refusals are asserted as carefully as the resolutions.

`RETURN_DATE_UNKNOWN` is an answer. These tests treat it as one.
"""
import datetime
import unittest

from tests.campaignbase import CampaignTest
from src import ooo, replies

# A Wednesday, so weekday arithmetic has somewhere to go in both directions.
SEP2 = "2026-09-02T08:14:00+00:00"


class Detection(unittest.TestCase):

    def test_the_provider_flag_is_authoritative(self):
        """It saw headers we never will."""
        got = ooo.detect("Thanks for your note.", automated=True)
        self.assertEqual(got["kind"], ooo.AUTORESPONDER)
        self.assertEqual(got["automated_source"], "provider")

    def test_machine_phrasing_alone_is_enough(self):
        got = ooo.detect("Automatic reply: I am out of the office.")
        self.assertEqual(got["kind"], ooo.AUTORESPONDER)
        self.assertEqual(got["automated_source"], "text")

    def test_a_person_writing_about_their_own_holiday_is_not_a_machine(self):
        """The case this module exists for. Demoting a human who happens to
        be away is how a real conversation gets filed as noise."""
        got = ooo.detect("I'm on holiday until the 8th, but yes - let's talk.",
                         automated=False)
        self.assertEqual(got["kind"], ooo.HUMAN_ABSENCE)
        self.assertTrue(got["is_absence"])

    def test_the_provider_saying_nothing_is_not_the_provider_saying_no(self):
        got = ooo.detect("I am away this week.", automated=None)
        self.assertEqual(got["kind"], ooo.HUMAN_ABSENCE)
        self.assertEqual(got["automated_source"], "unknown")
        self.assertIn("did not say", got["reason"])

    def test_an_ordinary_reply_is_not_an_absence(self):
        got = ooo.detect("Sounds interesting, send over some details.")
        self.assertEqual(got["kind"], ooo.NOT_ABSENCE)
        self.assertFalse(got["is_absence"])

    def test_the_flag_outranks_warm_words(self):
        """An autoresponder that quotes our own subject line still is one."""
        got = ooo.detect("Re: happy to chat - I am out of the office.",
                         automated=True)
        self.assertEqual(got["kind"], ooo.AUTORESPONDER)


class ReturnDatesThatResolve(unittest.TestCase):

    def date(self, text, received=SEP2, **kw):
        return ooo.return_date(text, received, **kw)

    def test_a_named_month_and_day(self):
        got = self.date("I am away until September 8 and will reply then.")
        self.assertEqual(got["status"], ooo.RESOLVED)
        self.assertEqual(got["return_date"], "2026-09-08")

    def test_the_other_word_order(self):
        got = self.date("Out of the office, back on 8 September.")
        self.assertEqual(got["return_date"], "2026-09-08")

    def test_an_ordinal_suffix_changes_nothing(self):
        self.assertEqual(self.date("back on 8th September")["return_date"],
                         "2026-09-08")
        self.assertEqual(self.date("back September 8th")["return_date"],
                         "2026-09-08")

    def test_an_abbreviated_month(self):
        self.assertEqual(self.date("back on 8 Sept")["return_date"],
                         "2026-09-08")

    def test_an_explicit_iso_date(self):
        self.assertEqual(self.date("back on 2026-09-08")["return_date"],
                         "2026-09-08")

    def test_a_day_of_the_month(self):
        got = self.date("I'm away, back in the office on the 15th.")
        self.assertEqual(got["status"], ooo.RESOLVED)
        self.assertEqual(got["return_date"], "2026-09-15")

    def test_a_day_of_the_month_that_has_passed_rolls_forward(self):
        got = self.date("back on the 1st")
        self.assertEqual(got["return_date"], "2026-10-01")

    def test_a_weekday(self):
        got = self.date("On leave, back Monday.")
        self.assertEqual(got["status"], ooo.RESOLVED)
        self.assertEqual(got["return_date"], "2026-09-07")

    def test_the_same_weekday_means_the_next_one(self):
        """Written on a Wednesday, "back Wednesday" is not today: the
        message says they are away now."""
        got = self.date("I am away, back Wednesday.")
        self.assertEqual(got["return_date"], "2026-09-09")

    def test_december_rolls_into_the_next_year(self):
        got = self.date("On leave until January 5.",
                        received="2026-12-20T09:00:00+00:00")
        self.assertEqual(got["return_date"], "2027-01-05")

    def test_a_stale_autoresponder_does_not_jump_a_year(self):
        """Read a few days late, "back September 8" means the 8th that has
        just passed - so they are already back. Next year would park the
        follow-up twelve months out."""
        got = self.date("I am away until September 8.",
                        received="2026-09-10T09:00:00+00:00")
        self.assertEqual(got["return_date"], "2026-09-08")


class ReturnDatesThatRefuse(unittest.TestCase):

    def date(self, text, received=SEP2):
        return ooo.return_date(text, received)

    def test_a_numeric_date_is_ambiguous_and_stays_ambiguous(self):
        """08/09 is 8 September or 9 August. No locale was recorded, and
        picking one would be a coin flip that moves somebody's return by a
        month."""
        got = self.date("Out of office, returning 08/09.")
        self.assertIsNone(got["return_date"])
        self.assertEqual(got["status"], ooo.UNKNOWN_AMBIGUOUS_NUMERIC)
        self.assertIn("08/09", got["evidence"])

    def test_a_vague_period_is_not_a_date(self):
        got = self.date("I'm out of the office, back next week.")
        self.assertIsNone(got["return_date"])
        self.assertEqual(got["status"], ooo.UNKNOWN_VAGUE_PERIOD)

    def test_a_couple_of_weeks_is_not_a_date(self):
        got = self.date("On leave for a couple of weeks.")
        self.assertEqual(got["status"], ooo.UNKNOWN_VAGUE_PERIOD)

    def test_a_month_with_no_day_is_not_a_date(self):
        got = self.date("I am on parental leave until January.")
        self.assertIsNone(got["return_date"])
        self.assertEqual(got["status"], ooo.UNKNOWN_MONTH_WITHOUT_DAY)

    def test_an_absence_with_no_date_at_all(self):
        got = self.date("I am currently out of the office.")
        self.assertIsNone(got["return_date"])
        self.assertEqual(got["status"], ooo.UNKNOWN_NOT_STATED)

    def test_an_impossible_day_is_refused_rather_than_clamped(self):
        got = self.date("back on 30 February")
        self.assertIsNone(got["return_date"])

    def test_without_a_received_date_nothing_is_anchored(self):
        """"back Monday" has no meaning without the day it was written, and
        defaulting to today would invent one."""
        got = ooo.return_date("back Monday", None)
        self.assertIsNone(got["return_date"])
        self.assertEqual(got["status"], ooo.UNKNOWN_NOT_STATED)

    def test_an_unparseable_received_date_is_not_treated_as_today(self):
        got = ooo.return_date("back Monday", "not a date")
        self.assertIsNone(got["return_date"])

    def test_a_date_with_no_return_cue_is_not_a_return_date(self):
        """"We shipped on the 3rd" is a date, not a return."""
        got = self.date("We shipped that on the 3rd. Not interested though.")
        self.assertIsNone(got["return_date"])

    def test_a_named_month_needs_a_cue_too(self):
        """This only covered the ordinal path, and passed while the
        month-and-day pattern read any date in the body. "We launched on 3
        March. Not interested." resolved to a return on 3 March 2027."""
        for text in ("We launched on 3 March. Not interested.",
                     "Our Q3 ended 30 September, so no.",
                     "The March 8 release went out already."):
            with self.subTest(text=text):
                got = self.date(text)
                self.assertIsNone(got["return_date"])
                self.assertEqual(got["status"], ooo.UNKNOWN_NOT_STATED)

    def test_a_numeric_date_needs_a_cue_before_it_is_even_ambiguous(self):
        """An invoice number is not an unreadable return date. Reporting it
        as one puts a row in front of a person for nothing."""
        got = self.date("Invoice 08/09 attached. No thanks.")
        self.assertEqual(got["status"], ooo.UNKNOWN_NOT_STATED)

    def test_a_period_keeps_its_reason_without_a_cue(self):
        """"On leave for a couple of weeks" names no cue and no date, and
        it still matters that they gave a period rather than nothing - the
        reason is what an operator reads."""
        got = self.date("On leave for a couple of weeks.")
        self.assertEqual(got["status"], ooo.UNKNOWN_VAGUE_PERIOD)


class Timezones(unittest.TestCase):

    def test_a_timezone_is_recorded_and_never_applied(self):
        """A calendar date is what was written. Shifting it by a zone moves
        somebody's return by a day for precision the message never had."""
        got = ooo.return_date("back on September 8", SEP2,
                              timezone="Australia/Sydney")
        self.assertEqual(got["return_date"], "2026-09-08")
        self.assertEqual(got["timezone"], "Australia/Sydney")
        self.assertTrue(got["timezone_known"])

    def test_an_unknown_timezone_stays_explicitly_unknown(self):
        got = ooo.return_date("back on September 8", SEP2)
        self.assertIsNone(got["timezone"])
        self.assertFalse(got["timezone_known"])


class ReadingBothAtOnce(unittest.TestCase):

    def test_a_non_absence_gets_no_return_date(self):
        got = ooo.read("Not interested, thanks.", SEP2)
        self.assertEqual(got["absence"]["kind"], ooo.NOT_ABSENCE)
        self.assertIsNone(got["return"]["return_date"])

    def test_the_mission_fixture(self):
        """Sent 1 Sep, this arrives 2 Sep."""
        got = ooo.read("Thanks for your email. I'm away until September 8 "
                       "and will respond when I'm back.", SEP2, automated=True)
        self.assertEqual(got["absence"]["kind"], ooo.AUTORESPONDER)
        self.assertEqual(got["return"]["return_date"], "2026-09-08")

    def test_the_positive_plus_absence_fixture(self):
        """A human who is interested and also away. Both facts survive:
        the absence carries a date, and the person is not a machine."""
        text = ("Yes, this looks relevant. I'm on holiday until the 8th - "
                "can you ping me when I'm back?")
        got = ooo.read(text, SEP2, automated=False)
        self.assertEqual(got["absence"]["kind"], ooo.HUMAN_ABSENCE)
        self.assertEqual(got["return"]["return_date"], "2026-09-08")

    def test_that_fixture_still_classifies_as_out_of_office_today(self):
        """Stated rather than asserted as desirable.

        `replies` puts OUT_OF_OFFICE above POSITIVE on purpose, so this
        message is categorised as an out-of-office and does not alert. This
        module now separates the two facts the category cannot carry - a
        person wrote it, and here is the date - which is what a follow-up
        would need. Whether the category itself should change is a business
        decision and is deliberately not made here.
        """
        text = ("Yes, this looks relevant. I'm on holiday until the 8th - "
                "can you ping me when I'm back?")
        verdict = replies.classify(text)
        self.assertEqual(verdict["classification"], replies.OUT_OF_OFFICE)
        self.assertEqual(ooo.detect(text, automated=False)["kind"],
                         ooo.HUMAN_ABSENCE)


class NothingHereActs(unittest.TestCase):

    def test_the_module_imports_nothing_that_can_act(self):
        """It reads a message and reports. Holding the cadence already
        happened in `events.apply` before any of this ran.

        Asserted on the import graph rather than on the text of the file:
        a test that greps source fails when somebody writes a comment.
        """
        import ast
        import io
        tree = ast.parse(io.open(ooo.__file__, encoding="utf-8").read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
                imported |= {a.name for a in node.names}
        self.assertEqual(imported, {"datetime", "re"},
                         "this module may read a string and a date, nothing "
                         "more")

    def test_reading_a_message_twice_says_the_same_thing(self):
        """No clock, no randomness: the same message and the same received
        date resolve identically, which is what makes a stored return date
        auditable."""
        text = "Out of office, back on 8 September."
        self.assertEqual(ooo.read(text, SEP2), ooo.read(text, SEP2))


class TheWholeChain(CampaignTest):
    """Provider payload -> adapter -> inbound -> replies -> canonical event.

    A module nothing calls is this repository's recurring defect, so the
    reading is traced end to end rather than unit-tested and left hanging.
    """

    def row(self, text, automated=None, ident=9001):
        row = {"id": ident, "uuid": f"uuid-{ident}", "type": "Tracked Reply",
               "folder": "Inbox", "from_email_address": "champ@acme.test",
               "created_at": SEP2, "date_received": SEP2,
               "text_body": text,
               "custom_variables": {"record_id": "acme",
                                    "contact_key": "acme-champ",
                                    "client": "demo"}}
        if automated is not None:
            row["automated_reply"] = automated
        return row

    def ingest(self, text, automated=None):
        from src import inbound
        recs = self.seed_records()
        inbound.ingest({"data": [self.row(text, automated)]}, "emailbison",
                       recs=recs, config=self.config,
                       post=lambda p, c=None: {"ok": True})
        return recs[0]

    def ooo_events(self, rec):
        from src import events
        return [e for e in (rec.get("events") or [])
                if e.get("type") == events.OUT_OF_OFFICE_RECORDED]

    def test_an_out_of_office_reply_records_its_return_date(self):
        rec = self.ingest("Automatic reply: I am out of the office until "
                          "September 8.", automated=True)
        found = self.ooo_events(rec)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["return_date"], "2026-09-08")
        self.assertEqual(found[0]["absence_kind"], ooo.AUTORESPONDER)
        self.assertEqual(found[0]["automated_source"], "provider")

    def test_an_undatable_out_of_office_records_why(self):
        """No date is written at all - `events.record` does not store an
        empty value, so an absent `return_date` means nobody knew one. The
        status carries the reason, which is what an operator reads."""
        rec = self.ingest("I am out of the office, back next week.",
                          automated=True)
        found = self.ooo_events(rec)
        self.assertEqual(len(found), 1)
        self.assertNotIn("return_date", found[0])
        self.assertEqual(found[0]["return_status"], ooo.UNKNOWN_VAGUE_PERIOD)

    def test_a_provider_that_does_not_say_is_not_read_as_a_denial(self):
        """The row omits `automated_reply` entirely."""
        rec = self.ingest("I am on holiday until September 8.")
        found = self.ooo_events(rec)
        self.assertEqual(found[0]["automated_source"], "unknown")
        self.assertEqual(found[0]["absence_kind"], ooo.HUMAN_ABSENCE)

    def test_a_reply_that_is_not_an_absence_records_nothing(self):
        rec = self.ingest("Not interested, thanks.")
        self.assertEqual(self.ooo_events(rec), [])

    def test_the_account_is_still_held_by_the_reply_itself(self):
        """Recording a return date must not look like permission. A human
        writing about their own absence is not a pure machine autoresponder,
        so the fail-safe pause still applies through `inbound.handle`."""
        rec = self.ingest("Out of office until September 8.")
        self.assertTrue(rec.get("paused"))


if __name__ == "__main__":
    unittest.main()
