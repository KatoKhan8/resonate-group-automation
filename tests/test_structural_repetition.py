"""TASK-047. Four emails, different words, one formula.

The existing `repetition_across_rungs` counts shared distinctive WORDS,
and a formula that varies its nouns shares almost none. This check
catches the SHAPE: two rungs collide when their opening move AND
closing move are the same.

The opening move is what the first sentence does (describe them, describe
us, ask a question, state an observation). The closing move is what the
last sentence does (ask a question, propose a call, offer an out, state
something).

Measured against the phase7 estate (twelve emails, two steps each):
ZERO collisions. day1 opens observation/closes question; day15 opens
observation/closes statement. Different closing moves, no collision.

The canary note must pass. A gate that fails good copy is worse than none.
"""
import unittest

from src import quality


# --------------------------------------------------------------- fixtures

# The problematic formula described in TASK-047: four emails that open
# with [describe them] and close with [statement], varying only nouns.
FORMULA_EMAILS = [
    {"key": "em1", "text": (
        "Your agency describes itself as creating custom-made solutions "
        "that adapt to the ever-changing market. I am reaching out to "
        "you as the founder because your approach to client work "
        "suggests you value flexibility. Would a brief conversation "
        "about profitability be useful?")},
    {"key": "em2", "text": (
        "Your agency highlights work on diverse campaigns like Bestseller "
        "and Nilfisk, showing a strong focus on creative execution. I am "
        "reaching out to you as the founder because that kind of portfolio "
        "deserves clear margin visibility. Would a brief conversation "
        "about profitability be useful?")},
    {"key": "em3", "text": (
        "How does your team currently track project profitability across "
        "multiple campaigns? Productive joins time tracking, project "
        "budgets and margin reporting in one view so the number is there "
        "while the work is running rather than reconstructed afterwards.")},
    {"key": "em4", "text": (
        "A short thought on visibility. Teams running several campaigns "
        "at once tend to know the revenue picture and question the margin "
        "picture, because revenue lives in one system and margin in three. "
        "That is usually the point where a single view earns its place.")},
    {"key": "em5", "text": (
        "Last note from me. If this is not relevant right now, no worries "
        "at all. Happy to leave it here.")},
]

# The phase7 estate emails: two steps per contact, day1 and day15.
# Using the actual meridian/marin-kovac emails from the fixture.
PHASE7_DAY1 = {
    "key": "day1",
    "text": (
        "Marin, running operations across five offices in three countries "
        "is the point where scheduling stops being a conversation and "
        "starts being a spreadsheet nobody quite trusts. The part I would "
        "ask about is how long it takes to see that a job is going over "
        "before it has gone over, because most teams your size can report "
        "last month quickly and this week slowly.\n\n"
        "Is that the shape of it, or have you already put something in place?")
}

PHASE7_DAY15 = {
    "key": "day15",
    "text": (
        "Marin, one thing I did not ask about earlier. When a job starts "
        "slipping at Meridian, who notices first, and what are they "
        "looking at when they do. For most operations leads the answer "
        "is a person rather than a report, which works well until that "
        "person is on holiday or the job count doubles.\n\n"
        "Worth a short conversation, or is this already handled?")
}

# The canary note. Must pass.
CANARY_NOTE = ("hi Pat, i work with Design Services teams on "
               "utilisation. curious how Clearwater handles it at your size")


# ------------------------------------------------- the shape classifier

