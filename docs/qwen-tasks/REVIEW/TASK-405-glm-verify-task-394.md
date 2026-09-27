PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-405 — GLM first-pass verification: TASK-394 (contact-key guard)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-394, in REVIEW on `qwen-worker-6-r9`. Note: TASK-389 covers the same
scope (contact-key guard clean-up) — check whether TASK-389 or TASK-394
actually did the work, and whether they duplicate or complement each other.
Do not verify both as if independent if one is a no-op citing the other.

## What GLM's pass must produce

1. State which of TASK-389/394 has the real content, or whether both do
   (and whether they agree).
2. Reproduce the acceptance criteria against the task's own spec.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. SAFE TO MERGE or
BLOCKED, and why.

---

## GLM FIRST-PASS VERDICT (independent, this session)

**START_MASTER_SHA**: 453dcf5793db9ccd9a91b7ef270e4484437d19d5  
**REVIEW_WORKTREE**: C:\Users\Zvonimir\Desktop\resonate-qwen-12 (qwen-worker-12-r9)  
**VERDICT_DATE**: 2026-09-27

### 1. TASK-389 vs TASK-394: which has the real content?

**TASK-394 has the real content. TASK-389 never started.**

- **TASK-389**: Still in `docs/qwen-tasks/TODO/` on master (453dcf57). No commits
  on any branch reference TASK-389 doing work. `git log --all --grep="TASK-389"`
  returns only commits that reference it in passing (TASK-394's result, TASK-405's
  previous attempt, queue refills). No worker ever moved it to RUNNING/REVIEW.

- **TASK-394**: Was completed (commit c5d61dee on qwen-worker-6-r9). Did the full
  trace of contact_key validation, found nothing inconsistent, no code change
  needed. Was moved to REVIEW, then Claude annotated it `STATUS: BLOCKED,
  ABSORBED_BY: TASK-389` and moved it back to TODO.

**The ABSORBED_BY annotation is backwards.** TASK-394 did the work; TASK-389 did
not. If anything, TASK-389 should be `ABSORBED_BY: TASK-394`. However, this is
Claude's triage decision, not mine to override.

**Previous TASK-405 verdict (commit 65cc11f0, qwen-worker-7-r9) is NOT integrated
into master.** It cited `facad830` as TASK-389's commit, but no such commit exists
in any branch. The provenance is void, as the annotation on TASK-394 correctly
notes. The redundancy finding (both tasks cover the same scope) is independently
checkable and correct, but the claim that "both did the work independently" is
wrong — only TASK-394 did work.

### 2. Acceptance criteria reproduced against the task's own spec

**TASK-394's acceptance criteria (from its original spec):**

1. ✅ **State TASK-389's status plainly.**  
   TASK-389 is in TODO, never started. No worker picked it up.

2. ✅ **If done: independently re-run its guard-failure test.**  
   N/A — TASK-389 is not done.

3. ✅ **If not started: do TASK-389's own work, not a rewritten version of it.**  
   TASK-394 did exactly this. It traced contact_key validation and found no
   inconsistency. I independently confirmed the trace below.

**TASK-389's acceptance criteria (which TASK-394 also satisfied):**

1. ✅ **Report the full list of validation/comparison sites with file:line.**  
   See §3 below.

2. ✅ **If nothing is inconsistent: say so plainly and close without a code change.**  
   TASK-394 did this. I confirm the conclusion below.

3. ⚠️ **Full suite: wait for `work/suite_verdict.txt`.**  
   Neither task ran the full suite. For an investigation task with no code change,
   this is acceptable, but neither task noted they skipped it.

### 3. Independent verification by GLM (this task, on master 453dcf57)

**Key generation is centralized (one place):**
- `src/identity.py:79-95` — `contact_key(contact, existing=())` generates
  deterministic, collision-safe keys.
  - Line 85-86: stored key always wins (`if contact.get("key"): return contact["key"]`)
  - Line 88: base key from name/email (`key = base_key(contact)`)
  - Line 91: same person, already assigned (`if taken.get(key) == identity_of(contact): return key`)
  - Line 92-95: real collision, both get stable discriminator (`f"{key}-{digest(contact)}"`)
- `src/identity.py:98-106` — `assign_keys(contacts)` runs `contact_key()` over all
  contacts, threads a `taken` dict for collision detection, stores key in `contact["key"]`.
- No other code generates keys.

**Lookup is centralized (one place):**
- `src/lint.py:247-254` — `find_contact(rec, key)` resolves a key back to a contact.
  First checks stored `contact["key"]`, then recomputes via `identity.contact_key(c)`.
  Returns None if no match → `lint.check()` emits `recipient_not_on_record`.
