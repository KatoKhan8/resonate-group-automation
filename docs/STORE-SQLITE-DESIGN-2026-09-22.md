# The store moves to SQLite — design, 2026-09-22

Written on branch `infra`, which does not push to master. This is a DESIGN and
a task breakdown. No behaviour has changed and nothing here is wired.

Read `src/queuejournal.py`'s module docstring first. It is the previous attempt
at this problem, it is correct about everything it measures, and **its headline
table under-states production by a factor of 22.** That correction is the
reason this design exists rather than a wiring change for the journal.

---

## 1. The measurement, taken today

`work/queue.jsonl`, read 2026-09-22 (read-only; the production session owns
that directory):

    records                    1,027
    total                     19.41 MB
    mean bytes per record     19,819
    largest single record    162,117

The brief carried ~31 KB per record. **The mean is 19.8 KB, not 31 KB.** The
31 KB figure is inside the observed range — the largest record is 162 KB — but
as a mean it over-states by ~56%. Every projection below uses the measured
mean and is therefore the conservative version of this argument.

### The journal's own benchmark used records 22x smaller than production's

`queuejournal.py` records this table from `scripts/store_write_profile.py`:

    RECORDS  CHECKPOINTS  WRITE_TIME  MB_WRITTEN  AMPLIFICATION
       5000         1000    211.72 s      4369.1        4918.9x

4,369.1 MB / 1,000 checkpoints / 5,000 records = **874 bytes per record**,
which matches the docstring's own "changing one ~900-byte record". Production
records are 19,819 bytes. So the profile was run against a synthetic estate
whose records are **22.7x smaller than the real ones**, and every wall-clock
and byte figure in that table is low by that factor.

This is the register's own recurring shape — *a value that was true when it
was written, cached somewhere that had no way to notice it had gone stale* —
arriving in a benchmark rather than in a credential name or a campaign list.
It belongs in PROBLEM-REGISTER.md as such.

### What that makes the 20k target

`run.CHECKPOINT_EVERY = 5` (`src/run.py:114`), so one pass over N records
performs N/5 whole-file writes, each costing O(N). At the measured mean:

    N        full rewrite   checkpoints   written per pass
    1,027        19.4 MB           205            3.9 GB
    5,000        94.5 MB         1,000           92.3 GB
    20,000      378.0 MB         4,000         1,476.6 GB

