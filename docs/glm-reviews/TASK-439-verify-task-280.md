# TASK-439: Independent Verification of TASK-280

**Review Date**: 2026-09-28  
**Reviewer**: GLM (independent verification)  
**Target Branch**: `qwen-worker-4-r9-task280`  
**Target SHA**: `cdffd0a2d3bab2bea4d7a35373876fce93cc97fe`  
**Verified SHA**: `cdffd0a2d3bab2bea4d7a35373876fce93cc97fe` ✓ (branch HEAD matches target)

**Worktree**: `.qwen/worktrees/task439-review` (isolated, detached HEAD at target SHA)

---

## Executive Summary

**DISPOSITION: REWORK**

The artifact exists and is structurally sound, but:
1. Live evidence is absent (0 campaigns walked, 0 provider rows read)
2. Two tests are source-text assertions, not behavioral proof
3. One test is a tautology that proves nothing
4. No integration test drives through the real entry point
5. The branch carries 2,378 lines of scope drift from TASK-308 and TASK-315

The script itself is correct and the core classification logic is testable. The rework is focused on test quality and live validation, not on the implementation.

---

## Finding 1: Artifact Exists and Matches Claims

**Status**: VERIFIED

The three artifacts named in the task file exist on the target ref:
- `scripts/reverse_reconcile.py` (552 lines, new file)
- `tests/test_reverse_reconciliation_is_exhaustive.py` (312 lines, new file)
- `docs/REVERSE-RECONCILIATION-2026-09-25.md` (182 lines, new file)

All three were added in commit `f8787aed` ("TASK-280: the reverse reconciler sweeps backward from provider truth to ledger") and are present at the exact SHA this verdict reviews.

**Evidence**:
```
git log --oneline --all --diff-filter=A -- scripts/reverse_reconcile.py
f8787aed TASK-280: the reverse reconciler sweeps backward from provider truth to ledger
```

The result block claims 25 tests, all passing. Verified: 25 tests run in 0.049s, all pass.

---

## Finding 2: Production Callers - Zero, But Consistent With Existing Pattern

**Status**: VERIFIED, NOT A DEFECT

`grep -rn reverse_reconcile src/ scripts/` returns one hit:
```
scripts/reverse_reconcile.py:483:    prog="reverse_reconcile",
```

The script is a standalone entry point with no production callers in `src/`. This is the same pattern as `reconcile_ledger.py` (the forward reconciler), which also has no callers in `src/`:
```
scripts/reconcile_ledger.py:42:    py -3 scripts/reconcile_ledger.py
scripts/reconcile_ledger.py:43:    py -3 scripts/reconcile_ledger.py --live --by claude
scripts/reconcile_ledger.py:288:    p = argparse.ArgumentParser(prog="reconcile_ledger", description=__doc__)
```

Both are operator tools invoked directly, not library modules imported by production code. This is consistent with the repository's pattern for reconciliation scripts.

**Verdict**: NOT A DEFECT. The task explicitly names this pattern and compares to the forward reconciler. Zero callers is the correct shape for an operator tool.

---

## Finding 3: Key Derivation Is Imported, Not Reimplemented

**Status**: VERIFIED

The script imports `push.push_id` from `src.push`:
```python
from src import push  # noqa: E402 - the key derivation, imported not rebuilt
```

And calls it:
```python
dk = push.push_id(rec, ckey, step_key, "linkedin")
dk = push.push_id(rec, ckey, step_key, "email")
```

The function exists in `src/push.py:37`:
```python
def push_id(rec, contact_key, step_key, channel):
```

And is consumed by production code (11 hits in `src/push.py` alone).

**Caveat**: The tests that verify this (`test_push_is_imported_in_reverse_reconcile` and `test_push_id_is_called`) use `inspect.getsource` to check for the presence of strings in the source text. This is explicitly called out in QWEN.md as NOT accepted as proof:

> "Not accepted as proof: `hasattr`, assertions on source text, a token appearing in a file, proving a function exists"

These tests would pass if the import were present but the function were broken, and would fail if the import were removed but the function still worked. They prove the text is present, not that the behavior is correct.

**Verdict**: The import is real and the function is consumed, but the tests are source-text assertions, not behavioral proof. This is a test quality issue, not an implementation defect.

---

## Finding 4: Live Evidence Is Absent

**Status**: NOT VERIFIED

The result block reports:
```
CAMPAIGNS WALKED / UNREADABLE: 0 / 0
PROVIDER ROWS READ: 0
MATCHED / UNRECORDED / STATE_MISMATCH / NOT_OURS / UNKNOWN: 0/0/0/0/0
```

The task file requires:
> "The sweep runs over **every** bound campaign, and the report says how many campaigns it walked"

And:
> "For at least one `UNRECORDED` row: the provider's own response fields (campaign id, lead id, event type, timestamp) quoted, and the ledger query that returned nothing quoted beside it."

