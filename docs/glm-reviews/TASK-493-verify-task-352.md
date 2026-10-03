# TASK-493 — GLM independent verification of TASK-352

## Target

    task            TASK-352
    branch          origin/qwen-worker-4-r9
    branch HEAD SHA 2cb8755afc8ad069ccab24a6d80819d779c57e54

**SHA verified:** `git rev-parse origin/qwen-worker-4-r9` returned `2cb8755afc8ad069ccab24a6d80819d779c57e54`. The branch has not moved.

**Review performed on:** An isolated worktree checked out at `2cb8755afc8ad069ccab24a6d80819d779c57e54` (detached HEAD). Not master, not the branch name.

**Note:** The task file says to write the verdict to `TASK-493-verify-task-219.md` — this is a copy-paste error from TASK-431. The correct target is TASK-352.

---

## 1. Does the artifact exist on this ref?

**YES.** Both artifacts exist at the exact SHA:

- `scripts/spend_report.py` — 334 lines, added in commit `84129e4ea`
- `tests/test_the_spend_report_never_sums_two_units.py` — 305 lines, added in the same commit

**Verified with:** `git log --diff-filter=A --all -- scripts/spend_report.py` → commit `84129e4ea7cc76b83d68b1575db3fd3bb08819b9` ("TASK-352: the spend report the operator can act on").

---

## 2. Does it do what the result block claims?

**YES, with one cosmetic defect.**

### Acceptance criteria re-verified

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | Mixed-unit client gets the tripwire, not a summed integer | **PASS** | Test `test_mixed_units_emit_tripwire_not_summed_integer` asserts `"MIXED UNITS - a tripwire, not an amount"` is present AND `"547"` (the wrong sum) is absent. Independently reproduced: recording 100 credits + 447 cents produces `mixed_units: True`, tripwire present, 547 absent. |
| 2 | All three cost-per-lead denominators appear, labelled | **PASS** | Test `test_all_three_denominators_appear_labelled` asserts all three keys exist, checks exact counts (5 cohort, 3 written, 2 approved from 5 records), and verifies every data line with "$" mentions a specific denominator. |
| 3 | Unpriced provider reports null, not zero or a guess | **PASS** | Test `test_credits_unpriced_reports_null` asserts `usd_estimate is None` and `rate_source == "unknown"`. Independently verified: `spendledger.usd_estimate(500, "credits")` → `(None, None, "unknown")`. |
| 4 | Unattributed `_model` rows reported separately with count | **PASS** | Test `test_model_rows_reported_separately` asserts count=2 and total_cost=3840 for two `_model` rows. |
| 5 | Read-only: ledger byte-identical before and after | **PASS** | Test `test_ledger_unchanged_after_report` reads the ledger as bytes before and after `generate_report()` and asserts equality. |
| 6 | Cost-per-lead calculation correct on all three denominators | **PASS** | Test `test_cost_per_lead_on_three_denominators` uses 50 leads, $3.1464 total, asserts $0.062928 / $0.101497 / $0.242031 — matching the task's 6.29c / 10.15c / 24.20c. |

### All tests pass

```
Ran 7 tests in 0.100s — OK
```

The 15 existing ledger tests (`tests/test_ledger_does_not_sum_across_units`) also pass alongside the 7 new ones (22 total, all green).

---

## 3. Existence is not function — does it have a production caller?

**The script is a CLI endpoint, not a pipeline component.** `grep -rn "spend_report" src/` returns zero hits. No `src/` module imports it. The only importer is the test file.

**However, this is intentional.** The task explicitly asks for "a spend report the operator can act on." The acceptance criterion is `py -3 scripts/spend_report.py --client productive` — the operator running it from the command line. The operator IS the consumer. This is not the "computed correctly but nothing reads it" defect (TASK-029, TASK-028, TASK-019 pattern) because the script is the endpoint, not a middleware function that production should call.

