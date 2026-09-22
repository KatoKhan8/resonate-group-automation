"""The one-shot migration from JSONL to SQLite, and the verifier that decides
it worked.

TASK-252, design `docs/STORE-SQLITE-DESIGN-2026-09-22.md` section 8.

The migration reads through `store._current_records()` - the base file WITH
any journal deltas replayed - and writes the SQLite store TASK-251 built.
It proves the two agree before reporting success.

The requirement most likely to be got wrong and expensive to get wrong:
reading `queue.jsonl` alone silently drops every checkpoint since the last
compaction, so a migration that looks clean has lost a day of work. The test
builds a fixture where `_current_records()` and `read_jsonl(queue_path())`
genuinely differ, then asserts the difference is what was migrated.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from src import store, sqlitestore


def record(rid, **extra):
    rec = {"id": rid, "lane": "cold", "client": "productive",
           "company": f"Co {rid}", "domain": f"{rid}.test",
           "state": "queued", "drop_reason": None, "log": []}
    rec.update(extra)
    return rec


class AnIsolatedStore(unittest.TestCase):
    """A temp-dir queue, QUEUE_JOURNAL off by default."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(_rmtree, self.dir)
        self._prev = {k: os.environ.get(k) for k in
                      ("QUEUE", "QUEUE_JOURNAL")}
        store.use_directory(self.dir)
        os.environ.pop("QUEUE_JOURNAL", None)

    def tearDown(self):
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


def _write_queue(records):
    """Seed the queue file with records, one JSON per line."""
    path = store.queue_path()
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _run_migration(db_path, extra_env=None):
    """Run the migration as a subprocess so the lock is real."""
    env = os.environ.copy()
    env["QUEUE"] = store.queue_path()
    env.pop("QUEUE_JOURNAL", None)
    if extra_env:
        env.update(extra_env)
    script = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "scripts", "migrate_store_sqlite.py")
    result = subprocess.run(
        [sys.executable, script, db_path],
        env=env, capture_output=True, text=True)
    return result


class FiveHundredRecordsRoundTrip(AnIsolatedStore):
    """Requirement 1: a 500-record fixture estate round-trips every record,
    in order, byte-identically on `json.dumps(..., sort_keys=True)`."""

    def test_five_hundred_records_in_order(self):
        ids = [f"rec-{n:04d}" for n in range(500)]
        shuffled = ids[250:] + ids[:250]
        recs = [record(r, state="enriched" if n % 3 == 0 else "queued")
                for n, r in enumerate(shuffled)]
        _write_queue(recs)

        db_path = os.path.join(self.dir, "queue.db")
        result = _run_migration(db_path)
        self.assertEqual(result.returncode, 0,
                         f"migration failed: {result.stderr}")

        conn = sqlitestore.open_db(db_path)
        self.addCleanup(conn.close)
        got = sqlitestore.read_all(conn)
        self.assertEqual(len(got), 500)
        self.assertEqual([r["id"] for r in got], shuffled)
        for src, dst in zip(recs, got):
            self.assertEqual(
                json.dumps(src, sort_keys=True, ensure_ascii=False),
                json.dumps(dst, sort_keys=True, ensure_ascii=False))


