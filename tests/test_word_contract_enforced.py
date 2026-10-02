"""The writer contract is the ONLY authority for an email body's word count.

Operator ruling, 2026-10-02, in those terms.
`skills.cold_email_writing.WORD_CONTRACT` declares a (floor, target, ceiling)
per step - em1 and em3 60-90 aiming for 75, em2 and em4 45-90 aiming for 60, em5
45-90 aiming for 65 - and `lint` reads that mapping rather than carrying numbers
of its own. `lint.py` previously carried no 60 and no 90 as a word bound at all;
its floor was `MIN_WORDS` (40) for all five, so the declared range was a
preference enforced by nothing. Measured 2026-10-02 on the one approved canary
copy (bigfish-co-uk / rowan-matthews), through BOTH doors, against the ranges as
they stood that morning:

    em1  61 words  60-90  passed
    em2  41 words  60-90  passed  - 19 words under contract
    em3  53 words  60-90  passed  -  7 words under contract
    em4  46 words  45-90  passed
    em5  41 words  45-90  passed  -  4 words under contract

WHAT THE SAME COPY GETS NOW, under the ruled ranges, measured not predicted:
em1 61 clean, em2 41 REFUSED (4 under its 45 floor), em3 53 REFUSED (7 under 60),
em4 46 clean, em5 41 REFUSED (4 under 45). The operator has confirmed that em2 at
41 words is correctly refused and that nothing is to be widened to rescue it.

ALSO ABOLISHED THAT DAY: the 15-to-60 thread-reply range for em2 and em4, which
`tests/test_a_thread_reply_has_its_own_word_range.py` asserted and which is
deleted with it. The parts of that file which are STILL TRUE are kept here -
`TestWhatCounts` (the signature and opt-out exclusion, and the mid-body sign-off
attack on the ceiling) and `TestTheKeyIsRecovered` (how a step's cadence key is
found, and that an ambiguous match answers nothing).

These tests are about the EFFECT: the verdict a body of a given length gets at a
given step key. Message text is asserted in exactly two places - the explanation
test and the prompt test - and never as a proxy for a verdict.

The bodies here are "word word word ..." on purpose - obviously synthetic, and
the only property under test is how many of them there are.
"""
import unittest

from src import copystages, lint, optout
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
STEPS = ("em1", "em2", "em3", "em4", "em5")


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
    """An em2 of 41 words is four words under its declared floor and refused.

    This is the test the mutation has to break: restore a 15-to-60-shaped em2 and
    41 words passes again, which is the defect.
    """

    def test_an_em2_of_41_words_is_refused(self):
        codes = both_doors("em2", 41)
        self.assertEqual(
            contract_fails(codes), ["em2_body_41_words_under_contract_45_to_90"])

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
    """Both bounds of every step's range, from the outside in.

    Driven FROM the mapping rather than from numbers retyped here, so moving a
    bound moves this test with it and a bound that moved by accident is still
    caught by `TestTheOperatorsCase` and `TestEveryRangeHasRoom`.
    """

    def test_every_floor_refuses_one_word_under_and_admits_itself(self):
        for step in STEPS:
            low, _, _ = writer.WORD_CONTRACT[step]
            under = contract_fails(both_doors(step, low - 1))
            self.assertEqual(len(under), 1, (step, low, under))
            self.assertIn("under_contract", under[0])
            self.assertEqual(contract_fails(both_doors(step, low)), [], step)

    def test_every_ceiling_admits_itself_and_refuses_one_word_over(self):
        for step in STEPS:
            _, _, high = writer.WORD_CONTRACT[step]
            self.assertEqual(contract_fails(both_doors(step, high)), [], step)
            over = contract_fails(both_doors(step, high + 1))
            self.assertEqual(len(over), 1, (step, high, over))
            self.assertIn("over_contract", over[0])

    def test_em1_and_em3_floor_is_60_and_em2_em4_em5_is_45(self):
        """The ruled numbers, spelled out once, so a silent edit to the mapping
        is a failure here rather than a test that moved with it."""
        self.assertEqual(writer.WORD_CONTRACT["em1"], (60, 75, 90))
        self.assertEqual(writer.WORD_CONTRACT["em2"], (45, 60, 90))
        self.assertEqual(writer.WORD_CONTRACT["em3"], (60, 75, 90))
        self.assertEqual(writer.WORD_CONTRACT["em4"], (45, 60, 90))
        self.assertEqual(writer.WORD_CONTRACT["em5"], (45, 65, 90))

    def test_a_body_over_the_ceiling_is_refused_before_body_too_long(self):
        """`MAX_WORDS` is 180. A 100-word em1 is inside that and outside its
        own contract, which is the whole point of having the narrower one."""
        codes = both_doors("em1", 100)
        self.assertNotIn("body_too_long", codes)
        self.assertEqual(contract_fails(codes),
                         ["em1_body_100_words_over_contract_60_to_90"])