**Verdict: NOT DISCONNECTED.** A CLI script invoked by the operator is a valid consumption pattern. This is the same pattern as `scripts/qa/check_reconcile.py` (TASK-299) and `scripts/qa/check_campaign_heyreach.py` (TASK-297), both of which were merged as READS ONLY CLI tools.

---

## 4. Are the tests falsifiable?

**YES.** The tests assert on behavior, not source text:

- The mixed-unit test asserts on the **formatted output string** and the **absence of a wrong sum** — not on `hasattr` or source inspection.
- The denominator test asserts on **exact integer counts** from a fixture queue — not on the existence of keys.
- The unpriced test asserts `assertIsNone` — not `assertIsNotNone` or a truthy check.
- The read-only test asserts **byte-identity** of the ledger file — not that no write function was called.

**Mutation test performed:** Setting `block["mixed_units"] = False` manually is caught by `self.assertTrue(block["mixed_units"])`. The test would fail for the intended reason.

**How could these pass while the implementation is wrong?**
- If the tripwire string changed, test 1 would fail.
- If a denominator were missing or mislabelled, test 2 would fail.
- If credits got a rate, test 3 would fail.
- If `_model` rows were dropped or merged, test 4 would fail.
- If the report wrote to the ledger, test 5 would fail.
- If the math were wrong, test 6 would fail.

I cannot construct a scenario where all seven pass with a broken implementation.

---

## 5. Would merging it DELETE anything?

**NO.** The diff `master...2cb8755afc8ad069ccab24a6d80819d779c57e54 -- src/ scripts/ tests/` shows:

```
scripts/spend_report.py                            | 334 ++++++++++
tests/test_the_spend_report_never_sums_two_units.py | 305 ++++++++++
2 files changed, 639 insertions(+)
```

Two new files, zero modifications, zero deletions. Clean.

---

## 6. Scope drift

**SIGNIFICANT.** The full branch diff against master carries 24 files:

- **TASK-352's work (3 files):** `scripts/spend_report.py`, `tests/test_the_spend_report_never_sums_two_units.py`, and the task file movement from TODO to REVIEW.
- **16 GLM verification task files** (TASK-431 through TASK-446) — all in TODO, all dispatching verdicts for other tasks.
- **TASK-430** — a real task file in TODO.
- **TASK-438** — a GLM verdict file and its movement to DONE.
- **`docs/OPERATING-MODE.md`** — modified (61 lines added).
- **`docs/BRIEF-dry-run-executes-the-safety-path.md`** — new (123 lines).

**Cherry-pick scope for TASK-352:** Only the two code files and the task file movement. The remaining 21 files are pollution for this specific merge and belong to other tasks/verdicts.

---

## 7. Findings

### Finding A: Label bug in formatted output (MINOR, COSMETIC)

**Location:** `scripts/spend_report.py`, line in `format_report()`:
```python
lines.append(f"  written leads (state='pushed'):  {lc['written_leads']}")
```

**Defect:** The label says `state='pushed'` but the code counts `{"drafted", "approved", "pushed"}` — three states, not just "pushed". The formatted output misleads the operator about what "written" means.

**Evidence:** Running the report with 50 leads (13 approved, 18 drafted, 19 queued) produces:
```
  written leads (state='pushed'):  31
```
But 31 = 13 approved + 18 drafted, not just "pushed" state.

**The result block is correct:** It says "written leads: records in states `drafted`, `approved`, or `pushed` (passed first gate: copylint)". The code implements this correctly. Only the formatted label is wrong.

**The docstring is also wrong:** Line 17 says "per WRITTEN lead (leads that reached 'pushed' state)" — same error.

**Fix:** Change the label to `written leads (drafted/approved/pushed):` or similar. Change the docstring to match the result block.

**Severity:** Minor. The data is correct; only the display label is misleading. Does not block the merge but should be fixed before the operator runs it against the live ledger.

### Finding B: Unused import (MINOR, COSMETIC)

**Location:** `scripts/spend_report.py`, line 44:
```python
from src import clients, spendledger, store  # noqa: E402
```

**Defect:** `clients` is imported but never used anywhere in the script.

**Fix:** Remove `clients` from the import.

