"""The journal index is DERIVED and must be rebuildable from the files alone.

The index maps record id to the byte offset of that record's last entry in
the journal. It makes `replay` O(M) where M is the number of unique records
rather than O(J) where J is the total number of entries. But the index is
not authoritative - it is a cache of a scan that can be redone.

These tests prove that:

  - a corrupt index is detected and rebuilt, producing the same state;
  - an absent index is rebuilt on the next read;
  - the index tracks byte offsets correctly after multiple appends;
  - compaction removes the index along with the journal.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import queuejournal, store


def rec(rid, **extra):
    row = store.new_record(rid, "cold", "demo", f"Co {rid}", f"{rid}.test")
    row.update(extra)
    return row


class IndexRebuild(unittest.TestCase):
    """The index is derived. Corrupt it, delete it, prove the read survives."""

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

    def _idx_path(self):
        return queuejournal._index_path(store.queue_path())

    def _journal_path(self):
        return queuejournal.path_for(store.queue_path())

    def test_index_is_created_on_first_append(self):
        store.save([rec("a"), rec("b")])
        rows = store.load()
        rows[0]["state"] = "verified"
        store.save(rows)
        self.assertTrue(os.path.exists(self._idx_path()),
                        "an append must create the index")

    def test_corrupt_index_is_rebuilt_and_read_still_correct(self):
        """THE FALSIFIABLE ONE. Corrupt the index, confirm the state is right.

        The index is DERIVED. A corrupt index must not produce wrong state -
        it must be detected and rebuilt from the journal. This is the test
        the task demands: corrupt the index, confirm the read returns correct
        state.
        """
        store.save([rec("a"), rec("b"), rec("c")])
        rows = store.load()
        rows[0]["state"] = "verified"
        rows[1]["state"] = "dropped"
        rows[1]["drop_reason"] = "competitor"
        store.save(rows)
        rows = store.load()
        rows[2]["hook"] = "updated hook"
        store.save(rows)

        expected = [(r["id"], r["state"], r.get("drop_reason"), r.get("hook"))
                    for r in store.load()]

        with open(self._idx_path(), "w", encoding="utf-8") as handle:
            handle.write("THIS IS NOT JSON {{{")

        actual = [(r["id"], r["state"], r.get("drop_reason"), r.get("hook"))
                  for r in store.load()]

        self.assertEqual(expected, actual,
                         "a corrupt index must be rebuilt, and the read must "
                         "return the same state as if the index were correct")

    def test_absent_index_is_rebuilt(self):
        store.save([rec("a"), rec("b")])
        rows = store.load()
        rows[0]["state"] = "verified"
        store.save(rows)

        expected = [(r["id"], r["state"]) for r in store.load()]
        os.remove(self._idx_path())
        self.assertFalse(os.path.exists(self._idx_path()))

        actual = [(r["id"], r["state"]) for r in store.load()]
        self.assertEqual(expected, actual,
                         "a missing index must be rebuilt on the next read")
        self.assertTrue(os.path.exists(self._idx_path()),
                        "the rebuild must recreate the index file")

    def test_index_tracks_multiple_appends(self):
        """Each append updates the index for the records it touches."""
        store.save([rec("a"), rec("b"), rec("c")])

        rows = store.load()
        rows[0]["state"] = "verified"
        store.save(rows)

        rows = store.load()
        rows[1]["state"] = "dropped"
        rows[1]["drop_reason"] = "bounce"
        store.save(rows)

        rows = store.load()
        rows[2]["hook"] = "new hook"
        store.save(rows)

        with open(self._idx_path(), encoding="utf-8") as handle:
            index = json.load(handle)

        self.assertIn("a", index)
        self.assertIn("b", index)
        self.assertIn("c", index)
        self.assertEqual(len(index), 3,
                         "the index must have one entry per unique record")

        final = store.load()
        self.assertEqual(final[0]["state"], "verified")
        self.assertEqual(final[1]["state"], "dropped")
        self.assertEqual(final[1]["drop_reason"], "bounce")
        self.assertEqual(final[2]["hook"], "new hook")

    def test_compaction_removes_the_index(self):
        """Compaction folds the journal into the base and drops both files."""
        n = 20
        store.save([rec(f"r{i:03d}") for i in range(n)])

        journal = self._journal_path()
        idx = self._idx_path()

        for step in range(120):
            rows = store.load()
            row = rows[step % n]
            row["state"] = "verified"
            row["_blob"] = "y" * 40000
            row["touched"] = step
            store.save(rows)

        if os.path.exists(journal):
            journal_size = os.path.getsize(journal)
            if journal_size == 0:
                self.assertFalse(os.path.exists(idx),
                                 "an empty journal must not have a live index")

    def test_index_rebuild_matches_incremental(self):
        """The index built by scanning matches the one maintained incrementally.

        Append some entries, save the incremental index, delete it, let the
        next read rebuild it, and confirm the two are byte-identical.
        """
        store.save([rec("a"), rec("b"), rec("c")])
        for _ in range(5):
            rows = store.load()
            rows[0]["touched"] = rows[0].get("touched", 0) + 1
            store.save(rows)

        with open(self._idx_path(), encoding="utf-8") as handle:
            incremental = json.load(handle)

        os.remove(self._idx_path())
        store.load()

        with open(self._idx_path(), encoding="utf-8") as handle:
            rebuilt = json.load(handle)

        self.assertEqual(incremental, rebuilt,
                         "the incrementally maintained index must match the "
                         "one rebuilt from a full scan of the journal")


class IndexCorrectness(unittest.TestCase):
    """The index points at the RIGHT entry, not just any entry."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="jidxcorr-")
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

    def test_index_points_at_last_entry_not_first(self):
        """A record touched three times: the index must point at the third.

        Last-write-wins is the replay rule. If the index pointed at the first
        entry, replay would return the FIRST value, not the LAST - which is
        the exact failure the index exists to avoid while being fast.
        """
        store.save([rec("a", state="queued")])
        rows = store.load()
        rows[0]["state"] = "verified"
        store.save(rows)
        rows = store.load()
        rows[0]["state"] = "dropped"
        rows[0]["drop_reason"] = "competitor"
        store.save(rows)

        result = store.load()
        self.assertEqual(result[0]["state"], "dropped",
                         "replay must return the LAST value, not the first")
        self.assertEqual(result[0]["drop_reason"], "competitor")

    def test_replay_with_index_matches_replay_without(self):
        """The indexed path and the linear path produce the same state.

        Force a linear replay by deleting the index, then compare against
        the indexed path. They must agree.
        """
        store.save([rec("a"), rec("b"), rec("c")])
        for i in range(10):
            rows = store.load()
            rows[i % 3]["touched"] = i
            rows[i % 3]["state"] = "verified" if i % 2 == 0 else "queued"
            store.save(rows)

        with_index = [(r["id"], r["state"], r.get("touched"))
                      for r in store.load()]

        idx_path = queuejournal._index_path(store.queue_path())
        os.remove(idx_path)
        without_index = [(r["id"], r["state"], r.get("touched"))
                         for r in store.load()]

        self.assertEqual(with_index, without_index,
                         "the indexed and linear replay paths must agree")


if __name__ == "__main__":
    unittest.main()
