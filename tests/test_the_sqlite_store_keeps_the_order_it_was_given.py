"""The SQLite record store, before anything reads it.

TASK-251. `src/sqlitestore.py` has NO CALLER and `src/store.py` is untouched;
that separation is the point, and it is the shape `src/queuejournal.py` was
landed in for the reason its own docstring gives - the storage engine and the
change to the only file holding real client state are two reviewable things.

THE REQUIREMENT MOST LIKELY TO BE GOT WRONG IS ORDER, and it is the one that
breaks every caller silently. `store.Snapshot.merge_onto` writes rows "in the
order every other reader sees", and rows with no baseline go on the end. A
backend that returns key-sorted rows changes what the whole repository
iterates over, and nothing would raise.
"""
import json
import os
import sqlite3
import tempfile
import unittest

from src import sqlitestore, store


def record(rid, **extra):
    rec = {"id": rid, "lane": "cold", "client": "productive",
           "company": f"Co {rid}", "domain": f"{rid}.test",
           "state": "queued", "drop_reason": None, "log": []}
    rec.update(extra)
    return rec


class ADatabaseInATempDirectory(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "queue.db")
        self.conn = sqlitestore.open_db(self.path)
        self.addCleanup(self.conn.close)


class TheOrderIsTheOrderItWasGiven(ADatabaseInATempDirectory):

    def test_five_hundred_records_read_back_in_insertion_order(self):
        ids = [f"rec-{n:04d}" for n in range(500)]
        # Shuffled deterministically: if the backend sorts by id, this fails;
        # if it preserves insertion, it passes. A sorted input could not tell
        # the two apart, which is why the input is not sorted.
        shuffled = ids[250:] + ids[:250]
        sqlitestore.write_changed(self.conn, [record(r) for r in shuffled])
        self.assertEqual([r["id"] for r in sqlitestore.read_all(self.conn)],
                         shuffled)

    def test_a_record_added_later_goes_on_the_end(self):
        sqlitestore.write_changed(self.conn, [record("a"), record("b")])
        sqlitestore.write_changed(self.conn, [record("a"), record("b"),
                                              record("c")])
        self.assertEqual([r["id"] for r in sqlitestore.read_all(self.conn)],
                         ["a", "b", "c"])

    def test_updating_a_record_does_not_move_it(self):
        """The hazard: an upsert implemented as delete-then-insert silently
        moves the row to the end, which reorders the file for every reader."""
        sqlitestore.write_changed(self.conn,
                                  [record("a"), record("b"), record("c")])
        sqlitestore.write_changed(self.conn, [record("a", state="enriched")])
        rows = sqlitestore.read_all(self.conn)
        self.assertEqual([r["id"] for r in rows], ["a", "b", "c"])
        self.assertEqual(rows[0]["state"], "enriched")


class EveryRecordShapeRoundTrips(ADatabaseInATempDirectory):

    def _round_trip(self, rec):
        sqlitestore.write_changed(self.conn, [rec])
        got = sqlitestore.read_all(self.conn)[0]
        self.assertEqual(json.dumps(got, sort_keys=True, ensure_ascii=False),
                         json.dumps(rec, sort_keys=True, ensure_ascii=False))

    def test_a_plain_record(self):
        self._round_trip(record("plain"))

    def test_nested_contacts_excluded_events_cadence_and_log(self):
        self._round_trip(record(
            "nested",
            contacts=[{"key": "k1", "name": "A Person",
                       "verification": {"evidence": [
                           {"email": "a@b.test", "provider": "reoon",
                            "status": "valid", "at": "2026-09-22T00:00:00+00:00"}]}}],
            excluded=[{"key": "k2", "why": "wrong persona"}],
            events=[{"id": "ev1", "type": "REPLY_RECEIVED", "contact": "k1"}],
            cadence={"a-person": {"day1": {"channel": "email",
                                           "subject": "s", "body": "b"}}},
            log=[{"step": "queued", "at": "2026-09-22T00:00:00+00:00",
                  "note": "ingested"}]))

    def test_unicode_survives(self):
        self._round_trip(record("unicode", company="Ćuk Šimić d.o.o. — 東京",
                                context="naïve café ✓"))

    def test_empty_and_null_fields_are_not_coerced(self):
        """`drop_reason: None` must not come back as the string 'None', and an
        empty list must not come back as null. Both are load-bearing:
        `validate` refuses a dropped record with no reason."""
        self._round_trip(record("empties", drop_reason=None, contacts=[],
                                company_facts={}, diagnosis=None, hook=None))

    def test_a_record_at_the_measured_production_maximum(self):
        """162,117 bytes is the largest record on the real queue on
        2026-09-22. A backend with a column limit fails here and nowhere
        else."""
        big = record("big", context="x" * 162_000)
        self._round_trip(big)
        self.assertGreater(
            len(json.dumps(sqlitestore.read_all(self.conn)[0])), 160_000)


