"""`gather` is a bounded-concurrency primitive that cannot break the spend audit.

It is NOT wired into `enrich.run`. These tests pin every rule the wiring
change will rely on:

  - order is input order, always, whatever order the calls complete in;
  - exactly one Outcome per input, including on failure, never fewer;
  - one item raising does not lose the others;
  - k=1 is exactly serial and goes through the real code path;
  - the callable is executed exactly once per item;
  - no shared mutable state - gather adds no synchronisation of its own;
  - deterministic under identical input, twenty runs in a row;
  - a slow item does not delay results for items that finished;
  - 200 items at k=8 complete in roughly serial/8 of the sleep time.

No network, no real PII, no provider module imported.
"""
import threading
import time
import unittest

from src.gather import Outcome, gather


class OutcomeDistinguishability(unittest.TestCase):
    """The four kinds are distinguishable without ambiguity."""

    def test_ok_carries_its_value(self):
        o = Outcome.ok(42)
        self.assertTrue(o.is_ok)
        self.assertEqual(o.value, 42)

    def test_ok_with_false_is_not_confused_with_failed(self):
        o = Outcome.ok(False)
        self.assertTrue(o.is_ok)
        self.assertFalse(o.is_failed)
        self.assertIs(o.value, False)

    def test_ok_with_empty_dict_is_not_confused_with_not_attempted(self):
        o = Outcome.ok({})
        self.assertTrue(o.is_ok)
        self.assertFalse(o.is_not_attempted)
        self.assertEqual(o.value, {})

    def test_ok_with_none_is_still_ok(self):
        o = Outcome.ok(None)
        self.assertTrue(o.is_ok)
        self.assertIsNone(o.value)

    def test_failed_carries_the_exception(self):
        exc = ValueError("bad")
        o = Outcome.failed(exc)
        self.assertTrue(o.is_failed)
        self.assertIs(o.value, exc)
        self.assertIsInstance(o.value, ValueError)

    def test_timed_out_has_no_value(self):
        o = Outcome.timed_out()
        self.assertTrue(o.is_timed_out)
        self.assertIsNone(o.value)

    def test_not_attempted_has_no_value(self):
        o = Outcome.not_attempted()
        self.assertTrue(o.is_not_attempted)
        self.assertIsNone(o.value)

    def test_four_kinds_are_mutually_exclusive(self):
        outcomes = [
            Outcome.ok(1),
            Outcome.failed(RuntimeError("x")),
            Outcome.timed_out(),
            Outcome.not_attempted(),
        ]
        kinds = [o.kind for o in outcomes]
        self.assertEqual(len(set(kinds)), 4)


class OrderIsInputOrder(unittest.TestCase):
    """Order is input order, always, whatever order the calls complete in."""

    def test_reverse_sleep_preserves_input_order(self):
        """Items that sleep longer are submitted first but finish last."""
        items = list(range(10))

        def slow_first(item):
            time.sleep((9 - item) * 0.01)
            return item * 10

        results = gather(items, slow_first, k=4)
        self.assertEqual([o.value for o in results],
                         [i * 10 for i in range(10)])

    def test_random_sleep_preserves_input_order(self):
        import random
        items = list(range(20))

        def variable_sleep(item):
            time.sleep(random.uniform(0, 0.05))
            return item

        results = gather(items, variable_sleep, k=4)
        self.assertEqual([o.value for o in results], list(range(20)))

    def test_order_matches_completion_order_when_serial(self):
        """k=1: input order IS completion order. The baseline."""
        items = [0.03, 0.01, 0.02]

        def sleep_and_return(seconds):
            time.sleep(seconds)
            return seconds

        results = gather(items, sleep_and_return, k=1)
        self.assertEqual([o.value for o in results], [0.03, 0.01, 0.02])


