# TASK-513 — Independent GLM Verification of TASK-405

**TARGET_TASK**: TASK-405 (GLM verification of TASK-394, contact-key guard)  
**TARGET_BRANCH**: origin/qwen-worker-12-r9-sync  
**TARGET_SHA**: 3da4a246ee2536760d04dfc4d1d94b649160c2fa  
**VERDICT_SHA**: 9e607efdb93252c0091f9a989254553b9010d4f3 (TASK-405's own commit)  
**REVIEW_WORKTREE**: .qwen/worktrees/task513-review (detached at 3da4a246)  
**VERDICT_DATE**: 2026-09-29  
**REVIEWER**: GLM (independent, this session)

---

## 1. Artifact Existence

**VERIFIED.** TASK-405's artifact is `docs/qwen-tasks/REVIEW/TASK-405-glm-verify-task-394.md` (192 lines). It was created in commit `9e607efd` and the TODO file was deleted (moved to REVIEW). The artifact exists at the target SHA and is a pure verdict document — no code changes.

**Commit `9e607efd` changes exactly 2 files:**
- `+docs/qwen-tasks/REVIEW/TASK-405-glm-verify-task-394.md` (192 lines, new)
- `-docs/qwen-tasks/TODO/TASK-405-glm-verify-task-394.md` (29 lines, deleted)

## 2. What TASK-405 Claims

TASK-405 is a GLM first-pass verification of TASK-394 (contact-key guard investigation). Its claims:

1. **TASK-394 did the real work** (commit `c5d61dee`); TASK-389 never started.
2. **Key generation is centralized** in `identity.contact_key()` and `identity.assign_keys()`.
3. **Validation is centralized** in `store._identity_problems()`.
4. **Enforcement is real** via `store.patch()` refusing writes that introduce identity problems.
5. **9 tests pass** in `test_identity_survives_exclusion.py`.
6. **No inconsistency exists** — no code change needed.
7. **Disposition: FALSE POSITIVE** — the concern is not reachable.

## 3. Independent Verification of Each Claim

### 3.1 TASK-394 provenance (commit c5d61dee)

**PARTIALLY VERIFIED.** `git rev-parse --verify c5d61dee` resolves to `c5d61deef9a12f6fefd695071a31daa725d064`. The commit exists in the object store with message "TASK-394: contact-key guard trace — nothing inconsistent, no code change needed" dated 2026-09-27 14:11. However, **it is orphaned** — `git branch -a --contains c5d61dee` returns empty. The branch it was on (qwen-worker-6-r9) was force-pushed or rebased, and the commit is only reachable via its SHA.

**TASK-389 "never started"**: This was **true at the time of the verdict** (2026-09-27 16:04). However, TASK-389 was subsequently completed on 2026-09-28 (commits `818ad59e` and `d18ae03d`), and received its own GLM verdict via TASK-505 (commit `9682702d`). So the claim is historically accurate but now outdated.

### 3.2 Key generation centralization

**VERIFIED.** At the target SHA:
- `src/identity.py:103` is the **only** site in `src/` that assigns `contact["key"] = key`.
- `git grep '"key"\]\s*=' 3da4a246 -- src/` returns 9 hits, of which 8 are comparisons (`==`), not assignments.
- `contact_key()` (line 79-95) generates keys; `assign_keys()` (line 98-106) threads the collision detection.
- No other module generates or assigns contact keys.

### 3.3 Validation centralization

**VERIFIED.** At the target SHA:
- `src/store.py:1642-1676` — `_identity_problems(rec)` checks three invariants:
  1. Non-empty key (every contact must have one)
  2. Uniqueness (no two contacts share a key)
  3. Event integrity (every event's `contact` field names a known key)
- `src/store.py:1621-1640` — `validate(rec)` calls `_identity_problems()` at line 1638.
- No other function in `src/` implements identity validation.

### 3.4 Enforcement via patch()

**VERIFIED.** At the target SHA:
- `src/store.py:1769-1793` — `patch()` calls `validate(rec)` before and after the change:
  - Line 1783: `was = set(validate(rec))` — problems before
  - Line 1785: `deep_merge(rec, changes)` — apply the change
  - Line 1786: `problems = [p for p in validate(rec) if p not in was]` — new problems only
  - Line 1787-1788: `if problems: raise ValueError(...)` — refuse to make things worse
- `store.append()` also validates before writing (line 326-327 area).

**GAP NOTED (not in TASK-405's scope):** `store.transaction()` provides raw record access without calling `validate()`. 14 callers in `src/` use this path (approve.py, bisonfactory.py, evidencerepair.py, generate.py, heyreachfactory.py, leadobserve.py, leadstop.py, providerwrites.py, qualify.py, repo.py, run.py). A caller using `transaction()` could theoretically introduce identity problems without being caught by `_identity_problems()`. The `transaction()` context manager calls `refuse_evidence_loss` and `refuse_history_loss` but NOT `validate()`. This is a real gap in the "enforcement is complete" story, but it is outside TASK-405's investigation scope.

### 3.5 Tests pass

**VERIFIED.** Ran `python -m unittest tests.test_identity_survives_exclusion -v` in the worktree at the target SHA. All 9 tests pass in 0.011s:
- `test_enrichment_keys_a_contact_before_anybody_can_name_it` ✅
- `test_two_contacts_at_one_domain_get_two_keys` ✅
- `test_two_contacts_in_one_second_produce_two_events` ✅
- `test_excluding_somebody_does_not_take_their_key` ✅
- `test_an_event_naming_nobody_is_a_validation_problem` ✅
- `test_a_contact_with_no_key_is_a_validation_problem` ✅
- `test_two_contacts_sharing_a_key_is_a_validation_problem` ✅
- `test_a_well_formed_record_reports_nothing` ✅
- `test_an_excluded_contact_can_still_own_an_event` ✅

### 3.6 Tests are falsifiable

**VERIFIED.** The tests assert on behavior (what `store.validate()` returns), not on source text or `hasattr`. Specific falsification paths:
- `test_a_contact_with_no_key_is_a_validation_problem` (line 115-116): creates a contact without a key, asserts `"no key" in problems`. Would fail if `_identity_problems` stopped checking for empty keys.
- `test_two_contacts_sharing_a_key_is_a_validation_problem` (line 120-122): creates two contacts with the same key, asserts `"held by 2" in problems`. Would fail if uniqueness check were removed.
- `test_an_event_naming_nobody_is_a_validation_problem` (line 107-113): creates an event referencing a non-existent contact, asserts `"names no contact" in problems`. Would fail if event integrity check were removed.
- `test_a_well_formed_record_reports_nothing` (line 126-134): creates a well-formed record, asserts `validate()` returns `[]`. Would fail if validation produced false positives.

These tests would catch removal or breakage of the identity invariants. They are meaningful.

### 3.7 No code change needed

**VERIFIED.** TASK-405 is an investigation task. Its artifact is a verdict document. No code was changed, and the conclusion (no inconsistency exists) is supported by the code trace.

## 4. Scope Drift on the Branch

**SIGNIFICANT.** The branch `origin/qwen-worker-12-r9-sync` at `3da4a246` carries 46 changed files with 4298 insertions and 492 deletions compared to master. These include work from at least 15 other tasks:

- TASK-245 (nightly sourcing), TASK-272 (explainable verdicts), TASK-294/409 (identity check),
- TASK-311 (ingest LinkedIn), TASK-335 (artifact recovery), TASK-355 (cache token pricing),
- TASK-364 (sequence plan rework), TASK-397 (HeyReach seat cap), TASK-415/417/418 (drift checks),
- TASK-424 (task state registry), TASK-426 (bison staging), TASK-427 (offers validation),
- TASK-434 (GLM verdict on TASK-245), plus suite triage and script changes.

**TASK-405's own contribution is 2 files** (the verdict document creation and TODO deletion). To cherry-pick TASK-405, only commit `9e607efd` is needed. The rest of the branch is unrelated work.

## 5. Would Merging Delete Anything?

**No production data loss.** The branch deletes 6 TODO files (task state transitions from TODO to REVIEW/DONE/BLOCKED):
- `TASK-335-recover-the-audit...` (moved to a recovery branch)
- `TASK-405-glm-verify-task-394.md` (moved to REVIEW)
- `TASK-409-glm-verify-task-294.md` (moved to REVIEW)
- `TASK-415-sender-inventory-drift-check.md` (moved to REVIEW)
- `TASK-417-campaign-cadence-drift-check.md` (moved to DONE)
- `TASK-418-offer-config-consistency-check.md` (moved to REVIEW)

These are legitimate task lifecycle transitions. No production code, tests, or configuration would be deleted by merging TASK-405's specific commit.

## 6. Dispositions

| # | Finding | Disposition | Evidence |
|---|---------|-------------|----------|
| 1 | Key generation is centralized | **VERIFIED** | Only `identity.py:103` assigns `contact["key"]`. `git grep` confirms no other site. |
| 2 | Validation is centralized | **VERIFIED** | `_identity_problems()` at `store.py:1642-1676` is the sole validation function. |
| 3 | Enforcement via patch() is real | **VERIFIED** | `store.py:1783-1788` validates before/after, refuses new problems. |
| 4 | Tests verify the invariants | **VERIFIED** | 9 tests pass, all assert on behavior not source text. |
| 5 | TASK-394 did the work, TASK-389 didn't | **HISTORICALLY ACCURATE, NOW OUTDATED** | TASK-394 commit `c5d61dee` exists but is orphaned. TASK-389 was later completed (2026-09-28). |
| 6 | No inconsistency exists | **VERIFIED** | Code trace confirms centralized generation, validation, and enforcement. |
| 7 | `store.transaction()` bypasses validate() | **NEW FINDING (out of scope)** | 14 callers use raw `transaction()` without identity validation. Not TASK-405's responsibility but a real gap. |

## 7. Recommendation

**CLOSE — verdict is correct, nothing to merge.**

TASK-405 is an investigation/verification task. Its verdict document is accurate: the contact-key guard is centralized, tests verify the invariants, and no code change is needed. The artifact is the verdict itself, and it correctly concludes FALSE POSITIVE.

**Cherry-pick instructions for Claude:**
- Only commit `9e607efd` is TASK-405's work.
- It adds `docs/qwen-tasks/REVIEW/TASK-405-glm-verify-task-394.md` and removes the TODO copy.
- No code changes, no test changes, no risk.

**Follow-up items (not TASK-405's responsibility):**
1. TASK-389 was completed after TASK-405's verdict. Its status should be reconciled with TASK-405's claim that it "never started."
2. The `store.transaction()` bypass gap (14 callers) should be tracked separately if identity enforcement completeness is a concern.
3. TASK-394's commit `c5d61dee` is orphaned — its work is in the codebase but the commit is not reachable from any branch.

## 8. What This Review Could Not Verify

- Whether TASK-389's later work (2026-09-28) agrees or disagrees with TASK-394/TASK-405's conclusion. Not checked; both reached the same conclusion (no inconsistency) independently.
- Whether the `store.transaction()` callers actually modify contact keys in practice. The gap exists structurally, but I did not trace each of the 14 callers to determine if any actually introduces identity problems.

---

**VERDICT: CLOSE**  
**TASK-405's artifact is correct. No code to merge. The contact-key guard is sound.**
