# TASK-471 — Independent verification of TASK-243

## Review metadata

| Field | Value |
|-------|-------|
| Target task | TASK-243 |
| Branch | origin/qwen-worker-2-task-243 |
| Branch HEAD SHA | d0f49d12d1990264b3fc847a8b31c0b3e42fb018 |
| SHA verified with git rev-parse | YES — matches task file |
| Review worktree | .qwen/worktrees/task471-review (detached HEAD at exact SHA) |
| Reviewer | Qwen (TASK-471) |
| Date | 2026-09-28 |

**A verdict that does not name the branch HEAD SHA it reviewed is void.**
SHA reviewed: `d0f49d12d1990264b3fc847a8b31c0b3e42fb018`. Confirmed.

---

## 1. Does the artifact exist, and does it do what the result block claims?

**YES — artifacts exist on this ref.**

Files added/modified (from `git diff master...HEAD --stat`):

| File | Change | Exists on ref |
|------|--------|---------------|
| `src/eligibility.py` | +27 lines: `BLOCKED_CLIENT_APPROVAL` reason, gate in `_suppressed()` and `decide()` | YES |
| `src/personas.py` | +24 lines: S4 gate in `select()` | YES |
| `scripts/stage_s5_verify.py` | +12/-5 lines: S5 gate, unconditional `is_approved()` filter | YES |
| `src/generate.py` | +13 lines: S7 gate, raises `ClientApprovalRequired` | YES |
| `src/executionguard.py` | +16 lines: enrollment gate in `authorize()` | YES |
| `src/dossier.py` | +14 lines: `client_approval` surface | YES |
| `src/funnel.py` | +9 lines: `client_approved` stage | YES |
| `src/digest.py` | +16 lines: `awaiting_client_approval` bucket | YES |
| `src/clientapproval.py` | +13 lines: `is_active()` function | YES |
| `src/store.py` | +6 lines: `CLIENT_APPROVAL` in `STATE_OVERRIDES` | YES |
| `tests/test_client_approval_gate_at_every_stage.py` | +304 lines: 24 new tests | YES |

**Claim: "24 new tests, all passing"** — VERIFIED. Ran `python -m unittest tests.test_client_approval_gate_at_every_stage -v`: 24 tests, all OK.

---

## 2. Existence is not function — are there production callers?

**YES — every gate has a real production caller.**

| Stage | File | Line | Call |
|-------|------|------|------|
| S4 persona discovery | `src/personas.py` | 373-374 | `clientapproval.is_active(client)` + `is_approved(domain, client)` |
| S5 verification | `scripts/stage_s5_verify.py` | 179-181 | `clientapproval.is_approved(d, "productive")` (unconditional) |
| S7 copy | `src/generate.py` | 1626-1631 | `clientapproval.is_active(...)` + `is_approved(...)`, raises |
| Enrollment (eligibility) | `src/eligibility.py` | 308-311, 622-625 | `is_active()` + `is_approved()` in `_suppressed()` and `decide()` |
| Enrollment (executionguard) | `src/executionguard.py` | 490-495 | `is_active()` + `is_approved()` in `authorize()` |
| Surface: dossier | `src/dossier.py` | 152 | `clientapproval.state_of(domain, client)` |
| Surface: funnel | `src/funnel.py` | 204 | `clientapproval.is_approved(...)` |
| Surface: digest | `src/digest.py` | 160 | `clientapproval.counts(...)` |

**NOT DISCONNECTED.** Every gate is consumed by the production entry point.

---

## 3. Falsification of result claims

### 3a. Mutation: would removing the gate from eligibility.decide() break tests?

YES — `test_eligibility_decide_blocks_unapproved` asserts `result["verdict"] == BLOCKED` and `BLOCKED_CLIENT_APPROVAL in reasons`. Removing the gate at lines 622-625 would cause the test to fail because the record would proceed past the approval check.

### 3b. Mutation: would removing the gate from personas.select() break tests?

YES — `test_an_unapproved_account_gets_no_personas` asserts `result["kept"] == []` and `result["awaiting_client_approval"]` is truthy. Removing the gate at lines 373-389 would let contacts through.

### 3c. Mutation: would removing the gate from generate.draft() break tests?

YES — `test_draft_raises_for_unapproved_domain` asserts `ClientApprovalRequired` is raised. Removing lines 1626-1631 would let draft proceed.

### 3d. S5 test — SOURCE-TEXT ASSERTION, NOT BEHAVIORAL

**FINDING: The S5 test (`test_eligible_domains_filters_unapproved`) uses `inspect.getsource(s5.main)` and checks for the string `"clientapproval.is_approved"` in the source.** This is explicitly the kind of test the protocol says is "not accepted as proof" — it proves the text exists, not that it executes.

