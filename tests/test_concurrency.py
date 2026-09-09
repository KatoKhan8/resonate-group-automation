"""Two writers must not silently overwrite each other. Task G.

The store was already safe against a crash: it writes a temp file and renames.
It was not safe against a second process, and this is the smallest mechanism
that fixes that for a CLI without introducing a database.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from src import store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def record(rid, company="X"):
    return store.new_record(rid, "domains", "productive", company, f"{rid}.test")


class LockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-lock-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev = os.environ.get("QUEUE"), os.environ.get("QUEUE_LOCK_TIMEOUT")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        for name, value in zip(("QUEUE", "QUEUE_LOCK_TIMEOUT"), self._prev):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestTheLockItself(LockTest):
    def test_the_lock_is_released_when_the_block_ends(self):
        with store.lock():
            self.assertTrue(os.path.exists(store.lock_path()))
        self.assertFalse(os.path.exists(store.lock_path()))

    def test_the_lock_is_released_even_when_the_block_raises(self):
        with self.assertRaises(ValueError):
            with store.lock():
                raise ValueError("boom")
        self.assertFalse(os.path.exists(store.lock_path()))

    def test_a_held_lock_makes_the_second_writer_wait_and_then_fail_cleanly(self):
        with store.lock():
            started = time.monotonic()
            with self.assertRaises(store.QueueLocked) as e:
                store.save([record("a")], timeout=0.3)
            waited = time.monotonic() - started
        self.assertGreaterEqual(waited, 0.25)
        self.assertIn("Nothing was written", str(e.exception))

    def test_a_refused_write_leaves_the_queue_exactly_as_it_was(self):
        store.save([record("first")])
        with open(self.queue, "rb") as f:
            before = f.read()
        with store.lock():
            with self.assertRaises(store.QueueLocked):
                store.save([record("second")], timeout=0.2)
        with open(self.queue, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual([r["id"] for r in store.load()], ["first"])

    def test_a_stale_lock_from_a_dead_process_is_reclaimed(self):
        os.makedirs(os.path.dirname(store.lock_path()), exist_ok=True)
        with open(store.lock_path(), "w", encoding="utf-8") as f:
            f.write("99999")
        old = time.time() - (store.LOCK_STALE_AFTER + 60)
        os.utime(store.lock_path(), (old, old))
        store.save([record("after-stale")], timeout=1)
        self.assertEqual([r["id"] for r in store.load()], ["after-stale"])

    def test_the_write_is_still_atomic(self):
        store.save([record("a"), record("b")])
        self.assertFalse(any(n.endswith(".tmp") for n in
                             os.listdir(os.path.dirname(self.queue))))


class TestContention(LockTest):
    def test_two_threads_writing_at_once_do_not_lose_a_record(self):
        store.save([record("seed")])
        errors = []

        def add(rid):
            try:
                with store.transaction() as recs:
                    time.sleep(0.02)          # widen the window on purpose
                    recs.append(record(rid))
            except Exception as e:            # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=add, args=(f"r{i}",)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        ids = sorted(r["id"] for r in store.load())
        self.assertEqual(ids, ["r0", "r1", "r2", "r3", "r4", "r5", "seed"])

    def test_a_read_modify_write_is_not_lost_under_contention(self):
        store.save([record("target")])

        def bump(note):
            with store.transaction() as recs:
                time.sleep(0.01)
                store.log(store.get("target", recs), "test", note)

        threads = [threading.Thread(target=bump, args=(f"n{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        notes = {e["note"] for e in store.get("target")["log"]}
        self.assertEqual(len({"n0", "n1", "n2", "n3", "n4"} - notes), 0)

    def test_the_queue_is_never_left_corrupt(self):
        store.save([record("seed")])

        def churn(i):
            try:
                with store.transaction() as recs:
                    recs.append(record(f"c{i}"))
            except store.QueueLocked:
                pass

        threads = [threading.Thread(target=churn, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with open(self.queue, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    json.loads(line)          # every line is still valid JSON


class TestCrossProcess(LockTest):
    """The case a thread test cannot prove: a genuinely separate process."""

    def test_a_second_process_cannot_write_while_the_lock_is_held(self):
        store.save([record("seed")])
        script = (
            "import os, sys; sys.path.insert(0, %r);"
            "os.environ['QUEUE'] = %r;"
            "from src import store;"
            "\ntry:\n"
            "    store.save([store.new_record('other', 'domains', 'productive', 'O', 'o.test')], timeout=0.3)\n"
            "    print('WROTE')\n"
            "except store.QueueLocked:\n"
            "    print('REFUSED')\n"
        ) % (ROOT, self.queue)

        with store.lock():
            result = subprocess.run([sys.executable, "-c", script],
                                    capture_output=True, text=True, cwd=ROOT,
                                    timeout=60)
        self.assertIn("REFUSED", result.stdout, result.stderr[-400:])
        self.assertEqual([r["id"] for r in store.load()], ["seed"])

    def test_a_second_process_writes_once_the_lock_is_free(self):
        store.save([record("seed")])
        script = (
            "import os, sys; sys.path.insert(0, %r);"
            "os.environ['QUEUE'] = %r;"
            "from src import store;"
            "store.save(store.load() + [store.new_record('other', 'domains', 'productive', 'O', 'o.test')]);"
            "print('WROTE')"
        ) % (ROOT, self.queue)

        result = subprocess.run([sys.executable, "-c", script],
                                capture_output=True, text=True, cwd=ROOT, timeout=60)
        self.assertIn("WROTE", result.stdout, result.stderr[-400:])
        self.assertEqual(sorted(r["id"] for r in store.load()), ["other", "seed"])


class TestEveryWriterUsesTheLock(unittest.TestCase):
    def test_the_mutating_entry_points_hold_the_lock(self):
        import inspect
        for fn in (store.save, store.append, store.patch):
            self.assertRegex(inspect.getsource(fn), r"with lock\(", fn.__name__)

    def test_the_bare_write_is_private(self):
        """No public function in `store` calls `_write` without the lock.

        Asserted over the parsed call graph rather than over the text of the
        source. The substring form of this test matched any identifier ending
        in `_write(`, so adding a guard called `refuse_production_write` to
        `write_jsonl` made it report that `write_jsonl` "writes without the
        lock" - a function that does not call `_write` at all, failing a test
        it has nothing to do with. A test that a rename can break is a test
        about spelling.
        """
        import ast
        import inspect
        import textwrap
        self.assertTrue(hasattr(store, "_write"))
        checked = 0
        for name, fn in vars(store).items():
            if name.startswith("_") or not inspect.isfunction(fn):
                continue
            if name in ("lock", "transaction"):
                continue
            tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
            called = {node.func.id for node in ast.walk(tree)
                      if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name)}
            if "_write" not in called:
                continue
            checked += 1
            self.assertIn("lock", called, f"{name} writes without the lock")
        self.assertTrue(checked, "no public writer was examined at all")


if __name__ == "__main__":
    unittest.main()
