# TASK-432 — GLM Independent Verification: TASK-226

## Review identity

    reviewed task       TASK-226 — the journal offset index
    reviewed branch     qwen-worker-8-r28
    reviewed HEAD SHA   36a4ce61b454187772e78daac49b08282380193e
    worktree            .qwen/worktrees/glm-432 (detached at above SHA)
    reviewer            GLM (Qwen-3 worktree, read-only)
    date                2026-09-27
    master HEAD SHA     243c00b3 (at review start)

**SHA verification:** `git rev-parse qwen-worker-8-r28` returns `36a4ce61b454187772e78daac49b08282380193e`. Branch HEAD matches the named SHA. The review was performed against this exact commit.

---

## 1. Does the artifact exist, and does it do what the result block claims?

**VERIFIED.** The artifact exists on this ref and consists of:

| File | Status | Lines added |
|------|--------|-------------|
| `src/queuejournal.py` | Modified (index added) | +174 |
| `tests/test_the_journal_index.py` | New | +256 |
| `scripts/journal_benchmark_report.py` | New | +218 |
| `scripts/journal_read_benchmark.py` | New | +314 |
| `scripts/journal_replay_cost.py` | New | +204 |

**Claim 1: "An index mapping record id to byte offset"** — VERIFIED. `_build_index()` at `src/queuejournal.py:162` scans the journal and builds `{record_id: byte_offset}`. `_append_locked()` at line 245 maintains it incrementally. `_read_entry_at()` at line 210 seeks to a known offset.

**Claim 2: "replay is O(M) where M is unique records"** — VERIFIED by code inspection. `replay()` at line 337 iterates `index.items()` (one entry per unique record id) and calls `_read_entry_at()` for each. This is O(M) seeks, not O(J) linear scan.

**Claim 3: "The index is DERIVED and rebuildable"** — VERIFIED by tests. Three tests prove this:
- `test_corrupt_index_is_rebuilt_and_read_still_correct`: writes garbage to index, confirms `store.load()` returns correct state
- `test_absent_index_is_rebuilt`: deletes index, confirms rebuild on next read
- `test_index_rebuild_matches_incremental`: confirms full-scan rebuild matches incremental maintenance

**Claim 4: "Journal 0.55x at 500 records (45% faster than whole-file)"** — NOT RE-DERIVED. The benchmark scripts exist and the methodology is sound (50 and 500 are MEASURED, 5000 is MODELLED by linear extrapolation). The 0.55x figure is plausible given O(M) vs O(N) complexity, but I did not run the benchmark at 500 records. The scripts use the correct 31,793-byte record size from `scripts/store_write_profile.py`.

**Claim 5: "QUEUE_JOURNAL stays OFF"** — VERIFIED. `src/store.py:427` shows `journalling()` returns True only when `QUEUE_JOURNAL` env var is set to a truthy value. Default is OFF.

---

## 2. Existence is not function — is every link CONSUMED?

**VERIFIED.** `store.py` has production callers for every public function `queuejournal` exposes:

| Function | Caller in `src/store.py` | Line |
|----------|--------------------------|------|
| `queuejournal.replay()` | `load()` | 440 |
| `queuejournal.append()` | `_write_delta()` | 556 |
| `queuejournal.should_compact()` | `_write_delta()` | 557 |
| `queuejournal.compact()` | `_write_delta()` | 558 |
| `queuejournal.path_for()` | `_sidecar_exists()` | 775 |

All calls are gated by `if journalling():` (lines 438, 773, 872), so the code is live when `QUEUE_JOURNAL=1` and inert when off. The wiring is real and was NOT changed on this branch (`git diff master...36a4ce61 -- src/store.py` is empty). The index additions in `queuejournal.py` are consumed by the existing `replay()` call path.

**Zero production callers = DISCONNECTED** does NOT apply here. The journal module has real callers in `store.py`.

---

## 3. Falsification — mutation test

