# GLM Independent Verification: TASK-352

**Task:** TASK-352 — A spend report the operator can act on  
**Branch:** origin/qwen-worker-4-r9  
**Branch HEAD SHA:** 2cb8755afc8ad069ccab24a6d80819d779c57e54  
**Verified at:** 2cb8755afc8ad069ccab24a6d80819d779c57e54 (exact SHA, isolated worktree)  
**Verifier:** GLM (TASK-493)  
**Date:** 2026-09-29

---

## Executive Summary

**DISPOSITION: MERGE with minor rework (labeling defect)**

The artifact exists, the tests pass, and the core claims hold under falsification. The branch carries significant scope drift (~20 other task files), so cherry-picking is required. One labeling defect in the formatted output is misleading but does not break the core invariant.

---

## 1. Artifact Existence — VERIFIED

Both artifacts exist on the branch at the exact SHA:

- `scripts/spend_report.py` (334 lines, NEW)
- `tests/test_the_spend_report_never_sums_two_units.py` (305 lines, NEW)

Verified with `git diff origin/master...2cb8755a --diff-filter=A --name-only`. Both files are new additions, not modifications.

The task file moved from `docs/qwen-tasks/TODO/TASK-352-...md` to `docs/qwen-tasks/REVIEW/TASK-352-...md`, as expected.

---

## 2. Test Results — ALL PASS

```
Ran 7 tests in 0.136s
OK
```

Tests cover:
1. Mixed-unit tripwire (not summed integer)
2. Three denominators labelled
3. Unpriced provider reports null
4. Unattributed _model rows reported separately
5. Ledger unchanged after report (read-only)
6. Cost-per-lead calculation on three denominators
7. `usd_estimate` function returns None for credits

---

## 3. Falsification Attempts

### 3.1 Mixed-Unit Sum — NOT SUMMED

**Claim:** A mixed-unit client gets the tripwire, not a summed integer.

**Test:** One `credits` row (100) + one `cents` row (447). If summed, the total would be 547. The formatted report contains "MIXED UNITS - a tripwire, not an amount" and does NOT contain "547".

**Verified:** The test asserts `assertNotIn("547", formatted)`. The code in `_summarize_provider` groups by unit (`by_unit` dict) and only sums `usd_estimate` values where they exist. Credits have `usd_estimate=None`, so they don't contribute to the USD total. The tripwire fires when `len(all_units) > 1`.

**Result:** Claim holds. The report does not sum across units.

### 3.2 Unpriced Provider — NULL, NOT ZERO

**Claim:** An unpriced provider (credits) reports `usd_estimate: null` and `rate_source: "unknown"`.

**Test:** `spendledger.record("acme", "deliverable", "deliverable-verify", 100)` writes a credits row. The report's provider summary has `usd_estimate=None` and `rate_source="unknown"`. The formatted report shows "usd_estimate: null", not "$0.0000".

**Verified:** The test asserts `assertIsNone(provider_summary["usd_estimate"])` and `assertIn("usd_estimate: null", formatted)`. The code in `spendledger.usd_estimate(500, "credits")` returns `(None, None, "unknown")` because `USD_PER_UNIT["credits"]` is `None`.

**Result:** Claim holds. The report does not invent a rate.

### 3.3 Three Denominators — LABELLED

**Claim:** All three cost-per-lead denominators appear, each labelled.

**Test:** 50 cohort leads, 31 written (drafted+approved+pushed), 13 approved (approved+pushed). The report shows:
- `per cohort lead: $0.0629`
- `per written lead: $0.1015`
- `per approved lead (both gates): $0.2420`

**Verified:** The test asserts all three keys exist in `block["cost_per_lead"]` and checks the formatted output contains "per cohort lead", "per written lead", "per approved lead (both gates)". It also checks that every data line with a dollar amount mentions a specific denominator (cohort/written/approved).

**Result:** Claim holds. A bare "cost per lead" without a label is not present.

### 3.4 Read-Only Ledger — BYTE-IDENTICAL

**Claim:** The ledger is byte-identical before and after generating the report.

**Test:** Write two rows, read the ledger file as bytes, generate the report, read the ledger again, assert equality.

**Verified:** The test asserts `assertEqual(before, after)`. The code in `spend_report.py` only calls `spendledger.load()`, which reads the ledger via `store.read_jsonl(path())`. No write operations.

**Result:** Claim holds. The report is read-only.

### 3.5 Unattributed _model Rows — SEPARATE

**Claim:** Rows with `client="_model"` are reported separately with a count.

**Test:** Two _model rows (2560 + 1280 = 3840 microusd). The report groups them under `client="_model"` and reports `unattributed_model_rows: {count: 2, total_cost: 3840}`.

**Verified:** The test asserts the _model block has `count=2` and `total_cost=3840`. The formatted report contains "UNATTRIBUTED MODEL ROWS" and "count: 2".

**Result:** Claim holds. The _model rows are reported separately.

**Note:** The implementation treats "_model" as a separate client block rather than a separate section within each client's report. This is technically correct but might not match the operator's intent if they expected unattributed rows to be reported alongside each client's spend. However, the task description says "Report their count and total separately, as unattributed" without specifying the exact structure, so this interpretation is acceptable.

---

## 4. Existence vs. Function — DISCONNECTED (but acceptable for a script)

**Finding:** `spend_report` is not imported or called anywhere in `src/`. Zero production callers.

**Context:** The task explicitly scoped this as a script (`scripts/spend_report.py`), not a library function. The acceptance criterion is running it from the command line: `py -3 scripts/spend_report.py --client productive`. The operator is the caller.

