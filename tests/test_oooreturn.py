"""They said they would be back today. That is a reason to look, not to write.

The safety property this suite exists to hold down is narrow and easy to lose:
an out-of-office maps to `NOT_NOW`, whose plan is `replier=stop`, so an
autoresponder stops that contact exactly as a refusal does. This module is
allowed to look past *that one stop* - the deferral it is following up - and
past nothing else.

It never clears it. `accountpolicy.apply_reply` only writes state that is
absent and `revival` may "never subtract"; a scheduler that reopened a person
because a date arrived would be the only thing here able to do that
automatically, on the strength of a regex reading of an autoresponder. So
`DUE` is a verdict a human acts on, and the stop is still there afterwards.

The adversarial cases are the point: every one of them is a date arriving
while the world changed underneath it.
"""
import unittest

from tests.campaignbase import CampaignTest
from src import accountpolicy as ap, events, inbound, oooreturn, store

SEP2 = "2026-09-02T08:14:00+00:00"


class ReturnTest(CampaignTest):

    def ooo_row(self, text, ident=7001, at=SEP2, contact="acme-champ"):
        return {"id": ident, "uuid": f"uuid-{ident}", "type": "Tracked Reply",
                "folder": "Inbox", "from_email_address": "champ@acme.test",
                "created_at": at, "date_received": at, "text_body": text,
                "automated_reply": True,
                "custom_variables": {"record_id": "acme",
                                     "contact_key": contact,
                                     "client": "demo"}}

    def ingest(self, row, recs=None):
        recs = recs if recs is not None else self.seed_records()
        inbound.ingest({"data": [row]}, "emailbison", recs=recs,
                       config=self.config, post=lambda p, c=None: {"ok": True})
        return recs

    def absent_until(self, text="Automatic reply: out of the office until "
                                "September 8.", **kw):
        """The ordinary starting point: one recorded absence, one stop."""
        recs = self.ingest(self.ooo_row(text, **kw))
        return recs, recs[0]

    def contact(self, rec, key="acme-champ"):
        return next(c for c in rec["contacts"] if c["key"] == key)

    def assess(self, rec, today, key="acme-champ"):
        return oooreturn.assess(rec, key, today=today, config=self.config)


class TheGroundTruth(ReturnTest):

    def test_an_out_of_office_stops_the_contact_today(self):
        """Stated first because everything else depends on it. If this ever
        stops being true, the module below is solving a problem that has
        moved."""
        _, rec = self.absent_until()
        stopped = self.contact(rec).get("stopped")
        self.assertTrue(stopped)
        self.assertEqual(stopped["reason"], ap.NOT_NOW)

    def test_a_record_with_no_absence_is_not_a_candidate(self):
        recs = self.seed_records()
        self.assertIsNone(oooreturn.assess(recs[0], "acme-champ",
                                           today="2026-09-08"))


class TheDate(ReturnTest):

    def test_before_the_date_they_are_not_due(self):
        _, rec = self.absent_until()
        got = self.assess(rec, "2026-09-05")
        self.assertEqual(got["verdict"], oooreturn.NOT_YET)
        self.assertEqual(got["days_until"], 3)

    def test_on_the_date_they_are_due(self):
        _, rec = self.absent_until()
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.DUE)
        self.assertEqual(got["return_date"], "2026-09-08")

    def test_after_the_date_they_are_still_due(self):
        """A follow-up nobody ran on the day is not a follow-up nobody
        should run."""
        got = self.assess(self.absent_until()[1], "2026-09-20")
        self.assertEqual(got["verdict"], oooreturn.DUE)
        self.assertEqual(got["days_since_return"], 12)

    def test_an_unreadable_date_asks_a_person(self):
        _, rec = self.absent_until(
            "Automatic reply: I am away, back next week.")
        got = self.assess(rec, "2026-09-20")
        self.assertEqual(got["verdict"], oooreturn.NEEDS_A_PERSON)
        self.assertEqual(got["detail"], "unknown:vague_period")

    def test_a_later_absence_supersedes_an_earlier_one(self):
        """Somebody extending their leave sends a second autoresponder.
        Following the first one up lands in the middle of the extension."""
        recs, rec = self.absent_until()
        self.ingest(self.ooo_row("Automatic reply: away until September 20.",
                                 ident=7002, at="2026-09-07T09:00:00+00:00"),
                    recs=recs)
        got = self.assess(recs[0], "2026-09-08")
        self.assertEqual(got["return_date"], "2026-09-20")
        self.assertEqual(got["verdict"], oooreturn.NOT_YET)