class WriteChangedWritesOnlyWhatChanged(ADatabaseInATempDirectory):

    def test_five_of_five_hundred(self):
        """Counted by `conn.total_changes`, which is SQLite's own tally of
        rows modified — an independent observable rather than the writer's
        account of itself.

        `updated_at` cannot do this job: it is second-resolution, matching
        `store.now()`, so two writes inside one second are indistinguishable
        by it. That is fine for the product — change detection compares the
        DOCUMENT, not the stamp — but it makes the stamp useless as a test
        probe, which is worth knowing before somebody builds one on it.
        """
        recs = [record(f"r{n:03d}") for n in range(500)]
        sqlitestore.write_changed(self.conn, recs)
        for rec in recs[:5]:
            rec["state"] = "enriched"

        before = self.conn.total_changes
        sqlitestore.write_changed(self.conn, recs)
        # 5 record rows + 1 meta revision row.
        self.assertEqual(self.conn.total_changes - before, 6)

        changed = [r["id"] for r in sqlitestore.read_all(self.conn)
                   if r["state"] == "enriched"]
        self.assertEqual(changed, [f"r{n:03d}" for n in range(5)])

    def test_writing_an_unchanged_set_changes_nothing(self):
        recs = [record(f"r{n}") for n in range(20)]
        sqlitestore.write_changed(self.conn, recs)
        before = self.conn.total_changes
        sqlitestore.write_changed(self.conn, recs)
        self.assertEqual(self.conn.total_changes, before,
                         "an unchanged set touched a row")


class TheRevisionIsTheDigest(ADatabaseInATempDirectory):

    def test_it_moves_on_a_write_that_changed_something(self):
        before = sqlitestore.revision(self.conn)
        sqlitestore.write_changed(self.conn, [record("a")])
        self.assertGreater(sqlitestore.revision(self.conn), before)

    def test_it_does_not_move_when_nothing_changed(self):
        sqlitestore.write_changed(self.conn, [record("a")])
        settled = sqlitestore.revision(self.conn)
        sqlitestore.write_changed(self.conn, [record("a")])
        self.assertEqual(sqlitestore.revision(self.conn), settled)

    def test_it_moves_again_on_a_change_back(self):
        """THE DELIBERATE DIFFERENCE FROM A CONTENT HASH, asserted rather than
        worked around. A record changed and changed back hashes the same and
        has a DIFFERENT revision, so `expect_digest` refuses where it once
        passed. That is the safe direction - the caller is already told to
        reload and re-apply - and a future session must not add a shim to
        bring the old behaviour back."""
        sqlitestore.write_changed(self.conn, [record("a")])
        start = sqlitestore.revision(self.conn)
        sqlitestore.write_changed(self.conn, [record("a", state="enriched")])
        sqlitestore.write_changed(self.conn, [record("a", state="queued")])
        self.assertGreater(sqlitestore.revision(self.conn), start)
        self.assertEqual(sqlitestore.read_all(self.conn)[0]["state"], "queued")


class ARecordIsNeverDeleted(ADatabaseInATempDirectory):

    def test_the_module_exposes_no_delete(self):
        """`drop` is a state change and belongs to `store`. A delete here
        would be a second way to remove a record, outside every guard."""
        for name in dir(sqlitestore):
            self.assertNotIn(
                name.lower().replace("_", ""),
                ("delete", "deleterecord", "remove", "removerecord", "purge"),
                f"sqlitestore exposes {name!r}")

    def test_writing_a_shorter_set_does_not_remove_the_others(self):
        sqlitestore.write_changed(self.conn,
                                  [record("a"), record("b"), record("c")])
        sqlitestore.write_changed(self.conn, [record("b", state="enriched")])
        self.assertEqual([r["id"] for r in sqlitestore.read_all(self.conn)],
                         ["a", "b", "c"])


