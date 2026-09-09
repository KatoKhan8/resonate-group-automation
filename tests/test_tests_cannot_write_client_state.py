"""The incident, reproduced, and both barriers that now stop it.

WHAT HAPPENED. `tests/base.py::ProviderTest` isolated the network and the
credentials and left the store pointing wherever it already pointed.
`tests/test_signals.py::TheEstateWalksReadTheSignalFileOnce` inherited it,
called `store.save()` with twenty-five `walk-N` fixtures, and because
`store.save` replaces the whole file rather than appending, a real client
estate - fifty Productive records with ICP verdicts, contacts, events and a
spend ledger - was overwritten by test companies called "Co 0". The loss was
total: `work/` is gitignored, no backup predated it, and the waterfall and
event logs live *on the record*, so they died with it.

TWO BARRIERS, deliberately independent:

  1. `ProviderTest` now points the store at a throwaway directory, which is
     what its module docstring always claimed. That closes the known way in.

  2. `store` refuses any write to the real `work/` directory while a test is
     running, whatever the test forgot. That closes the class.

The second exists because the first can be forgotten again. Forty-two classes
inherit `ProviderTest`; the forty-third might not, or might not call
`super().setUp()`, and isolation that depends on remembering is isolation
that fails the same way twice.

`under_test()` reads `sys.modules` rather than an environment marker a harness
has to set, because the thing being prevented is a forgotten setup step and
the guard may not have a setup step of its own.
"""
import os
import shutil
import tempfile
import unittest

from src import store
from tests.base import ProviderTest


class TheSecondBarrierRefusesRealState(unittest.TestCase):
    """Barrier 2 alone, with no isolation in place at all."""

    def setUp(self):
        self._queue = os.environ.get("QUEUE")
        os.environ.pop("QUEUE", None)      # resolve to the real work/

    def tearDown(self):
        if self._queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._queue

    def test_the_real_queue_is_where_this_would_have_written(self):
        """Anchors the test: without the guard this path is the live file."""
        self.assertEqual(os.path.dirname(store.queue_path()),
                         store.PRODUCTION_WORK)

    def test_saving_real_client_state_from_a_test_is_refused(self):
        with self.assertRaises(store.ProductionStateUnderTest):
            store.save([store.new_record("would-have-clobbered", "domains",
                                         "productive", "X", "x.test")])

    def test_the_refusal_says_how_to_fix_it(self):
        try:
            store.save([])
        except store.ProductionStateUnderTest as e:
            self.assertIn("use_directory", str(e))
        else:
            self.fail("the write was not refused")

    def test_under_test_is_true_here_and_needs_no_setup(self):
        self.assertTrue(store.under_test())


class TheSentinelSurvives(ProviderTest):
    """The incident itself: an exposed ProviderTest subclass, a real-state
    sentinel, and the same `store.save` call that destroyed the estate."""

    def test_a_provider_test_writes_only_to_its_throwaway(self):
        # Where the real queue is, and what is in it right now.
        real = os.path.join(store.PRODUCTION_WORK, "queue.jsonl")
        before = None
        if os.path.exists(real):
            with open(real, "rb") as f:
                before = f.read()

        # Barrier 1: setUp already moved us off it.
        self.assertNotEqual(os.path.dirname(store.queue_path()),
                            store.PRODUCTION_WORK,
                            "ProviderTest did not isolate the store")

        # The exact call that caused the incident.
        store.save([store.new_record("walk-0", "domains", "productive",
                                     "Co 0", "co0.test")])

        # The sentinel survived, byte for byte.
        if before is not None:
            with open(real, "rb") as f:
                self.assertEqual(f.read(), before,
                                 "a test wrote the real client queue")

        # And the write landed in the throwaway.
        self.assertEqual([r["id"] for r in store.load()], ["walk-0"])

    def test_the_throwaway_is_empty_for_each_test(self):
        """No leakage between tests sharing the base class."""
        self.assertEqual(store.load(), [])