class TestEveryRangeHasRoom(unittest.TestCase):
    """EVERY STEP HAS AT LEAST THIRTY ALLOWED LENGTHS. The operator's own test.

    THE DEFECT THIS GUARDS, which is the reason the 2026-10-01 thread-reply
    ruling was abolished a day later: that ruling made em2 15 to 60 words while
    the writer contract made it 60 to 90, and the INTERSECTION OF THOSE TWO IS
    THE SINGLE VALUE 60. A range with one legal length is an equality, not a
    threshold - no writer hits it reliably, and a gate that demands it converges
    on nothing. Thirty is not a magic number; it is comfortably more room than
    any writer needs and comfortably less than the 141 that `MIN_WORDS` to
    `MAX_WORDS` allows, so it fails loudly for a range that has collapsed and
    never for one that is merely strict.

    Measured on the five ruled ranges: em1 31, em2 46, em3 31, em4 46, em5 46.
    """

    MINIMUM_ALLOWED_LENGTHS = 30

    def test_every_step_has_at_least_thirty_allowed_lengths(self):
        for step in STEPS:
            low, _, high = writer.WORD_CONTRACT[step]
            room = high - low + 1
            self.assertGreaterEqual(
                room, self.MINIMUM_ALLOWED_LENGTHS,
                "%s allows only %d word lengths (%d to %d). A range this narrow "
                "is an equality, not a threshold: the abolished 15-to-60 reply "
                "range intersected a 60-to-90 em2 to exactly one legal value."
                % (step, room, low, high))

    def test_the_room_is_measured_on_the_whole_mapping_not_a_sample(self):
        """A test that silently inspected zero steps would pass. This fails if
        the mapping stops holding all five."""
        self.assertEqual(sorted(writer.WORD_CONTRACT), sorted(STEPS))

    def test_every_allowed_length_is_actually_accepted(self):
        """Room declared is not room enforced. Every length the mapping calls
        legal must lint clean at that step - otherwise the usable range is
        narrower than the declared one and this guard measures the wrong thing."""
        for step in STEPS:
            low, _, high = writer.WORD_CONTRACT[step]
            refused = [n for n in range(low, high + 1)
                       if contract_fails(both_doors(step, n))]
            self.assertEqual(refused, [], (step, refused))


