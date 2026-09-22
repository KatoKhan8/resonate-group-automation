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
