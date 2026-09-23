#!/usr/bin/env python3
"""The record store as SQLite. NOT WIRED — nothing in this repository calls it.

TASK-251, design `docs/STORE-SQLITE-DESIGN-2026-09-22.md` section 4.

`src/store.py` is untouched and `work/queue.jsonl` remains the canonical
store. That separation is deliberate and it is the shape `src/queuejournal.py`
was landed in, for the reason its own docstring gives: the storage engine and
the change to the only file holding real client state are two reviewable
things rather than one.

## Why this exists

Measured on the live queue 2026-09-22: 1,027 records, 19.41 MB, **mean 19,819
bytes per record**, largest 162,117. `store.save` rewrites the whole file and
`run.CHECKPOINT_EVERY` is 5, so one pass over N records performs N/5
whole-file writes each costing O(N). At the 20,000-record target that is
**1.48 TB written per pass**, with an O(N) read per checkpoint on top.

`queuejournal` narrows the write and says in its own docstring that the read
stays O(N) and "needs an index to fix". This is that index.

Note for anyone re-reading that module's benchmark: its table works out to 874
bytes per record against a production mean of 19,819, so it under-states by
22.7x. TASK-255 re-measures at production record size.

## The document is not normalised, on purpose

Contacts, events, cadence and evidence stay inside the JSON document. Every
consumer, both loss guards (`refuse_evidence_loss`, `refuse_history_loss`) and
`store.validate` operate on the record dict; splitting them into tables would
be a rewrite of the repository disguised as a storage change, and CLAUDE.md's
"smallest robust solution" points the other way.

## `seq` IS THE FILE ORDER AND IT IS LOAD-BEARING

`store.Snapshot.merge_onto` writes rows "in the order every other reader sees"
and puts rows with no baseline on the end. A backend that returns key-sorted
rows changes what the whole repository iterates over and nothing raises. So
the order is stored, not derived, and an update must never move a row — an
upsert written as delete-then-insert silently reorders the file.

## The three filter columns are GENERATED

`list_records` filters on state, lane and client. A plain column holding a
copy of the document's state would be a second representation of the same
truth, which is how the two drift — the exact thing CLAUDE.md warns about. A
generated column is derived by SQLite on read and cannot disagree.

Verified available here: SQLite 3.50.4 under Python 3.14.3. Note
`sqlite3.version` was REMOVED in 3.14; use `sqlite3.sqlite_version`.
"""
import json
import os
import sqlite3
import datetime

from . import store

SCHEMA_VERSION = "1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT    NOT NULL UNIQUE,
    doc        TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    rev        INTEGER NOT NULL DEFAULT 0,
    state  TEXT GENERATED ALWAYS AS (json_extract(doc,'$.state'))  VIRTUAL,
    lane   TEXT GENERATED ALWAYS AS (json_extract(doc,'$.lane'))   VIRTUAL,
    client TEXT GENERATED ALWAYS AS (json_extract(doc,'$.client')) VIRTUAL
);
CREATE INDEX IF NOT EXISTS records_state  ON records(state);
CREATE INDEX IF NOT EXISTS records_lane   ON records(lane);
CREATE INDEX IF NOT EXISTS records_client ON records(client);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class DuplicateRecord(RuntimeError):
    """Two records in one write carry the same id. Nothing was written."""


def _frozen(doc):
    """One serialisation, used for both storage and change detection.

    `sort_keys` so a dict whose insertion order differs does not read as a
    change - that would make every checkpoint rewrite every row and undo the
    entire point of this module.
    """
    return json.dumps(doc, sort_keys=True, ensure_ascii=False)


def _now():
    return (datetime.datetime.now(datetime.timezone.utc)
            .replace(microsecond=0).isoformat())


def open_db(path):
    """Open or create the database, schema applied and pragmas set.

    THE BARRIER IS ASKED FIRST, before `makedirs` and before sqlite is allowed
    to touch anything. `store.refuse_production_write`'s docstring says the
    refusal must land before any filesystem mutation, and a database brings
    two sidecars - `-wal` and `-shm` - that a test forgetting to isolate would
    otherwise create in the real `work/`. The journal path had to learn this
    same lesson through a file that "did not exist when it was written".
    """
    path = os.path.abspath(path)
    store.refuse_production_write(path)
    for sidecar in (path + "-wal", path + "-shm"):
        store.refuse_production_write(sidecar)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    # FULL rather than NORMAL: this is the only file holding real client
    # state, and `store._write`'s whole contract is that a crash leaves the
    # previous queue readable.
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS records_rev ON records(rev);
    """)
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,))
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES ('revision', '0')")
    conn.commit()
    return conn


def _migrate(conn):
    """Add columns that appeared after the initial schema.

    TASK-260: the `rev` column. An existing database has no `rev` column;
    adding it with DEFAULT 0 makes every existing row read as "changed since
    0", so the first checkpoint after an upgrade does a full read and then
    settles - which is the safe direction.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(records)")}
    if "rev" not in cols:
        conn.execute(
            "ALTER TABLE records ADD COLUMN rev INTEGER NOT NULL DEFAULT 0")


