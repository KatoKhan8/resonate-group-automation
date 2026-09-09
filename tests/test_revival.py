"""Quiet accounts, and whether there is anything new to say to them.

Two failures are worth more than the rest here. Writing again to somebody
who asked us to stop, because the clock ran out and nobody checked what the
silence meant. And writing again with the same angle that already failed,
which is not a revival - it is the same campaign with a later date on it,
and the recipient reads it that way.
"""
import unittest

from src import events, revival
from tests.campaignbase import CampaignTest

TODAY = "2026-08-31"
LONG_AGO = "2026-01-05T09:00:00+00:00"     # 238 days: well past cooling
RECENT = "2026-08-01T09:00:00+00:00"       # 30 days: inside cooling


def touch(at=LONG_AGO, contact="a", kind=events.PUSH_MARKED):
    return {"type": kind, "contact": contact, "channel": "email",
            "step": "day1", "at": at}


def reply(classification, at=LONG_AGO, contact="a"):
    return {"type": events.REPLY_CLASSIFIED, "contact": contact,
            "channel": "email", "at": at, "classification": classification}


def a_record(events_=(), contacts=None, **kw):
    rec = {"id": "a1", "company": "Acme", "domain": "acme.test",
           "client": "productive",
           "events": list(events_),
           "contacts": contacts if contacts is not None else
                       [{"key": "a", "name": "A Person", "selected": True,
                         "persona": "champion", "angle": "finance"}]}
    rec.update(kw)
    return rec


class Revival(CampaignTest):

    def assess(self, rec, today=TODAY, config=None):
        return revival.assess(rec, today=today,
                              config=self.config if config is None else config,
                              workspace="productive")


class SomeAccountsAreClosedForGood(Revival):

    def test_somebody_who_asked_us_to_stop(self):
        found = self.assess(a_record([touch(), reply("unsubscribe")]))
        self.assertEqual(found["verdict"], revival.NEVER)
        self.assertEqual(found["why"], revival.UNSUBSCRIBED)

    def test_a_company_that_asked_us_to_stop(self):
        found = self.assess(a_record([touch(), reply("account_dnc")]))
        self.assertEqual(found["verdict"], revival.NEVER)
        self.assertEqual(found["why"], revival.ACCOUNT_REMOVED)

    def test_an_existing_client(self):
        found = self.assess(a_record([touch(), reply("existing_client")]))
        self.assertEqual(found["verdict"], revival.NEVER)
        self.assertEqual(found["why"], revival.EXISTING_CLIENT)

    def test_wrong_person_does_not_close_the_account(self):
        """It names somebody else at the same company, which is a reason to
        look again rather than a reason to stop."""
        found = self.assess(a_record([touch(), reply("wrong_person")]))
        self.assertNotEqual(found["verdict"], revival.NEVER)

    def test_an_account_level_suppression(self):
        rec = a_record([touch()])
        rec["suppression"] = {"unsubscribed": True}
        self.assertEqual(self.assess(rec)["verdict"], revival.NEVER)

    def test_a_dropped_record(self):
        rec = a_record([touch()], state="dropped", drop_reason="out of geo")
        found = self.assess(rec)
        self.assertEqual(found["verdict"], revival.NEVER)
        self.assertEqual(found["why"], "out of geo")

    def test_a_closed_account_is_not_examined_for_interest(self):
        """The permanent checks run before any signal is read. An account
        that asked us to stop must not have its news scanned to see whether
        it has become interesting again."""
        rec = a_record([touch(), reply("unsubscribe")],
                       contacts=[{"key": "b", "selected": True,
                                  "name": "Never Touched"}])
        found = self.assess(rec)
        self.assertEqual(found["verdict"], revival.NEVER)
        self.assertEqual(found["cases"], [])


class SomeAccountsAreMerelyNotYet(Revival):

    def test_an_account_nobody_has_written_to(self):
        """There is nothing to revive. Named rather than swept into "too
        soon", because "we have not started" and "we tried and it went
        quiet" are different queues."""
        found = self.assess(a_record([]))
        self.assertEqual(found["verdict"], revival.NOT_YET)
        self.assertEqual(found["why"], revival.NEVER_CONTACTED)

    def test_inside_the_cooling_period(self):
        found = self.assess(a_record([touch(at=RECENT)]))
        self.assertEqual(found["verdict"], revival.NOT_YET)
        self.assertEqual(found["why"], revival.TOO_SOON)
        self.assertEqual(found["days_since"], 30)
        self.assertEqual(found["cooling_days"], 90)

    def test_a_booked_meeting(self):
        found = self.assess(a_record([touch(), reply("meeting")]))
        self.assertEqual(found["verdict"], revival.NOT_YET)
        self.assertEqual(found["why"], revival.MEETING_BOOKED)

    def test_a_live_conversation(self):
        rec = a_record([touch()])
        rec["paused"] = {"since": RECENT, "reason": "reply_received"}
        found = self.assess(rec)
        self.assertEqual(found["verdict"], revival.NOT_YET)
        self.assertEqual(found["why"], revival.CONVERSATION_LIVE)

    def test_the_clock_starts_at_a_confirmed_touch_not_a_prepared_one(self):
        """A payload that was built and never left is not outreach that
        happened, and a cooling period measured from it would start the
        clock on a message nobody received."""
        rec = a_record([touch(kind=events.PUSH_PREPARED)])
        self.assertIsNone(revival.last_touch(rec))
        self.assertEqual(self.assess(rec)["why"], revival.NEVER_CONTACTED)