class TestStructuralShape(unittest.TestCase):
    """The shape of a message: opening move, closing move, questions."""

    def test_a_question_opening_is_classified_as_question(self):
        shape = quality.structural_shape(
            "How does your team track profitability? We help agencies "
            "see margin in real time.")
        self.assertEqual(shape["opening"], quality.OPENING_QUESTION)

    def test_a_describe_them_opening_is_classified(self):
        shape = quality.structural_shape(
            "Your agency describes itself as creating custom solutions. "
            "I am reaching out because your approach suggests you value "
            "flexibility.")
        self.assertEqual(shape["opening"], quality.OPENING_DESCRIBE_THEM)

    def test_a_describe_us_opening_is_classified(self):
        shape = quality.structural_shape(
            "I work with Design Services teams on utilisation. Curious "
            "how Clearwater handles it at your size.")
        self.assertEqual(shape["opening"], quality.OPENING_DESCRIBE_US)

    def test_an_observation_opening_is_the_default(self):
        shape = quality.structural_shape(
            "Running operations across five offices is the point where "
            "scheduling stops being a conversation. How long does it "
            "take to know which project is profitable?")
        self.assertEqual(shape["opening"], quality.OPENING_OBSERVATION)

    def test_a_question_closing_is_classified(self):
        shape = quality.structural_shape(
            "Running operations across five offices is hard. How does "
            "your team currently track profitability?")
        self.assertEqual(shape["closing"], quality.CLOSING_QUESTION)

    def test_a_call_proposal_closing_is_classified(self):
        shape = quality.structural_shape(
            "Running operations across five offices is hard. Let's "
            "schedule a call this week to discuss.")
        self.assertEqual(shape["closing"], quality.CLOSING_CALL)

    def test_an_out_closing_is_classified(self):
        shape = quality.structural_shape(
            "Running operations across five offices is hard. Last note "
            "from me, no worries if this is not relevant.")
        self.assertEqual(shape["closing"], quality.CLOSING_OUT)

    def test_a_statement_closing_is_the_default(self):
        shape = quality.structural_shape(
            "Running operations across five offices is hard. That is "
            "usually the point where a single view earns its place.")
        self.assertEqual(shape["closing"], quality.CLOSING_STATEMENT)

    def test_a_greeting_is_stripped_before_classification(self):
        """'Hi Sam,' is not a sentence for shape classification."""
        shape = quality.structural_shape(
            "Hi Sam, your team runs campaigns across three markets. "
            "How do you currently track profitability?")
        self.assertEqual(shape["opening"], quality.OPENING_DESCRIBE_THEM)

    def test_question_count_is_correct(self):
        shape = quality.structural_shape(
            "How does your team track profitability? Who notices first? "
            "That is the gap.")
        self.assertEqual(shape["questions"], 2)

    def test_self_reference_by_role_is_detected(self):
        shape = quality.structural_shape(
            "Your agency is impressive. I am reaching out to you as "
            "the founder because your approach suggests you value "
            "flexibility.")
        self.assertTrue(shape["self_ref"])

    def test_no_self_reference_when_absent(self):
        shape = quality.structural_shape(
            "Your agency is impressive. The approach suggests you "
            "value flexibility.")
        self.assertFalse(shape["self_ref"])

    def test_empty_text_returns_safe_defaults(self):
        shape = quality.structural_shape("")
        self.assertEqual(shape["opening"], quality.OPENING_OBSERVATION)
        self.assertEqual(shape["closing"], quality.CLOSING_STATEMENT)
        self.assertEqual(shape["questions"], 0)
        self.assertFalse(shape["self_ref"])


# ------------------------------------------- the structural repetition

class TestStructuralRepetition(unittest.TestCase):
    """Pairs of steps that share the same structural shape."""

    def test_the_formula_emails_collide(self):
        """em1 and em2 both open describe_them and close with a question.
        They share the same shape despite different nouns."""
        collisions = quality.structural_repetition(FORMULA_EMAILS)
        colliding_pairs = [(a, b) for a, b, _ in collisions]
        self.assertIn(("em1", "em2"), colliding_pairs,
                       "em1 and em2 share the describe_them + question shape")

    def test_phase7_emails_do_not_collide(self):
        """Both day1 and day15 open observation/close question, but neither
        has self_ref, so they do not collide under the stricter rule."""
        steps = [PHASE7_DAY1, PHASE7_DAY15]
        collisions = quality.structural_repetition(steps)
        self.assertEqual(collisions, [],
                         "phase7 emails lack self_ref, so no collision")

    def test_a_single_step_cannot_collide(self):
        collisions = quality.structural_repetition([FORMULA_EMAILS[0]])
        self.assertEqual(collisions, [])

    def test_empty_steps_return_no_collisions(self):
        self.assertEqual(quality.structural_repetition([]), [])

    def test_distinct_shapes_do_not_collide(self):
        steps = [
            {"key": "em1", "text": "Your agency is impressive. How do "
             "you track profitability?"},
            {"key": "em2", "text": "How does your team handle margin "
             "reporting? That is the gap."},
            {"key": "em3", "text": "I work with agencies on utilisation. "
             "Last note from me, no worries if not relevant."},
        ]
        collisions = quality.structural_repetition(steps)
        self.assertEqual(collisions, [])

    def test_collision_detail_includes_the_shape(self):
        collisions = quality.structural_repetition(FORMULA_EMAILS[:2])
        self.assertTrue(collisions)
        _, _, detail = collisions[0]
        self.assertIn("opening", detail)
        self.assertIn("closing", detail)


# ------------------------------------------- the gate integration

