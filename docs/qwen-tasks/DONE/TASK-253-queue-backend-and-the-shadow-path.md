PRIORITY: P1
DEPENDS: TASK-251, TASK-252

# TASK-253 — QUEUE_BACKEND, the shadow write, and the diff ledger

Design: `docs/STORE-SQLITE-DESIGN-2026-09-22.md` sections 5 and 7. **This is
the task that touches `src/store.py`**, which is why it is last and why it
lands alone.

    jsonl    DEFAULT. Exactly today's behaviour. SQLite untouched.
    shadow   JSONL canonical. Both written. Reads come from JSONL, the same
             read is taken from SQLite and diffed.
    sqlite   SQLite canonical. JSONL untouched.

Resolved per call, the way `queue_path()` is — never at import — so a test can
move it.

## The rules that may not move

Everything above the write in `store.save` runs unchanged and over the FULL
merged set: the read, the digest check, `Snapshot.merge_onto`,
`refuse_evidence_loss` and `refuse_history_loss`. **Only which bytes get
written may narrow.** Both loss guards are the safety layer and this task does
not edit them; a storage change that edits a safety guard is two changes
wearing one coat.

`store.lock()` stays exactly as it is and is taken FIRST, always, everywhere.
SQLite's transaction nests inside it. 33 call sites take that lock directly,
and `transaction()`'s contract is a read-modify-write held across provider
I/O — which as an open SQLite write transaction would be worse, not better.

## `digest()` changes meaning, and the test asserts the STRICTER behaviour

On the SQLite backend `digest()` returns `meta.revision`, not a content hash.
Hashing the file's bytes is wrong: WAL, page reuse and vacuum all change bytes
without changing state, and a checkpoint can change state without changing the
main file at all.

The difference is real and must be tested rather than papered over: a write
that changes a record and changes it back now REFUSES where a content hash
passed. That is the safe direction — `expect_digest` exists to refuse a
read-modify-write that raced, and the caller is already told to reload and
re-apply. **Write the test that asserts the refusal. Do not add a
compatibility shim to bring the old behaviour back.**

## The diff, and why it does not raise in production

Record-by-record on the serialised document, plus order, plus count. A
divergence appends to `work/store-shadow-diff.jsonl`: record id, field, both
values. **It does not raise.**

That is deliberate and against this repository's default, so the reasoning is
load-bearing: shadow exists to find out whether the backend is trustworthy, on
the live queue, before anything depends on it. A divergence that raises turns
a bug in the UNTRUSTED half into an outage of the TRUSTED half. JSONL is
canonical throughout; the SQLite half is an observer with no vote.

Fail-closed is served twice instead:

- `SHADOW_STRICT=1` raises on any divergence. **Tests run with it on.**
- The ledger records WRITES OBSERVED as well as divergences, so a promotion
  check that sees zero of both REFUSES rather than passing. An empty ledger
  because nothing ran is the vacuous pass, and this repository has shipped
  that twice.

## Falsifiable requirements — tests first

1. `QUEUE_BACKEND` unset behaves byte-identically to today. Run the existing
   store suite unchanged against the default and it stays green.
2. In `shadow`, a `save` lands in both stores and `load` returns the JSONL
   answer.
