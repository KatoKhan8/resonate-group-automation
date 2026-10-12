"""Three Croatian subjects the no-model fallback could not route, and the
collisions that a substring match makes possible.

Baseline 93e2d658b, measured by `scripts/slack_planner_scorecard.py`:
`meeting` 0 of 3, `lead` 0 of 3, `report` 0 of 2. All eight fell through to
the default triple `workspace_summary, batch_state, sends_today`, because
`KEYWORD_PLAN` carried no Croatian word for any of the three and the
catalogue is 24 of 27 Croatian.

After this change: `meeting` 3 of 3, `lead` 3 of 3, `report` 2 of 2, and
the internal-scope rate 9/18 -> 16/18. Zero rows went from pass to not-pass.

## THE RISK IS NOT THE MISSING WORD, IT IS THE EXTRA MATCH

`keyword_plan` tests `word in lowered`. No word boundary, no stemmer. So
every keyword added here also matches anything CONTAINING it, and the
second half of this file is the negative controls for that - most
importantly `lead` vs **leadership**, which is a room in this workspace.

## WHAT THIS FILE DOES NOT CLAIM

It measures `keyword_plan`, the fallback used when no model is configured.
The live loop runs WITH a model, so nothing here says what the agent would
really plan or say. `sastan` and `izvještaj` have zero catalogue hits and
are included on meaning alone - `TestWhatThisCorpusDoesNotMeasure` says so
rather than letting a green file imply otherwise.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import slackagenttools as agenttools                    # noqa: E402
from src import slackconversation as conversation                # noqa: E402
from src import slackscope                                       # noqa: E402

INTERNAL = slackscope.Scope(slackscope.INTERNAL, source="test")
CLIENT = slackscope.Scope(slackscope.CLIENT, workspace="test-slug",
                          source="test")
UNBOUND = slackscope.Scope(slackscope.UNBOUND, source="test")

#: The default the fallback lands on when nothing matches. Every baseline
#: failure below was exactly this.
DEFAULT_TRIPLE = ["workspace_summary", "batch_state", "sends_today"]


def plan(question, scope=INTERNAL):
    return [call["name"] for call in conversation.keyword_plan(question,
                                                               scope)]


class TestTheEightThatUsedToFallThrough(unittest.TestCase):
    """POSITIVE CONTROLS. The catalogue's own phrasings, verbatim.

    Each asserts the right tool is now planned AND that the default triple
    is gone - a question that returned the default plus the right tool
    would still be reading three things it was not asked for.
    """

    CASES = (
        # (phrasing, tool it must now plan)
        ("na koliko leadova smo poslali ... ovaj tjedan?", "lead_counts"),
        ("Jel bilo dobrih leadova danas na heyreach?", "lead_counts"),
        ("imamo 1.5 kontakata po domeni?", "lead_counts"),
        ("kakvo je bilo stanje s pozivima do sad?", "meetings_booked"),
        ("jel imamo koji meeting još?", "meetings_booked"),
        ("Na koliko smo [client] meetinga sada?", "meetings_booked"),
        ("možeš izvući reports?", "weekly_report"),
        ("monthly report?", "weekly_report"),
    )

    def test_each_one_now_plans_the_tool_that_answers_it(self):
        for question, tool in self.CASES:
            got = plan(question)
            self.assertIn(tool, got,
                          "%r should plan %r and planned %r"
                          % (question, tool, got))

    def test_none_of_them_falls_through_to_the_default_any_more(self):
        for question, _tool in self.CASES:
            self.assertNotEqual(
                plan(question), DEFAULT_TRIPLE,
                "%r still returns the fallback default" % (question,))

    def test_the_same_holds_in_a_client_channel(self):
        """All three tools are INTERNAL_CLIENT, so a client asking the same
        question gets the same read. Asserted, because availability is the
        REGISTRY's call and not this file's."""
        for question, tool in self.CASES:
            self.assertIn(tool, agenttools.for_scope(CLIENT))
            self.assertIn(tool, plan(question, CLIENT),
                          "%r in a client channel planned %r"
                          % (question, plan(question, CLIENT)))


class TestTheSubstringMatchIsWhatItIs(unittest.TestCase):
    """The semantics the keyword choices were made against.

    If `keyword_plan` ever grows word boundaries or a stemmer, `leadov`
    stops matching "leadova" and every positive control above breaks - so
    the premise is measured here rather than assumed.
    """

    def test_matching_is_a_plain_substring_with_no_word_boundary(self):
        self.assertIn("lead_counts", plan("xxleadovaxx"),
                      "an embedded substring no longer matches, so the "
                      "keyword choices in KEYWORD_PLAN need rereading")

    def test_there_is_no_stemmer(self):
        """"leadom" shares a stem with "leadova" and is NOT matched. This
        is a known miss, documented beside the keywords."""
        self.assertEqual(plan("imamo li jos leadom"), DEFAULT_TRIPLE)

    def test_a_superstring_keyword_would_be_redundant(self):
        """Why `meetinga` was dropped: `meeting` already matches it."""
        self.assertIn("meetings_booked", plan("koliko meetinga"))
        self.assertIn("meetings_booked", plan("koliko meetings"))
        self.assertIn("meetings_booked", plan("koliko meetinge"))


class TestTheNegativeControls(unittest.TestCase):
    """A broad word must not drag an unrelated question to the wrong read."""

    def test_a_broad_word_does_not_reroute_an_unrelated_question(self):
        """THE COLLISION THAT DECIDED `leadov` OVER `lead`.

        `resonate-leadership` is a room in this workspace. A bare `lead`
        substring would have made every mention of leadership ask for lead
        counts.
        """
        for question in ("ko je u leadership timu?",
                         "leadership sync je u 10",
                         "who is on the leadership call"):
            got = plan(question)
            self.assertNotIn(
                "lead_counts", got,
                "%r was routed to lead counts by a leadership mention: %r"
                % (question, got))

    def test_leadership_is_not_matched_by_the_keyword_we_chose(self):
        """The mechanism, not just the outcome."""
        words = [w for ws, names in conversation.KEYWORD_PLAN
                 for w in ws if "lead_counts" in names]
        self.assertIn("leadov", words)
        self.assertNotIn("lead", words,
                         "a bare `lead` keyword is back; it matches "
                         "'leadership'")
        for word in words:
            self.assertNotIn(word, "leadership",
                             "%r is a substring of 'leadership'" % (word,))

    def test_izvuci_is_not_a_report_keyword(self):
        """REJECTED CANDIDATE, pinned so it is not added back by reflex.

        "izvući" means "to pull out". `izvuci leadove` is a LEAD question,
        and routing it to the weekly report would be wrong. It is also
        unnecessary: `report` already matches the one catalogue phrasing
        that uses it.
        """
        words = [w for ws, names in conversation.KEYWORD_PLAN
                 for w in ws if "weekly_report" in names]
        for rejected in ("izvuci", "izvući", "izvu"):
            self.assertNotIn(rejected, words,
                             "%r routes `izvuci leadove` to the weekly "
                             "report" % (rejected,))
        got = plan("možeš izvući leadove za ovaj tjedan?")
        self.assertNotIn("weekly_report", got,
                         "'izvući leadove' asked for a report: %r" % (got,))
        self.assertIn("lead_counts", got,
                      "'izvući leadove' should still be a lead question")

    def test_the_report_keyword_still_answers_the_catalogue_phrasing(self):
        """And the positive half: dropping `izvuci` cost nothing."""
        self.assertIn("weekly_report", plan("možeš izvući reports?"))

    def test_an_unrelated_question_still_gets_the_default(self):
        """The new keywords did not make the fallback match everything."""
        for question in ("what's the status on that?",
                         "na kolko smo?",
                         "jesmo im ovo bili poslali?"):
            self.assertNotIn("meetings_booked", plan(question))
            self.assertNotIn("weekly_report", plan(question))
            self.assertNotIn("lead_counts", plan(question))

    def test_nothing_was_pushed_past_the_call_cap(self):
        """`MAX_CALLS_PER_TURN` is 5. Three new entries could in principle
        crowd the right tool out of a plan that matches many rows."""
        for question, tool in TestTheEightThatUsedToFallThrough.CASES:
            got = plan(question)
            self.assertLessEqual(len(got), agenttools.MAX_CALLS_PER_TURN)
            self.assertIn(tool, got[:agenttools.MAX_CALLS_PER_TURN])


class TestAnUnknownScopeStillCannotPass(unittest.TestCase):
    """Adding keywords must not give an unbound channel a read."""

    def test_the_unbound_scope_plans_nothing(self):
        self.assertEqual(agenttools.for_scope(UNBOUND), {})
        for question, _tool in TestTheEightThatUsedToFallThrough.CASES:
            self.assertEqual(
                plan(question, UNBOUND), [],
                "%r planned a tool in an unbound scope: %r"
                % (question, plan(question, UNBOUND)))

    def test_the_new_tools_are_not_unbound_callable(self):
        for tool in ("meetings_booked", "lead_counts", "weekly_report"):
            self.assertNotIn(tool, agenttools.for_scope(UNBOUND))


class TestTheAnswerKeyIsStillIndependent(unittest.TestCase):
    """The expectations must not have moved to meet the planner.

    This is the direction that matters. Making the PLANNER satisfy an
    independent spec is the fix; deriving the SPEC from the planner would
    make the measurement meaningless, and that is what this asserts cannot
    have happened.
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "slack_agent_replay",
            os.path.join(ROOT, "scripts", "slack_agent_replay.py"))
        self.replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.replay)

    def test_the_expectations_do_not_read_keyword_plan(self):
        """Emptied of every keyword, the planner plans the default - and the
        expectations are byte-for-byte the same answers. Behavioural proof
        that one does not feed the other."""
        before = {q: self.replay.expected_tools_for(q)
                  for q, _t in TestTheEightThatUsedToFallThrough.CASES}
        original = conversation.KEYWORD_PLAN
        conversation.KEYWORD_PLAN = ()
        try:
            self.assertEqual(plan("jel imamo koji meeting još?"),
                             DEFAULT_TRIPLE,
                             "premise: an empty table yields the default")
            after = {q: self.replay.expected_tools_for(q)
                     for q, _t in TestTheEightThatUsedToFallThrough.CASES}
        finally:
            conversation.KEYWORD_PLAN = original
        self.assertEqual(before, after,
                         "the expectation table changed when KEYWORD_PLAN "
                         "did. The answer key is derived from the planner.")

    def test_a_wrong_tool_still_fails_the_scorecard(self):
        """CONTROL. The scorecard did not become unable to fail.

        `what is running` is still expected to be about campaigns, and
        `monitors` still does not answer it - this change touched none of
        that.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "slack_planner_scorecard",
            os.path.join(ROOT, "scripts", "slack_planner_scorecard.py"))
        card = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(card)
        row = card.score_one("what is running", INTERNAL,
                             self.replay.expected_tools_for)
        self.assertEqual(row["planned"], ["monitors"])
        self.assertEqual(row["mark"], card.FAIL)


class TestWhatThisCorpusDoesNotMeasure(unittest.TestCase):
    """Said out loud, so a green file does not imply more than it proves."""

    def test_sastan_and_izvjestaj_have_no_catalogue_phrasing(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "slack_agent_replay",
            os.path.join(ROOT, "scripts", "slack_agent_replay.py"))
        replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(replay)
        questions = [r["text"].lower()
                     for r in replay.catalogue_questions(ROOT)]
        for word in ("sastan", "izvještaj"):
            self.assertEqual(
                [q for q in questions if word in q], [],
                "%r now appears in the catalogue, so it IS measured - "
                "good, and this test's premise is gone." % (word,))

    def test_but_they_do_route_when_they_appear(self):
        """THE POSITIVE CONTROL for the test above: unmeasured by the
        corpus is not the same as inert."""
        self.assertIn("meetings_booked", plan("kad je sastanak s klijentom?"))
        self.assertIn("weekly_report", plan("treba mi mjesečni izvještaj"))

    def test_the_reply_subject_is_still_unrouted(self):
        """A REMAINING GAP, measured and left alone on purpose.

        "can you please stop sending messages to people who have
        replied????" expects a reply read and still gets none - this patch
        covered meetings, leads and reports only. Filed, not fixed.
        """
        got = plan("can you please stop sending messages to people who "
                   "have replied????")
        self.assertNotIn("replies", got,
                         "the reply subject now routes - this gap is "
                         "closed and the report should say so")


if __name__ == "__main__":
    unittest.main()
