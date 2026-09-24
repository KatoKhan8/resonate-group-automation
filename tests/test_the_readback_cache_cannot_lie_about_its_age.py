"""The 60-second readback cache, and the two ways a cache like this lies.

Built 2026-09-24 against the 2026-09-23 replay measurement: p50 24.3s, p95
132.3s, and **100% of it serial provider HTTP**. A five-tool turn reads the
same campaign up to four times.

The saving is not what is tested hardest here. These are:

  1. **A reused value must not wear a fresh timestamp.** That is the only
     way a readback cache turns a correct system into a confidently wrong
     one, and `read_at` is what every downstream answer stamps itself with.

  2. **A failure must not be cached.** One transient provider error held
     for a minute is sixty seconds of invented outage, and this module's
     stated contract is that a readback which fails says so.

  3. **It must actually be a cache.** A "cache" that re-fetches every time
     passes 1 and 2 perfectly and buys nothing, so the hit is asserted too.
"""
import shutil
import threading
import time
import unittest

from src import slackagentreadback as readback
from tests.slackbase import IsolatedState


class Counter:
    """A fetch that records how often it really ran."""

    def __init__(self, value="v", delay=0.0, boom=None):
        self.value, self.delay, self.boom = value, delay, boom
        self.calls = 0
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.boom:
            raise self.boom
        return self.value


class InATurn(unittest.TestCase):
    """The cache is only live inside `readback.turn()`.

    Outside one, `cached` is a pass-through - see `_TURN_DEPTH`. Every test
    below that is ABOUT caching therefore has to open a turn, and the two
    classes at the bottom are about the scoping itself.
    """

    def setUp(self):
        readback.cache_clear()
        self._turn = readback.turn()
        self._turn.__enter__()
        self.addCleanup(self._turn.__exit__, None, None, None)
        self.addCleanup(readback.cache_clear)


class TestItIsActuallyACache(InATurn):

    def test_the_second_read_does_not_reach_the_provider(self):
        fetch = Counter("rows")
        first, _at, age = readback.cached("queue", 491, fetch)
        second, _at2, age2 = readback.cached("queue", 491, fetch)
        self.assertEqual((first, second), ("rows", "rows"))
        self.assertEqual(fetch.calls, 1, "the cache re-fetched; it is not one")
        self.assertEqual(age, 0.0)
        self.assertGreaterEqual(age2, 0.0)

    def test_the_route_is_part_of_the_key(self):
        """`campaign` and `queue` are different reads of the same id."""
        row, queue_rows = Counter("row"), Counter("rows")
        self.assertEqual(readback.cached("campaign", 491, row)[0], "row")
        self.assertEqual(readback.cached("queue", 491, queue_rows)[0], "rows")
        self.assertEqual((row.calls, queue_rows.calls), (1, 1))

    def test_a_different_campaign_is_a_different_key(self):
        fetch = Counter()
        readback.cached("campaign", 491, fetch)
        readback.cached("campaign", 492, fetch)
        self.assertEqual(fetch.calls, 2)

    def test_it_expires(self):
        fetch = Counter()
        readback.cached("campaign", 491, fetch, ttl=0.01)
        time.sleep(0.05)
        readback.cached("campaign", 491, fetch, ttl=0.01)
        self.assertEqual(fetch.calls, 2, "a value past its TTL was reused")

    def test_the_default_ttl_is_sixty_seconds(self):
        """The operator's number. A test so it is changed on purpose."""
        self.assertEqual(readback.READBACK_TTL, 60.0)


class TestItCannotLieAboutHowOldTheValueIs(InATurn):
    """THE FAILURE MODE THIS WHOLE FILE EXISTS FOR."""


    def test_a_reused_value_keeps_the_time_it_was_actually_fetched(self):
        fetch = Counter()
        _v, first_at, _age = readback.cached("campaign", 491, fetch)
        time.sleep(0.05)
        _v2, second_at, second_age = readback.cached("campaign", 491, fetch)
        self.assertEqual(
            second_at, first_at,
            "the reused value was stamped with the moment it was REUSED. "
            "Every answer built on it would report a stale number as "
            "current, which is the one thing this cache must never do.")
        self.assertGreater(second_age, 0.0,
                           "a reused value reported an age of zero")

    def test_a_fresh_fetch_reports_an_age_of_zero(self):
        """The control: if every age were non-zero the check above is vacuous."""
        _v, _at, age = readback.cached("campaign", 491, Counter())
        self.assertEqual(age, 0.0)


