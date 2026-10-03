# TASK-508 — GLM independent verification of TASK-395

## Review metadata

| Field | Value |
|---|---|
| Target task | TASK-395 (spend-report-wiring) |
| Target branch | origin/qwen-worker-r9 |
| Stated HEAD SHA | 0ef44103a27b0b9c6fceb9183951b0d2e658ba50 |
| Actual HEAD SHA at review time | af4836929c167bf45568e315f39b16996be34456 (branch moved) |
| SHA reviewed | 0ef44103a27b0b9c6fceb9183951b0d2e658ba50 (per task instruction) |
| Review worktree | .qwen/worktrees/task508-review (detached HEAD at target SHA) |
| Reviewer | GLM (independent, read-only) |
| Date | 2026-10-03 |

**Branch movement note:** `origin/qwen-worker-r9` has moved from `0ef44103a` to `af4836929`. Per task instruction, the review targets the original SHA `0ef44103a` as the artifact under verdict.

---

## Finding 1: Artifact exists and matches the result block's claims

**Status: VERIFIED**

TASK-395 claims two artifacts:
1. `scripts/glm_verify_branch.py` — fix to `_read_spend()` (modified)
2. `tests/test_glm_verify_branch_reads_attributed_spend.py` — new test file (5 tests)

Both exist at SHA `0ef44103a`. The fix drops `client == "_model"` from the filter, keeping only `provider == "glm"`. The test file contains 5 tests across 2 classes.

The result block's trace table is accurate: line numbers for `spendledger.spent()` (436), `spendledger.progress_block()` (923), `spendledger.report()` (1047), and `web/api.py spend_ledger()` (4270) all match. Client handling descriptions are correct.

---

## Finding 2: The defect is real and the fix addresses it

**Status: VERIFIED**

TASK-346 changed the default client sentinel from `"_model"` to `"unattributed"`. The old filter `client == "_model" and provider == "glm"` matched zero rows post-TASK-346, so every GLM verification report showed "0 rows, 0 micro-USD" regardless of actual spend.

**Mutation test performed:** Recorded a GLM row with `client="unattributed"` and measured both filters:
- OLD filter (`client == "_model"`): 0 rows, cost=0
- NEW filter (`provider == "glm"`): 1 row, cost=2560

The fix is correct: dropping the client filter and keeping only the provider filter is sufficient for the before/after delta measurement the script performs.

---

## Finding 3: Tests are falsifiable

**Status: VERIFIED**

All 5 tests pass on the branch (ran in isolated worktree, 0.123s).

Mutation test: monkey-patched `_read_spend` back to the old filter and confirmed:
- `test_reads_unattributed_glm_rows`: returns n=0, cost=0 (expects n=1, cost=2560) → FAILS
- The test fails for the INTENDED reason (the stale sentinel filter), not because of a different guard

The tests assert on return values (row count and cost), not on source text, hasattr, or JSON shape. They are genuine behavioural tests.

---

## Finding 4: _read_spend has a real caller

**Status: VERIFIED**

`_read_spend()` is called at lines 558 and 576 of `scripts/glm_verify_branch.py`, in a before/after delta around a GLM `complete()` call. The script is a verification tool (not production code), but the function is consumed within its module. This is not a zero-caller situation.

---

## Finding 5: Master has already superseded this fix

**Status: VERIFIED — this is the critical finding**

Master's current `scripts/glm_verify_branch.py` (line 855+) contains a SUPERSET of the TASK-395 fix:

| Aspect | TASK-395 branch (0ef44103a) | Master |
|---|---|---|
| Client filter | Dropped (was `_model`) | Dropped (same fix) |
| Return shape | 2-tuple: `(rows, cost)` | 3-tuple: `(rows, cost, by_client)` |
| Client breakdown | None | Groups by client with per-client row count and cost |
| Error handling | Swallows all exceptions → `0, 0` | `_read_spend_safely()` wrapper surfaces errors by name |
| Test coverage | 5 tests in new file | 5 tests (TASK-395) + 9 tests (TASK-414, already on master) |

Master's version was integrated via commit `90cd41752` ("INTEGRATE TASK-279, TASK-285, TASK-315, TASK-414, and two artifacts off the 9-r9 branch"). The `test_spend_report_groups_by_real_client_id.py` file (TASK-414, 9 tests) already exists on master.

**Implication:** Merging the TASK-395 branch's version of `_read_spend` would REGRESS master: it returns a 2-tuple where master's callers expect a 3-tuple. The branch's exception swallowing would also undo master's error surfacing.

---

## Finding 6: Merge would not delete production files

**Status: VERIFIED**

`git diff master...0ef44103a --diff-filter=D` shows only 3 deleted files:
- `docs/qwen-tasks/TODO/TASK-395-spend-report-wiring.md` (moved to REVIEW)
- `docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md` (moved to REVIEW)
- `docs/qwen-tasks/TODO/TASK-449-three-order-dependent-failures.md` (moved to REVIEW)

No production files, source modules, or test files would be deleted.

---

## Finding 7: Significant scope drift

**Status: NOTED**

The branch carries work from approximately 15 other tasks (TASK-273, TASK-283, TASK-298, TASK-421, TASK-427, TASK-449, TASK-452, TASK-470, TASK-474, TASK-478, and others). The diff is 52 files changed, +7088/-215 lines. TASK-395's own contribution is 2 files.

Cherry-picking TASK-395's specific changes would require extracting:
- `scripts/glm_verify_branch.py` (the 4-line filter change)
- `tests/test_glm_verify_branch_reads_attributed_spend.py` (new file)

Both are already superseded on master (see Finding 5).

---

## Disposition

| # | Finding | Disposition |
|---|---|---|
| 1 | Artifact exists | VERIFIED |
| 2 | Defect real, fix correct | VERIFIED |
| 3 | Tests falsifiable | VERIFIED |
| 4 | Function has caller | VERIFIED |
| 5 | Master already superseded | VERIFIED — critical |
| 6 | No production file deletion | VERIFIED |
| 7 | Scope drift | NOTED — 50 files from other tasks |

## Recommendation: CLOSE

TASK-395 identified a real defect (stale `_model` sentinel in `_read_spend`) and produced a correct fix with falsifiable tests. The work was legitimate and the result block is accurate.

However, master has already integrated a superset of this fix via TASK-414 and subsequent work. Master's version:
- Applies the same core fix (drops the `_model` filter)
- Adds client breakdown (3-tuple return)
- Improves error handling (surfaces exceptions instead of swallowing them)
- Has additional test coverage (9 more tests from TASK-414)

Merging the branch's version would regress master's 3-tuple interface and error handling. The fix is correct but no longer needed as a merge candidate. Cherry-picking the 2 files is unnecessary because master already has the superior version.

**No action required from Claude.** The defect is fixed, the fix is on master, and the branch artifact is a historical stepping stone that has been consumed.