The actual S5 script behavior IS correct (unconditional `is_approved()` filter at line 179), but the test does not prove this behavior. If someone changed the filter to a no-op while leaving the import in place, the test would still pass.

**Severity: MEDIUM.** The code is correct; the test is weak. Replace with a behavioral test that calls the S5 filtering logic and asserts on the filtered domain set.

### 3e. Executionguard enrollment gate — NO BEHAVIORAL TEST

**FINDING: The `executionguard.authorize()` path (line 490-495) has no behavioral test in this test file.** The "EnrollmentRefusesUnapproved" class tests `eligibility.decide()`, which is a different code path. The executionguard gate is the one the provider write path actually consults, and it is untested here.

If someone removed lines 490-495 from `executionguard.py`, all 24 tests in this file would still pass.

**Severity: MEDIUM.** The code is correct; the test coverage has a gap at the most critical gate (the one closest to the provider write).

---

## 4. Are tests falsifiable?

**Mostly YES, with two exceptions noted above.**

- S4 behavioral test: YES — asserts on `result["kept"]` and `result["awaiting_client_approval"]`
- S5 test: NO — source-text assertion (`inspect.getsource`)
- S7 behavioral test: YES — asserts `ClientApprovalRequired` is raised
- Enrollment (eligibility) behavioral test: YES — asserts `BLOCKED` verdict and reason
- Enrollment (executionguard) behavioral test: NO — not tested at all
- Fail-closed tests: YES — assert `is_approved()` returns False for unknown/pending
- Counting tests: YES — assert on counted exclusion numbers
- No-kill-switch tests: YES — assert on function signatures (these are appropriate for this kind of negative proof)
- Surface tests: YES — assert on dossier/funnel/digest output structure

---

## 5. Would merging DELETE anything?

**NO.** `git diff master...HEAD --diff-filter=D --name-only` returns empty. No files would be deleted.

---

## 6. Scope drift — pollution on the branch

**FINDING: Two scratch files are committed:**

- `.qwen-TASK.err` — contains a Qwen session warning about headless/yolo mode
- `.qwen-TASK.out` — empty file

These are Qwen Code session artifacts, not part of the task. They must be excluded from any cherry-pick or merge.

**Severity: LOW.** Easy to exclude during cherry-pick. The actual work files are clean.

---

## 7. Additional finding: `is_active()` conditional gate

All four in-stage gates (S4, S7, eligibility, executionguard) are guarded by `clientapproval.is_active()`, which returns True only when at least one decision record exists. This means:

- Before any client-approval records are written, ALL gates are open
- The gate becomes fail-closed only after the system is "initialized" by a record

The operator directive says "client account approval is a hard gate" and "same class as verification and collision." Verification and collision do NOT have an `is_active()` guard — they fire unconditionally.

**This is a design choice, not a defect.** The task documents it in FINDINGS and it's a reasonable rollout strategy to avoid breaking pre-existing workflows. But it is a conditional gate, not the unconditional hard gate the operator described. The S5 script, notably, does NOT use `is_active()` — it's unconditionally fail-closed, which is the stricter and more correct behavior.

**Severity: LOW.** Documented, intentional, and defensible. Worth confirming with the operator that conditional activation is acceptable.

---

## Findings summary

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| F1 | S5 test is source-text assertion, not behavioral | MEDIUM | REWORK — replace with behavioral test |
| F2 | Executionguard enrollment gate has no behavioral test | MEDIUM | REWORK — add test that calls `executionguard.authorize()` with unapproved domain |
| F3 | Scratch files `.qwen-TASK.err` and `.qwen-TASK.out` committed | LOW | CHERRY-PICK EXCLUSION — do not include in merge |
| F4 | `is_active()` conditional makes gates dormant until initialized | LOW | ACCEPTED — documented design choice, confirm with operator |

---

## Recommendation

**REWORK** — two test gaps need filling before merge.

The production code is correct, well-placed, and consumed at every stage. The architecture is sound. But:

1. The S5 test must be replaced with a behavioral test (the current one proves text, not function)
2. The executionguard gate needs a behavioral test (it's the gate closest to the provider write and has zero test coverage in this file)
3. The scratch files must be excluded from any cherry-pick

Once those are addressed, this is a clean merge. The `is_active()` conditional is acceptable as a rollout strategy but should be explicitly acknowledged by the operator as a deviation from "same class as verification and collision."

### Cherry-pick scope (for when rework is done)

Clean files to take:
- `src/eligibility.py`
- `src/personas.py`
- `scripts/stage_s5_verify.py`
- `src/generate.py`
- `src/executionguard.py`
- `src/dossier.py`
- `src/funnel.py`
- `src/digest.py`
- `src/clientapproval.py`
- `src/store.py`
- `tests/test_client_approval_gate_at_every_stage.py`

Files to LEAVE:
- `.qwen-TASK.err`
- `.qwen-TASK.out`