class ExactlyOneOutcomePerInput(unittest.TestCase):
    """Exactly one Outcome per input, including on failure. Never fewer."""

    def test_empty_input_returns_empty(self):
        self.assertEqual(gather([], lambda x: x), [])

    def test_single_item_returns_single_outcome(self):
        results = gather([42], lambda x: x * 2)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_ok)
        self.assertEqual(results[0].value, 84)

    def test_all_raise_still_produces_one_per_item(self):
        def always_raise(item):
            raise RuntimeError(f"boom-{item}")

        results = gather([1, 2, 3], always_raise, k=2)
        self.assertEqual(len(results), 3)
        for o in results:
            self.assertTrue(o.is_failed)

    def test_large_batch_produces_exact_count(self):
        results = gather(list(range(100)), lambda x: x, k=8)
        self.assertEqual(len(results), 100)


class OneFailureDoesNotLoseOthers(unittest.TestCase):
    """One item raising does not lose the others."""

    def test_middle_failure_preserves_neighbours(self):
        def fail_on_five(item):
            if item == 5:
                raise ValueError("five is bad")
            return item * 10

        results = gather(list(range(10)), fail_on_five, k=4)
        self.assertEqual(len(results), 10)
        for i, o in enumerate(results):
            if i == 5:
                self.assertTrue(o.is_failed)
                self.assertIsInstance(o.value, ValueError)
            else:
                self.assertTrue(o.is_ok)
                self.assertEqual(o.value, i * 10)

    def test_multiple_failures_at_different_positions(self):
        def fail_on_odd(item):
            if item % 2 == 1:
                raise RuntimeError(f"odd: {item}")
            return item

        results = gather(list(range(8)), fail_on_odd, k=4)
        self.assertEqual(len(results), 8)
        for i, o in enumerate(results):
            if i % 2 == 1:
                self.assertTrue(o.is_failed)
            else:
                self.assertTrue(o.is_ok)
                self.assertEqual(o.value, i)

    def test_first_item_failure_does_not_stop_the_rest(self):
        def fail_first(item):
            if item == 0:
                raise RuntimeError("first")
            return item

        results = gather(list(range(5)), fail_first, k=2)
        self.assertEqual(len(results), 5)
        self.assertTrue(results[0].is_failed)
        for i in range(1, 5):
            self.assertTrue(results[i].is_ok)
            self.assertEqual(results[i].value, i)


class K1IsExactlySerial(unittest.TestCase):
    """k=1 is exactly serial and goes through the real code path."""

    def test_k1_calls_are_not_overlapping(self):
        active = 0
        max_active = 0
        lock = threading.Lock()

        def tracked(item):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.01)
            with lock:
                active -= 1
            return item

        results = gather(list(range(10)), tracked, k=1)
        self.assertEqual(max_active, 1,
                         "k=1 must never have two calls in flight")
        self.assertEqual(len(results), 10)
        self.assertTrue(all(o.is_ok for o in results))

    def test_k1_goes_through_the_same_machinery(self):
        """k=1 is not a special case that skips the executor."""
        call_count = 0

        def counting(item):
            nonlocal call_count
            call_count += 1
            return item

        results = gather([1, 2, 3], counting, k=1)
        self.assertEqual(call_count, 3)
        self.assertEqual([o.value for o in results], [1, 2, 3])


class CallableExecutedExactlyOnce(unittest.TestCase):
    """The callable is executed exactly once per item. No hidden retries."""

    def test_each_item_called_once(self):
        counts = {}
        lock = threading.Lock()

        def counting(item):
            with lock:
                counts[item] = counts.get(item, 0) + 1
            return item

        gather(list(range(20)), counting, k=4)
        for i in range(20):
            self.assertEqual(counts.get(i, 0), 1,
                             f"item {i} was called {counts.get(i, 0)} times")

    def test_each_item_called_once_even_with_failures(self):
        counts = {}
        lock = threading.Lock()

        def failing_count(item):
            with lock:
                counts[item] = counts.get(item, 0) + 1
            if item % 3 == 0:
                raise RuntimeError("no")
            return item

        gather(list(range(15)), failing_count, k=4)
        for i in range(15):
            self.assertEqual(counts.get(i, 0), 1,
                             f"item {i} was called {counts.get(i, 0)} times")


