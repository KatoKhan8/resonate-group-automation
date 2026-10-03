"""ONE MEASURED AUTHORITY FOR THE LENGTH OF A LINKEDIN NOTE OR MESSAGE.

Operator ruling, 2026-10-03, in those terms: NOTE_MIN_CHARS, MESSAGE_MIN_CHARS
and MESSAGE_MAX_CHARS are replaced by one measured contract in the same shape
as the email word contract - li2 100-299 aiming for 125, li1 with no floor
while it is UNKNOWN, the measured note ceiling of 179 recorded, and LinkedIn's
own 300 kept as the only hard cap on a note.

`skills.linkedin_writing.LINKEDIN_CHAR_CONTRACT` is that authority, a
(floor, target, ceiling) in CHARACTERS per role, and `lint` reads it rather
than carrying numbers of its own - exactly as `lint.STEP_WORD_CONTRACT` reads
`cold_email_writing.WORD_CONTRACT`.

WHAT WAS THERE BEFORE, AND WHY EACH NUMBER IS GONE. Measured 2026-10-03 in
`docs/second-brain/linkedin.md` section 14, over 54,647 outbound messages and
17,732 conversation-to-campaign pairs on HeyReach organisation unit 118832,
window 2026-04-01 to 2026-10-04, classified by `replies.classify_rules`
version "rules-4" with no model:

    NOTE_MIN_CHARS    = 40    REFUTED. It would have refused the
                              best-accepting note in the estate: 19
                              characters, 13.66% acceptance on n = 7,988,
                              +3.13pp over the 10.52% no-note baseline on
                              n = 92,220. It is DELETED, not lowered to 19 -
                              one campaign is not a measurement of a floor.
    MESSAGE_MAX_CHARS = 1900  HAS NEVER BOUND. Longest outbound message in
                              54,647 is 1,097; p99 is 801. The ceiling that
                              separates outcomes is 299, 6.4x lower.
    MESSAGE_MIN_CHARS = 60    BELOW THE MEASURED FLOOR. The 60-99 band it
                              permitted is the worst bucket in the corpus:
                              0.136 strict positives per 100 touches on
                              n = 4,425, against 0.291 in band.
    no target anywhere        THE GAP the contract closes.

These tests are about the EFFECT: the verdict a note or message of a given
length gets at a given step. Two of them are CONTROLS that pass both before
and after this change and are labelled as such, so a blanket change that
simply stopped enforcing length could not be credited to this suite.
"""
import ast
import io
import os
import unittest

from src import copystages, lint
from src.skills import linkedin_writing as licontract

ROLES = ("li1", "li2", "li3+")

#: The three the operator ruled out. Deleted, not re-pointed: each one is
#: refuted by measurement and none is replaced by a second guess.
BANNED_NAMES = ("NOTE_MIN_CHARS", "MESSAGE_MIN_CHARS", "MESSAGE_MAX_CHARS")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCANNED = ("src", "scripts", "tools", "tests")


def _assignments_to(names):
    """["<path>:<line>"] for every ASSIGNMENT to one of `names` under REPO.

    Parsed, not grepped: the refutation is written out in prose in several
    docstrings and comments, and naming a deleted constant in a sentence is
    how that stays readable. Binding the name again is the defect.
    """
    wanted = set(names)
    found = []
    for folder in SCANNED:
        for here, _dirs, files in os.walk(os.path.join(REPO, folder)):
            if "__pycache__" in here:
                continue
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(here, name)
                with io.open(path, encoding="utf-8") as handle:
                    source = handle.read()
                try:
                    tree = ast.parse(source, filename=path)
                except SyntaxError:          # not ours to judge
                    continue
                for node in ast.walk(tree):
                    targets = []
                    if isinstance(node, ast.Assign):
                        targets = node.targets
                    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                        targets = [node.target]
                    for target in targets:
                        if (isinstance(target, ast.Name)
                                and target.id in wanted):
                            found.append("%s:%d" % (path, node.lineno))
    return sorted(found)


