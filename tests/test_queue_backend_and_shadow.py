"""TASK-253: QUEUE_BACKEND, the shadow write, and the diff ledger.

Tests the three backend modes (jsonl, shadow, sqlite), the shadow divergence
detection, the diff ledger, SHADOW_STRICT mode, and the promotion check.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from src import store, sqlitestore
from tests.base import QueueTest


def rec(rid="meridian", **kw):
    r = store.new_record(rid, "domains", "productive", "Meridian", "meridian.test")
    r.update(kw)
    return r


class TestBackendResolution(QueueTest):
    """QUEUE_BACKEND is resolved per call, not at import."""

    def test_default_is_jsonl(self):
        os.environ.pop("QUEUE_BACKEND", None)
        self.assertEqual(store.backend(), "jsonl")

    def test_shadow_mode(self):
        os.environ["QUEUE_BACKEND"] = "shadow"
        self.addCleanup(os.environ.pop, "QUEUE_BACKEND", None)
        self.assertEqual(store.backend(), "shadow")

    def test_sqlite_mode(self):
        os.environ["QUEUE_BACKEND"] = "sqlite"
        self.addCleanup(os.environ.pop, "QUEUE_BACKEND", None)
        self.assertEqual(store.backend(), "sqlite")

    def test_unknown_backend_refused(self):
        os.environ["QUEUE_BACKEND"] = "postgres"
        self.addCleanup(os.environ.pop, "QUEUE_BACKEND", None)
        with self.assertRaises(ValueError):
            store.backend()


class TestJsonlDefaultUnchanged(QueueTest):
    """QUEUE_BACKEND unset behaves byte-identically to today."""

    def test_save_and_load_round_trip(self):
        os.environ.pop("QUEUE_BACKEND", None)
        store.append([rec()])
        loaded = store.load()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["id"], "meridian")

    def test_digest_is_content_hash(self):
        os.environ.pop("QUEUE_BACKEND", None)
        store.append([rec()])
        d1 = store.digest()
        store.patch("meridian", {"state": "enriched"})
        d2 = store.digest()
        self.assertNotEqual(d1, d2)


class TestShadowMode(QueueTest):
    """Shadow mode: JSONL canonical, both written, reads from JSONL."""

    def setUp(self):
        super().setUp()
        os.environ["QUEUE_BACKEND"] = "shadow"
        self.db_path = os.path.join(self.tmp, "work", "queue.db")
        os.environ["QUEUE_DB"] = self.db_path

    def tearDown(self):
        os.environ.pop("QUEUE_BACKEND", None)
        os.environ.pop("QUEUE_DB", None)
        super().tearDown()

    def test_save_writes_both_stores(self):
        store.append([rec()])
        # JSONL has the record
        jsonl_recs = store.read_jsonl(store.queue_path())
        self.assertEqual(len(jsonl_recs), 1)
        # SQLite has the record
        conn = sqlite3.connect(self.db_path)
        try:
            sqlite_recs = sqlitestore.read_all(conn)
            self.assertEqual(len(sqlite_recs), 1)
            self.assertEqual(sqlite_recs[0]["id"], "meridian")
        finally:
            conn.close()

    def test_load_returns_jsonl_answer(self):
        store.append([rec()])
        loaded = store.load()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["id"], "meridian")

    def test_divergence_written_to_ledger_not_raised(self):
        """An injected divergence is caught, written to ledger, does NOT raise."""
        os.environ.pop("SHADOW_STRICT", None)
        store.append([rec()])
        # Patch the SQLite row behind the store's back
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE records SET doc=? WHERE id=?",
                (json.dumps({"id": "meridian", "state": "enriched"}), "meridian"))
            conn.commit()
        finally:
            conn.close()
        # Now trigger another write - this should detect the divergence
        store.patch("meridian", {"state": "verified"})
        # The write succeeded (did not raise)
        r = store.get("meridian")
        self.assertEqual(r["state"], "verified")
        # The ledger has a divergence entry
        ledger_path = os.path.join(self.tmp, "work", "store-shadow-diff.jsonl")
        self.assertTrue(os.path.exists(ledger_path))
        with open(ledger_path, encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
        self.assertGreater(len(entries), 0)
        # At least one entry is a divergence
        divergences = [e for e in entries if e.get("type") == "divergence"]
        self.assertGreater(len(divergences), 0)

    def test_divergence_raises_under_shadow_strict(self):
        """SHADOW_STRICT=1 raises on any divergence."""
        os.environ["SHADOW_STRICT"] = "1"
        store.append([rec()])
        # Patch the SQLite row behind the store's back
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE records SET doc=? WHERE id=?",
                (json.dumps({"id": "meridian", "state": "enriched"}), "meridian"))
            conn.commit()
        finally:
            conn.close()
        # Now trigger another write - this should raise
        with self.assertRaises(store.ShadowDivergence):
            store.patch("meridian", {"state": "verified"})

    def test_ledger_records_writes_observed(self):
        """The ledger records writes observed as well as divergences."""
        os.environ.pop("SHADOW_STRICT", None)
        store.append([rec()])
        ledger_path = os.path.join(self.tmp, "work", "store-shadow-diff.jsonl")
        self.assertTrue(os.path.exists(ledger_path))
        with open(ledger_path, encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
        # At least one entry is a write observed
        writes = [e for e in entries if e.get("type") == "write"]
        self.assertGreater(len(writes), 0)


class TestSqliteMode(QueueTest):
    """SQLite mode: SQLite canonical, JSONL untouched."""

    def setUp(self):
        super().setUp()
        os.environ["QUEUE_BACKEND"] = "sqlite"
        self.db_path = os.path.join(self.tmp, "work", "queue.db")
        os.environ["QUEUE_DB"] = self.db_path

    def tearDown(self):
        os.environ.pop("QUEUE_BACKEND", None)
        os.environ.pop("QUEUE_DB", None)
        super().tearDown()

    def test_append_and_get(self):
        store.append([rec()])
        r = store.get("meridian")
        self.assertIsNotNone(r)
        self.assertEqual(r["id"], "meridian")
        self.assertEqual(r["state"], "queued")

    def test_patch_deep_merges(self):
        store.append([rec(company_facts={"employees": 26, "revenue": "$3.6M"})])
        store.patch("meridian", {"company_facts": {"employees": 30}, "state": "enriched"})
        r = store.get("meridian")
        self.assertEqual(r["company_facts"], {"employees": 30, "revenue": "$3.6M"})
        self.assertEqual(r["state"], "enriched")

    def test_drop_keeps_the_record(self):
        store.append([rec(), rec("lumen", company="Lumen", domain="lumen.test")])
        store.drop("meridian", "suppressed (live account)")
        r = store.get("meridian")
        self.assertEqual(r["state"], "dropped")
        self.assertEqual(r["drop_reason"], "suppressed (live account)")

    def test_list_records_filters(self):
        store.append([rec(), rec("lumen", company="Lumen", domain="lumen.test"),
                      rec("five", company="Five", domain="fivepoint.test", lane="cold")])
        store.drop("five", "no signal")
        self.assertEqual(len(store.list_records(client=store.ALL, state="queued")), 2)
        self.assertEqual(len(store.list_records(client=store.ALL, lane="cold")), 1)

    def test_stats(self):
        store.append([rec(), rec("lumen", company="Lumen", domain="lumen.test")])
        s = store.stats()
        self.assertEqual(s["records"], 2)
        self.assertEqual(s["states"], {"queued": 2})

    def test_transaction_read_modify_write(self):
        store.append([rec()])
        with store.transaction() as recs:
            for r in recs:
                if r["id"] == "meridian":
                    r["state"] = "enriched"
        r = store.get("meridian")
        self.assertEqual(r["state"], "enriched")

    def test_digest_is_revision(self):
        store.append([rec()])
        d1 = store.digest()
        store.patch("meridian", {"state": "enriched"})
        d2 = store.digest()
        self.assertNotEqual(d1, d2)
        # Revision is an integer string
        self.assertTrue(d1.isdigit() or d1 == "absent")
        self.assertTrue(d2.isdigit())

    def test_digest_refuses_changed_and_changed_back(self):
        """A write that changes a record and changes it back now REFUSES.

        This is the STRICTER behaviour of revision vs content hash. The task
        says to write the test that asserts the refusal and NOT add a shim.
        """
        store.append([rec()])
        d1 = store.digest()
        # Change and change back
        store.patch("meridian", {"state": "enriched"})
        store.patch("meridian", {"state": "queued"})
        d2 = store.digest()
        # The revision changed even though the state is the same
        self.assertNotEqual(d1, d2)
        # Now an expect_digest with the old digest should refuse
        with self.assertRaises(store.QueueChanged):
            recs = store.load()
            store.save(recs, expect_digest=d1)

    def test_order_preserved_through_cycle(self):
        """Order is preserved through a full load -> mutate -> save -> load cycle."""
        store.append([rec("a"), rec("b"), rec("c")])
        loaded = store.load()
        ids_before = [r["id"] for r in loaded]
        self.assertEqual(ids_before, ["a", "b", "c"])
        # Mutate
        for r in loaded:
            if r["id"] == "b":
                r["state"] = "enriched"
        store.save(loaded)
        # Load again
        reloaded = store.load()
        ids_after = [r["id"] for r in reloaded]
        self.assertEqual(ids_after, ["a", "b", "c"])


class TestPromotionCheck(QueueTest):
    """Promotion check refuses if ledger has zero rows AND zero observed writes."""

    def setUp(self):
        super().setUp()
        self.ledger_path = os.path.join(self.tmp, "work", "store-shadow-diff.jsonl")

    def test_empty_ledger_refuses(self):
        """A promotion check against a ledger with zero rows and zero observed
        writes REFUSES. An empty ledger because nothing ran is the vacuous pass."""
        # No ledger file exists
        result = store.check_promotion_readiness(self.ledger_path)
        self.assertFalse(result["ready"])
        self.assertIn("no writes observed", result["reason"])

    def test_ledger_with_only_divergences_refuses(self):
        """A ledger with divergences but no writes observed refuses."""
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "divergence", "id": "x", "field": "state",
                                "jsonl": "queued", "sqlite": "enriched"}) + "\n")
        result = store.check_promotion_readiness(self.ledger_path)
        self.assertFalse(result["ready"])
        self.assertIn("no writes observed", result["reason"])

    def test_ledger_with_writes_and_no_divergences_passes(self):
        """A ledger with writes observed and no divergences passes."""
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "write", "at": "2026-09-22T12:00:00+00:00"}) + "\n")
            f.write(json.dumps({"type": "write", "at": "2026-09-22T12:01:00+00:00"}) + "\n")
        result = store.check_promotion_readiness(self.ledger_path)
        self.assertTrue(result["ready"])
        self.assertEqual(result["writes"], 2)
        self.assertEqual(result["divergences"], 0)

    def test_ledger_with_writes_and_divergences_refuses(self):
        """A ledger with both writes and divergences refuses."""
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "write", "at": "2026-09-22T12:00:00+00:00"}) + "\n")
            f.write(json.dumps({"type": "divergence", "id": "x", "field": "state",
                                "jsonl": "queued", "sqlite": "enriched"}) + "\n")
        result = store.check_promotion_readiness(self.ledger_path)
        self.assertFalse(result["ready"])
        self.assertIn("divergence", result["reason"])


class TestParameterizedStoreTests(QueueTest):
    """The existing store tests parameterized over both backends.

    This is the real acceptance test for TASK-253.
    """

    def _run_for_backend(self, backend_name):
        """Helper to run a test for a specific backend."""
        if backend_name == "sqlite":
            os.environ["QUEUE_BACKEND"] = "sqlite"
            db_path = os.path.join(self.tmp, "work", "queue.db")
            os.environ["QUEUE_DB"] = db_path
        else:
            os.environ.pop("QUEUE_BACKEND", None)
            os.environ.pop("QUEUE_DB", None)

    def test_append_writes_and_logs_jsonl(self):
        self._run_for_backend("jsonl")
        store.append([rec()])
        r = store.get("meridian")
        self.assertEqual(r["state"], "queued")
        self.assertEqual(len(r["log"]), 1)
        self.assertEqual(r["log"][0]["step"], "queued")
        os.environ.pop("QUEUE_BACKEND", None)
        os.environ.pop("QUEUE_DB", None)

    def test_append_writes_and_logs_sqlite(self):
        self._run_for_backend("sqlite")
        store.append([rec()])
        r = store.get("meridian")
        self.assertEqual(r["state"], "queued")
        self.assertEqual(len(r["log"]), 1)
        self.assertEqual(r["log"][0]["step"], "queued")
        os.environ.pop("QUEUE_BACKEND", None)
        os.environ.pop("QUEUE_DB", None)

    def test_patch_deep_merges_jsonl(self):
        self._run_for_backend("jsonl")
        store.append([rec(company_facts={"employees": 26, "revenue": "$3.6M"})])
        store.patch("meridian", {"company_facts": {"employees": 30}, "state": "enriched"})
        r = store.get("meridian")
        self.assertEqual(r["company_facts"], {"employees": 30, "revenue": "$3.6M"})
        self.assertEqual(r["state"], "enriched")
        os.environ.pop("QUEUE_BACKEND", None)
        os.environ.pop("QUEUE_DB", None)

    def test_patch_deep_merges_sqlite(self):
        self._run_for_backend("sqlite")
        store.append([rec(company_facts={"employees": 26, "revenue": "$3.6M"})])
        store.patch("meridian", {"company_facts": {"employees": 30}, "state": "enriched"})
        r = store.get("meridian")
        self.assertEqual(r["company_facts"], {"employees": 30, "revenue": "$3.6M"})
        self.assertEqual(r["state"], "enriched")
        os.environ.pop("QUEUE_BACKEND", None)
        os.environ.pop("QUEUE_DB", None)

    def test_list_and_stats_filter_jsonl(self):
        self._run_for_backend("jsonl")
        store.append([rec(), rec("lumen", company="Lumen", domain="lumen.test"),
                      rec("five", company="Five", domain="fivepoint.test", lane="cold")])
        store.drop("five", "no signal")
        self.assertEqual(len(store.list_records(client=store.ALL, state="queued")), 2)
        self.assertEqual(len(store.list_records(client=store.ALL, lane="cold")), 1)
        s = store.stats()
        self.assertEqual(s["records"], 3)
        self.assertEqual(s["states"], {"queued": 2, "dropped": 1})
        os.environ.pop("QUEUE_BACKEND", None)
        os.environ.pop("QUEUE_DB", None)

    def test_list_and_stats_filter_sqlite(self):
        self._run_for_backend("sqlite")
        store.append([rec(), rec("lumen", company="Lumen", domain="lumen.test"),
                      rec("five", company="Five", domain="fivepoint.test", lane="cold")])
        store.drop("five", "no signal")
        self.assertEqual(len(store.list_records(client=store.ALL, state="queued")), 2)
        self.assertEqual(len(store.list_records(client=store.ALL, lane="cold")), 1)
        s = store.stats()
        self.assertEqual(s["records"], 3)
        self.assertEqual(s["states"], {"queued": 2, "dropped": 1})
        os.environ.pop("QUEUE_BACKEND", None)
        os.environ.pop("QUEUE_DB", None)


if __name__ == "__main__":
    unittest.main()
