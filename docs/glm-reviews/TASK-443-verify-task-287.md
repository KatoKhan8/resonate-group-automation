# TASK-443 — GLM independent verification of TASK-287

**Reviewed branch:** `qwen-worker-4-r60`
**Reviewed HEAD SHA:** `8d98cb78410bf840958ef88b0d2d2fe220cd3223`
**Branch HEAD confirmed at stated SHA:** YES (`git rev-parse qwen-worker-4-r60` → `8d98cb78`)
**Merge base with master:** `0af11fcb`
**Master HEAD at review time:** `f6979300`
**Review worktree:** `.qwen/worktrees/glm-443` (detached at `8d98cb78`)
**Date:** 2026-09-28

---

## Summary

TASK-287 audited the problem register (`docs/state/PROBLEM-REGISTER.md`) for
duplicate IDs, unsupported status claims, and queue hygiene. It was a
read-only audit task: produce a report, a checker script, and a test. All
three artifacts exist, are correct, and are consumed.

**Disposition: MERGE** — with one merge-time adjustment needed (see Finding 1).

---

## Artifact existence

| Artifact | Exists on branch? | Verified how? |
|----------|-------------------|---------------|
| `docs/REGISTER-HYGIENE-2026-09-25.md` | YES | `git log --diff-filter=A` confirms added; 312 lines read |
| `scripts/register_lint.py` | YES | Added by this branch; 51 lines |
| `tests/test_the_register_has_no_duplicate_ids.py` | YES | Added by this branch; 50 lines |
| Task file in REVIEW/ with result block | YES | `docs/qwen-tasks/REVIEW/TASK-287-four-issue-numbers-were-taken-twice.md` |

All four files are new or modified only by this branch. No forbidden files
touched (`docs/state/PROBLEM-REGISTER.md` is unmodified — verified with
`git diff master...8d98cb78 -- docs/state/PROBLEM-REGISTER.md` → empty).

---

## Claim-by-claim verification

### 1. Register has 44 ISSUE headings

**VERIFIED.** `grep -c "^### ISSUE-" docs/state/PROBLEM-REGISTER.md` → 44.

### 2. Four duplicate IDs detected

**VERIFIED.** Both the script and the test detect exactly:
- ISSUE-006 (2x)
- ISSUE-011 (2x)
- ISSUE-012 (2x)
- ISSUE-016 (2x)

Script exit code: 1. Test result: FAIL with correct assertion message.

### 3. `EveryActorIdIsOneApifyKnows` class does not exist

**VERIFIED.** `grep -r "EveryActorIdIsOneApifyKnows" tests/` → no matches.
The result block's claim is correct: ISSUE-034's register entry names a test
class that does not exist. The file has 21 tests across other classes, all
green.

### 4. ISSUE-002 seal test is RED

**VERIFIED.** `test_enabling_it_moved_nothing_else` fails:
`AssertionError: 16 != 15`. The SUPPORTED set has grown to 16 since the
register's "seal holds at 14 verbs" claim was written.

### 5. Commit SHAs verified

**VERIFIED.** All six SHAs named in the result block as "backed" resolve to
valid commit objects: `0379958d`, `abfc844a`, `7bb23d6d`, `5257adbe`,
`d6a719c2`, `5cd5173d`.

### 6. Named tests pass

**VERIFIED:**
- `test_a_campaign_we_did_not_stop_is_critical` → 12 tests OK
- `test_a_linkedin_stop_is_not_handed_the_email_campaign` → 5 tests OK
- `test_researchpack` → 21 tests OK (but the named class is wrong — see above)

---

## Consumption check (existence ≠ function)

| Artifact | Production caller? | Assessment |
|----------|-------------------|------------|
| `scripts/register_lint.py` | Standalone script | ACCEPTABLE — task asked for "a script or committed command that regenerates the check." It runs with `python scripts/register_lint.py` and exits non-zero on duplicates. |
| `tests/test_the_register_has_no_duplicate_ids.py` | `python -m unittest discover` | CONSUMED — runs in standard discovery path. Verified: it FAILS correctly against the current register. |
| `docs/REGISTER-HYGIENE-2026-09-25.md` | Human-readable audit | ACCEPTABLE — this is the deliverable report. |