def _rec():
    return {"id": "li-contract", "state": "ready",
            "contacts": [{"key": "c1", "name": "A Person",
                          "linkedin": "https://www.linkedin.com/in/x"}]}


def note_fails(text, step_key="li1"):
    """Verdict on a CONNECTION REQUEST of this length. No `requires`.

    Called with THREE arguments on purpose, the step carrying its own `key`.
    `step_key_of` recovers the key that way (route 2), so every assertion in
    this file runs unchanged against the gate as it stood before this change
    and reports a VERDICT rather than a TypeError. A test that errors on the
    old code has not shown that the old code was wrong.
    """
    step = {"channel": "linkedin", "key": step_key, "note": text}
    return lint.check_linkedin(_rec(), "c1", step)


def message_fails(text, step_key="li2"):
    """Verdict on a MESSAGE of this length. `requires` an established
    connection, which is what `lint.is_connection_note` reads."""
    step = {"channel": "linkedin", "key": step_key, "requires": "connected",
            "body": text}
    return lint.check_linkedin(_rec(), "c1", step)


def length_codes(failures):
    return [c for c in failures if c.endswith(("_too_short", "_too_long"))]


class TestTheContractIsData(unittest.TestCase):
    """A contract nothing can read is not a contract."""

    def test_it_is_a_mapping_of_role_to_floor_target_ceiling(self):
        self.assertEqual(sorted(licontract.LINKEDIN_CHAR_CONTRACT),
                         sorted(ROLES))
        for role in ROLES:
            spec = licontract.LINKEDIN_CHAR_CONTRACT[role]
            self.assertEqual(len(spec), 3, role)

    def test_every_known_bound_is_ordered_floor_target_ceiling(self):
        for role in ROLES:
            low, target, high = licontract.LINKEDIN_CHAR_CONTRACT[role]
            known = [v for v in (low, target, high)
                     if v is not licontract.UNKNOWN]
            self.assertEqual(known, sorted(known), role)

    def test_it_is_the_same_shape_as_the_email_word_contract(self):
        """Operator's words: 'isti obrazac kao email' - the same pattern."""
        from src.skills import cold_email_writing as emailcontract
        self.assertEqual(
            {len(v) for v in emailcontract.WORD_CONTRACT.values()},
            {len(v) for v in licontract.LINKEDIN_CHAR_CONTRACT.values()})
        self.assertIs(lint.STEP_WORD_CONTRACT, emailcontract.WORD_CONTRACT)
        self.assertIs(lint.LINKEDIN_CHAR_CONTRACT,
                      licontract.LINKEDIN_CHAR_CONTRACT)


class TestTheMeasuredNumbers(unittest.TestCase):
    """The values, with the measurement each one came from in the name."""

    def test_li2_is_100_to_299_aiming_for_125(self):
        self.assertEqual(licontract.LINKEDIN_CHAR_CONTRACT["li2"],
                         (100, 125, 299))

    def test_li3_plus_is_100_to_299_aiming_for_173(self):
        self.assertEqual(licontract.LINKEDIN_CHAR_CONTRACT["li3+"],
                         (100, 173, 299))

    def test_li1_has_linkedins_own_300_and_no_floor_and_no_target(self):
        low, target, high = licontract.LINKEDIN_CHAR_CONTRACT["li1"]
        self.assertIs(low, licontract.UNKNOWN)
        self.assertIs(target, licontract.UNKNOWN)
        self.assertEqual(high, 300)

    def test_the_measured_note_ceiling_is_recorded_and_is_not_a_refusal(self):
        """179, from the one campaign whose notes averaged 212 characters and
        accepted 8.31% against a 10.52% baseline. It is a prior on one
        campaign, so it is recorded and NOT enforced: a 200-character note
        passes."""
        self.assertEqual(licontract.LI1_MEASURED_CEILING, 179)
        self.assertEqual(length_codes(note_fails("x" * 200)), [])

    def test_every_follow_up_key_resolves_to_the_li3_plus_row(self):
        self.assertEqual(licontract.contract_role("li1"), "li1")
        self.assertEqual(licontract.contract_role("li2"), "li2")
        for key in ("li3", "li4", "li5", "li9"):
            self.assertEqual(licontract.contract_role(key), "li3+", key)

    def test_a_key_the_contract_does_not_name_answers_nothing(self):
        """None means 'this contract says nothing about that key', NOT
        'anything goes' - the same reading `word_range` carries."""
        for key in ("em1", "day1", "", None, "li0"):
            self.assertIsNone(licontract.contract_role(key), key)
            self.assertIsNone(licontract.char_bounds(key), key)
            self.assertIsNone(licontract.char_target(key), key)


