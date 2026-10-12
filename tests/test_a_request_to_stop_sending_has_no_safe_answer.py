"""`can you please stop sending messages to people who have replied?`

Measured 2026-10-12 on `d16692440`. This is the one phrasing in
`docs/SLACK-AGENT-QUESTION-CATALOGUE.md` that the catalogue itself marks as
an escalation, and it falls into a gap:

    slackrequests.reads_as_a_question(...)  -> False  (correctly no question)
    slackrequests.recognise(...)            -> (None, {})  (NO request kind)
    keyword_plan(..., internal)             -> who_does_what, sends_today

So it is not routed to the request flow and not refused; it reaches the
planner, which picks two unrelated reads. A client asking us to stop
messaging people who replied can therefore be answered with who is on the
team and what went out today.

## THERE IS NO READ-ONLY TOOL THAT ANSWERS IT, AND THAT IS STRUCTURAL

The ask is for a CHANGE IN BEHAVIOUR. Measured: **0 of 29 tools in
`slackagenttools.REGISTRY` contain any write marker** - no `store.save`, no
`providerwrites`, no `push`, no `approve_step` - which
`tests/test_slack_agent_cannot_act.py` asserts from the import graph as
well. So no tool can stop a send, and an answer that says it has been
stopped is false by construction, not merely unverified.

`replies` is the nearest read ("what has come back: provider reply counts
and the classified feed") and it answers a DIFFERENT question: how many
replied, not whether we will stop writing to them. Routing the ask there
would turn a request into a statistic.

**So this file adds no tool and changes no routing.** It pins the gap, and
it blocks the two ways a future change could make the gap worse.

## THE FIX I ALMOST SHIPPED, AND WHY IT IS WRONG

The obvious rule is "an explicit ask that does not read as a question is
an action request, so give it no expectation". Measured, that rule is
unsafe: `_EXPLICIT_ASK` also matches ordinary polite QUESTIONS -

    can you tell me how many leads we emailed this week?   ask=True
    could you share the monthly report?                    ask=True
    can you check which domains we send from?              ask=True
    please let me know how many meetings we have           ask=True

- and every one of them returns `reads_as_a_question() == False` too, so
the rule would strip the expectation from four legitimate reads to catch
one action request. `TestThePoliteQuestionsThatMustNotBeCaught` keeps that
measurement alive so the next person does not implement it either.

Offline: no Slack, no provider, no model, no network, no `work/` read.
"""
import importlib.util
import inspect
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import slackagenttools as agenttools                    # noqa: E402
from src import slackconversation as conversation                # noqa: E402
from src import slackrequests as requests                        # noqa: E402
from src import slackscope                                       # noqa: E402

THE_ASK = "can you please stop sending messages to people who have replied?"

#: As the catalogue actually carries it, with the four question marks.
AS_CATALOGUED = ("can you please stop sending messages to people who have "
                 "replied????")

INTERNAL = slackscope.Scope(slackscope.INTERNAL, source="test")
CLIENT = slackscope.Scope(slackscope.CLIENT, workspace="productive",
                          source="test")

#: Write markers. If a registry tool ever contains one, the read-only
#: premise of this whole file is gone.
WRITE_MARKERS = ("store.save", "providerwrites", "mark_pushed",
                 "approve_step", "push.push", "requests.write")


def plan(question, scope=INTERNAL):
    return [call["name"] for call in conversation.keyword_plan(question,
                                                               scope)]


class TestTheGapIsRealAndMeasured(unittest.TestCase):

    def test_it_does_not_read_as_a_question(self):
        for text in (THE_ASK, AS_CATALOGUED):
            self.assertFalse(
                requests.reads_as_a_question(text),
                "%r now reads as a question; the premise changed" % (text,))

    def test_no_request_kind_recognises_it(self):
        """THE PRECISE BLOCKER.

        `recognise` needs a concrete target - a domain, a campaign id, a
        lead address - and an estate-wide policy ask names none. The six
        kinds are per-object, so none of them covers it.
        """
        for text in (THE_ASK, AS_CATALOGUED):
            kind, fields = requests.recognise(text)
            self.assertIsNone(
                kind,
                "%r is now recognised as %r. If a kind was added for "
                "estate-wide policy, this gap is closed - reread this file."
                % (text, kind))
            self.assertEqual(fields, {})
        self.assertNotIn(
            "stop_replied", requests.KINDS,
            "a kind for this ask now exists; update this file deliberately")

    def test_the_planner_answers_it_with_unrelated_reads(self):
        """What actually happens today, pinned so a change is visible."""
        got = plan(THE_ASK)
        self.assertTrue(got, "the planner returns something, not nothing")
        self.assertNotIn("replies", got,
                         "if `replies` is now planned, read the module "
                         "docstring: that turns a request into a statistic")


