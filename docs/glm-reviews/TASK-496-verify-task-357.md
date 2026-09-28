# TASK-496 — Independent verification of TASK-357

**Branch:** `origin/qwen-worker-r69`
**Branch HEAD SHA reviewed:** `a66b6c5bc8a8cdc6f275e45f9702171269021750`
**Verified SHA matches:** `git rev-parse origin/qwen-worker-r69` → `a66b6c5bc8a8cdc6f275e45f9702171269021750` ✓
**Review worktree:** `.qwen/worktrees/review-496` (detached at SHA, now removed)
**Date:** 2026-09-28

Note: the task file said to write to `TASK-496-verify-task-219.md` — that is a template
error. This review covers TASK-357, not TASK-219.

---

## Finding 1 — Artifact exists and the core function works

**Disposition: FIXED (core code correct for the new-record path)**

`src/ingest.py` on the branch adds three new functions:
- `_extract_domain_from_email(email)` — line 272
- `_contact_from_person_row(row)` — line 279
- `run_person_centric(source, client, lane, suppress_path=None)` — line 296

Plus a `--person-centric` CLI flag in `main()` at line 462.

The diff is purely additive to `src/ingest.py`: +203 lines, 0 deleted. The existing
`run()` function is untouched.

The test file `tests/test_a_person_centric_csv_becomes_one_record_per_company.py` is
new: +363 lines, 18 test methods across 8 test classes.

**Verified:** All 18 new tests pass. All 18 existing `test_ingest.py` tests pass
(no regression). 36/36 green in 0.65s.

**Evidence:**
```
$ python -m unittest tests.test_a_person_centric_csv_becomes_one_record_per_company -v
Ran 18 tests in 0.405s — OK

$ python -m unittest tests.test_ingest -v
Ran 18 tests in 0.246s — OK
```

---

## Finding 2 — Production caller chain

**Disposition: FIXED (consumed via CLI)**

```
grep -n "run_person_centric" src/ingest.py:
  296: def run_person_centric(...)       ← definition
  469:     result = run_person_centric(...)  ← called from main() with --person-centric flag
```

The function is consumed via the CLI entrypoint `python -m src.ingest --person-centric`.
This is the correct pattern for an import tool — it is not called from background
processes or other modules, and that is appropriate for its purpose.

The helper functions `_extract_domain_from_email` and `_contact_from_person_row` are
called from within `run_person_centric` at lines 332 and 360 respectively.

`identity.assign_keys()` (imported lazily at line 306) exists and is confirmed callable.

**NOT DISCONNECTED.** The chain is consumed.

---

## Finding 3 — Falsification: grouping works, old behavior would lose contacts

**Disposition: FIXED (tests are meaningful)**

**Manual mutation test performed:** I replaced `run_person_centric` with a broken
version that deduplicates by domain (keeping only the first row per domain — the old
behavior). Against 3 people at one domain:

- Broken version: 1 contact attached (only the first person)
- New version: 3 contacts attached (all three)
- Key assertion `contacts_attached == 3`: **FAILS** under the broken version ✓

The mutation confirms: if the grouping code were reverted, the test would fail for
the intended reason (lost contacts), not because of an unrelated guard.

**Note on acceptance criterion 5:** The task asked to "revert the domain grouping so
it dedups by domain and drops, confirm the test FAILS naming the dropped contacts,
restore." The branch's `TestGuardIsSeenToFail` does NOT do this — it asserts the new
behavior positively and simulates the old behavior in a separate test with inline data.
This is a logical proof rather than a code mutation, but my independent mutation test
confirms the conclusion is correct.

---

## Finding 4 — Tests are falsifiable

**Disposition: FIXED (tests assert behavior, not text)**

| Test | What it asserts | Could pass with wrong code? |
|------|----------------|-----------------------------|
| `test_three_people_at_one_domain...` | 3 people → 1 record, 3 contacts | No — asserts record count AND contact count |
| `test_two_domains_become_two_records` | 2 domains → 2 records | No — asserts domain values |
| `test_contact_carries_...` | Each field on the contact dict | No — asserts exact values per field |
| `test_arithmetic_balances` | rows_in == contacts + skipped | No — asserts the return value |
| `test_importing_twice_...` | Second import: 0 new, all skipped | No — asserts idempotency |
| `test_suppressed_domain_is_skipped` | 0 contacts, 1 skip, "suppressed" in reason | No — asserts skip reason text |
| `test_no_record_is_deleted` | Existing record survives import | No — asserts count before/after |
| `test_store_is_the_only_writer` | Records validate against schema | No — calls `store.validate()` |

No `hasattr`, no source-text assertions, no fake cassettes. Tests drive through
`run_person_centric()` (the real entry point) and assert on `store.load()` (the real
output).