class TheDateArrivesAndTheWorldChanged(ReturnTest):
    """Mission 75, one test per row. Each is a date coming due while
    something underneath it moved."""

    def test_they_unsubscribed_in_the_meantime(self):
        _, rec = self.absent_until()
        self.contact(rec)["unsubscribed"] = {"since": "2026-09-04"}
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.NEVER)
        self.assertEqual(got["why"], oooreturn.UNSUBSCRIBED)

    def test_the_account_was_removed_in_the_meantime(self):
        """Driven through the real transition. Account state is derived
        from the event log, so writing a key onto the record would be a
        fixture asserting against a shape nothing produces."""
        _, rec = self.absent_until()
        ap.apply_reply(rec, "acme-buyer", ap.ACCOUNT_DNC,
                       config=self.config, at="2026-09-04T09:00:00+00:00")
        self.assertEqual(ap.account_state(rec)[0], ap.SUPPRESS)
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.NEVER)
        # A company-wide removal suppresses every contact, so the
        # contact-level gate answers first. Both readings are true and both
        # are permanent; the more specific one is the better thing to show
        # an operator, which is why it is checked first.
        self.assertEqual(got["why"], oooreturn.UNSUBSCRIBED)
        self.assertTrue(self.contact(rec).get("unsubscribed"))

    def test_the_record_was_dropped_in_the_meantime(self):
        _, rec = self.absent_until()
        rec["state"] = "dropped"
        rec["drop_reason"] = "out of ICP"
        self.assertEqual(self.assess(rec, "2026-09-08")["verdict"],
                         oooreturn.NEVER)

    def test_they_replied_properly_in_the_meantime(self):
        """A human came back on their own. A follow-up written against a
        stale autoresponder would talk over a live conversation."""
        recs, rec = self.absent_until()
        events.record(rec, events.REPLY_CLASSIFIED, contact_key="acme-champ",
                      at="2026-09-06T10:00:00+00:00", classification="positive")
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.NOT_YET)
        self.assertEqual(got["why"], oooreturn.REPLIED_SINCE)

    def test_the_absence_itself_does_not_count_as_replying_since(self):
        """The out-of-office is a reply. Reading it as "they came back to
        us" would defer every follow-up for ever."""
        got = self.assess(self.absent_until()[1], "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.DUE)

    def test_they_left_the_company_in_the_meantime(self):
        _, rec = self.absent_until()
        events.record(rec, events.REPLY_CLASSIFIED, contact_key="acme-champ",
                      at="2026-09-06T10:00:00+00:00",
                      classification="left_company")
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.NEVER)
        self.assertEqual(got["why"], oooreturn.DEPARTED)

    def test_a_meeting_was_booked_in_the_meantime(self):
        _, rec = self.absent_until()
        events.record(rec, events.REPLY_CLASSIFIED, contact_key="acme-buyer",
                      at="2026-09-06T10:00:00+00:00", classification="meeting")
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.NOT_YET)
        self.assertEqual(got["why"], oooreturn.MEETING_BOOKED)

    def test_a_colleague_in_conversation_defers_the_follow_up(self):
        """The account hold is attributed. A hold this person's own
        absence raised is that absence; a hold a colleague raised is a
        live conversation, and writing into it is what the account pause
        exists to prevent."""
        _, rec = self.absent_until()
        events.record(rec, events.REPLY_CLASSIFIED, contact_key="acme-buyer",
                      at="2026-09-05T09:00:00+00:00", classification="positive")
        ap.apply_reply(rec, "acme-buyer", ap.POSITIVE, config=self.config,
                       at="2026-09-05T09:00:00+00:00")
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.NOT_YET)
        self.assertEqual(got["why"], oooreturn.CONVERSATION_LIVE)
        self.assertIn("acme-buyer", got["detail"])

    def test_a_stop_for_any_other_reason_is_a_refusal_not_a_wait(self):
        """The single most important negative case. Only the `not_now` stop
        an out-of-office writes may be looked past."""
        _, rec = self.absent_until()
        self.contact(rec)["stopped"] = {"since": "2026-09-04",
                                        "reason": ap.NEGATIVE,
                                        "why": "not interested"}
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.NEVER)
        self.assertEqual(got["why"], oooreturn.REFUSED)


class ItNeverActs(ReturnTest):

    def test_being_due_does_not_lift_the_stop(self):
        """The asymmetry the whole build rests on: a timer may add to
        safety state and may never subtract from it."""
        _, rec = self.absent_until()
        before = dict(self.contact(rec)["stopped"])
        got = self.assess(rec, "2026-09-08")
        self.assertEqual(got["verdict"], oooreturn.DUE)
        self.assertEqual(self.contact(rec).get("stopped"), before,
                         "the stop is still there and unchanged")

    def test_assessing_writes_nothing_to_the_record(self):
        _, rec = self.absent_until()
        import copy
        before = copy.deepcopy(rec)
        oooreturn.candidates([rec], today="2026-09-08", config=self.config)
        self.assertEqual(rec, before)

    def test_it_imports_nothing_that_can_send(self):
        import ast
        import io
        tree = ast.parse(io.open(oooreturn.__file__, encoding="utf-8").read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
        for forbidden in ("push", "tagsync", "generate", "orchestrator"):
            self.assertNotIn(forbidden, imported)


class Listing(ReturnTest):

    def test_candidates_puts_the_due_ones_first(self):
        recs, _ = self.absent_until()
        rows = oooreturn.candidates(recs, today="2026-09-08",
                                    config=self.config)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["verdict"], oooreturn.DUE)
        self.assertEqual(oooreturn.summarise(rows)[oooreturn.DUE], 1)

    def test_a_workspace_filter_keeps_other_workspaces_out(self):
        recs, rec = self.absent_until()
        rows = oooreturn.candidates(recs, today="2026-09-08",
                                    config=self.config, workspace="elsewhere")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