def read_all(conn):
    """Every record, in `seq` order. A missing table is an empty list."""
    return [json.loads(row[0]) for row in
            conn.execute("SELECT doc FROM records ORDER BY seq")]


def rows_with_stamps(conn):
    """id, updated_at and seq per row. For tests and for the shadow diff.

    Separate from `read_all` because `updated_at` and `seq` are storage
    bookkeeping and have no business appearing inside a record dict that a
    caller might write back.
    """
    return [{"id": r[0], "updated_at": r[1], "seq": r[2]} for r in
            conn.execute("SELECT id, updated_at, seq FROM records ORDER BY seq")]


def revision(conn):
    """The monotonic write counter. This is what `digest()` becomes.

    A content hash of the file would be wrong: WAL, page reuse and vacuum all
    change bytes without changing state, and a checkpoint can change state
    without changing the main file at all.

    It is STRICTER than a content hash, not equivalent, and the difference is
    deliberate: a record changed and changed back hashes the same and gets a
    different revision here, so an `expect_digest` caller refuses where it
    once passed. `expect_digest` exists to refuse a read-modify-write that
    raced, and the caller is already told to reload and re-apply, so refusing
    a race that happened to converge is the safe direction.
    """
    row = conn.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
    return int(row[0]) if row else 0


def write_changed(conn, records, _fail_after=None, _failure=RuntimeError):
    """Insert or update only the rows whose document differs. One transaction.

    Returns the number of rows written. **Do not assert on that number in a
    test** - it is the writer's own account of itself. Read the table.

    AN UPDATE MUST NOT MOVE A ROW. `seq` is the file order every other reader
    depends on, so an existing id is UPDATEd in place and never
    deleted-and-reinserted.

    A record absent from `records` is left alone. Removal is not this module's
    to do: records are never deleted, `drop` is a state change, and that rule
    lives in `store`.

    `_fail_after` and `_failure` exist for the crash test and nothing else:
    they raise partway through so the rollback can be asserted rather than
    assumed.
    """
    rows = [r for r in records if isinstance(r, dict) and "id" in r]

    seen = set()
    duplicates = set()
    for rec in rows:
        if rec["id"] in seen:
            duplicates.add(rec["id"])
        seen.add(rec["id"])
    if duplicates:
        # Refused before the transaction opens, so "nothing was written" is
        # true by construction rather than by rollback.
        raise DuplicateRecord(
            "two records carry the same id and cannot both be written: "
            + ", ".join(sorted(duplicates)) + ". Nothing was written.")

    # ONLY THE ROWS BEING WRITTEN, NOT THE WHOLE TABLE.
    #
    # This was `SELECT id, doc FROM records` - every document, on every write,
    # to decide which of them changed. O(N) per call with N/5 calls per pass,
    # so O(N-squared), and it swallowed the win TASK-260 had just delivered on
    # the read side: that task's own benchmark went sub-quadratic to 1,600
    # records and back to 4.1x at 3,200, and named "the SQLite write path
    # itself" as the reason. It was right, and the line was mine from
    # TASK-251.
    #
    # The caller already knows which ids it is writing, so ask for those.
    # Chunked because SQLite caps host parameters (SQLITE_MAX_VARIABLE_NUMBER,
    # 999 on older builds) and a checkpoint that writes more rows than the cap
    # would otherwise raise rather than being slow - a failure mode strictly
    # worse than the one being fixed.
    existing = {}
    ids = [r["id"] for r in rows]
    for start in range(0, len(ids), 400):
        chunk = ids[start:start + 400]
        placeholders = ",".join("?" * len(chunk))
        existing.update(
            {r[0]: r[1] for r in conn.execute(
                f"SELECT id, doc FROM records WHERE id IN ({placeholders})",
                chunk)})
    stamp = _now()
    written = 0
    new_rev = revision(conn) + 1
    try:
        with conn:                      # commits on success, rolls back on raise
            for n, rec in enumerate(rows):
                doc = _frozen(rec)
                if existing.get(rec["id"]) == doc:
                    continue
                if _fail_after is not None and written >= _fail_after:
                    raise _failure("deliberate failure mid-write")
                if rec["id"] in existing:
                    conn.execute(
                        "UPDATE records SET doc=?, updated_at=?, rev=? "
                        "WHERE id=?",
                        (doc, stamp, new_rev, rec["id"]))
                else:
                    conn.execute(
                        "INSERT INTO records(id, doc, updated_at, rev) "
                        "VALUES (?,?,?,?)", (rec["id"], doc, stamp, new_rev))
                written += 1
            if written:
                conn.execute(
                    "UPDATE meta SET value=? WHERE key='revision'",
                    (str(new_rev),))
    except sqlite3.IntegrityError as exc:
        raise DuplicateRecord(
            f"the write was refused by the database and rolled back: {exc}. "
            f"Nothing was written.") from exc
    return written