**Verdict:** For a standalone report script, the absence of a production caller is not a defect. The script is designed for ad-hoc operator use, not automation. However, if the operator expects this report to be generated automatically (e.g., as part of a daily digest), the lack of automation wiring would be a gap. The task description does not specify automation, so this is acceptable.

**Recommendation:** If the operator wants automated reports, a separate task should wire this script into a scheduled job or digest generator. As scoped, the artifact is complete.

---

## 5. Scope Drift — SIGNIFICANT

The branch carries ~20 other task files and docs besides TASK-352's work:

- 16 GLM verification task files (TASK-431 through TASK-446)
- TASK-430 (ICP verdicts)
- TASK-438 (GLM verdict for TASK-272)
- `docs/BRIEF-dry-run-executes-the-safety-path.md`
- `docs/glm-reviews/TASK-438-verify-task-272.md`
- `docs/OPERATING-MODE.md` changes

**Impact:** Merging the entire branch would bring all of this onto master. Cherry-picking only TASK-352's artifacts is required to avoid scope pollution.

**Files to cherry-pick:**
- `scripts/spend_report.py`
- `tests/test_the_spend_report_never_sums_two_units.py`
- `docs/qwen-tasks/REVIEW/TASK-352-a-spend-report-that-does-not-add-up-three-units.md` (move from TODO)

**Deletions:** The branch would delete `docs/qwen-tasks/TODO/TASK-352-...md` (moved to REVIEW). This is expected and correct.

---

## 6. Labeling Defect — MINOR

**Finding:** The formatted report says:
```
written leads (state='pushed'):  31
```

But the code defines `written_states = {"drafted", "approved", "pushed"}`. The label says "state='pushed'" but actually counts drafted+approved+pushed.

**Impact:** Misleading. An operator reading the report might think "written leads" only counts records in the "pushed" state, when it actually includes all three states that indicate passing the first gate.

**Severity:** Minor. The core invariant (never sum two units, label all denominators) is not broken. The label is a display issue, not a calculation issue.

**Fix:** Change the label to:
```python
lines.append(f"  written leads (drafted+approved+pushed):  {lc['written_leads']}")
```

Or more concisely:
```python
lines.append(f"  written leads (passed first gate):  {lc['written_leads']}")
```

**Recommendation:** Fix before merge, or file as a follow-up task. This is a one-line change.

---

## 7. Merge Safety — NO DELETIONS (except task file move)

`git diff origin/master...2cb8755a --diff-filter=D --name-only` returns only:
```
docs/qwen-tasks/TODO/TASK-352-a-spend-report-that-does-not-add-up-three-units.md
```

This is the task file moving from TODO to REVIEW. No other files would be deleted. Safe.

---

## 8. Dependency on TASK-332 — VERIFIED

TASK-352 depends on TASK-332, which "stops `report()` summing cents, credits and microusd into one printed number."

**Verified:** The `spendledger.py` module on this branch has the `row_unit()` function and the `USD_PER_UNIT` table, which are the TASK-332 artifacts. The `spend_report.py` script uses `spendledger.row_unit(row)` to determine each row's unit and groups by unit in `_summarize_provider`. The mixed-unit tripwire fires when `len(all_units) > 1`.

**Result:** TASK-332's work is present and consumed by TASK-352. The dependency is satisfied.

---

## 9. Acceptance Criteria — ALL MET

The task lists six acceptance criteria:

1. ✅ The report runs against the real ledger and prints per-provider, per-unit figures.
2. ✅ A mixed-unit client gets the tripwire, not a summed integer.
3. ✅ All three cost-per-lead denominators appear, each labelled.
4. ✅ An unpriced provider reports null, not zero or a guess.
5. ✅ Unattributed _model rows reported separately, with a count.
6. ✅ Read-only: the ledger is byte-identical before and after.

All six are verified by tests and confirmed by falsification.

---

## 10. Risks

1. **Labeling defect:** The "written leads (state='pushed')" label is misleading. Minor, one-line fix.
2. **Scope drift:** The branch carries ~20 other task files. Cherry-picking required.
3. **No automation:** The script is standalone and has no automated caller. Acceptable for the scoped task, but a gap if the operator expects automated reports.
4. **_model rows structure:** The implementation treats "_model" as a separate client block. This is technically correct but might not match the operator's intent. Acceptable given the task description's ambiguity.

---

## 11. Recommendation

**MERGE with minor rework.**

The artifact exists, the tests pass, the core claims hold under falsification, and the dependency on TASK-332 is satisfied. The labeling defect is minor and does not break the core invariant. The scope drift is significant but manageable via cherry-picking.

**Before merge:**
- Fix the "written leads" label (one-line change).
- Cherry-pick only TASK-352's artifacts to avoid scope pollution.

**After merge:**
- If the operator wants automated reports, file a follow-up task to wire this script into a scheduled job or digest generator.

---

## 12. Disposition

**MERGE / REWORK / CLOSE:** MERGE with minor rework (labeling defect).

**Reason:** The artifact is complete, the tests are falsifiable, and the core claims hold. The labeling defect is a one-line fix and does not block integration. The scope drift requires cherry-picking but does not indicate a fundamental problem with the work.

**Evidence:**
- Artifacts exist at exact SHA: verified.
- Tests pass: 7/7 green.
- Falsification: mixed-unit tripwire works, unpriced provider returns null, ledger is read-only, three denominators labelled.
- No deletions: safe to merge (with cherry-pick).
- Dependency satisfied: TASK-332's work is present and consumed.

**Not verified:**
- Whether the operator expects automated reports (out of scope for this task).
- Whether the "_model" rows structure matches the operator's intent (task description is ambiguous).

---

**Verdict written by GLM, TASK-493.**  
**Branch HEAD SHA reviewed: 2cb8755afc8ad069ccab24a6d80819d779c57e54.**
