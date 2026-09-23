"""The 07:15 briefing, which was over its own call budget and untested.

OPERATOR, increment 4: "briefing additions".

## THE ADDITION THAT HAD TO COME FIRST WAS A SUBTRACTION OF A BUG

`scripts/slack_agent_briefing.py` asked `tools.run_all` for SIX readbacks
against `MAX_CALLS_PER_TURN = 5`. The sixth was `monitors`, so every single
morning the briefing rendered

    monitors -> {"_error": "dropped: over the 5-call budget"}

into the model's material. `monitors` is "which watchers are beating and how
long ago" - a dead watcher is the most briefing-shaped fact there is, and the
briefing has never once carried one. On the day this was found it would have
reported `bison-491` failing its inventory read a hundred times, and a
follow-up loop that had never been started.

**And it meant "briefing additions" was impossible as stated**: anything
appended to that list would have been dropped the same way, and the
increment would have looked done while changing nothing.

## WHY THE BUDGET WAS NOT SIMPLY RAISED

`MAX_CALLS_PER_TURN` is an anti-injection budget on a conversational TURN -
a message can drive an agent into a loop, and the call list there is chosen
by a model reading text a prospect wrote. Raising it would have removed the
protection from the one path that needs it.

A scheduled job is the other thing: its call list is a literal in this
repository and nothing anyone says changes it. So `run_scheduled` exists,
takes no budget, and **refuses any scope but INTERNAL** - which is the whole
safety argument, and is the first thing asserted below.

## AND THE BRIEFING HAD NO TESTS AT ALL

`grep -rn slack_agent_briefing` over the tree returned the script and four
documents. No test imported it. So the DST arithmetic, the late cutoff, the
idempotence, the destination fallback and the no-model path were all
unasserted, which is how six-into-five survived.
"""
import importlib.util
import os
import unittest

from src import slackagenttools as tools, slackscope

BRIEFING = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "slack_agent_briefing.py")


def briefing_module():
    spec = importlib.util.spec_from_file_location("_briefing", BRIEFING)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheScheduledRunnerIsInternalOnly(unittest.TestCase):
    """The entire reason it is allowed to have no budget."""

    def test_a_client_scope_is_refused(self):
        scope = slackscope.Scope(slackscope.CLIENT, workspace="productive",
                                 source="test")
        with self.assertRaises(tools.ToolRefused):
            tools.run_scheduled(scope, [{"name": "timeline"}])

    def test_an_unbound_scope_is_refused(self):
        scope = slackscope.Scope(slackscope.UNBOUND, source="test")
        with self.assertRaises(tools.ToolRefused):
            tools.run_scheduled(scope, [{"name": "timeline"}])

    def test_the_refusal_names_the_budgeted_path_to_use_instead(self):
        scope = slackscope.Scope(slackscope.CLIENT, workspace="productive",
                                 source="test")
        try:
            tools.run_scheduled(scope, [{"name": "timeline"}])
        except tools.ToolRefused as exc:
            self.assertIn("run_all", str(exc))
        else:                                           # pragma: no cover
            self.fail("a client scope was not refused")

    def test_internal_is_allowed_and_nothing_is_dropped(self):
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        calls = [{"name": "timeline"} for _ in range(9)]
        out = tools.run_scheduled(scope, calls)
        self.assertEqual(len(out), 9)
        for _name, _arg, result in out:
            self.assertNotIn("budget", str((result or {}).get("_error") or ""))

    def test_run_all_still_has_its_budget(self):
        """The guard this did NOT weaken. A turn is still capped."""
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        calls = [{"name": "timeline"} for _ in range(8)]
        out = tools.run_all(scope, calls)
        dropped = [r for _n, _a, r in out
                   if "budget" in str((r or {}).get("_error") or "")]
        self.assertEqual(len(dropped), 8 - tools.MAX_CALLS_PER_TURN)


