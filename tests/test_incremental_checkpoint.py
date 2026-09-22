"""TASK-260: incremental checkpoint reads O(changed), not O(N).

The hazard: narrowing the read converts refuse_evidence_loss and
refuse_history_loss into no-ops for everything they did not read. The
correctness must come from the INPUT being provably sufficient.

Tests first, as the task requires.
"""
import copy
import json
import os
import random
import sqlite3
import tempfile
import unittest

from src import store, sqlitestore
from tests.base import QueueTest


def _rec(rid, **kw):
    r = store.new_record(rid, "cold", "testclient", f"Co {rid}", f"{rid}.test")
    r.update(kw)
    return r


def _rec_with_evidence(rid, email="a@test.com", provider="bison", status="valid"):
    r = _rec(rid)
    r["contacts"] = [{
        "contact_id": f"{rid}-c0",
        "key": f"{rid}-k0",
        "name": "Test",
        "email": email,
        "verification": {
            "status": "verified",
            "evidence": [{"email": email, "provider": provider, "status": status}],
        },
    }]
    return r


def _rec_with_event(rid, event_id="evt-1", event_type="replied"):
    r = _rec(rid)
    r["events"] = [{"id": event_id, "type": event_type, "at": "2026-09-22T10:00:00+00:00"}]
    return r


def _rec_with_stop(rid, paused=True):
    r = _rec(rid)
    r["paused"] = paused
    return r


class TestRevColumn(QueueTest):
    """Requirement 1: rev is monotonic and per-write."""

    def _open(self):
        path = os.path.join(self.tmp, "queue.db")
        os.environ["QUEUE_DB"] = path
        return sqlitestore.open_db(path), path

    def tearDown(self):
        os.environ.pop("QUEUE_DB", None)
        super().tearDown()

    def test_rev_column_exists_after_open(self):
        conn, _ = self._open()
        try:
            cols = {row[1] for row in
                    conn.execute("PRAGMA table_info(records)")}
            self.assertIn("rev", cols)
        finally:
            conn.close()

    def test_rev_default_zero_on_fresh_db(self):
        """DEFAULT 0 means the first checkpoint after upgrade does a full read."""
        conn, _ = self._open()
        try:
            rows = conn.execute("SELECT rev FROM records").fetchall()
            self.assertEqual(rows, [])
        finally:
            conn.close()

    def test_rev_increments_per_write(self):
        conn, _ = self._open()
        try:
            sqlitestore.write_changed(conn, [_rec("a")])
            rev1 = sqlitestore.revision(conn)
            row = conn.execute(
                "SELECT rev FROM records WHERE id='a'").fetchone()
            self.assertEqual(row[0], rev1)

            sqlitestore.write_changed(conn, [_rec("a", state="enriched")])
            rev2 = sqlitestore.revision(conn)
            row2 = conn.execute(
                "SELECT rev FROM records WHERE id='a'").fetchone()
            self.assertEqual(row2[0], rev2)
            self.assertGreater(rev2, rev1)
        finally:
            conn.close()

    def test_two_writes_same_second_get_different_rev(self):
        """updated_at is second-resolution; rev is not. This is the property
        updated_at lacked (TASK-251)."""
        conn, _ = self._open()
        try:
            sqlitestore.write_changed(conn, [_rec("x"), _rec("y")])
            rev_after_first = sqlitestore.revision(conn)

            sqlitestore.write_changed(conn, [_rec("x", state="enriched")])
            rev_after_second = sqlitestore.revision(conn)

            x_rev = conn.execute(
                "SELECT rev FROM records WHERE id='x'").fetchone()[0]
            y_rev = conn.execute(
                "SELECT rev FROM records WHERE id='y'").fetchone()[0]

            self.assertEqual(y_rev, rev_after_first)
            self.assertEqual(x_rev, rev_after_second)
            self.assertNotEqual(x_rev, y_rev)
        finally:
            conn.close()

    def test_rev_index_exists(self):
        conn, _ = self._open()
        try:
            indexes = {row[1] for row in
                       conn.execute("PRAGMA index_list(records)").fetchall()}
            self.assertIn("records_rev", indexes)
        finally:
            conn.close()