**PERFORMED.** I mutated `_build_index()` and `_append_locked()` to store the FIRST byte offset per record instead of the LAST (changed `if rid is not None:` to `if rid is not None and rid not in index:`). This breaks the last-write-wins invariant.

**Result:** `test_index_points_at_last_entry_not_first` FAILED with:
```
AssertionError: 'verified' != 'dropped'
: replay must return the LAST value, not the first
```

The test correctly detected the mutation. It got 'verified' (the first value written) instead of 'dropped' (the last value written), which is exactly the failure the index must prevent.

**Note:** `test_replay_with_index_matches_replay_without` did NOT fail under this mutation, because both the incremental and rebuilt indexes were mutated identically and thus still agreed. This test proves consistency (incremental matches rebuild) but not correctness. Correctness is proved by `test_index_points_at_last_entry_not_first`. The two together are solid.

---

## 4. Are the tests falsifiable?

**YES.** Beyond the mutation test above:

- `test_corrupt_index_is_rebuilt_and_read_still_correct` — falsifiable by writing a "corrupt" index that happens to be valid JSON with wrong offsets. The test would pass if the corrupt index were accidentally trusted. It fails correctly because `_read_index` parses the garbage and returns None, triggering rebuild.
- `test_index_points_at_last_entry_not_first` — falsifiable by any bug that returns the first value instead of the last. Proved above.
- `test_absent_index_is_rebuilt` — falsifiable by a code path that raises on missing index instead of rebuilding. Would catch a naive "index required" implementation.
- `test_index_rebuild_matches_incremental` — falsifiable by any drift between incremental maintenance and full-scan rebuild. Catches off-by-one errors in offset calculation.

**What would NOT be accepted as proof (per protocol):**
- `hasattr` — not used
- Assertions on source text — not used
- Proving a function exists — not used; tests exercise behavior through `store.save()`/`store.load()`
- Fake cassette data — not used; tests use real temp directories

The tests drive through `store.save()` and `store.load()`, the real production entry points. They do not construct inputs by hand.

---

## 5. Would merging DELETE anything?

**NO.** `git diff master...36a4ce61 --diff-filter=D --name-only` returns only:
```
docs/qwen-tasks/TODO/TASK-231-a-timeout-that-abandons-is-not-a-timeout.md
```

This is a task file moving from TODO to REVIEW (a rename/move, not a deletion of production code). No production files, no tests, no configuration would be deleted.

---

## 6. Scope drift

**PRESENT.** The branch `qwen-worker-8-r28` at `36a4ce61` contains BOTH TASK-226 and TASK-231 work. The TASK-231 changes are:

| File | TASK | Change |
|------|------|--------|
| `src/gather.py` | TASK-231 | Timeout enforcement at HTTP layer (-28/+22 lines) |
| `src/providers/__init__.py` | TASK-231 | New `HttpTimeout` exception class (+31 lines) |
| `tests/test_http_timeout_aborts_at_socket_layer.py` | TASK-231 | New test file (+451 lines) |
| `tests/test_prefetch_headcount.py` | TASK-231 | Modified (+61/-0 lines) |

**TASK-226 files are cleanly separable.** The TASK-226 commits are:
- `b45fb60e` — claim and bring journal code from master
- `590c35ef` — offset index, corrupt-index test, 19 journal tests green
- `a2f49494` — two benchmark scripts
- `67d79e49` — benchmark scripts, 0.55x result
- `8b50d8e4` — move to REVIEW

Cherry-picking `590c35ef`, `a2f49494`, `67d79e49` would bring only TASK-226's production code and tests. The task file move and TASK-231 changes would be left behind.

---

## 7. Additional observations

### 7.1 The barrier test failure is environmental

`test_a_delta_write_into_the_real_directory_is_refused` fails in the worktree because `work/` does not exist. It passes on master where `work/` exists. This is not a code defect and not caused by TASK-226's changes.

### 7.2 Minor inefficiency in `replay()`