class TheJournalIsReplayed(AnIsolatedStore):
    """Requirement 2: with QUEUE_JOURNAL on and un-compacted deltas present,
    the migrated set equals `store._current_records()` and NOT
    `read_jsonl(queue_path())`. The fixture makes the two genuinely differ."""

    def test_journal_deltas_are_migrated_not_the_base_alone(self):
        base = [record(f"r{n}") for n in range(10)]
        _write_queue(base)

        os.environ["QUEUE_JOURNAL"] = "1"
        from src import queuejournal
        qpath = store.queue_path()
        base_digest = store.digest()

        changed = [record("r0", state="enriched"),
                   record("r5", state="dropped", drop_reason="wrong_persona")]
        queuejournal.append(qpath, changed, base_digest)

        base_only = store.read_jsonl(qpath)
        current = store._current_records()

        self.assertNotEqual(
            json.dumps(base_only, sort_keys=True),
            json.dumps(current, sort_keys=True),
            "the fixture did not make _current_records differ from the base; "
            "the test proves nothing")

        db_path = os.path.join(self.dir, "queue.db")
        result = _run_migration(db_path,
                                extra_env={"QUEUE_JOURNAL": "1"})
        self.assertEqual(result.returncode, 0,
                         f"migration failed: {result.stderr}")

        conn = sqlitestore.open_db(db_path)
        self.addCleanup(conn.close)
        got = sqlitestore.read_all(conn)

        self.assertEqual(len(got), len(current))
        for src, dst in zip(current, got):
            self.assertEqual(
                json.dumps(src, sort_keys=True, ensure_ascii=False),
                json.dumps(dst, sort_keys=True, ensure_ascii=False))

        base_ids = [r["id"] for r in base_only]
        current_ids = [r["id"] for r in current]
        self.assertEqual(base_ids, current_ids)
        base_states = [r.get("state") for r in base_only]
        current_states = [r.get("state") for r in current]
        self.assertNotEqual(base_states, current_states)


class TheVerifierRefusesAndRollsBack(AnIsolatedStore):
    """Requirement 3: a deliberately corrupted read-back makes the verifier
    REFUSE and roll back, leaving no database behind."""

    def test_corrupted_readback_leaves_no_database(self):
        _write_queue([record(f"r{n}") for n in range(5)])

        db_path = os.path.join(self.dir, "queue.db")

        corruptor = textwrap.dedent("""\
            import sqlite3, sys
            conn = sqlite3.connect(sys.argv[1])
            conn.execute("UPDATE records SET doc='{}' WHERE id='r2'")
            conn.commit()
            conn.close()
        """)

        script = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "scripts", "migrate_store_sqlite.py")
        env = os.environ.copy()
        env["QUEUE"] = store.queue_path()
        env.pop("QUEUE_JOURNAL", None)

        hook = os.path.join(self.dir, "corrupt_after.py")
        with open(hook, "w") as f:
            f.write(corruptor)

        env["_MIGRATE_CORRUPT_HOOK"] = hook
        result = subprocess.run(
            [sys.executable, script, db_path],
            env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0,
                            "migration should have refused")
        self.assertIn("verif", result.stderr.lower() + result.stdout.lower())
        self.assertFalse(os.path.exists(db_path),
                         "a refused migration left a database behind")


class IdempotentOnUnchangedSource(AnIsolatedStore):
    """Requirement 4: re-running on an unchanged source is a no-op that
    exits 0 and says so."""

    def test_second_run_is_a_noop(self):
        _write_queue([record(f"r{n}") for n in range(20)])
        db_path = os.path.join(self.dir, "queue.db")

        first = _run_migration(db_path)
        self.assertEqual(first.returncode, 0, first.stderr)
        mtime_after_first = os.path.getmtime(db_path)

        import time
        time.sleep(1.1)

        second = _run_migration(db_path)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already", second.stdout.lower() + second.stderr.lower())
        self.assertEqual(os.path.getmtime(db_path), mtime_after_first,
                         "a no-op re-run touched the database")


class RefusesWhenSourceChanged(AnIsolatedStore):
    """Requirement 5: re-running after the source has changed REFUSES and
    exits non-zero."""

    def test_changed_source_is_refused(self):
        _write_queue([record(f"r{n}") for n in range(5)])
        db_path = os.path.join(self.dir, "queue.db")

        first = _run_migration(db_path)
        self.assertEqual(first.returncode, 0, first.stderr)

        _write_queue([record(f"r{n}", state="enriched") for n in range(5)])
        second = _run_migration(db_path)
        self.assertNotEqual(second.returncode, 0,
                            "migration should have refused on changed source")
        self.assertIn("digest", (second.stderr + second.stdout).lower())


