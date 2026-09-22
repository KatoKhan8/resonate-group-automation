PRIORITY: P1
DEPENDS: TASK-251

# TASK-252 — the one-shot migration, and the verifier that decides it worked

Design: `docs/STORE-SQLITE-DESIGN-2026-09-22.md` section 8.

`scripts/migrate_store_sqlite.py`. Reads the queue, writes the SQLite store
TASK-251 built, and proves the two agree before reporting success.

## The steps, in this order

1. Take `store.lock()`. Nothing else may write for the duration.
2. Read through **`store._current_records()`**, not `read_jsonl(queue_path())`.
   **This is the step that is easy to get wrong and expensive to get wrong.**
   With journalling on the base file is deliberately not rewritten, so reading
   it alone silently drops every checkpoint since the last compaction — a
   migration that looks clean and has lost a day of work.
3. Insert in file order, one transaction, `seq` ascending.
4. Record `meta.migrated_from` = the source digest, `meta.revision` = 1.
5. **Verify before reporting success.** Read every record back and compare the
   serialised document AND the position against the source, record for record.
   Any mismatch rolls back and refuses. A migration that reports success
   without this is the vacuous pass the register has already caught twice
   (F-003, and `leadstop.sweep` reporting clean because it counted nobody).
6. Never delete or modify `queue.jsonl`.

## Idempotence, stated precisely

    migrated_from == current source digest   completed; no-op, say so, exit 0
    migrated_from != current source digest   REFUSE. Do not guess which is
                                             newer and do not re-migrate over
                                             it; that is how the newer half
                                             gets silently dropped.
    no database                              migrate

## Falsifiable requirements — tests first

1. A migration of a 500-record fixture estate round-trips every record, in
   order, byte-identically on `json.dumps(..., sort_keys=True)`.
2. **With `QUEUE_JOURNAL` on and un-compacted deltas present**, the migrated
   set equals `store._current_records()` and NOT `read_jsonl(queue_path())`.
   Build the fixture so the two genuinely differ, then assert the difference
   is what was migrated. A test where they happen to be equal proves nothing.
3. A deliberately corrupted read-back (patch one document after insert) makes
   the verifier REFUSE and roll back, leaving no database behind.
4. Re-running on an unchanged source is a no-op that exits 0 and says so.
5. Re-running after the source has changed REFUSES and exits non-zero.
6. It never writes `work/` under test — `refuse_production_write`.
7. The lock is held across read and write: a second process attempting a
   migration concurrently gets `QueueLocked` and writes nothing.

## Not in this task

Reading from SQLite in anger, `QUEUE_BACKEND`, shadow mode, any change to
`store.py`. This produces a database and proves it faithful. Nothing reads it.