---

## Finding 5 — Accounting bug for existing-record path

**Disposition: DEFECT — `contacts_attached` miscounts when updating existing records**

When `run_person_centric` adds contacts to an existing record (domain already in queue),
`contact_counts` is set to `len(rec["contacts"])` — the TOTAL contacts on the record
after the update, not just the newly added ones.

**Reproduced:**
```
Phase 1: import 2 people at acme.test (new record)
  → rows_in=2, contacts_attached=2, arithmetic_ok=True ✓

Phase 2: import 2 MORE people at acme.test (existing record, 2 contacts)
  → rows_in=2, contacts_attached=4, skipped=0, arithmetic_ok=False ✗
  (2 ≠ 4 + 0)
```

The record correctly has 4 contacts (2 pre-existing + 2 new). The contacts ARE attached.
But `contacts_attached` reports 4 when only 2 were newly added, and `arithmetic_ok`
falsely reports failure.

**Root cause:** Line in `run_person_centric`:
```python
contact_counts.append(len(rec["contacts"]))  # TOTAL, not newly added
```
Should be tracking the `added` count for updated records, not the total.

**Test gap:** `TestExistingRecordGetsNewContacts.test_new_contacts_added_to_existing_record`
asserts on `store.load()` (correct: 2 contacts on the record) but does NOT assert on
`result["contacts_attached"]` or `result["arithmetic_ok"]`. The bug is invisible to the
test suite.

**Severity:** The import itself works correctly — contacts are attached, records are
saved, idempotency holds. Only the summary accounting is wrong. For the real import
(TASK-347), this would produce misleading progress reports when adding contacts to
pre-existing records.

---

## Finding 6 — Scope drift: branch deletes unrelated TASK-345

**Disposition: REWORK required (cherry-pick must exclude this)**

```
git diff master...a66b6c5b --name-status -- docs/qwen-tasks/:
  R052  TODO/TASK-357-...  →  REVIEW/TASK-357-...   ← expected (task moved to REVIEW)
  D     TODO/TASK-345-glm-verifies-a-finished-branch-before-claude-picksit.md  ← SCOPE DRIFT
```

The branch deletes `docs/qwen-tasks/TODO/TASK-345-...` which EXISTS on master and is
completely unrelated to TASK-357. Merging this branch as-is would delete TASK-345 from
the queue.

**Cherry-pick scope:** To merge safely, cherry-pick only:
1. `src/ingest.py` (modified — additive, safe)
2. `tests/test_a_person_centric_csv_becomes_one_record_per_company.py` (new)
3. `docs/qwen-tasks/REVIEW/TASK-357-...` (new — task moved to REVIEW)
4. `docs/qwen-tasks/TODO/TASK-357-...` (deleted — task moved to REVIEW)

Do NOT take the deletion of `docs/qwen-tasks/TODO/TASK-345-...`.

---

## Finding 7 — Would merging delete anything from master?

Beyond the TASK-345 scope drift (Finding 6), no. The diff is:
- `src/ingest.py`: +203 lines, 0 deleted — purely additive
- Test file: new, +363 lines
- Task file: rename TODO → REVIEW (expected workflow)

No master code, config, or documentation is modified or removed (except TASK-345).

---

## Finding 8 — Conflict markers

**Disposition: CLEAN**

```
grep -c "^<<<<<<< \|^======= $\|^>>>>>>> " src/ingest.py → 0
```

No conflict markers in any changed file.

---

## Summary

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | Artifact exists, core function works | — | Verified |
| 2 | Production caller chain | — | Consumed via CLI |
| 3 | Falsification: grouping works | — | Mutation confirms |
| 4 | Tests are falsifiable | — | Behavior-asserting |
| 5 | `contacts_attached` miscounts for existing records | Medium | DEFECT |
| 6 | Branch deletes unrelated TASK-345 | Medium | SCOPE DRIFT |
| 7 | No master deletion (beyond TASK-345) | — | Clean |
| 8 | No conflict markers | — | Clean |

---

## Recommendation: **REWORK**

Two issues must be fixed before merge:

1. **Accounting bug (Finding 5):** `contacts_attached` must count only newly added
   contacts for existing records, not the total after update. The fix is to track the
   `added` count (already computed in the loop) instead of `len(rec["contacts"])` for
   the update path. Add a test that imports to an existing record and asserts
   `arithmetic_ok` is True.

2. **Scope drift (Finding 6):** The deletion of TASK-345 must be excluded from the
   merge. Cherry-pick the four relevant files, not the branch as a whole.

Both are small fixes. The core implementation — domain grouping, contact extraction,
suppression, idempotency, key assignment — is correct and well-tested. The 18 tests
are meaningful (mutation-confirmed) and drive through the real entry point.