class TimePassingIsNotSomethingToSay(Revival):
    """The point of the module. An account that heard one thing and said
    nothing does not need to hear it again in March."""

    def quiet(self, **kw):
        """Past cooling, with every angle already used and nobody new."""
        angles = sorted(revival.angles_available(self.config))
        contacts = [{"key": f"c{i}", "name": f"Person {i}", "selected": True,
                     "angle": angle}
                    for i, angle in enumerate(angles)]
        touches = [touch(contact=c["key"]) for c in contacts]
        return a_record(touches + list(kw.pop("extra", [])),
                        contacts=contacts, **kw)

    def test_nothing_has_changed_is_its_own_verdict(self):
        found = self.assess(self.quiet())
        self.assertEqual(found["verdict"], revival.NOTHING_NEW)
        self.assertEqual(found["cases"], [])
        self.assertIn("same message", found["why"])

    def test_it_is_not_ready_and_not_closed(self):
        """Both would be wrong: one writes a repeat, the other writes the
        account off."""
        found = self.assess(self.quiet())
        self.assertNotIn(found["verdict"], (revival.READY, revival.NEVER))

    def test_a_contact_we_would_never_write_to_makes_no_case(self):
        """Not selected for the campaign, so "we have never approached
        them" is not an opportunity - it is the plan working."""
        rec = self.quiet()
        rec["contacts"].append({"key": "shelved", "name": "Not Selected",
                                "selected": False, "angle": "finance"})
        found = self.assess(rec)
        self.assertEqual(found["verdict"], revival.NOTHING_NEW)

    def test_a_decision_maker_nobody_wrote_to_makes_a_case(self):
        rec = self.quiet()
        rec["contacts"].append({"key": "new", "name": "New Person",
                                "selected": True, "angle": "finance"})
        found = self.assess(rec)
        self.assertEqual(found["verdict"], revival.READY)
        self.assertIn(revival.NEW_PERSON,
                      [c["case"] for c in found["cases"]])

    def test_an_unused_angle_makes_a_case(self):
        """Every angle this client sells against, not only the one persona
        we happened to write to."""
        rec = self.quiet()
        rec["contacts"] = rec["contacts"][:1]
        rec["events"] = [touch(contact=rec["contacts"][0]["key"])]
        found = self.assess(rec)
        self.assertEqual(found["verdict"], revival.READY)
        cases = {c["case"]: c for c in found["cases"]}
        self.assertIn(revival.UNUSED_ANGLE, cases)
        self.assertNotIn(rec["contacts"][0]["angle"],
                         cases[revival.UNUSED_ANGLE]["detail"])

    def test_somebody_leaving_makes_a_case(self):
        rec = self.quiet(extra=[reply("left_company")])
        found = self.assess(rec)
        self.assertEqual(found["verdict"], revival.READY)
        self.assertIn(revival.EMPLOYMENT_CHANGE,
                      [c["case"] for c in found["cases"]])

    def test_an_angle_carried_by_a_draft_nobody_sent_is_not_used(self):
        """`angles_used` reads confirmed touches. An angle that only ever
        reached a draft has not been tried on this account."""
        rec = a_record([], contacts=[{"key": "a", "selected": True,
                                      "angle": "finance"}])
        self.assertEqual(revival.angles_used(rec), set())


