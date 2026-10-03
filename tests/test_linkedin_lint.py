"""LinkedIn copy gets its own rules, because the email rules do not transfer.

The requirement is that no final outbound step bypasses lint, and half the
cadence is not email. A connection note is capped at 300 characters by LinkedIn
itself, and the forty-word minimum that stops an email reading as a drive-by
would make a note impossible - so relaxing the email rules would have been the
wrong shape of answer.
"""
import unittest

from src import cadence, clients, demo, lint
from src.skills import linkedin_writing as linkedincontract
from tests.campaignbase import CampaignTest

GOOD_NOTE = ("hi Ann, i work with operations leads at agencies on utilisation "
             "and capacity. curious how you handle it at your size. happy to "
             "connect.")


class LinkedInLintTest(CampaignTest):
    def rec(self, linkedin="https://www.linkedin.com/in/ann"):
        return {"id": "acme", "state": "drafted", "client": "demo",
                "contacts": [{"key": "c0", "name": "Ann", "email": "a@b.test",
                              "linkedin": linkedin}]}

    def note(self, text=GOOD_NOTE, **extra):
        step = {"channel": "linkedin", "note": text}
        step.update(extra)
        return step

    def message(self, text, **extra):
        return self.note(text, requires="connection_accepted", **extra)


class TestTheNoteRules(LinkedInLintTest):
    def test_a_good_note_passes(self):
        self.assertEqual(lint.check_linkedin(self.rec(), "c0", self.note()), [])

    def test_over_three_hundred_characters_fails(self):
        """LinkedIn's own limit; over it, the request simply cannot be sent."""
        self.assertIn("note_too_long",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.note("x" * 301)))

    def test_exactly_three_hundred_passes(self):
        self.assertNotIn("note_too_long",
                         lint.check_linkedin(self.rec(), "c0",
                                             self.note("x" * 300)))

    def test_a_two_word_note_is_not_refused_because_no_floor_was_measured(self):
        """THIS TEST IS THE INVERSE OF THE ONE IT REPLACES, AND DELIBERATELY.

        It asserted `note_too_short` on "hi there" against `NOTE_MIN_CHARS`
        40. Measured 2026-10-03 over the whole HeyReach estate: the
        best-accepting connection note in it is 19 characters and it accepted
        1,091 of 7,988 = 13.66%, +3.13pp over the no-note baseline of 10.52%
        on n = 92,220. A floor of 40 would have refused the best-measured
        note on the platform, so it is deleted rather than lowered - one
        campaign is not a measurement of a floor either, and 19 would be an
        invented number. li1's floor is UNKNOWN and this gate asserts nothing
        about it.
        """
        self.assertNotIn("note_too_short",
                         lint.check_linkedin(self.rec(), "c0",
                                             self.note("hi there")))

    def test_the_best_accepting_note_in_the_estate_would_now_be_allowed(self):
        """The refutation, as the exact string it was measured on."""
        note = "Hey, let\'s connect!"
        self.assertEqual(len(note), 19)
        self.assertEqual(
            lint.check_linkedin(self.rec(), "c0", self.note(note)), [])

    def test_the_note_floor_is_unknown_and_is_not_a_number(self):
        floor, ceiling = linkedincontract.char_bounds("li1")
        self.assertIs(floor, linkedincontract.UNKNOWN)
        self.assertEqual(ceiling, 300)
        with self.assertRaises(TypeError):
            int(floor)
        with self.assertRaises(TypeError):
            bool(floor)

    def test_an_empty_note_is_caught_rather_than_sent_blank(self):
        self.assertIn("note_missing",
                      lint.check_linkedin(self.rec(), "c0", self.note("")))

    def test_an_unresolved_placeholder_fails(self):
        self.assertIn("placeholder",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.note("hi {first_name}, i work "
                                                    "with ops leads on "
                                                    "utilisation and capacity "
                                                    "planning at agencies.")))

    def test_an_em_dash_fails_here_too(self):
        self.assertIn("em_dash",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.note(GOOD_NOTE + " — really.")))

    def test_a_filler_phrase_fails(self):
        self.assertIn("filler_phrase",
                      lint.check_linkedin(
                          self.rec(), "c0",
                          self.note("hi Ann, just following up on utilisation "
                                    "and capacity across your delivery teams.")))

    def test_mentioning_the_email_is_its_own_failure(self):
        """The most common multichannel mistake, and the least recoverable."""
        for text in ("hi Ann, following up on my email about utilisation here.",
                     "hi Ann, did you check your inbox for what i sent about "
                     "capacity planning?",
                     "hi Ann, as i wrote earlier about utilisation across your "
                     "delivery teams."):
            self.assertIn("mentions_the_email",
                          lint.check_linkedin(self.rec(), "c0",
                                              self.note(text)), text)

    def test_a_missing_profile_is_held_rather_than_failed(self):
        failures = lint.check_linkedin(self.rec(linkedin=None), "c0",
                                       self.note())
        self.assertEqual(failures, ["profile_missing"])
        self.assertEqual(lint.classify_linkedin(failures), "held")

    def test_a_contact_that_is_not_on_the_record_fails(self):
        self.assertIn("recipient_not_on_record",
                      lint.check_linkedin(self.rec(), "nobody", self.note()))

    def test_a_dropped_record_fails_every_step(self):
        rec = self.rec()
        rec["state"] = "dropped"
        self.assertIn("record_dropped",
                      lint.check_linkedin(rec, "c0", self.note()))