class TestTheContractNeverLoosensTheOldBounds(unittest.TestCase):
    """Operator ruling point 3: a step the contract does not name keeps
    `MIN_WORDS` 40 and `MAX_WORDS` 180, and that floor is not to be loosened.

    This asserts the stronger property the five named steps have to satisfy for
    that to be safe: every contract range sits INSIDE 40..180, so applying the
    contract can only ever refuse more than 40..180 would and never less. That
    is what makes it sound for `check` to report a contract refusal rather than
    a second `body_too_short` for the same body.
    """

    def test_every_contract_range_is_inside_min_and_max_words(self):
        for step in STEPS:
            low, target, high = writer.WORD_CONTRACT[step]
            self.assertGreaterEqual(low, lint.MIN_WORDS, step)
            self.assertLessEqual(high, lint.MAX_WORDS, step)
            self.assertLessEqual(low, target, step)
            self.assertLessEqual(target, high, step)

    def test_the_old_bounds_are_still_the_ones_section_6_2_names(self):
        self.assertEqual((lint.MIN_WORDS, lint.MAX_WORDS), (40, 180))


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
                         ["em2_body_41_words_under_contract_45_to_90"])

    def test_the_declared_ranges_are_the_ones_the_writer_is_told(self):
        self.assertEqual(writer.word_range("em1"), (60, 90))
        self.assertEqual(writer.word_range("em2"), (45, 90))
        self.assertEqual(writer.word_target("em1"), 75)
        self.assertEqual(writer.word_target("em2"), 60)
        self.assertEqual(writer.word_target("em5"), 65)
        for step in STEPS:
            low, target, high = writer.WORD_CONTRACT[step]
            self.assertIn("%d-%d range" % (low, high),
                          writer.SKILL.output_schema["emails"][step])
            self.assertIn("~%d words" % target,
                          writer.SKILL.output_schema["emails"][step])

    def test_the_skills_validation_line_names_every_step(self):
        """One line covering all five, rendered from the mapping. It said
        "email bodies are 60-90 words" while em2's range was 45-90, which is
        the wrong number told to the one step that needed the right one."""
        said = "\n".join(writer.SKILL.validation)
        for step in STEPS:
            low, target, high = writer.WORD_CONTRACT[step]
            self.assertIn("%s %d-%d aiming for %d" % (step, low, high, target),
                          said)


class TestTheAbolishedRuleIsGone(unittest.TestCase):
    """The 15-to-60 thread-reply range left no residue behind it.

    Not a style check: every one of these names was a live reader of a word
    bound, and a gate that still carries one has two authorities for a body's
    length, which is the condition the ruling exists to end.
    """

    def test_the_reply_range_names_are_gone_from_the_gate(self):
        for name in ("REPLY_MIN_WORDS", "REPLY_MAX_WORDS", "REPLY_STEPS",
                     "reply_steps_for", "word_range"):
            self.assertFalse(hasattr(lint, name),
                             "lint.%s survived the abolition" % name)

    def test_the_reply_codes_can_no_longer_be_produced_or_explained(self):
        self.assertNotIn("reply_too_short", lint.EXPLAIN)
        self.assertNotIn("reply_too_long", lint.EXPLAIN)
        # An unknown code is passed through rather than invented, which is how a
        # stored historical verdict stays readable.
        self.assertEqual(lint.explain(["reply_too_short"]), "reply_too_short")

    def test_no_step_is_ever_judged_against_15_or_60_again(self):
        """THE EFFECT, not the names: a 20-word em2 and a 59-word em2 are both
        verdicts the abolished range got right and the contract gets differently.
        20 was legal under 15-to-60 and is refused now; 59 was legal under it and
        is legal now, but by the contract's floor of 45 rather than its own."""
        self.assertTrue(contract_fails(both_doors("em2", 20)))
        self.assertIn("body_too_short", both_doors("em2", 20))
        self.assertEqual(contract_fails(both_doors("em2", 59)), [])
        self.assertEqual(contract_fails(both_doors("em2", 61)), [])

    def test_the_offer_has_no_say_in_a_bodys_length(self):
        """`lint.check` used to take `reply_steps`, so an offer's own
        `thread_reply_rungs` could change a word bound. It cannot now - and the
        offer keeps the say it always had over the step-objective LADDER, which
        `sequencegate` reads from that field directly and never through `lint`."""
        import inspect
        for fn in (lint.check, lint.check_step):
            self.assertNotIn("reply_steps",
                             inspect.signature(fn).parameters, fn.__name__)
        from src import sequencegate
        self.assertIn("thread_reply_rungs",
                      inspect.getsource(sequencegate))


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
                         ["em2_body_2_words_under_contract_45_to_90"])

    def test_the_forty_word_floor_still_stands_where_no_contract_applies(self):
        self.assertIn("body_too_short", both_doors("day1", 39))
        self.assertNotIn("body_too_short", both_doors("day1", 40))

    def test_a_step_the_contract_does_not_name_keeps_its_old_verdict(self):
        """`day1` is the single-email draft shape, 40-180 words. 41 words is
        fine there and this change must not have an opinion about it."""
        self.assertEqual(both_doors("day1", 41), [])
        self.assertEqual(both_doors("day15", 41), [])
        self.assertEqual(both_doors("day1", 180), [])
        self.assertEqual(both_doors("day1", 181), ["body_too_long"])


