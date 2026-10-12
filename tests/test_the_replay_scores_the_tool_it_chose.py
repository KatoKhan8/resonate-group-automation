"""The third hole in the replay harness: nothing scored the TOOL.

Written 2026-10-12 against `scripts/slack_agent_replay.py`, master
2bf7b8a5. The 2026-09-23 audit listed three defects and master had fixed
two of them:

  1. `--catalogue` parsed the wrong bullet shape - FIXED, and
     `test_the_replay_harness_can_fail.py` holds the controls.
  2. The right number answering the wrong question - FIXED by the
     `subject` check, which reads the REPLY.
  3. ...and `subject` reads the reply only. `replay_one` has recorded
     `out["tools"]` since the harness was written and **no check has ever
     looked at it.** An answer that names campaigns, in the right
     language, at the right length, with every figure real, built out of a
     monitor-health readback, scores clean on all seven.

So this file is about the `tool` check: the question says what it is
about, `EXPECTED_TOOLS` says which reads could answer that, and a turn
that read none of them fails.

## WHAT MAKES THIS MORE THAN A RESTATEMENT OF THE PLANNER

`slackconversation.KEYWORD_PLAN` maps "running" to `monitors`. That line
is the proximate cause of the audit's headline defect. A check derived
from the planner would therefore call the defect a pass, and
`test_the_expectations_are_not_the_planners` asserts the table disagrees
with the planner on exactly that phrasing. **That assertion is the whole
argument for writing the expectations by hand.**

Every test here is offline: `score` is a pure function of a question and a
recorded result dict, so nothing below calls Slack, a model or a provider.
"""
import importlib.util
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import slackagenttools as agenttools                    # noqa: E402
from src import slackconversation as conversation                # noqa: E402


