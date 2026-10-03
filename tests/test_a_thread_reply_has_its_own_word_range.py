#!/usr/bin/env python3
"""A thread reply is 15 to 60 words. em1, em3 and em5 are still 40 or more.

Operator ruling, 2026-10-01: "Thread-reply steps (em2, em4, per
`thread_reply_rungs`) get their OWN range of 15 to 60 words in the body,
excluding the signature and the opt-out line. em1, em3 and em5 keep the
existing 40-word minimum."

WHAT THIS FILE IS FOR, beyond the four cases the ruling named. The expensive
failure here is not a wrong bound, it is a bound enforced at ONE gate. If
generation accepts a 25 word em2 and `approve`, `eligibility` or
`executionguard` then refuse it as `body_too_short`, the canary converges and
stalls one step later - which is this repository's recurring shape. So the last
class drives the range through a call that passes NO step key at all, the way
every one of those modules calls it, and asserts they agree.

NOTHING HERE WIDENS A GATE. `test_em3_at_35_words_is_still_refused` is the
control the ruling asked for, and `test_an_unknown_step_key_gets_the_stricter
_floor` is the one that says an unnamed caller can never be handed the shorter
one by accident.
"""
import unittest

from src import lint, optout, verification


def contact():
    c = {"name": "Petra Horvat", "title": "Operations Director",
         "email": "petra.horvat@harbourline.test", "verdict": "valid"}
    evidence = [verification.result("contactout", verification.S_VALID,
                                    c["email"]),
                verification.result("deliverable", verification.S_VALID,
                                    c["email"])]
    verification.apply(c, verification.decide(evidence), evidence)
    return c


def words(n):
    return " ".join(["word"] * n)


def record(step_key, body, subject="a subject that is fine"):
    """A record whose cadence holds ONE step, under `step_key`."""
    return {"id": "harbourline", "lane": "cold", "client": "productive",
            "company": "Harbourline", "domain": "harbourline.test",
            "state": "drafted", "drop_reason": None, "log": [],
            # A cold record with no hook trips `cold_no_hook`, which is a rule
            # about the RECORD and not about this step's length. Supplied so
            # the length verdicts are the only thing these tests can see.
            "hook": "opened a second studio in May",
            "diagnosis": None,
            "contacts": [contact()],
            "cadence": {"petra-horvat": {
                step_key: {"channel": "email", "generated": True,
                           "subject": subject, "body": body}}}}


def length_codes(step_key, body, **kw):
    """Only the length verdicts, so an unrelated rule cannot pass this test."""
    rec = record(step_key, body)
    step = rec["cadence"]["petra-horvat"][step_key]
    fails = lint.check(rec, "petra-horvat", step, **kw)
    return sorted(f for f in fails
                  if f in ("body_too_short", "body_too_long",
                           "reply_too_short", "reply_too_long"))


class TestTheFourCasesTheRulingNamed(unittest.TestCase):
    def test_em2_at_14_words_is_refused(self):
        self.assertEqual(length_codes("em2", words(14)), ["reply_too_short"])

    def test_em2_at_25_words_passes(self):
        self.assertEqual(length_codes("em2", words(25)), [])

    def test_em4_at_70_words_is_refused(self):
        self.assertEqual(length_codes("em4", words(70)), ["reply_too_long"])

    def test_em3_at_35_words_is_still_refused(self):
        """THE CONTROL: the other three steps did not move."""
        self.assertEqual(length_codes("em3", words(35)), ["body_too_short"])