class TestReadChangedSince(QueueTest):
    """Requirement 2: read_changed_since returns exactly rows with rev > r."""

    def _open(self):
        path = os.path.join(self.tmp, "queue.db")
        os.environ["QUEUE_DB"] = path
        return sqlitestore.open_db(path), path

    def tearDown(self):
        os.environ.pop("QUEUE_DB", None)
        super().tearDown()

    def test_returns_exact_rows_above_cursor(self):
        conn, _ = self._open()
        try:
            sqlitestore.write_changed(conn, [_rec("a"), _rec("b"), _rec("c")])
            rev1 = sqlitestore.revision(conn)

            sqlitestore.write_changed(conn, [_rec("b", state="enriched")])
            rev2 = sqlitestore.revision(conn)

            changed = sqlitestore.read_changed_since(conn, rev1)
            ids = [r["id"] for r in changed]
            self.assertEqual(ids, ["b"])

            changed_all = sqlitestore.read_changed_since(conn, 0)
            ids_all = [r["id"] for r in changed_all]
            self.assertEqual(sorted(ids_all), ["a", "b", "c"])
        finally:
            conn.close()

    def test_order_is_seq_order(self):
        """Order is still load-bearing."""
        conn, _ = self._open()
        try:
            sqlitestore.write_changed(conn, [
                _rec("c"), _rec("a"), _rec("b")])
            rev1 = sqlitestore.revision(conn)

            sqlitestore.write_changed(conn, [
                _rec("a", state="enriched"),
                _rec("c", state="verified"),
            ])

            changed = sqlitestore.read_changed_since(conn, rev1)
            ids = [r["id"] for r in changed]
            self.assertEqual(ids, ["c", "a"])
        finally:
            conn.close()

    def test_empty_when_nothing_changed(self):
        conn, _ = self._open()
        try:
            sqlitestore.write_changed(conn, [_rec("a")])
            rev1 = sqlitestore.revision(conn)
            changed = sqlitestore.read_changed_since(conn, rev1)
            self.assertEqual(changed, [])
        finally:
            conn.close()


class TestMigrationDefaultZero(QueueTest):
    """An existing database with no rev column: DEFAULT 0 means the first
    checkpoint after upgrade does a full read."""

    def _open(self):
        path = os.path.join(self.tmp, "queue.db")
        os.environ["QUEUE_DB"] = path
        return sqlitestore.open_db(path), path

    def tearDown(self):
        os.environ.pop("QUEUE_DB", None)
        super().tearDown()

    def test_existing_rows_get_rev_zero_then_first_write_sets_real_rev(self):
        """Simulate migration: create a DB without rev, insert rows, then
        open with the new schema and verify DEFAULT 0 behaviour."""
        path = os.path.join(self.tmp, "queue.db")
        os.environ["QUEUE_DB"] = path

        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE records (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                doc TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                state  TEXT GENERATED ALWAYS AS (json_extract(doc,'$.state'))  VIRTUAL,
                lane   TEXT GENERATED ALWAYS AS (json_extract(doc,'$.lane'))   VIRTUAL,
                client TEXT GENERATED ALWAYS AS (json_extract(doc,'$.client')) VIRTUAL
            )
        """)
        conn.execute("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)
        """)
        conn.execute("INSERT INTO meta VALUES ('schema_version', '1')")
        conn.execute("INSERT INTO meta VALUES ('revision', '5')")
        conn.execute(
            "INSERT INTO records(id, doc, updated_at) VALUES (?,?,?)",
            ("old1", json.dumps(_rec("old1")), "2026-09-22T00:00:00+00:00"))
        conn.commit()
        conn.close()

        conn = sqlitestore.open_db(path)
        try:
            row = conn.execute(
                "SELECT rev FROM records WHERE id='old1'").fetchone()
            self.assertEqual(row[0], 0)

            rev_before = sqlitestore.revision(conn)
            sqlitestore.write_changed(conn, [_rec("old1", state="enriched")])
            rev_after = sqlitestore.revision(conn)

            row_after = conn.execute(
                "SELECT rev FROM records WHERE id='old1'").fetchone()
            self.assertEqual(row_after[0], rev_after)

            changed = sqlitestore.read_changed_since(conn, 0)
            ids = [r["id"] for r in changed]
            self.assertIn("old1", ids)
        finally:
            conn.close()


