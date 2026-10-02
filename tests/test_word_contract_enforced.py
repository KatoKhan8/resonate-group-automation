"""The lint enforces the word contract the writer declares.

`skills.cold_email_writing.WORD_CONTRACT` says em1 to em3 are 60-90 words and
em4 and em5 are 45-90. `lint.py` carried no 60 and no 90 as a word bound at all;
its floor was `MIN_WORDS` (40) for all five, so the declared range was a
preference enforced by nothing. Measured 2026-10-02 on the one approved canary
copy (bigfish-co-uk / rowan-matthews), through BOTH doors:

    em1  61 words  60-90  passed
    em2  41 words  60-90  passed  - 19 words under contract
    em3  53 words  60-90  passed  -  7 words under contract
    em4  46 words  45-90  passed
    em5  41 words  45-90  passed  -  4 words under contract

These tests are about the EFFECT: the verdict a body of a given length gets at a
given step key. Message text is asserted in exactly one place, the explanation
test, and never as a proxy for a verdict.

The bodies here are "word word word ..." on purpose - obviously synthetic, and
the only property under test is how many of them there are.
"""
import unittest

from src import lint
from src.skills import cold_email_writing as writer


def body(n):
    """A body of exactly `n` words. No greeting, so the wrong-person rule and
    the banned-phrase rule both stay out of the way of the word count."""
    return " ".join(["word"] * n)


def contact():
    from src import verification
    c = {"key": "ivana-saric", "name": "Ivana Saric", "title": "Head of Finance",
         "email": "ivana.saric@meridian.test", "angle": "finance",
         "verdict": "valid", "reoon": None}
    evidence = [verification.result("contactout", verification.S_VALID, c["email"]),
                verification.result("deliverable", verification.S_VALID, c["email"])]
    verification.apply(c, verification.decide(evidence), evidence)
    return c


KEY = "ivana-saric"


def record(step_key="em2", words=41, text=None, subject="a subject that is fine"):
    """One record carrying one generated email, stored under `step_key`.

    Stored under its real key rather than handed to `check` out of band: the
    step key is part of the record's shape, and the gate has to work for a
    caller that only has the record.
    """
    text = body(words) if text is None else text
    return {"id": "meridian", "lane": "cold", "client": "productive",
            "company": "Meridian", "domain": "meridian.test",
            "state": "drafted", "drop_reason": None, "contacts": [contact()],
            "diagnosis": None, "hook": "raised a seed round in May", "log": [],
            "cadence": {KEY: {step_key: {"channel": "email", "generated": True,
                                         "subject": subject, "body": text}}}}


def both_doors(step_key="em2", words=41, **kw):
    """The verdict from `check` and from `check_step`, asserted to be the same.

    The two linters were measured to agree at every length before this change
    and must keep agreeing, so every call in this file goes through here.
    """
    rec = record(step_key=step_key, words=words, **kw)
    step = rec["cadence"][KEY][step_key]
    by_check = lint.check(rec, KEY, step)
    by_step = lint.check_step(rec, KEY, step)
    assert by_check == by_step, (step_key, words, by_check, by_step)
    return by_check


def contract_fails(codes):
    return [c for c in codes if lint.is_contract_failure(c)]


class TestTheOperatorsCase(unittest.TestCase):
    """An em2 of 41 words is 19 words under its declared floor and is refused.

    This is the test the mutation has to break: restore the old behaviour - a
    floor of `MIN_WORDS` (40) and no per-step contract - and 41 words passes
    again, which is the defect.
    """

    def test_an_em2_of_41_words_is_refused(self):
        codes = both_doors("em2", 41)
        self.assertEqual(
            contract_fails(codes), ["em2_body_41_words_under_contract_60_to_90"])

    def test_an_em2_of_41_words_is_not_merely_held(self):
        """A refusal that classifies as `held` would still ship the draft."""
        self.assertEqual(lint.classify(both_doors("em2", 41)), "failed")

    def test_an_em3_of_53_words_is_refused(self):
        codes = both_doors("em3", 53)
        self.assertEqual(
            contract_fails(codes), ["em3_body_53_words_under_contract_60_to_90"])

    def test_an_em5_of_41_words_is_refused(self):
        """em5's floor is 45, not 40, so 41 words misses it by four."""
        codes = both_doors("em5", 41)
        self.assertEqual(
            contract_fails(codes), ["em5_body_41_words_under_contract_45_to_90"])

    def test_the_lengths_the_canary_got_right_still_pass(self):
        """em1 at 61 and em4 at 46 are inside their own ranges and must stay
        clean. Enforcing a contract is not tightening it."""
        self.assertEqual(contract_fails(both_doors("em1", 61)), [])
        self.assertEqual(contract_fails(both_doors("em4", 46)), [])


