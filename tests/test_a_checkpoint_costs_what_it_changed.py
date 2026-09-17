"""`queuejournal`: the delta log that makes a checkpoint cost O(changed).

NOT WIRED. `store.save` is untouched, so nothing here asserts anything about
production behaviour today. What it asserts is that the primitive a wiring
change would use behaves correctly at its edges - particularly the crash
edges, which are the reason this is landed separately from the change to the
only file holding real client state.
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


class JournalTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="journal-")
        self.queue = os.path.join(self.dir, "queue.jsonl")
        self.base = [rec("a"), rec("b"), rec("c")]
        with open(self.queue, "w", encoding="utf-8", newline="\n") as f:
            for r in self.base:
                f.write(json.dumps(r) + "\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _journal_lines(self):
        with open(qj.path_for(self.queue), encoding="utf-8") as f:
            return f.read().splitlines()

    # ----------------------------------------------------- the point

    def test_a_delta_writes_only_what_changed(self):
        """The whole reason this module exists, asserted in bytes."""
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        journal_bytes = os.path.getsize(qj.path_for(self.queue))
        base_bytes = os.path.getsize(self.queue)
        self.assertLess(journal_bytes, base_bytes,
                        "a one-record delta must not cost more than the file "
                        "it avoided rewriting")
        self.assertEqual(len(self._journal_lines()), 1)

    def test_the_base_file_is_never_touched(self):
        with open(self.queue, "rb") as f:
            before = f.read()
        qj.append(self.queue, [rec("a", state="dropped")], "d0")
        with open(self.queue, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_replay_applies_the_delta(self):
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        out, applied, torn = qj.replay(self.base, self.queue)
        self.assertEqual(applied, 1)
        self.assertFalse(torn)
        self.assertEqual([r["id"] for r in out], ["a", "b", "c"])
        self.assertEqual(out[1]["state"], "verified")
        self.assertEqual(out[0]["state"], "queued")

    def test_the_last_write_for_a_record_wins(self):
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        qj.append(self.queue, [rec("b", state="drafted")], "d0")
        out, applied, _torn = qj.replay(self.base, self.queue)
        self.assertEqual(applied, 1, "two entries, one record")
        self.assertEqual(out[1]["state"], "drafted")

    def test_a_record_the_base_never_had_is_appended(self):
        qj.append(self.queue, [rec("d", state="queued")], "d0")
        out, _applied, _torn = qj.replay(self.base, self.queue)
        self.assertEqual([r["id"] for r in out], ["a", "b", "c", "d"])

    def test_base_order_is_preserved(self):
        qj.append(self.queue, [rec("c", state="x"), rec("a", state="y")], "d0")
        out, _a, _t = qj.replay(self.base, self.queue)
        self.assertEqual([r["id"] for r in out], ["a", "b", "c"])

    def test_no_journal_means_the_base_unchanged(self):
        out, applied, torn = qj.replay(self.base, self.queue)
        self.assertEqual(out, self.base)
        self.assertEqual(applied, 0)
        self.assertFalse(torn)

    def test_an_empty_delta_writes_nothing(self):
        self.assertEqual(qj.append(self.queue, [], "d0"), 0)
        self.assertFalse(os.path.exists(qj.path_for(self.queue)))

    # ----------------------------------------------------- crash edges

    def test_a_torn_final_line_is_discarded_not_raised(self):
        """A process dying mid-append. The readable entries must survive."""
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        with open(qj.path_for(self.queue), "a", encoding="utf-8") as f:
            f.write('{"seq": 1, "record": {"id": "c", "stat')   # torn
        out, applied, torn = qj.replay(self.base, self.queue)
        self.assertTrue(torn)
        self.assertEqual(applied, 1)
        self.assertEqual(out[1]["state"], "verified")
        self.assertEqual(out[2]["state"], "queued", "the torn entry for c "
                                                    "must not be half-applied")

    def test_a_torn_middle_line_raises(self):
        """Not a crash. Replaying around it invents a state nobody wrote."""
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        lines = self._journal_lines()
        with open(qj.path_for(self.queue), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write('{"seq": 0, "record": {"id": "a", "st\n')   # torn, FIRST
            f.write(lines[0] + "\n")
        with self.assertRaises(qj.JournalCorrupt) as e:
            qj.replay(self.base, self.queue)
        self.assertIn("not the final line", str(e.exception))

    def test_an_entry_without_a_record_raises(self):
        with open(qj.path_for(self.queue), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(json.dumps({"seq": 0, "at": None}) + "\n")
        with self.assertRaises(qj.JournalCorrupt):
            qj.replay(self.base, self.queue)

    def test_a_record_without_an_id_raises(self):
        with open(qj.path_for(self.queue), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(json.dumps({"seq": 0, "record": {"state": "x"}}) + "\n")
        with self.assertRaises(qj.JournalCorrupt) as e:
            qj.replay(self.base, self.queue)
        self.assertIn("no `id`", str(e.exception))

    def test_a_delta_from_a_different_base_raises(self):
        """The guard against replaying onto the wrong file.

        Without it a journal left beside a compacted base would silently
        revert records to values nobody wrote.
        """
        qj.append(self.queue, [rec("b", state="verified")], "digest-one")
        with self.assertRaises(qj.JournalCorrupt) as e:
            qj.replay(self.base, self.queue, base_digest="digest-two")
        self.assertIn("digest", str(e.exception).lower())

    def test_a_matching_base_digest_replays(self):
        qj.append(self.queue, [rec("b", state="verified")], "digest-one")
        out, applied, _t = qj.replay(self.base, self.queue,
                                     base_digest="digest-one")
        self.assertEqual(applied, 1)
        self.assertEqual(out[1]["state"], "verified")

    # ----------------------------------------------------- compaction

    def test_a_small_journal_does_not_compact(self):
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        self.assertFalse(qj.should_compact(self.queue))

    def test_a_journal_larger_than_its_base_compacts(self):
        big = "x" * 4000
        for n in range(400):
            qj.append(self.queue, [rec("b", state=f"s{n}", pad=big)], "d0")
        self.assertGreater(os.path.getsize(qj.path_for(self.queue)),
                           1_000_000)
        self.assertTrue(qj.should_compact(self.queue))

    def test_discard_removes_the_journal_and_is_idempotent(self):
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        qj.discard(self.queue)
        self.assertFalse(os.path.exists(qj.path_for(self.queue)))
        qj.discard(self.queue)          # a second crash-recovery pass

    def test_discarding_does_not_touch_the_base(self):
        with open(self.queue, "rb") as f:
            before = f.read()
        qj.append(self.queue, [rec("b", state="verified")], "d0")
        qj.discard(self.queue)
        with open(self.queue, "rb") as f:
            self.assertEqual(f.read(), before)

    # ----------------------------------------------------- scale

    def test_the_cost_of_a_pass_stops_being_quadratic(self):
        """5000 records, 1000 checkpoints, measured in bytes.

        The whole-file path writes 4.4 GB for this. The assertion is
        deliberately loose - two orders of magnitude - because the point is
        the SHAPE, and a tight bound would fail on a record-size change that
        means nothing.
        """
        base = [rec(f"r{i:05d}", pad="y" * 800) for i in range(5000)]
        queue = os.path.join(self.dir, "big.jsonl")
        with open(queue, "w", encoding="utf-8", newline="\n") as f:
            for r in base:
                f.write(json.dumps(r) + "\n")
        whole_file = os.path.getsize(queue)

        for n in range(1000):
            qj.append(queue, [dict(base[n * 5], state="verified")], "d0")

        journal_bytes = os.path.getsize(qj.path_for(queue))
        whole_file_cost = whole_file * 1000
        self.assertLess(journal_bytes, whole_file_cost / 100,
                        f"journal {journal_bytes} vs whole-file "
                        f"{whole_file_cost}: the delta path must be at least "
                        f"two orders of magnitude cheaper for this pass")
        out, applied, torn = qj.replay(base, queue)
        self.assertFalse(torn)
        self.assertEqual(applied, 1000)
        self.assertEqual(len(out), 5000, "replay must not change the count")
        self.assertEqual(sum(1 for r in out if r["state"] == "verified"), 1000)


if __name__ == "__main__":
    unittest.main()


class ConcurrencyGlmFound(unittest.TestCase):
    """The defects GLM's adversarial review named, each reproduced first.

    The review was run against this module BEFORE it had a caller. Three of
    its findings were accepted; one was measured and is the reason `append`
    now takes a lock at all.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="journal-race-")
        self.queue = os.path.join(self.dir, "queue.jsonl")
        with open(self.queue, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec("a")) + "\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_concurrent_appends_do_not_lose_entries(self):
        """GLM finding 4a, MEASURED TRUE before it was fixed.

        Six processes appending 400 lines each to one journal with a bare
        `open(path, "a")` produced 2,193 of 2,400 lines, 207 missing and one
        mangled, silently - because Windows implements append as
        seek-to-EOF-then-write rather than atomically.

        Threads here rather than processes: `store.lock` is a cross-process
        advisory lock and this proves the serialisation it provides. The
        process-level measurement is recorded in the module docstring.
        """
        import threading
        errors = []

        def worker(tag):
            try:
                for i in range(25):
                    qj.append(self.queue,
                              [rec(f"{tag}-{i}", pad="z" * 300)], "d0")
            except Exception as exc:                       # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(f"t{n}",))
                   for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"append raised under contention: {errors}")
        entries, torn = qj.read(self.queue)
        self.assertFalse(torn, "a locked append must never leave a torn tail")
        self.assertEqual(len(entries), 100,
                         "every append must survive; this is the assertion "
                         "that fails without the lock")
        ids = {e["record"]["id"] for e in entries}
        self.assertEqual(len(ids), 100)

    def test_compaction_folds_in_and_then_drops_the_journal(self):
        qj.append(self.queue, [rec("a", state="verified")], "d0")
        qj.append(self.queue, [rec("b", state="queued")], "d0")
        written = {}

        def write_base(records):
            written["records"] = records
            with open(self.queue, "w", encoding="utf-8", newline="\n") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")

        applied = qj.compact(self.queue, write_base)
        self.assertEqual(applied, 2)
        self.assertFalse(os.path.exists(qj.path_for(self.queue)),
                         "the journal is dropped only AFTER the base is written")
        ids = [r["id"] for r in written["records"]]
        self.assertEqual(ids, ["a", "b"])
        self.assertEqual(written["records"][0]["state"], "verified")

    def test_compaction_is_a_noop_with_no_journal(self):
        calls = []
        self.assertEqual(
            qj.compact(self.queue, lambda recs: calls.append(recs)), 0)
        self.assertEqual(calls, [],
                         "nothing to fold means the base is not rewritten")

    def test_a_stale_delta_overwrites_a_newer_one_AND_THAT_IS_THE_HAZARD(self):
        """GLM finding 3. ACCEPTED, NOT FIXED, and pinned here deliberately.

        This test asserts the BAD behaviour, because the bad behaviour is
        real and a wiring change has to deal with it. `replay` is
        last-write-wins in file order with no version comparison, so:

          1. A and B both read the record at t0.
          2. B appends the record carrying paid verification evidence.
          3. A appends its STALE copy, without that evidence.
          4. replay keeps A's. The paid evidence is gone, nothing raises,
             and `torn_tail` is clean.

        `store.save` prevents exactly this with `refuse_evidence_loss` and
        `expect_digest` on a read-and-compare path this module does not
        reproduce. **A caller that appends deltas without running those
        guards has removed them.** If a future change makes this test fail,
        that is good news - it means the delta path grew the guard - and the
        test should then be inverted rather than deleted.
        """
        paid = rec("a", state="verified",
                   verification={"confirmations": ["contactout", "reoon"]})
        stale = rec("a", state="queued", attempts=1)
        qj.append(self.queue, [paid], "d0")      # B, newer knowledge
        qj.append(self.queue, [stale], "d0")     # A, stale read

        out, applied, torn = qj.replay([rec("a")], self.queue)
        self.assertFalse(torn)
        self.assertEqual(applied, 1)
        self.assertEqual(out[0]["state"], "queued")
        self.assertNotIn("verification", out[0],
                         "THE HAZARD: paid verification evidence was dropped "
                         "by a stale delta and nothing objected")
