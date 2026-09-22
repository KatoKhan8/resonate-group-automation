PRIORITY: P1
DEPENDS:

# TASK-251 — the SQLite record store, with no caller

Design: `docs/STORE-SQLITE-DESIGN-2026-09-22.md`. Read it first; this task
builds section 4 and nothing else.

**NOT WIRED. `src/store.py` IS NOT TOUCHED BY THIS TASK.** That is the whole
shape of it, and it is the shape `src/queuejournal.py` was landed in for the
same reason its docstring gives: *"the storage engine and the change to the
only file holding real client state are two reviewable things rather than
one"*. A diff that also edits `store.py` will be sent back.

## Why

`work/queue.jsonl` is 1,027 records, 19.41 MB, mean 19,819 bytes per record,
measured 2026-09-22. `store.save` rewrites the whole file and
`run.CHECKPOINT_EVERY` is 5, so one pass over N records performs N/5
whole-file writes each costing O(N). At the 20,000-record target that is
**1.48 TB written per pass**, and the O(N) read per checkpoint on top.

The journal halves that and says so itself. This is the other half.

## Build

`src/sqlitestore.py`. Stdlib `sqlite3` only — zero third-party deps is a
standing rule and `sqlite3` is in the standard library. Verified present here:
SQLite 3.50.4 under Python 3.14.3.

    open_db(path)                 create or open, apply schema, set pragmas
    read_all(conn)                every record, IN SEQ ORDER, as dicts
    write_changed(conn, records)  upsert only rows whose document differs
    revision(conn)                the monotonic counter
    close(conn)

Schema exactly as the design's section 4:

```sql
CREATE TABLE records (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT    NOT NULL UNIQUE,
    doc        TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    state  TEXT GENERATED ALWAYS AS (json_extract(doc,'$.state'))  VIRTUAL,
    lane   TEXT GENERATED ALWAYS AS (json_extract(doc,'$.lane'))   VIRTUAL,
    client TEXT GENERATED ALWAYS AS (json_extract(doc,'$.client')) VIRTUAL
);
CREATE INDEX records_state  ON records(state);
CREATE INDEX records_lane   ON records(lane);
CREATE INDEX records_client ON records(client);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```

`journal_mode = WAL`, `synchronous = FULL`. The three filter columns are
GENERATED, not stored: `list_records` filters on them, and a plain column
holding a copy of the document's state is a second representation of the same
truth, which is how the two drift.

## Falsifiable requirements — write these tests FIRST

1. **Order is preserved exactly.** `read_all` returns records in `seq` order,
   and `seq` follows insertion order. Write 500 records in a shuffled order,
   read them back, assert the sequence is identical to what went in.
   *This is the requirement most likely to be got wrong and it is the one that
   breaks every caller silently:* `Snapshot.merge_onto` writes rows "in the
   order every other reader sees", so a backend that returns key-sorted rows
   changes what the whole repository iterates over.
2. **Every record shape round-trips byte-identically.** Take the record
   fixtures in `tests/fixtures/` plus one synthesised to the measured
   production extremes (a 162 KB record; nested `contacts`, `excluded`,
   `events`, `cadence`; unicode; an empty list; a null; a `drop_reason`).
   `json.dumps(read_all(...)[i], sort_keys=True)` must equal the input's.
3. **`write_changed` writes only what changed.** Insert 500, change 5, call
   `write_changed`, and assert exactly 5 rows have a new `updated_at`.
   Assert it by reading the table, not by trusting a returned count.
4. **The revision moves on every write and only on a write.** `revision()`
   strictly increases across each `write_changed` that changed anything, and
   does NOT move when `write_changed` is called with nothing changed.
5. **A record is never deleted.** There is no delete path. Assert the module
   exposes none — `drop` is a state change and belongs to `store`.
6. **An id collision refuses.** Two records with one id raises, and nothing is
   written. The `UNIQUE` constraint does this; assert the transaction rolled
   back rather than assuming it.
7. **A crash mid-write leaves the previous state readable.** Kill the write
   between statements (raise inside the transaction) and assert `read_all`
   returns the pre-write set, whole.
8. **`refuse_production_write` covers the database AND its sidecars.** A test
   that has not isolated the store must not be able to create
   `work/queue.db`, `work/queue.db-wal` or `work/queue.db-shm`. Call the
   barrier before any filesystem mutation, including `makedirs` — `store`'s
   own comment says the refusal must land first, and `_write_delta` had to
   learn this when the journal sidecar "did not exist when it was written".

## What NOT to do

- **Do not normalise the record.** Contacts, events, cadence and evidence stay
  inside the JSON document. Every consumer, both loss guards and
  `store.validate` operate on the record dict; splitting them into tables is a
  rewrite of the repository disguised as a storage change.
- **Do not touch `store.py`, `queuejournal.py` or anything in `work/`.**
- **Do not add a `digest()`.** That is TASK-253's, and it changes meaning.
- **Do not import `store` for anything but `refuse_production_write`.** A
  circular import between the two stores is how this gets hard to reason
  about.
- `sqlite3.version` was REMOVED in Python 3.14. Use `sqlite3.sqlite_version`.
  Reading the old attribute raises `AttributeError` on this machine.

## Done when

Tests green in isolation, `src/store.py` unchanged in the diff, and the module
has no caller anywhere in `src/`.
