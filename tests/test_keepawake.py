"""The keep-awake request, and the three ways it could silently do nothing.

The interesting assertions are not "it returns True". They are:

  * a `0` return from the API is a FAILURE, not a previous state of zero -
    this is the one that would otherwise report success for ever;
  * `ES_DISPLAY_REQUIRED` is never asked for, so a closed laptop stays dark;
  * the request is per-thread, so `holding()` from another thread is False
    even while the process-wide flag says held.

The last one is the defect this module exists to make visible. A supervisor
that acquires on a worker thread which then exits has no request and no
symptom until the machine sleeps mid-run.
"""
import threading
import unittest

from src import keepawake


class FakeApi:
    """Stands in for `SetThreadExecutionState`. Records every flag word."""

    def __init__(self, returns=0x80000000):
        self.calls = []
        self._returns = returns

    def __call__(self, flags):
        value = int(getattr(flags, "value", flags))
        self.calls.append(value)
        if callable(self._returns):
            return self._returns(value)
        return self._returns


class KeepAwakeTest(unittest.TestCase):

    def setUp(self):
        keepawake.reset_for_test()
        self.addCleanup(keepawake.reset_for_test)


class WhatItAsksFor(KeepAwakeTest):

    def test_it_asks_for_continuous_and_system_required(self):
        api = FakeApi()
        self.assertTrue(keepawake.acquire(api=api, system="Windows"))
        self.assertEqual(api.calls, [keepawake.ES_CONTINUOUS
                                     | keepawake.ES_SYSTEM_REQUIRED])

    def test_it_never_asks_for_the_display(self):
        """A display request on a closed laptop is a burned panel."""
        api = FakeApi()
        keepawake.acquire(api=api, system="Windows")
        keepawake.release(api=api, system="Windows")
        for flags in api.calls:
            self.assertFalse(flags & keepawake.ES_DISPLAY_REQUIRED,
                             "ES_DISPLAY_REQUIRED was requested")
        self.assertFalse(keepawake.status()["display_request"])

    def test_release_clears_the_requirement_but_stays_continuous(self):
        api = FakeApi()
        keepawake.acquire(api=api, system="Windows")
        self.assertTrue(keepawake.release(api=api, system="Windows"))
        self.assertEqual(api.calls[-1], keepawake.ES_CONTINUOUS)
        self.assertFalse(keepawake.holding())


class AZeroReturnIsAFailure(KeepAwakeTest):
    """The defect this project keeps shipping: a call nobody read the result of."""

    def test_zero_is_not_success(self):
        api = FakeApi(returns=0)
        self.assertFalse(keepawake.acquire(api=api, system="Windows"))
        self.assertFalse(keepawake.holding())

    def test_and_it_says_why(self):
        api = FakeApi(returns=0)
        keepawake.acquire(api=api, system="Windows")
        self.assertIn("returned 0", keepawake.status()["error"])

    def test_an_exception_is_reported_not_raised(self):
        def boom(_flags):
            raise OSError("no kernel32 here")
        self.assertFalse(keepawake.acquire(api=boom, system="Windows"))
        self.assertIn("OSError", keepawake.status()["error"])


class ItIsPerThread(KeepAwakeTest):

    def test_holding_is_false_from_a_different_thread(self):
        api = FakeApi()
        self.assertTrue(keepawake.acquire(api=api, system="Windows"))
        self.assertTrue(keepawake.holding())

        seen = {}

        def other():
            seen["holding"] = keepawake.holding()
            seen["same_thread"] = keepawake.status()["same_thread"]

        thread = threading.Thread(target=other)
        thread.start()
        thread.join()

        self.assertFalse(seen["holding"],
                         "a request taken on another thread was reported live")
        self.assertFalse(seen["same_thread"])


class OffWindows(KeepAwakeTest):

    def test_it_refuses_rather_than_pretending(self):
        api = FakeApi()
        self.assertFalse(keepawake.acquire(api=api, system="Linux"))
        self.assertEqual(api.calls, [], "the Windows API was called off Windows")
        self.assertFalse(keepawake.holding())
        self.assertEqual(keepawake.status()["error"], "not Windows")


class TheStatusLineDoesNotOverclaim(KeepAwakeTest):

    def test_it_says_what_it_does_not_cover(self):
        """The machine died to a reboot. Nobody may read `held: true` as safe."""
        api = FakeApi()
        keepawake.acquire(api=api, system="Windows")
        covers = keepawake.status()["covers"]
        self.assertIn("idle sleep", covers)
        self.assertIn("NOT", covers)
        self.assertIn("restart", covers)


class TheContextManager(KeepAwakeTest):

    def test_it_reports_refusal_without_raising(self):
        api = FakeApi(returns=0)
        with keepawake.KeepAwake(api=api, system="Windows") as awake:
            self.assertFalse(awake.entered_ok)
            self.assertIn("returned 0", awake.error)

    def test_it_releases_on_the_way_out(self):
        api = FakeApi()
        with keepawake.KeepAwake(api=api, system="Windows") as awake:
            self.assertTrue(awake.entered_ok)
            self.assertTrue(keepawake.holding())
        self.assertFalse(keepawake.holding())
        self.assertEqual(api.calls[-1], keepawake.ES_CONTINUOUS)


if __name__ == "__main__":
    unittest.main()
