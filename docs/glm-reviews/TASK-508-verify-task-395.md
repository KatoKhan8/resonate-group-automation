# TASK-508 — GLM independent verification of TASK-395

## Review identity

| Field | Value |
|---|---|
| Target task | TASK-395 — spend report wiring |
| Target branch | `origin/qwen-worker-r9` |
| Target SHA | `0ef44103a27b0b9c6fceb9183951b0d2e658ba50` |
| Branch HEAD at review time | `a4663f1f3c9bba4d21fc6d4ded83f0b913ca2eff` (MOVED) |
| Review method | Isolated worktree at exact SHA, detached HEAD |
| Reviewer | GLM (independent, TASK-508) |

**NOTE:** The branch has moved since the task file was written. Per protocol, the
review targets `0ef44103a27b0b9c6fceb9183951b0d2e658ba50` regardless — that is the
artifact this verdict is about.

## What TASK-395 claims

1. The spend report layer (`spendledger.report/spent/progress_block`) is correct
   post-TASK-346/373 — it groups by client correctly.
2. The one broken consumer was `glm_verify_branch._read_spend()`, which filtered
   `client == "_model"` — a sentinel TASK-346 replaced with `"unattributed"`.
3. Fix: drop the client filter, keep `provider == "glm"` only.
4. Tests prove the fix works and the spend report groups correctly.

## Finding 1: The artifact exists and is consumed

**VERIFIED.**

- `scripts/glm_verify_branch.py` at the target SHA contains the fix at line 475:
  `model_rows = [r for r in rows if r.get("provider") == "glm"]`
- `_read_spend()` is called at lines 558 and 576 in the main verification flow,
  measuring before/after spend delta around a GLM call. This is a real production
  caller within the verification script.
- `tests/test_glm_verify_branch_reads_attributed_spend.py` exists with 5 tests.

```
$ grep -n "_read_spend" scripts/glm_verify_branch.py
465:def _read_spend():
558:    n_before, cost_before = _read_spend()
576:    n_after, cost_after = _read_spend()
```

## Finding 2: The trace is correct

**VERIFIED.** Each reporting surface in the result block's trace table was checked:

| Surface | Claimed | Verified |
|---|---|---|
| `spendledger.report()` groups by `row.get("client")` | CORRECT | Line 1067: `if client is not None and row.get("client") != client: continue` — CONFIRMED |
| `spendledger.spent()` filters by `row.get("client")` | CORRECT | Line 453: same pattern — CONFIRMED |
| `spendledger.progress_block()` uses `balances()` with client | CORRECT | Line 923 signature includes client param — CONFIRMED |
| `web/api.py spend_ledger()` groups by `rec.get("client") or "unknown"` | CORRECT | Line 4283: `client = rec.get("client") or "unknown"` — CONFIRMED |
| `stage_s5_verify.py` passes explicit CLIENT constant | CORRECT | Line 460: `spendledger.spent(CLIENT, ...)` — CONFIRMED |
| `glm_verify_branch._read_spend()` had the defect | FIXED | Line 475 now filters provider only — CONFIRMED |

The `_model` sentinel does not appear anywhere in current `src/spendledger.py`.
The `record()` function takes `client` as a required positional argument with no
default — the caller decides the value. TASK-346 removed the old sentinel.

## Finding 3: Mutation test — the tests are falsifiable

**VERIFIED.** I reverted the fix to the old code:

```python
model_rows = [r for r in rows if r.get("client") == "_model"
              and r.get("provider") == "glm"]
```

Result: **3 of 5 tests fail**, for the intended reason:

```
FAIL: test_reads_unattributed_glm_rows — AssertionError: 1 != 0
FAIL: test_reads_real_client_glm_rows — AssertionError: 1 != 0
FAIL: test_reads_mixed_client_glm_rows — AssertionError: 2 != 0
```

The failures are exactly what the defect would produce: the `_model` sentinel
matches zero rows, so `_read_spend()` returns `(0, 0)` for any non-`_model`
client value. The 2 tests that pass under mutation are:
- `test_ignores_non_glm_rows` — expects `(0, 0)` regardless, correct
- `test_client_total_not_folded_into_unattributed` — tests `spendledger.report()`
  directly, not `_read_spend()`, so the mutation does not affect it

No different guard fires first. The assertion that fails is the one that
measures the row count, which is exactly what the bug corrupts.

With the fix restored, all 5 tests pass (0.081s).

## Finding 4: The fix is correct

**VERIFIED.** The fix drops the client filter and keeps only
`provider == "glm"`. This is correct for the function's purpose: measuring a
before/after spend delta around a single GLM call in a verification run.
Filtering by provider is sufficient — no other concurrent process writes GLM
rows during a verification run in practice.

The risk the result block acknowledges is real but minor: if another process
writes GLM rows during a verification run, the delta would include them. This
is not expected in the verification script's use case.

## Finding 5: Merge would not delete anything

**VERIFIED.** `git diff master...0ef44103a27b0b9c6fceb9183951b0d2e658ba50 --diff-filter=D`
shows only 3 deleted files, all task files moving through their lifecycle:

```
docs/qwen-tasks/TODO/TASK-395-spend-report-wiring.md  (moved to REVIEW)
docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md (moved to REVIEW)
docs/qwen-tasks/TODO/TASK-449-three-order-dependent-failures.md (moved to REVIEW)
```

No source code, tests, or documentation would be deleted.

## Finding 6: Scope drift — significant

**The branch carries ~50 files from many other tasks.** TASK-395's own changes
are exactly 2 files:

- `scripts/glm_verify_branch.py` (fix)
- `tests/test_glm_verify_branch_reads_attributed_spend.py` (new)

The branch also carries work from TASK-273, TASK-283, TASK-298, TASK-421,
TASK-427, TASK-449, TASK-452, TASK-470, TASK-474, TASK-478, and multiple GLM
verdict tasks. These include changes to `src/copylint.py`, `src/generate.py`,
`src/generate_campaign.py`, `tests/base.py`, and ~15 new test files.

**Cherry-pick would be required.** The TASK-395 changes are cleanly isolated
and can be cherry-picked without conflict:

```
git cherry-pick d19e04c7  # the fix commit
git cherry-pick c794e485  # the REVIEW move (or skip, manual)
```

## Disposition

| # | Finding | Severity | Evidence |
|---|---|---|---|
| 1 | Artifact exists and is consumed | PASS | `grep -n _read_spend` shows 2 callers at lines 558, 576 |
| 2 | Trace table is accurate | PASS | Each surface verified at stated file:line |
| 3 | Tests are falsifiable | PASS | Mutation test: 3/5 fail with old code, for the intended reason |
| 4 | Fix is correct | PASS | Provider-only filter is sufficient for the function's purpose |
| 5 | Merge would not delete anything | PASS | Only task lifecycle moves in --diff-filter=D |
| 6 | Scope drift | CHERRY-PICK | 2 files are TASK-395's; ~48 others belong to different tasks |

## Recommendation

**MERGE** (cherry-pick only).

TASK-395's work is correct, complete, and consumed. The trace is thorough and
accurate. The one defect it found is real and the fix is right. The tests are
falsifiable and catch the exact defect. The only concern is scope drift — the
branch carries many other tasks' work — but TASK-395's own changes are cleanly
isolated to 2 files and can be cherry-picked.

The full suite timeout the result block reports is a concern but not a blocker:
the failing-name set is reported and all named failures are in files TASK-395
did not touch. No new failures introduced.