class TestIncrementalGuardInput(QueueTest):
    """Requirement 3: THE ONE THAT MATTERS.

    Property test: randomised estate, random touches, assert the narrowed
    input gives the IDENTICAL verdict to the full set. At least 200 rounds.
    """

    def _open(self):
        path = os.path.join(self.tmp, "queue.db")
        os.environ["QUEUE_DB"] = path
        return sqlitestore.open_db(path), path

    def tearDown(self):
        os.environ.pop("QUEUE_DB", None)
        super().tearDown()

    def _make_estate(self, n, rng):
        records = []
        for i in range(n):
            rid = f"rec{i:04d}"
            r = _rec_with_evidence(rid, email=f"e{i}@test.com")
            r["events"] = [{"id": f"evt-{i}-0", "type": "enriched",
                            "at": "2026-09-22T10:00:00+00:00"}]
            if rng.random() < 0.3:
                r["paused"] = True
            records.append(r)
        return records

    def _verdict_evidence(self, old_recs, new_recs):
        try:
            store.refuse_evidence_loss(old_recs, new_recs)
            return (False, set())
        except store.EvidenceLost as e:
            ids = set()
            for part in str(e).split("; "):
                rid = part.split(":")[0].strip()
                ids.add(rid)
            return (True, ids)

    def _verdict_history(self, old_recs, new_recs):
        try:
            store.refuse_history_loss(old_recs, new_recs)
            return (False, set())
        except store.HistoryLost as e:
            ids = set()
            for part in str(e).split("; "):
                rid = part.split(":")[0].strip()
                ids.add(rid)
            return (True, ids)

    def test_incremental_input_matches_full_set_200_rounds(self):
        """Property test: at least 200 randomised rounds."""
        for round_num in range(200):
            rng = random.Random(round_num)
            n = rng.randint(10, 50)
            estate = self._make_estate(n, rng)

            old_recs = [dict(r) for r in estate]

            caller_touched_ids = set(rng.sample(
                [r["id"] for r in estate],
                min(rng.randint(1, 5), n)))

            new_recs = [dict(r) for r in estate]
            for r in new_recs:
                if r["id"] in caller_touched_ids:
                    r["state"] = "verified"

            second_writer_ids = set()
            for r in new_recs:
                if r["id"] not in caller_touched_ids and rng.random() < 0.15:
                    second_writer_ids.add(r["id"])
                    if r.get("contacts"):
                        r["contacts"][0]["verification"] = {
                            "status": "unverified", "evidence": []}
                    if r.get("events"):
                        r["events"] = r["events"][:max(0, len(r["events"]) - 1)]
                    if r.get("paused"):
                        r["paused"] = False

            full_evidence_raised, full_evidence_ids = self._verdict_evidence(
                old_recs, new_recs)
            full_history_raised, full_history_ids = self._verdict_history(
                old_recs, new_recs)

            touched = caller_touched_ids | second_writer_ids
            narrowed_old = [r for r in old_recs if r["id"] in touched]
            narrowed_new = [r for r in new_recs if r["id"] in touched]

            narrow_evidence_raised, narrow_evidence_ids = \
                self._verdict_evidence(narrowed_old, narrowed_new)
            narrow_history_raised, narrow_history_ids = \
                self._verdict_history(narrowed_old, narrowed_new)

            self.assertEqual(
                full_evidence_raised, narrow_evidence_raised,
                f"round {round_num}: evidence verdict mismatch")
            if full_evidence_raised:
                self.assertEqual(
                    full_evidence_ids, narrow_evidence_ids,
                    f"round {round_num}: evidence ids mismatch")

            self.assertEqual(
                full_history_raised, narrow_history_raised,
                f"round {round_num}: history verdict mismatch")
            if full_history_raised:
                self.assertEqual(
                    full_history_ids, narrow_history_ids,
                    f"round {round_num}: history ids mismatch")