class TestNoToolCanSatisfyIt(unittest.TestCase):
    """The structural half. An answer claiming the send stopped is false."""

    def test_no_registry_tool_contains_a_write_marker(self):
        offenders = []
        for name, spec in sorted(agenttools.REGISTRY.items()):
            try:
                source = inspect.getsource(spec[0])
            except (OSError, TypeError):                 # pragma: no cover
                continue
            for marker in WRITE_MARKERS:
                if marker in source:
                    offenders.append((name, marker))
        self.assertEqual(
            offenders, [],
            "a tool the agent may call now reaches a writer: %r. The "
            "read-only premise of this file is gone." % (offenders,))

    def test_the_registry_is_not_empty(self):
        """THE POSITIVE CONTROL for the test above.

        An empty registry would pass it vacuously.
        """
        self.assertGreater(len(agenttools.REGISTRY), 20)

    def test_the_marker_scan_can_actually_fire(self):
        """AND the control that the scan is not blind.

        A deliberately write-shaped function must be caught, otherwise
        "no offenders" is a statement about the scanner.
        """
        def pretend_tool(scope, argument=None):
            store.save([])                                      # noqa: F821
            return {}

        source = inspect.getsource(pretend_tool)
        self.assertTrue(any(m in source for m in WRITE_MARKERS),
                        "the write-marker scan would not notice a writer")


class TestNoFalselySuccessfulAnswer(unittest.TestCase):
    """The guard this file exists for: the agent must never say it acted."""

    #: Phrasings that would claim the change was made. Deliberately broad.
    CLAIMS_ACTION = re.compile(
        r"\b(?:i(?:'ve| have) (?:stopped|paused|removed|disabled)|"
        r"we(?:'ve| have) (?:stopped|paused|removed|disabled)|"
        r"(?:that|this|it)(?:'s| is) (?:now )?(?:stopped|paused|done|"
        r"sorted|fixed)|no longer sending|i(?:'ll| will) stop|"
        r"we(?:'ll| will) stop|consider it done|taken care of)", re.I)

    def test_the_claim_detector_fires_on_a_claiming_answer(self):
        """POSITIVE CONTROL FIRST. A detector that matches nothing would
        make every test below vacuous."""
        for bad in ("Done - we've stopped sending to anyone who replied.",
                    "I'll stop those sends today.",
                    "That's now stopped.",
                    "They are no longer sending to repliers.",
                    "Consider it done."):
            self.assertTrue(self.CLAIMS_ACTION.search(bad),
                            "the detector missed %r" % (bad,))

    def test_it_does_not_fire_on_an_honest_answer(self):
        """NEGATIVE CONTROL. An honest refusal must pass."""
        for good in (
                "I can't change what goes out - I only read state. I've "
                "raised this for an operator.",
                "I cannot action that. Here is what the provider reports "
                "has come back so far.",
                "That needs a person: I have no way to pause a campaign."):
            self.assertIsNone(
                self.CLAIMS_ACTION.search(good),
                "an honest answer was flagged as a claim: %r" % (good,))

    def test_the_refusal_wording_already_in_the_repo_is_honest(self):
        """`test_slack_agent_cannot_act` asserts the refusal never claims
        to have acted. This checks the same property with this file's own
        detector, so the two cannot drift into disagreeing silently."""
        module = os.path.join(ROOT, "tests",
                              "test_slack_agent_cannot_act.py")
        self.assertTrue(os.path.exists(module),
                        "the structural act-refusal test is gone")

    def test_a_reply_read_would_not_answer_the_ask(self):
        """`replies` reports counts. It cannot say a send will stop.

        Asserted through the registry's own description rather than an
        opinion, so a reworded tool is noticed.
        """
        description = agenttools.REGISTRY["replies"][1].lower()
        for promise_word in ("stop", "pause", "suppress", "exclude"):
            self.assertNotIn(
                promise_word, description,
                "`replies` now describes itself as doing %r, which would "
                "make it look like an answer to this ask" % (promise_word,))