class NeverWritesWork(AnIsolatedStore):
    """Requirement 6: the migration never writes `work/` under test."""

    def test_refuse_production_write_covers_the_database(self):
        """The barrier must fire before any filesystem mutation. Run
        in-process so `unittest` is in `sys.modules`."""
        import importlib.util
        _write_queue([record("r0")])
        target = os.path.join(store.PRODUCTION_WORK, "queue.db")
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(target + suffix)
            except FileNotFoundError:
                pass
        script = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "scripts", "migrate_store_sqlite.py")
        spec = importlib.util.spec_from_file_location(
            "_migrate_for_test", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with self.assertRaises(store.ProductionStateUnderTest):
            mod.migrate(target)
        for suffix in ("", "-wal", "-shm"):
            self.assertFalse(os.path.exists(target + suffix),
                             f"barrier did not fire before creating {suffix}")


class TheLockIsHeldAcrossReadAndWrite(unittest.TestCase):
    """Requirement 7: a second process attempting a migration concurrently
    gets QueueLocked and writes nothing."""

    def test_concurrent_migration_is_refused(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(_rmtree, tmp)
        prev = {k: os.environ.get(k) for k in
                ("QUEUE", "QUEUE_JOURNAL", "QUEUE_LOCK_TIMEOUT")}
        try:
            store.use_directory(tmp)
            os.environ.pop("QUEUE_JOURNAL", None)
            _write_queue([record(f"r{n}") for n in range(10)])

            db_path = os.path.join(tmp, "queue.db")

            project_root = os.path.dirname(os.path.dirname(__file__))
            blocker_script = textwrap.dedent(f"""\
                import os, sys, time
                sys.path.insert(0, {project_root!r})
                from src import store
                store.use_directory(sys.argv[1])
                os.environ.pop("QUEUE_JOURNAL", None)
                with store.lock(timeout=5):
                    time.sleep(8)
            """)
            blocker = os.path.join(tmp, "hold_lock.py")
            with open(blocker, "w") as f:
                f.write(blocker_script)

            blocker_proc = subprocess.Popen(
                [sys.executable, blocker, tmp],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            import time
            time.sleep(1.0)

            result = _run_migration(db_path,
                                    extra_env={"QUEUE_LOCK_TIMEOUT": "1"})
            self.assertNotEqual(result.returncode, 0,
                                "concurrent migration should have been refused")
            self.assertFalse(os.path.exists(db_path),
                             "a refused migration left a database behind")

            blocker_proc.terminate()
            blocker_proc.wait(timeout=10)
        finally:
            for k, v in prev.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class MetaIsRecorded(AnIsolatedStore):

    def test_migrated_from_and_revision(self):
        _write_queue([record(f"r{n}") for n in range(5)])
        db_path = os.path.join(self.dir, "queue.db")
        result = _run_migration(db_path)
        self.assertEqual(result.returncode, 0, result.stderr)

        conn = sqlitestore.open_db(db_path)
        self.addCleanup(conn.close)
        self.assertEqual(sqlitestore.revision(conn), 1)
        migrated_from = sqlitestore.meta_get(conn, "migrated_from")
        self.assertIsNotNone(migrated_from)
        self.assertEqual(migrated_from, store.digest())


class TheSourceIsNotModified(AnIsolatedStore):

    def test_queue_jsonl_is_untouched(self):
        recs = [record(f"r{n}") for n in range(10)]
        _write_queue(recs)
        qpath = store.queue_path()
        with open(qpath, "rb") as f:
            before = f.read()

        db_path = os.path.join(self.dir, "queue.db")
        result = _run_migration(db_path)
        self.assertEqual(result.returncode, 0, result.stderr)

        with open(qpath, "rb") as f:
            after = f.read()
        self.assertEqual(before, after,
                         "the migration modified queue.jsonl; it must not")


if __name__ == "__main__":
    unittest.main()
