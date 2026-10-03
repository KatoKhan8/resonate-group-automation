"""The offset index so a journal replay reads O(M) not O(N).

TASK-226. The journal fixed the write; this fixes the read. An index maps
record id to byte offset in the base file, so `replay_narrow` reads only the
records the journal and caller touch rather than the entire base.

The index is DERIVED: it can be rebuilt from the base file alone. These tests
prove that a corrupt, stale or absent index is detected and rebuilt, never
trusted.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import store


def rec(rid, **extra):
    row = store.new_record(rid, "cold", "demo", f"Co {rid}", f"{rid}.test")
    row.update(extra)
    return row


class IndexBuildAndLoad(unittest.TestCase):
    """The index is built alongside the base and validated on load."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="jidx-")
        self.was = os.environ.get("QUEUE")
        self.was_flag = os.environ.get("QUEUE_JOURNAL")
        store.use_directory(self.dir)
        os.environ["QUEUE_JOURNAL"] = "1"

    def tearDown(self):
        for name, value in (("QUEUE", self.was),
                            ("QUEUE_JOURNAL", self.was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_index_built_after_base_write(self):
        """A save with journalling on builds the index alongside the base."""
        from src import queuejournal
        store.save([rec("a"), rec("b"), rec("c")])
        idx_path = queuejournal.index_path(store.queue_path())
        self.assertTrue(os.path.exists(idx_path),
                        "the index must exist after a base write")
        idx = queuejournal.load_index(store.queue_path())
        self.assertIsNotNone(idx, "the index must load successfully")
        self.assertEqual(set(idx["offsets"].keys()), {"a", "b", "c"})

    def test_index_offsets_point_to_correct_records(self):
        """Each offset in the index reads the correct record."""
        from src import queuejournal
        records = [rec(f"r{i:03d}") for i in range(20)]
        store.save(records)
        idx = queuejournal.load_index(store.queue_path())
        self.assertIsNotNone(idx)
        for rid, offset in idx["offsets"].items():
            with open(store.queue_path(), "rb") as f:
                f.seek(offset)
                line = json.loads(f.readline().decode("utf-8"))
            self.assertEqual(line["id"], rid,
                             f"offset {offset} should point to {rid}, "
                             f"got {line['id']}")

    def test_index_absent_returns_none(self):
        """No index file -> load returns None."""
        from src import queuejournal
        store.save([rec("a")])
        idx_path = queuejournal.index_path(store.queue_path())
        os.remove(idx_path)
        self.assertIsNone(queuejournal.load_index(store.queue_path()))

    def test_index_corrupt_returns_none(self):
        """A corrupt index file -> load returns None, not a crash."""
        from src import queuejournal
        store.save([rec("a"), rec("b")])
        idx_path = queuejournal.index_path(store.queue_path())
        with open(idx_path, "w") as f:
            f.write("NOT VALID JSON{{{")
        self.assertIsNone(queuejournal.load_index(store.queue_path()))

    def test_index_stale_after_base_change_returns_none(self):
        """If the base changes without rebuilding the index, load returns None.

        This simulates a crash between the base write and the index write.
        """
        from src import queuejournal
        store.save([rec("a"), rec("b")])
        idx_path = queuejournal.index_path(store.queue_path())
        idx = queuejournal.load_index(store.queue_path())
        self.assertIsNotNone(idx)
        idx["base_digest"] = "stale-digest-value"
        with open(idx_path, "w") as f:
            json.dump(idx, f)
        self.assertIsNone(queuejournal.load_index(store.queue_path()),
                          "a stale digest must be detected")

    def test_load_or_build_rebuilds_corrupt_index(self):
        """load_or_build_index rebuilds when the index is corrupt."""
        from src import queuejournal
        store.save([rec("a"), rec("b"), rec("c")])
        idx_path = queuejournal.index_path(store.queue_path())
        with open(idx_path, "w") as f:
            f.write("CORRUPT")
        idx = queuejournal.load_or_build_index(store.queue_path())
        self.assertIsNotNone(idx)
        self.assertEqual(set(idx["offsets"].keys()), {"a", "b", "c"})

    def test_load_or_build_rebuilds_stale_index(self):
        """load_or_build_index rebuilds when the base changed."""
        from src import queuejournal
        store.save([rec("a"), rec("b")])
        idx_path = queuejournal.index_path(store.queue_path())
        with open(idx_path, "r") as f:
            idx = json.load(f)
        idx["base_digest"] = "wrong"
        with open(idx_path, "w") as f:
            json.dump(idx, f)
        idx = queuejournal.load_or_build_index(store.queue_path())
        self.assertIsNotNone(idx)
        self.assertIn("a", idx["offsets"])
        self.assertIn("b", idx["offsets"])


class ReplayNarrowCorrectness(unittest.TestCase):
    """The narrowed replay returns the same records as the full replay."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="jnarrow-")
        self.was = os.environ.get("QUEUE")
        self.was_flag = os.environ.get("QUEUE_JOURNAL")
        store.use_directory(self.dir)
        os.environ["QUEUE_JOURNAL"] = "1"

    def tearDown(self):
        for name, value in (("QUEUE", self.was),
                            ("QUEUE_JOURNAL", self.was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_narrow_matches_full_replay(self):
        """replay_narrow returns the same records as full replay for the
        ids it covers."""
        from src import queuejournal
        store.save([rec(f"r{i:03d}") for i in range(50)])
        rows = store.load()
        rows[3]["state"] = "verified"
        rows[17]["state"] = "dropped"
        rows[17]["drop_reason"] = "competitor"
        store.save(rows)

        qpath = store.queue_path()
        full_base = store.read_jsonl(qpath)
        full_result, full_applied, _ = queuejournal.replay(
            full_base, qpath)

        narrow_result, narrow_applied, _ = queuejournal.replay_narrow(
            qpath, {"r003", "r017"})

        self.assertEqual(full_applied, narrow_applied)
        narrow_by_id = {r["id"]: r for r in narrow_result}
        for r in full_result:
            rid = r["id"]
            if rid in narrow_by_id:
                self.assertEqual(
                    r["state"], narrow_by_id[rid]["state"],
                    f"record {rid} state mismatch")

    def test_narrow_with_no_journal(self):
        """With no journal, replay_narrow reads from base via index."""
        from src import queuejournal
        store.save([rec("a"), rec("b"), rec("c")])
        result, applied, torn = queuejournal.replay_narrow(
            store.queue_path(), {"a", "b"})
        self.assertEqual(applied, 0)
        self.assertFalse(torn)
        ids = {r["id"] for r in result}
        self.assertIn("a", ids)
        self.assertIn("b", ids)

    def test_narrow_with_empty_journal(self):
        """With a journal that has no entries, reads from base."""
        from src import queuejournal
        store.save([rec("a"), rec("b")])
        result, applied, _ = queuejournal.replay_narrow(
            store.queue_path(), {"a"})
        self.assertEqual(applied, 0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "a")

    def test_narrow_includes_journal_only_records(self):
        """Records the journal introduces but the caller didn't touch."""
        from src import queuejournal
        store.save([rec("a"), rec("b")])
        rows = store.load()
        rows.append(rec("c", state="queued"))
        store.save(rows)
        result, applied, _ = queuejournal.replay_narrow(
            store.queue_path(), set())
        ids = {r["id"] for r in result}
        self.assertIn("c", ids,
                       "a record introduced by the journal must appear")


class NarrowedSaveCorrectness(unittest.TestCase):
    """save() with the narrowed path produces the same state as the full path."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="jsave-")
        self.was = os.environ.get("QUEUE")
        self.was_flag = os.environ.get("QUEUE_JOURNAL")
        store.use_directory(self.dir)

    def tearDown(self):
        for name, value in (("QUEUE", self.was),
                            ("QUEUE_JOURNAL", self.was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.dir, ignore_errors=True)

    def _run_edits(self):
        """A sequence of edits, returning the final state."""
        store.save([rec("a"), rec("b"), rec("c")])
        rows = store.load()
        rows[1]["state"] = "verified"
        store.save(rows)
        rows = store.load()
        rows[2]["state"] = "dropped"
        rows[2]["drop_reason"] = "competitor"
        store.save(rows)
        rows = store.load()
        rows.append(rec("d", state="queued"))
        store.save(rows)
        return [(r["id"], r["state"], r.get("drop_reason"))
                for r in store.load()]

    def test_narrowed_save_matches_whole_file(self):
        """Same edits, same result, journalled and whole-file paths."""
        os.environ.pop("QUEUE_JOURNAL", None)
        without = self._run_edits()
        shutil.rmtree(self.dir, ignore_errors=True)
        store.use_directory(self.dir)
        os.environ["QUEUE_JOURNAL"] = "1"
        with_journal = self._run_edits()
        self.assertEqual(without, with_journal)

    def test_guards_still_refuse_evidence_loss(self):
        """The narrowed path must still refuse to drop paid evidence."""
        os.environ["QUEUE_JOURNAL"] = "1"
        paid = rec("a")
        paid["contacts"] = [{
            "key": "a-c1", "email": "x@a.test",
            "verification": {"status": "valid", "evidence": [
                {"provider": "contactout", "status": "valid",
                 "at": "2026-09-17T10:00:00Z", "email": "x@a.test"}]},
        }]
        store.save([paid, rec("b")])
        stripped = json.loads(json.dumps(paid))
        stripped["contacts"][0]["verification"] = {"status": "unverified",
                                                   "evidence": []}
        with self.assertRaises(store.EvidenceLost):
            store.save([stripped, rec("b")])

    def test_survives_corrupt_index(self):
        """A corrupt index must be rebuilt, and the read still returns
        correct state."""
        from src import queuejournal
        os.environ["QUEUE_JOURNAL"] = "1"
        store.save([rec("a"), rec("b"), rec("c")])
        rows = store.load()
        rows[0]["state"] = "verified"
        store.save(rows)
        idx_path = queuejournal.index_path(store.queue_path())
        with open(idx_path, "w") as f:
            f.write("CORRUPT {{{")
        loaded = store.load()
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0]["state"], "verified")
        self.assertEqual(loaded[1]["state"], "queued")

    def test_survives_deleted_index(self):
        """A missing index must be rebuilt transparently."""
        from src import queuejournal
        os.environ["QUEUE_JOURNAL"] = "1"
        store.save([rec("a"), rec("b")])
        rows = store.load()
        rows[0]["state"] = "verified"
        store.save(rows)
        idx_path = queuejournal.index_path(store.queue_path())
        os.remove(idx_path)
        loaded = store.load()
        self.assertEqual(loaded[0]["state"], "verified")
        self.assertEqual(loaded[1]["state"], "queued")


class IndexRebuildFromFilesAlone(unittest.TestCase):
    """The index is DERIVED: rebuildable from the base file alone.

    TASK-226 requirement 3: corrupt the index, confirm the read still returns
    correct state. The index must never be trusted without validation.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="jrebuild-")
        self.was = os.environ.get("QUEUE")
        self.was_flag = os.environ.get("QUEUE_JOURNAL")
        store.use_directory(self.dir)
        os.environ["QUEUE_JOURNAL"] = "1"

    def tearDown(self):
        for name, value in (("QUEUE", self.was),
                            ("QUEUE_JOURNAL", self.was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_corrupt_index_rebuilt_and_read_correct(self):
        from src import queuejournal
        store.save([rec(f"r{i:03d}") for i in range(30)])
        rows = store.load()
        rows[5]["state"] = "verified"
        rows[15]["state"] = "dropped"
        rows[15]["drop_reason"] = "competitor"
        store.save(rows)

        idx_path = queuejournal.index_path(store.queue_path())
        with open(idx_path, "w") as f:
            f.write('{"base_digest": "wrong", "offsets": {}}')

        loaded = store.load()
        self.assertEqual(len(loaded), 30)
        by_id = {r["id"]: r for r in loaded}
        self.assertEqual(by_id["r005"]["state"], "verified")
        self.assertEqual(by_id["r015"]["state"], "dropped")
        self.assertEqual(by_id["r015"]["drop_reason"], "competitor")

    def test_index_with_wrong_digest_rejected(self):
        """An index with wrong digest is rejected even if offsets look valid."""
        from src import queuejournal
        store.save([rec("a"), rec("b")])
        idx_path = queuejournal.index_path(store.queue_path())
        with open(idx_path, "r") as f:
            idx = json.load(f)
        idx["base_digest"] = "0" * 32
        with open(idx_path, "w") as f:
            json.dump(idx, f)
        idx = queuejournal.load_index(store.queue_path())
        self.assertIsNone(idx,
                          "a wrong digest must be rejected even if the "
                          "offsets look plausible")

    def test_rebuild_after_compaction(self):
        """After compaction, the index is rebuilt for the new base."""
        from src import queuejournal
        n = 10
        store.save([rec(f"r{i:03d}") for i in range(n)])
        journal = queuejournal.path_for(store.queue_path())
        for step in range(60):
            rows = store.load()
            row = rows[step % n]
            row["state"] = "verified"
            row["_blob"] = "y" * 40000
            row["touched"] = step
            store.save(rows)

        idx = queuejournal.load_or_build_index(store.queue_path())
        self.assertIsNotNone(idx)
        self.assertEqual(len(idx["offsets"]), n)
        final = store.load()
        self.assertEqual(len(final), n)


if __name__ == "__main__":
    unittest.main()
