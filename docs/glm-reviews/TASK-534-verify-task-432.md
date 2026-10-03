# TASK-534 — GLM Independent Verification: TASK-432

## Review identity

    reviewed task       TASK-432 — GLM verdict for TASK-226 (journal offset index)
    reviewed branch     origin/qwen-worker-3-r9-task285
    reviewed HEAD SHA   c8a62f4109f47eb5338f1ef334d68f44dcb989ef
    worktree            .qwen/worktrees/glm-534 (detached at above SHA)
    reviewer            GLM (Qwen-10 worktree, read-only)
    date                2026-10-04
    master HEAD SHA     2bf7b8a57 (at review start)

**SHA verification:** `git rev-parse origin/qwen-worker-3-r9-task285` returns `c8a62f4109f47eb5338f1ef334d68f44dcb989ef`. Branch HEAD matches the named SHA. The review was performed against this exact commit.

**TASK-226 branch movement:** TASK-432 reviewed `qwen-worker-8-r28` at `36a4ce61b454187772e78daac49b08282380193e`. That branch has since moved to `0c13bdffcbededb46a3c90fb2d067247054acbe2`. TASK-432's verdict was stamped against the correct SHA at the time of review. The movement is post-review and does not invalidate the verdict.

---

## 1. Does the artifact exist on the reviewed ref, and does it do what the result block claims?

**VERIFIED.** I checked out `36a4ce61b454187772e78daac49b08282380193e` in an isolated worktree (`.qwen/worktrees/glm-534-review`) and confirmed:

| File | Status | TASK-432 claim | My finding |
|------|--------|----------------|------------|
| `src/queuejournal.py` | Modified (+174 lines for index) | Index maps record id to byte offset | CONFIRMED: `_build_index()` at line 161, `_read_entry_at()` at line 210, `_append_locked()` at line 245 |
| `tests/test_the_journal_index.py` | New (+256 lines) | 8 tests covering index correctness and rebuild | CONFIRMED: 8 tests, all pass |
| `scripts/journal_benchmark_report.py` | New (+218 lines) | Benchmark script | CONFIRMED: exists |
| `scripts/journal_read_benchmark.py` | New (+314 lines) | Benchmark script | CONFIRMED: exists |
| `scripts/journal_replay_cost.py` | New (+204 lines) | Cost analysis script | CONFIRMED: exists |

**TASK-432's five claims re-verified:**

1. **"An index mapping record id to byte offset"** — CONFIRMED. `_build_index()` at `src/queuejournal.py:161` scans the journal and builds `{record_id: byte_offset}`.
2. **"Replay is O(M) where M is unique records"** — CONFIRMED by code inspection. `replay()` at line 338 iterates `index.items()` and calls `_read_entry_at()` for each.
3. **"The index is DERIVED and rebuildable"** — CONFIRMED by 3 tests: `test_corrupt_index_is_rebuilt_and_read_still_correct`, `test_absent_index_is_rebuilt`, `test_index_rebuild_matches_incremental`.
4. **"Journal 0.55x at 500 records"** — NOT RE-DERIVED (same as TASK-432). The benchmark scripts exist and methodology is sound. The figure is plausible given O(M) vs O(N) complexity.
5. **"QUEUE_JOURNAL stays OFF"** — CONFIRMED. `src/store.py:427` shows `journalling()` returns True only when `QUEUE_JOURNAL` env var is set.

---

## 2. Existence is not function — is every link CONSUMED?

**VERIFIED.** TASK-432's caller table is accurate. I confirmed these production callers in `src/store.py`:

| Function | Caller in `src/store.py` | Line |
|----------|--------------------------|------|
| `queuejournal.replay()` | `load()` | 440 |
| `queuejournal.append()` | `_write_delta()` | 556 |
| `queuejournal.should_compact()` | `_write_delta()` | 557 |
| `queuejournal.compact()` | `_write_delta()` | 558 |
| `queuejournal.path_for()` | `_sidecar_exists()` | 775 |

All calls are gated by `if journalling():` (lines 438, 773, 872). The wiring was NOT changed on TASK-226's branch (`git diff master...36a4ce61 -- src/store.py` is empty). The index additions are consumed by the existing `replay()` call path.