class TestWhatCounts(unittest.TestCase):
    """ONE definition of "a word", and it excludes what no prospect reads.

    Kept from `test_a_thread_reply_has_its_own_word_range.py`, whose reply range
    was abolished and whose count rule was not. MEASURED on production before it
    was written: zero of 4082 generated email bodies in the queue carry the
    opt-out line or a sign-off, because the renderer appends the opt-out and the
    prompt forbids a signature. So these assert a property that cannot currently
    be reached from the writer - deliberately, because the count must not
    silently start crediting words no prospect reads if one day it is.
    """

    def test_the_opt_out_line_does_not_count_toward_the_floor(self):
        text = body(42) + "\n\n" + optout.OPT_OUT_LINE
        self.assertGreaterEqual(len(text.split()), 45)
        self.assertEqual(contract_fails(both_doors("em2", text=text)),
                         ["em2_body_42_words_under_contract_45_to_90"])

    def test_a_signature_block_does_not_count_toward_the_floor(self):
        text = body(42) + "\n\nBest,\nDana Sample\nProductive\nsome more lines"
        self.assertGreaterEqual(len(text.split()), 45)
        self.assertEqual(contract_fails(both_doors("em2", text=text)),
                         ["em2_body_42_words_under_contract_45_to_90"])

    def test_removing_text_can_only_make_it_stricter(self):
        """A body at the ceiling is not rescued by padding it with a sign-off."""
        text = body(91) + "\n\nBest,\nDana Sample"
        self.assertEqual(contract_fails(both_doors("em2", text=text)),
                         ["em2_body_91_words_over_contract_45_to_90"])

    def test_a_signoff_in_the_middle_does_not_hide_a_long_body(self):
        """THE ATTACK: strip-from-the-first-sign-off would defeat the ceiling.

        A 190-word em1 with a line reading "Best," at word 100 must still be
        counted at 191 and refused. Only a SHORT trailing block is a signature.
        """
        text = body(100) + "\n\nBest,\n" + body(90)
        self.assertEqual(len(lint.countable_words(text)), 191)
        codes = both_doors("em1", text=text)
        self.assertIn("body_too_long", codes)
        self.assertEqual(contract_fails(codes),
                         ["em1_body_191_words_over_contract_60_to_90"])

    def test_a_genuinely_short_trailing_signature_is_still_excluded(self):
        text = body(42) + "\n\nBest,\nDana Sample\nProductive"
        self.assertEqual(len(lint.countable_words(text)), 42)
        self.assertEqual(contract_fails(both_doors("em2", text=text)),
                         ["em2_body_42_words_under_contract_45_to_90"])


class TestBothDoorsAgree(unittest.TestCase):
    """A sweep across both bounds, verdict by verdict, through both linters."""

    def test_check_and_check_step_agree_at_every_length(self):
        for step in ("em1", "em2", "day1"):
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

    def test_em2_and_em1_disagree_where_their_floors_differ(self):
        """45 to 59 words is legal for em2 and refused for em1. The same body.
        A contract that gave every step the same range would pass everything
        else in this file and fail here."""
        for words in (45, 52, 59):
            self.assertEqual(contract_fails(both_doors("em2", words)), [], words)
            self.assertEqual(len(contract_fails(both_doors("em1", words))), 1,
                             words)


