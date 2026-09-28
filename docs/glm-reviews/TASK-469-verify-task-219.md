# GLM Independent Verification: TASK-230

## Review metadata

| Field | Value |
|-------|-------|
| Task | TASK-230 — give the bounded gather its first caller: the free call |
| Branch | `origin/task-230-prefetch-headcount` |
| Branch HEAD SHA | `f0ada227185fad2f54e5f1bca1e2d37357ff8098` |
| Verified SHA | `f0ada227185fad2f54e5f1bca1e2d37357ff8098` (confirmed via `git rev-parse`) |
| Review worktree | `.qwen/worktrees/review-task-469` (detached HEAD at verified SHA) |
| Reviewer | GLM (independent, TASK-469) |
| Date | 2026-09-28 |
| Disposition | **MERGE** |

---

## 1. Does the artifact exist, and does it do what the result block claims?

**VERIFIED.** The artifact exists on the reviewed ref.

### Files changed (4 source/test files, 2 task files)

| File | Change | Lines |
|------|--------|-------|
| `src/gather.py` | Modified — added `prefetch_headcount()` and `DEFAULT_HEADCOUNT_K = 8` | +202 |
| `src/enrich.py` | Modified — wired prefetch into `enrich.run()`, added spend bridge | +58 / -7 |
| `tests/test_prefetch_headcount.py` | New — 15 tests | +623 |
| `tests/test_enrich.py` | Modified — one test opts out with `prefetch=False` | +9 / -1 |
| `docs/qwen-tasks/DONE/TASK-230-...` | New (task moved from TODO to DONE) | +206 |
| `docs/qwen-tasks/TODO/TASK-230-...` | Deleted (moved to DONE) | -102 |

### Claim-by-claim verification

| # | Result block claim | Verified? | Evidence |
|---|-------------------|-----------|----------|
| 1 | Ledger equality holds (serial vs K=8) | **YES** | `test_ledger_is_byte_identical_serial_vs_k8` passes; independently reproduced by running the test in the review worktree (15/15 pass in 1.267s) |
| 2 | 20 consecutive runs at K=8 all byte-identical | **YES** | `test_ledger_equality_holds_across_twenty_runs` passes |
| 3 | Results land on the right records | **YES** | `test_each_domains_count_lands_on_that_domain` asserts `[10, 20, 30, 40, 50]` with distinguishable fakes |
| 4 | Break-proof: reversed apply is caught | **YES** | Independently reproduced: mutation produces `[40, 30, 20, 10]` vs expected `[10, 20, 30, 40]` |
| 5 | `spend()` called exactly once per record that needs it | **YES** | `test_spend_called_once_per_record_that_needs_it` and `test_spend_not_called_for_record_already_carrying_headcount` pass |
| 6 | One record's failure leaves others intact | **YES** | `test_one_failure_preserves_neighbours` and `test_a_timeout_leaves_neighbours_intact` pass |
| 7 | Budget cap stays serial | **YES** | `test_a_tight_cap_refuses_in_order` passes with cost pinned to 1 and cap=3 |
| 8 | Default K is 8 | **YES** | `DEFAULT_HEADCOUNT_K = 8` at `src/gather.py:289`; `test_default_k_is_eight` passes |

---

## 2. Existence is not function — is every link CONSUMED?

**VERIFIED.** The full chain has real production callers at every link.

### Caller chain

```
enrich.run()                          src/enrich.py:1410
  └─ _gather.prefetch_headcount()    src/gather.py:363 (inside prefetch_headcount)
       └─ gather()                   src/gather.py:190 (the primitive)
```

**`prefetch_headcount` callers in `src/`:**
- `src/enrich.py:1410` — `enrich.run()` calls `_gather.prefetch_headcount(targets, contactout.people_count, _spend)`

**`gather()` callers in `src/`:**
- `src/gather.py:363` — `prefetch_headcount()` calls `gather(need, ..., k=k, timeout=timeout)`

The primitive-without-a-caller mistake (TASK-029/028/019) is NOT repeated. Both `gather` and `prefetch_headcount` have exactly one production caller each, and both are consumed.

**Guard consistency:** The DECIDE phase in `prefetch_headcount` checks `"headcount_signal" in facts` (line 345). `enrich_record` at line 954 checks `"headcount_signal" not in facts` before making the people-count call. These are the same guard, so the prefetch and the serial path make identical decisions. Records the prefetch populates are correctly skipped by `enrich_record`.

---

## 3. Falsification — can the tests pass while the implementation is wrong?

### Mutation test (independently reproduced)

Reversed the gather output and confirmed:
- Mutated values: `[40, 30, 20, 10]`
- Expected: `[10, 20, 30, 40]`
- **Mutation detected: YES**

The break-proof tests (`BreakProof` class) catch a scrambled apply order through the aggregate of `(record_id, headcount_signal)` pairs, even when ok values collide (timeout pattern differs).

### Tests that would pass with a wrong implementation (rejected as proof)

None of the tests rely on:
- `hasattr` checks
- Assertions on source text
- Token-in-file checks
- Proving a function exists
- JSON shape alone
- Fake cassettes returning fake data

All tests use deterministic fake providers with distinguishable answers and assert on observable behaviour (record state, ledger content, spend call log).

### Wiring falsification (noted, not blocking)

The `test_prefetch_headcount.py` tests call `prefetch_headcount` directly, not through `enrich.run`. No test runs `enrich.run(live=True)` with the prefetch enabled and asserts on the resulting waterfall ledger. The wiring into `enrich.run` is verified by code inspection:

1. `enrich.run` imports `gather` (line 1389: `from . import gather as _gather`)
2. `enrich.run` calls `_gather.prefetch_headcount(targets, contactout.people_count, _spend)` (line 1410)
3. The spend bridge (lines 1398-1408) charges the shared `Budget` and writes the per-record waterfall step via `waterfall.record_step`