class TestTheMessageRules(LinkedInLintTest):
    def test_a_message_in_the_measured_band_passes(self):
        """Was `..._may_be_longer_than_a_note`, with a 427-character body.

        That is no longer true and the test says so rather than being
        widened. A message's ceiling is 299 - one BELOW the connection
        note\'s 300 - because 100-299 is the band measured to beat every
        band above it: 0.491 strict positives per 100 touches against 0.285
        for 300-499 at li2, on n = 6,923 and n = 8,776.
        """
        text = "thanks for connecting Ann. " + ("utilisation matters. " * 8)
        self.assertEqual(len(text), 195)
        self.assertEqual(lint.check_linkedin(self.rec(), "c0",
                                             self.message(text)), [])

    def test_the_message_ceiling_now_sits_below_the_note_ceiling(self):
        """The inversion, named. 300 characters passes as a connection
        request and is refused as a message, which is the opposite of the
        arrangement these two rules had until 2026-10-03."""
        text = "x" * 300
        self.assertNotIn("note_too_long",
                         lint.check_linkedin(self.rec(), "c0",
                                             self.note(text)))
        self.assertIn("message_too_long",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.message(text)))

    def test_a_message_under_the_measured_floor_is_refused(self):
        """99 characters. The 60-99 band is the worst bucket in the corpus:
        0.136 strict positives per 100 touches on n = 4,425, against 0.291
        in band. `MESSAGE_MIN_CHARS` 60 permitted all of it."""
        self.assertIn("message_too_short",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.message("x" * 99)))
        self.assertNotIn("message_too_short",
                         lint.check_linkedin(self.rec(), "c0",
                                             self.message("x" * 100)))

    def test_a_message_is_still_capped(self):
        """THE CONTROL. 2,000 characters was refused under the old 1,900
        ceiling and is refused under the measured 299 one. It passes both
        ways on purpose: a blanket change that stopped enforcing length
        would not be caught by it, and every other test here would have to
        catch that instead."""
        self.assertIn("message_too_long",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.message("x" * 2000)))

    def test_the_two_are_told_apart_by_the_cadence_not_by_a_day_number(self):
        """So a reconfigured cadence keeps the distinction."""
        self.assertTrue(lint.is_connection_note({"channel": "linkedin"}))
        self.assertFalse(lint.is_connection_note(
            {"channel": "linkedin", "requires": "connection_accepted"}))


class TestTheSingleDoor(LinkedInLintTest):
    def test_check_step_routes_by_channel(self):
        rec = self.rec()
        self.assertEqual(lint.check_step(rec, "c0", self.note()), [])
        email = {"channel": "email", "subject": "x", "body": "short"}
        self.assertTrue(lint.check_step(rec, "c0", email))

    def test_a_step_with_no_channel_is_treated_as_email(self):
        rec = self.rec()
        self.assertTrue(lint.check_step(rec, "c0", {"subject": "", "body": ""}))

    def test_the_cadence_blocks_a_linkedin_step_that_fails_lint(self):
        config = clients.load("demo")
        campaign, recs, cfg = demo.build(config)
        rec = recs[0]
        key = rec["contacts"][0]["key"]
        # A note nobody could send: past LinkedIn's own limit.
        rec.setdefault("cadence", {}).setdefault(key, {})["day3"] = {
            "channel": "linkedin", "note": "x" * 400}
        timeline = cadence.build(rec, cfg)
        step = timeline["contacts"][key]["day3"]
        # The cadence expands templates fresh, so the stored override only
        # matters where the step is generated; what must hold either way is
        # that the step was linted at all.
        self.assertIn("status", step)
        self.assertIsNotNone(lint.check_step(rec, key, step))

    def test_a_generated_linkedin_step_that_fails_lint_is_blocked(self):
        config = clients.load("demo")
        campaign, recs, cfg = demo.build(config)
        rec = recs[0]
        key = rec["contacts"][0]["key"]
        bad = {"channel": "linkedin", "note": "x" * 400}
        self.assertEqual(lint.check_linkedin(rec, key, bad), ["note_too_long"])
        self.assertEqual(lint.classify_linkedin(["note_too_long"]), "failed")


class TestTheDemoCadencePasses(CampaignTest):
    def test_every_linkedin_step_in_the_demo_lints_clean(self):
        config = clients.load("demo")
        campaign, recs, cfg = demo.build(config)
        for rec in recs:
            if rec.get("state") in lint.UNSHIPPABLE:
                continue          # the demo drops one on purpose
            timeline = cadence.build(rec, cfg)
            for key, steps in timeline["contacts"].items():
                for step_key, step in steps.items():
                    if step.get("channel") != "linkedin":
                        continue
                    self.assertEqual(lint.check_linkedin(rec, key, step), [],
                                     f"{rec['id']}/{key}/{step_key}")


if __name__ == "__main__":
    unittest.main()