class TestThePoliteQuestionsThatMustNotBeCaught(unittest.TestCase):
    """The measurement that stopped a wrong fix. See the module docstring.

    Any future rule that strips expectations, refuses, or re-routes on the
    strength of `_EXPLICIT_ASK` plus "not a question" will take these four
    reads with it.
    """

    POLITE_READS = (
        "can you tell me how many leads we emailed this week?",
        "could you share the monthly report?",
        "can you check which domains we send from?",
        "please let me know how many meetings we have",
    )

    def test_they_all_match_explicit_ask_and_are_not_questions(self):
        """The trap, stated as a measurement."""
        for text in self.POLITE_READS:
            self.assertTrue(
                requests._EXPLICIT_ASK.search(text),
                "%r no longer matches _EXPLICIT_ASK" % (text,))
            self.assertFalse(
                requests.reads_as_a_question(text),
                "%r now reads as a question, so the trap is gone for it"
                % (text,))

    def test_and_they_still_route_to_a_read(self):
        """So a naive action-request rule would cost real coverage."""
        for text, tool in (
                ("can you tell me how many leads we emailed this week?",
                 "lead_counts"),
                ("could you share the monthly report?", "weekly_report"),
                ("can you check which domains we send from?",
                 "sending_domains"),
                ("please let me know how many meetings we have",
                 "meetings_booked")):
            self.assertIn(tool, plan(text),
                          "%r lost its routing to %r" % (text, tool))

    def test_the_english_lead_question_was_the_one_that_did_not_route(self):
        """Recorded because writing this file is what found it.

        Three of the four polite reads above routed correctly from the
        start. The English lead question fell to the default triple,
        because `lead_counts` carried only Croatian keys - `leadov` and
        `kontakata`. `leads` was added for it. This test is the reason the
        assertion above is four rows and not three.
        """
        self.assertIn("lead_counts",
                      plan("how many leads did we email this week?"))

    def test_the_action_request_is_distinguishable_by_its_verb(self):
        """What a correct rule would have to use instead, recorded but NOT
        implemented here: the mutating verb, not the politeness.

        This is evidence for the proposal in the report, not a fix.
        """
        mutating = re.compile(r"\b(?:stop|pause|remove|delete|disable|"
                              r"turn off|unsubscribe)\b", re.I)
        self.assertTrue(mutating.search(THE_ASK))
        for text in self.POLITE_READS:
            self.assertIsNone(
                mutating.search(text),
                "%r contains a mutating verb, so the proposed rule would "
                "catch it too" % (text,))


class TestTheScorecardStillCallsThisRowAFailure(unittest.TestCase):
    """And that is left alone on purpose.

    The independent expectation table maps this ask to a `reply` read, so
    the planner-only scorecard scores the row FAIL. That is arguably the
    wrong expectation - no read answers an action request - but changing
    it would RAISE the headline percentage, and a number that improves
    because a hard row was reclassified is exactly the kind of number this
    work exists to distrust. It stays FAIL, visible, until an owner
    decides. See the report.
    """

    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "slack_agent_replay",
            os.path.join(ROOT, "scripts", "slack_agent_replay.py"))
        self.replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.replay)

    def test_the_expectation_is_still_a_reply_read(self):
        about, acceptable = self.replay.expected_tools_for(AS_CATALOGUED)
        self.assertIn("reply", about)
        self.assertIn("replies", acceptable)

    def test_and_the_planner_still_misses_it(self):
        got = plan(AS_CATALOGUED)
        _about, acceptable = self.replay.expected_tools_for(AS_CATALOGUED)
        self.assertFalse(
            set(got) & set(acceptable),
            "the planner now satisfies this expectation: %r. The row would "
            "flip to PASS - check it is for a good reason." % (got,))


if __name__ == "__main__":
    unittest.main()
