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


class TestItIsActuallyACache(unittest.TestCase):

    def setUp(self):
        readback.cache_clear()
        self.addCleanup(readback.cache_clear)

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


class TestItCannotLieAboutHowOldTheValueIs(unittest.TestCase):
    """THE FAILURE MODE THIS WHOLE FILE EXISTS FOR."""

    def setUp(self):
        readback.cache_clear()
        self.addCleanup(readback.cache_clear)

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


class TestAFailureIsNotCached(unittest.TestCase):

    def setUp(self):
        readback.cache_clear()
        self.addCleanup(readback.cache_clear)

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


class TestConcurrentReadsCoalesce(unittest.TestCase):
    """The cold first turn: five parallel reads of one campaign, one fetch."""

    def setUp(self):
        readback.cache_clear()
        self.addCleanup(readback.cache_clear)

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
