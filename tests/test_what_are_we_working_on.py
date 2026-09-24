""""What are we working on" — the same words, a different question per reader.

OPERATOR, 2026-09-23: "what are we working on" as a CLIENT answer.

## WHY IT IS NOT `next_actions` WITH A FILTER

`next_actions` already answers those words, for Resonate. It reads our own
handoff — the headline, what waits on the operator, the problem register,
campaigns awaiting an internal decision — and it is `_INTERNAL` twice over,
registered internal AND self-guarding.

Filtering it down for a client would have been wrong in two directions at
once. It leaks by omission-failure the day somebody adds a field, and it
answers a question the client did not ask: a client asking what we are
working on is not asking which branch is unmerged.

So `working_on` composes readbacks this channel could already have asked for
one at a time, and the tests below are mostly about what it REFUSES to say.
"""
import unittest
from unittest import mock

from src import slackagenttools as tools, slackscope


#: THIS MODULE ASSERTED AGAINST AMBIENT STATE AND ONLY PASSED IN COMPANY.
#:
#: Measured 2026-09-24: green in the full suite, **9 of 16 red when run on
#: its own**, because `tools.run(client(), "working_on")` read whatever
#: knowledge pack and records the process happened to have. In a full run a
#: neighbouring module had built them; alone there was nothing, so
#: `self.out` came back without `accounts` and seven tests raised KeyError.
#:
#: `tests/slackbase.py` is written about exactly this - "a test file that
#: isolates nothing passes when it runs after one that does" - and the
#: module it names, `test_slack_agent_numbers`, had the same shape.
#:
#: So the fixtures are pinned here. A test for a client-facing answer that
#: cannot run by itself is not evidence about the answer.
PACK = {
    "built_at": "2026-09-21T00:00:00Z",
    "workspaces": {
        "productive": {"provider_campaign_ids": [], "name": "Productive"},
        "contactout": {"provider_campaign_ids": [], "name": "ContactOut"},
    },
}

RECORDS = [
    {"id": "acme-test", "lane": "domains", "client": "productive",
     "company": "Acme", "domain": "acme.test", "state": "verified",
     "contacts": [{"key": "ada", "name": "Ada Tester", "email":
                   "ada@acme.test", "persona": "delivery", "selected": True}],
     "events": []},
]


class PinnedState(unittest.TestCase):
    """One fixture, shared, so every class below runs on its own."""

    def setUp(self):
        self._pack = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: PACK
        self.addCleanup(setattr, tools.knowledge, "pack", self._pack)
        self._records = mock.patch.object(
            tools, "_records",
            lambda slug: [r for r in RECORDS if r.get("client") == slug])
        self._records.start()
        self.addCleanup(self._records.stop)
        # The workspace-level witness is module-level and cached, so a
        # verdict left by another test decides this one's answer.
        tools._LEDGER_WITNESS.clear()
        self.addCleanup(tools._LEDGER_WITNESS.clear)


def client(slug="productive"):
    return slackscope.Scope(slackscope.CLIENT, workspace=slug, source="test",
                            slugs=("productive", "contactout"))


def internal():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


class ItAnswersTheThreeParts(PinnedState):

    def setUp(self):
        super().setUp()
        self.out = tools.run(client(), "working_on")

    def test_it_says_which_campaigns_are_running(self):
        self.assertIn("campaigns_running", self.out)

    def test_it_says_where_the_accounts_stand(self):
        from src import accountstate

        accounts = self.out["accounts"]
        for state in accountstate.ACCOUNT_STATES:
            self.assertIn(state, accounts)

    def test_it_says_what_is_waiting_on_them(self):
        self.assertIn("waiting_on_you", self.out)
        self.assertIn("accounts_awaiting_your_approval",
                      self.out["waiting_on_you"])

    def test_it_uses_the_operators_vocabulary_and_not_the_retired_one(self):
        """One vocabulary for the Monday post, the PDF, this answer and
        later the portal - the decision of 2026-09-23."""
        for retired in ("targeted", "contacted", "positive"):
            self.assertNotIn(retired, self.out["accounts"])

    def test_in_flight_is_a_sum_and_not_a_ninth_state(self):
        from src import accountstate

        accounts = self.out["accounts"]
        self.assertEqual(accounts["in_flight"],
                         sum(accounts[s] for s in accountstate.IN_FLIGHT))
        self.assertNotIn("in_flight", self.out["accounts_order"])

    def test_unanswerable_is_carried_and_never_folded_into_untouched(self):
        self.assertIn("unanswerable", self.out["accounts"])


class WhatItRefusesToSay(PinnedState):
    """The half that matters."""

    def setUp(self):
        super().setUp()
        self.out = tools.run(client(), "working_on")

    def test_our_own_backlog_is_a_COUNT_and_not_a_list(self):
        """A client can see there is work without being handed it to
        manage. The internal caller gets the rows."""
        self.assertIsInstance(self.out["waiting_on_us"], int)

    def test_the_internal_caller_does_get_the_rows(self):
        """The control. If `waiting_on_us` were always a count, the
        assertion above would pass and prove nothing about scoping."""
        out = tools.run(internal(), "working_on")
        self.assertIsInstance(out["waiting_on_us"], list)

    def test_it_never_reads_the_handoff_or_the_problem_register(self):
        """`next_actions`' four fields must not appear under any name."""
        for leaked in ("headline", "waiting_on_operator", "problem_register",
                       "campaigns_awaiting_decision"):
            self.assertNotIn(leaked, self.out)

    def test_it_states_no_plan_past_the_providers_horizon(self):
        self.assertIn("day after tomorrow", self.out["horizon_note"])

    def test_the_answer_survives_the_client_backstop(self):
        """The real test of a client-facing readback: everything in it has
        to pass `check_outbound`, or the turn discards the whole answer and
        the client gets the fallback instead of this."""
        scope = client()
        scope.check_outbound(tools.render([("working_on", None, self.out)]))


class ItIsScopedLikeEveryOtherClientTool(PinnedState):

    def test_it_is_offered_to_a_client(self):
        self.assertIn("working_on", tools.for_scope(client()))

    def test_it_is_offered_internally(self):
        self.assertIn("working_on", tools.for_scope(internal()))

    def test_an_unbound_channel_is_refused(self):
        scope = slackscope.Scope(slackscope.UNBOUND, source="test")
        with self.assertRaises(tools.ToolRefused):
            tools.run(scope, "working_on")

    def test_it_answers_about_the_channels_own_workspace_only(self):
        """A slug argument from another client is pinned back, the same way
        every other client tool pins it."""
        out = tools.run(client("productive"), "working_on", "contactout")
        self.assertEqual(out["workspace"], "productive")

    def test_next_actions_is_still_internal_only(self):
        """This increment must not have widened the thing it is replacing
        for one of the two readers."""
        self.assertNotIn("next_actions", tools.for_scope(client()))
        with self.assertRaises(tools.ToolRefused):
            tools.run(client(), "next_actions")


if __name__ == "__main__":
    unittest.main()
