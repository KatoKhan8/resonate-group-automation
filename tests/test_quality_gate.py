"""The quality gate between the model and a prospect.

TASK-014. A semantic QA gate that reads a generated message and decides
PASS or FAIL with a reason, so a weak draft is escalated rather than
sent.

The six real `16kagency-com` LinkedIn notes that `openai/gpt-4o-mini`
produced from six DISTINCT briefs - the wiring was correct, `step_block`
resolved `purpose` for all six rungs of `LINKEDIN_LADDER` - and
returned six rephrasings of one idea. Every one passed lint. At least
three defects a person would catch instantly:

  li1  the client's own angle wording is put in the prospect's mouth
  li4  an unsupported claim about other customers
  all  six rungs, one idea - the failure LINKEDIN_LADDER was written to
       prevent

And the `nineyards-ie` template note - honest, short, specific - must
PASS. A gate that fails good copy is worse than none.
"""
import unittest

from src import clients, quality


# --------------------------------------------------------------- fixtures

def _productive_config():
    """The live Productive config, which carries the angles that leaked."""
    return clients.load("productive")


# The six real notes from `16kagency-com`, measured 2026-09-13.
# Every one passed lint. The gate must fail at least li1 and li4, and
# the repetition check must fire across the set.
SIX_NOTES = [
    {"key": "li1", "text": (
        "hi izabelle, as a founder, you know the importance of having "
        "profitability visible on monday. let's connect!")},
    {"key": "li2", "text": (
        "how do you currently track profitability for your projects?")},
    {"key": "li3", "text": (
        "without clear visibility on profitability, it can be tough to "
        "make timely decisions. how are you currently tracking this?")},
    {"key": "li4", "text": (
        "many teams like yours have found that visibility into "
        "profitability can transform their operations. have you seen "
        "similar challenges?")},
    {"key": "li5", "text": (
        "just checking in to see if you had a chance to think about how "
        "we can help with profitability visibility. any thoughts?")},
    {"key": "li6", "text": (
        "if you're looking to enhance profitability visibility, i'd "
        "love to hear your thoughts on that.")},
]

# The canary note. "hi Brooke, i work with Design Services teams on "
# "utilisation. curious how Nineyards handles it at your size" - honest,
# short, specific. A gate that fails this is worse than none.
CANARY_NOTE = ("hi Brooke, i work with Design Services teams on "
               "utilisation. curious how Nineyards handles it at your size")


# --------------------------------------------------------------- the checks

class TestAngleLeakage(unittest.TestCase):
    """The client's own angle wording appearing verbatim in a message."""

    def setUp(self):
        self.config = _productive_config()

    def test_li1_leaks_the_founder_angle_wording(self):
        """'profitability visible on monday' is Productive's phrasing, not
        something to put in the prospect's mouth."""
        leaked = quality.angle_leakage(SIX_NOTES[0]["text"], self.config)
        self.assertTrue(leaked,
                        "li1 should leak at least one angle phrase")
        found = " ".join(leaked)
        self.assertIn("profitability", found)

    def test_a_note_without_angle_wording_does_not_leak(self):
        leaked = quality.angle_leakage(CANARY_NOTE, self.config)
        self.assertEqual(leaked, [])

    def test_empty_text_returns_no_leakage(self):
        self.assertEqual(quality.angle_leakage("", self.config), [])

    def test_no_config_returns_no_leakage(self):
        leaked = quality.angle_leakage(SIX_NOTES[0]["text"], None)
        self.assertEqual(leaked, [])

    def test_a_short_phrase_does_not_fire(self):
        """'profitability on monday' is only two distinctive words and
        must not trigger on common vocabulary."""
        config = {"angle_labels": {"test": "good morning"}}
        leaked = quality.angle_leakage("good morning, how are you today",
                                       config)
        self.assertEqual(leaked, [])

    def test_partial_match_is_not_a_leak(self):
        """Using one word from a phrase is not the same as using the
        phrase. 'profitability' alone is a topic, not a leak."""
        text = "how do you handle profitability at your company?"
        leaked = quality.angle_leakage(text, self.config)
        self.assertEqual(leaked, [])