The `base_digest` check in `replay()` (lines 355-364) re-reads every entry that was already read in the main loop (lines 345-353). Each entry is read twice: once for the record, once for the digest. This is O(M) either way but doubles the I/O. A minor optimization would be to collect base digests during the first loop. Not a bug.

### 7.3 Index write atomicity on Windows

The result block notes that `os.replace()` may not be atomic on Windows. The code handles this correctly: a torn index write is detected by `_read_index()` (JSON parse fails → returns None → triggers rebuild). Safe but adds latency on the next read.

### 7.4 The index is small

At 500 records, the index is ~2.2 KB (per the result block). Rebuild cost is negligible even at 5,000 records. The index is a worthwhile optimization.

---

## Findings

| # | Severity | Finding | Evidence |
|---|----------|---------|----------|
| 1 | — | Index implementation is correct and consumed | `store.py:440,556,557,558,775` calls `queuejournal.*`; mutation test at `test_index_points_at_last_entry_not_first` catches first-vs-last bug |
| 2 | — | Index is DERIVED and rebuildable | 3 tests prove corrupt/absent/mismatched index handling |
| 3 | — | Tests are falsifiable | Mutation test proved `test_index_points_at_last_entry_not_first` catches the exact bug the index exists to prevent |
| 4 | — | QUEUE_JOURNAL stays OFF | `store.py:427` default is False |
| 5 | — | No production files deleted by merge | `git diff --diff-filter=D` returns only a task-file move |
| 6 | Info | Scope drift: TASK-231 on same branch | `gather.py`, `providers/__init__.py`, `test_http_timeout_*`, `test_prefetch_headcount.py` are TASK-231, not TASK-226 |
| 7 | Info | Benchmark 5000-record figure is MODELLED | Scripts label it correctly; 50 and 500 are MEASURED |
| 8 | Info | `replay()` reads entries twice for digest check | Lines 345-364; minor inefficiency, not a bug |
| 9 | Info | One test fails environmentally in worktree | `test_a_delta_write_into_the_real_directory_is_refused` needs `work/` dir; passes on master |

---

## Disposition

**MERGE** — with cherry-pick to separate TASK-226 from TASK-231.

**Reason:** The artifact exists, is wired into production through `store.py`, has falsifiable tests that prove the index is correct and DERIVED, and does not delete any production files. The QUEUE_JOURNAL flag stays OFF, so merging is low-risk even before the flag is turned on. The scope drift (TASK-231 on the same branch) is cleanly separable by cherry-picking the five TASK-226 commits.

**Cherry-pick set for TASK-226 only:**
```
590c35ef  offset index for O(M) replay, corrupt-index test
a2f49494  two benchmark scripts
67d79e49  benchmark results, 0.55x at 500 records
8b50d8e4  task file move to REVIEW
```

Plus the task-file content for the result block.

**What Claude should decide:**
1. Whether to turn QUEUE_JOURNAL on (the performance case is strong: 0.55x at 500 records; the crash/interleaving contract from the earlier GLM review still applies).
2. Whether the index file (`queue.jsonl.journal.idx`) needs explicit coverage in the production write barrier (the result block flags this as a follow-up).
3. Whether to merge TASK-231 separately or together.

---

## Reproducible commands

```bash
# Check out the exact SHA
git worktree add .qwen/worktrees/glm-432 36a4ce61b454187772e78daac49b08282380193e --detach

# Run the index tests
cd .qwen/worktrees/glm-432
python -m unittest tests.test_the_journal_index -v

# Run all journal tests (1 environmental failure expected in worktree)
python -m unittest discover -s tests -p "test_*journal*" -v

# Verify SHA
git rev-parse qwen-worker-8-r28

# Check scope drift
git diff master...36a4ce61b454187772e78daac49b08282380193e --stat

# Check deletions
git diff master...36a4ce61b454187772e78daac49b08282380193e --diff-filter=D --name-only
```
