# TASK-437 — GLM Independent Verification of TASK-267

**Review target:** TASK-267, LLM tiebreaker for FLAGGED domains
**Branch:** qwen-worker-3-r9
**Target SHA reviewed:** 402a0d305c5a9c9acf6591956b13bf7372369477
**Branch HEAD at review time:** 734cc062e97fae2a601ad3032f37827961d19f7c (branch has moved)
**Review date:** 2026-09-28
**Reviewer:** GLM (independent verification)

---

## 1. Artifact Existence — VERIFIED

Both artifacts exist at the target SHA:

| File | Lines | Status |
|------|-------|--------|
| `scripts/stage_s3_llm_tiebreaker.py` | 385 | New file, exists |
| `tests/test_llm_tiebreaker.py` | 436 | New file, exists |

Confirmed via `git show 402a0d30:scripts/stage_s3_llm_tiebreaker.py` and `git show 402a0d30:tests/test_llm_tiebreaker.py`.

---

## 2. Test Results — VERIFIED

**Claim:** 23 new tests, all pass.

**Verification:** Ran `python -m unittest tests.test_llm_tiebreaker -v` at the target SHA.

**Result:** All 23 tests pass in 0.202s.

```
Ran 23 tests in 0.202s
OK
```

Test classes verified:
- `TestIsJudgeable` (4 tests) — no-company-data exclusion
- `TestParseResponse` (6 tests) — strict JSON validation
- `TestValidateReason` (3 tests) — tautology rejection (TASK-272)
- `TestCostReport` (3 tests) — ESTIMATED_ONLY status
- `TestNoModelRefuses` (2 tests) — dry-run and NoModel refusal
- `TestSetDiffLostIsZero` (2 tests) — LOST assertion
- `TestModelFailureKeepsOriginal` (2 tests) — error handling
- `TestNoCompanyDataExcluded` (1 test) — integration test

---

## 3. Production Callers — NOT APPLICABLE (Script Pattern)

**Finding:** Zero `src/` callers of `stage_s3_llm_tiebreaker.py`.

**Context:** This is the established pattern for `scripts/stage_s3_*`. Verified:
- `stage_s3_rejudge_amended.py` — zero `src/` callers
- `stage_s3_icp.py` — zero `src/` callers

These are standalone CLI tools invoked via `py -3 scripts/stage_s3_llm_tiebreaker.py`, not library modules imported by production code. The script is the artifact.

**Verification command:**
```bash
git grep -n "stage_s3_llm_tiebreaker\|llm_tiebreaker" 402a0d30 -- src/
# (empty — no callers)
```

---

## 4. Safety Gates — VERIFIED

### 4.1 Dry-run refusal
**Test:** Run without `--live` flag.
**Result:** Exits 0, prints "DRY RUN: no model will be called", no output file created.

### 4.2 NoModel refusal
**Test:** Run with `--live` but `llm.from_env()` returns `NoModel`.
**Result:** Exits 1, prints "REFUSING: no model configured", no output file created.

### 4.3 Model error handling
**Test:** Model raises `ModelError` or `ModelUnavailable`.
**Result:** Domain keeps original FLAGGED verdict, not written to tiebreaker journal.

**Verification:** Drove through `main()` entry point with faked model and temp journals.

---

## 5. Falsification — VERIFIED

### 5.1 Mutation tests
Broke the implementation and confirmed tests catch it:

| Mutation | Broken behavior | Test that catches it |
|----------|-----------------|---------------------|
| `is_judgeable` returns True for no-company-data | Excluded population judged | `test_no_company_data_is_not_judgeable` |
| `validate_reason` always returns True | Tautologies accepted | `test_tautological_in_reason_rejected` |
| `parse_response` skips verdict validation | Invalid verdicts accepted | `test_invalid_verdict_rejected` |

### 5.2 Integration tests drive real entry point
Tests call `mod.main(["--live"])` with faked `llm.from_env`, not internal functions directly. The `FakeModel` records calls and returns scripted answers.

### 5.3 Not accepted as proof
- No `hasattr` checks
- No assertions on source text
- No fake cassettes returning fake data — `FakeModel` is a proper test double that exercises the real parsing/validation pipeline

---

## 6. TASK-272 Warning — VERIFIED

**Claim:** Tautological reasons (verdict restatements) are rejected.

**Implementation:** `validate_reason(data, row)` at line 149 checks against a dictionary of tautologies per verdict:
- "in": "fits the criteria", "meets the criteria", "is a good fit", etc.
- "out": "does not fit", "is not a fit", etc.
- "flagged": "insufficient evidence", "cannot determine", etc.