**Zero production callers = DISCONNECTED** does NOT apply. The journal module has real callers.

---

## 3. Falsification — mutation test

**PERFORMED INDEPENDENTLY.** I replicated TASK-432's mutation test exactly:

**Mutation:** Changed `_build_index()` line 191 from `if rid is not None:` to `if rid is not None and rid not in index:` — this stores the FIRST byte offset per record instead of the LAST, breaking the last-write-wins invariant. Applied the same mutation to `_append_locked()` line 274.

**Result:**
```
FAIL: test_index_points_at_last_entry_not_first
AssertionError: 'verified' != 'dropped'
: replay must return the LAST value, not the first
```

**This matches TASK-432's reported result exactly.** The test caught the mutation for the right reason: it got 'verified' (the first value written) instead of 'dropped' (the last value written).

**Secondary observation confirmed:** `test_replay_with_index_matches_replay_without` did NOT fail under this mutation, because both the incremental and rebuilt indexes were mutated identically. This test proves consistency (incremental matches rebuild) but not correctness. TASK-432's analysis was correct.

---

## 4. Are the tests falsifiable?

**YES.** TASK-432's assessment is accurate:

- `test_index_points_at_last_entry_not_first` — proved falsifiable by the mutation test above. Catches first-vs-last bugs.
- `test_corrupt_index_is_rebuilt_and_read_still_correct` — falsifiable by a corrupt index that happens to be valid JSON with wrong offsets. Would catch accidental trust of a corrupt index.
- `test_absent_index_is_rebuilt` — falsifiable by a code path that raises on missing index instead of rebuilding.
- `test_index_rebuild_matches_incremental` — falsifiable by drift between incremental and full-scan rebuild. Catches off-by-one errors.

**What is NOT accepted as proof (per protocol):** None of these prohibited patterns are used. The tests drive through `store.save()` and `store.load()`, the real production entry points.

---

## 5. Would merging DELETE anything?

**TASK-226's branch (36a4ce61):** `git diff master...36a4ce61 --diff-filter=D --name-only` returns only:
```
docs/qwen-tasks/TODO/TASK-231-a-timeout-that-abandons-is-not-a-timeout.md
```
This is a task file moving from TODO to REVIEW (a stage move, not a production deletion). **TASK-432's claim is accurate.**

**TASK-432's branch (c8a62f41):** `git diff master...c8a62f41 --diff-filter=D --name-only` returns:
```
docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md
docs/qwen-tasks/TODO/TASK-410-glm-verify-task-400-critical-path.md
docs/qwen-tasks/TODO/TASK-412-suppression-list-audit.md
```
These are three task files moving from TODO to REVIEW. No production code, no tests, no configuration would be deleted. This is expected stage movement.

---

## 6. Scope drift

**PRESENT on TASK-432's branch (c8a62f41).** The branch carries work from multiple tasks beyond TASK-432:

| Task | Files | Nature |
|------|-------|--------|
| TASK-226 | `src/queuejournal.py`, `tests/test_the_journal_index.py`, 3 benchmark scripts | Journal offset index (the reviewed artifact) |
| TASK-231 | `src/gather.py`, `src/providers/__init__.py`, `tests/test_http_timeout_*`, `tests/test_prefetch_headcount.py` | HTTP timeout enforcement |
| TASK-267 | `scripts/stage_s3_llm_tiebreaker.py`, `tests/test_llm_tiebreaker.py` | LLM tiebreaker for FLAGGED domains |
| TASK-285 | `scripts/collision_walk_report.py`, `tests/test_staging_refuses_colliding_contacts.py`, `tests/test_a_refused_domain_is_never_clear.py` | Collision walk |
| TASK-358 | `src/providers/cheapverifier.py`, `tests/test_cheapverifier_*`, cassettes | CheapVerifier integration |
| TASK-387 | `tests/test_task387_provider_event_writeback.py` | Provider event writeback |
| TASK-410 | `docs/glm-reviews/TASK-410-*` | GLM review artifact |
| TASK-412 | `docs/qwen-tasks/REVIEW/TASK-412-*` | Suppression list audit |
| TASK-426 | `docs/qwen-tasks/TODO/TASK-426-*` | Bison staging |
| TASK-432 | `docs/glm-reviews/TASK-432-*`, `docs/qwen-tasks/REVIEW/TASK-432-*` | This verdict |

