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

---

STATUS
DONE — built on branch `infra` rather than dispatched to a worker. The Qwen
pool's worktrees were carrying other sessions' branches (task-244 … 249) and
dispatching into shared infrastructure was not mine to do without asking; the
task is small enough that writing it was cheaper than coordinating it.

COMMIT SHA
3402ddd9

TESTS
`tests/test_the_sqlite_store_keeps_the_order_it_was_given.py` — 26, green.
Written first, confirmed red. Attacked with three deliberate breaks, each
caught by its intended test: `read_all` sorted by id (the shuffled 500-record
order test), upsert as delete-then-insert (8 tests), `open_db` without the
barrier (both barrier tests).

FILES CHANGED
    src/sqlitestore.py                                          new
    tests/test_the_sqlite_store_keeps_the_order_it_was_given.py new

`src/store.py` untouched, asserted in both directions.

FINDINGS

1. `updated_at` is unusable as a test probe. It is second-resolution, matching
   `store.now()`, so two writes inside one second are indistinguishable by it.
   Change detection compares the DOCUMENT and is unaffected, but anything
   building a "what changed" check on the stamp will silently see nothing.
   The test counts `conn.total_changes` instead — SQLite's own tally rather
   than the writer's account of itself.

2. The first version of the no-circular-import test GREPPED THE SOURCE and
   failed on this module's own docstring, which explains `store.save`'s cost
   as the reason the module exists. That is exactly the failure CLAUDE.md
   names — "searching source for words produces a test that fails when
   somebody writes a comment, which has happened repeatedly here" — and it
   was reproduced within the hour of writing it. It walks the AST now. Worth
   repeating in the next task's brief.

3. A sorted fixture cannot distinguish insertion order from key order. The
   order test shuffles deliberately, and ATTACK 1 confirmed only the shuffled
   test catches a key-sorting backend — the two small a/b/c ordering tests do
   not, because their ids are already sorted.

RISKS

- `revision()` is stricter than the content hash it replaces: a record changed
  and changed back now refuses under `expect_digest`. Asserted as intended in
  a test so nobody shims it back, but TASK-253 is where it becomes visible to
  callers, and it is a concurrency guard.
- Nothing here is proven at 20k records. TASK-255 owns that, and it must build
  its estate at the MEASURED record size — the 22.7x error in the journal's
  benchmark came from exactly that assumption going unchecked.

RECOMMENDED CLAUDE ACTION
Merge with `docs/MERGE-REQUEST-INFRA-2026-09-22.md`. TASK-252 (migration) is
next and depends only on this. TASK-253 is the one that touches `store.py` and
should land alone.
