"""`_fan_out`: the per-campaign provider reads, in parallel and in order.

The 2026-09-23 replay measured `sends_today` at 21.72s over 8 campaigns and
`activity_this_week` at 44.81s over 10, and **100% of the agent's latency
was serial provider HTTP**. This is the other half of the fix, the first
being the 60-second readback cache.

The saving is the easy part. Three things are easy to get wrong and hard to
notice, so they are what is tested:

  1. **Order.** `_campaigns_to_read` hands over NEWEST FIRST and several
     answers walk that list to a cap. Returning completion order would
     change which campaigns a capped answer is about, and nothing would
     say so - the count would be identical.

  2. **A failure is handed back, not swallowed and not raised.** The serial
     loops each treat an unreadable campaign differently; a helper that
     picked one would rewrite what every caller reports.

  3. **It is actually concurrent.** A `_fan_out` that ran serially would
     pass 1 and 2 and buy nothing, which is the shape of every green test
     in this repository's lesson list.
"""
import threading
import time
import unittest

from src import slackagenttools as tools


class TestOrderIsTheCallersNotCompletionOrder(unittest.TestCase):

    def test_the_slowest_campaign_first_still_comes_back_first(self):
        """Completion order would put this exactly backwards."""
        delays = {"a": 0.20, "b": 0.10, "c": 0.01}

        def read(key):
            time.sleep(delays[key])
            return key.upper()

        out = tools._fan_out(["a", "b", "c"], read)
        self.assertEqual([i for i, _v, _e in out], ["a", "b", "c"])
        self.assertEqual([v for _i, v, _e in out], ["A", "B", "C"])

    def test_one_id_and_no_ids_are_handled_without_a_pool(self):
        """`ThreadPoolExecutor(max_workers=0)` raises; zero ids must not."""
        self.assertEqual(tools._fan_out([], lambda i: i), [])
        self.assertEqual(tools._fan_out(["a"], str.upper), [("a", "A", None)])


class TestAFailureIsHandedBack(unittest.TestCase):

    def test_the_exception_is_returned_beside_its_campaign(self):
        boom = RuntimeError("provider down")

        def read(key):
            if key == "b":
                raise boom
            return key.upper()

        out = tools._fan_out(["a", "b", "c"], read)
        self.assertEqual(out[0], ("a", "A", None))
        self.assertEqual(out[1][0], "b")
        self.assertIsNone(out[1][1])
        self.assertIs(out[1][2], boom)
        self.assertEqual(out[2], ("c", "C", None))

    def test_one_failure_does_not_lose_the_campaigns_after_it(self):
        """A raise out of the pool would drop c, and the count would be the
        only sign - which is how a floor gets reported as a total."""
        def read(key):
            if key == "a":
                raise RuntimeError("down")
            return key.upper()

        out = tools._fan_out(["a", "b", "c"], read)
        self.assertEqual(len(out), 3)
        self.assertEqual([v for _i, v, _e in out][1:], ["B", "C"])


class TestItIsActuallyConcurrent(unittest.TestCase):

    def test_six_slow_reads_do_not_take_six_times_as_long(self):
        def read(key):
            time.sleep(0.15)
            return key

        started = time.monotonic()
        tools._fan_out(list("abcdef"), read)
        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed, 0.5,
            "six 0.15s reads took %.2fs - serial is 0.90s, so the fan-out "
            "is not fanning out." % elapsed)

    def test_the_concurrency_is_bounded(self):
        """Unbounded fan-out over a thirty-campaign estate is a burst the
        provider's 60-calls-a-minute limit was not asked about."""
        live, peak = [0], [0]
        lock = threading.Lock()

        def read(key):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.05)
            with lock:
                live[0] -= 1
            return key

        tools._fan_out(list(range(30)), read)
        self.assertLessEqual(
            peak[0], tools.PROVIDER_FANOUT,
            "%d reads were in flight at once against a bound of %d"
            % (peak[0], tools.PROVIDER_FANOUT))

    def test_it_does_not_pretend_to_enforce_a_per_minute_rate(self):
        """WHAT THIS BOUND IS NOT, demonstrated rather than asserted of a
        comment.

        Six in flight is a BURST bound. Nothing here spends a per-minute
        budget, so a hundred reads issued back to back go out as fast as
        six-at-a-time allows - well past 60 a minute. That is fine for the
        twenty-odd calls one turn makes and it is not a rate limiter, and
        the next person to need one should find this test rather than
        discover it from the provider.
        """
        sent = []

        def read(key):
            sent.append(time.monotonic())
            return key

        started = time.monotonic()
        tools._fan_out(list(range(100)), read)
        elapsed = time.monotonic() - started
        self.assertEqual(len(sent), 100)
        self.assertLess(
            elapsed, 6.0,
            "100 reads took %.1fs. If that is because something is now "
            "pacing them to 60 a minute, this test is out of date - but "
            "nothing was pacing them when it was written." % elapsed)
        self.assertEqual(tools.PROVIDER_FANOUT, 6)