class TestUnknownIsNotANumber(unittest.TestCase):
    """A guessed number is worse than a missing one, so UNKNOWN refuses to
    behave like one. It is not None, not 0, not 'no limit'."""

    def test_it_is_a_singleton_tested_with_is(self):
        self.assertIs(licontract.LINKEDIN_CHAR_CONTRACT["li1"][0],
                      licontract.UNKNOWN)
        self.assertIs(lint.LINKEDIN_UNKNOWN, licontract.UNKNOWN)

    def test_it_is_not_none_and_not_zero(self):
        self.assertIsNot(licontract.UNKNOWN, None)
        self.assertNotEqual(licontract.UNKNOWN, 0)
        self.assertNotEqual(licontract.UNKNOWN, "")

    def test_it_has_no_truth_value(self):
        """`if floor:` must raise rather than silently mean 'yes there is a
        floor' or 'no there is not'."""
        with self.assertRaises(TypeError):
            bool(licontract.UNKNOWN)

    def test_it_cannot_become_an_integer(self):
        with self.assertRaises(TypeError):
            int(licontract.UNKNOWN)

    def test_it_cannot_be_compared_to_a_length(self):
        """The accident this guards: `len(text) < floor` with floor UNKNOWN
        would otherwise have to mean something, and both meanings are wrong."""
        with self.assertRaises(TypeError):
            19 < licontract.UNKNOWN          # noqa: B015
        with self.assertRaises(TypeError):
            licontract.UNKNOWN > 19          # noqa: B015

    def test_it_says_its_own_name(self):
        self.assertEqual(repr(licontract.UNKNOWN), "UNKNOWN")
        self.assertEqual(licontract.bound_phrase(licontract.UNKNOWN),
                         "UNKNOWN")