**Severity:** Cosmetic. No functional impact.

---

## 8. Disposition

| Finding | Severity | Disposition |
|---------|----------|-------------|
| A: Label bug | Minor | FIX BEFORE MERGE or ACCEPT DEFERRED |
| B: Unused import | Cosmetic | FIX BEFORE MERGE or ACCEPT DEFERRED |

**Both findings are cosmetic.** The data, logic, and tests are correct. The label bug could confuse the operator but does not produce wrong numbers.

---

## 9. Recommendation

**MERGE** with minor findings.

**Rationale:**
1. The artifact exists and does what the result block claims.
2. All 7 tests pass and are falsifiable.
3. The 15 existing ledger tests also pass (22 total, all green).
4. No deletion risk — only two new files added.
5. The script is a CLI endpoint, not a disconnected module.
6. The two findings are cosmetic and do not affect correctness.

**Cherry-pick instructions:**
- Take only `scripts/spend_report.py`, `tests/test_the_spend_report_never_sums_two_units.py`, and the task file movement (`docs/qwen-tasks/TODO/TASK-352-*` → `docs/qwen-tasks/REVIEW/TASK-352-*`).
- Do NOT take the 16 GLM verification task files, TASK-430, TASK-438, OPERATING-MODE changes, or the dry-run brief — those belong to other tasks.

**Optional pre-merge fix:**
- Correct the label in `format_report()` from `state='pushed'` to `drafted/approved/pushed` or similar.
- Correct the docstring from "leads that reached 'pushed' state" to "leads that passed the first gate (drafted, approved, or pushed)".
- Remove the unused `clients` import.

These fixes are minor and could be done by Claude during integration, or deferred to a follow-up task.

---

## 10. What I could not verify

- **Live run against the real ledger:** The task's acceptance criterion 1 says "The report runs against the real ledger and prints per-provider, per-unit figures: `py -3 scripts/spend_report.py --client productive`". I did not run this because it requires `work/queue.jsonl` and the live spend ledger, which are not present in this worktree. The tests use fixtures and pass, but the live run is **NOT VERIFIED**.
- **Operator usability:** I did not evaluate whether the report's format is actually useful to the operator beyond the acceptance criteria. That is a product decision, not a code review.

---

## 11. Reproducible commands

All commands were run in an isolated worktree at `2cb8755afc8ad069ccab24a6d80819d779c57e54`:

```bash
# Verify the SHA
git rev-parse origin/qwen-worker-4-r9

# Run the tests
py -3 -m unittest tests.test_the_spend_report_never_sums_two_units -v

# Run the existing ledger tests
py -3 -m unittest tests.test_ledger_does_not_sum_across_units -v

# Check the diff
git diff master...2cb8755afc8ad069ccab24a6d80819d779c57e54 --stat -- src/ scripts/ tests/

# Verify the label bug
py -3 -c "
import sys, os, tempfile, shutil, json
sys.path.insert(0, '.')
from src import spendledger, store
from scripts import spend_report
tmp = tempfile.mkdtemp()
store.use_directory(tmp)
spendledger.record('acme', 'anthropic', 'sonnet', 3_146_400, unit='microusd')
queue_path = os.path.join(tmp, 'queue.jsonl')
with open(queue_path, 'w') as fh:
    for i in range(50):
        state = 'approved' if i < 13 else ('drafted' if i < 31 else 'queued')
        fh.write(json.dumps({'id': f'rec-{i}', 'client': 'acme', 'state': state}) + '\n')
report = spend_report.generate_report(client='acme')
formatted = spend_report.format_report(report)
for line in formatted.split('\n'):
    if 'written leads' in line.lower():
        print('LABEL:', repr(line))
shutil.rmtree(tmp, ignore_errors=True)
"
```

---

**Verdict date:** 2026-10-03
**Reviewer:** GLM (TASK-493)
**Target:** TASK-352 @ `2cb8755afc8ad069ccab24a6d80819d779c57e54`
**Recommendation:** MERGE with minor cosmetic findings