class AnIdCollisionRefusesAndWritesNothing(ADatabaseInATempDirectory):

    def test_two_records_with_one_id_raise(self):
        with self.assertRaises(Exception):
            sqlitestore.write_changed(self.conn,
                                      [record("dup"), record("dup")])

    def test_nothing_was_written_by_that(self):
        sqlitestore.write_changed(self.conn, [record("keep")])
        before = sqlitestore.read_all(self.conn)
        with self.assertRaises(Exception):
            sqlitestore.write_changed(
                self.conn, [record("new-a"), record("dup"), record("dup")])
        self.assertEqual(sqlitestore.read_all(self.conn), before)


class ACrashMidWriteLeavesThePreviousStateReadable(ADatabaseInATempDirectory):

    def test_the_set_before_the_failed_write_survives_whole(self):
        good = [record("a"), record("b")]
        sqlitestore.write_changed(self.conn, good)
        before = sqlitestore.read_all(self.conn)
        before_rev = sqlitestore.revision(self.conn)

        boom = [record("a", state="enriched"), record("c")]

        class Boom(RuntimeError):
            pass

        with self.assertRaises(Boom):
            sqlitestore.write_changed(self.conn, boom,
                                      _fail_after=1, _failure=Boom)
        self.assertEqual(sqlitestore.read_all(self.conn), before)
        self.assertEqual(sqlitestore.revision(self.conn), before_rev)


class TheBarrierCoversTheDatabaseAndItsSidecars(unittest.TestCase):
    """`store.refuse_production_write` must cover `queue.db`, `-wal` and
    `-shm`. The journal path had to learn this: `_write_delta` calls the
    barrier explicitly because the sidecar "did not exist when it was
    written"."""

    def test_opening_a_database_in_the_real_work_directory_refuses(self):
        target = os.path.join(store.PRODUCTION_WORK, "queue.db")
        with self.assertRaises(store.ProductionStateUnderTest):
            sqlitestore.open_db(target)

    def test_nothing_was_created_by_that(self):
        """The refusal has to land before any filesystem mutation, including
        creating the directory - `store.refuse_production_write` says so and
        `open_db` must ask before it opens."""
        before = sorted(os.listdir(store.PRODUCTION_WORK))
        for name in ("queue.db", "queue.db-wal", "queue.db-shm"):
            try:
                sqlitestore.open_db(
                    os.path.join(store.PRODUCTION_WORK, name))
            except store.ProductionStateUnderTest:
                pass
        self.assertEqual(sorted(os.listdir(store.PRODUCTION_WORK)), before)


class TheSchemaIsWhatTheDesignSays(ADatabaseInATempDirectory):

    def test_the_filter_columns_are_generated_not_stored(self):
        """A plain column holding a copy of the document's state is a second
        representation of the same truth, which is how the two drift."""
        sql = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='records'").fetchone()[0]
        for column in ("state", "lane", "client"):
            self.assertIn("GENERATED ALWAYS AS", sql)
            self.assertIn(f"$.{column}", sql)

    def test_a_generated_column_cannot_disagree_with_the_document(self):
        sqlitestore.write_changed(self.conn, [record("a")])
        sqlitestore.write_changed(self.conn, [record("a", state="enriched")])
        got = self.conn.execute(
            "SELECT state FROM records WHERE id='a'").fetchone()[0]
        self.assertEqual(got, "enriched")

    def test_the_filter_columns_are_indexed(self):
        names = {row[0] for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        for column in ("state", "lane", "client"):
            self.assertIn(f"records_{column}", names)

    def test_journal_mode_is_wal(self):
        self.assertEqual(
            self.conn.execute("PRAGMA journal_mode").fetchone()[0].lower(),
            "wal")


class ItDoesNotTouchTheRealStore(unittest.TestCase):

    def test_store_py_is_not_used_for_anything_but_the_barrier(self):
        """A circular dependency between the two stores is how this becomes
        hard to reason about. The only thing `sqlitestore` may want from
        `store` is `refuse_production_write`.

        WALKED AS AN AST, NOT GREPPED. The first version of this test searched
        the source text and failed on its own module docstring, which explains
        `store.save`'s cost as the reason this module exists. That is exactly
        the failure CLAUDE.md names - "searching source for words produces a
        test that fails when somebody writes a comment, which has happened
        repeatedly here" - and it happened here within the hour. What matters
        is which attributes are actually reached, so that is what is asserted.
        """
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(sqlitestore))
        used = {node.attr for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "store"}
        self.assertEqual(
            used - {"refuse_production_write"}, set(),
            "sqlitestore reaches into store for more than the barrier")

if __name__ == "__main__":
    unittest.main()