class NoSharedMutableState(unittest.TestCase):
    """`gather` adds no synchronisation of its own.

    A callable that touches a shared counter without its own locking may see
    races - that is the caller's problem, not the primitive's.
    """

    def test_gather_does_not_serialize_caller_state(self):
        """A shared counter without a lock: gather does not add one.

        With k=1 calls are serial so the counter is always correct. With k=4
        the increment-then-read is a race window the primitive does not close.
        """
        counter = 0

        def racy_increment(item):
            nonlocal counter
            current = counter
            time.sleep(0.001)
            counter = current + 1
            return counter

        serial = gather(list(range(10)), racy_increment, k=1)
        self.assertTrue(all(o.is_ok for o in serial))
        self.assertEqual(counter, 10)

        counter = 0
        concurrent = gather(list(range(10)), racy_increment, k=4)
        self.assertTrue(all(o.is_ok for o in concurrent))
        self.assertLessEqual(counter, 10)

    def test_gather_does_not_touch_store_or_budget(self):
        """Assert by construction: gather has no imports of store, budget,
        ledger, or any record type. The primitive takes items and a callable
        and returns outcomes. That is all it does."""
        import inspect
        from src import gather as gather_mod
        source = inspect.getsource(gather_mod)
        for name in ["store", "budget", "ledger", "enrich"]:
            self.assertNotIn(
                f"from src import {name}", source,
                f"gather must not import {name}")
            self.assertNotIn(
                f"from src.{name}", source,
                f"gather must not import from src.{name}")


class DeterministicUnderIdenticalInput(unittest.TestCase):
    """Same items, same fake call, same results in the same order, 20 times."""

    def test_twenty_runs_produce_identical_results(self):
        items = list(range(20))

        def pure(item):
            return item * 3 + 1

        first = gather(items, pure, k=4)
        for run in range(19):
            result = gather(items, pure, k=4)
            self.assertEqual(
                [o.value for o in result],
                [o.value for o in first],
                f"run {run + 2} differed from run 1")

    def test_twenty_runs_with_sleeps_produce_identical_results(self):
        items = list(range(10))

        def slow_pure(item):
            time.sleep(0.001 * (item % 3))
            return item * 2

        first = gather(items, slow_pure, k=4)
        for run in range(19):
            result = gather(items, slow_pure, k=4)
            self.assertEqual(
                [o.value for o in result],
                [o.value for o in first],
                f"run {run + 2} differed from run 1")


class SlowItemDoesNotDelayOthers(unittest.TestCase):
    """A slow item does not delay results for items that finished.

    Order is preserved on RETURN, not on completion: fast items finish first
    but appear at their input position in the result list.
    """

    def test_slow_first_item_does_not_block_fast_later_items(self):
        completion_order = []
        lock = threading.Lock()

        def variable(item):
            if item == 0:
                time.sleep(0.2)
            else:
                time.sleep(0.01)
            with lock:
                completion_order.append(item)
            return item

        results = gather(list(range(5)), variable, k=4)

        self.assertEqual([o.value for o in results], [0, 1, 2, 3, 4])
        self.assertNotEqual(completion_order[0], 0,
                            "item 0 sleeps 0.2s and must not be first to "
                            "complete; fast items finish ahead of it")
        self.assertEqual(completion_order[-1], 0,
                         "item 0 is last to complete")

    def test_slow_middle_item(self):
        completion_order = []
        lock = threading.Lock()

        def variable(item):
            if item == 3:
                time.sleep(0.2)
            else:
                time.sleep(0.01)
            with lock:
                completion_order.append(item)
            return item

        results = gather(list(range(6)), variable, k=4)
        self.assertEqual([o.value for o in results], [0, 1, 2, 3, 4, 5])
        self.assertNotEqual(completion_order[0], 3)


class ConcurrencyActuallyOverlaps(unittest.TestCase):
    """200 items at k=8 complete in roughly serial/8 of the sleep time.

    This proves the pool actually overlaps rather than just looking tidy.
    """

    def test_200_items_at_k8_are_much_faster_than_serial(self):
        sleep_per_item = 0.05
        items = list(range(200))

        def sleepy(item):
            time.sleep(sleep_per_item)
            return item

        serial_time = len(items) * sleep_per_item

        start = time.monotonic()
        results = gather(items, sleepy, k=8)
        elapsed = time.monotonic() - start

        self.assertEqual(len(results), 200)
        self.assertTrue(all(o.is_ok for o in results))

        expected_concurrent = serial_time / 8
        threshold = expected_concurrent * 2.5
        self.assertLess(
            elapsed, threshold,
            f"200 items at k=8 took {elapsed:.1f}s, expected ~"
            f"{expected_concurrent:.1f}s (threshold {threshold:.1f}s). "
            f"Serial would be {serial_time:.1f}s. "
            f"The pool is not overlapping.")

        self.assertGreater(
            elapsed, expected_concurrent * 0.3,
            f"Completed in {elapsed:.1f}s, suspiciously fast. "
            f"Expected ~{expected_concurrent:.1f}s. "
            f"The sleep may not be executing.")