The bridge shape matches what `prefetch_headcount` expects: `spend(call, why, provider, rec=rec)`. The bridge is identical in structure to the test's `_bridge_spend` helper.

However, 48 of 49 tests in `test_enrich.py` call `enrich.run(live=True)` with the prefetch enabled (default `prefetch=True`) and pass. This means the prefetch IS exercised in the test suite — it runs against the fake `contactout.people_count`, populates `headcount_signal`, and the subsequent `enrich_record` walk correctly skips the people-count branch. The tests pass because the prefetch and the serial path make the same decisions (guard consistency verified above).

**Assessment:** The wiring is correct and verified by code inspection and indirect exercise. An explicit integration test asserting on the waterfall ledger after `enrich.run(live=True)` with the prefetch would be stronger, but the absence is not a blocker given the guard consistency and the 48 passing tests that exercise the path.

---

## 4. Are the tests falsifiable?

**YES.** Each test class tests a distinct property with observable assertions:

| Test class | What it falsifies | How it could pass while wrong |
|------------|-------------------|-------------------------------|
| `LedgerEquality` | Serial vs concurrent produce identical waterfalls | Only if the apply is in input order AND spend is called identically |
| `ResultsLandOnTheRightRecords` | Company A's count on company A | Would fail if gather returned completion-order results |
| `BreakProof` | Scrambled apply is detected | Would fail if the test compared aggregates that are order-insensitive |
| `FailureIsolation` | One failure doesn't break neighbours | Would fail if an exception propagated to the pool level |
| `SpendIsCalledCorrectly` | spend() called exactly when needed | Would fail if spend were called for already-populated records |
| `BudgetCapIsSerial` | Cap refuses in order | Would fail if concurrent charges read the same `spent` |
| `DefaultK` | K=8 is the default | Would fail if the constant were different |

None of these tests assert on source text, function existence, or JSON shape alone. All assert on observable behaviour.

---

## 5. Would merging DELETE anything?

**NO.** The `--diff-filter=D` shows only one deleted file:

- `docs/qwen-tasks/TODO/TASK-230-the-free-call-that-dominates-the-count.md` — the task file, moved to DONE.

No source files, test files, or configuration files are deleted. The `--shortstat` for `src/` and `tests/` shows `4 files changed, 870 insertions(+), 22 deletions(-)` — all deletions are within modified files (replaced function signatures, updated docstrings), not removed files.

---

## 6. Scope drift

**NONE.** The branch carries exactly three commits:

1. `01d1df6b` — Qwen claims TASK-230
2. `8c105f73` — TASK-230: prefetch headcount_signal concurrently at K=8
3. `f0ada227` — TASK-230 result block carries its own commit SHA

All changes are within the task's scope. No unrelated files, no scratch output, no configuration changes. The branch is clean for cherry-pick or merge.

---

## 7. Additional observations

### Positive

1. **The timeout trap is correctly acknowledged, not hidden.** `gather`'s docstring explicitly states that a timed-out call still reached the provider and still cost a credit. On people-count (cost 0) this has no value to be wrong about. The task explicitly deferred HTTP-layer timeout enforcement as a prerequisite for wiring any PAID route.

2. **The prefetch is live-only.** Dry runs plan via `plan()` and charge the in-memory budget without calling providers. A prefetch in dry run would have produced waterfall entries the planning pass would not, and the code correctly gates on `if live and targets and prefetch:`.

3. **The `prefetch=False` opt-out is well-motivated.** The one test updated in `test_enrich.py` asserts on the log shape, which the prefetch legitimately changes. The opt-out is documented in the function docstring.

### Noted risks (not blocking)

1. **No explicit integration test for `enrich.run` + prefetch + waterfall assertion.** The wiring is verified by code inspection and indirect exercise (48 tests pass with prefetch enabled), but no test explicitly asserts on the waterfall ledger after running `enrich.run(live=True)` with the prefetch. The ledger equality test in `test_prefetch_headcount.py` uses the same bridge shape, which provides strong indirect evidence.

2. **The `enrich_record` log entry is no longer written for prefetched records.** The `store.log(rec, "enrich", f"people-count: {count.get('profiles')} profiles (free)")` line in `enrich_record` (line 963) is only reached when `headcount_signal` is NOT already present. After a successful prefetch, the record already has `headcount_signal`, so this log entry is skipped. Any downstream reader that depended on this log entry for every record would need updating. The result block notes this risk explicitly.

---

## 8. Conflict markers

**NONE.** `grep -rn "^<<<<<<< \|^======= $\|^>>>>>>> " src/ tests/ scripts/` returns nothing.

---

## Findings summary

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | Artifact exists and does what the result block claims | — | VERIFIED |
| 2 | Every link in the caller chain is consumed | — | VERIFIED |
| 3 | Mutation test catches reversed apply | — | VERIFIED |
| 4 | Tests are falsifiable (behaviour assertions, not source text) | — | VERIFIED |
| 5 | Merging would not delete any source/test files | — | VERIFIED |
| 6 | No scope drift | — | VERIFIED |
| 7 | No conflict markers | — | VERIFIED |
| 8 | No explicit integration test for `enrich.run` + prefetch + waterfall | Low | NOTED — not blocking; indirect evidence is strong |

---

## Recommendation

**MERGE.**

The work is correct, well-tested, and scoped. The caller chain is complete (no primitive-without-a-caller defect). The ledger equality test is the acceptance test the task named, and the break-proof tests confirm the test would catch a scrambled apply. The timeout trap is acknowledged and correctly deferred. The only noted gap — no explicit integration test for `enrich.run` with the prefetch — is low severity given the indirect evidence from 48 passing tests and the identical bridge shape.
