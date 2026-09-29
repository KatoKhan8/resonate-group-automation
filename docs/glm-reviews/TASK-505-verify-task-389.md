# TASK-505 — GLM Independent Verification of TASK-389

## Target

    task            TASK-389 (contact-key guard clean-up)
    branch          origin/qwen-worker-7-r9
    named HEAD SHA  a47ecb515c7bddc63d256c24b3768d04a3df7133
    actual HEAD SHA 723e21fde827ce9f9ace93b9cc85a19d47f2f053
    reviewed SHA    a47ecb515c7bddc63d256c24b3768d04a3df7133 (detached worktree)

**Branch movement:** The branch has moved from `a47ecb51` to `723e21fd` since this
task was dispatched. Per standing instructions, the verdict reviews the original
SHA `a47ecb51` as the artifact under review. An isolated worktree was created at
that exact commit (`.qwen/worktrees/glm-505`, detached HEAD).

## Task summary

TASK-389 is an investigation task: trace all `contact_key` validation sites in
`src/`, determine whether validation is centralized or duplicated with drift, and
report. The task explicitly permits closing with no code change if nothing is
inconsistent.

**Result block claim:** DONE — no code change, no inconsistency found. Validation
is centralized in three places: `identity.contact_key()` (generation),
`identity.assign_keys()` (assignment), `store._identity_problems()` (validation).

## Verification

### 1. Does the artifact exist on this ref?