class ANewSignalMakesACase(Revival):

    def setUp(self):
        super().setUp()
        from src import signals
        self.signals = signals

    def note(self, rec, observed_at, kind=None):
        from src import signals

        return signals.record(signals.signal(
            "productive", kind or signals.FUNDING, record_id=rec["id"],
            evidence="A EUR 12m Series B announced on their newsroom.",
            source=signals.MANUAL, observed_at=observed_at,
            created_by="op@productive.test"))

    def quiet(self, touched_at=LONG_AGO):
        angles = sorted(revival.angles_available(self.config))
        contacts = [{"key": f"c{i}", "selected": True, "angle": angle}
                    for i, angle in enumerate(angles)]
        return a_record([touch(at=touched_at, contact=c["key"])
                         for c in contacts], contacts=contacts)

    def test_a_signal_after_the_last_touch(self):
        rec = self.quiet()
        self.note(rec, "2026-08-20T09:00:00+00:00")
        found = self.assess(rec)
        self.assertEqual(found["verdict"], revival.READY)
        self.assertIn(revival.NEW_SIGNAL, [c["case"] for c in found["cases"]])

    def test_a_signal_from_before_the_last_touch_does_not_count(self):
        """We already knew it when we wrote. It is not new.

        Dated so that only the "since" rule can refuse it: 113 days old, so
        it is comfortably inside the 120-day floor, and ten days before the
        last touch. A fixture that fell foul of both rules would pass with
        either one deleted.
        """
        rec = self.quiet(touched_at="2026-05-20T09:00:00+00:00")
        self.note(rec, "2026-05-10T09:00:00+00:00")
        self.assertEqual(self.assess(rec)["verdict"], revival.NOTHING_NEW)

    def test_the_same_signal_after_the_last_touch_does_count(self):
        """The other half of the pair, so the previous test is measuring
        the rule and not the fixture."""
        rec = self.quiet(touched_at="2026-05-20T09:00:00+00:00")
        self.note(rec, "2026-05-30T09:00:00+00:00")
        self.assertEqual(self.assess(rec)["verdict"], revival.READY)

    def test_a_signal_too_old_to_matter_does_not_count(self):
        """An account last touched two years ago would otherwise revive on
        something from eighteen months ago, which is new only in the
        arithmetic."""
        rec = self.quiet()
        rec["events"] = [touch(at="2024-01-05T09:00:00+00:00", contact=c["key"])
                         for c in rec["contacts"]]
        self.note(rec, "2024-06-01T09:00:00+00:00")
        self.assertEqual(self.assess(rec)["verdict"], revival.NOTHING_NEW)

    def test_our_own_outreach_is_not_news_from_the_account(self):
        """Engagement signals are readings of what *we* did. Counting them
        would revive every quiet account on the strength of being quiet.

        The fixture is a "you want somebody else" reply after the last
        touch, because that is an engagement signal whose timestamp is
        genuinely later than the touch - the derived `contacted` signal
        shares the touch's own timestamp and would be refused by the
        "since" rule whether or not this one existed.
        """
        from src import signals

        rec = self.quiet()
        rec["events"].append(reply("wrong_person",
                                   at="2026-06-01T09:00:00+00:00",
                                   contact=rec["contacts"][0]["key"]))
        derived = signals.derive(rec, "productive", self.config, TODAY)
        self.assertIn("wrong_person", [s["type"] for s in derived])
        self.assertEqual(
            {s["scope"] for s in derived}, {signals.ENGAGEMENT},
            "the fixture must produce engagement signals and nothing else")

        self.assertEqual(self.assess(rec)["verdict"], revival.NOTHING_NEW)


class ItDecidesNothing(unittest.TestCase):

    def test_it_writes_no_state_and_calls_no_provider(self):
        import inspect

        source = inspect.getsource(revival)
        for banned in ("store.save", "store.log", "events.record",
                       "providers.request", "urlopen", "live=True",
                       "push.", "generate."):
            self.assertNotIn(banned, source, banned)

    def test_the_summary_says_a_verdict_is_not_an_instruction(self):
        found = revival.summarise([])
        self.assertIn("never an instruction", found["note"])

    def test_every_verdict_has_a_sentence(self):
        for verdict in revival.VERDICTS:
            self.assertTrue(revival.VERDICT_LABEL[verdict])
        for case in revival.CASES:
            self.assertTrue(revival.CASE_LABEL[case])


class TheListPutsTheWorkFirst(Revival):

    def test_ready_accounts_come_before_everything_else(self):
        closed = a_record([touch(), reply("unsubscribe")])
        closed["id"] = "closed"
        soon = a_record([touch(at=RECENT)])
        soon["id"] = "soon"
        ready = a_record([touch(contact="a")],
                         contacts=[{"key": "a", "selected": True,
                                    "angle": "finance"},
                                   {"key": "b", "selected": True,
                                    "angle": "ops"}])
        ready["id"] = "ready"
        rows = revival.candidates([closed, soon, ready], today=TODAY,
                                  config=self.config, workspace="productive")
        self.assertEqual(rows[0]["record_id"], "ready")
        self.assertEqual(rows[0]["verdict"], revival.READY)

    def test_the_counts_survive_the_filter(self):
        """"No revival candidates" reads very differently from "forty, and
        none of them has anything new"."""
        rows = revival.candidates(
            [a_record([touch(), reply("unsubscribe")])],
            today=TODAY, config=self.config, workspace="productive")
        found = revival.summarise(rows)
        self.assertEqual(found["counts"][revival.NEVER], 1)
        self.assertEqual(found["ready"], 0)
        self.assertEqual(found["total"], 1)


if __name__ == "__main__":
    unittest.main()
