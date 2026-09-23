r"""Two posts per opted-in thread, and the second one is about a PERSON.

OPERATOR, 2026-09-23: "post once when that batch's first provider-confirmed
send lands and once on first human reply, then stop."

The send half shipped in C3. This file is the reply half, and it exists in
this shape because of what the module it tests is famous for: it was written
because the agent offered an update nothing could deliver, and then shipped
with `register()` wired in and `due()` READ BY NOTHING - the identical fault
one level down, wearing a journal.

So **every test here drives the real deliverer**, loaded by path, through
`loop.tick()` or `loop.read_human_replies`. None of them calls
`followup.due_replies` with a hand-made reader and calls that a passing
feature. A caller that does not exist is the failure mode; a test that
supplies the caller itself cannot see it.

## WHAT IS ASSERTED

1. **Two posts, never three.** The send post ADVANCES the watch; the reply
   post closes it; a third tick posts nothing.
2. **A person, not a counter.** The provider's `replied` counter includes
   autoresponders. An out-of-office, a ticket acknowledgement and an
   assistant redirect are not a first reply, and each is rejected here
   through the real `replies.is_automated`.
3. **Two witnesses, and disagreement fails closed.** A row the provider
   flags `automated_reply` is not human however it reads, and a row whose
   text classifies as automated is not human however the provider flags it.
4. **The marker, not a count.** A reply that arrived before the client said
   yes never fires the second post.
5. **Unreadable is not zero**, at both ends: no marker at registration means
   the reply half is never promised, and a feed that cannot be read at fire
   time leaves the watch open rather than announcing silence.

## THE ONE THING A FIXTURE CANNOT PROVE

The reply rows here are the provider's real shape, taken off the live feed
on 2026-09-23 - `id`, `campaign_id`, `automated_reply`, `text_body`, `type`,
`folder` - because the last three defects in this repository were all
invisible to fixtures that mocked the layer the defect lived in. What no
fixture can prove is that the live feed still carries `campaign_id`. It did
this morning, on 15 rows, campaign 492 among them.
"""
import importlib.util
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
    spec = importlib.util.spec_from_file_location(
        "slack_followup_loop_replies",
        os.path.join(ROOT, "scripts", "slack_followup_loop.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loop = _loop()


def _human(row):
    """The trigger's own verdict on one row, straight off the deliverer."""
    return loop._is_human(row)

#: A reply row in the provider's real shape. Trimmed to the fields anything
#: here reads, with the names and types the live feed uses.
def reply(ident, campaign_id="491", text="Sounds good, send times.",
          automated=False, kind="Reply", folder="Inbox"):
    return {"id": ident, "uuid": "u-%s" % ident, "campaign_id": campaign_id,
            "type": kind, "folder": folder, "automated_reply": automated,
            "subject": "Re: quick question", "text_body": text,
            "lead_id": 1000 + ident, "lead": {"id": 1000 + ident},
            "date_received": "2026-09-23T08:00:00Z"}


#: Verbatim shapes the operator's rule of 2026-09-22 names. The EA one is
#: the reply that was the day's only "positive" before that rule existed.
OUT_OF_OFFICE = ("I am currently out of the office returning 30 September "
                 "with limited access to email.")
#: NO REFUSAL IN IT, deliberately. "he is not taking new meetings" classifies
#: as `negative` and should: NEGATIVE outranks ASSISTANT_REDIRECT in the rule
#: table precisely so a classification can never soften a stop. An EA who
#: refuses on her principal's behalf is a refusal first and a redirect
#: second, and that ordering is not this feature's to relitigate. What this
#: fixture has to exercise is the redirect ALONE.
#: YESTERDAY'S ACTUAL EA REPLY, imported rather than re-invented.
#:
#: It is the reply the operator named: the single `positive` in the whole of
#: 2026-09-22, an executive assistant explaining that she manages her
#: principal's inbox, which matched POSITIVE_PATTERNS on the warmth of its
#: prose while nobody at that account had expressed interest in anything.
#: `4af4f982` reclassified it `assistant_redirect`.
#:
#: Imported from `tests/test_an_assistant_is_not_a_buying_signal.py`, where
#: it was sanitised, rather than copied: ONE canonical fixture for one real
#: reply. A second copy is a second thing to keep in step, and the emoji and
#: exclamation marks matter - they are what made the old classifier read it
#: as warmth, and a paraphrase would quietly stop testing that.
from tests.test_an_assistant_is_not_a_buying_signal import (       # noqa: E402
    EA_REDIRECT as ASSISTANT)

#: A SECOND assistant shape, and a finding rather than a fixture note:
#: "I manage Peter's inbox and I look after his diary - I will pass this
#: along to him" classifies `negative`, because "I will pass this along"
#: matches the decline sense of "I'll pass". A forwarding assistant read as
#: a refusal errs in the safe direction - it stops contact rather than
#: continuing it - but it loses the contact candidate `assistant_redirect`
#: exists to keep, and it WOULD fire this feature's second post. Kept here
#: as a live boundary, asserted below rather than assumed.
#: `src/replies.py` is not this session's to edit.
ASSISTANT_WHO_FORWARDS = ("I manage Peter's inbox and I look after his "
                          "diary - I will pass this along to him.")
TICKET = ("Thank you for contacting support. Your request has been logged "
          "as ticket #44812 and a member of the team will respond.")
HUMAN = "Yes please, Thursday works. What time zone are you in?"


class ReplyHalf(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-fu-reply-")
        self._prev = {}
        for key, value in ((followup.JOURNAL_VAR,
                            os.path.join(self.tmp, "f.jsonl")),
                           (followup.HEARTBEAT_VAR,
                            os.path.join(self.tmp, "beat.json")),
                           (loop.LOG_VAR,
                            os.path.join(self.tmp, "delivered.jsonl"))):
            self._prev[key] = os.environ.get(key)
            os.environ[key] = value
        self.posted = []

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ----------------------------------------------------------- fixtures

    def arm(self, marker=100, **over):
        row = {"channel": "C1", "thread_ts": "T1", "workspace": "alpha",
               "campaign_ids": ["491", "492"],
               "baseline": {"491": 0, "492": 0}, "language": "en",
               "reply_marker": marker}
        row.update(over)
        return followup.register(**row)

    def bound(self, workspace="alpha"):
        return mock.patch.object(
            slackscope, "resolve",
            lambda **k: slackscope.Scope(slackscope.CLIENT,
                                         workspace=workspace, source="test"))

    def feed(self, rows, fail=False):
        """Patch the provider's reply feed. One page, newest first."""
        def fetch_replies(cursor=None, per_page=None, path=None):
            if fail:
                raise RuntimeError("provider down")
            return list(rows), None
        return mock.patch.object(loop.bison, "fetch_replies", fetch_replies)

    def sent(self, count=5):
        """The send half: every campaign has sent, so it fires at once."""
        return mock.patch.object(loop.readback, "campaign_by_id",
                                 lambda cid: {"emails_sent": count})

    def quiet(self):
        return mock.patch.object(loop.readback, "campaign_by_id",
                                 lambda cid: {"emails_sent": 0})

    def posting(self):
        return mock.patch.object(loop.slack, "post",
                                 lambda payload: self.posted.append(payload))

    def run_tick(self, rows=(), sends=True, fail=False):
        counter = self.sent() if sends else self.quiet()
        with self.bound(), self.posting(), counter, self.feed(rows, fail), \
                mock.patch.object(loop.watchsink, "beat"):
            return loop.tick()


# ================================ 1. TWO POSTS, NEVER THREE

class TheThreadGetsExactlyTwo(ReplyHalf):

    def test_the_send_post_advances_rather_than_closing(self):
        watch = self.arm()
        self.run_tick()
        after = [r for r in followup.load() if r["id"] == watch["id"]][0]
        self.assertEqual(after["status"], followup.REGISTERED)
        self.assertEqual(followup.stage_of(after), followup.AWAITING_REPLY)
        self.assertEqual(len(self.posted), 1)

    def test_the_reply_post_closes_it(self):
        self.arm()
        self.run_tick()                                   # send announced
        self.run_tick([reply(101, text=HUMAN)])           # a person replied
        self.assertEqual(len(self.posted), 2)
        self.assertEqual(followup.open_watches(), [])

    def test_a_third_tick_posts_nothing(self):
        """The whole of "then stop", as one assertion."""
        self.arm()
        self.run_tick()
        self.run_tick([reply(101, text=HUMAN)])
        self.run_tick([reply(102, text=HUMAN), reply(103, text=HUMAN)])
        self.assertEqual(len(self.posted), 2)

    def test_the_second_message_says_a_person_wrote_it(self):
        self.arm()
        self.run_tick()
        self.run_tick([reply(101, text=HUMAN)])
        self.assertIn("written by a person", self.posted[1]["text"])

    def test_it_goes_into_the_same_thread(self):
        self.arm()
        self.run_tick()
        self.run_tick([reply(101, text=HUMAN)])
        self.assertEqual([p["thread_ts"] for p in self.posted], ["T1", "T1"])


# ================================ 2. A PERSON, NOT A COUNTER

class AnAutoresponderIsNotAFirstReply(ReplyHalf):

    def advanced(self):
        self.arm()
        self.run_tick()
        self.posted[:] = []

    def test_an_out_of_office_does_not_fire_it(self):
        self.advanced()
        self.run_tick([reply(101, text=OUT_OF_OFFICE)])
        self.assertEqual(self.posted, [])

    def test_yesterdays_ea_auto_reply_does_not_fire_it(self):
        """THE NAMED CASE, on the actual reply.

        2026-09-22's only `positive` in the whole day: an executive
        assistant explaining that she manages her principal's inbox. Under
        the old classifier this was a buying signal. Under the new one it
        is `assistant_redirect`, and a client who opted into two updates
        must not be told this was the first reply a person wrote to them -
        nobody at that account has expressed interest in anything.
        """
        self.advanced()
        self.run_tick([reply(101, text=ASSISTANT)])
        self.assertEqual(self.posted, [])

    def test_it_is_the_new_classifier_that_stops_it(self):
        """NAMES THE MECHANISM, so a later refactor cannot pass this class
        by accident - if the trigger stopped consulting the classifier and
        leaned on the provider's flag alone, every test above would still
        pass and this one would not."""
        self.assertEqual(loop.replies.classify(ASSISTANT)["classification"],
                         loop.replies.ASSISTANT_REDIRECT)
        self.assertTrue(loop.replies.is_automated(
            loop.replies.ASSISTANT_REDIRECT))
        self.assertFalse(_human(reply(101, text=ASSISTANT)))

    def test_the_provider_did_not_flag_it(self):
        """And it is stopped anyway.

        The EA reply is carried here with `automated_reply` false, which is
        the hard case: the provider's own flag was true on 21 of that day's
        26 replies but a flag is not the rule. If this feature leaned on
        the provider alone it would announce this as a human reply.
        """
        row = reply(101, text=ASSISTANT)
        self.assertFalse(row["automated_reply"])
        self.assertFalse(_human(row))

    def test_a_ticket_acknowledgement_does_not_fire_it(self):
        self.advanced()
        self.run_tick([reply(101, text=TICKET)])
        self.assertEqual(self.posted, [])

    def test_the_forwarding_assistant_is_the_boundary_and_it_does_fire(self):
        """AN HONEST FAILURE, ASSERTED RATHER THAN HIDDEN.

        "I will pass this along to him" classifies `negative`, not
        `assistant_redirect`, because it matches the decline sense of "I'll
        pass" - so it is not automated, so it DOES fire the second post.

        This is written as an assertion of current behaviour, not of
        desired behaviour. It is here so the boundary is visible and so
        that the day somebody fixes `src/replies.py` this test fails
        loudly and tells them a client-facing trigger moved with it.
        """
        self.advanced()
        self.assertEqual(
            loop.replies.classify(ASSISTANT_WHO_FORWARDS)["classification"],
            loop.replies.NEGATIVE)
        self.run_tick([reply(101, text=ASSISTANT_WHO_FORWARDS)])
        self.assertEqual(len(self.posted), 1)

    def test_a_person_after_three_autoresponders_still_fires_it(self):
        """The autoresponders do not consume the promise."""
        self.advanced()
        self.run_tick([reply(103, text=TICKET), reply(102, text=ASSISTANT),
                       reply(101, text=OUT_OF_OFFICE)])
        self.assertEqual(self.posted, [])
        self.run_tick([reply(104, text=HUMAN), reply(103, text=TICKET)])
        self.assertEqual(len(self.posted), 1)


# ================================ 3. TWO WITNESSES, FAIL CLOSED

class TheWitnessesMustAgree(ReplyHalf):

    def advanced(self):
        self.arm()
        self.run_tick()
        self.posted[:] = []

    def test_the_provider_flag_alone_disqualifies_it(self):
        """Human prose, flagged automated by the provider. Not counted."""
        self.advanced()
        self.run_tick([reply(101, text=HUMAN, automated=True)])
        self.assertEqual(self.posted, [])

    def test_our_classifier_alone_disqualifies_it(self):
        """Unflagged by the provider, automated by our own rule."""
        self.advanced()
        self.run_tick([reply(101, text=OUT_OF_OFFICE, automated=False)])
        self.assertEqual(self.posted, [])

    def test_a_classifier_that_raises_is_not_a_licence(self):
        self.advanced()
        with mock.patch.object(loop.replies, "classify",
                               side_effect=RuntimeError("boom")):
            self.run_tick([reply(101, text=HUMAN)])
        self.assertEqual(self.posted, [])


# ================================ 4. THE MARKER

class AReplyFromBeforeTheYesIsNotTheFirstReply(ReplyHalf):

    def test_an_older_reply_does_not_fire_it(self):
        self.arm(marker=100)
        self.run_tick()
        self.posted[:] = []
        self.run_tick([reply(99, text=HUMAN), reply(50, text=HUMAN)])
        self.assertEqual(self.posted, [])

    def test_the_marker_row_itself_is_not_counted(self):
        self.arm(marker=100)
        self.run_tick()
        self.posted[:] = []
        self.run_tick([reply(100, text=HUMAN)])
        self.assertEqual(self.posted, [])

    def test_another_campaign_does_not_fire_it(self):
        """The feed is the whole workspace's; the watch is one batch's."""
        self.arm(marker=100)
        self.run_tick()
        self.posted[:] = []
        self.run_tick([reply(101, campaign_id="777", text=HUMAN)])
        self.assertEqual(self.posted, [])

    def test_the_walk_stops_at_the_marker_rather_than_skipping(self):
        """Rows below the marker end the walk. A human reply buried under
        one of them belongs to a previous watch and is not ours."""
        self.arm(marker=100)
        self.run_tick()
        self.posted[:] = []
        self.run_tick([reply(99, text=HUMAN), reply(101, text=HUMAN)])
        self.assertEqual(self.posted, [])


# ================================ 5. UNREADABLE IS NOT ZERO

class ACannotReadIsNeverASilence(ReplyHalf):

    def test_no_marker_means_the_reply_half_is_never_promised(self):
        """`register(reply_marker=None)` - the feed was down when they said
        yes. The send is still announced; the watch then closes."""
        watch = self.arm(marker=None)
        self.run_tick()
        self.assertEqual(len(self.posted), 1)
        after = [r for r in followup.load() if r["id"] == watch["id"]][0]
        self.assertEqual(after["status"], followup.FIRED)
        self.assertEqual(followup.open_watches(), [])

    def test_an_unreadable_feed_leaves_the_watch_open(self):
        self.arm()
        self.run_tick()
        self.posted[:] = []
        self.run_tick(fail=True)
        self.assertEqual(self.posted, [])
        self.assertEqual(len(followup.open_watches()), 1)
        still = followup.open_watches()[0]
        self.assertEqual(followup.stage_of(still), followup.AWAITING_REPLY)

    def test_it_recovers_on_the_next_tick(self):
        self.arm()
        self.run_tick()
        self.posted[:] = []
        self.run_tick(fail=True)
        self.run_tick([reply(101, text=HUMAN)])
        self.assertEqual(len(self.posted), 1)

    def test_read_human_replies_returns_none_rather_than_zero(self):
        """Directly, because the distinction is the whole point and a
        caller that reads None as 0 announces a silence nobody measured."""
        watch = dict(self.arm(), reply_marker=100)
        with self.feed([], fail=True):
            self.assertIsNone(loop.read_human_replies(watch))
        with self.feed([]):
            self.assertEqual(loop.read_human_replies(watch), 0)


# ================================ 6. THE EXPIRY SAYS SO OUT LOUD

class SevenQuietDaysAreReported(ReplyHalf):

    def test_the_reply_half_gets_its_own_longer_window(self):
        self.assertGreater(followup.REPLY_TTL_SECONDS, followup.TTL_SECONDS)

    def test_an_expired_reply_watch_says_nobody_wrote(self):
        watch = self.arm()
        self.run_tick()
        self.posted[:] = []
        stale = [r for r in followup.load() if r["id"] == watch["id"]][0]
        followup._append(dict(stale, expires_epoch=int(time.time()) - 5))
        self.run_tick()
        self.assertEqual(len(self.posted), 1)
        self.assertIn("no reply written by a person", self.posted[0]["text"])
        self.assertEqual(followup.open_watches(), [])


# ================================ 7. THE SCOPE PROPERTY, AT BOTH STAGES

class ARebindingCancelsTheSecondPostToo(ReplyHalf):

    def test_a_rebound_channel_is_cancelled_unposted(self):
        """The first half already had this. The second must, because it
        fires DAYS later - the window in which a rebinding is likeliest."""
        self.arm()
        self.run_tick()
        self.posted[:] = []
        with self.bound(workspace="someone-else"), self.posting(), \
                self.sent(), self.feed([reply(101, text=HUMAN)]), \
                mock.patch.object(loop.watchsink, "beat"):
            loop.tick()
        self.assertEqual(self.posted, [])
        closed = [r for r in followup.load()][-1]
        self.assertEqual(closed["status"], followup.CANCELLED)


if __name__ == "__main__":
    unittest.main()
