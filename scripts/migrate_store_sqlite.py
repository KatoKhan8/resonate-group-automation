#!/usr/bin/env python3
"""One-shot migration from `work/queue.jsonl` to the SQLite store.

TASK-252, design `docs/STORE-SQLITE-DESIGN-2026-09-22.md` section 8.

Usage:
    python scripts/migrate_store_sqlite.py <path-to-queue.db>

Steps, in this order:
  1. Take `store.lock()`. Nothing else may write for the duration.
  2. Read through `store._current_records()`, NOT `read_jsonl(queue_path())`.
     With journalling on, reading the base file alone silently drops every
     checkpoint since the last compaction.
  3. Insert in file order, one transaction, `seq` ascending.
  4. Record `meta.migrated_from` = the source digest, `meta.revision` = 1.
  5. Verify before reporting success: read every record back and compare the
     serialised document AND the position against the source, record for
     record. Any mismatch rolls back and refuses.
  6. Never delete or modify `queue.jsonl`.

Idempotence:
    migrated_from == current source digest   completed; no-op, exit 0
    migrated_from != current source digest   REFUSE, exit non-zero
    no database                              migrate
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import store, sqlitestore


def _verify(conn, source_records):
    """Read every record back and compare serialised doc AND position.

    Returns True on match. On mismatch: closes the connection, deletes the
    database file and its sidecars, returns False.
    """
    rows = conn.execute(
        "SELECT doc FROM records ORDER BY seq").fetchall()
    if len(rows) != len(source_records):
        return False
    for row, src in zip(rows, source_records):
        expected = json.dumps(src, sort_keys=True, ensure_ascii=False)
        if row[0] != expected:
            return False
    return True


def _remove_database(path):
    """Delete the database and its WAL/SHM sidecars, if present."""
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except FileNotFoundError:
            pass


def migrate(db_path, _after_insert=None):
    """Run the migration. Returns (exit_code, message).

    `_after_insert` is a test seam and nothing else: a callable invoked with
    `(conn, db_path)` after the rows are inserted and BEFORE `_verify` runs, so
    a test can corrupt the database in the one window the verifier exists to
    police. It is a parameter rather than an environment variable so it cannot
    be reached from outside this process. Nothing in production passes it.
    """
    db_path = os.path.abspath(db_path)

    store.refuse_production_write(db_path)
    for sidecar in (db_path + "-wal", db_path + "-shm"):
        store.refuse_production_write(sidecar)

    source_digest = store.digest()

    with store.lock():
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            try:
                existing = sqlitestore.meta_get(conn, "migrated_from")
                if existing == source_digest:
                    conn.close()
                    return 0, ("migration already completed: migrated_from "
                               "matches current source digest. No-op.")
                elif existing is not None:
                    conn.close()
                    return 2, (f"REFUSED: migrated_from ({existing[:16]}...) "
                               f"does not match current source digest "
                               f"({source_digest[:16]}...). Do not guess "
                               f"which is newer.")
                else:
                    conn.close()
                    _remove_database(db_path)

            except Exception:
                conn.close()
                raise

        source_records = store._current_records()

        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(sqlitestore.SCHEMA)

        try:
            with conn:
                for rec in source_records:
                    doc = sqlitestore._frozen(rec)
                    stamp = sqlitestore._now()
                    conn.execute(
                        "INSERT INTO records(id, doc, updated_at) "
                        "VALUES (?,?,?)", (rec["id"], doc, stamp))
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) "
                    "VALUES ('revision', '1')")
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) "
                    "VALUES ('migrated_from', ?)", (source_digest,))
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) "
                    "VALUES ('schema_version', ?)",
                    (sqlitestore.SCHEMA_VERSION,))

            # A SEAM, NOT AN ENVIRONMENT HOOK. This was
            # `_MIGRATE_CORRUPT_HOOK`: an arbitrary file named by an
            # environment variable, run as a subprocess with `check=True`,
            # unguarded, on the path that migrates the only file holding real
            # client state. The test needs the database corrupted between
            # insert and verify; it does not need this script to be able to
            # execute anything the environment points it at.
            #
            # A parameter cannot be reached from outside the process at all,
            # which is the property that matters. It follows
            # `sqlitestore.write_changed`'s `_fail_after`, and it is why
            # `store.save`'s `allow_history_loss` is a keyword argument that
            # `test_invariants` forbids `src/` from passing rather than a flag
            # in the environment: an escape hatch nobody can reach for in
            # production is a different thing from a guard with a hole in it.
            if _after_insert is not None:
                _after_insert(conn, db_path)

            if not _verify(conn, source_records):
                conn.close()
                _remove_database(db_path)
                return 3, ("REFUSED: verification failed. The database did "
                           "not match the source after insert. Rolled back.")

            conn.close()
            return 0, (f"migration complete: {len(source_records)} records "
                       f"written and verified, digest={source_digest[:16]}...")

        except Exception:
            conn.close()
            _remove_database(db_path)
            raise


def main(argv=None):
    argv = argv or sys.argv
    if len(argv) < 2:
        print("usage: migrate_store_sqlite.py <path-to-queue.db>",
              file=sys.stderr)
        return 1
    db_path = argv[1]
    code, message = migrate(db_path)
    if code == 0:
        print(message)
    else:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
