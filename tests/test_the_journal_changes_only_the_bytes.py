"""`QUEUE_JOURNAL` changes which bytes a checkpoint writes. Nothing else.

The flag is OFF by default because this is the only file holding real client
state. These tests are the argument for ever turning it on:

  - off, the behaviour is byte-identical to before the flag existed;
  - on, `load()` returns exactly what the whole-file path would have;
  - on, every guard `save` runs still runs, and still refuses.

The last one is the one that matters. A delta path that skipped
`refuse_evidence_loss` would be faster and would silently drop paid
verification evidence, which is the failure `store.save` was built to prevent.
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


class JournalFlag(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="jflag-")
        self.was = os.environ.get("QUEUE")
        self.was_flag = os.environ.get("QUEUE_JOURNAL")
        store.use_directory(self.dir)
        os.environ.pop("QUEUE_JOURNAL", None)

    def tearDown(self):
        if self.was is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self.was
        if self.was_flag is None:
            os.environ.pop("QUEUE_JOURNAL", None)
        else:
            os.environ["QUEUE_JOURNAL"] = self.was_flag
        shutil.rmtree(self.dir, ignore_errors=True)

    def _on(self):
        os.environ["QUEUE_JOURNAL"] = "1"

    # ------------------------------------------------------------- off

    def test_off_by_default(self):
        self.assertFalse(store.journalling(),
                         "the flag must be off unless asked for")

    def test_off_writes_no_journal_at_all(self):
        store.save([rec("a"), rec("b")])
        rows = store.load()
        rows[0]["state"] = "verified"
        store.save(rows)
        from src import queuejournal
        self.assertFalse(
            os.path.exists(queuejournal.path_for(store.queue_path())),
            "the whole-file path must not leave a journal behind")
        self.assertEqual([r["state"] for r in store.load()],
                         ["verified", "queued"])

    # ------------------------------------------------------------- on

    def test_on_produces_the_same_load_as_off(self):
        """The falsifiable one: same edits, same result, both paths."""
        def apply_edits():
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

        without = apply_edits()
        shutil.rmtree(self.dir, ignore_errors=True)
        store.use_directory(self.dir)
        self._on()
        with_journal = apply_edits()

        self.assertEqual(without, with_journal)
        self.assertEqual(
            [r[0] for r in with_journal], ["a", "b", "c", "d"],
            "order follows the disk on both paths, new rows on the end")

    def test_on_writes_far_less_than_the_whole_file(self):
        self._on()
        store.save([rec(f"r{i:04d}") for i in range(400)])
        base_bytes = os.path.getsize(store.queue_path())
        from src import queuejournal
        journal = queuejournal.path_for(store.queue_path())
        before = os.path.getsize(journal) if os.path.exists(journal) else 0

        rows = store.load()
        rows[7]["state"] = "verified"
        store.save(rows)

        grew = os.path.getsize(journal) - before
        self.assertGreater(grew, 0, "the change must be persisted")
        self.assertLess(grew, base_bytes / 10,
                        f"one changed record cost {grew} bytes against a "
                        f"{base_bytes}-byte file; the whole point is that it "
                        f"should not scale with the cohort")

    def test_on_does_not_rewrite_the_base_file(self):
        self._on()
        store.save([rec(f"r{i:03d}") for i in range(50)])
        before = os.path.getmtime(store.queue_path())
        with open(store.queue_path(), "rb") as handle:
            base_before = handle.read()
        rows = store.load()
        rows[3]["state"] = "verified"
        store.save(rows)
        with open(store.queue_path(), "rb") as handle:
            self.assertEqual(handle.read(), base_before,
                             "a delta checkpoint must leave the base alone")
        self.assertEqual(os.path.getmtime(store.queue_path()), before)

    def test_on_writes_nothing_when_nothing_changed(self):
        self._on()
        store.save([rec("a"), rec("b")])
        from src import queuejournal
        journal = queuejournal.path_for(store.queue_path())
        rows = store.load()
        store.save(rows)                      # no edits
        size = os.path.getsize(journal) if os.path.exists(journal) else 0
        self.assertEqual(size, 0,
                         "an unchanged checkpoint must cost no bytes")

    # ------------------------------------------- the guards still guard

    def test_on_still_refuses_to_drop_paid_evidence(self):
        """The guard that must survive the optimisation, or it is not one."""
        self._on()
        paid = rec("a")
        # `evidence`, not `confirmations`: `store._evidence_index` reads the
        # former, and a first version of this test built the latter and
        # passed on BOTH paths for the wrong reason - the guard never fired
        # at all. Checked against the whole-file path before being believed.
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

    def test_on_still_refuses_a_stale_write(self):
        """`expect_digest` has to keep working when the base stops moving.

        The digest is of the base file, and a delta checkpoint deliberately
        does not touch the base - so this asserts the optimistic-concurrency
        refusal still fires rather than being quietly defeated by a file that
        no longer changes.
        """
        self._on()
        store.save([rec("a"), rec("b")])
        rows = store.load()
        rows[0]["state"] = "verified"
        with self.assertRaises(store.QueueChanged):
            store.save(rows, expect_digest="not-the-digest-on-disk")

    def test_on_survives_a_torn_tail_from_a_killed_process(self):
        self._on()
        store.save([rec("a"), rec("b")])
        rows = store.load()
        rows[0]["state"] = "verified"
        store.save(rows)
        from src import queuejournal
        with open(queuejournal.path_for(store.queue_path()), "a",
                  encoding="utf-8") as handle:
            handle.write('{"seq": 9, "record": {"id": "b", "sta')
        loaded = store.load()
        self.assertEqual([r["id"] for r in loaded], ["a", "b"])
        self.assertEqual(loaded[0]["state"], "verified")
        self.assertEqual(loaded[1]["state"], "queued",
                         "the torn entry must not be half-applied")


if __name__ == "__main__":
    unittest.main()


class TheBarrierCoversTheSidecar(unittest.TestCase):
    """A journal must not be writable into the real `work/` directory.

    `_write` asks `refuse_production_write`; the delta path does not go
    through `_write`. Without an explicit check, a test that forgot to
    isolate the store would create `work/queue.jsonl.journal` next to 300
    real companies - the exact failure the barrier exists to stop, arriving
    through a file that did not exist when the barrier was written.
    """

    def setUp(self):
        self.was = os.environ.get("QUEUE")
        self.was_flag = os.environ.get("QUEUE_JOURNAL")
        os.environ["QUEUE_JOURNAL"] = "1"
        os.environ["QUEUE"] = os.path.join(store.PRODUCTION_WORK,
                                           "queue.jsonl")

    def tearDown(self):
        for name, value in (("QUEUE", self.was),
                            ("QUEUE_JOURNAL", self.was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_a_delta_write_into_the_real_directory_is_refused(self):
        before = sorted(os.listdir(store.PRODUCTION_WORK))
        with self.assertRaises(store.ProductionStateUnderTest):
            store._write_delta([], [rec("a")])
        self.assertEqual(sorted(os.listdir(store.PRODUCTION_WORK)), before,
                         "the refusal must land before the filesystem moves")


class CompactionThroughSave(unittest.TestCase):
    """`save` -> `_write_delta` -> `compact` had no test until it was run.

    The unit tests exercise `queuejournal.compact` directly. The path that
    actually reaches it in production is `store.save` noticing
    `should_compact` and calling it under the lock it already holds - and a
    400-record run at realistic record sizes never triggered it, because the
    2.0 ratio against a 12.5 MB base needs a 25 MB journal. So the branch
    existed, was correct, and had never executed.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="jcompact-")
        self.was = os.environ.get("QUEUE")
        self.was_flag = os.environ.get("QUEUE_JOURNAL")
        store.use_directory(self.dir)
        os.environ["QUEUE_JOURNAL"] = "1"

    def tearDown(self):
        for name, value in (("QUEUE", self.was), ("QUEUE_JOURNAL", self.was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_compaction_fires_and_loses_nothing(self):
        from src import queuejournal
        n = 20
        store.save([rec(f"r{i:03d}") for i in range(n)])

        journal = queuejournal.path_for(store.queue_path())
        compactions, previous = 0, 0
        for step in range(120):
            rows = store.load()
            row = rows[step % n]
            row["state"] = "verified"
            row["_blob"] = "y" * 40000     # fat deltas reach the 1 MB floor
            row["touched"] = step
            store.save(rows)
            size = os.path.getsize(journal) if os.path.exists(journal) else 0
            if size < previous:
                compactions += 1
                # THE INVARIANT IS HERE, not at the end of the loop: a fold
                # leaves the journal empty, because a journal sitting beside
                # a base that already contains its deltas is the thing that
                # would replay them twice. Afterwards deltas accumulate
                # again, which is why asserting an empty journal at the END
                # asserts the wrong property.
                self.assertEqual(size, 0,
                                 "compaction must empty the journal it folded")
            previous = size

        self.assertGreater(compactions, 0,
                           "the compaction branch in _write_delta never ran")
        final = store.load()
        self.assertEqual(len(final), n, "compaction must not change the count")
        ids = [r["id"] for r in final]
        self.assertEqual(ids, sorted(ids), "compaction must not reorder")
        self.assertEqual(len(set(ids)), n, "compaction must not duplicate")
        self.assertTrue(all("touched" in r for r in final),
                        "every record's last edit must survive the fold")
        self.assertTrue(all(len(r.get("_blob", "")) == 40000 for r in final),
                        "a folded record must keep its whole body")
        # And the base alone - with whatever journal remains replayed over it
        # - is still the whole estate. Checked above by `final`.