class TestTheThreeOpenersKeptTheirRange(unittest.TestCase):
    """em3 and em5 keep 40 to 180. em1 NO LONGER DOES.

    THE OPERATOR MOVED em1 ON 2026-10-03 and these three tests are updated
    rather than deleted, because what they are really for is "the floor and
    the ceiling are enforced at this gate and the codes say which range was
    applied" - and that is still what they assert. The NUMBERS now come from
    `lint.WORD_CONTRACT`, which is the single authority the same decision
    created (A21), so this file cannot be the place a stale em1 bound
    survives. The band is (90, 120, 140) and it was measured against the
    operator's own 17 em1 exemplars: 16 of 16 inside it, median 120.5.
    """

    def test_em3_and_em5_keep_the_40_word_floor(self):
        for step in ("em3", "em5"):
            self.assertEqual(length_codes(step, words(39)),
                             ["body_too_short"], step)
            self.assertEqual(length_codes(step, words(40)), [], step)

    def test_em1_has_the_operators_own_floor(self):
        low, _target, _high = lint.WORD_CONTRACT["em1"]
        self.assertEqual(length_codes("em1", words(low - 1)),
                         ["body_too_short"])
        self.assertEqual(length_codes("em1", words(low)), [])

    def test_em3_and_em5_may_still_run_to_180_words(self):
        self.assertEqual(length_codes("em3", words(180)), [])
        self.assertEqual(length_codes("em3", words(181)), ["body_too_long"])

    def test_em1_has_the_operators_own_ceiling(self):
        _low, _target, high = lint.WORD_CONTRACT["em1"]
        self.assertEqual(length_codes("em1", words(high)), [])
        self.assertEqual(length_codes("em1", words(high + 1)),
                         ["body_too_long"])

    def test_a_reply_may_not_use_the_openers_ceiling(self):
        """61 words is fine for em3 and refused for em2. Same body.

        em3 rather than em1, because em1's own floor is now 90 and the point
        of this test is the CEILING: one length, legal for a step that opens
        a thread and refused for one that replies inside it.
        """
        self.assertEqual(length_codes("em3", words(61)), [])
        self.assertEqual(length_codes("em2", words(61)), ["reply_too_long"])


class TestTheCodeSaysWhichRangeWasApplied(unittest.TestCase):
    """The code is the writer's retry instruction, so it must be the right one.

    Telling a step whose floor is 15 that it is "under 40 words" is an
    instruction to break its own ceiling. Measured on the canary record: em4
    came back under length 7 then 10 times in consecutive rounds.
    """

    def test_a_short_reply_is_never_reported_as_body_too_short(self):
        codes = length_codes("em2", words(10))
        self.assertIn("reply_too_short", codes)
        self.assertNotIn("body_too_short", codes)

    def test_the_explanation_names_15_and_not_40(self):
        sentence = lint.explain(["reply_too_short"])
        self.assertIn("15", sentence)
        self.assertNotIn("40", sentence)

    def test_the_long_explanation_names_60(self):
        self.assertIn("60", lint.explain(["reply_too_long"]))


class TestWhatCounts(unittest.TestCase):
    """The ruling measures the body "excluding the signature and the opt-out".

    MEASURED on production before this was written: zero of 4082 generated
    email bodies in the queue carry either, because the renderer appends the
    opt-out and the prompt forbids a signature. So these assert a property that
    cannot currently be reached from the writer - deliberately, because the
    count must not silently start crediting words no prospect reads if one day
    it is.
    """

    def test_the_opt_out_line_does_not_count_toward_the_floor(self):
        body = words(12) + "\n\n" + optout.OPT_OUT_LINE
        self.assertGreaterEqual(len(body.split()), 15)
        self.assertEqual(length_codes("em2", body), ["reply_too_short"])

    def test_a_signature_block_does_not_count_toward_the_floor(self):
        body = words(12) + "\n\nBest,\nIvan Mamic\nProductive\nsome more lines"
        self.assertGreaterEqual(len(body.split()), 15)
        self.assertEqual(length_codes("em2", body), ["reply_too_short"])

    def test_removing_text_can_only_make_it_stricter(self):
        """A reply at the ceiling is not rescued by padding it with a sign-off."""
        body = words(61) + "\n\nBest,\nIvan Mamic"
        self.assertEqual(length_codes("em2", body), ["reply_too_long"])

    def test_a_signoff_in_the_middle_does_not_hide_a_long_body(self):
        """THE ATTACK: strip-from-the-first-sign-off would defeat the ceiling.

        A 190-word em1 with a line reading "Best," at word 100 must still be
        refused as too long. Only a SHORT trailing block is a signature.
        """
        body = words(100) + "\n\nBest,\n" + words(90)
        self.assertEqual(len(lint.countable_words(body)), 191)
        self.assertEqual(length_codes("em1", body), ["body_too_long"])

    def test_a_reply_cannot_duck_its_ceiling_with_a_mid_body_signoff(self):
        body = words(40) + "\n\nThanks,\n" + words(40)
        self.assertEqual(length_codes("em2", body), ["reply_too_long"])

    def test_a_genuinely_short_trailing_signature_is_still_excluded(self):
        body = words(12) + "\n\nBest,\nIvan Mamic\nProductive"
        self.assertEqual(len(lint.countable_words(body)), 12)
        self.assertEqual(length_codes("em2", body), ["reply_too_short"])


