"""The journal index is derived, not authoritative.

A corrupt, stale or absent index must be detected and rebuilt, never trusted.
This test proves it: corrupt the index, confirm the read still returns correct
state.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import queuejournal as qj


def rec(rid, **extra):
    row = {"id": rid, "state": "queued", "company": f"Co {rid}"}
    row.update(extra)
    return row


class JournalIndexTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="jidx-")
        self.queue = os.path.join(self.dir, "queue.jsonl")
        self.base = [rec("a"), rec("b"), rec("c")]
        with open(self.queue, "w", encoding="utf-8", newline="\n") as f:
            for r in self.base:
                f.write(json.dumps(r) + "\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_index_is_built_on_first_read(self):
        """Absent index is rebuilt from the base file."""
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        idx_path = qj.index_path(self.queue)
        self.assertFalse(os.path.exists(idx_path),
                         "index should not exist before first indexed read")
        changed, torn = qj.read_changed(self.queue, self.queue)
        self.assertTrue(os.path.exists(idx_path),
                        "index should be built after first indexed read")
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["id"], "b")
        self.assertEqual(changed[0]["state"], "verified")

    def test_corrupt_index_is_rebuilt(self):
        """A corrupt index is detected and rebuilt, never trusted."""
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        idx_path = qj.index_path(self.queue)
        with open(idx_path, "w", encoding="utf-8") as f:
            f.write("{corrupt json")
        changed, torn = qj.read_changed(self.queue, self.queue)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["id"], "b")
        self.assertEqual(changed[0]["state"], "verified")

    def test_stale_index_is_rebuilt(self):
        """A stale index (missing records) is detected and rebuilt."""
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        idx_path = qj.index_path(self.queue)
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump({"nonexistent": 0}, f)
        changed, torn = qj.read_changed(self.queue, self.queue)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["id"], "b")
        self.assertEqual(changed[0]["state"], "verified")

    def test_index_survives_compaction(self):
        """Compaction invalidates the index, which is rebuilt on next read."""
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        idx_path = qj.index_path(self.queue)
        self.assertFalse(os.path.exists(idx_path))
        qj.read_changed(self.queue, self.queue)
        self.assertTrue(os.path.exists(idx_path))
        big = "x" * 4000
        for n in range(400):
            qj.append(self.queue, [rec("b", state=f"s{n}", pad=big)], "d0")
        self.assertTrue(qj.should_compact(self.queue))

        def write_base(records):
            with open(self.queue, "w", encoding="utf-8", newline="\n") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")

        qj.compact(self.queue, write_base)
        self.assertFalse(os.path.exists(idx_path),
                         "compaction must invalidate the index")
        qj.append(self.queue, [rec("a", state="dropped")], "d0")
        changed, torn = qj.read_changed(self.queue, self.queue)
        self.assertTrue(os.path.exists(idx_path),
                        "index should be rebuilt after compaction")
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["id"], "a")

    def test_read_changed_returns_only_journal_records(self):
        """read_changed returns only the records the journal touched."""
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        qj.append(self.queue, [rec("c", state="dropped")], "d0")
        changed, torn = qj.read_changed(self.queue, self.queue)
        self.assertEqual(len(changed), 2)
        ids = {r["id"] for r in changed}
        self.assertEqual(ids, {"b", "c"})

    def test_read_changed_with_no_journal(self):
        """No journal means no changed records."""
        changed, torn = qj.read_changed(self.queue, self.queue)
        self.assertEqual(changed, [])
        self.assertFalse(torn)


if __name__ == "__main__":
    unittest.main()