def harness():
    spec = importlib.util.spec_from_file_location(
        "slack_agent_replay",
        os.path.join(ROOT, "scripts", "slack_agent_replay.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The audit's own first row, verbatim from `docs/AGENT-REPLAY-2026-09-23.md`
#: section 5 item 3: "`what is running` answered with MONITOR HEALTH rather
#: than campaigns is invisible to every check here."
THE_AUDIT_QUESTION = "what is running"

#: A reply good enough to pass every other check, so that when `tool`
#: fails below it is the only thing that failed. Campaigns are named, the
#: language matches, the length is in range, no promise, no figure.
A_GOOD_LOOKING_REPLY = (
    "The campaigns are active and sending on their normal window. "
    "Nothing is paused right now.")


class TestTheToolCheckScoresTheAuditCase(unittest.TestCase):
    """The failure the first audit could not see, both directions."""

    def setUp(self):
        self.h = harness()

    def mark(self, question, tools, reply=A_GOOD_LOOKING_REPLY):
        """`score` for one recorded turn. Returns the whole mark dict."""
        result = {"reply": reply, "scope": None, "workspace": None,
                  "guard": None, "tools": list(tools)}
        marks = self.h.score({"text": question}, result)
        return marks, result

    def test_the_wrong_tool_fails(self):
        """THE POSITIVE CONTROL FOR A FAILURE.

        `monitors` answers "which watchers are beating and how long ago".
        It cannot answer what is running, and this is the one check in the
        harness that can say so.
        """
        marks, result = self.mark(THE_AUDIT_QUESTION, ["monitors"])
        self.assertEqual(
            marks["tool"], self.h.FAIL,
            "'what is running' read monitor health and the harness scored "
            "it %r. This is the 2026-09-23 defect and it is back."
            % (marks["tool"],))
        # AND IT SAYS WHAT WAS MISSED. A bare `fail` sends the next reader
        # to the transcript.
        self.assertIn("tool_expected", result)
        self.assertEqual(result["tool_expected"]["called"], ["monitors"])
        self.assertIn("campaign", result["tool_expected"]["about"])
        self.assertIn("sends_today", result["tool_expected"]["any_of"])

    def test_the_right_tool_passes(self):
        """THE POSITIVE CONTROL FOR A PASS.

        A check that refused every answer would also fail the case above
        and be worth nothing. Same question, a read that answers it.
        """
        for tool in ("sends_today", "activity_this_week", "campaign_detail",
                     "weekly_plan", "batch_state", "working_on"):
            marks, result = self.mark(THE_AUDIT_QUESTION, [tool])
            self.assertEqual(
                marks["tool"], self.h.PASS,
                "%r answers what is running and scored %r"
                % (tool, marks["tool"]))
            self.assertNotIn("tool_expected", result)

    def test_nothing_else_in_the_scorecard_caught_it(self):
        """WHY THE CHECK HAD TO BE ADDED, asserted rather than asserted of.

        The failing turn above passes or n/a's every OTHER check. If this
        ever stops being true, the `tool` column is no longer the only
        thing standing between this harness and the audit's defect, and
        whoever changed that should know.
        """
        marks, _ = self.mark(THE_AUDIT_QUESTION, ["monitors"])
        others = {c: m for c, m in marks.items() if c != "tool"}
        self.assertNotIn(
            self.h.FAIL, others.values(),
            "another check now fails this turn too: %r. Good news, but "
            "this test's premise is gone - reread it." % (others,))

    def test_a_turn_that_read_the_right_thing_and_said_it_badly(self):
        """`tool` passes and `subject` fails: different halves.

        The reply names nothing about campaigns; the read was correct.
        This is the case `tool` must NOT claim.
        """
        marks, _ = self.mark(THE_AUDIT_QUESTION, ["sends_today"],
                             reply="Everything looks fine at the moment.")
        self.assertEqual(marks["tool"], self.h.PASS)
        self.assertEqual(marks["subject"], self.h.FAIL)


class TestTheExpectationsAreNotThePlanners(unittest.TestCase):
    """The anti-tautology control. See the module docstring."""

    def setUp(self):
        self.h = harness()

    def test_the_planner_really_does_pick_monitors_for_running(self):
        """The premise: `KEYWORD_PLAN` maps "running" to `monitors`.

        If this ever stops being true the planner was fixed at the cause,
        which is better than scoring it - but then the next test is
        measuring nothing, so it has to be read again.
        """
        words = [w for words, names in conversation.KEYWORD_PLAN
                 for w in words if "monitors" in names]
        self.assertIn(
            "running", words,
            "`KEYWORD_PLAN` no longer routes 'running' to `monitors`. The "
            "planner may have been fixed at the cause; reread this file.")

    def test_the_table_disagrees_with_the_planner_there(self):
        """And this is why the table is written by hand.

        A check generated from `KEYWORD_PLAN` would accept `monitors` for
        "what is running" and report the defect as a pass.
        """
        _about, acceptable = self.h.expected_tools_for(THE_AUDIT_QUESTION)
        self.assertNotIn(
            "monitors", acceptable,
            "the expectation for 'what is running' now accepts `monitors`, "
            "which is the planner's own bug. The check agrees with the "
            "thing it exists to catch.")
        self.assertTrue(acceptable, "and it expects something")

    def test_a_question_actually_about_watchers_expects_monitors(self):
        """THE INVERSE CONTROL.

        A table that simply never expected `monitors` would pass the two
        tests above and be wrong. `monitors` is a real answer to a real
        question and this is it.
        """
        for question in ("are the monitors alive?",
                         "which watchers are beating?",
                         "is the heartbeat still going"):
            _about, acceptable = self.h.expected_tools_for(question)
            self.assertEqual(
                acceptable, ["monitors"],
                "%r should expect `monitors` and expects %r"
                % (question, acceptable))
        result = {"reply": "Every watcher beat within the last minute.",
                  "scope": None, "guard": None, "tools": ["monitors"]}
        marks = self.h.score({"text": "are the monitors alive?"}, result)
        self.assertEqual(marks["tool"], self.h.PASS)
        result = {"reply": "Every watcher beat within the last minute.",
                  "scope": None, "guard": None, "tools": ["sends_today"]}
        marks = self.h.score({"text": "are the monitors alive?"}, result)
        self.assertEqual(marks["tool"], self.h.FAIL)


class TestTheTableCannotBeUnsatisfiable(unittest.TestCase):
    """A typo in the table is a column that always fails."""

    def setUp(self):
        self.h = harness()

    def test_every_expected_tool_exists(self):
        """A misspelled read can never be called, so its row never passes.

        `provider_enrolled` is the trap here: it is a function in
        `slackagenttools` and NOT a key in `REGISTRY`, so the model cannot
        choose it and expecting it would be expecting the impossible.
        """
        for name, _asked, allowed in self.h.EXPECTED_TOOLS:
            for tool in allowed:
                self.assertIn(
                    tool, agenttools.REGISTRY,
                    "row %r expects %r, which is not a tool the model can "
                    "choose. `REGISTRY` is the authority, not this table."
                    % (name, tool))

    def test_every_row_compiles_and_matches_its_own_intent(self):
        for name, asked, _allowed in self.h.EXPECTED_TOOLS:
            re.compile(asked)                       # raises if malformed
            self.assertTrue(_allowed, "row %r expects nothing" % (name,))


class TestTheStatedLimits(unittest.TestCase):
    """`n/a` is used in two places on purpose. Both are asserted here so
    neither can quietly turn into a pass."""

    def setUp(self):
        self.h = harness()

    def test_no_expectation_is_na_and_never_pass(self):
        """"what's the status on that?" names nothing extractable.

        Scoring it `pass` would report a check that had not run as a check
        that had succeeded - the `terms` column of the last audit, 32 of 32
        `n/a` read as 32 passes.
        """
        result = {"reply": "It is moving along.", "scope": None,
                  "guard": None, "tools": ["working_on"]}
        marks = self.h.score({"text": "what's the status on that?"}, result)
        self.assertEqual(marks["tool"], self.h.NA)

    def test_a_turn_that_called_no_tool_is_na(self):
        """A pack-only answer and a gagged turn are not wrong CHOICES.

        This check measures which read was chosen, not whether one was.
        Scoring these `fail` would report the gag a second time in a column
        that is not about it.
        """
        result = {"reply": A_GOOD_LOOKING_REPLY, "scope": None,
                  "guard": None, "tools": []}
        marks = self.h.score({"text": THE_AUDIT_QUESTION}, result)
        self.assertEqual(marks["tool"], self.h.NA)


class TestItFiresOnTheRealCorpus(unittest.TestCase):
    """A check that is `n/a` on every real question is not a check.

    The `terms` column of the 2026-09-23 audit was 32 of 32 `n/a` and was
    read as 32 passes. This measures the new column against the real
    catalogue corpus BEFORE anybody reads a number out of it, so a table
    that matches nothing people actually ask is caught here and not in a
    report.
    """

    def setUp(self):
        self.h = harness()

    def test_most_catalogue_questions_get_an_expectation(self):
        rows = self.h.catalogue_questions(ROOT)
        self.assertGreater(len(rows), 20, "the catalogue parser found "
                                         "almost nothing; see "
                                         "test_the_replay_harness_can_fail")
        with_expectation = [r for r in rows
                            if self.h.expected_tools_for(r["text"])[1]]
        share = len(with_expectation) / float(len(rows))
        self.assertGreater(
            share, 0.5,
            "only %d of %d real phrasings (%.0f%%) get any expected tool, "
            "so the `tool` column would be mostly n/a and mean little. "
            "The catalogue is the authority on what gets asked, not this "
            "table." % (len(with_expectation), len(rows), 100 * share))


class TestTheCheckListCarriesIt(unittest.TestCase):

    def test_tool_is_scored_and_tallied(self):
        """In `CHECKS`, so the report prints a column and `failed` names it."""
        h = harness()
        self.assertIn("tool", h.CHECKS)

    def test_a_failing_tool_lands_in_failed(self):
        """`replay_one` builds `failed` from `CHECKS`; this is the path a
        report actually reads."""
        h = harness()
        result = {"reply": A_GOOD_LOOKING_REPLY, "scope": None,
                  "guard": None, "tools": ["monitors"]}
        marks = h.score({"text": THE_AUDIT_QUESTION}, result)
        failed = [c for c in h.CHECKS if marks.get(c) == h.FAIL]
        self.assertEqual(failed, ["tool"])


if __name__ == "__main__":
    unittest.main()