**YES.** `docs/qwen-tasks/REVIEW/TASK-389-contact-key-guard-cleanup.md` exists at
`a47ecb51` with a complete result block. Created in commit `d18ae03d` ("TASK-389:
contact-key guard trace complete, no inconsistency found"). The task file was moved
from RUNNING to REVIEW with a 119-line result block.

### 2. Are the result block's claims accurate?

**Claim 1: `identity.contact_key()` at src/identity.py:79 is the single authority.**
**VERIFIED.** Read the function. It implements: stored key wins → name slug → email
slug → digest fallback, with collision handling via digest suffix. `lint.contact_key()`
at src/lint.py:242-244 delegates directly: `return identity.contact_key(contact)`.
No other module implements independent key generation logic.

**Claim 2: `contact["key"] = key` appears exactly once in all of src/.**
**VERIFIED.** `grep -rn 'contact\["key"\]\s*=' src/*.py` returns exactly one hit:
`src/identity.py:103`, inside `assign_keys()`.

**Claim 3: `assign_keys()` is defined once, at src/identity.py:98.**
**VERIFIED.** `grep -rn "def assign_keys" src/*.py` returns one hit.

**Claim 4: Callers of `assign_keys` are `enrich.py:626` and `personas.py:366,375`.**
**VERIFIED.** `grep -rn "assign_keys" src/*.py` confirms exactly these call sites
(plus the definition and two comments).

**Claim 5: `store._identity_problems()` at src/store.py:1642 checks three invariants.**
**VERIFIED.** Read the function (lines 1642-1676):
- (a) Every contact/excluded has a non-empty key → `"contact with no key"`
- (b) No two contacts share a key → `"contact key held by N contacts"`
- (c) Every event references an existing contact → `"event X names no contact"`

**Claim 6: All module-local `_contact_of` functions do the same single-pass comparison.**
**VERIFIED.** `grep -rn '.get("key") ==' src/*.py` returns 30+ hits, all performing
`contact.get("key") == contact_key` — identical single-pass lookup. The two-pass
`lint.find_contact()` (stored key then recompute) is strictly more defensive but
not functionally different for well-formed records, because `identity.contact_key()`
returns the stored key when present.

### 3. Are the tests falsifiable? (Mutation test)

**YES.** Performed mutation: changed `len(held) > 1` to `len(held) > 99` in
`store._identity_problems()` (src/store.py:1668). Result:

    test_two_contacts_sharing_a_key_is_a_validation_problem ... FAIL
    AssertionError: False is not true

The test failed for the intended reason (the uniqueness guard was disabled, so
`store.validate()` no longer reported the collision), and no other guard fired
first. Restored the file after confirmation.

**Test coverage of all three invariants** (in `tests/test_identity_survives_exclusion.py`):
- `test_a_contact_with_no_key_is_a_validation_problem` → invariant (a) ✓
- `test_two_contacts_sharing_a_key_is_a_validation_problem` → invariant (b) ✓
- `test_an_event_naming_nobody_is_a_validation_problem` → invariant (c) ✓

All 9 tests in the module pass at `a47ecb51`.

### 4. Existence is not function — are there production callers?

**Not applicable in the usual sense.** TASK-389 is an investigation task with no
code change. The question becomes: are the existing validation sites CONSUMED?

- `store.validate()` is called from the generation pipeline and test suite.
- `identity.assign_keys()` is called from `enrich.merge_contacts()` and
  `personas.select()` — both production paths.
- `lint.find_contact()` is called from `approve.py`, `executionguard.py`,
  `generate.py`, `push.py`, `lint.py` — all production paths.

The validation chain is fully wired and consumed. No disconnected components.

### 5. Would merging delete anything?

**TASK-389's own commits:** No. The two commits (`818ad59e`, `d18ae03d`) only
move the task file from TODO → RUNNING → REVIEW. No src/, tests/, or docs/ files
are deleted.

**Branch-wide diff vs master:** 4 TODO files are deleted (moved to REVIEW/DONE),
10 src/ files are modified (+1442/-149 lines), 22+ test files modified/added.
These are other tasks' work, not TASK-389's. Cherry-picking TASK-389 is clean:
only the task file move is needed.

### 6. Scope drift

**The branch carries massive scope beyond TASK-389.** 102 files changed, 13,947
insertions. This is a review/audit branch (`qwen-worker-7-r9`) carrying ~30 GLM
verdicts and their associated task file movements. TASK-389's contribution is
exactly 2 commits touching 1 file (the task file). Cherry-pick is trivial and
isolated.

## Findings

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | Result block accurately traces all contact_key validation sites | — | CONFIRMED |
| 2 | Single assignment site (`identity.py:103`) verified by grep | — | CONFIRMED |
| 3 | Three-invariant validation in `_identity_problems` verified by read | — | CONFIRMED |
| 4 | Mutation test reproduces: breaking uniqueness guard trips the right test | — | CONFIRMED |
| 5 | All 9 identity tests pass at reviewed SHA | — | CONFIRMED |
| 6 | No inconsistency exists; no code change was needed | — | CONFIRMED |
| 7 | Task file output path in TASK-505 has template error (`task-219` → `task-389`) | cosmetic | NOTED |

## Disposition

**MERGE.**

TASK-389 is a clean investigation that reached the correct conclusion: the
`contact_key` invariant is well-guarded with centralized generation, assignment,
and validation. The result block is thorough, accurate, and verifiable. Every
claim was independently confirmed against the code at the reviewed SHA. The
mutation test proves the existing tests are behavioral, not source-text.

No code change was needed and none was made. The artifact is the finding itself,
documented in the result block. This is an acceptable and complete outcome for
an investigation task.

Cherry-pick is trivial: commits `818ad59e` and `d18ae03d`, touching only the
task file. No risk of deletion, no scope pollution in TASK-389's own diff.

## Reproducible commands

    # Check out the reviewed SHA
    git worktree add .qwen/worktrees/glm-505 a47ecb515c7bddc63d256c24b3768d04a3df7133 --detach

    # Verify single assignment site
    cd .qwen/worktrees/glm-505 && grep -rn 'contact\["key"\]\s*=' src/*.py

    # Verify assign_keys is the only key-setting function
    cd .qwen/worktrees/glm-505 && grep -rn "def assign_keys" src/*.py

    # Read the validation function
    cd .qwen/worktrees/glm-505 && sed -n '1642,1676p' src/store.py

    # Run the identity tests
    cd .qwen/worktrees/glm-505 && python -m unittest tests.test_identity_survives_exclusion -v

    # Mutation: break uniqueness guard, confirm test catches it
    # Change line 1668: `> 1` → `> 99`, run test, restore

    # Clean up
    git worktree remove .qwen/worktrees/glm-505