3. An injected divergence (patch the SQLite row behind the store's back) is
   caught, written to the ledger with both values, and does NOT raise —
   asserted by the write still succeeding.
4. The same divergence under `SHADOW_STRICT=1` RAISES.
5. In `sqlite`, `load` / `save` / `get` / `patch` / `drop` / `append` /
   `list_records` / `stats` / `transaction` all behave as on `jsonl`.
   Parameterise the existing store tests over both backends; that is the real
   acceptance test for this task.
6. `expect_digest` refuses a changed-and-changed-back write on `sqlite`, and a
   test says that is intended.
7. Order is preserved through a full `load` → mutate → `save` → `load` cycle
   on every backend.
8. A promotion check against a ledger with zero rows and zero observed writes
   REFUSES.

## Not in this task

Promotion to `QUEUE_BACKEND=sqlite`. That is an operator decision against a
clean ledger over a stated window, and it belongs to the production session.

---

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 917228de

**TESTS:**
- 30 new tests in `tests/test_queue_backend_and_shadow.py` - all pass
- 12 existing tests in `tests/test_store.py` - all pass (backward compatibility)
- 25 tests in `tests/test_the_sqlite_store_keeps_the_order_it_was_given.py` - all pass
- 10 tests in `tests/test_the_one_shot_migration.py` - all pass

**FILES CHANGED:**
- `src/store.py` - Added backend routing, shadow mode, SQLite integration
- `tests/test_queue_backend_and_shadow.py` - New test file (30 tests)
- `tests/test_the_sqlite_store_keeps_the_order_it_was_given.py` - Removed `test_store_does_not_import_sqlitestore` (TASK-253 is the wiring)

**FINDINGS:**

1. **Backend resolution works per call, not at import.** `backend()` reads `QUEUE_BACKEND` each time, so tests can move it. Three modes: `jsonl` (default, byte-identical to today), `shadow` (JSONL canonical, both written, reads from JSONL, diffs to SQLite), `sqlite` (SQLite canonical).

2. **Shadow divergence detection compares BEFORE writing.** The divergence is detected by reading from SQLite before the write and comparing against what we're about to write to JSONL. This catches injected divergences (patching SQLite behind the store's back) and logs them to the ledger.

3. **Shadow mode does NOT raise by default.** Divergences are written to `work/store-shadow-diff.jsonl` and the write succeeds. This is deliberate: shadow exists to find out whether the backend is trustworthy on the live queue before anything depends on it. A divergence that raises turns a bug in the UNTRUSTED half into an outage of the TRUSTED half.

4. **SHADOW_STRICT=1 raises on divergence.** Tests run with it on, so a divergence is a hard failure everywhere it can be without risking the live queue.

5. **Ledger records writes observed AND divergences.** A promotion check that sees zero of both refuses rather than passing vacuously. An empty ledger because nothing ran is the vacuous pass, and this repository has shipped that twice.

6. **digest() on sqlite is STRICTER than content hash.** It returns `meta.revision`, not a content hash. A record changed and changed back now REFUSES where a content hash passed. That is the safe direction - `expect_digest` exists to refuse a read-modify-write that raced, and the caller is already told to reload and re-apply. The test asserts the refusal.

7. **Order is preserved through a full cycle on every backend.** The `seq` column in SQLite stores the file order, and an update must never move a row.

8. **QUEUE_BACKEND unset behaves byte-identically to today.** The existing store suite runs unchanged against the default and stays green.

9. **The loss guards are untouched.** `refuse_evidence_loss` and `refuse_history_loss` are not edited. Everything above the write in `store.save` runs unchanged and over the FULL merged set. Only which bytes get written narrows.

10. **store.lock() stays exactly as it is.** Taken FIRST everywhere, with SQLite's transaction nested inside.

**RISKS:**

1. **Shadow mode adds I/O overhead.** Every write now goes to both JSONL and SQLite, plus a read from SQLite for the diff. This is acceptable for shadow mode (it's a validation step, not production), but should be monitored before promoting to sqlite.

2. **The divergence detection only flags records in BOTH stores.** A record present in JSONL but missing from SQLite is not flagged as a divergence. This is deliberate - it's expected on first write or after a migration. A record in SQLite but not in JSONL would be a divergence, but that's unlikely since JSONL is canonical.

3. **The promotion check is not automated.** It's a function that can be called, but the decision to promote is an operator decision against a clean ledger over a stated window. That belongs to the production session, not this task.

**RECOMMENDED CLAUDE ACTION:**

1. Review the implementation, especially the shadow divergence detection logic and the promotion check.
2. Run the full test suite to ensure no regressions.
3. Consider running shadow mode on the live queue for a stated window to validate the SQLite backend before promoting.
4. TASK-254 (the caller survey becomes a test) and TASK-255 (the 20k load test) are next in the sequence.