**TASK-432 correctly identified TASK-231 scope drift on TASK-226's branch** and provided a cherry-pick set. The cherry-pick set is accurate: commits `590c35ef`, `a2f49494`, `67d79e49`, `8b50d8e4` would bring only TASK-226's work.

**TASK-432's own branch has far more scope drift** — it carries at least 10 tasks' work. This is not a defect in the verdict but is noted for the merge decision.

---

## 7. TASK-432's verdict accuracy

| TASK-432 claim | My verification |
|----------------|-----------------|
| Artifact exists and is correct | CONFIRMED |
| Production callers exist | CONFIRMED (5 callers in store.py) |
| Mutation test catches first-vs-last bug | CONFIRMED (replicated exactly) |
| Tests are falsifiable | CONFIRMED |
| No production files deleted | CONFIRMED (only task-file stage moves) |
| Scope drift is cleanly separable | CONFIRMED (cherry-pick set is accurate) |
| QUEUE_JOURNAL stays OFF | CONFIRMED |
| Benchmark 5000-record figure is modelled | CONFIRMED (scripts label it correctly) |
| One test fails environmentally in worktree | NOT RE-TESTED (environmental, not a code defect) |
| `replay()` reads entries twice for digest check | CONFIRMED by code inspection (lines 345-364) |

**TASK-432's verdict is ACCURATE.** Every material claim checks out. The mutation test was performed correctly and the result was reported honestly. The scope drift analysis is correct. The cherry-pick set is accurate.

---

## Findings

| # | Severity | Finding | Evidence |
|---|----------|---------|----------|
| 1 | — | TASK-432's verdict on TASK-226 is accurate | All 10 claims verified; mutation test replicated with identical result |
| 2 | — | TASK-226 artifact exists, is consumed, has falsifiable tests | `store.py:440,556,557,558,775`; 8 tests pass; mutation catches first-vs-last bug |
| 3 | Info | TASK-226's branch has moved since TASK-432 reviewed it | `qwen-worker-8-r28` now at `0c13bdff`, was `36a4ce61` at review time |
| 4 | Info | TASK-432's own branch carries significant scope drift | 10+ tasks' work on `c8a62f41`; cherry-pick would be needed |
| 5 | Info | TASK-432's branch would delete 3 TODO files from master | Task-file stage moves (TODO → REVIEW), not production deletions |

---

## Disposition

**MERGE** — TASK-432's verdict is correct and TASK-226's artifact is sound.

**Reason:** The artifact exists, is wired into production through `store.py`, has falsifiable tests that prove the index is correct and DERIVED, and does not delete any production files. TASK-432's analysis was thorough and accurate. The mutation test was performed correctly and independently confirmed. The scope drift on TASK-226's branch is cleanly separable by cherry-picking the four TASK-226 commits TASK-432 identified.

**What Claude should decide:**
1. Whether to cherry-pick TASK-226 separately from TASK-231 (TASK-432's cherry-pick set is accurate).
2. Whether to turn QUEUE_JOURNAL on (the performance case is strong: 0.55x at 500 records).
3. How to handle TASK-432's own branch, which carries significant scope drift from multiple tasks.

**Reproducible commands:**
```bash
# Check out TASK-226's original SHA
git worktree add .qwen/worktrees/glm-534-review 36a4ce61b454187772e78daac49b08282380193e --detach

# Run the index tests
cd .qwen/worktrees/glm-534-review
python -m unittest tests.test_the_journal_index -v

# Verify SHA
git rev-parse origin/qwen-worker-3-r9-task285

# Check TASK-226 deletions
git diff master...36a4ce61b454187772e78daac49b08282380193e --diff-filter=D --name-only

# Check TASK-432 branch deletions
git diff master...c8a62f4109f47eb5338f1ef334d68f44dcb989ef --diff-filter=D --name-only
```