class TheBriefingAsksForEverythingItNeeds(unittest.TestCase):

    def setUp(self):
        self.module = briefing_module()

    def test_it_no_longer_uses_the_turn_budget(self):
        with open(BRIEFING, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("run_scheduled", source)
        self.assertNotIn("tools.run_all", source)

    def test_nothing_it_asks_for_is_dropped(self):
        """THE REGRESSION TEST FOR THE WHOLE BUG. Not 'it asks for eight' -
        that would pass if the ninth were added and silently dropped."""
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        _scope, results = self.module.gather(scope)
        for name, _argument, value in results:
            error = str((value or {}).get("_error") or "") \
                if isinstance(value, dict) else ""
            self.assertNotIn("budget", error,
                             "%s was dropped by a call budget" % name)

    def test_monitors_is_actually_read(self):
        """It was asked for from the beginning and never arrived."""
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        _scope, results = self.module.gather(scope)
        got = {name for name, _a, _v in results}
        self.assertIn("monitors", got)
        value = dict((n, v) for n, _a, v in results)["monitors"]
        self.assertNotIn("_error", value or {})

    def test_the_operators_bounce_check_is_in_the_material(self):
        """`SLACK-AGENT-EXPECTATIONS.md` section 4 item 2: lead with any
        sender over 1.5% bounce. That needs `sender_roster`, which was a
        registered tool the whole time and was never asked for."""
        scope = slackscope.Scope(slackscope.INTERNAL, source="test")
        _scope, results = self.module.gather(scope)
        self.assertIn("sender_roster", {n for n, _a, _v in results})

    def test_the_threshold_is_a_percentage_not_a_fraction(self):
        """`sender_roster` reports `bounce_rate_percent`, so 1.5 means 1.5%.
        A threshold of 0.015 compared against that flags every sender."""
        self.assertEqual(self.module.BOUNCE_ALERT_PERCENT, 1.5)


class ThePromptDoesNotContradictItself(unittest.TestCase):

    def setUp(self):
        self.prompt = briefing_module().BRIEFING_PROMPT

    def test_it_does_not_demand_three_sentences_and_then_list_more(self):
        """It said "EXACTLY THREE SENTENCES, in this order" and then listed
        four numbered items. A rule the material cannot satisfy is a rule
        the model has to pick which half of to break."""
        self.assertNotIn("EXACTLY THREE SENTENCES", self.prompt)

    def test_every_numbered_item_is_covered_by_a_gathered_readback(self):
        """A prompt item with no readback behind it invites invention, and
        the first rule of this prompt is never to state a number that is not
        in the material."""
        for needed in ("promises", "monitors", "sender_roster"):
            self.assertIn(needed, self.prompt)

    def test_a_failed_read_is_not_an_empty_result(self):
        self.assertIn("_error", self.prompt)


class TheNoModelPathAnswersTheWholeQuestion(unittest.TestCase):
    """`_plain` gathered six readbacks and rendered three."""

    def setUp(self):
        self.module = briefing_module()

    def rows(self, **over):
        base = {
            "next_actions": {"headline": "batch 1 is sending",
                             "waiting_on_operator": []},
            "sends_today": {"campaigns": [{"campaign_id": "491",
                                           "emails_sent": 272}]},
            "batch_state": {},
            "meetings_booked": {},
            "promises": {"open": [{"what": "send the Croatian correction"}]},
            "monitors": {"monitors": [
                {"watcher": "bison-491", "age_seconds": 30},
                {"watcher": "slack-followup", "age_seconds": 99999},
                {"watcher": "notify-deliver", "age_seconds": None}]},
            "sender_roster": {"senders": [
                {"name": "Sender One", "bounce_rate_percent": 0.4},
                {"name": "Sender Two", "bounce_rate_percent": 1.5},
                {"name": "Sender Three", "bounce_rate_percent": 3.2}]},
            "change_requests": {"change_requests_awaiting_operator": []},
        }
        base.update(over)
        return [(name, None, value) for name, value in base.items()]

    def test_an_open_promise_is_reported(self):
        out = self.module._plain(self.rows())
        self.assertIn("Croatian correction", out)

    def test_a_quiet_watcher_is_named(self):
        out = self.module._plain(self.rows())
        self.assertIn("slack-followup", out)

    def test_an_undated_beat_counts_as_quiet(self):
        """`watchsink.stale`'s rule: the question is whether silence may be
        read as unchanged, and for an unreadable beat the answer is no."""
        out = self.module._plain(self.rows())
        self.assertIn("notify-deliver", out)

    def test_a_beating_watcher_is_not_named(self):
        out = self.module._plain(self.rows())
        self.assertNotIn("bison-491", out)

    def test_the_bounce_threshold_is_inclusive_at_one_point_five(self):
        """The operator said 1.5, "early enough to matter, not at 2%". A
        sender exactly at the threshold is the one the rule is about."""
        out = self.module._plain(self.rows())
        self.assertIn("Sender Two", out)
        self.assertIn("Sender Three", out)
        self.assertNotIn("Sender One", out)

    def test_the_percentage_is_not_multiplied_twice(self):
        out = self.module._plain(self.rows())
        self.assertIn("3.20%", out)
        self.assertNotIn("320", out)

    def test_a_failed_readback_is_named_rather_than_read_as_quiet(self):
        """A morning where `monitors` could not be read must not look like a
        morning where every watcher was healthy."""
        out = self.module._plain(
            self.rows(monitors={"_error": "monitors failed: OSError"}))
        self.assertIn("Could not be read", out)
        self.assertIn("monitors", out)


if __name__ == "__main__":
    unittest.main()