The result block acknowledges this:
> "Live sweep requires production work/ state which is not in this worktree"
> "Live sweep is owed from Claude's worktree"

**Verdict**: NOT VERIFIED. The script is structurally correct but has not been run against live provider data. The task's evidence requirements are not met. This is the most significant gap.

---

## Finding 5: Test Falsifiability - Mixed

**Status**: PARTIALLY VERIFIED

### Good: Behavioral Tests

The `_classify_provider_lead` tests are behavioral. I performed a mutation test:
- Overrode `_classify_provider_lead` to always return "MATCHED"
- Ran `test_no_ledger_rows_is_unrecorded`
- The test failed (as expected)

This proves the test would catch a broken implementation.

The sweep functions (`_sweep_heyreach`, `_sweep_bison`) do call `_classify_provider_lead`, so the classification logic is connected to the entry point.

### Bad: Source-Text Assertions

Two tests use `inspect.getsource` to check for strings in the source:
```python
def test_push_is_imported_in_reverse_reconcile(self):
    import inspect
    source = inspect.getsource(reverse_reconcile)
    self.assertIn("from src import push", source)

def test_push_id_is_called(self):
    import inspect
    source = inspect.getsource(reverse_reconcile)
    self.assertIn("push.push_id", source)
```

These are explicitly forbidden by QWEN.md. They prove the text is present, not that the behavior is correct.

### Bad: Tautological Test

`test_identity_holds_with_lost_row_simulation` claims to simulate a lost row:
```python
def test_identity_holds_with_lost_row_simulation(self):
    """Simulate what happens if a row is lost: the identity breaks."""
    results = [{
        "campaign_id": "c1",
        "heyreach_results": [
            {"classification": "MATCHED"},
            # Imagine a `continue` dropped a row here
        ],
        "bison_results": [],
    }]
    counts = reverse_reconcile._count_classifications(results)
    total = reverse_reconcile._total_provider_rows(results)
    
    classified = sum(v for k, v in counts.items() if k != "UNKNOWN")
    unknown = counts.get("UNKNOWN", 0)
    self.assertEqual(classified + unknown, total)
    
    # But if we HAD read 2 rows and only classified 1, the identity
    # would break. This is what the test guards against:
    actual_provider_rows = 2  # we read 2 rows
    self.assertNotEqual(classified + unknown, actual_provider_rows)
```

This test does NOT simulate a lost row. It constructs a result with 1 row, verifies the identity holds (1 + 0 == 1), then asserts that 1 != 2. This is a tautology - it proves nothing about what happens when a row is actually lost.

A real test would:
1. Construct a scenario where the sweep reads 2 rows
2. Simulate a bug that drops one row (e.g., a `continue` in the loop)
3. Verify the identity breaks (classified + unknown != total)

### Bad: No Integration Test

No test drives through `main()` with mocked provider data. All tests call internal functions directly. This means the wiring between `main()`, `_sweep_campaign()`, `_sweep_heyreach()`, and `_classify_provider_lead()` is not tested.

**Verdict**: PARTIALLY VERIFIED. The core classification logic is testable and the tests would catch a broken implementation. But two tests are source-text assertions, one is a tautology, and there is no integration test.

---

## Finding 6: Merging Would Not Delete Anything

**Status**: VERIFIED

The diff against master shows:
```
13 files changed, 3700 insertions(+), 9 deletions(-)
```

The 9 deletions are:
- 6 lines in task files (moving TASK-280 from TODO to REVIEW)
- 1 line in `tests/base.py` (reformatting to add `ANTHROPIC_API_KEY`)
- 2 lines in `tests/test_invariants.py` (reformatting to add `"anthropic"` to the allowed list)

These are all additive changes or task state transitions. No existing functionality is deleted.

**Verdict**: SAFE TO MERGE (from a deletion perspective).

---

## Finding 7: Scope Drift - Significant

**Status**: VERIFIED

The branch carries work from three tasks:
- TASK-280: reverse reconciler (the target of this review)
- TASK-308: Anthropic provider (676 lines + 328 lines of tests + 120 lines of fixtures)
- TASK-315: cross-channel stop (1254 lines of tests)

Total scope drift: 2,378 lines across 4 files:
```
src/providers/anthropic.py                    |  676 +++++++++++++
tests/fixtures/cassettes/anthropic.json       |  120 +++
tests/test_a_reply_stops_the_other_channel.py | 1254 +++++++++++++++++++++++++
tests/test_anthropic.py                       |  328 +++++++
```

These files are NOT part of TASK-280 and would need to be cherry-picked separately if merged.

**Verdict**: SCOPE DRIFT. The branch carries 2,378 lines of work from other tasks. Merging the entire branch would integrate TASK-308 and TASK-315 without independent review. Only TASK-280's files should be merged:
- `scripts/reverse_reconcile.py`
- `tests/test_reverse_reconciliation_is_exhaustive.py`
- `docs/REVERSE-RECONCILIATION-2026-09-25.md`
- Changes to `tests/test_invariants.py` (adding "anthropic" to allowed list) - but this is TASK-308's change, not TASK-280's
- Changes to `tests/base.py` (adding ANTHROPIC_API_KEY) - also TASK-308's change

