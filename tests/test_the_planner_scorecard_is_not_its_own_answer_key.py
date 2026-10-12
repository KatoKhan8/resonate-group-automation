"""The planner-only scorecard, and the five things it has to prove.

Written 2026-10-12 against `scripts/slack_planner_scorecard.py`, on top of
e8da7edf0. The step before this one produced a `tool` column that was n/a
on all 27 catalogue questions, for a sound reason: the catalogue emits
`channel: None`, `slackscope.resolve` refuses to guess a binding, and an
UNBOUND scope may call no tool. `test_the_unbound_scope_really_is_empty`
keeps that premise measured rather than remembered.

The danger in the replacement is different and worse. A scorecard that got
its SCOPE or its AVAILABLE TOOLS from the same table it grades against
would move whenever somebody edited the table and would always look
reasonable. So the separation is asserted here as behaviour:

    expectations    `slack_agent_replay.EXPECTED_TOOLS`, hand-written
    availability    `slackagenttools.for_scope`, the REGISTRY
    the plan        `slackconversation.keyword_plan`

`TestScopeIsNotComputedFromTheExpectations` substitutes an absurd
expectation function and proves the available-tool set does not budge.

Offline by construction: nothing here touches a model, a provider, Slack,
the network, or `work/`.
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import slackagenttools as agenttools                    # noqa: E402
from src import slackconversation as conversation                # noqa: E402
from src import slackscope                                       # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "scripts", "%s.py" % name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scorecard():
    return load("slack_planner_scorecard")


def replay():
    return load("slack_agent_replay")


INTERNAL = slackscope.Scope(slackscope.INTERNAL, source="test")
CLIENT = slackscope.Scope(slackscope.CLIENT, workspace="test-slug",
                          source="test")
UNBOUND = slackscope.Scope(slackscope.UNBOUND, source="test")

#: The audit's own phrasing. Not in the catalogue - see
#: `TestWhatTheCatalogueDoesNotMeasure` - but it is the case the whole
#: expectation table was written around, so the controls use it.
RUNNING = "what is running"


class TestControl1WrongToolFails(unittest.TestCase):
    """CONTROL 1. A plan that reads nothing able to answer is a FAIL."""

    def test_the_planner_fails_on_what_is_running(self):
        s = scorecard()
        row = s.score_one(RUNNING, INTERNAL, replay().expected_tools_for)
        self.assertEqual(row["planned"], ["monitors"],
                         "premise: the planner routes 'running' to monitors")
        self.assertEqual(
            row["mark"], s.FAIL,
            "'what is running' planned %r against expectation %r and scored "
            "%r" % (row["planned"], row["acceptable"], row["mark"]))
        self.assertIsNone(row["reason"], "a fail carries no n/a reason")

    def test_an_arbitrary_wrong_plan_fails_too(self):
        """Not just the one phrasing: the rule, with the plan supplied."""
        s = scorecard()

        def only_monitors(_question, _scope):
            return [{"name": "monitors"}]

        original = conversation.keyword_plan
        conversation.keyword_plan = only_monitors
        try:
            row = s.score_one("jesu puštene kampanje sada?", INTERNAL,
                              replay().expected_tools_for)
        finally:
            conversation.keyword_plan = original
        self.assertEqual(row["mark"], s.FAIL)
        self.assertEqual(row["planned"], ["monitors"])


class TestControl2RightToolPasses(unittest.TestCase):
    """CONTROL 2. The SAME question, with a plan that answers it, passes.

    Without this, control 1 is satisfied by a scorecard that fails
    everything.
    """

    def test_the_same_question_passes_with_a_correct_plan(self):
        s = scorecard()
        expected = replay().expected_tools_for
        _about, acceptable = expected(RUNNING)
        self.assertIn("sends_today", acceptable)

        original = conversation.keyword_plan
        conversation.keyword_plan = lambda q, sc: [{"name": "sends_today"}]
        try:
            row = s.score_one(RUNNING, INTERNAL, expected)
        finally:
            conversation.keyword_plan = original
        self.assertEqual(
            row["mark"], s.PASS,
            "the same question with an answering read scored %r"
            % (row["mark"],))

    def test_every_acceptable_read_passes_it(self):
        s = scorecard()
        expected = replay().expected_tools_for
        _about, acceptable = expected(RUNNING)
        original = conversation.keyword_plan
        try:
            for tool in acceptable:
                conversation.keyword_plan = (
                    lambda q, sc, t=tool: [{"name": t}])
                row = s.score_one(RUNNING, INTERNAL, expected)
                self.assertEqual(row["mark"], s.PASS,
                                 "%r should pass and scored %r"
                                 % (tool, row["mark"]))
        finally:
            conversation.keyword_plan = original


class TestControl3MissingScopeIsNeverAPass(unittest.TestCase):
    """CONTROL 3. An unknown or toolless scope cannot be shown as a pass."""

    def test_the_unbound_scope_really_is_empty(self):
        """THE PREMISE OF THE WHOLE EXERCISE, measured not remembered.

        If the REGISTRY ever grants an unbound channel a tool, the replay's
        all-n/a result has a different explanation and this file needs
        rereading.
        """
        self.assertEqual(
            agenttools.for_scope(UNBOUND), {},
            "an UNBOUND scope now has tools. The 2026-10-12 all-n/a replay "
            "result rested on it having none - reread this.")

    def test_every_unbound_row_is_na_and_none_is_pass(self):
        s = scorecard()
        expected = replay().expected_tools_for
        for question in (RUNNING, "jesu puštene kampanje sada?",
                         "jel imamo koji meeting još?"):
            row = s.score_one(question, UNBOUND, expected)
            self.assertEqual(row["mark"], s.NA,
                             "%r scored %r in an unbound scope"
                             % (question, row["mark"]))
            self.assertEqual(row["reason"], "unavailable_in_scope")

    def test_an_internal_only_expectation_in_a_client_scope_is_na(self):
        """`monitors` is internal-only. A client channel cannot call it, so
        the planner is not FAILED for not calling it - the row is
        unscoreable, and saying so is the point of the third reason."""
        s = scorecard()
        self.assertNotIn("monitors", agenttools.for_scope(CLIENT))
        row = s.score_one("are the monitors alive?", CLIENT,
                          replay().expected_tools_for)
        self.assertEqual(row["mark"], s.NA)
        self.assertEqual(row["reason"], "unavailable_in_scope")

    def test_no_expectation_is_na_with_its_own_reason(self):
        s = scorecard()
        row = s.score_one("what's the status on that?", INTERNAL,
                          replay().expected_tools_for)
        self.assertEqual(row["mark"], s.NA)
        self.assertEqual(row["reason"], "no_expectation")

    def test_the_three_na_reasons_are_distinct_and_never_pass(self):
        s = scorecard()
        expected = replay().expected_tools_for
        seen = set()
        for question, scope in ((RUNNING, UNBOUND),
                                ("what's the status on that?", INTERNAL),
                                ("are the monitors alive?", CLIENT)):
            row = s.score_one(question, scope, expected)
            self.assertEqual(row["mark"], s.NA)
            seen.add(row["reason"])
        self.assertEqual(seen, {"unavailable_in_scope", "no_expectation"})

        # planner_chose_nothing: the third reason, reachable and distinct.
        original = conversation.keyword_plan
        conversation.keyword_plan = lambda q, sc: []
        try:
            row = s.score_one(RUNNING, INTERNAL, expected)
        finally:
            conversation.keyword_plan = original
        self.assertEqual(row["mark"], s.NA)
        self.assertEqual(row["reason"], "planner_chose_nothing")


class TestControl4ExpectedToolsExistInTheRegistry(unittest.TestCase):
    """CONTROL 4. A name the model cannot choose is a row that never passes."""

    def test_every_expected_name_is_a_registry_key(self):
        for name, _asked, allowed in replay().EXPECTED_TOOLS:
            for tool in allowed:
                self.assertIn(
                    tool, agenttools.REGISTRY,
                    "expectation row %r names %r, which is not a tool the "
                    "model can choose" % (name, tool))

    def test_every_planned_name_is_a_registry_key(self):
        """And the other side of it: the planner cannot name a ghost either."""
        s = scorecard()
        _questions, rows = s.build(ROOT)
        for row in rows:
            for tool in row["planned"]:
                self.assertIn(tool, agenttools.REGISTRY,
                              "the planner chose %r, which is not in the "
                              "REGISTRY" % (tool,))


class TestControl5ScopeIsNotComputedFromTheExpectations(unittest.TestCase):
    """CONTROL 5. The answer key does not decide what was available.

    This is the one that makes the rest worth reading. If `for_scope` were
    fed from `EXPECTED_TOOLS`, every number here would move with the table
    and the scorecard would be grading itself.
    """

    def test_an_absurd_expectation_does_not_change_availability(self):
        s = scorecard()
        before = dict(agenttools.for_scope(INTERNAL))

        def absurd(_text):
            return (["invented"], ["credits"])

        row = s.score_one(RUNNING, INTERNAL, absurd)
        after = dict(agenttools.for_scope(INTERNAL))
        self.assertEqual(
            before, after,
            "the available-tool set moved when the expectation function "
            "changed. Scope is being computed from the answer key.")
        # The expectation DID change the verdict - proving the substitution
        # took effect and the test is not vacuous.
        self.assertEqual(row["acceptable"], ["credits"])
        self.assertEqual(row["mark"], s.FAIL)

    def test_availability_comes_from_the_registry_not_the_table(self):
        """The two sets are genuinely different, so the swap is detectable."""
        s = scorecard()
        from_registry = set(agenttools.for_scope(INTERNAL))
        from_table = set()
        for _name, _asked, allowed in replay().EXPECTED_TOOLS:
            from_table.update(allowed)
        self.assertNotEqual(
            from_registry, from_table,
            "the expectation table and the REGISTRY now list the same "
            "tools, so this control cannot tell them apart - reread it.")
        rows = [s.score_one(RUNNING, scope, replay().expected_tools_for)
                for scope in s.candidate_scopes()]
        for row in rows:
            scope = next(sc for sc in s.candidate_scopes()
                         if sc.kind == row["scope"])
            self.assertEqual(row["available_in_scope"],
                             len(agenttools.for_scope(scope)))

    def test_the_slug_does_not_change_the_plan(self):
        """A client Scope must name a workspace; the name is not a variable.

        The placeholder slug in the scorecard is therefore not a hidden
        input to the measurement, which is asserted rather than claimed.
        """
        s = scorecard()
        expected = replay().expected_tools_for
        one = s.score_one(RUNNING, slackscope.Scope(
            slackscope.CLIENT, workspace="slug-one", source="test"), expected)
        two = s.score_one(RUNNING, slackscope.Scope(
            slackscope.CLIENT, workspace="slug-two", source="test"), expected)
        self.assertEqual(one["planned"], two["planned"])
        self.assertEqual(one["mark"], two["mark"])
        self.assertEqual(one["available_in_scope"], two["available_in_scope"])


class TestThePerExpectationBreakdownDoesNotDouble_Count(unittest.TestCase):
    """The union is right for a verdict and wrong for a breakdown.

    Three catalogue rows match more than one expectation. Crediting the
    row's union pass to every expectation it matched made the lead gap look
    one third smaller than it is.
    """

    def test_the_per_expectation_walk_agrees_with_the_union(self):
        """THE DRIFT GUARD the scorecard's docstring promises.

        `per_expectation` re-runs the table's own regexes. If it ever found
        a different SET of names than `expected_tools_for` does, the
        breakdown would be describing a different question than the verdict.
        """
        s = scorecard()
        h = replay()
        questions, _rows = s.build(ROOT)
        self.assertTrue(questions)
        for question in questions:
            union_names, _acceptable = h.expected_tools_for(question)
            walk_names = [name for name, _allowed
                          in s.per_expectation(question, h.EXPECTED_TOOLS)]
            self.assertEqual(
                sorted(union_names), sorted(walk_names),
                "the two matchers disagree on %r: %r vs %r"
                % (question, union_names, walk_names))

    def test_a_multi_expectation_pass_is_not_credited_to_both(self):
        """The measured case, asserted.

        "...podijelimo one EU ili safe to send leadove po kampanjama"
        matches `campaign` AND `lead`. The planner read `sends_today`,
        which answers the campaign expectation and NOT the lead one.
        """
        s = scorecard()
        h = replay()
        rows = [r for r in s.build(ROOT)[1]
                if r["scope"] == slackscope.INTERNAL
                and len(r["about"]) > 1]
        self.assertGreater(len(rows), 0, "no multi-expectation row left; "
                                         "this test's premise is gone")
        split = [r for r in rows
                 if len(set((r.get("by_expectation") or {}).values())) > 1]
        self.assertTrue(
            split,
            "every multi-expectation row now scores the same for all of its "
            "expectations, so this control cannot tell a double-count from "
            "an honest count - reread it. rows=%r"
            % ([(r["about"], r.get("by_expectation")) for r in rows],))
        for row in split:
            detail = row["by_expectation"]
            self.assertEqual(row["mark"], s.PASS,
                             "premise: the union verdict passes")
            self.assertIn(s.FAIL, detail.values(),
                          "at least one expectation was NOT answered: %r"
                          % (detail,))

    def test_the_breakdown_total_is_not_inflated(self):
        """A per-expectation count can exceed the row count - that is
        correct, a row with two expectations contributes to two. What it
        may NOT do is report more passes than there are answered
        expectations."""
        s = scorecard()
        internal = [r for r in s.build(ROOT)[1]
                    if r["scope"] == slackscope.INTERNAL]
        passes = sum(1 for r in internal
                     for v in (r.get("by_expectation") or {}).values()
                     if v == s.PASS)
        union_passes = len([r for r in internal if r["mark"] == s.PASS])
        self.assertGreaterEqual(
            union_passes, 1, "premise: something passes")
        self.assertLessEqual(
            passes, sum(len(r["about"]) for r in internal),
            "more per-expectation passes than expectations matched")


class TestWhatTheCatalogueDoesNotMeasure(unittest.TestCase):
    """Stated as tests so a later reader cannot mistake absence for health."""

    def test_the_catalogue_carries_no_running_or_monitor_phrasing(self):
        s = scorecard()
        questions, _rows = s.build(ROOT)
        words = [w for ws, names in conversation.KEYWORD_PLAN
                 for w in ws if "monitors" in names]
        hits = [q for q in questions
                if any(w in q.lower() for w in words)]
        self.assertEqual(
            hits, [],
            "the catalogue now contains a monitors-keyword phrasing: %r. "
            "The 'running -> monitors' case became measurable here - good, "
            "and this test's premise is gone." % (hits,))

    def test_the_detector_would_fire_if_it_were_there(self):
        """THE POSITIVE CONTROL FOR THE TEST ABOVE.

        Zero hits is only meaningful if a hit is detectable. Without this,
        a typo in `words` would report a clean catalogue forever.
        """
        s = scorecard()
        row = s.score_one(RUNNING, INTERNAL, replay().expected_tools_for)
        self.assertIn("monitors", row["planned"])
        self.assertEqual(row["mark"], s.FAIL)

    def test_the_scorecard_scores_something_in_internal_scope(self):
        """And the whole exercise fails if this is still all n/a."""
        s = scorecard()
        _questions, rows = s.build(ROOT)
        internal = [r for r in rows
                    if r["scope"] == slackscope.INTERNAL]
        scored = [r for r in internal if r["mark"] in (s.PASS, s.FAIL)]
        self.assertGreater(
            len(scored), 10,
            "only %d of %d internal rows were scored. The replay's all-n/a "
            "result has not actually been replaced."
            % (len(scored), len(internal)))


if __name__ == "__main__":
    unittest.main()