class TestTheDeclaredBounds(unittest.TestCase):
    """Both bounds of both ranges, from the outside in."""

    def test_em1_to_em3_floor_is_60(self):
        for step in ("em1", "em2", "em3"):
            self.assertEqual(len(contract_fails(both_doors(step, 59))), 1, step)
            self.assertEqual(contract_fails(both_doors(step, 60)), [], step)

    def test_em4_and_em5_floor_is_45(self):
        for step in ("em4", "em5"):
            self.assertEqual(len(contract_fails(both_doors(step, 44))), 1, step)
            self.assertEqual(contract_fails(both_doors(step, 45)), [], step)

    def test_every_ceiling_is_90(self):
        for step in ("em1", "em2", "em3", "em4", "em5"):
            self.assertEqual(contract_fails(both_doors(step, 90)), [], step)
            over = contract_fails(both_doors(step, 91))
            self.assertEqual(len(over), 1, step)
            self.assertIn("over_contract", over[0])

    def test_a_body_over_the_ceiling_is_refused_before_body_too_long(self):
        """`MAX_WORDS` is 180. A 100-word em1 is inside that and outside its
        own contract, which is the whole point of having the narrower one."""
        codes = both_doors("em1", 100)
        self.assertNotIn("body_too_long", codes)
        self.assertEqual(contract_fails(codes),
                         ["em1_body_100_words_over_contract_60_to_90"])


class TestOneAuthority(unittest.TestCase):
    """The numbers are READ from the writer's declaration, not copied here.

    Asserted by effect: move the declaration and the gate moves with it. A
    second copy in `lint.py` would survive this and the test would fail.
    """

    def test_the_gate_reads_the_writers_mapping_itself(self):
        self.assertIs(lint.STEP_WORD_CONTRACT, writer.WORD_CONTRACT)

    def test_changing_the_declaration_changes_the_gate(self):
        original = dict(writer.WORD_CONTRACT)
        try:
            writer.WORD_CONTRACT.clear()
            writer.WORD_CONTRACT.update(original)
            writer.WORD_CONTRACT["em2"] = (30, 35, 40)
            self.assertEqual(contract_fails(both_doors("em2", 41)),
                             ["em2_body_41_words_over_contract_30_to_40"])
            self.assertEqual(contract_fails(both_doors("em2", 35)), [])
        finally:
            writer.WORD_CONTRACT.clear()
            writer.WORD_CONTRACT.update(original)
        self.assertEqual(contract_fails(both_doors("em2", 41)),
                         ["em2_body_41_words_under_contract_60_to_90"])

    def test_the_declared_ranges_are_the_ones_the_writer_is_told(self):
        self.assertEqual(writer.word_range("em1"), (60, 90))
        self.assertEqual(writer.word_range("em4"), (45, 90))
        self.assertEqual(writer.word_target("em1"), 75)
        self.assertEqual(writer.word_target("em4"), 65)
        for step in ("em1", "em2", "em3", "em4", "em5"):
            low, target, high = writer.WORD_CONTRACT[step]
            self.assertIn("%d-%d range" % (low, high),
                          writer.SKILL.output_schema["emails"][step])
            self.assertIn("~%d words" % target,
                          writer.SKILL.output_schema["emails"][step])


class TestTheOldRuleIsNotMasked(unittest.TestCase):
    """The positive control that already existed must keep firing."""

    def test_a_two_word_body_still_yields_body_too_short(self):
        codes = both_doors("em2", text="Ivana hello")
        self.assertIn("body_too_short", codes)

    def test_a_two_word_body_yields_both_refusals(self):
        """Not one instead of the other: the forty-word floor and the contract
        are separate rules and a two-word body breaks both."""
        codes = both_doors("em2", text=body(2))
        self.assertIn("body_too_short", codes)
        self.assertEqual(contract_fails(codes),
                         ["em2_body_2_words_under_contract_60_to_90"])

    def test_the_forty_word_floor_still_stands_where_no_contract_applies(self):
        self.assertIn("body_too_short", both_doors("day1", 39))
        self.assertNotIn("body_too_short", both_doors("day1", 40))

    def test_a_step_the_contract_does_not_name_keeps_its_old_verdict(self):
        """`day1` is the single-email draft shape, 40-180 words. 41 words is
        fine there and this change must not have an opinion about it."""
        self.assertEqual(both_doors("day1", 41), [])
        self.assertEqual(both_doors("day15", 41), [])


class TestBothDoorsAgree(unittest.TestCase):
    """A sweep across both bounds, verdict by verdict, through both linters."""

    def test_check_and_check_step_agree_at_every_length(self):
        for step in ("em1", "em4", "day1"):
            for words in range(10, 201):
                rec = record(step_key=step, words=words)
                held = rec["cadence"][KEY][step]
                self.assertEqual(lint.check(rec, KEY, held),
                                 lint.check_step(rec, KEY, held),
                                 "%s at %d words" % (step, words))

    def test_the_sweep_actually_crosses_both_bounds(self):
        """A sweep that never changes verdict proves nothing. em1 must pass
        inside 60-90 and be refused on both sides of it."""
        verdicts = {w: bool(contract_fails(both_doors("em1", w)))
                    for w in (10, 59, 60, 75, 90, 91, 200)}
        self.assertEqual(verdicts, {10: True, 59: True, 60: False, 75: False,
                                    90: False, 91: True, 200: True})


