"""What the loop lets through, and what it answers only once.

The loop is thin on purpose - it resolves nothing and decides nothing - but
it owns two rules that no other module can test, and a mutation run found
that neither was covered:

1. **Which events are answered at all.** In a channel the agent answers a
   MENTION, with exactly one exception: `approve <id>` / `reject <id>`
   typed in an INTERNAL channel, so the operator need not @-mention a bot
   to approve something. Removing the internal-channel half of that check
   broke no test, and it would have made every `approve <id>` typed in a
   CLIENT channel into a live decision attempt.

2. **One answer per message, across a restart.** The idempotency set is
   rebuilt from the answer log, so neither a Slack redelivery nor a process
   restart can produce a second answer.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from src import slackscope                                      # noqa: E402
import slack_agent_loop as loop                                 # noqa: E402

INTERNAL = "C0INTERNALL"
CLIENT = "C0CLIENTTTT"
TICKET = "2026-09-21-abcd"


class LoopEnvironment(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-loop-")
        self._log = loop.LOG
        loop.LOG = os.path.join(self.tmp, "work", "slack-agent.jsonl")
        self._prev = {}
        for key, value in ((slackscope.INTERNAL_CHANNELS_VAR, INTERNAL),
                           (slackscope.OPS_CHANNEL_VAR, ""),
                           (slackscope.STATUS_CHANNEL_VAR, "")):
            self._prev[key] = os.environ.get(key)
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def tearDown(self):
        loop.LOG = self._log
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)


class OnlyMentionsAndOperatorDecisions(LoopEnvironment):

    def message(self, channel, text, kind="message"):
        return {"type": kind, "channel": channel, "text": text,
                "ts": "1.1", "user": "U0SOMEBODY"}

    def test_a_plain_message_in_a_channel_is_ignored(self):
        self.assertFalse(loop.handle(self.message(INTERNAL, "morning all"),
                                     set(), dry_run=True))

    def test_a_plain_message_in_a_client_channel_is_ignored(self):
        self.assertFalse(loop.handle(self.message(CLIENT, "any update?"),
                                     set(), dry_run=True))

    def test_a_decision_in_an_internal_channel_is_let_through(self):
        self.assertTrue(loop._is_operator_decision(
            self.message(INTERNAL, "approve %s" % TICKET)))

    def test_a_decision_in_a_CLIENT_channel_is_NOT_let_through(self):
        """The one that a mutation slipped past.

        `approve <id>` in a client channel must not reach the decision
        path at all. It is answered - by the mention path, which says where
        approvals happen - and never treated as a decision.
        """
        self.assertFalse(loop._is_operator_decision(
            self.message(CLIENT, "approve %s" % TICKET)))
        self.assertFalse(loop.handle(
            self.message(CLIENT, "approve %s" % TICKET), set(),
            dry_run=True))

    def test_a_decision_in_an_unknown_channel_is_not_let_through(self):
        self.assertFalse(loop._is_operator_decision(
            self.message("C0NOBODYKNOWS", "approve %s" % TICKET)))

    def test_an_ordinary_sentence_in_an_internal_channel_is_not_a_decision(
            self):
        for text in ("we should approve that batch",
                     "approve the pending campaign",
                     "I approve of this"):
            self.assertFalse(loop._is_operator_decision(
                self.message(INTERNAL, text)), text)

    def test_a_bot_message_is_ignored(self):
        event = self.message(INTERNAL, "approve %s" % TICKET)
        event["bot_id"] = "B123"
        self.assertFalse(loop.handle(event, set(), dry_run=True))

    def test_an_edit_or_join_subtype_is_ignored(self):
        event = self.message(INTERNAL, "approve %s" % TICKET)
        event["subtype"] = "message_changed"
        self.assertFalse(loop.handle(event, set(), dry_run=True))

    def test_a_direct_message_is_always_answered(self):
        event = self.message("D0DIRECT", "what is running?")
        event["channel_type"] = "im"
        self.assertTrue(loop.handle(event, set(), dry_run=True))


class OneAnswerPerMessage(LoopEnvironment):

    def test_an_empty_log_has_answered_nothing(self):
        self.assertEqual(loop.answered_already(), set())

    def test_an_answered_message_is_remembered_across_a_restart(self):
        loop.log({"kind": "answered", "message_id": "C1:111.222"})
        self.assertIn("C1:111.222", loop.answered_already())

    def test_a_question_row_alone_does_not_count_as_answered(self):
        """The log records the question BEFORE the answer is posted. If a
        question row counted, a crash between the two would silence that
        message forever rather than retry it."""
        loop.log({"kind": "question", "message_id": "C1:333.444"})
        self.assertNotIn("C1:333.444", loop.answered_already())

    def test_a_seen_message_is_not_answered_again(self):
        event = {"type": "app_mention", "channel": INTERNAL,
                 "text": "what is running?", "ts": "9.9", "user": "U1"}
        seen = {"%s:9.9" % INTERNAL}
        self.assertFalse(loop.handle(event, seen, dry_run=True))

    def test_a_corrupt_log_line_does_not_lose_the_set(self):
        loop.log({"kind": "answered", "message_id": "C1:111.222"})
        with open(loop.LOG, "a", encoding="utf-8") as handle:
            handle.write("{not json" + chr(10))
        loop.log({"kind": "answered", "message_id": "C1:555.666"})
        self.assertEqual(loop.answered_already(),
                         {"C1:111.222", "C1:555.666"})


if __name__ == "__main__":
    unittest.main()
