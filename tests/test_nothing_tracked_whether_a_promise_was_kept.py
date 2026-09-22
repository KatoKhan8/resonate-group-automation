"""Fifty-three promises in ten days, and nothing checking any of them.

`docs/SLACK-AGENT-EXPECTATIONS.md`, section 5, on the gap the exercise
found:

    Fifty-three promise-shaped messages in ten days, and **no system
    anywhere tracks whether any of them was kept.** The domain-list promise
    on Monday was kept in 119 minutes with the wrong artefact, and the only
    reason anybody knows is that the client replied.

    A `promises` readback ... is the highest-value thing this history
    suggests building, and it is not on the tool list yet because it needs
    a decision about what counts as delivery.

OPERATOR, 2026-09-22 — the decision: *delivered when, in the same thread
and after it, an internal user posts a file, a link, a list (3+ lines) or
an explicit delivery word (sent / poslano / evo / done / here you go), or
when the system posts a matching artifact. Otherwise it is open once its
stated time has passed, and appears in the 07:15 briefing internally only.
Clients never see the promise scan.*

The properties that make it a scan people keep reading:

1. **`undated` is not `open`.** Calling a promise late when nobody said
   when is how a monitor teaches its readers to skip it.
2. **"danas ili sutra" is judged on sutra.** One false alarm costs more
   attention than one missed promise.
3. **An empty history is not a clean week.**
4. **A client never reaches it** — not by filtering, but because there is
   no scope that can call it.
"""
import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackagenttools as tools                         # noqa: E402
from src import slackpromises as promises, slackscope            # noqa: E402

US, THEM = "U0RESONATE1", "U0CLIENTAAA"
NOW = 1790000000.0
DAY = 86400.0


def msg(ts, text, user=US, channel="C1", thread=None, **over):
    row = {"_channel": channel, "_channel_name": "outbound",
           "ts": "%.6f" % ts, "user": user, "text": text}
    if thread is not None:
        row["thread_ts"] = "%.6f" % thread
    row.update(over)
    return row


def scan(rows, now=NOW):
    return promises.scan(rows, internal_users=[US], now=now)


# ================================ 1. WHAT IS A PROMISE

class AnAcknowledgementIsNotACommitment(unittest.TestCase):

    def test_the_real_promise_from_the_history_is_recognised(self):
        """The one the expectations doc is written about."""
        found = scan([msg(NOW - 2 * DAY,
                          "moze, posaljemo najnoviju listu danas ili sutra")])
        self.assertEqual(len(found), 1)

    def test_english_and_croatian_commitments_both_count(self):
        for text in ("I'll send the list tomorrow",
                     "we'll put together the numbers today",
                     "poslat cu ti to danas",
                     "javim ti sutra",
                     "pripremit cu izvjestaj"):
            self.assertEqual(len(scan([msg(NOW - DAY, text)])), 1, text)

    def test_a_question_containing_the_verb_is_not_a_promise(self):
        for text in ("mozes poslati popis?",
                     "can you send the list?",
                     "could you share the numbers today?"):
            self.assertEqual(scan([msg(NOW - DAY, text)]), [], text)

    def test_an_acknowledgement_is_deliberately_not_one(self):
        """"momenat, gledam" and "on it" owe nobody an artefact, and a
        briefing full of them is a briefing people stop reading."""
        for text in ("momenat, gledam", "on it, dodala task!", "ok",
                     "heeej, you're back!"):
            self.assertEqual(scan([msg(NOW - DAY, text)]), [], text)

    def test_a_client_promising_us_something_is_not_our_promise(self):
        self.assertEqual(
            scan([msg(NOW - DAY, "I'll send you the brief tomorrow",
                      user=THEM)]), [])

    def test_the_agents_own_messages_are_not_promises(self):
        """Carrying an internal user id as well, so it is `_is_system` that
        excludes it and not the user filter getting there first."""
        self.assertEqual(
            scan([msg(NOW - DAY, "I'll send the list tomorrow",
                      bot_id="B1")]), [])
        self.assertEqual(
            scan([msg(NOW - DAY, "I'll send the list tomorrow",
                      subtype="bot_message")]), [])

    def test_a_promise_older_than_the_window_is_history(self):
        self.assertEqual(
            scan([msg(NOW - 40 * DAY, "poslat cu ti to danas")]), [])


# ================================ 2. THE OPERATOR'S FOUR DELIVERY SHAPES