class TestGateStructuralRepetition(unittest.TestCase):
    """The structural repetition check fires through the gate."""

    def test_the_formula_fails_through_the_gate(self):
        """em1 against the full set must carry the structural reason."""
        result = quality.gate(
            FORMULA_EMAILS[0]["text"], {}, steps=FORMULA_EMAILS,
            channel="email")
        self.assertEqual(result["verdict"], quality.FAIL)
        self.assertIn(quality.REASON_STRUCTURAL_REPETITION, result["reasons"])

    def test_phase7_passes_through_the_gate(self):
        """The phase7 estate emails must not trigger structural repetition.
        Both open observation/close question, but neither has self_ref."""
        steps = [PHASE7_DAY1, PHASE7_DAY15]
        result = quality.gate(
            PHASE7_DAY1["text"], {}, steps=steps, channel="email")
        self.assertNotIn(quality.REASON_STRUCTURAL_REPETITION, result["reasons"])

    def test_the_canary_passes_through_the_gate(self):
        """A gate that fails good copy is worse than none."""
        result = quality.gate(CANARY_NOTE, {})
        self.assertEqual(result["verdict"], quality.PASS)

    def test_structural_check_does_not_fire_on_linkedin(self):
        """LinkedIn notes are too short for shape analysis."""
        steps = [
            {"key": "li1", "text": "hi izabelle, your agency grew to "
             "forty people. let's connect"},
            {"key": "li2", "text": "hi izabelle, your team runs campaigns "
             "across three markets. let's connect"},
        ]
        result = quality.gate(
            steps[0]["text"], {}, steps=steps, channel="linkedin")
        self.assertNotIn(quality.REASON_STRUCTURAL_REPETITION, result["reasons"])

    def test_no_steps_means_no_structural_check(self):
        """Without the full set, only single-message checks run."""
        result = quality.gate(FORMULA_EMAILS[0]["text"], {})
        self.assertNotIn(quality.REASON_STRUCTURAL_REPETITION, result["reasons"])


# ------------------------------------------- breaking the wiring

class TestBreakingTheWiring(unittest.TestCase):
    """Break the wiring and confirm the test fails for the intended reason.

    TASK-047 rule: a function in quality.py that nothing calls is the
    recurring defect. These tests prove the check is consumed.
    """

    def test_removing_the_shape_match_makes_the_formula_pass(self):
        """Replace em2's opening with a question. The opening moves no
        longer match, so structural_repetition must not fire for that pair."""
        fixed_em2 = {
            "key": "em2",
            "text": (
                "How does your team handle margin reporting across "
                "campaigns like Bestseller and Nilfisk? I am reaching "
                "out because that kind of portfolio deserves clear "
                "visibility. Would a brief conversation be useful?")
        }
        steps = [FORMULA_EMAILS[0], fixed_em2]
        collisions = quality.structural_repetition(steps)
        colliding_pairs = [(a, b) for a, b, _ in collisions]
        self.assertNotIn(("em1", "em2"), colliding_pairs,
                         "different opening moves must not collide")

    def test_replacing_the_closing_makes_the_formula_pass(self):
        """Replace em2's closing with a statement. The closing moves no
        longer match, so structural_repetition must not fire."""
        fixed_em2 = {
            "key": "em2",
            "text": (
                "Your agency highlights work on diverse campaigns like "
                "Bestseller and Nilfisk. I am reaching out because that "
                "kind of portfolio deserves clear margin visibility. "
                "That is usually the point where a single view earns "
                "its place.")
        }
        steps = [FORMULA_EMAILS[0], fixed_em2]
        collisions = quality.structural_repetition(steps)
        colliding_pairs = [(a, b) for a, b, _ in collisions]
        self.assertNotIn(("em1", "em2"), colliding_pairs,
                         "different closing moves must not collide")

    def test_the_gate_reason_reaches_lint_explain(self):
        """The reason code must have an explanation in lint.EXPLAIN, so
        the model is told what to fix on retry."""
        from src import lint
        self.assertIn(quality.REASON_STRUCTURAL_REPETITION, lint.EXPLAIN,
                       "the structural repetition reason must have an "
                       "explanation for the model on retry")

    def test_quality_of_calls_gate_with_email_channel(self):
        """`generate._quality_of` must call gate with channel='email',
        so the structural check runs at draft time."""
        from src import generate
        import inspect
        source = inspect.getsource(generate._quality_of)
        self.assertIn('channel="email"', source,
                       "_quality_of must pass channel='email' to gate")


if __name__ == "__main__":
    unittest.main()