class TestUntouchedRecordLossCaught(QueueTest):
    """Requirement 4: a record the caller did not touch, that a second writer
    diminished, is still caught by virtue of the cursor."""

    def _open(self):
        path = os.path.join(self.tmp, "queue.db")
        os.environ["QUEUE_DB"] = path
        return sqlitestore.open_db(path), path

    def tearDown(self):
        os.environ.pop("QUEUE_DB", None)
        super().tearDown()

    def test_evidence_removed_from_untouched_record_is_caught(self):
        conn, _ = self._open()
        try:
            records = [
                _rec_with_evidence("caller_rec", email="c@test.com"),
                _rec_with_evidence("untouched_rec", email="u@test.com"),
            ]
            sqlitestore.write_changed(conn, records)
            baseline_rev = sqlitestore.revision(conn)

            old_recs = sqlitestore.read_all(conn)

            new_recs = [copy.deepcopy(r) for r in old_recs]
            for r in new_recs:
                if r["id"] == "caller_rec":
                    r["state"] = "verified"
                if r["id"] == "untouched_rec":
                    r["contacts"][0]["verification"] = {
                        "status": "unverified", "evidence": []}

            sqlitestore.write_changed(conn, new_recs)
            current_rev = sqlitestore.revision(conn)

            caller_touched = {"caller_rec"}
            changed_since = sqlitestore.read_changed_since(conn, baseline_rev)
            changed_ids = {r["id"] for r in changed_since}

            incremental_ids = caller_touched | changed_ids
            narrowed_old = [r for r in old_recs if r["id"] in incremental_ids]
            narrowed_new = [r for r in new_recs if r["id"] in incremental_ids]

            with self.assertRaises(store.EvidenceLost):
                store.refuse_evidence_loss(narrowed_old, narrowed_new)
        finally:
            conn.close()

    def test_stop_lifted_on_untouched_record_is_caught(self):
        conn, _ = self._open()
        try:
            records = [
                _rec("caller_rec"),
                _rec_with_stop("untouched_rec", paused=True),
            ]
            records[1]["events"] = [
                {"id": "evt-stop", "type": "replied",
                 "at": "2026-09-22T10:00:00+00:00"}]
            sqlitestore.write_changed(conn, records)
            baseline_rev = sqlitestore.revision(conn)

            old_recs = sqlitestore.read_all(conn)

            new_recs = [copy.deepcopy(r) for r in old_recs]
            for r in new_recs:
                if r["id"] == "caller_rec":
                    r["state"] = "verified"
                if r["id"] == "untouched_rec":
                    r["paused"] = False

            sqlitestore.write_changed(conn, new_recs)

            caller_touched = {"caller_rec"}
            changed_since = sqlitestore.read_changed_since(conn, baseline_rev)
            changed_ids = {r["id"] for r in changed_since}

            incremental_ids = caller_touched | changed_ids
            narrowed_old = [r for r in old_recs if r["id"] in incremental_ids]
            narrowed_new = [r for r in new_recs if r["id"] in incremental_ids]

            with self.assertRaises(store.HistoryLost):
                store.refuse_history_loss(narrowed_old, narrowed_new)
        finally:
            conn.close()