class TestTheForwardWindowGoesThroughTheReadback(unittest.TestCase):
    """The third provider read, which was not in `slackagentreadback` at all.

    Found 2026-09-24 by stubbing the campaign and queue reads and profiling
    `weekly_plan`: it still cost 3.4s and still made **thirty live HTTPS
    requests**, because `_forward_window` called `bison.sending_schedule`
    directly - three days by ten campaigns, serially. The readback module's
    docstring said two functions reach the provider and they are "the ONLY
    provider calls here", and that was true of the file and false of the
    agent. Neither the cache nor the fan-out covered it, for the same
    reason: it was not there to be found.
    """

    def setUp(self):
        from src import slackagentreadback as readback
        readback.cache_clear()
        self.addCleanup(readback.cache_clear)

    def test_it_no_longer_reaches_the_provider_module_directly(self):
        """BEHAVIOUR, not the text of the source.

        The first version of this grepped `_forward_window` for
        `bison.sending_schedule` and failed on the DOCSTRING that explains
        why it is gone - which is the "test the words, not the system"
        mistake this repository has made repeatedly. So: the provider's
        function is replaced with one that fails the test if it is reached,
        and the readback's with one that counts.
        """
        from src import slackagentreadback as readback
        from src.providers import bison

        reached = []
        real_bison = bison.sending_schedule
        bison.sending_schedule = lambda *a, **k: reached.append(a)
        self.addCleanup(setattr, bison, "sending_schedule", real_bison)

        counted = []
        real_readback = readback.sending_schedule

        def through(campaign_id, day):
            counted.append((campaign_id, day))
            return {"emails_being_sent": 3}

        readback.sending_schedule = through
        self.addCleanup(setattr, readback, "sending_schedule", real_readback)

        tools._forward_window(["a", "b"])
        self.assertEqual(
            reached, [],
            "the forward window went straight to the provider, so the "
            "60-second cache does not cover it and its calls are not "
            "counted against the same budget as every other read")
        self.assertEqual(len(counted), 2 * len(tools.FORWARD_DAYS))

    def test_the_three_states_survive_the_fan_out(self):
        """An integer, the provider's own empty answer, and a failed read.
        Collapsing the middle two into 0 is the mistake this codebase is a
        monument to, so the parallel version has to keep them apart too."""
        from src import slackagentreadback as readback

        class SendingScheduleEmpty(Exception):
            pass

        def fake(campaign_id, day):
            if campaign_id == "b":
                raise SendingScheduleEmpty("no emails for this period")
            if campaign_id == "c":
                raise RuntimeError("gateway timeout")
            return {"emails_being_sent": 7}

        real = readback.sending_schedule
        readback.sending_schedule = fake
        self.addCleanup(setattr, readback, "sending_schedule", real)

        out = tools._forward_window(["a", "b", "c"])
        for day in tools.FORWARD_DAYS:
            self.assertEqual(out[day]["a"], 7)
            self.assertEqual(out[day]["b"], "none scheduled")
            self.assertEqual(out[day]["c"], "unreadable")

    def test_every_day_and_campaign_pair_is_answered(self):
        """Three sequential fan-outs of ten would leave two thirds of the
        wait in place, so the pairs go out together - and nothing may be
        dropped in the flattening."""
        from src import slackagentreadback as readback
        real = readback.sending_schedule
        readback.sending_schedule = lambda c, d: {"emails_being_sent": 1}
        self.addCleanup(setattr, readback, "sending_schedule", real)

        ids = [str(i) for i in range(10)]
        out = tools._forward_window(ids)
        self.assertEqual(sorted(out), sorted(tools.FORWARD_DAYS))
        for day in tools.FORWARD_DAYS:
            self.assertEqual(sorted(out[day]), sorted(ids))


if __name__ == "__main__":
    unittest.main()
