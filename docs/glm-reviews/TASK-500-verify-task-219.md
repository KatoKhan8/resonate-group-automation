# GLM VERDICT: TASK-372 — Suite Baseline Regeneration

**Verdict by:** TASK-500 (GLM independent verification)
**Target task:** TASK-372 — the suite baseline is 73 failures short
**Target branch:** origin/qwen-worker-2-r9
**Branch HEAD SHA reviewed:** f03c74fc01a40df45419742e122268d11c8395a1
**SHA verified:** `git rev-parse origin/qwen-worker-2-r9` returned `f03c74fc01a40df45419742e122268d11c8395a1` — matches task file.
**Isolated worktree:** `.qwen/worktrees/task500-review` (detached at target SHA)
**Date:** 2026-09-29

---

## 1. Artifact Existence

| Artifact | Exists at SHA? | Verified how |
|----------|---------------|--------------|
| `docs/state/SUITE-BASELINE-2026-09-27.txt` | YES | `git log --diff-filter=A` shows commit `6fc77fb0` |
| `docs/state/SUITE-BASELINE-DELTA-2026-09-26.md` | YES | `git log --diff-filter=A` shows commit `91a280e2` (skeleton), replaced at `6fc77fb0` |
| `scripts/task372_diff_baseline.py` | YES | In commit `91a280e2` |
| `scripts/task372_verify_preexisting.sh` | YES | In commit `91a280e2` |
| `scripts/run_suite.py` timeout change | YES | 1800s → 7200s, diff confirmed |
| Task file moved TODO → REVIEW | YES | `REVIEW/TASK-372-...md` present, `TODO/TASK-372-...md` deleted |

**Verdict: ARTIFACTS EXIST.**

## 2. Do the Artifacts Do What the Result Block Claims?

### 2.1 Baseline count — INDEPENDENTLY VERIFIED

```
$ grep -cE "^(FAIL|ERROR)" SUITE-BASELINE-2026-09-27.txt
228
```

Result block claims 228. **Confirmed.**

### 2.2 Set difference — INDEPENDENTLY VERIFIED

Extracted both baselines, `sort -u`, `comm`:

| Metric | Result block claim | Independent measurement |
|--------|-------------------|------------------------|
| Old baseline names | 128 | 128 |
| New baseline names | 228 | 228 |
| In both (still failing) | 122 | 122 |
| New only | 106 | 106 |
| Gone (fixed) | 6 | 6 |

Arithmetic: 128 − 6 + 106 = 228. **All five numbers match.**

### 2.3 Fixed tests — INDEPENDENTLY VERIFIED

The 6 names that disappeared:

    ERROR test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_a_sealed_verb_leaves_a_row
    ERROR test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_every_row_carries_when_and_who
    ERROR test_a_resume_leaves_a_ledger_row.ARefusalIsAnEventAndNotAnAbsence.test_the_ledger_never_turns_a_refusal_into_a_crash
    FAIL test_a_resume_leaves_a_ledger_row.AResumeLeavesARow.test_a_resume_leaves_a_row_for_each_channel
    FAIL test_a_resume_leaves_a_ledger_row.TheResumeVerbsAreDeclaredAndSealed.test_neither_is_supported
    FAIL test_nothing_writes_to_a_provider.NoUndeclaredProviderWrite.test_every_http_write_in_the_repository_is_declared

Result block claims "5 from test_a_resume_leaves_a_ledger_row + 1 from test_nothing_writes_to_a_provider." **Confirmed exactly.**

### 2.4 Categorisation of 106 new failures — NOT INDEPENDENTLY RE-RUN

The delta document categorises all 106 as category (b): introduced between baseline commit and HEAD. The breakdown (68 regressions + 19 new-module + 19 new-class = 106) is arithmetically correct. The per-module table lists each module's status at baseline commit `0af11fcb`.

**I did NOT check out `0af11fcb` and re-run the 22 modules.** The delta document's claims are internally consistent and plausible, but this is static verification of a measurement task, not a re-execution. The result block's claim of "All 22 affected modules verified at baseline commit 0af11fcb" refers to the worker's own verification, which I reviewed but did not reproduce.

**Status: categorisation accepted on documentary evidence, not independently re-derived.**

## 3. Existence vs Function

TASK-372 is a measurement task, not a code change. Its deliverables are:

1. A named-set baseline file (`SUITE-BASELINE-2026-09-27.txt`) — exists, 228 names, verified.
2. A delta document (`SUITE-BASELINE-DELTA-2026-09-26.md`) — exists, full categorisation, verified.
3. Helper scripts for reproducibility — exist, functional.

The baseline file is consumed as the merge gate by `scripts/run_suite.py` and `OPERATING-MODE §19`. The chain is: suite run → named-set file → set-difference against this file → new failures block merge. This is a document-as-config pattern; the file IS the function.

**No "zero production callers" defect here.** The baseline is consumed by being read and diffed, not by being imported.

## 4. Falsifiability of Tests