class TestTheGateEnforcesTheContract(unittest.TestCase):
    """THE EFFECT. Every assertion here is a verdict from `check_linkedin`."""

    # ---- li1: NO FLOOR WHILE IT IS UNKNOWN. Fails without the change.
    def test_the_19_character_note_the_corpus_measured_best_is_clean(self):
        """`NOTE_MIN_CHARS` 40 refused this exact shape. 13.66% acceptance on
        n = 7,988, the best note-carrying prospecting campaign in the estate
        and +3.13pp over the no-note baseline."""
        text = "Hey, let's connect!"
        self.assertEqual(len(text), 19)
        self.assertEqual(note_fails(text), [])

    def test_no_note_however_short_is_refused_for_length(self):
        for length in (1, 5, 19, 39, 40, 99):
            self.assertEqual(length_codes(note_fails("x" * length)), [],
                             "a %d-character note was refused" % length)

    def test_an_empty_note_is_still_missing_rather_than_short(self):
        """'No floor' is not 'no note'. An empty step is a different defect
        and keeps its own code."""
        self.assertIn("note_missing", note_fails(""))
        self.assertNotIn("note_too_short", note_fails(""))

    # ---- li1: LinkedIn's own 300 still bites. CONTROL - passes both ways.
    def test_CONTROL_a_301_character_note_is_still_refused(self):
        """Passed before this change and passes after it. Here so that a
        blanket 'stop checking length' cannot satisfy this file."""
        self.assertIn("note_too_long", note_fails("x" * 301))

    def test_CONTROL_a_300_character_note_is_still_allowed(self):
        """The other half of the same control."""
        self.assertNotIn("note_too_long", note_fails("x" * 300))

    # ---- messages: the measured floor. Fails without the change.
    def test_a_99_character_message_is_refused_under_the_measured_floor(self):
        """`MESSAGE_MIN_CHARS` 60 permitted the whole 60-99 band, which is
        the worst-performing length in the corpus."""
        self.assertIn("message_too_short", message_fails("x" * 99))

    def test_a_100_character_message_is_in_band(self):
        self.assertEqual(length_codes(message_fails("x" * 100)), [])

    def test_the_floor_binds_on_every_follow_up_key_too(self):
        for key in ("li3", "li4", "li5"):
            self.assertIn("message_too_short", message_fails("x" * 99, key),
                          key)

    # ---- messages: the measured ceiling. Fails without the change.
    def test_a_300_character_message_is_refused_over_the_measured_ceiling(self):
        """1,900 never bound in 54,647 messages. 299 does."""
        self.assertIn("message_too_long", message_fails("x" * 300))

    def test_a_299_character_message_is_in_band(self):
        self.assertEqual(length_codes(message_fails("x" * 299)), [])

    def test_CONTROL_a_1901_character_message_is_still_refused(self):
        """Refused under the old 1,900 ceiling and under the measured 299
        one. Passes both ways, on purpose."""
        self.assertIn("message_too_long", message_fails("x" * 1901))

    # ---- one refusal at a time, as before.
    def test_a_too_long_message_is_not_also_reported_as_too_short(self):
        self.assertEqual(length_codes(message_fails("x" * 5000)),
                         ["message_too_long"])

    def test_a_message_whose_step_key_is_unknown_gets_the_strictest_bounds(self):
        """No `key` on the step and nothing on the record to recover it from.
        It is known to be a message, so it is gated - at the strictest bounds
        any message role carries, never a looser one."""
        step = {"channel": "linkedin", "requires": "connected",
                "body": "x" * 99}
        self.assertIn("message_too_short",
                      lint.check_linkedin(_rec(), "c1", step))
        step["body"] = "x" * 300
        self.assertIn("message_too_long",
                      lint.check_linkedin(_rec(), "c1", step))
        self.assertEqual(licontract.strictest_message_bounds(), (100, 299))

    def test_the_door_every_step_goes_through_threads_the_key(self):
        """`check_step` is the single door. It must hand the key to the
        LinkedIn side, which until 2026-10-03 it did not."""
        step = {"channel": "linkedin", "requires": "connected",
                "body": "x" * 99}
        self.assertIn("message_too_short",
                      lint.check_step(_rec(), "c1", step, step_key="li2"))


class TestTheRefusalsNameTheirNumber(unittest.TestCase):
    """A reason string is fed back to the writer as its retry instruction.
    'Too short' with no number is a guessing game."""

    def test_the_message_explanations_carry_the_measured_bounds(self):
        low, high = licontract.strictest_message_bounds()
        self.assertIn(str(high), lint.explain(["message_too_long"]))
        self.assertIn(str(low), lint.explain(["message_too_short"]))

    def test_the_message_explanation_names_both_targets(self):
        """The gap the contract closes: there was no target anywhere."""
        said = lint.explain(["message_too_long"])
        self.assertIn(str(licontract.char_target("li2")), said)
        self.assertIn(str(licontract.char_target("li3+")), said)

    def test_the_note_explanation_names_the_cap_and_the_measured_ceiling(self):
        said = lint.explain(["note_too_long"])
        self.assertIn("300", said)
        self.assertIn(str(licontract.LI1_MEASURED_CEILING), said)

    def test_the_note_floor_explanation_says_unknown_while_it_is_unknown(self):
        """And flips to a number the moment one is measured, because it is
        rendered from the contract rather than typed."""
        said = lint.explain(["note_too_short"])
        if licontract.LINKEDIN_CHAR_CONTRACT["li1"][0] is licontract.UNKNOWN:
            self.assertIn("UNKNOWN", said)
        else:
            self.assertIn(
                str(licontract.LINKEDIN_CHAR_CONTRACT["li1"][0]), said)