class BothBarriersAreIndependent(ProviderTest):

    def test_barrier_two_still_fires_if_barrier_one_is_undone(self):
        """Simulates the forty-third subclass that forgets to isolate."""
        os.environ.pop("QUEUE", None)
        self.assertEqual(os.path.dirname(store.queue_path()),
                         store.PRODUCTION_WORK)
        with self.assertRaises(store.ProductionStateUnderTest):
            store.save([])

    def test_an_isolated_directory_is_never_refused(self):
        """Otherwise the guard refuses every test and proves nothing."""
        tmp = tempfile.mkdtemp(prefix="rga-barrier-")
        try:
            store.use_directory(os.path.join(tmp, "work"))
            store.save([store.new_record("ok", "domains", "c", "C", "c.test")])
            self.assertEqual([r["id"] for r in store.load()], ["ok"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


class TheBarrierCoversEveryStateFileAndNotJustTheQueue(unittest.TestCase):
    """`work/` holds twenty-odd state files; the guard used to cover one.

    Found after a machine restart, by diffing `work/` against a backup taken
    before a suite run: the run had added sixteen test-created draft rows to
    the real `report-drafts.jsonl`, and `replywatch.json` held
    `RuntimeError: still on fire` from `tests/test_replywatch.py`. The queue
    was untouched, because the queue was the only file behind the barrier.

    That mattered beyond the debris. `PRODUCT-GAPS.md` section 22 item 9 cites
    `work/replywatch.json` as evidence that reply detection is down - a red
    team reading test fixtures as a production signal.

    Barrier 1 (`store.use_directory`) always covered these files: they are all
    in `STATE_OVERRIDES`. Barrier 2 did not, so any test that forgot barrier 1
    reached real client state. The two barriers are supposed to be
    independent, and one of them covering a twenty-second of the other is not
    independence.
    """

    def setUp(self):
        self._queue = os.environ.get("QUEUE")
        os.environ.pop("QUEUE", None)          # resolve to the real work/
        self._saved = {}
        for name in store.STATE_OVERRIDES:
            self._saved[name] = os.environ.get(name)
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        if self._queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._queue

    def _is_real(self, path):
        """Anchors each case: without the guard this is the live file."""
        self.assertEqual(os.path.dirname(os.path.abspath(path)),
                         store.PRODUCTION_WORK)

    def test_write_jsonl_refuses_the_real_directory(self):
        """The writer behind campaigns, drafts, senders, signals, tag outbox."""
        target = os.path.join(store.PRODUCTION_WORK, "guard-probe.jsonl")
        self._is_real(target)
        with self.assertRaises(store.ProductionStateUnderTest):
            store.write_jsonl(target, [{"would": "have clobbered"}])
        self.assertFalse(os.path.exists(target))

    def test_a_report_draft_cannot_be_written_into_real_client_state(self):
        """The file that was actually polluted, through its own module."""
        from src import reportdraft
        self._is_real(reportdraft.path())
        with self.assertRaises(store.ProductionStateUnderTest):
            reportdraft.save([{"id": "draft-would-have-landed"}])

    def test_the_reply_watcher_cannot_report_health_into_real_state(self):
        """The file whose fixture content was read as a production signal."""
        from src import replywatch
        self._is_real(replywatch.status_path())
        with self.assertRaises(store.ProductionStateUnderTest):
            replywatch._write_status("emailbison", {"healthy": False,
                                                    "last_error": "fixture"})

    def test_the_mx_cache_cannot_be_written_into_real_state(self):
        from src import mx
        self._is_real(mx.cache_path())
        with self.assertRaises(store.ProductionStateUnderTest):
            mx.save_cache({"example.test": {"mx": []}})

    def test_a_poller_checkpoint_cannot_be_written_into_real_state(self):
        """A fixture cursor here silently skips real replies on the next poll."""
        from src import poller
        self._is_real(poller.checkpoint_path())
        with self.assertRaises(store.ProductionStateUnderTest):
            poller.save_checkpoint("emailbison", "fixture-cursor")

    def test_every_state_override_names_a_file_the_guard_would_refuse(self):
        """The set, not the five above.

        `STATE_OVERRIDES` is the repository's own list of files written beside
        the queue, and `test_invariants.py` already fails a module missing from
        it. So the list is trustworthy, and the guard has to refuse the whole
        directory rather than an enumerated subset - which is what makes a
        newly added state file covered on the day it is added.
        """
        for name in store.STATE_OVERRIDES:
            with self.subTest(override=name):
                target = os.path.join(store.PRODUCTION_WORK,
                                      f"{name.lower()}.jsonl")
                with self.assertRaises(store.ProductionStateUnderTest):
                    store.refuse_production_write(target)

    def test_the_guard_still_permits_an_isolated_directory(self):
        """The refusal must be about the location, not about being a test."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        store.use_directory(tmp)
        target = os.path.join(tmp, "report-drafts.jsonl")
        store.write_jsonl(target, [{"id": "fine"}])
        self.assertEqual(store.read_jsonl(target), [{"id": "fine"}])