class TestTheOfferIsTheAuthority(unittest.TestCase):
    def test_an_offer_declaring_its_reply_rungs_decides_them(self):
        self.assertEqual(sorted(lint.reply_steps_for(
            {"thread_reply_rungs": [2, 4]})), ["em2", "em4"])

    def test_an_offer_with_a_different_shape_is_not_forced_into_offer_as(self):
        steps = lint.reply_steps_for({"thread_reply_rungs": [3]})
        self.assertEqual(sorted(steps), ["em3"])
        self.assertEqual(lint.word_range("em3", steps),
                         (lint.REPLY_MIN_WORDS, lint.REPLY_MAX_WORDS))
        self.assertEqual(lint.word_range("em2", steps),
                         (lint.MIN_WORDS, lint.MAX_WORDS))

    def test_an_offer_declaring_none_falls_back_to_the_ruled_steps(self):
        """`OFFER-B-OPERATIONS` declares no `thread_reply_rungs`. Measured."""
        self.assertEqual(sorted(lint.reply_steps_for(None)), ["em2", "em4"])
        self.assertEqual(sorted(lint.reply_steps_for({})), ["em2", "em4"])

    def test_the_offer_the_canary_actually_selects_declares_none(self):
        """If this ever starts failing, the config caught up with the ruling.

        It is here so that the fallback's reason is a measured fact rather than
        a claim in a comment: `OFFER-B-OPERATIONS` is what
        `_select_offers('productive', 'champion')` returns, and it carries no
        `thread_reply_rungs`, which is why keying the range off that field
        alone would have changed nothing for the canary.
        """
        from src import generate_campaign
        selected = generate_campaign._select_offers("productive", "champion")
        self.assertEqual(sorted(selected), ["OFFER-B-OPERATIONS"])
        offer = selected["OFFER-B-OPERATIONS"]
        self.assertFalse(offer.get("thread_reply_rungs"))
        # And the fallback therefore still gives em2 and em4 the reply range.
        self.assertEqual(lint.word_range("em4", lint.reply_steps_for(offer)),
                         (lint.REPLY_MIN_WORDS, lint.REPLY_MAX_WORDS))