class TestOneAuthority(unittest.TestCase):
    """The numbers are READ from the declaration, not copied anywhere.

    Asserted by EFFECT: move the declaration and the gate moves with it. A
    second copy in `lint.py` would survive this and these would fail.
    """

    def test_the_gate_reads_the_skills_mapping_itself(self):
        self.assertIs(lint.LINKEDIN_CHAR_CONTRACT,
                      licontract.LINKEDIN_CHAR_CONTRACT)

    def test_changing_the_declaration_changes_the_gate(self):
        original = dict(licontract.LINKEDIN_CHAR_CONTRACT)
        try:
            licontract.LINKEDIN_CHAR_CONTRACT["li2"] = (10, 20, 30)
            self.assertIn("message_too_long", message_fails("x" * 31))
            self.assertEqual(length_codes(message_fails("x" * 20)), [])
            self.assertIn("message_too_short", message_fails("x" * 9))
        finally:
            licontract.LINKEDIN_CHAR_CONTRACT.clear()
            licontract.LINKEDIN_CHAR_CONTRACT.update(original)
        self.assertEqual(length_codes(message_fails("x" * 125)), [])
        self.assertIn("message_too_long", message_fails("x" * 300))

    def test_giving_li1_a_floor_starts_refusing_short_notes(self):
        """The UNKNOWN branch is live, not dead code: the gate asserts no
        floor BECAUSE the contract declares none, and it would assert one the
        moment the corpus could answer."""
        original = dict(licontract.LINKEDIN_CHAR_CONTRACT)
        try:
            licontract.LINKEDIN_CHAR_CONTRACT["li1"] = (19, 50, 300)
            self.assertIn("note_too_short", note_fails("x" * 18))
            self.assertEqual(length_codes(note_fails("x" * 19)), [])
        finally:
            licontract.LINKEDIN_CHAR_CONTRACT.clear()
            licontract.LINKEDIN_CHAR_CONTRACT.update(original)
        self.assertEqual(length_codes(note_fails("x" * 18)), [])

    def test_note_max_chars_is_read_from_the_contract_not_retyped(self):
        self.assertEqual(lint.NOTE_MAX_CHARS,
                         licontract.LINKEDIN_CHAR_CONTRACT["li1"][2])

    def test_the_three_refuted_constants_are_gone_from_lint(self):
        for name in ("NOTE_MIN_CHARS", "MESSAGE_MIN_CHARS",
                     "MESSAGE_MAX_CHARS"):
            self.assertFalse(hasattr(lint, name),
                             "%s is a second authority and must not exist"
                             % name)

    def test_no_module_anywhere_declares_one_of_them_again(self):
        """A constant left behind is the two-authorities defect this
        repository has already paid for once. Scanned as SOURCE over every
        shipped module, script, tool and test, so a new copy in a file
        nothing imports is caught too.

        Parsed with `ast` rather than grepped, because the refutation is
        written out in prose in several docstrings and comments and that
        prose is how it stays readable. A NAME in a sentence is fine; an
        ASSIGNMENT to that name is not.
        """
        offenders = _assignments_to(BANNED_NAMES)
        self.assertEqual(offenders, [], "a second authority was declared")

    def test_the_positive_control_for_that_scan(self):
        """The scan above can only be trusted if it CAN fire. A search that
        never matches anything is green for the wrong reason, and the
        equivalent grep DID silently never fire once in this repository.

        So: write one of the deleted constants into a real .py file under the
        scanned tree, run the same function, and require that it is found -
        then delete it and require that it is not.
        """
        planted = os.path.join(REPO, "tools", "_li_contract_scan_control.py")
        try:
            with io.open(planted, "w", encoding="utf-8") as handle:
                handle.write("MESSAGE_MIN_CHARS = 60\n")
            found = _assignments_to(BANNED_NAMES)
            self.assertTrue(
                any(f.startswith(planted) for f in found),
                "the scan cannot see a constant that is really there: %r"
                % (found,))
        finally:
            if os.path.exists(planted):
                os.remove(planted)
        self.assertEqual(_assignments_to(BANNED_NAMES), [])


