# TASK-438 — GLM independent verification of TASK-272

**VERDICT: REWORK**

## Review metadata

    Reviewed branch     qwen-worker-12-r9
    Reviewed SHA        c5a756d27a730c0ce6f8dc764444b9c92d2ecdef
    Branch moved?       YES — branch now points to 243c00b3, not the target SHA.
                        Reviewing c5a756d2 per task instruction.
    Review worktree     This session (qwen-worker-4-r9), read-only against target SHA
    Start master SHA    13a64166 (current master at review time)
    Reviewer            TASK-438 (GLM independent verification)
    Date                2026-09-27

## What TASK-272 claims

Explainable verdicts: fix ISSUE-019/ISSUE-023 by ensuring a row with no positive
evidence produces NO reason string, not the tautology "scored above threshold".
Add "why it matched" column to `clientexport` (7 columns, not 6). Stamp `_icp_why`
on qualified rows in `qualify_sourced_supply.py`. 13 new tests.

## 1. Does the artifact exist?

**YES.** All four code changes are present at `c5a756d2`:

| File | Change | Present |
|------|--------|---------|
| `src/nightlysourcing.py:383-393` | `_icp_evidence_text` returns `""` not `"scored above threshold"` | ✅ |
| `src/clientexport.py:42-43,89-125` | `EXPORT_COLUMNS` has 7 entries; `_row_for` includes `"why it matched"`; `_evidence_text` helper added | ✅ |
| `scripts/qualify_sourced_supply.py:51-63,158` | `_evidence_text` helper added; `row["_icp_why"]` stamped on qualified rows | ✅ |
| `tests/test_explainable_verdicts.py` | 190-line test file with 13 tests | ✅ |
| `tests/test_client_export_and_s1_suppression.py` | Updated to expect 7 columns | ✅ |

## 2. Existence is not function — are the links consumed?

**YES.** All three evidence-text functions have real production callers:

- `nightlysourcing._icp_evidence_text` → called at `nightlysourcing.py:355`
  (`company["_icp_why"] = _icp_evidence_text(verdict)`), which flows into
  `candidateexport` via `_to_candidate` at line 512 (`"why_matched": company.get("_icp_why", "")`).
  **Consumed.**

- `clientexport._evidence_text` → called at `clientexport.py:100` inside `_row_for`,
  which is called by `build_candidate_list` at line 182, which is called by
  `scripts/client_snapshot.py:186`. **Consumed.**

- `qualify_sourced_supply._evidence_text` → called at line 158
  (`row["_icp_why"] = _evidence_text(verdict)`). **Consumed** (script output).

- `clientexport.EXPORT_COLUMNS` → consumed by `src/clients.py:490-492` (default
  column list for client config) and by `clientexport.py:202-205` (CSV header and
  row construction). **Consumed.**

No zero-consumer components in the TASK-272 scope.

## 3. Falsification of the result's own claims

### 3.1 The core fix: "scored above threshold" is gone

**CONFIRMED.** `nightlysourcing._icp_evidence_text` at `c5a756d2`:

```python
return "; ".join(parts[:3]) if parts else ""
```

Master at the same location:

```python
return "; ".join(parts[:3]) if parts else "scored above threshold"
```

The tautology is removed. A verdict with empty `positive_signals` now produces
an empty string, not a pass-shaped sentence.

### 3.2 The bank/telecom case

**CONFIRMED.** The test constructs a 130,377-employee bank scoring 0.0 and
asserts the evidence text does not contain "scored above threshold". With the
fix, it returns `""`. The defect is not reachable.

### 3.3 Two tests are conditional and do NOT unconditionally falsify

**FINDING.** `test_zero_score_produces_empty_reason_in_nightlysourcing` and
`test_zero_score_produces_empty_reason_in_clientexport` both guard their
assertion with `if verdict["icp_score"] <= 0:`. If the test company ("Nothing",
50000 employees, banking, United States) ever scores above 0.0 under the
PRODUCTIVE config, the test passes vacuously — it asserts nothing.