class TestTheRefusalCanBeActedOn(unittest.TestCase):
    """The refusal names the step, the count and both bounds, so the reader
    knows which way it missed and by how much. The only test in this file that
    reads message text, and it reads it for content, not for a verdict."""

    def test_the_code_itself_names_step_count_and_both_bounds(self):
        code = contract_fails(both_doors("em2", 41))[0]
        for part in ("em2", "41", "45", "90", "under"):
            self.assertIn(part, code)

    def test_the_explanation_names_the_size_of_the_miss(self):
        code = contract_fails(both_doors("em2", 41))[0]
        said = lint.explain([code])
        self.assertIn("em2", said)
        self.assertIn("41 words", said)
        self.assertIn("45 to 90", said)
        self.assertIn("4 words under", said)
        self.assertIn("60", said)

    def test_the_explanation_names_an_overshoot_as_an_overshoot(self):
        code = contract_fails(both_doors("em4", 100))[0]
        said = lint.explain([code])
        self.assertIn("10 words over", said)

    def test_the_explanation_names_the_target_not_the_floor(self):
        """The recurring failure this code exists for: a writer told its floor
        writes its floor. em5 aims for 65 and must be told 65, not 45."""
        said = lint.explain([contract_fails(both_doors("em5", 41))[0]])
        self.assertIn("about 65 words", said)

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
                         ["em2_body_41_words_under_contract_45_to_90"])

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
                         ["em2_body_41_words_under_contract_45_to_90"])

    def test_a_step_carrying_its_own_key_is_gated_by_it(self):
        loose = {"channel": "email", "generated": True, "key": "em2",
                 "subject": "a subject that is fine", "body": body(41)}
        rec = record("em2", 41)
        rec["cadence"][KEY] = {}
        self.assertEqual(contract_fails(lint.check(rec, KEY, loose)),
                         ["em2_body_41_words_under_contract_45_to_90"])


class TestTheKeyIsRecovered(unittest.TestCase):
    """`step_key_of` - which cadence key is this step? ONE implementation.

    Kept from `test_a_thread_reply_has_its_own_word_range.py`, which is deleted:
    the range it was written for is abolished, the recovery it asserts is not,
    and it is the only thing that puts the contract in front of `cadence.
    status_for`, `eligibility.decide`, `approve` and `executionguard`, none of
    which passes a step key.
    """

    def test_identity_finds_the_stored_step(self):
        rec = record("em2", 41)
        step = rec["cadence"][KEY]["em2"]
        self.assertEqual(lint.step_key_of(rec, KEY, step), "em2")

    def test_the_key_is_recovered_from_a_copy_not_only_the_same_object(self):
        rec = record("em2", 41)
        twin = dict(rec["cadence"][KEY]["em2"])
        self.assertEqual(lint.step_key_of(rec, KEY, twin), "em2")

    def test_identity_still_wins_over_an_ambiguous_equality(self):
        """The real em2 object is still em2, even with an identical twin at em1."""
        rec = record("em2", 41)
        step = rec["cadence"][KEY]["em2"]
        rec["cadence"][KEY]["em1"] = dict(step)
        self.assertEqual(lint.step_key_of(rec, KEY, step), "em2")

    def test_two_steps_with_the_same_body_name_no_step(self):
        """THE ATTACK: identical copy across steps must not lend em2's floor.

        Byte-identical bodies across steps are real here - the phase7 fixture is
        twelve of them. If equality matching answered with the FIRST equal key, a
        50-word em1 whose body matched em2's would be judged at 45 and pass.
        Ambiguity resolves to None, and None is the stricter 40-word floor.
        """
        rec = record("em2", 50)
        same = rec["cadence"][KEY]["em2"]["body"]
        rec["cadence"][KEY]["em1"] = {"channel": "email", "generated": True,
                                      "subject": "a subject that is fine",
                                      "body": same}
        loose = {"channel": "email", "generated": True,
                 "subject": "a subject that is fine", "body": same}
        self.assertIsNone(lint.step_key_of(rec, KEY, loose))
        self.assertEqual(contract_fails(lint.check(rec, KEY, loose)), [])
        # ...but each stored step is still gated by its own key, and em1's floor
        # of 60 refuses the 50 words that em2's floor of 45 admits.
        self.assertEqual(
            contract_fails(lint.check(rec, KEY, rec["cadence"][KEY]["em2"])), [])
        self.assertEqual(
            contract_fails(lint.check(rec, KEY, rec["cadence"][KEY]["em1"])),
            ["em1_body_50_words_under_contract_60_to_90"])

    def test_a_step_that_is_on_no_record_is_not_guessed_at(self):
        """A step handed in loose, with no key anywhere, cannot be attributed
        to em1 rather than em2 - so it keeps the 40-word floor and nothing is
        invented about which contract it is under."""
        loose = {"channel": "email", "generated": True,
                 "subject": "a subject that is fine", "body": body(41)}
        rec = record("em2", 41)
        rec["cadence"][KEY] = {}
        self.assertIsNone(lint.step_key_of(rec, KEY, loose))
        self.assertEqual(contract_fails(lint.check(rec, KEY, loose)), [])


