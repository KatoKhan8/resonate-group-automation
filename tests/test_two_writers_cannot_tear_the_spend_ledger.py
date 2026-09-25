"""A torn row in the spend ledger stops every later call, so it must not tear.

Found in production on 2026-09-24, the hour S5 was wired into this ledger and
run at eight workers: 1,957 rows in, one append TORE. The file kept a complete
row followed by an orphaned eleven-byte tail whose own head was gone.

What that cost is the point. `load()` refuses an unreadable ledger rather than
reading it as empty - deliberately, because a spend control that opens when
its own state is damaged fails exactly when something is already wrong - and
`check()` reads the ledger before every paid call. So one torn line refused
every subsequent verification for that client, and the run stopped buying.

The refusal is correct and is not what these tests change. What they pin is
that the WRITE cannot interleave: `record` takes `store.lock`, which is
cross-process rather than merely cross-thread, because the enrich loops, the
monitors and the staging runners all bill the same client from different
processes and an in-process lock would have left that race exactly where it
was while looking like a fix.
"""
import concurrent.futures as cf
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store                           # noqa: E402


class TornLedgerTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self.tmp))

    def test_a_held_lock_blocks_the_append_rather_than_racing_it(self):
        """The decisive one: while the lock is held, nothing may append.

        Deterministic, unlike a thread race. If `record` stops taking the
        lock, this call succeeds and the test fails on the row it should not
        have been able to write.
        """
        real_timeout = store.LOCK_TIMEOUT
        store.LOCK_TIMEOUT = 0.2
        self.addCleanup(setattr, store, "LOCK_TIMEOUT", real_timeout)

        with store.lock(for_path=spendledger.path()):
            with self.assertRaises(store.QueueLocked):
                spendledger.record("productive", "reoon", "reoon-verify", 1)

        self.assertEqual([], spendledger.load())
        # And the lock being released is not a one-way door.
        spendledger.record("productive", "reoon", "reoon-verify", 1)
        self.assertEqual(1, spendledger.spent("productive"))

    def test_many_concurrent_writers_leave_a_readable_ledger(self):
        """Every row present, every row parseable, the total exact.

        `load()` raises on the first unparseable line, so "readable" here is
        the same assertion the production failure violated.
        """
        writers, each = 8, 60
        with cf.ThreadPoolExecutor(max_workers=writers) as pool:
            list(pool.map(
                lambda n: [spendledger.record("productive", "reoon",
                                              "reoon-verify", 1)
                           for _ in range(each)],
                range(writers)))

        rows = spendledger.load()                 # raises if anything tore
        self.assertEqual(writers * each, len(rows))
        self.assertEqual(writers * each, spendledger.spent("productive"))
        with open(spendledger.path(), encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    self.assertEqual("reoon", json.loads(line)["provider"])

    def test_an_unreadable_ledger_refuses_spend_rather_than_allowing_it(self):
        """The guard the torn row tripped, pinned so nobody softens it.

        Making `load` tolerant of a bad line would have hidden the production
        failure instead of fixing it, and would leave a ceiling reading a
        ledger that silently under-reports whatever it could not parse.
        """
        spendledger.record("productive", "reoon", "reoon-verify", 1)
        with open(spendledger.path(), "a", encoding="utf-8") as fh:
            fh.write('id": null}\n')

        with self.assertRaises(spendledger.LedgerUnreadable):
            spendledger.load()
        with self.assertRaises(spendledger.LedgerUnreadable):
            spendledger.check("productive", {"budget": {"per_day": 10}}, 1)


if __name__ == "__main__":
    unittest.main()