class TestTheRefusalCanBeActedOn(unittest.TestCase):
    """The refusal names the step, the count and both bounds, so the reader
    knows which way it missed and by how much. The only test in this file that
    reads message text, and it reads it for content, not for a verdict."""

    def test_the_code_itself_names_step_count_and_both_bounds(self):
        code = contract_fails(both_doors("em2", 41))[0]
        for part in ("em2", "41", "60", "90", "under"):
            self.assertIn(part, code)

    def test_the_explanation_names_the_size_of_the_miss(self):
        code = contract_fails(both_doors("em2", 41))[0]
        said = lint.explain([code])
        self.assertIn("em2", said)
        self.assertIn("41 words", said)
        self.assertIn("60 to 90", said)
        self.assertIn("19 words under", said)
        self.assertIn("75", said)

    def test_the_explanation_names_an_overshoot_as_an_overshoot(self):
        code = contract_fails(both_doors("em4", 100))[0]
        said = lint.explain([code])
        self.assertIn("10 words over", said)

    def test_an_unexplained_code_is_still_passed_through(self):
        self.assertEqual(lint.explain(["something_nobody_explained"]),
                         "something_nobody_explained")


class TestEveryDoorOnTheRecord(unittest.TestCase):
    """`check_record` walks the record itself, which is how the queue is linted."""

    def test_check_record_refuses_the_under_contract_step(self):
        rec = record("em2", 41)
        results = lint.check_record(rec)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(contract_fails(results[0]["failures"]),
                         ["em2_body_41_words_under_contract_60_to_90"])

    def test_a_caller_with_no_key_still_gets_the_gate(self):
        """`eligibility.decide` lints the stored step and passes no key. The
        step is found on the record, so the contract still applies."""
        rec = record("em3", 53)
        step = rec["cadence"][KEY]["em3"]
        self.assertEqual(contract_fails(lint.check(rec, KEY, step)),
                         ["em3_body_53_words_under_contract_60_to_90"])

    def test_an_expanded_step_is_found_by_its_words(self):
        """`cadence.status_for` lints a freshly EXPANDED step: a new object,
        carrying the stored body, and not equal to the stored step either - it
        has a status and a day the stored one does not. Measured: identity
        found none of 2,734 of these. The body does."""
        rec = record("em2", 41)
        stored = rec["cadence"][KEY]["em2"]
        expanded = dict(stored)
        expanded.update({"day": 4, "status": "eligible", "variant_id": "v1"})
        self.assertIsNot(expanded, stored)
        self.assertNotEqual(expanded, stored)
        self.assertEqual(contract_fails(lint.check(rec, KEY, expanded)),
                         ["em2_body_41_words_under_contract_60_to_90"])

    def test_two_steps_with_the_same_body_name_no_step(self):
        """Ambiguity is refused rather than guessed. A template body repeated
        across two steps could be either, and attributing it to whichever came
        first would put a verdict on the wrong step."""
        rec = record("em2", 41)
        same = rec["cadence"][KEY]["em2"]["body"]
        rec["cadence"][KEY]["em4"] = {"channel": "email", "generated": True,
                                     "subject": "a subject that is fine",
                                     "body": same}
        loose = {"channel": "email", "generated": True,
                 "subject": "a subject that is fine", "body": same}
        self.assertEqual(lint.step_contract_key(rec, KEY, loose), "")
        self.assertEqual(contract_fails(lint.check(rec, KEY, loose)), [])
        # ...but each stored step is still gated by its own key.
        self.assertEqual(
            contract_fails(lint.check(rec, KEY, rec["cadence"][KEY]["em2"])),
            ["em2_body_41_words_under_contract_60_to_90"])

    def test_a_step_that_is_on_no_record_is_not_guessed_at(self):
        """A step handed in loose, with no key anywhere, cannot be attributed
        to em2 rather than em4 - so it keeps the 40-word floor and nothing is
        invented about which contract it is under."""
        loose = {"channel": "email", "generated": True,
                 "subject": "a subject that is fine", "body": body(41)}
        rec = record("em2", 41)
        rec["cadence"][KEY] = {}
        self.assertEqual(contract_fails(lint.check(rec, KEY, loose)), [])

    def test_a_step_carrying_its_own_key_is_gated_by_it(self):
        loose = {"channel": "email", "generated": True, "key": "em2",
                 "subject": "a subject that is fine", "body": body(41)}
        rec = record("em2", 41)
        rec["cadence"][KEY] = {}
        self.assertEqual(contract_fails(lint.check(rec, KEY, loose)),
                         ["em2_body_41_words_under_contract_60_to_90"])


class TestLinkedInIsUntouched(unittest.TestCase):
    def test_a_linkedin_step_is_not_measured_in_words(self):
        rec = record("em2", 41)
        rec["cadence"][KEY] = {"li2": {"channel": "linkedin",
                                       "linkedin_action": "message",
                                       "text": "A short note that is long "
                                               "enough to clear the sixty "
                                               "character minimum here."}}
        step = rec["cadence"][KEY]["li2"]
        self.assertEqual(contract_fails(lint.check_step(rec, KEY, step)), [])


if __name__ == "__main__":
    unittest.main()
