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
import subprocess
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


class TheMainCheckoutIsBehindTheBarrierToo(unittest.TestCase):
    """TASK-973. The barrier was aimed at the tree it was imported from.

    `store.PRODUCTION_WORK` is `ROOT/work`, and `ROOT` is the tree the module
    was imported from. `work/` is gitignored, so every worktree has its own
    empty one - and every suite in this project's merge gate runs from a
    worktree. Measured 2026-10-03, from a gate worktree, with the barrier live:

        this worktree's work/       REFUSED
        MAIN checkout's work/       ALLOWED
        MAIN work/campaigns.jsonl   ALLOWED

    So for every run that has ever gated a merge, the guard watched an empty
    directory while the file it exists to defend - the OS authority,
    `work/campaigns.jsonl` in the MAIN checkout - sat outside it. What held
    instead was `use_directory`, which pops every `STATE_OVERRIDES` entry for
    each `ProviderTest`: the estate was defended by the layer nobody
    advertised as the barrier, while the barrier watched an empty directory.

    BOTH directories are refused now, never one instead of the other.
    """

    def setUp(self):
        store.reset_main_work_cache()
        self.addCleanup(store.reset_main_work_cache)

    @staticmethod
    def _git_answer():
        """What git says the common dir is, asked independently of `store`."""
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=False)
        value = (out.stdout or "").strip()
        return value if out.returncode == 0 and value else None

    def test_the_main_checkouts_work_directory_is_refused(self):
        """The defect itself, as an assertion."""
        common = self._git_answer()
        self.assertTrue(
            common and os.path.isabs(common),
            "git could not answer absolutely, so this would measure "
            "nothing: %r" % (common,))
        main = os.path.abspath(os.path.join(os.path.dirname(common), "work"))
        with self.assertRaises(store.ProductionStateUnderTest):
            store.refuse_production_write(main)
        with self.assertRaises(store.ProductionStateUnderTest):
            store.refuse_production_write(
                os.path.join(main, "campaigns.jsonl"))

    def test_the_invoking_trees_own_work_is_still_refused(self):
        """Both, not either. Trading one for the other moves the hole."""
        with self.assertRaises(store.ProductionStateUnderTest):
            store.refuse_production_write(store.PRODUCTION_WORK)
        with self.assertRaises(store.ProductionStateUnderTest):
            store.refuse_production_write(
                os.path.join(store.PRODUCTION_WORK, "queue.jsonl"))

    def test_an_isolated_tempdir_is_still_writable(self):
        """The control a 'refuse everything' barrier would fail.

        Without it, the cheapest way to pass every other test in this class is
        to refuse unconditionally - which would red the whole suite instead,
        forty minutes later rather than now.
        """
        tmp = tempfile.mkdtemp(prefix="barrier-control-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        store.refuse_production_write(os.path.join(tmp, "queue.jsonl"))

    def test_both_directories_are_named_by_the_seam(self):
        """`protected_directories` is what the barrier reads, so assert it."""
        dirs = store.protected_directories()
        self.assertIn(os.path.abspath(store.PRODUCTION_WORK), dirs)
        main = store.main_checkout_work()
        self.assertTrue(main, "git could not answer; nothing to assert")
        self.assertIn(main, dirs)

    def test_a_relative_answer_from_git_is_refused_rather_than_resolved(self):
        """`abspath` would resolve it against the caller's cwd.

        From a worktree that is the worktree, which is the per-tree barrier
        this change exists to end. `--path-format=absolute` should make it
        unreachable; this asserts the check that does not trust the flag.
        """
        class _Relative:
            returncode = 0
            stdout = ".git\n"
            stderr = ""

        real = store.subprocess.run
        store.subprocess.run = lambda *a, **k: _Relative()
        self.addCleanup(setattr, store.subprocess, "run", real)
        self.assertIsNone(store._git_common_dir())

    def test_a_failure_to_resolve_is_never_cached(self):
        """Otherwise one ask from outside a repository disables half the barrier.

        Permanently, for the rest of the process, and silently - no later
        correct ask could undo it.
        """
        class _Failed:
            returncode = 128
            stdout = ""
            stderr = "fatal: not a git repository"

        real = store.subprocess.run
        store.subprocess.run = lambda *a, **k: _Failed()
        try:
            self.assertIsNone(store.main_checkout_work())
            self.assertEqual(store._MAIN_WORK_BY_CWD, {})
        finally:
            store.subprocess.run = real
        self.assertTrue(store.main_checkout_work(),
                        "the failure poisoned the cache")

    def test_the_resolution_is_cached_rather_than_a_subprocess_per_write(self):
        """Measured 2026-10-03: 25.8 ms resolved against 2.3 us cached.

        A factor of about eleven thousand, so resolving per write would add
        minutes of pure subprocess across a suite. Asserted by COUNTING the
        resolutions, not by timing, which would be a flake.
        """
        tmp = tempfile.mkdtemp(prefix="barrier-count-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        target = os.path.join(tmp, "queue.jsonl")
        calls = []
        real = store.subprocess.run

        def counted(*a, **k):
            calls.append(a)
            return real(*a, **k)

        store.subprocess.run = counted
        self.addCleanup(setattr, store.subprocess, "run", real)
        for _ in range(50):
            store.refuse_production_write(target)
        self.assertEqual(len(calls), 1,
                         "fifty writes cost %d git resolutions" % len(calls))

    def test_the_cache_does_not_outlive_a_use_directory_redirect(self):
        """The operator's condition on TASK-973, proven by EFFECT.

        A throwaway repository is made and entered, so its `work/` is what the
        resolver protects. Then git is broken, which leaves the CACHE as the
        only thing that could still answer - and the proof has two halves:
        without a redirect the stale answer is still served, so the cache is
        real and this test is not vacuous; after `use_directory` it is not, so
        the redirect dropped it and the next ask resolved afresh.
        """
        repo = tempfile.mkdtemp(prefix="barrier-repo-")
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        made = subprocess.run(["git", "init", "-q", repo],
                              capture_output=True, text=True, check=False)
        self.assertEqual(made.returncode, 0, made.stderr)

        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        os.chdir(repo)
        store.reset_main_work_cache()

        target = os.path.join(os.getcwd(), "work", "queue.jsonl")
        with self.assertRaises(store.ProductionStateUnderTest):
            store.refuse_production_write(target)
        self.assertEqual(len(store._MAIN_WORK_BY_CWD), 1,
                         "nothing was cached, so this test proves nothing")

        os.rename(os.path.join(repo, ".git"), os.path.join(repo, ".git-off"))
        self.assertIsNone(
            store._git_common_dir(),
            "git still answers here, so the rest would measure nothing")

        # CONTROL: the stale entry is still served, so the refusal below is
        # about the cache rather than about git having stopped answering.
        with self.assertRaises(store.ProductionStateUnderTest):
            store.refuse_production_write(target)

        tmp = tempfile.mkdtemp(prefix="barrier-redirect-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.addCleanup(store.use_directory(tmp))
        self.assertEqual(store._MAIN_WORK_BY_CWD, {},
                         "the redirect did not drop the cached resolution")
        store.refuse_production_write(target)