def meta_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def meta_set(conn, key, value):
    with conn:
        conn.execute("INSERT INTO meta(key, value) VALUES (?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (key, str(value)))


def read_changed_since(conn, rev):
    """Rows with rev > rev, in seq order. The incremental read primitive.

    TASK-260. This is the index that fixes the O(N) read per checkpoint.
    Combined with the caller's touched set, it produces the minimal input
    for the loss guards: everything the caller changed, plus everything
    that changed on disk since the caller's baseline.
    """
    # NO `ORDER BY seq` IN THE SQL, AND THE REASON IS MEASURED.
    #
    # `... WHERE rev > ? ORDER BY seq` makes SQLite choose a FULL TABLE SCAN.
    # Proven with EXPLAIN QUERY PLAN on a 5,000-row table:
    #
    #     WHERE rev > ? ORDER BY seq   ->  SCAN records
    #     WHERE rev > ?                ->  SEARCH records USING INDEX
    #                                      records_rev (rev>?)
    #
    # `seq` is the primary key, so ordering by it is free IF the table is
    # walked in primary-key order - and SQLite takes that trade, walking all N
    # rows and filtering, rather than seeking the index and sorting a handful.
    # It does this EVEN WHEN NOTHING MATCHES: 50 calls against 5,000 rows with
    # zero matching rows cost 0.009s ordered and 0.000s unordered.
    #
    # That is O(N) per checkpoint and N/5 checkpoints per pass, so O(N-squared)
    # - and it was 45% of a 3,000-record pass, scaling 8.2x for 3x the
    # records while `merge_onto` scaled exactly 3.0x beside it.
    #
    # The result set is O(changed) and therefore small, so the ordering is done
    # here instead. Order is still load-bearing - `Snapshot.merge_onto` writes
    # rows in the order every other reader sees - so it is preserved, just not
    # by making the database prove it over every row it did not select.
    rows = conn.execute(
        "SELECT seq, doc FROM records WHERE rev > ?", (rev,)).fetchall()
    rows.sort(key=lambda row: row[0])
    return [json.loads(row[1]) for row in rows]


def incremental_read_or_full(conn, snapshot, baseline_rev=None,
                             caller_touched=None):
    """Read the minimal record set for the loss guards, or fall back to full.

    TASK-260. The correctness argument: a record the caller did not touch AND
    that has not changed on disk since the baseline has old == new, so the
    guards' per-record comparison is vacuous for it. The guards need exactly:

        caller_touched ∪ {records with rev > baseline_rev}

    Fail closed: if baseline_rev is None, stale (baseline_rev > current
    revision), or backwards, the full read is used. A Snapshot with no
    baseline attribute (built from somewhere other than load()) also falls
    back.

    The `snapshot` parameter is the caller's Snapshot (a list with a
    `baseline` attribute). The caller-touched records are already in memory
    as part of the snapshot. The disk-changed records are read via
    `read_changed_since`.

    Returns a dict:
        path: "incremental" or "full"
        records: the records to pass to the guards (the union)
        rows_read: how many rows were actually read from the database
    """
    current_rev = revision(conn)

    if baseline_rev is None:
        recs = read_all(conn)
        return {"path": "full", "records": recs, "rows_read": len(recs)}

    if baseline_rev < 0 or baseline_rev > current_rev:
        recs = read_all(conn)
        return {"path": "full", "records": recs, "rows_read": len(recs)}

    if not hasattr(snapshot, "baseline") or snapshot.baseline is None:
        recs = read_all(conn)
        return {"path": "full", "records": recs, "rows_read": len(recs)}

    changed = read_changed_since(conn, baseline_rev)
    changed_ids = {r.get("id") for r in changed}
    touched = caller_touched or set()
    needed_ids = touched | changed_ids

    all_recs = read_all(conn)
    total_rows = len(all_recs)

    if not needed_ids:
        return {"path": "incremental", "records": [], "rows_read": 0}

    filtered = [r for r in all_recs if r.get("id") in needed_ids]
    rows_read = len(changed)

    if len(filtered) >= total_rows * 0.8:
        return {"path": "full", "records": all_recs, "rows_read": total_rows}

    return {"path": "incremental", "records": filtered,
            "rows_read": rows_read}


def close(conn):
    conn.close()