class TestFailClosedFallback(QueueTest):
    """Requirement 5: fail closed when the cursor is missing, stale, backwards,
    or the Snapshot has no baseline."""

    def _open(self):
        path = os.path.join(self.tmp, "queue.db")
        os.environ["QUEUE_DB"] = path
        return sqlitestore.open_db(path), path

    def tearDown(self):
        os.environ.pop("QUEUE_DB", None)
        super().tearDown()

    def test_no_baseline_falls_back_to_full_read(self):
        """A Snapshot built from somewhere other than load() has no baseline."""
        conn, _ = self._open()
        try:
            records = [_rec("a"), _rec("b"), _rec("c")]
            sqlitestore.write_changed(conn, records)

            plain_list = list(records)
            self.assertFalse(hasattr(plain_list, "baseline"))

            result = sqlitestore.incremental_read_or_full(
                conn, plain_list, baseline_rev=None)
            self.assertEqual(result["path"], "full")
            self.assertEqual(len(result["records"]), 3)
            self.assertGreaterEqual(result["rows_read"], 3)
        finally:
            conn.close()

    def test_missing_cursor_falls_back_to_full_read(self):
        conn, _ = self._open()
        try:
            records = [_rec("a"), _rec("b")]
            sqlitestore.write_changed(conn, records)

            snapshot = store.Snapshot(records)
            result = sqlitestore.incremental_read_or_full(
                conn, snapshot, baseline_rev=None)
            self.assertEqual(result["path"], "full")
        finally:
            conn.close()

    def test_stale_cursor_does_full_read(self):
        """A cursor older than any known revision: full read."""
        conn, _ = self._open()
        try:
            records = [_rec("a")]
            sqlitestore.write_changed(conn, records)

            sqlitestore.write_changed(conn, [_rec("a", state="enriched")])

            snapshot = store.Snapshot(records)
            result = sqlitestore.incremental_read_or_full(
                conn, snapshot, baseline_rev=0)
            self.assertEqual(result["path"], "full")
        finally:
            conn.close()

    def test_backwards_revision_falls_back(self):
        """A baseline_rev HIGHER than current revision: impossible, fall back."""
        conn, _ = self._open()
        try:
            records = [_rec("a")]
            sqlitestore.write_changed(conn, records)

            snapshot = store.Snapshot(records)
            result = sqlitestore.incremental_read_or_full(
                conn, snapshot, baseline_rev=9999)
            self.assertEqual(result["path"], "full")
        finally:
            conn.close()

    def test_incremental_path_fires_when_valid(self):
        conn, _ = self._open()
        try:
            records = [_rec("a"), _rec("b"), _rec("c")]
            sqlitestore.write_changed(conn, records)
            baseline_rev = sqlitestore.revision(conn)

            sqlitestore.write_changed(conn, [_rec("b", state="enriched")])

            snapshot = store.Snapshot(records)
            caller_touched = {"a"}
            result = sqlitestore.incremental_read_or_full(
                conn, snapshot, baseline_rev=baseline_rev,
                caller_touched=caller_touched)
            self.assertEqual(result["path"], "incremental")
            ids = {r["id"] for r in result["records"]}
            self.assertIn("a", ids)
            self.assertIn("b", ids)
            self.assertLess(result["rows_read"], 3)
        finally:
            conn.close()

    def test_rows_read_count_is_actual_not_flag(self):
        """Count the rows actually read, not a flag the code sets."""
        conn, _ = self._open()
        try:
            records = [_rec(f"r{i}") for i in range(20)]
            sqlitestore.write_changed(conn, records)
            baseline_rev = sqlitestore.revision(conn)

            sqlitestore.write_changed(conn, [_rec("r0", state="enriched")])

            snapshot = store.Snapshot(records)
            result = sqlitestore.incremental_read_or_full(
                conn, snapshot, baseline_rev=baseline_rev,
                caller_touched={"r0"})
            self.assertEqual(result["path"], "incremental")
            self.assertLessEqual(result["rows_read"], 2)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