The DIRECT tests (`test_empty_positive_signals_produce_empty_reason`,
`test_no_tautology_in_evidence_text`) are properly unconditional and DO
falsify the claim. The conditional tests are weaker than they appear but do
not mask a defect.

**Severity:** Low. The unconditional tests cover the fix. The conditional tests
are misleading but not harmful.

### 3.4 "candidateexport's existing column is unchanged"

**CONFIRMED.** `candidateexport.EXPORT_COLUMNS` and `candidateexport.FIELD_MAP`
are not modified by this branch. The two tests asserting this pass trivially.

## 4. Test falsifiability — how could these pass while the implementation is wrong?

**Mostly falsifiable.** The direct tests (`test_empty_positive_signals_*`,
`test_no_tautology_in_evidence_text`, `test_row_for_includes_why_it_matched`)
would all fail if the fix were reverted. They test behaviour, not source text.

**Weakness:** No test verifies that `_row_for` produces an EMPTY `"why it matched"`
when the verdict has no positive signals. The test `test_row_for_includes_why_it_matched`
only tests the positive case (a verdict WITH signals). A regression where `_row_for`
fell back to a hardcoded string for empty verdicts would pass all existing tests.

**Not accepted as proof:** None of the tests use `hasattr`, source-text assertions,
or token-in-file checks. All test runtime behaviour through function calls. This
is correct.

## 5. Would merging delete anything?

**No content deletion.** The diff deletes 6 files, all of which are task state
transitions (TODO→REVIEW, TODO→DONE, DONE→BLOCKED):

| Deleted from TODO | Exists at c5a756d2 in |
|---|---|
| `TASK-405-glm-verify-task-394.md` | `REVIEW/` (moved) |
| `TASK-409-glm-verify-task-294.md` | `REVIEW/` (moved) |
| `TASK-415-sender-inventory-drift-check.md` | `BLOCKED/` (moved) |
| `TASK-417-campaign-cadence-drift-check.md` | `DONE/` (moved) |
| `TASK-418-offer-config-consistency-check.md` | `REVIEW/` (moved) |
| Doc file (renamed) | `REVIEW/` under new name |

No source code, config, or test files are deleted. The task-file moves are
legitimate state transitions but are NOT part of TASK-272's scope.

## 6. Scope drift

**SIGNIFICANT.** The branch carries 37 changed files; TASK-272 accounts for 5.
The remaining 32 files are from other tasks and other work:

### Non-TASK-272 source changes (must NOT be cherry-picked with TASK-272):

| File | From task | Nature |
|------|-----------|--------|
| `src/ingest.py` (+265/-lines) | TASK-311 | LinkedIn URL + operational column preservation |
| `scripts/claim_task.py` (+177/-lines) | TASK-424+ | Terminal branch stages, cache schema |
| `config/clients/productive-offers.yaml` (+79/-lines) | Other | Capability name fix, ai_capabilities format |
| `src/notify.py` (+31/-lines) | Other | ops_channel fallback logic |
| `scripts/task397_heyreach_seat_cap_check.py` (+206) | TASK-397 | New script |
| `tests/test_claim_task_readiness_is_not_inferred.py` (+412) | Other | New test file |
| `tests/test_ingest_carries_linkedin.py` (+193) | TASK-311 | New test file |
| `tests/test_claim_task.py` (+52/-lines) | TASK-424+ | Extended tests |
| `tests/test_no_route_resolves_to_retired_channel.py` (+14) | Other | New test |
| `docs/SUITE-TRIAGE-2026-09-27.md` (+306) | Other | Triage doc |
| `docs/TASK-STATE-REGISTRY-DESIGN.md` (+389) | TASK-424 | Design doc |
| `docs/OPERATING-MODE.md` (+13) | Other | Doc update |
| Various task files in REVIEW/DONE/BLOCKED/TODO | Various | State transitions |