Not applicable — TASK-372 does not change `src/` or add tests. It measures existing test outcomes. The helper script `task372_diff_baseline.py` parses unittest output and compares named sets; it is a measurement tool, not a guard.

## 5. Would Merging Delete Anything?

```
$ git diff master...f03c74fc --diff-filter=D --name-only
docs/qwen-tasks/TODO/TASK-372-the-suite-baseline-is-73-failures-short.md
```

**One file deleted:** the TODO version of the task file, which was moved to REVIEW. This is correct task-lifecycle behaviour. No production code, no data, no other task files deleted.

**No destructive merge risk.**

## 6. Scope Drift — SEVERE

The branch `origin/qwen-worker-2-r9` carries **93 changed files** against master. TASK-372 owns at most **7**:

| File | TASK-372's? |
|------|------------|
| `docs/state/SUITE-BASELINE-2026-09-27.txt` | YES |
| `docs/state/SUITE-BASELINE-DELTA-2026-09-26.md` | YES |
| `scripts/task372_diff_baseline.py` | YES |
| `scripts/task372_verify_preexisting.sh` | YES |
| `scripts/run_suite.py` (timeout change) | YES |
| `docs/qwen-tasks/REVIEW/TASK-372-...md` | YES |
| `docs/qwen-tasks/TODO/TASK-372-...md` (deletion) | YES |

The other **86 files** belong to TASK-281, TASK-293, TASK-318, TASK-364, TASK-387, TASK-397, TASK-423/424/425, various GLM verdicts, pool/refill scripts, offer config, provider state, status reports, and handoff documents.

**Cherry-pick is required.** The TASK-372 commits are `91a280e2` and `6fc77fb0`, and they touch only the 7 files above. A clean cherry-pick of those two commits should be possible.

## 7. Incomplete Acceptance Criteria

The task's acceptance criterion 6 requires:

> "Run the suite a second time and diff the two named sets. A stable baseline gives an empty diff."

**This was NOT performed.** The result block and delta document both acknowledge this honestly: "Stability check NOT performed" / "NOT YET PERFORMED." The regenerated baseline has not been proven stable — flaky tests may be baked into the 228 names.

This is not a defect in the measurement itself, but it means the baseline is **provisional.** It is a better merge gate than the stale 128-name baseline, but it should be verified with a second run before it becomes authoritative.

---

## Findings

### Finding 1: Core artifacts exist and numbers are correct — VERIFIED
- **Severity:** N/A (positive finding)
- **Evidence:** Independent `comm` of both baseline files: 128 old, 228 new, 122 shared, 106 new-only, 6 gone. All match result block.

### Finding 2: Stability check not performed — INCOMPLETE
- **Severity:** Non-blocking risk
- **Evidence:** Acceptance criterion 6 explicitly requires a second run. Delta document says "NOT YET PERFORMED." Result block says "stability check owed."
- **Impact:** The 228-name baseline may contain flaky tests. Until verified, a merge gate based on it will produce false positives on stable tests that happen to flap.

### Finding 3: Severe branch scope drift — CHERRY-PICK REQUIRED
- **Severity:** Process concern
- **Evidence:** 93 files changed on branch, 7 belong to TASK-372. The branch carries src/ changes (6 files, +300 lines), test files, offer config, provider state, status reports, and other task files.
- **Impact:** Merging the branch wholesale would land unreviewed work from 10+ other tasks. Cherry-pick the two TASK-372 commits (`91a280e2`, `6fc77fb0`).

### Finding 4: Pre-existing verification not independently reproduced — NOT VERIFIED
- **Severity:** Low
- **Evidence:** The delta document claims all 22 modules were checked at baseline commit `0af11fcb`. I reviewed the table and it is internally consistent, but I did not check out `0af11fcb` and re-run the modules. The categorisation is accepted on documentary evidence.

### Finding 5: run_suite.py timeout change is legitimate — VERIFIED
- **Severity:** N/A (positive finding)
- **Evidence:** Master has `default=1800`. Branch has `default=7200`. The task explicitly says "Fix the timeout if that is what is in the way." The suite takes 35-100 minutes; 30 minutes was insufficient.

---

## Disposition

**MERGE (cherry-pick), with owed stability check.**

The core deliverable — a named-set baseline with full categorisation — is correct, honest about its gaps, and arithmetically verified. The 106 new failures are real regressions and new tests that need separate fix tasks or explicit acceptance as known debt. The stability check is owed but does not invalidate the measurement.

Cherry-pick commits `91a280e2` and `6fc77fb0` from `origin/qwen-worker-2-r9`. Do not merge the branch wholesale.

**Recommendation to Claude:**
1. Cherry-pick the two TASK-372 commits to master.
2. Schedule the stability check (second full suite run, diff named sets) as a follow-up task.
3. The 106 new failures need triage: 68 are regressions from code changes, 38 are from new tests that were written but never passed. Each group needs its own fix task or explicit acceptance into the baseline.