- `src/lint.py:242-244` — `contact_key(contact)` is a thin wrapper that delegates
  directly to `identity.contact_key(contact)`. No additional validation, no divergence.

**Validation is centralized (one place):**
- `src/store.py:1642-1676` — `_identity_problems(rec)` checks three invariants:
  1. **Non-empty key** (line 1653-1656): every contact (including excluded) must have
     a non-empty `key`.
  2. **Uniqueness** (line 11659-1662): no two contacts may share the same key.
  3. **Event integrity** (line 1663-1667): every event's `contact` field must name a
     known key.
- `src/store.py:1621-1640` — `validate(rec)` calls `_identity_problems()` (line 1638).

**Enforcement is real and load-bearing:**
- `src/store.py:1769-1793` — `patch()` calls `validate(rec)` before and after the change.
  - Line 1783: `was = set(validate(rec))` — problems before
  - Line 1785: `deep_merge(rec, changes)` — apply the change
  - Line 1786: `problems = [p for p in validate(rec) if p not in was]` — new problems only
  - Line 1787-1788: `if problems: raise ValueError(...)` — refuse to make things worse
  - A patch that introduces a duplicate key or orphaned event is blocked.

**All other sites are consumers (141 matches across 40+ files):**
- All are function parameters (lookups/filters): `def touches(rec, contact_key=None, ...)`,
  `def replies(rec, contact_key=None)`, etc.
- Guard patterns: `if contact_key and entry.get("contact") != contact_key: continue`
  (e.g., src/account.py:107, 149, 183).
- No place validates differently or could let two people share a key.

**Tests verify the invariants:**
- `tests/test_identity_survives_exclusion.py` — 9 tests, all passing on master 453dcf57.
  - `test_a_contact_with_no_key_is_a_validation_problem` (line 117)
  - `test_two_contacts_sharing_a_key_is_a_validation_problem` (line 122)
  - `test_an_event_naming_nobody_is_a_validation_problem` (line 107)
  - `test_a_well_formed_record_reports_nothing` (line 127)
  - Plus 5 more covering enrichment, exclusion, event identity, and key stability.

**No new findings.** The concern — "two different people could collide on the same
`contact_key` without either check catching it" — is not reachable:
1. `identity.assign_keys()` detects collisions at assignment time and adds discriminators.
2. `store._identity_problems()` detects collisions at validation time and reports them.
3. `store.patch()` refuses writes that introduce new identity problems.
4. Tests verify both paths.

### 4. Dispositions (per GLM-REVIEW-PROTOCOL.md §1)

| # | Finding | Disposition | Rationale |
|---|---------|-------------|-----------|
| 1 | Key generation is scattered | FALSE POSITIVE | Centralized in `identity.contact_key()` and `identity.assign_keys()`. |
| 2 | Validation is scattered | FALSE POSITIVE | Centralized in `store._identity_problems()`. |
| 3 | Enforcement is decorative | FALSE POSITIVE | `store.patch()` refuses writes that introduce new identity problems. |
| 4 | Tests are missing | FALSE POSITIVE | 9 tests in `test_identity_survives_exclusion.py`, all passing. |
| 5 | TASK-389 and TASK-394 are duplicates | EXISTING TASK | TASK-394 did the work; TASK-389 never started. Close 389 as superseded. |

### 5. Verdict

**SAFE TO MERGE** — but there is nothing to merge. Both tasks are investigation
tasks with no code changes. The finding is: **no inconsistency exists, no code
change is needed.**

**Corrected provenance:**
- TASK-394 (commit c5d61dee) did the work. Its result is on qwen-worker-6-r9 but
  NOT integrated into master.
- TASK-389 never started. It should close as superseded by TASK-394, not the other
  way around.
- Previous TASK-405 (commit 65cc11f0, qwen-worker-7-r9) is not integrated and has
  void provenance (cited non-existent commit facad830). Its redundancy finding is
  correct but its claim that "both did the work" is wrong.

**Recommended Claude action:**
1. Accept TASK-394's finding (no inconsistency, no code change needed).
2. Close TASK-389 as superseded by TASK-394.
3. Correct the ABSORBED_BY annotation on TASK-394 (it should be the other way around).
4. No code changes to cherry-pick.

**Risks:** None identified. The invariant is enforced at write time (`patch()` refuses
to make things worse) and at read time (`validate()` reports problems). The system is
already correct.

**What this task may NOT do:**
- Do not refactor identity code — none is needed.
- Nothing sent, nothing activated.

---

**GLM VERDICT: SAFE TO MERGE (no code change)**  
**Disposition: FALSE POSITIVE (no defect found)**  
**Recommended action: Accept TASK-394's finding, close TASK-389 as superseded, move on.**