The test is a guard: it is SUPPOSED to fail until the renumbering is applied.
This is correct behavior, not a defect.

---

## Deletion check

**No files deleted.** `git diff master...8d98cb78 --diff-filter=D --name-only`
returns empty. The branch only adds files.

---

## Scope drift

**None.** The branch carries exactly 4 changed files:
1. `docs/REGISTER-HYGIENE-2026-09-25.md` — the audit report (ALLOWED)
2. `docs/qwen-tasks/REVIEW/TASK-287-*.md` — task file moved to REVIEW (expected)
3. `scripts/register_lint.py` — the checker (ALLOWED)
4. `tests/test_the_register_has_no_duplicate_ids.py` — the test (ALLOWED)

All within the task's FILES ALLOWED list. No junk, no unrelated changes.

---

## Findings

### Finding 1: Renumbering proposals collide with master (MERGE-TIME ADJUSTMENT)

The branch proposes renumbering the 4 duplicates to ISSUE-046, ISSUE-047,
ISSUE-048, ISSUE-049. Master has already assigned ALL FOUR to different
findings:

| Proposed by branch | Already on master |
|--------------------|-------------------|
| ISSUE-046 (PII guard reopened) | ISSUE-046 (64 emails, different agency pitch) — commit `667cea6b` |
| ISSUE-047 (forward book COVERING) | ISSUE-047 (secondbrain cites unread source) — commit `667cea6b` |
| ISSUE-048 (collision gate) | ISSUE-048 (claims.support_text licenses claim from client CSV) |
| ISSUE-049 (attach_leads recurred) | ISSUE-049 (raw client-CSV headcount crashes qualify.company) |

**Impact:** The audit and its analysis remain valid. The renumbering
proposals need to be updated to ISSUE-050+ before being applied to the
register. This is a merge-time adjustment, not a rework of the audit.

**Severity:** Low — the audit is correct, only the proposed numbers are stale.

### Finding 2: Result block is honest and thorough

The result block correctly identifies:
- 6 fully-backed FIXED rows with commit + test
- 5 partial rows (commit exists, test not as described)
- 5 proposed downgrades (no commit SHA)
- The ISSUE-034 wrong test name
- The ISSUE-002 stale seal count
- The register growth from 39 to 44 rows

No claims are overstated. The audit does what it says it does.

### Finding 3: The test is correctly RED by design

The test fails against the current register because the 4 duplicates still
exist. This is the intended behavior — the test is a guard that will go
green once the renumbering is applied. It is not a broken test.

---

## What would make this a false pass?

I checked for:
- **Editing the register into agreement:** NOT done. The register is unmodified.
- **Accepting status because the row says so:** NOT done. Each status is independently checked.
- **A passing test accepted as PRODUCTION_VERIFIED:** NOT done. PV claims are checked against provider observations.
- **Deleting REFUTED rows:** NOT done. All 6 REFUTED rows are kept.
- **Counting rows instead of listing them:** NOT done. All 44 rows appear in the table.
- **A checker with no caller:** NOT the case. The test is in unittest discover.

None of the false-pass modes apply.

---

## Recommendation

**MERGE** — with one merge-time adjustment:

1. Update the proposed renumbering from ISSUE-046/047/048/049 to ISSUE-050+
   (or whatever the next free numbers are at merge time).
2. Apply the 5 downgrades (ISSUE-020, ISSUE-013, ISSUE-017, ISSUE-024,
   ISSUE-012 collision) from FIXED to CONFIRMED.
3. Correct ISSUE-034's test name and ISSUE-002's seal count.
4. Once renumbered, the test and script will go green.

The audit is thorough, honest, and well-scoped. The checker and test are
correct and consumed. The only issue is that master has moved on and claimed
the proposed numbers — a trivial adjustment.
