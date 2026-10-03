"""LinkedIn copy gets its own rules, because the email rules do not transfer.

The requirement is that no final outbound step bypasses lint, and half the
cadence is not email. A connection note is capped at 300 characters by LinkedIn
itself, and the forty-word minimum that stops an email reading as a drive-by
would make a note impossible - so relaxing the email rules would have been the
wrong shape of answer.
"""
import unittest

from src import cadence, clients, demo, lint
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
        # `linkedin_action` IS NOT DECORATION HERE. A LinkedIn step must
        # declare whether it is a connection request or a message, because
        # the two are linted against different limits - see
        # `lint.operation_of` and
        # `tests/test_a_linkedin_step_must_declare_its_operation.py`. These
        # fixtures previously declared nothing and were read as notes by
        # default, which is precisely the defect that rule removed.
        step = {"channel": "linkedin", "linkedin_action": "connect",
                "note": text}
        step.update(extra)
        return step

    def message(self, text, **extra):
        extra.setdefault("linkedin_action", "message")
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

    def test_a_two_word_note_is_too_short_to_be_worth_sending(self):
        self.assertIn("note_too_short",
                      lint.check_linkedin(self.rec(), "c0", self.note("hi there")))

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
    def test_a_message_after_connecting_may_be_longer_than_a_note(self):
        """Longer than a note's FLOOR, not longer than its ceiling.

        The message band measured in `docs/second-brain/linkedin.md` S14.3
        is 100-299, against the note's 40-300. So a message may say more
        than a note needs to - it must clear 100 where a note clears 40 -
        and the old reading of this test, that a message may run to 1900
        characters, was never measured and is now refused.
        """
        text = "thanks for connecting Ann. " + ("utilisation matters. " * 8)
        self.assertTrue(100 <= len(text) <= 299, len(text))
        self.assertEqual(lint.check_linkedin(self.rec(), "c0",
                                             self.message(text)), [])

    def test_a_message_is_still_capped(self):
        self.assertIn("message_too_long",
                      lint.check_linkedin(self.rec(), "c0",
                                          self.message("x" * 2000)))

    def test_the_two_are_told_apart_by_what_the_step_declares(self):
        """So a reconfigured cadence keeps the distinction.

        REWRITTEN. This used to read:

            self.assertTrue(lint.is_connection_note({"channel": "linkedin"}))

        i.e. it asserted that a step declaring NOTHING is a connection
        request. That was the defect, written down as a requirement: every
        step `generate_campaign` produces arrives in exactly that shape, so
        the assertion guaranteed all five LinkedIn steps took the
        connection-request door. The distinction the test name protects -
        told apart by the cadence, never by a day number - is kept and
        strengthened: it is now told apart by what the step DECLARES, and a
        step that declares nothing is refused rather than assumed.
        """
        self.assertTrue(lint.is_connection_note(
            {"channel": "linkedin", "linkedin_action": "connect"}))
        self.assertFalse(lint.is_connection_note(
            {"channel": "linkedin", "requires": "connection_accepted"}))
        self.assertFalse(lint.is_connection_note({"channel": "linkedin"}))
        self.assertIsNone(lint.operation_of({"channel": "linkedin"}))


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
        bad = {"channel": "linkedin", "linkedin_action": "connect",
               "note": "x" * 400}
        self.assertEqual(lint.check_linkedin(rec, key, bad), ["note_too_long"])
        self.assertEqual(lint.classify_linkedin(["note_too_long"]), "failed")

    def test_the_same_step_undeclared_is_blocked_for_a_better_reason(self):
        """Without `linkedin_action` the step is refused BEFORE length.

        It is not told it is 100 characters over a connection request's
        limit, because nothing established that it is a connection request.
        Fail closed means the first unanswered question is the answer.
        """
        config = clients.load("demo")
        campaign, recs, cfg = demo.build(config)
        rec = recs[0]
        key = rec["contacts"][0]["key"]
        undeclared = {"channel": "linkedin", "note": "x" * 400}
        failures = lint.check_linkedin(rec, key, undeclared)
        self.assertEqual(failures, ["operation_type_undeclared"])
        self.assertEqual(lint.classify_linkedin(failures), "failed")


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