**1.48 TB of writes for one pass over 20,000 records**, before a single
provider call is waited on — and the read is O(N) per checkpoint too, so the
real I/O is roughly double. This is not a constant that can be tuned down.
`CHECKPOINT_EVERY` is a durability decision with a reproduced incident behind
it (`store.save`'s docstring, 2026-09-12) and `queuejournal.py` is explicit
that it "must not be relitigated as a performance one". It stays at five.

---

## 2. Why the journal is not enough, and what it is still good for

The journal narrows the WRITE and leaves the READ at O(N). Its own docstring
says so: *"this halves the work rather than fixing it … the O(N) READ per
checkpoint stays. That read needs an index to fix and an index is a bigger
change than this one."*

This design is that bigger change. At 20k the read half alone is ~1.48 TB per
pass, so halving is not a fix — it is the same wall a factor of two later.

`TASK-226` (in `docs/qwen-tasks/TODO/`, with work already on branch
`qwen-worker-8-r28` as `590c35ef`) adds an offset index for O(M) journal
replay. **It is not wasted and it is not superseded yet**, because the journal
remains the default until the SQLite backend is proven in shadow. It becomes
redundant only at the point the backend is promoted, and that point is months
of production evidence away, not days. Do not close TASK-226 on the strength
of this document.

---

## 3. What "behind the existing store.py interface" actually requires

Surveyed across `src/`, `scripts/` and `tests/`. Call counts:

    store.load      858      store.save       599      store.get        279
    store.transaction 131    store.queue_path  97      store.read_jsonl  32
    store.digest      8      store.Snapshot     7

`queue_path()` is the one that looked fatal and is not. Of its callers outside
`store.py`:

    36   os.path.dirname(store.queue_path())    — they want the DIRECTORY
     2   read_jsonl(store.queue_path())         — scripts/profile_scale.py
     1   open(queue_path)                       — scripts/task191_funnel.py
     1   open(queue_path)                       — src/queuejournal.py (store's own)
   rest  a display string, a size for profiling, a prefix assertion

**No module under `src/` parses `work/queue.jsonl` itself.** Production reads
the queue only through `store.load()`. The two direct readers are a profiling
script and a funnel analysis script, both offline, both ours to update.

That is what makes this feasible at all, and it is the single fact the whole
design rests on. It was verified by grep rather than assumed, and a task below
adds a test that keeps it true.

### The read semantics that must not move

1. **`load()` returns a `Snapshot`, and order follows the disk.**
   `Snapshot.merge_onto` writes rows "in the order every other reader sees",
   and rows with no baseline go on the end. A backend that returns rows in an
   arbitrary or key-sorted order changes what every caller iterates over. The
   schema below carries an explicit sequence column for exactly this.
2. **A missing queue is an empty list, not an error** (`read_jsonl`).
3. **Records are never deleted.** `drop()` is a state change.
4. **The guards see the FULL merged record set.** `refuse_evidence_loss` and
   `refuse_history_loss` take lists of record dicts and are untouched by this
   change. They must stay untouched: they are the safety layer, and a storage
   change that edits a safety guard is two changes wearing one coat.
5. **`under_test()` / `refuse_production_write` must cover the database file
   and every sidecar it brings** (`-wal`, `-shm`). The journal path had to
   learn this the hard way — `_write_delta` calls the barrier explicitly
   because the sidecar "did not exist when it was written".

---

## 4. Schema

One row per record, the record itself as JSON. **Not normalised.** Contacts,
events, cadence and evidence stay inside the document because every consumer,
every guard and `store.validate` operate on the record dict; splitting them
into tables would be a rewrite of the whole repository disguised as a storage
change, and CLAUDE.md's "smallest robust solution" and "no abstraction with
one caller" both point the other way.

```sql
CREATE TABLE records (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,   -- disk order, never reused
    id         TEXT    NOT NULL UNIQUE,
    doc        TEXT    NOT NULL,                    -- the record, JSON
    updated_at TEXT    NOT NULL,

    state  TEXT GENERATED ALWAYS AS (json_extract(doc,'$.state'))  VIRTUAL,
    lane   TEXT GENERATED ALWAYS AS (json_extract(doc,'$.lane'))   VIRTUAL,
    client TEXT GENERATED ALWAYS AS (json_extract(doc,'$.client')) VIRTUAL
);
CREATE INDEX records_state  ON records(state);
CREATE INDEX records_lane   ON records(lane);
CREATE INDEX records_client ON records(client);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- 'revision'      monotonic, bumped inside every write transaction
-- 'schema_version'
-- 'migrated_from' the queue.jsonl digest the migration consumed
```

**The three filter columns are GENERATED, not stored.** `list_records` filters
on state, lane and client and would otherwise force a full scan, but a plain
column holding a copy of `doc`'s state is a second representation of the same
truth — the exact thing CLAUDE.md warns produces drift. A generated column is
derived by SQLite on read and cannot disagree with the document. Verified
available here: SQLite 3.50.4 under Python 3.14.3, generated columns, `json1`
and indexes over them all confirmed working.

`seq` is `AUTOINCREMENT` so a deleted-and-reinserted id cannot reclaim an
earlier position. Records are never deleted, so this is belt-and-braces, and
it costs one `sqlite_sequence` row.

**Journal mode WAL**, so a reader does not block the writer. `synchronous =
FULL` — this is the only file holding real client state, and the whole point
of `_write`'s atomic rename is that a crash leaves the previous queue
readable. WAL + FULL keeps that guarantee.

---

## 5. `digest()` changes meaning, in the strict direction — say so out loud

Today `digest()` is sha256 of the queue file's bytes (plus the journal's, when
journalling is on). It backs `expect_digest`, the optimistic-concurrency
refusal in `save()`.

Hashing a SQLite file's bytes is wrong: WAL, page reuse and vacuum all change
bytes without changing state, and a checkpoint can change state without
changing the main file at all. So on the SQLite backend `digest()` returns the
`meta.revision` counter, bumped inside the same transaction as every write.

**This is not a like-for-like swap and the difference matters:**

    content hash    two identical states hash the same, whoever wrote them
    revision        two identical states differ if anything committed between

So a write that changes a record and changes it back — or two processes that
converge on the same bytes — now *refuses* where it previously passed.
`expect_digest` exists to refuse a read-modify-write that raced, and refusing
a race that happened to converge is the SAFE direction: the caller reloads and
re-applies, which is what the refusal already tells it to do. It will fire
slightly more often. That is the trade, it is deliberate, and a test asserts
the stricter behaviour rather than working around it.

`digest()` also stops being O(N). It is currently a full file read on every
`save()` with `expect_digest`, which at 20k records is 378 MB per call.

---

## 6. Locking: the advisory lock stays exactly as it is

SQLite has its own locking, and it is tempting to drop `store.lock()`. Do not.

- 33 call sites take `store.lock()` directly, and `file_transaction` takes it
  for other files entirely. It is not the queue's lock, it is the work
  directory's lock.
- `transaction()`'s contract is read-modify-write under one lock held across
  provider I/O. SQLite's transaction would have to be held open across that
  same window, which is a long-running write transaction on a WAL database —
  worse, not better.
- The lock is proven on Windows, where this runs, and `queuejournal.py`
  records a measured Windows-specific failure (six processes, 207 lines
  missing) from assuming a primitive was atomic when it was not. That lesson
  applies to any assumption about SQLite's cross-process behaviour here too.

So: the advisory lock keeps its job, SQLite's transaction keeps its own, and
they nest. The lock is taken first, always, in the same order everywhere.

---

## 7. Shadow-write, and what it does when the two disagree

`QUEUE_BACKEND`, read per call the way `queue_path()` is, never at import:

    jsonl    default. Exactly today's behaviour. SQLite untouched.
    shadow   JSONL is canonical. Every write goes to both. Every read comes
             from JSONL, and the same read is taken from SQLite and diffed.
    sqlite   SQLite is canonical. JSONL untouched.

The diff is record-by-record on the serialised document, plus order, plus
count. A divergence writes a structured row to `work/store-shadow-diff.jsonl`
carrying the record id, the field, and both values — and **does not raise**.

That last decision needs its reasoning on the record, because this repository
fails closed by default and this is deliberately not that:

> Shadow mode exists to find out whether the backend is trustworthy, on the
> live queue, before anything depends on it. A divergence that raises turns a
> bug in the UNTRUSTED half into an outage of the TRUSTED half — it would take
> production down to protect a store nothing is reading yet. The canonical
> store is JSONL throughout shadow; the SQLite half is an observer with no
> vote.

The fail-closed instinct is still served, twice over:

- `SHADOW_STRICT=1` makes any divergence raise. **Tests run with it on**, so a
  divergence is a hard failure everywhere it can be one without risking the
  live queue.
- Promotion to `sqlite` requires a clean diff ledger over a stated window, and
  the promotion task asserts the ledger is empty rather than trusting that
  nobody looked. An empty ledger because nothing ran is the vacuous-pass trap
  the register already caught twice (F-003, and `leadstop.sweep` in
  ISSUE-002), so the ledger records **writes observed** as well as
  divergences, and a promotion check that sees zero of both refuses.

---

## 8. The one-shot migration

`scripts/migrate_store_sqlite.py`:

1. Take `store.lock()`. Nothing else may write during this.
2. Read the current state through `store._current_records()` — the base file
   **with any journal deltas replayed**. Reading `queue.jsonl` alone would
   silently drop every checkpoint since the last compaction.
3. Insert in file order, `seq` ascending, one transaction.
4. Record `migrated_from` = the source digest, and `revision` = 1.
5. **Verify before reporting success**: read every record back out and compare
   the serialised document and the order against the source, record for
   record. Any mismatch rolls back and refuses.
6. Idempotent: a database that already carries `migrated_from` equal to the
   current source digest is a completed migration, and re-running is a no-op
   that says so. A database whose `migrated_from` names a DIFFERENT digest
   refuses rather than guessing which is newer.

It never deletes `queue.jsonl`. The JSONL file stays as the canonical store
through shadow and stays on disk as a readable artifact afterwards.

---

## 9. What this design does NOT settle

- **It does not make `load()` cheap — NOW MEASURED, not predicted.**
  TASK-255 ran the three arms at production record size
  (`docs/LOAD-TEST-20K-2026-09-22.md`):

        ARM              RECORDS  CHECKPOINTS  TIME_S  MB_WRITTEN  AMPLIFICATION
        jsonl              1,000          200    65.4     3,981.8       1108.1x
        jsonl+journal      1,000          200   123.9         3.6          1.0x
        sqlite             1,000          200    43.3         0.2          0.1x

  On write volume it is a rout, and O(changed) is demonstrated across three
  sizes rather than asserted at one: sqlite writes a constant ~180-188 KB from
  500 to 1,000 records while the payload doubles.

  **But all three arms are O(N²) in wall clock.** 2x the records costs 4x the
  time on every arm, because the read per checkpoint is O(N) and there are N/5
  checkpoints. Narrowing the write does not change the shape. Projected at
  20,000: jsonl ~7 hours, journal ~52 minutes, sqlite ~23 minutes.

  So this design is a very large win and NOT the finish line — 7 hours to 23
  minutes, and 1.59 TB of writes to 188 KB. The read half stays open, it needs
  the guards to work against a subset, and that is a safety change deliberately
  not in this design. **Do not let "SQLite fixes the storage problem" be the
  sentence that survives from this document.**
- **It does not touch `work/campaigns.jsonl`.** 58 KB, 1 file, no pressure.
  Migrating it would be scope nobody asked for.
- **It is not proven at 20k.** Every figure above is measured at 1,027 records
  and projected. The task list ends with a load test that builds a synthetic
  20k estate **at production record size** — the 22x error in section 1 came
  from exactly that assumption going unchecked, and repeating it here would be
  embarrassing.
- **Zero third-party deps stays true.** `sqlite3` is stdlib. Confirmed
  present: SQLite 3.50.4. One environment note — `sqlite3.version` was
  REMOVED in Python 3.14; use `sqlite3.sqlite_version`. Code that reads the
  old attribute raises `AttributeError` on this machine.

---

## 10. The bounded tasks

Written to `docs/qwen-tasks/TODO/`, tests first, each independently
reviewable. They land in this order and each is useless to promote alone,
which is the point — the storage engine and the change to the only file
holding real client state are separate reviewable things, exactly as
`queuejournal.py` was landed unwired for the same reason.

    TASK-251  the SQLite backend module, with NO caller.
              Schema, open/close, read-all, write-changed, revision.
              Round-trips every record shape in the fixtures. Not wired.

    TASK-252  the one-shot migration and its verifier.
              Reads through _current_records, replays the journal, verifies
              record-for-record and in order, refuses on mismatch,
              idempotent by source digest.

    TASK-253  QUEUE_BACKEND and the shadow path.
              Both stores written, reads diffed, ledger written, SHADOW_STRICT
              raises, tests run strict. JSONL stays canonical.

    TASK-254  the caller survey becomes a test.
              Nothing under src/ may read the queue file directly; the two
              scripts that do are updated to go through the store.

    TASK-255  the 20k load test, at production record size.
              Builds a synthetic estate with the MEASURED mean and tail, not
              a 900-byte one, and reports the same columns as
              store_write_profile so the two are comparable.

Promotion to `QUEUE_BACKEND=sqlite` is NOT in this list. See §11.

---

## 11. THE PROMOTION RULE — recorded, operator, 2026-09-22

**Set by Zvonimir. Four conditions, all of them, and none is inferable from a
passing test suite. Until every one holds, JSONL stays live.**

    1. TASK-259 green    the reproduced-incident tests run on BOTH backends,
                         so both loss guards are exercised on both. Until
                         this, the three-way merge and both guards are
                         proven on JSONL only.

    2. TASK-260 green    the checkpoint read is O(changed).
                         **NOT MET as of 2026-09-22, and 260 is merged.**
                         Measured after it landed: 1,000 records 60.53s,
                         5,000 records 1,522.58s - a ratio of 25.2x for 5x
                         the records, where 5 squared is 25. A pass is still
                         quadratic to two significant figures.
                         The cause is NOT the storage backend: `Snapshot`
                         re-serialises every record TWICE per checkpoint to
                         re-derive which the caller edited, on every arm.
                         TASK-261 owns it.
                         `docs/BENCHMARK-PASS-WALL-CLOCK-2026-09-22.md`.

    3. 48 HOURS OF SHADOW WITH A ZERO DIFF
                         `QUEUE_BACKEND=shadow` on the live queue, for two
                         full days, with `work/store-shadow-diff.jsonl`
                         carrying no divergence.

    4. THE PRODUCTION SESSION FLIPS IT, IN A WINDOW WITH NO SENDS.
                         Not this session, not a worker, not a script. And
                         not while a campaign is sending.

### The trap condition 3 is built to avoid, and how to not fall into it

**An empty diff ledger is not the same as a clean one.** A ledger with zero
rows because nothing ran looks identical to a ledger with zero rows because
everything agreed, and this repository has shipped that exact vacuous pass
twice — F-003's `active_campaign_ids` defaulting to `()` so `coverage()`
passed against nothing, and `leadstop.sweep` reporting clean because it never
incremented its counter.

TASK-253's ledger therefore records **writes observed** as well as
divergences, and the promotion check refuses on zero of both. So condition 3
is not "the file is empty" — it is:

    writes_observed > 0  AND  divergences == 0  over 48 hours

Read the count before believing the silence.

### What promotion does NOT require, so nobody adds it later

Not a full-suite green: the baseline carries 111 known failures
(`docs/state/SUITE-BASELINE-2026-09-22.md`) and none of them is about storage.
Not the 20k load test being performed on the jsonl arm — it writes ~1.59 TB
and is projected by design.

### And it is reversible

`QUEUE_BACKEND=jsonl` puts the old path back, because the migration never
deletes or modifies `queue.jsonl` (§8) and the JSONL file keeps being written
throughout shadow. The rollback is one environment variable, provided nothing
has been written in `sqlite` mode that JSONL did not also get — which is the
reason shadow comes first and the reason it is 48 hours rather than an
afternoon.
