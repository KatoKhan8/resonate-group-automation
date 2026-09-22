"""A registered watch is not a mechanism. A process that fires it is.

`src/slackfollowup.py` was written because the first live client answer
ended "would you like a short update once the first batch-1 mails go out"
and nothing anywhere could have produced that update. It then shipped with
`register()` wired into the conversation and `due()` READ BY NOTHING - so a
client could say yes, a row was written, and the identical silence
followed. The fault was one level down and harder to see, because a journal
full of registered watches looks like a working feature.

`scripts/slack_followup_loop.py` is the process. These tests assert the two
halves that make the promise real:

1. **The offer is unavailable while nothing is beating.** Committed and not
   started is indistinguishable, from the client's side, from never built -
   so the agent stays quiet rather than optimistic.
2. **The delivery is ordered so a failure cannot lose the message.** Post
   first, close second; a failed post leaves the watch open for the next
   tick, and the TTL eventually says so out loud rather than leaving the
   client waiting.

And one scope property: a channel rebound between registering and firing is
cancelled unposted, because posting a day-old batch's campaign ids into a
channel that now belongs to somebody else is a cross-client leak arriving
late.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackfollowup as followup, slackscope             # noqa: E402


def _loop():
    """The deliverer, loaded by path - `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "slack_followup_loop",
        os.path.join(ROOT, "scripts", "slack_followup_loop.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loop = _loop()


class Delivering(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-fu-loop-")
        self._prev = {}
        for key, value in ((followup.JOURNAL_VAR,
                            os.path.join(self.tmp, "f.jsonl")),
                           (followup.HEARTBEAT_VAR,
                            os.path.join(self.tmp, "beat.json")),
                           (loop.LOG_VAR,
                            os.path.join(self.tmp, "delivered.jsonl"))):
            self._prev[key] = os.environ.get(key)
            os.environ[key] = value

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def arm(self, **over):
        row = {"channel": "C1", "thread_ts": "T1", "workspace": "alpha",
               "campaign_ids": ["491", "492"],
               "baseline": {"491": 0, "492": 0}, "language": "hr"}
        row.update(over)
        return followup.register(**row)

    def bound(self, workspace="alpha"):
        """Pretend C1 is a client channel bound to `workspace`."""
        return mock.patch.object(
            slackscope, "resolve",
            lambda **k: slackscope.Scope(slackscope.CLIENT,
                                         workspace=workspace, source="test"))


# ================================ 1. THE GATE

class TheOfferIsUnavailableWhileNothingIsBeating(Delivering):

    def test_a_cold_deliverer_reads_as_not_running(self):
        self.assertFalse(followup.deliverer_is_running())

    def test_a_tick_makes_it_run(self):
        with mock.patch.object(loop.watchsink, "beat") as beat:
            loop.tick()
        self.assertTrue(beat.called)
        self.assertEqual(beat.call_args[0][0], followup.WATCHER)

    def test_the_beat_says_what_the_pass_found(self):
        self.arm()
        seen = {}
        with mock.patch.object(loop.watchsink, "beat",
                               lambda name, state=None: seen.update(
                                   state or {})), \
                mock.patch.object(loop.readback, "campaign_by_id",
                                  lambda cid: {"emails_sent": 0}):
            loop.tick()
        self.assertEqual(seen["open"], 1)
        self.assertEqual(seen["due"], 0)
        self.assertEqual(seen["delivered"], 0)


# ================================ 2. READING THE COUNTER

class AnUnreadableCampaignIsNotAZero(Delivering):

    def test_it_is_absent_rather_than_zero(self):
        """`due` compares against a baseline, and a zero standing in for an
        unreadable campaign is a send that never gets announced."""
        def detail(campaign_id):
            if str(campaign_id) == "491":
                return {"_error": "provider down"}
            return {"emails_sent": 4}

        with mock.patch.object(loop.readback, "campaign_by_id", detail):
            counts = loop.read_counts(["491", "492"])
        self.assertEqual(counts, {"492": 4})

    def test_a_non_integer_counter_is_not_read_as_a_number(self):
        with mock.patch.object(loop.readback, "campaign_by_id",
                               lambda c: {"emails_sent": "several"}):
            self.assertEqual(loop.read_counts(["491"]), {})


# ================================ 3. THE ORDER OF POST AND CLOSE

class AFailedPostKeepsTheWatchOpen(Delivering):

    def test_a_post_that_raises_leaves_it_registered(self):
        watch = self.arm()
        with self.bound(), mock.patch.object(
                loop.slack, "post",
                side_effect=RuntimeError("slack is down")):
            delivered = loop.deliver(watch, {"491": 3})
        self.assertFalse(delivered)
        still = followup.for_thread("C1", "T1")
        self.assertIsNotNone(still)
        self.assertEqual(still["status"], followup.REGISTERED)

    def test_a_post_that_lands_closes_it_as_fired(self):
        watch = self.arm()
        with self.bound(), mock.patch.object(loop.slack, "post") as post:
            self.assertTrue(loop.deliver(watch, {"491": 3}))
        self.assertIsNone(followup.for_thread("C1", "T1"))
        payload = post.call_args[0][0]
        self.assertEqual(payload["channel"], "C1")
        self.assertEqual(payload["thread_ts"], "T1")
        self.assertIn("491: 3", payload["text"])

    def test_it_posts_in_the_language_the_thread_was_in(self):
        watch = self.arm(language="hr")
        with self.bound(), mock.patch.object(loop.slack, "post") as post:
            loop.deliver(watch, {"491": 3})
        self.assertIn("Javljam", post.call_args[0][0]["text"])

    def test_an_expiry_says_so_rather_than_going_quiet(self):
        watch = self.arm()
        with self.bound(), mock.patch.object(loop.slack, "post") as post:
            loop.deliver(watch, None)
        text = post.call_args[0][0]["text"]
        self.assertIn("nijedan mail", text)
        closed = [r for r in followup.load() if r["id"] == watch["id"]]
        self.assertEqual(closed[0]["status"], followup.EXPIRED)

    def test_a_dry_run_posts_nothing_and_closes_nothing(self):
        watch = self.arm()
        with self.bound(), mock.patch.object(loop.slack, "post") as post:
            loop.deliver(watch, {"491": 3}, dry_run=True)
        self.assertFalse(post.called)
        self.assertEqual(followup.for_thread("C1", "T1")["status"],
                         followup.REGISTERED)


# ================================ 4. THE BINDING IS CHECKED AGAIN

class AChannelReboundBetweenArmingAndFiringIsCancelled(Delivering):

    def test_a_channel_now_belonging_to_another_client_is_not_posted_to(self):
        watch = self.arm(workspace="alpha")
        with self.bound("beta"), mock.patch.object(loop.slack,
                                                   "post") as post:
            self.assertFalse(loop.deliver(watch, {"491": 3}))
        self.assertFalse(post.called)
        closed = [r for r in followup.load() if r["id"] == watch["id"]]
        self.assertEqual(closed[0]["status"], followup.CANCELLED)

    def test_a_channel_that_is_no_longer_a_client_channel_is_not_posted_to(
            self):
        watch = self.arm()
        unbound = mock.patch.object(
            slackscope, "resolve",
            lambda **k: slackscope.Scope(slackscope.UNBOUND, source="test"))
        with unbound, mock.patch.object(loop.slack, "post") as post:
            self.assertFalse(loop.deliver(watch, {"491": 3}))
        self.assertFalse(post.called)

    def test_the_right_channel_still_gets_it(self):
        watch = self.arm(workspace="alpha")
        with self.bound("alpha"), mock.patch.object(loop.slack,
                                                    "post") as post:
            self.assertTrue(loop.deliver(watch, {"491": 3}))
        self.assertTrue(post.called)


# ================================ 5. END TO END, ONE TICK

class OneTickTakesAWatchFromArmedToPosted(Delivering):

    def test_the_counter_moving_is_what_fires_it(self):
        self.arm()
        sent = {"491": 0, "492": 0}
        with self.bound(), mock.patch.object(
                loop.readback, "campaign_by_id",
                lambda c: {"emails_sent": sent[str(c)]}), \
                mock.patch.object(loop.watchsink, "beat"), \
                mock.patch.object(loop.slack, "post") as post:
            self.assertEqual(loop.tick(), 0)
            self.assertFalse(post.called)
            sent["491"] = 2
            self.assertEqual(loop.tick(), 1)
            self.assertTrue(post.called)
            self.assertEqual(loop.tick(), 0)
        self.assertIsNone(followup.for_thread("C1", "T1"))

    def test_a_campaign_that_had_already_sent_does_not_fire_it_instantly(self):
        """The baseline is what makes "the first mail has gone out" about
        mail that went out after they asked."""
        self.arm(baseline={"491": 40, "492": 0})
        with self.bound(), mock.patch.object(
                loop.readback, "campaign_by_id",
                lambda c: {"emails_sent": 40 if str(c) == "491" else 0}), \
                mock.patch.object(loop.watchsink, "beat"), \
                mock.patch.object(loop.slack, "post") as post:
            self.assertEqual(loop.tick(), 0)
        self.assertFalse(post.called)


if __name__ == "__main__":
    unittest.main()