**Cherry-pick scope for TASK-272 only:**

    src/nightlysourcing.py          (1 hunk: _icp_evidence_text fix)
    src/clientexport.py             (3 hunks: EXPORT_COLUMNS, _row_for, _evidence_text)
    scripts/qualify_sourced_supply.py (2 hunks: _evidence_text, _icp_why stamp)
    tests/test_explainable_verdicts.py (new file)
    tests/test_client_export_and_s1_suppression.py (1 hunk: 6→7 columns)

## 7. Issues found

### ISSUE 1: Three copies of the same function (Suggestion)

`_evidence_text` / `_icp_evidence_text` is implemented identically in three places:

    src/nightlysourcing.py:383      _icp_evidence_text(verdict)
    src/clientexport.py:112         _evidence_text(verdict)
    scripts/qualify_sourced_supply.py:51  _evidence_text(verdict)

The task spec said "Reuse that chain; do not write a second reason generator."
The implementation wrote three. The function body is 6 lines, so this is not
dangerous, but a future change to the evidence assembly logic must now be made
in three places or the outputs diverge.

**Disposition:** Suggestion. Not a safety defect. All three are consumed.

### ISSUE 2: Module docstring not updated (Suggestion)

`clientexport.py` module docstring lines 8-9 still read:

    "Write a CSV with exactly: domain, company, headcount, industry,
     country, website."

The export now has 7 columns. The docstring says "exactly" six. This is
wrong and will mislead the next reader.

**Disposition:** Suggestion. Cosmetic but the docstring uses the word "exactly".

### ISSUE 3: `_row_for` does not reuse `nightlysourcing`'s stored `_icp_why` (Informational)

`nightlysourcing.py:355` stores `company["_icp_why"] = _icp_evidence_text(verdict)`
on the record. `clientexport._row_for` could read `rec.get("qualification", {}).get("verdict", {})`
and recompute, which is what it does — but it does NOT read the stored `_icp_why`.
Both paths read the same verdict, so the output is consistent, but the stored value
is unused by the export. This is not a defect but it means the "reuse the chain"
instruction was interpreted as "reuse the logic" (copy the function) rather than
"reuse the stored value" (read the field).

**Disposition:** Informational. Consistent today; fragile if the logic diverges.

## 8. Dispositions

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | Core fix correct: "scored above threshold" removed | — | CONFIRMED |
| 2 | Production callers exist for all three functions | — | CONFIRMED |
| 3 | Three copies of _evidence_text | Suggestion | EXISTING TASK — consolidate if the logic evolves |
| 4 | Module docstring says "exactly" 6 columns, now 7 | Suggestion | EXISTING TASK — update docstring |
| 5 | Two conditional tests may pass vacuously | Low | ACCEPTED DEFERRED RISK — unconditional tests cover the fix |
| 6 | No test for empty-reason path through _row_for | Suggestion | EXISTING TASK — add negative test |
| 7 | Significant scope drift (32 non-TASK-272 files) | — | Cherry-pick required; do not merge the branch wholesale |

## Recommendation

**REWORK — minor.** The core fix is correct, the chain is consumed, and the tests
are mostly falsifiable. The issues are:

1. **Must fix before merge:** Update the module docstring in `clientexport.py`
   to say 7 columns. The word "exactly" in a docstring that is wrong is a
   future confusion.

2. **Should fix before merge:** Add one test: `_row_for` with a verdict that
   has empty `positive_signals` produces `"why it matched": ""`. This closes
   the only untested path.

3. **Nice to have:** Consolidate the three `_evidence_text` copies into one.
   Not blocking — the function is 6 lines and all three are consumed.

4. **Cherry-pick, do not merge the branch.** 32 of 37 changed files are from
   other tasks. The TASK-272 cherry-pick is 5 files with 4 small hunks.

**What Claude should cherry-pick:**

    src/nightlysourcing.py           — _icp_evidence_text fix (1 hunk)
    src/clientexport.py              — EXPORT_COLUMNS + _row_for + _evidence_text
    scripts/qualify_sourced_supply.py — _evidence_text + _icp_why stamp
    tests/test_explainable_verdicts.py — new file (whole)
    tests/test_client_export_and_s1_suppression.py — 6→7 columns (1 hunk)