class DeliveryIsOneOfFourThingsAndItSaysWhich(unittest.TestCase):

    def promise(self):
        return msg(NOW - 2 * DAY, "poslat cu ti popis danas")

    def delivered_by(self, reply):
        found = scan([self.promise(), reply])
        self.assertEqual(len(found), 1)
        return found[0]

    def reply(self, text="", **over):
        return msg(NOW - 2 * DAY + 3600, text,
                   thread=NOW - 2 * DAY, **over)

    def test_a_file(self):
        row = self.delivered_by(self.reply(files=[{"id": "F1"}]))
        self.assertEqual(row["status"], promises.DELIVERED)
        self.assertEqual(row["evidence"], "a file")

    def test_a_link(self):
        row = self.delivered_by(self.reply("<https://example.test/list|x>"))
        self.assertEqual(row["evidence"], "a link")

    def test_a_list_of_three_or_more_lines(self):
        row = self.delivered_by(self.reply("one\ntwo\nthree"))
        self.assertEqual(row["evidence"], "a list")
        two = scan([self.promise(), self.reply("one\ntwo")])
        self.assertEqual(two[0]["status"], promises.OPEN)

    def test_each_explicit_delivery_word(self):
        for word in ("sent", "poslano", "evo", "done", "here you go"):
            row = self.delivered_by(self.reply(word))
            self.assertEqual(row["evidence"], "an explicit delivery word",
                             word)

    def test_the_system_posting_the_artifact_counts(self):
        row = self.delivered_by(
            self.reply("a\nb\nc", user=None, bot_id="B1"))
        self.assertEqual(row["delivered_by"], "the system")

    def test_the_other_party_posting_a_link_does_not(self):
        """A client posting something in the thread is not us keeping a
        promise."""
        found = scan([self.promise(),
                      self.reply("https://example.test/x", user=THEM)])
        self.assertEqual(found[0]["status"], promises.OPEN)

    def test_the_evidence_is_named_rather_than_collapsed(self):
        """The domain-list promise was "kept" with the wrong artefact. A
        scan that only says `delivered` would say it about that too."""
        row = self.delivered_by(self.reply(files=[{"id": "F1"}]))
        self.assertIn("evidence", row)
        self.assertIn("minutes_taken", row)

    def test_something_posted_before_the_promise_does_not_deliver_it(self):
        found = scan([msg(NOW - 2 * DAY - 60, "evo", thread=NOW - 2 * DAY),
                      self.promise()])
        self.assertEqual(found[0]["status"], promises.OPEN)

    def test_delivery_in_another_thread_does_not_count(self):
        """The operator's definition, taken literally: the same thread."""
        found = scan([self.promise(),
                      msg(NOW - 2 * DAY + 3600, "evo", channel="C1",
                          thread=NOW - 5 * DAY)])
        self.assertEqual(found[0]["status"], promises.OPEN)


# ================================ 3. OPEN, DUE, UNDATED

class UndatedIsNotLate(unittest.TestCase):

    def test_a_promise_with_no_time_is_never_called_late(self):
        row = scan([msg(NOW - 5 * DAY, "javim ti")])[0]
        self.assertEqual(row["status"], promises.UNDATED)
        self.assertIn("not late", row["note"])
        self.assertNotIn("due_by", row)

    def test_a_stated_time_that_has_passed_is_open(self):
        row = scan([msg(NOW - 3 * DAY, "poslat cu ti to danas")])[0]
        self.assertEqual(row["status"], promises.OPEN)
        self.assertIn("due_by", row)

    def test_a_stated_time_still_ahead_is_due_and_not_open(self):
        row = scan([msg(NOW - 600, "I'll send the list tomorrow")])[0]
        self.assertEqual(row["status"], promises.DUE)

    def test_danas_ili_sutra_is_judged_on_sutra(self):
        """One false alarm costs more attention than one missed promise."""
        text = "posaljemo najnoviju listu danas ili sutra"
        self.assertEqual(promises.deadline_days(text), 1)
        # Thirty hours later: today has passed, tomorrow has not.
        row = scan([msg(NOW - 30 * 3600, text)])[0]
        self.assertEqual(row["status"], promises.DUE)

    def test_the_week_shapes_are_read(self):
        self.assertEqual(promises.deadline_days("do kraja tjedna"), 5)
        self.assertEqual(promises.deadline_days("next week"), 7)
        self.assertIsNone(promises.deadline_days("poslat cu ti"))


# ================================ 4. AN EMPTY FILE IS NOT A CLEAN WEEK

class TheHonestEmptyCase(unittest.TestCase):

    def test_no_history_pulled_says_so(self):
        out = promises.summary([], history_found=False)
        self.assertIn("not a clean week", out["note"])
        self.assertIn("slack_history.py --read", out["note"])

    def test_history_with_no_promises_says_that_instead(self):
        out = promises.summary([], history_found=True)
        self.assertIn("no promise-shaped message", out["note"])

    def test_the_summary_leads_with_the_open_ones(self):
        found = scan([msg(NOW - 3 * DAY, "poslat cu ti to danas"),
                      msg(NOW - 5 * DAY, "javim ti", channel="C2")])
        out = promises.summary(found)
        self.assertEqual(len(out["open"]), 1)
        self.assertEqual(out["by_status"][promises.UNDATED], 1)


# ================================ 5. A CLIENT CANNOT REACH IT

class ClientsNeverSeeThePromiseScan(unittest.TestCase):

    def client(self):
        return slackscope.Scope(slackscope.CLIENT, workspace="alpha",
                                source="test")

    def test_it_is_not_on_a_client_channels_tool_list(self):
        self.assertNotIn("promises", tools.for_scope(self.client()))
        self.assertIn("promises", tools.for_scope(
            slackscope.Scope(slackscope.INTERNAL, source="test")))

    def test_asking_for_it_by_name_is_refused_rather_than_filtered(self):
        with self.assertRaises(tools.ToolRefused):
            tools.run(self.client(), "promises")

    def test_an_unbound_channel_cannot_either(self):
        with self.assertRaises(tools.ToolRefused):
            tools.run(slackscope.Scope(slackscope.UNBOUND, source="test"),
                      "promises")


if __name__ == "__main__":
    unittest.main()