class TestTheProseAndTheContractAgree(unittest.TestCase):
    """The prompt the model receives states the same numbers the gate enforces.

    A range the prompt does not state is a range the writer cannot satisfy, and a
    range the prompt states differently is worse: the writer satisfies the prompt
    and the gate refuses it, round after round. Measured on the bigfish canary,
    2026-10-01: em4 came back under length 7 then 10 times in consecutive rounds
    because the prompt demanded a number its own gate did not.

    These assert the TEXT HANDED TO THE MODEL - `copystages.STRATEGY_SYSTEM`,
    `WRITER_SYSTEM` and `FINAL_CHECK` are passed verbatim - not that a sentence
    appears in a source file.

    WHY THE PROSE IS NOT RENDERED FROM THE MAPPING, which would make this test
    unnecessary. `skills.cold_email_writing` imports `copystages` at module level
    to build `SKILL.procedure`, so `copystages` cannot import the contract back:
    the cycle breaks at import time, measured, not assumed. The numbers are
    therefore written out in the prompt and this test is what keeps them honest.
    """

    def prompts(self):
        return "\n".join((copystages.STRATEGY_SYSTEM, copystages.WRITER_SYSTEM,
                          copystages.FINAL_CHECK))

    def test_every_step_range_is_stated_somewhere_in_the_prompts(self):
        said = self.prompts().lower()
        for step in STEPS:
            low, target, high = writer.WORD_CONTRACT[step]
            self.assertIn("%d to %d" % (low, high), said, step)
            self.assertIn("%d-%d range" % (low, high),
                          copystages.WRITER_SYSTEM)
            self.assertIn("~%d words" % target, copystages.WRITER_SYSTEM)

    def test_the_output_schema_in_the_prompt_names_each_steps_own_range(self):
        """The JSON skeleton the model copies is the most literal instruction in
        the prompt. An em2 slot reading "60-90" there outranks any prose."""
        for step in STEPS:
            low, target, high = writer.WORD_CONTRACT[step]
            self.assertIn('"%s":"<full body, ~%d words, %d-%d range>"'
                          % (step, target, low, high),
                          copystages.WRITER_SYSTEM)

    def test_the_prompts_no_longer_state_the_abolished_reply_range(self):
        text = self.prompts().lower()
        for gone in ("15 to 60", "reply_too_short", "reply_too_long",
                     "45 to 180", "every email body is at least 45 words"):
            self.assertNotIn(gone, text, gone)

    def test_the_prompts_never_state_a_bound_the_contract_does_not_have(self):
        """The failure mode this catches is a leftover: a number that was true
        of a previous ruling and is now an instruction to be refused."""
        text = self.prompts()
        floors = {low for low, _, _ in writer.WORD_CONTRACT.values()}
        ceilings = {high for _, _, high in writer.WORD_CONTRACT.values()}
        for bogus in ("15 TO 60", "60 TO 60", "40 TO 90"):
            self.assertNotIn(bogus, text.upper(), bogus)
        self.assertEqual(floors, {45, 60})
        self.assertEqual(ceilings, {90})


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