class TestAFailureIsNotCached(InATurn):


    def test_the_error_is_raised_to_the_caller(self):
        fetch = Counter(boom=RuntimeError("provider down"))
        with self.assertRaises(RuntimeError):
            readback.cached("queue", 491, fetch)

    def test_the_next_caller_asks_again(self):
        boom = Counter(boom=RuntimeError("provider down"))
        with self.assertRaises(RuntimeError):
            readback.cached("queue", 491, boom)
        good = Counter("rows")
        value, _at, _age = readback.cached("queue", 491, good)
        self.assertEqual(value, "rows",
                         "a transient failure was held and served as state")
        self.assertEqual(good.calls, 1)

    def test_a_failure_does_not_evict_the_good_value_before_it(self):
        """Nothing is written on the raising path, so the hit survives."""
        good = Counter("rows")
        readback.cached("queue", 491, good)
        boom = Counter(boom=RuntimeError("provider down"))
        value, _at, _age = readback.cached("queue", 491, boom)
        self.assertEqual(value, "rows")
        self.assertEqual(boom.calls, 0, "a live value was discarded to re-ask")


class TestConcurrentReadsCoalesce(InATurn):
    """The cold first turn: five parallel reads of one campaign, one fetch."""


    def test_eight_threads_on_one_key_make_one_request(self):
        fetch = Counter("rows", delay=0.1)
        out = []
        threads = [threading.Thread(
            target=lambda: out.append(readback.cached("queue", 491, fetch)[0]))
            for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(out, ["rows"] * 8)
        self.assertEqual(
            fetch.calls, 1,
            "eight threads made %d requests for one campaign. The cache is "
            "cold exactly when the parallel reads fan out, so without "
            "coalescing it saves nothing on the turn that needs it most."
            % fetch.calls)

    def test_different_keys_are_not_serialised_behind_each_other(self):
        """A single global lock held across the fetch would undo the
        parallelism this cache was built to enable."""
        fetch = Counter("rows", delay=0.2)
        started = time.monotonic()
        threads = [threading.Thread(
            target=lambda i=i: readback.cached("queue", 500 + i, fetch))
            for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - started
        self.assertEqual(fetch.calls, 4)
        self.assertLess(
            elapsed, 0.6,
            "four reads of four DIFFERENT campaigns took %.2fs against a "
            "0.2s provider - they ran one after another, so a lock is held "
            "across the fetch." % elapsed)


class TestItIsNeverPersisted(unittest.TestCase):

    def test_clearing_it_empties_it(self):
        readback.cache_clear()
        with readback.turn():
            readback.cached("campaign", 491, Counter())
            self.assertTrue(readback.cache_state())
            readback.cache_clear()
            self.assertEqual(readback.cache_state(), {})

    def test_using_the_cache_writes_no_file_anywhere(self):
        """A per-process cache that wrote itself down would survive the
        restart it must not survive.

        BEHAVIOUR, not a grep of the source for `open(`. The first version
        of this searched `cached`'s text, which is the "test the words, not
        the system" mistake - it would have gone green the day the write
        moved one function along. This walks the state directory instead.
        """
        import os
        import tempfile
        from src import store

        before_dir = tempfile.mkdtemp(prefix="rga-cache-nofile-")
        self.addCleanup(shutil.rmtree, before_dir, True)
        previous = {key: os.environ.get(key) for key in store.STATE_OVERRIDES}
        store.use_directory(before_dir)

        def restore():
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.addCleanup(restore)

        def listing():
            found = set()
            for root, _dirs, files in os.walk(before_dir):
                for name in files:
                    found.add(os.path.join(root, name))
            return found

        was = listing()
        readback.cached("campaign", 491, Counter("row"))
        readback.cached("queue", 491, Counter("rows"))
        readback.cached("campaign", 491, Counter("row"))
        self.assertEqual(
            listing(), was,
            "the readback cache wrote something to the state directory. It "
            "is per-process by design: a cached '491 sent 494 today' that "
            "survived a restart would be read as today's number tomorrow.")


if __name__ == "__main__":
    unittest.main()


class TestItIsScopedToOneTurn(unittest.TestCase):
    """THE PROPERTY THAT COST 154 FAILURES BEFORE IT EXISTED.

    The first version was a plain process-global 60-second cache. That is
    correct in production - one loop, one turn at a time, minutes apart -
    and wrong everywhere else: a test that stubs the provider, calls a
    tool, restubs and calls again got the FIRST stub's answer. The full
    suite went from green to 154 failures and **not one of them named the
    cache**; they named `'unreadable' != 40` in a module about scheduling.

    Scoping it to a turn keeps the whole measured saving, because every
    repeat it removes is inside one turn, and retires the staleness risk
    the last handoff named at the same time.
    """

    def setUp(self):
        readback.cache_clear()
        self.addCleanup(readback.cache_clear)

    def test_outside_a_turn_nothing_is_cached(self):
        fetch = Counter()
        readback.cached("campaign", 491, fetch)
        readback.cached("campaign", 491, fetch)
        self.assertEqual(
            fetch.calls, 2,
            "a read outside a turn was served from cache. Every direct "
            "caller - a script, the briefing loop, a test that stubs the "
            "provider - must get what it got before the cache existed.")
        self.assertFalse(readback.caching())

    def test_inside_a_turn_it_is(self):
        """The control: if nothing were ever cached the test above passes
        and the cache is decoration."""
        fetch = Counter()
        with readback.turn():
            readback.cached("campaign", 491, fetch)
            readback.cached("campaign", 491, fetch)
            self.assertTrue(readback.caching())
        self.assertEqual(fetch.calls, 1)

    def test_a_new_turn_starts_cold(self):
        """A campaign paused between two questions is visible in the
        second one. This is the staleness risk, closed."""
        fetch = Counter()
        with readback.turn():
            readback.cached("campaign", 491, fetch)
        with readback.turn():
            readback.cached("campaign", 491, fetch)
        self.assertEqual(fetch.calls, 2)

    def test_the_turn_is_closed_even_when_the_turn_raises(self):
        fetch = Counter()
        with self.assertRaises(ValueError):
            with readback.turn():
                readback.cached("campaign", 491, fetch)
                raise ValueError("the turn blew up")
        self.assertFalse(readback.caching())
        self.assertEqual(readback.cache_state(), {})

    def test_nesting_does_not_end_the_turn_early(self):
        """`working_on` calls `sends_today`; if either opened its own turn
        the inner one must not clear the outer one's readbacks."""
        fetch = Counter()
        with readback.turn():
            readback.cached("campaign", 491, fetch)
            with readback.turn():
                readback.cached("campaign", 491, fetch)
            readback.cached("campaign", 491, fetch)
        self.assertEqual(fetch.calls, 1)
        self.assertFalse(readback.caching())


class TestAWholeTurnOpensOne(IsolatedState, unittest.TestCase):

    def setUp(self):
        # A real turn reads the knowledge pack and a stale pack is REBUILT
        # AND WRITTEN, so this has to isolate the store or `store`'s own
        # guard refuses it. See tests/slackbase.py.
        self.isolate()
        self.addCleanup(self.restore)

    def test_respond_opens_a_turn(self):
        """Without this the cache is unreachable in production and every
        number in the merge request is about a code path nothing takes."""
        from src import slackconversation as conversation
        from src import slackscope

        saw = []

        class Model:
            model = "m"

            def complete(self, prompt, temperature=0):
                saw.append(readback.caching())
                return '{"tools": [], "clarify": null}'

        import os
        previous = os.environ.get(slackscope.INTERNAL_CHANNELS_VAR)
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = "C_TURNTEST"

        def restore():
            if previous is None:
                os.environ.pop(slackscope.INTERNAL_CHANNELS_VAR, None)
            else:
                os.environ[slackscope.INTERNAL_CHANNELS_VAR] = previous
        self.addCleanup(restore)

        conversation.respond("are the monitors alive?",
                             channel="C_TURNTEST", user="U", model=Model())
        self.assertTrue(saw and all(saw),
                        "the model ran outside a readback turn, so nothing "
                        "in the turn was cached")
        self.assertFalse(readback.caching(), "the turn was left open")