class TestEveryGateAgrees(unittest.TestCase):
    """The range must hold where NO step key is passed, which is most callers.

    `approve`, `eligibility`, `executionguard`, `campaigns`, `cadence`,
    `heyreachfactory` and `benchmark` all call `lint.check(rec, key, step)` with
    three arguments. Two of those modules are owned by other agents and were not
    edited. If the key could not be recovered from the record they would each
    apply em1's floor to a reply that generation had just accepted.
    """

    def test_a_stored_em2_of_25_words_passes_a_three_argument_call(self):
        rec = record("em2", words(25))
        step = rec["cadence"]["petra-horvat"]["em2"]
        self.assertEqual(lint.step_key_of(rec, "petra-horvat", step), "em2")
        self.assertEqual(lint.check(rec, "petra-horvat", step), [])

    def test_a_stored_em3_of_25_words_still_fails_a_three_argument_call(self):
        rec = record("em3", words(25))
        step = rec["cadence"]["petra-horvat"]["em3"]
        self.assertIn("body_too_short",
                      lint.check(rec, "petra-horvat", step))

    def test_the_key_is_recovered_from_a_copy_not_only_the_same_object(self):
        rec = record("em2", words(25))
        twin = dict(rec["cadence"]["petra-horvat"]["em2"])
        self.assertEqual(lint.step_key_of(rec, "petra-horvat", twin), "em2")
        self.assertEqual(lint.check(rec, "petra-horvat", twin), [])

    def test_two_identical_steps_resolve_to_the_stricter_floor(self):
        """THE ATTACK: identical copy across steps must not lend em2's floor.

        Byte-identical bodies across steps are real here - the phase7 fixture is
        twelve of them. If equality matching answered with the FIRST equal key,
        a 25-word em3 whose body matched em2's would be judged at 15 and pass.
        """
        rec = record("em2", words(25))
        same = dict(rec["cadence"]["petra-horvat"]["em2"])
        rec["cadence"]["petra-horvat"]["em3"] = dict(same)
        twin = dict(same)
        self.assertIsNone(lint.step_key_of(rec, "petra-horvat", twin))
        self.assertIn("body_too_short",
                      lint.check(rec, "petra-horvat", twin))

    def test_identity_still_wins_over_an_ambiguous_equality(self):
        """The real em2 object is still em2, even with an identical twin at em3."""
        rec = record("em2", words(25))
        step = rec["cadence"]["petra-horvat"]["em2"]
        rec["cadence"]["petra-horvat"]["em3"] = dict(step)
        self.assertEqual(lint.step_key_of(rec, "petra-horvat", step), "em2")
        self.assertEqual(lint.check(rec, "petra-horvat", step), [])

    def test_an_unknown_step_key_gets_the_stricter_floor(self):
        """A step that is not in the cadence is judged at 40, never at 15."""
        rec = record("em2", words(25))
        orphan = {"channel": "email", "subject": "a subject that is fine",
                  "body": words(25)}
        self.assertIsNone(lint.step_key_of(rec, "petra-horvat", orphan))
        self.assertEqual(lint.word_range(None), (lint.MIN_WORDS,
                                                 lint.MAX_WORDS))

    def test_a_day_keyed_cadence_is_untouched_by_this(self):
        """`day1`/`day15` steps are not em-keyed and keep the 40-word floor."""
        self.assertEqual(length_codes("day1", words(25)), ["body_too_short"])
        self.assertEqual(length_codes("day15", words(25)), ["body_too_short"])


class TestTheWriterIsToldTheSameNumbers(unittest.TestCase):
    """A range the prompt does not state is a range the writer cannot satisfy.

    This asserts the PROMPT the model receives, which is the artefact that
    actually governs what gets written - not that a particular sentence appears
    in the source. `copystages.WRITER_SYSTEM` is the text handed to the model
    verbatim, so it is the behaviour here.
    """

    def test_the_prompt_states_the_reply_range(self):
        from src import copystages
        text = copystages.WRITER_SYSTEM + copystages.FINAL_CHECK
        self.assertIn("15 TO 60 WORDS", text)
        self.assertIn(str(lint.REPLY_MIN_WORDS), text)
        self.assertIn(str(lint.REPLY_MAX_WORDS), text)

    def test_the_prompt_no_longer_demands_45_words_of_every_step(self):
        from src import copystages
        text = copystages.WRITER_SYSTEM + copystages.FINAL_CHECK
        self.assertNotIn("EVERY EMAIL BODY IS AT LEAST 45 WORDS", text)
        self.assertNotIn("em2 to em5 included", text)


if __name__ == "__main__":
    unittest.main()