TASK-280's actual footprint is 3 new files (1,046 lines total).

---

## Finding 8: ISSUE-025 Analysis - Not Verified

**Status**: NOT VERIFIED

The task requires:
> "The 76-blank-email incident (ISSUE-025): say whether this sweep would have surfaced it, and show the classification it produces for those rows."

The result block says:
> "Would this sweep have caught ISSUE-025's 76 blanks: Yes, in principle. Those leads would classify as UNRECORDED (provider has them, ledger has no ATTEMPTED row). Cannot show live classification from this worktree - campaign bindings are not present. Live sweep is owed from Claude's worktree."

This is a theoretical claim, not a verified one. The sweep has not been run against campaigns 491-498, and no actual classification is shown.

**Verdict**: NOT VERIFIED. The claim is plausible but unproven.

---

## Summary of Findings

| # | Finding | Status | Severity |
|---|---------|--------|----------|
| 1 | Artifact exists and matches claims | VERIFIED | - |
| 2 | Zero production callers, but consistent with pattern | VERIFIED, NOT A DEFECT | - |
| 3 | Key derivation is imported, not reimplemented | VERIFIED (with caveat) | LOW |
| 4 | Live evidence is absent | NOT VERIFIED | HIGH |
| 5 | Test falsifiability is mixed | PARTIALLY VERIFIED | MEDIUM |
| 6 | Merging would not delete anything | VERIFIED | - |
| 7 | Scope drift is significant | VERIFIED | MEDIUM |
| 8 | ISSUE-025 analysis is not verified | NOT VERIFIED | HIGH |

---

## Recommendation: REWORK

The script is structurally correct and the core logic is sound. The rework is focused on:

### Must Fix (HIGH)

1. **Run the live sweep** from Claude's worktree with production state. The task requires:
   - Per-campaign counts from a run against production campaign bindings
   - At least one UNRECORDED row with provider response fields quoted
   - ISSUE-025 classification for campaigns 491-498

2. **Replace source-text assertions** with behavioral tests:
   - `test_push_is_imported_in_reverse_reconcile` and `test_push_id_is_called` should test that the derived keys match what `push.push_id` produces, not that the import statement exists
   - Example: call `_sweep_heyreach` with mocked data and verify the `derived_keys` field matches `push.push_id(rec, ckey, step_key, "linkedin")`

3. **Replace the tautological test** with a real mutation test:
   - `test_identity_holds_with_lost_row_simulation` should construct a scenario where the sweep reads N rows, simulate a bug that drops one, and verify the identity breaks

### Should Fix (MEDIUM)

4. **Add an integration test** that drives through `main()` with mocked provider data and verifies the end-to-end flow

5. **Cherry-pick only TASK-280's files** when merging, not the entire branch. The branch carries 2,378 lines from TASK-308 and TASK-315 that have not been independently reviewed

### Nice to Have (LOW)

6. **Document the operator tool pattern** in a comment or docstring, noting that this is invoked directly like `reconcile_ledger.py` and has no production callers by design

---

## What Would Make This a MERGE

1. Live sweep results with per-campaign counts and at least one UNRECORDED row
2. Behavioral tests for the key derivation (not source-text assertions)
3. A real mutation test for the exhaustiveness identity
4. Confirmation that only TASK-280's files will be merged (not the scope drift)

---

## Appendix: Commands Run

```bash
# Verify target SHA
git rev-parse qwen-worker-4-r9-task280
git rev-parse cdffd0a2d3bab2bea4d7a35373876fce93cc97fe

# Create isolated worktree
git worktree add .qwen/worktrees/task439-review cdffd0a2d3bab2bea4d7a35373876fce93cc97fe --detach

# Check diff against master
git diff master...cdffd0a2d3bab2bea4d7a35373876fce93cc97fe --stat

# Run tests
cd .qwen/worktrees/task439-review
python -m unittest tests.test_reverse_reconciliation_is_exhaustive -v

# Check production callers
git -C .qwen/worktrees/task439-review grep -rn "reverse_reconcile" src/ scripts/

# Verify push.push_id exists
git -C .qwen/worktrees/task439-review grep -rn "push_id" src/push.py

# Mutation test
python -c "..."  # Override _classify_provider_lead to always return MATCHED

# Check for deletions
git diff master...cdffd0a2d3bab2bea4d7a35373876fce93cc97fe --numstat
```

---

**Verdict Author**: GLM (independent reviewer)  
**Verdict Date**: 2026-09-28  
**Target SHA Reviewed**: `cdffd0a2d3bab2bea4d7a35373876fce93cc97fe`  
**Recommendation**: REWORK