class TestRepetitionAcrossRungs(unittest.TestCase):
    """Two steps for the same contact making the same point."""

    def test_the_six_notes_share_distinctive_words(self):
        """All six are about profitability visibility. The repetition
        check must fire."""
        collisions = quality.repetition_across_rungs(SIX_NOTES)
        self.assertTrue(collisions,
                        "six paraphrases of one idea must collide")

    def test_distinct_steps_do_not_collide(self):
        steps = [
            {"key": "li1", "text": "hi izabelle, let's connect about "
             "your delivery workflow"},
            {"key": "li2", "text": "quick question about how your team "
             "handles resource planning across offices"},
        ]
        collisions = quality.repetition_across_rungs(steps)
        self.assertEqual(collisions, [])

    def test_a_single_step_cannot_collide(self):
        collisions = quality.repetition_across_rungs([SIX_NOTES[0]])
        self.assertEqual(collisions, [])

    def test_empty_steps_return_no_collisions(self):
        self.assertEqual(quality.repetition_across_rungs([]), [])

    def test_collisions_are_sorted_by_shared_count_descending(self):
        collisions = quality.repetition_across_rungs(SIX_NOTES)
        counts = [c[2] for c in collisions]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_below_threshold_does_not_fire(self):
        """Four shared words is below the threshold of five."""
        steps = [
            {"key": "a", "text": "the quick brown fox jumps over "
             "the lazy dog"},
            {"key": "b", "text": "a quick brown fox was seen near "
             "the lazy dog"},
        ]
        collisions = quality.repetition_across_rungs(steps)
        self.assertEqual(collisions, [])


class TestUnsupportedThirdParty(unittest.TestCase):
    """Claims about populations the record cannot support."""

    def test_li4_has_an_unsupported_claim(self):
        """'many teams like yours have found...' is a claim with no
        referent."""
        found = quality.unsupported_third_party(SIX_NOTES[3]["text"])
        self.assertTrue(found,
                        "li4 should contain an unsupported third-party "
                        "claim")

    def test_a_note_without_third_party_claims_is_clean(self):
        found = quality.unsupported_third_party(CANARY_NOTE)
        self.assertEqual(found, [])

    def test_empty_text_returns_no_claims(self):
        self.assertEqual(quality.unsupported_third_party(""), [])

    def test_honest_copy_about_our_experience_is_not_caught(self):
        """'most operations leads we speak to' is honest copy about our
        own experience, not a claim about what others achieved."""
        text = ("most operations leads we speak to lose the best part "
                "of a day every month reconciling time")
        found = quality.unsupported_third_party(text)
        self.assertEqual(found, [])

    def test_several_teams_have_found_is_caught(self):
        text = ("several teams have found that visibility into "
                "utilisation can transform operations")
        found = quality.unsupported_third_party(text)
        self.assertTrue(found)

    def test_companies_we_work_with_have_seen_is_caught(self):
        text = ("companies we work with have seen a significant "
                "improvement in margin visibility")
        found = quality.unsupported_third_party(text)
        self.assertTrue(found)


# --------------------------------------------------------------- the gate

class TestTheGate(unittest.TestCase):
    """The combined gate: PASS or FAIL with named reasons."""

    def setUp(self):
        self.config = _productive_config()

    def test_li1_fails_for_angle_leakage(self):
        result = quality.gate(SIX_NOTES[0]["text"], self.config)
        self.assertEqual(result["verdict"], quality.FAIL)
        self.assertIn(quality.REASON_ANGLE_LEAKAGE, result["reasons"])

    def test_li4_fails_for_unsupported_claim(self):
        result = quality.gate(SIX_NOTES[3]["text"], self.config)
        self.assertEqual(result["verdict"], quality.FAIL)
        self.assertIn(quality.REASON_UNSUPPORTED_CLAIM,
                      result["reasons"])

    def test_li1_and_li4_fail_for_different_reasons(self):
        """Each check fails for its OWN reason, not a generic one."""
        r1 = quality.gate(SIX_NOTES[0]["text"], self.config)
        r4 = quality.gate(SIX_NOTES[3]["text"], self.config)
        self.assertIn(quality.REASON_ANGLE_LEAKAGE, r1["reasons"])
        self.assertNotIn(quality.REASON_UNSUPPORTED_CLAIM, r1["reasons"])
        self.assertIn(quality.REASON_UNSUPPORTED_CLAIM, r4["reasons"])
        self.assertNotIn(quality.REASON_ANGLE_LEAKAGE, r4["reasons"])

    def test_the_canary_note_passes(self):
        """A gate that fails good copy is worse than none."""
        result = quality.gate(CANARY_NOTE, self.config)
        self.assertEqual(result["verdict"], quality.PASS)
        self.assertEqual(result["reasons"], [])

    def test_repetition_fires_across_the_six_notes(self):
        """The full set of six notes must trigger the repetition check."""
        steps = SIX_NOTES
        result = quality.gate(SIX_NOTES[0]["text"], self.config,
                              steps=steps)
        self.assertIn(quality.REASON_REPETITION, result["reasons"])

    def test_gate_steps_returns_a_result_per_step(self):
        results = quality.gate_steps(SIX_NOTES, self.config)
        self.assertEqual(len(results), len(SIX_NOTES))
        for step in SIX_NOTES:
            self.assertIn(step["key"], results)

    def test_gate_steps_includes_repetition_for_every_step(self):
        """When repetition fires, every step in the set carries the
        reason, because the collision is a property of the set."""
        results = quality.gate_steps(SIX_NOTES, self.config)
        repeating = [k for k, v in results.items()
                     if quality.REASON_REPETITION in v["reasons"]]
        self.assertTrue(repeating,
                        "at least some steps should carry the repetition "
                        "reason")

    def test_empty_text_passes(self):
        result = quality.gate("", self.config)
        self.assertEqual(result["verdict"], quality.PASS)

    def test_no_config_passes(self):
        result = quality.gate(SIX_NOTES[0]["text"], None)
        self.assertEqual(result["verdict"], quality.PASS)