class TestTheProseAndTheContractAgree(unittest.TestCase):
    """The writer prompt states the numbers in prose. If the prose and the
    mapping drift apart, the writer is told one number and refused on
    another, which is this repository's recurring shape."""

    def test_the_writer_prompt_states_the_message_band_and_both_targets(self):
        said = copystages.WRITER_SYSTEM
        low, high = licontract.strictest_message_bounds()
        self.assertIn("%d TO %d CHARACTERS" % (low, high), said)
        self.assertIn("aiming for %d at li2 and %d"
                      % (licontract.char_target("li2"),
                         licontract.char_target("li3+")), said)

    def test_the_writer_prompt_carries_the_contract_as_a_table(self):
        said = copystages.WRITER_SYSTEM
        for role in ROLES:
            self.assertIn(role, said)
        self.assertIn("NO FLOOR (UNKNOWN)", said)
        self.assertIn(str(licontract.LI1_MEASURED_CEILING), said)

    def test_the_close_is_no_longer_told_sixty_characters_is_enough(self):
        """The ladder brief said a 78-character close 'clears the gate with
        room to spare'. Under the measured floor it does not, and a prompt
        that asks for copy the gate refuses is a defect, not a style note."""
        from src import cadencelibrary
        close = cadencelibrary.LINKEDIN_DEFAULT_LADDER[4]
        low, _high = licontract.strictest_message_bounds()
        self.assertIn("AT LEAST %d CHARACTERS" % low, close)
        self.assertIn(str(licontract.char_target("li3+")), close)
        self.assertNotIn("One line is the right length", close)

    def test_the_skills_own_validation_line_is_rendered_from_the_mapping(self):
        said = "\n".join(licontract.SKILL.validation)
        self.assertIn(licontract.chars_rule(), said)
        self.assertNotIn("no message is over 600 characters", said)

    def test_the_rendered_rule_names_unknown_as_a_word_not_a_number(self):
        rule = licontract.chars_rule()
        self.assertIn("li1 UNKNOWN-300 aiming for UNKNOWN", rule)
        self.assertIn("li2 100-299 aiming for 125", rule)
        self.assertIn("li3+ 100-299 aiming for 173", rule)


class TestTheCanonicalCopyStillPasses(unittest.TestCase):
    """A contract that refuses the cadence it gates is not shippable. This is
    the measurement, not an assumption: every LinkedIn step the demo cadence
    produces is linted under the new contract.

    THE THIRD CONTROL. It passed before this change and passes after it -
    measured, 18 steps, 129 to 176 characters, every one of them inside both
    the old bounds and the measured band. A change that widened the gate into
    uselessness would also satisfy it, which is exactly why the refusal tests
    above are the ones that carry the weight.
    """

    def test_CONTROL_every_linkedin_step_in_the_demo_lints_clean(self):
        from src import cadence, clients, demo
        config = clients.load("demo")
        _campaign, recs, cfg = demo.build(config)
        checked = 0
        for rec in recs:
            if rec.get("state") in lint.UNSHIPPABLE:
                continue
            timeline = cadence.build(rec, cfg)
            for key, steps in timeline["contacts"].items():
                for step_key, step in steps.items():
                    if step.get("channel") != "linkedin":
                        continue
                    checked += 1
                    self.assertEqual(
                        lint.check_linkedin(rec, key, step), [],
                        "%s/%s/%s" % (rec["id"], key, step_key))
        self.assertGreater(checked, 0, "no LinkedIn step was reached")


if __name__ == "__main__":
    unittest.main()
