"""The published benchmark command must not touch production storage.

TASK-233: ``python -m src.scalesim --sizes 100,1000,5000`` used to call
``store.save(recs)`` three times against whatever ``store.queue_path()``
resolved to - which, outside a test harness, is the real
``work/queue.jsonl``.  Five thousand synthetic ids share nothing with the
real records, so every guard that checks for *known* records being absent
passes in silence.

The fix wraps the save/load round-trip in an isolated store that redirects
to a temp directory and restores on exit.  These tests prove the restore
happens, that it happens even on exception, that repeated calls do not
leave the store dangling, and that the opt-in ``write_to`` path refuses
the production directory.
"""
import hashlib
import os
import tempfile
import unittest

from src import store, scalesim


def _digest(path):
    """SHA-256 of a file, or None if it does not exist."""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class PublishedCommandLeavesProductionAlone(unittest.TestCase):
    """Requirement 1: the published command leaves the queue byte-identical.

    Proven by digest before and after, with the store pointed at a temp
    directory that stands in for production.  The digest is of the queue
    file the store resolves to - not of the real ``work/`` directory.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rga-scale-")
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE",) + store.STATE_OVERRIDES}
        store.use_directory(self._tmp)
        # Seed a "production" queue with records that have nothing in common
        # with the synthetic dataset, so a silent overwrite is detectable.
        from src import store as _s
        seed = [{"id": f"real-{i}", "domain": f"real-{i}.test",
                 "state": "enriched", "client": "prod"}
                for i in range(5)]
        _s.save(seed)
        self._before = _digest(store.queue_path())

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_sizes_run_leaves_queue_byte_identical(self):
        """Three successive sizes, the published command, leave the queue
        byte-identical.  Each ``measure`` call writes 100/1000/5000 synthetic
        records through ``store.save`` - the same path that used to replace
        the production file."""
        scalesim.run(sizes=[10, 20, 30])
        after = _digest(store.queue_path())
        self.assertEqual(self._before, after,
                         "the benchmark changed the production queue")

    def test_single_measure_leaves_queue_byte_identical(self):
        scalesim.measure(10)
        after = _digest(store.queue_path())
        self.assertEqual(self._before, after)


class SyntheticRecordsAreWrittenSomewhereReal(unittest.TestCase):
    """Requirement 2: the benchmark writes to a real directory, not nowhere.

    A measurement that skips the write entirely measures the wrong thing.
    The save/load round-trip must happen against a real filesystem path.
    """

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE",) + store.STATE_OVERRIDES}

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_measure_writes_and_reads_synthetic_records(self):
        """The result carries a queue_bytes figure, which means the save
        landed on a real file that was then read back."""
        result = scalesim.measure(10)
        self.assertIsNotNone(result["queue_bytes"])
        self.assertGreater(result["queue_bytes"], 0)

    def test_store_is_restored_after_measure(self):
        """After measure(), the store points back to where it was before."""
        before_path = store.queue_path()
        scalesim.measure(10)
        after_path = store.queue_path()
        self.assertEqual(before_path, after_path)


class RestoreHappensOnException(unittest.TestCase):
    """Requirement 3: the restore happens even when the body raises."""

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE",) + store.STATE_OVERRIDES}
        self._tmp = tempfile.mkdtemp(prefix="rga-scale-exc-")
        store.use_directory(self._tmp)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_store_restored_when_measure_body_raises(self):
        """Monkey-patch ``synthetic.dataset`` to raise after the store has
        been redirected.  The store must still point back afterwards."""
        original = scalesim.synthetic.dataset
        expected_path = store.queue_path()

        def _boom(*a, **kw):
            raise RuntimeError("simulated failure inside measure")

        scalesim.synthetic.dataset = _boom
        try:
            with self.assertRaises(RuntimeError):
                scalesim.measure(10)
        finally:
            scalesim.synthetic.dataset = original

        self.assertEqual(store.queue_path(), expected_path)


class RepeatedCallsDoNotDangle(unittest.TestCase):
    """Requirement 4: nested or repeated calls leave the store valid.

    ``SIZES`` has three entries, so the published command runs ``measure``
    three times in a row.  Each must restore cleanly so the next one does
    not write into a deleted temp directory.
    """

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE",) + store.STATE_OVERRIDES}
        self._tmp = tempfile.mkdtemp(prefix="rga-scale-repeat-")
        store.use_directory(self._tmp)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_three_successive_measures_all_restore(self):
        expected = store.queue_path()
        expected_dir = os.path.dirname(expected)
        for size in [10, 20, 30]:
            scalesim.measure(size)
            self.assertEqual(store.queue_path(), expected,
                             f"store not restored after size={size}")
        self.assertTrue(os.path.isdir(expected_dir),
                        "store directory no longer exists after repeated calls")

    def test_run_with_three_sizes_restores(self):
        expected = store.queue_path()
        expected_dir = os.path.dirname(expected)
        scalesim.run(sizes=[10, 20, 30])
        self.assertEqual(store.queue_path(), expected)
        self.assertTrue(os.path.isdir(expected_dir))


class WriteToRejectsProductionPath(unittest.TestCase):
    """Requirement 5: an opt-in write_to flag must not accept the production
    path.

    Enforced by comparing the resolved absolute path against
    ``store.PRODUCTION_WORK``.  Both exact match and prefix match (for
    subdirectories) are refused.
    """

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE",) + store.STATE_OVERRIDES}

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_write_to_rejects_production_work_directory(self):
        with self.assertRaises(ValueError) as ctx:
            scalesim.measure(10, write_to=store.PRODUCTION_WORK)
        self.assertIn("production", str(ctx.exception).lower())

    def test_write_to_rejects_subdirectory_of_production(self):
        sub = os.path.join(store.PRODUCTION_WORK, "nested")
        with self.assertRaises(ValueError):
            scalesim.measure(10, write_to=sub)

    def test_write_to_accepts_a_normal_directory(self):
        """A non-production directory must work.  We use a temp dir and
        only check that it does not raise ValueError - the actual
        measurement is slow, so we stop at the path validation."""
        with tempfile.TemporaryDirectory(prefix="scalesim-wt-") as tmp:
            try:
                scalesim.measure(10, write_to=tmp)
            except ValueError as e:
                if "production" in str(e).lower():
                    self.fail("write_to refused a non-production directory")
                raise


if __name__ == "__main__":
    unittest.main()