**Tests:** 3 tests verify tautology rejection and grounded-reason acceptance.

**Verification:** Directly called `validate_reason` with tautological and grounded reasons.

---

## 7. Deletion Check — NO PRODUCTION CODE DELETED

**Command:** `git diff master...402a0d30 --diff-filter=D --name-only`

**Result:** Three task files "deleted":
- `docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md`
- `docs/qwen-tasks/TODO/TASK-410-glm-verify-task-400-critical-path.md`
- `docs/qwen-tasks/TODO/TASK-412-suppression-list-audit.md`

**Analysis:** These are task lifecycle moves (TODO → REVIEW/RUNNING), not content deletion. TASK-387 exists at `docs/qwen-tasks/RUNNING/TASK-387-ledger-write-back-of-provider-sends-and-replies.md` at the target SHA. No production code deleted.

---

## 8. Scope Drift — SIGNIFICANT

**Branch carries work from 6+ tasks:**
- TASK-267: LLM tiebreaker (target of this review)
- TASK-358: CheapVerifier integration (`src/providers/cheapverifier.py`, 1141 lines)
- TASK-387: Provider event writeback (`tests/test_task387_provider_event_writeback.py`)
- TASK-410: GLM verify task 400 (task file moves)
- TASK-412: Suppression list audit (task file moves)
- TASK-426: Bison staging (`src/bisonfactory.py` modifications)
- Suite triage and other infrastructure

**TASK-267 specific changes:** Only 3 files added (script, tests, task file). No modifications to existing code.

**Cherry-pick path:** TASK-267's changes can be cleanly cherry-picked:
```bash
git cherry-pick 82d86014 d0ea4327 402a0d30
```

---

## 9. Code Quality Observations

### 9.1 Minor: unused parameter
`cost_report(model, n_calls)` takes `n_calls` but derives call count from `model.calls` instead. Not a bug, but the parameter is unused.

### 9.2 Module loading pattern
The script loads `stage_s3_icp.py` dynamically via `importlib.util` to access the `STAGE` directory constant. This is the same pattern used by other `stage_s3_*` scripts.

### 9.3 Prompt design
The prompt template includes the row's actual fields (employees, country, industry, reason) and instructs the model to ground its reason in those fields. This addresses TASK-272's concern about verdict-restating reasons.

---

## 10. Disposition

### TASK-267: MERGE

**Rationale:**
1. Artifact exists and does what the result block claims.
2. All 23 tests pass, and they are falsifiable (mutation tests confirm).
3. Safety gates work correctly through the real entry point.
4. No existing code modified, no regressions possible.
5. Follows established `scripts/stage_s3_*` pattern (standalone CLI tool).
6. TASK-272 warning heeded — tautological reasons rejected.
7. No production code deleted.

**Cherry-pick recommended** due to branch scope drift. TASK-267's 3 commits are clean and self-contained.

### Branch-level: SCOPE DRIFT

The branch carries significant work from other tasks. Merging the full branch would integrate TASK-358 (CheapVerifier), TASK-387 (writeback), TASK-412 (suppression audit), and TASK-426 (bison staging) changes. These require their own reviews.

---

## 11. Verification Commands

```bash
# Checkout target SHA
git checkout 402a0d305c5a9c9acf6591956b13bf7372369477 --detach

# Run tests
python -m unittest tests.test_llm_tiebreaker -v

# Check for src/ callers
git grep -n "stage_s3_llm_tiebreaker\|llm_tiebreaker" 402a0d30 -- src/

# Check for deletions
git diff master...402a0d30 --diff-filter=D --name-only

# Return to branch
git checkout qwen-worker-3-r9
```

---

## 12. Summary

| Check | Result |
|-------|--------|
| Artifact exists | ✓ VERIFIED |
| Tests pass | ✓ 23/23 pass |
| Tests falsifiable | ✓ Mutation tests confirm |
| Safety gates work | ✓ Dry-run and NoModel refusal verified |
| Production callers | N/A (script pattern) |
| No code deleted | ✓ Only task file moves |
| TASK-272 heeded | ✓ Tautologies rejected |
| Scope drift | ⚠ Significant — cherry-pick recommended |

**Recommendation:** MERGE TASK-267's specific changes via cherry-pick. The script is well-designed, comprehensively tested, and follows established patterns. The branch requires separate review for other tasks' contributions.