class TestTheTableOfSixNotes(unittest.TestCase):
    """The six notes against the reasons they failed.

    This doubles as the first measurement of this model on this task.
    """

    def setUp(self):
        self.config = _productive_config()
        self.results = quality.gate_steps(SIX_NOTES, self.config)

    def test_li1_fails(self):
        self.assertEqual(self.results["li1"]["verdict"], quality.FAIL)

    def test_li4_fails(self):
        self.assertEqual(self.results["li4"]["verdict"], quality.FAIL)

    def test_repetition_fires_somewhere(self):
        any_repetition = any(
            quality.REASON_REPETITION in v["reasons"]
            for v in self.results.values())
        self.assertTrue(any_repetition,
                        "the repetition check must fire across the set")

    def test_li1_reason_is_angle_leakage(self):
        self.assertIn(quality.REASON_ANGLE_LEAKAGE,
                      self.results["li1"]["reasons"])

    def test_li4_reason_is_unsupported_claim(self):
        self.assertIn(quality.REASON_UNSUPPORTED_CLAIM,
                      self.results["li4"]["reasons"])


# ----------------------------------------------- breaking each check

class TestBreakingEachCheck(unittest.TestCase):
    """Break each check and confirm the intended test fails for the
    intended reason. A red test is not proof by itself: the intended
    guard must be the one that fired."""

    def setUp(self):
        self.config = _productive_config()

    def test_removing_angle_words_makes_li1_pass_that_check(self):
        """Replace the leaked phrase. The angle_leakage check must no
        longer fire, proving it was the phrase that tripped it."""
        fixed = SIX_NOTES[0]["text"].replace(
            "profitability visible on monday", "keeping numbers current")
        leaked = quality.angle_leakage(fixed, self.config)
        self.assertEqual(leaked, [])

    def test_removing_third_party_phrase_makes_li4_pass_that_check(self):
        """Replace the unsupported claim. The unsupported_third_party
        check must no longer fire."""
        fixed = SIX_NOTES[3]["text"].replace(
            "many teams like yours have found that visibility into "
            "profitability can transform their operations",
            "clear visibility on numbers helps teams make better "
            "decisions")
        found = quality.unsupported_third_party(fixed)
        self.assertEqual(found, [])

    def test_making_steps_distinct_removes_repetition(self):
        """Replace the six notes with six genuinely different messages.
        The repetition check must no longer fire."""
        distinct = [
            {"key": "li1", "text": "hi izabelle, noticed your agency "
             "grew to forty people this year. let's connect"},
            {"key": "li2", "text": "quick question about how borealis "
             "handles client billing across entities"},
            {"key": "li3", "text": "the vienna office opening must "
             "have changed how you track project budgets"},
            {"key": "li4", "text": "curious whether month-end "
             "reconciliation still takes your team a full day"},
            {"key": "li5", "text": "just wondering if resourcing "
             "visibility across projects is something you have "
             "solved for"},
            {"key": "li6", "text": "no worries if now is not the "
             "right time, but happy to share how similar agencies "
             "approach this"},
        ]
        collisions = quality.repetition_across_rungs(distinct)
        self.assertEqual(collisions, [])


class TestGateDoesNotFailGoodCopy(unittest.TestCase):
    """A gate that fails good copy is worse than none. These are
    messages that should pass."""

    def setUp(self):
        self.config = _productive_config()

    def test_the_canary_passes(self):
        result = quality.gate(CANARY_NOTE, self.config)
        self.assertEqual(result["verdict"], quality.PASS)

    def test_a_question_about_their_workflow_passes(self):
        text = ("hi sam, how does your team currently handle resource "
                "planning across multiple projects? curious whether "
                "you have found a approach that works at your size")
        result = quality.gate(text, self.config)
        self.assertEqual(result["verdict"], quality.PASS)

    def test_a_short_followup_passes(self):
        text = ("hi sam, just circling back on my earlier note. "
                "would a quick call be useful, or is now not the "
                "right time?")
        result = quality.gate(text, self.config)
        self.assertEqual(result["verdict"], quality.PASS)

    def test_an_easy_no_passes(self):
        text = ("hi sam, last note from me. if this is not relevant "
                "right now, no worries at all. happy to leave it "
                "here")
        result = quality.gate(text, self.config)
        self.assertEqual(result["verdict"], quality.PASS)


if __name__ == "__main__":
    unittest.main()
