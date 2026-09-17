# GLM adversarial review - storage

2026-09-17T22:50:29.161467+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## store.save

`glm-5.3`, 129.146s, usage {'prompt_tokens': 1655, 'completion_tokens': 7307, 'total_tokens': 8962, 'reasoning_tokens': 6302, 'cached_tokens': 0}.

## 1. Arithmetic

Per record: 17,484,788 / 550 = **31.79 KB**, i.e. **7.57×** the 4.2 KB every benchmark assumed. All benchmark-derived throughput/latency numbers are ~7.6× optimistic at any N.

| | 5,000 | 100,000 | (1,000,000) |
|---|---|---|---|
| Queue size | 159 MB | 3.18 GB | 31.8 GB |
| RAM at each `save` (≥ `on_disk` + `recs`, 3rd copy if merge materializes) | 318–477 MB | 6.4–9.5 GB | 64–95 GB |
| Full-file writes per stage (every 5 records) | 1,000 | 20,000 | 200,000 |
| Whole-file bytes written per stage | 159 GB | **63.6 TB** | 6.36 PB |
| Journalling on: bytes *written* per stage | ~159 MB | ~3.18 GB | ~31.8 GB |
| Journalling on: bytes *read* under the lock per stage (`_current_records()` is O(N) every checkpoint) | 159 GB | **63.6 TB** | 6.36 PB |
| Merge comparisons/hashes per stage | 5.0 M | 2.0 × 10⁹ | 2.0 × 10¹¹ |

Journalling narrows the write only. At 100k, each of 20,000 checkpoints holds the lock across a 3.18 GB read plus a 100k-row merge and digest — writers serialize behind multi-GB I/O 20,000 times per stage.

## 2. Single change, largest benefit/risk

**`CHECKPOINT_EVERY`: 5 → 100.** One constant. Divides lock-held O(N) reads, merges, digests, and writes by 20 (at 100k: 63.6 TB → 3.18 TB read per stage; 20,000 → 1,000 lock acquisitions). Risk: a crash costs re-work of ≤100 of *this run's own* edits instead of 5 — concurrency semantics are unchanged (absent-row keep, both guards, and field merge are frequency-independent). Not a rewrite; the code itself names the alternatives (index, narrow read) as larger changes.

Rejected: keying verification evidence by company id rather than record id — at 100k with any cross-cohort overlap, provider spend scales with records not companies (no overlap rate given, so no arithmetic) — but that is a data-model rewrite, excluded by the brief.

## 3. Concurrency defect — substantiated

**Last-write-wins on a shared field, with both guards blind to it.** Exact interleaving:

1. Pipeline P calls `load()` → Snapshot S; record X: `state: "queued"`.
2. Inbound ingest receives a positive reply for X, sets `state: "paused"`, appends the reply event, saves. Disk: X paused.
3. P processes X from its stale copy, transitions `state: "queued" → "contacted"` — its own field write.
4. P's next checkpoint: merge classifies X as *changed by both*; P changed `state`, so **P wins `state`**. X lands on disk as `contacted`. The pause is erased.

Neither guard fires: `refuse_evidence_loss` indexes verification evidence; `refuse_history_loss` compares events — the reply event survives (P never touched it), so the `state` overwrite passes both. Every later gate reads X as contactable and sends to an account that replied stop. This is the exact harm the docstring's first paragraph describes ("a positive reply that paused an account was revertible by any concurrent run"), narrowed from whole-file to one field — the class survives the fix. Rate: once per ingest landing inside any batch window; 1,000 checkpoint windows per 5,000-record stage.

## 4. NO FINDING

- **Crash mid-write:** whole-file atomicity (tmp+rename) is asserted, not shown; `_write_delta`'s framing/fsync is not shown at all. Cannot substantiate a torn journal record or lost delta from the code given.
- **Partial/torn read by a concurrent `load()`:** `load()`'s locking protocol is not shown; the lock here provably covers read-through-write. No constructible interleaving from what's visible.
- **`allow_history_loss` escape:** test-only, build-enforced. No production path shown.

## store.load

`glm-5.3`, 104.445s, usage {'prompt_tokens': 374, 'completion_tokens': 5336, 'total_tokens': 5710, 'reasoning_tokens': 4493, 'cached_tokens': 320}.

## 1. Arithmetic (per-record = 17,484,788 / 550 = 31,790.5 B)

| | 5,000 records | 100,000 records | 1,000,000 (for scale) |
|---|---|---|---|
| Bytes held per `load()` (raw, one Snapshot) | 158,952,618 B ≈ **159 MB** | 3,179,052,364 B ≈ **3.18 GB** | ≈ 31.8 GB |
| Checkpoints per full pass (every 5) | 1,000 | 20,000 | 200,000 |
| Bytes per checkpoint (full-file write) | ~159 MB | ~3.18 GB | ~31.8 GB |
| **Bytes written per full pass** | 1,000 × 159 MB ≈ **159 GB** | 20,000 × 3.18 GB ≈ **63.6 TB** | ≈ **6.36 PB** |

- Write amplification: **~1,000×** — each 31.8 KB record processed causes ~31.8 MB of writes. At 100k, that's **636 MB written per record processed**.
- Every `load()` fully re-parses the base file: at 100k that's 3.18 GB of JSON parsed per call, before journal replay.
- Benchmark skew: 31.8/4.2 = **7.57×** — every byte-dependent benchmark figure is ~7.6× optimistic.
- Cross-cohort evidence keyed by record id ⇒ cost is linear in *total records*, not unique companies. A company in k cohorts pays k×; zero reuse term. (No duplication rate given, so no dollar number.)

## 2. Highest benefit/risk change

Bump the checkpoint interval from 5 to 500 — a one-constant change. Write volume drops **100×** (63.6 TB → 636 GB per 100k pass). Risk is bounded to longer journal replay on load. Durability is unchanged **if** deltas are journalled per-record between checkpoints, which the docstring implies. Not a rewrite.

## 3. Correctness/concurrency — one constructible interleaving

**Lost-update read across the non-atomic two-artifact load.** `load()` must read base and journal as two steps; a checkpoint compacts between them:

1. Reader finishes reading `work/queue.jsonl` — state as of t0, missing record X.
2. Writer commits X: delta appended to journal, then checkpoints — X folded into base, journal cleared.
3. Reader reads journal: empty. Replays nothing.
4. Reader returns a Snapshot **without X**, though X was durably committed before the reader returned. Downstream "not yet contacted → send" logic double-sends.

The window is the checkpoint's base-write duration — at 100k that's 3.18 GB, i.e. **10–30 s** of exposure on ordinary storage, widening linearly with scale. Trigger: any second caller of `load()` (second stage, monitor, resume script) while a pipeline stage runs.

## 4. NO FINDING

- **Crash mid-checkpoint (torn/truncated base):** the write path is not shown. If checkpoint truncates in place the torn read follows, but I won't assert code I haven't seen. NO FINDING on exact behavior and ordering.
- **Two writers:** no locking visible in `load()`, but absence in the one shown function is not proof of absence in the writer. NO FINDING.
- **Defects inside `_current_records()` / `Snapshot`:** not shown. NO FINDING.

The one-line fix that would also close #3's write side (temp file + atomic rename at checkpoint) is cheap, but I can only recommend it conditionally — the checkpoint code isn't in evidence.