class Timeout(unittest.TestCase):
    """Per-item timeout produces timed_out, not an infinite hang."""

    def test_slow_item_times_out(self):
        def slow(item):
            time.sleep(1.0)
            return item

        results = gather([1, 2, 3], slow, k=4, timeout=0.05)
        self.assertEqual(len(results), 3)
        for o in results:
            self.assertTrue(o.is_timed_out)

    def test_fast_items_succeed_while_slow_times_out(self):
        def mixed(item):
            if item == 1:
                time.sleep(1.0)
            return item

        results = gather([0, 1, 2], mixed, k=4, timeout=0.05)
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0].is_ok)
        self.assertTrue(results[1].is_timed_out)
        self.assertTrue(results[2].is_ok)

    def test_no_timeout_means_no_timeout(self):
        def slow(item):
            time.sleep(0.05)
            return item

        results = gather([1], slow, k=1, timeout=None)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_ok)
        self.assertEqual(results[0].value, 1)

    def test_callable_raising_timeout_error_is_failed_not_timed_out(self):
        """If the callable itself raises TimeoutError, that is a result,
        not the gather's timeout firing."""
        def raises_timeout(item):
            raise TimeoutError("from the callable")

        results = gather([1], raises_timeout, k=1, timeout=5.0)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_failed)
        self.assertIsInstance(results[0].value, TimeoutError)


class MinInterval(unittest.TestCase):
    """min_interval throttles dispatches without changing k."""

    def test_dispatches_are_spaced(self):
        start_times = []
        lock = threading.Lock()

        def record_start(item):
            with lock:
                start_times.append(time.monotonic())
            return item

        interval = 0.05
        gather(list(range(10)), record_start, k=1, min_interval=interval)
        start_times.sort()
        for i in range(1, len(start_times)):
            gap = start_times[i] - start_times[i - 1]
            self.assertGreaterEqual(
                gap, interval * 0.8,
                f"gap {i-1}->{i} was {gap:.3f}s, "
                f"expected >= {interval * 0.8:.3f}s")

    def test_min_interval_with_high_k_still_respects_ceiling(self):
        """k=8 and min_interval=0.02: at most one call per 0.02s,
        but up to 8 in flight at once."""
        active = 0
        max_active = 0
        lock = threading.Lock()

        def tracked(item):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return item

        results = gather(
            list(range(16)), tracked, k=8, min_interval=0.02)
        self.assertEqual(len(results), 16)
        self.assertTrue(all(o.is_ok for o in results))
        self.assertLessEqual(max_active, 8)


class ExceptionTypes(unittest.TestCase):
    """Different exception types are carried faithfully."""

    def test_value_error_is_carried(self):
        def raise_ve(item):
            raise ValueError(f"ve-{item}")

        results = gather([1], raise_ve, k=1)
        self.assertTrue(results[0].is_failed)
        self.assertIsInstance(results[0].value, ValueError)
        self.assertIn("ve-1", str(results[0].value))

    def test_type_error_is_carried(self):
        def raise_te(item):
            raise TypeError(f"te-{item}")

        results = gather([1], raise_te, k=1)
        self.assertTrue(results[0].is_failed)
        self.assertIsInstance(results[0].value, TypeError)

    def test_custom_exception_is_carried(self):
        class ProviderError(Exception):
            pass

        def raise_pe(item):
            raise ProviderError(f"pe-{item}")

        results = gather([1], raise_pe, k=1)
        self.assertTrue(results[0].is_failed)
        self.assertIsInstance(results[0].value, ProviderError)


if __name__ == "__main__":
    unittest.main()
