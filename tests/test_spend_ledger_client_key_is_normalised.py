"""TASK-994: the spend ledger client key is normalised to lowercase on write.

## The defect this pins

Measured 2026-10-12 over 20,446 rows of `work/spend-ledger.jsonl`:

    productive       18,128 rows
    Productive        2,087 rows
    unattributed        111 rows

Two thousand and eighty-seven rows were filed under "Productive" while
eighteen thousand used "productive". A spend reader filtering on one spelling
saw nothing and reported clean - the same class of defect as a retired tenant
filter watching a zero balance while the live tenant spends underneath it.

## What this test proves

1. `spendledger.record()` lowercases the client key on write, so "Productive",
   "PRODUCTIVE" and "productive" all land as "productive" in the ledger.
2. `spendledger.spent()` normalises the client parameter, so a caller passing
   any casing sees the same rows.
3. `spendledger.Hold` lowercases the client key, so reservations and ledger
   rows use the same identity.
4. `spendledger.reserved()` normalises the client parameter the same way.

## Why lowercase

The alternative is to preserve the caller's casing and require every reader to
do case-insensitive comparison. That splits the identity across the codebase:
a filter that forgets is a filter that watches nothing. Lowercase on write
makes one identity the only identity, and a reader that filters on the wrong
spelling fails loudly instead of silently.
"""
import json
import os
import tempfile
import unittest

from src import spendledger
from src import store


class TestSpendLedgerClientKeyNormalisation(unittest.TestCase):
    """The client key is normalised to lowercase on write and on read."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: _cleanup(self.tmpdir))
        self.ledger_path = os.path.join(self.tmpdir, "spend-ledger.jsonl")
        os.environ["SPEND_LEDGER"] = self.ledger_path
        store.use_directory(self.tmpdir)
        # Clear any holds from previous tests to ensure isolation.
        spendledger._HOLDS.clear()

    def test_record_lowercases_client_on_write(self):
        """`record("Productive", ...)` writes "productive" to the ledger."""
        row = spendledger.record("Productive", "deliverable", "verify", 100)
        self.assertEqual(row["client"], "productive")
        # And the file agrees with the return value.
        with open(self.ledger_path, "r", encoding="utf-8") as fh:
            written = json.loads(fh.readline())
        self.assertEqual(written["client"], "productive")

    def test_record_lowercases_mixed_case_client(self):
        """`record("PrOdUcTiVe", ...)` writes "productive" to the ledger."""
        row = spendledger.record("PrOdUcTiVe", "deliverable", "verify", 100)
        self.assertEqual(row["client"], "productive")

    def test_record_handles_none_client(self):
        """`record(None, ...)` does not raise and writes None."""
        row = spendledger.record(None, "deliverable", "verify", 100)
        self.assertIsNone(row["client"])

    def test_record_handles_empty_string_client(self):
        """`record("", ...)` writes "" (empty string is falsy but preserved)."""
        row = spendledger.record("", "deliverable", "verify", 100)
        self.assertEqual(row["client"], "")

    def test_spent_normalises_client_parameter(self):
        """`spent("Productive")` sees rows written as "productive"."""
        spendledger.record("productive", "deliverable", "verify", 100)
        spendledger.record("productive", "reoon", "verify", 50)
        # A caller passing the wrong casing must see the same rows.
        self.assertEqual(spendledger.spent("Productive"), 150)
        self.assertEqual(spendledger.spent("PRODUCTIVE"), 150)
        self.assertEqual(spendledger.spent("productive"), 150)

    def test_spent_with_none_client_counts_all(self):
        """`spent(None)` counts every tenant, as documented."""
        spendledger.record("acme", "deliverable", "verify", 100)
        spendledger.record("globex", "deliverable", "verify", 200)
        self.assertEqual(spendledger.spent(None), 300)

    def test_hold_lowercases_client(self):
        """`Hold("Productive", ...)` stores "productive"."""
        hold = spendledger.Hold("Productive", "deliverable", "verify",
                                "run-1", "2026-10-12", 100, "credit")
        self.assertEqual(hold.client, "productive")

    def test_hold_handles_none_client(self):
        """`Hold(None, ...)` does not raise and stores None."""
        hold = spendledger.Hold(None, "deliverable", "verify",
                                "run-1", "2026-10-12", 100, "credit")
        self.assertIsNone(hold.client)

    def test_reserved_normalises_client_parameter(self):
        """`reserved("Productive")` sees holds created as "productive"."""
        # `reserve` requires a config; pass an empty one (no ceilings).
        spendledger.reserve("productive", {}, 100)
        # A caller passing the wrong casing must see the same holds.
        self.assertEqual(spendledger.reserved("Productive"), 100)
        self.assertEqual(spendledger.reserved("PRODUCTIVE"), 100)
        self.assertEqual(spendledger.reserved("productive"), 100)

    def test_two_spellings_cannot_both_exist_in_ledger(self):
        """The whole point: "Productive" and "productive" are one identity."""
        spendledger.record("Productive", "deliverable", "verify", 100)
        spendledger.record("PRODUCTIVE", "deliverable", "verify", 200)
        spendledger.record("productive", "deliverable", "verify", 300)
        # All three rows are filed under "productive".
        rows = spendledger.load()
        clients = [row["client"] for row in rows]
        self.assertEqual(clients, ["productive", "productive", "productive"])
        # And a filter on any spelling sees all three.
        self.assertEqual(spendledger.spent("productive"), 600)
        self.assertEqual(spendledger.spent("Productive"), 600)
        self.assertEqual(spendledger.spent("PRODUCTIVE"), 600)

    def test_committed_normalises_client_parameter(self):
        """`committed("Productive")` sees both ledger rows and holds."""
        spendledger.record("productive", "deliverable", "verify", 100)
        spendledger.reserve("productive", {}, 50)
        # A caller passing the wrong casing must see the same total.
        self.assertEqual(spendledger.committed("Productive"), 150)
        self.assertEqual(spendledger.committed("PRODUCTIVE"), 150)
        self.assertEqual(spendledger.committed("productive"), 150)


def _cleanup(tmpdir):
    """Remove the temp directory and its contents."""
    import shutil
    try:
        shutil.rmtree(tmpdir)
    except OSError:
        pass


if __name__ == "__main__":
    unittest.main()
