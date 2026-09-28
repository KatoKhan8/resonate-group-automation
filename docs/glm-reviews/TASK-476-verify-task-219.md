# TASK-476 — Independent verification of TASK-266

## Review identity

| Field | Value |
|-------|-------|
| Task under review | TASK-266 — Learnings A/B/C, and the rule that was never promoted |
| Branch | origin/qwen-worker-r58 |
| Branch HEAD SHA | cf1515fb40730ba47dd134bb54a3ebaceabd5d32 |
| Verified SHA | cf1515fb40730ba47dd134bb54a3ebaceabd5d32 (matches task file) |
| Review worktree | .qwen/worktrees/task476-review (detached HEAD at exact SHA) |
| Reviewer | Qwen (TASK-476) |
| Date | 2026-09-28 |

## Files changed (branch vs master)

| File | Insertions | Deletions |
|------|-----------|-----------|
| `docs/qwen-tasks/DONE/TASK-266-learnings-a-b-c-and-the-rule-that-was-never-promoted.md` | 64 | 0 |
| `src/learningrules.py` | 263 | 0 |
| `tests/test_learningrules.py` | 246 | 0 |
| **Total** | **573** | **0** |

**Merging would delete nothing.** Pure addition.

---

## Finding 1: Artifact exists and is functional

**Status:** VERIFIED

`src/learningrules.py` exists at the reviewed SHA and defines the A/B/C scheme:
- `observation()` — addressable measurements (A)
- `proposal()` — rules resting on observation ids (B)
- `approve()` — unconditional raise (the guard)
- `mark_approved()` — records a decision made elsewhere (the seam)
- `behind()`, `approved_for()` — consumer checks (read, not write)

All 25 tests in `tests/test_learningrules.py` pass (verified: `Ran 25 tests in 0.001s — OK`).

## Finding 2: Zero production callers — DISCONNECTED but BY DESIGN

**Status:** VERIFIED, with context

```
grep -rn "learningrules" src/ scripts/ --include="*.py"
→ only src/learningrules.py itself (self-reference in docstring)
→ zero imports from any other module
```

The review protocol says "zero production callers means DISCONNECTED, which is a rework and not a merge." **However**, the task explicitly instructed: "Do not wire it up." The deliverable was the shape, not the integration. The task says: "Leave a documented seam for the learning doc to be wired in when one exists."

**Verdict on this point:** The zero-caller state is intentional and matches the task's acceptance criteria. The module is a seam, not a feature. This is not the recurring defect of "computed correctly but nothing reads it" — it is "built the representation so something CAN read it when the learning doc exists." The FINDINGS in the result block correctly classify `learning.boost()` as "a B that was never promoted" and note that the two named artifacts (learning doc, workforce scorecard) do not exist.

**Risk:** The seam has no scheduled consumer. If no subsequent task wires the learning doc or scorecard into this scheme, the module remains inert indefinitely. This is acknowledged in the result block's RISKS section.

## Finding 3: The approval guard is enforced, with a caveat

**Status:** VERIFIED with one observation

**The guard fires.** `approve()` raises unconditionally:
```
approve() → LearningRuleError: "no code path may write an approval..."
```
Two tests prove it: `test_approve_raises` and `test_approve_raises_even_for_a_valid_proposal`. Both pass.

**Mutation check:** If `approve()` were changed to return instead of raise, both tests would fail — the `assertRaises` context manager would not catch an exception. The tests are connected to the behavior.

**Caveat — `mark_approved()` bypasses the guard.** `mark_approved(prop_id, entry)` sets status to APPROVED without any access control or human-initiation check. It succeeds programmatically:
```python
entry = proposal('p1', observation_ids=['obs1'], surface='copy', what='test')
result = mark_approved('p1', entry)
# result['status'] == 'approved' — no guard fired
```

The task describes `mark_approved()` as "the seam a hand-edit reaches" — the operator edits YAML, and the import records the decision. This is a defensible design: `approve()` says "code cannot decide," `mark_approved()` says "a decision was made elsewhere, and we record it." The protection is that `mark_approved()` has zero callers and no YAML integration exists. But the function is callable, and a future task that wires YAML import could inadvertently create the code path `approve()` exists to prevent.

**Severity:** Low. The task explicitly designed this seam. No caller exists. But the distinction between `approve()` (guard) and `mark_approved()` (seam) is a naming and documentation constraint, not a structural one. A future task that adds YAML import must ensure the import path is triggered by file change, not by code logic.

## Finding 4: Tests are falsifiable

**Status:** VERIFIED

The tests assert on behavior, not source text:
- `test_unknown_status_is_refused` — calls `proposal()` with invalid status, asserts `LearningRuleError` raised with "unknown status" in message
- `test_approve_raises` — calls `approve()`, asserts `LearningRuleError` raised with "no code path may write an approval"
- `test_superseded_proposal_cannot_be_approved` — creates a superseded entry via `supersede()`, then calls `mark_approved()`, asserts raise with "superseded"
- `test_behind_returns_approved_rule` — creates an APPROVED entry, calls `behind()`, asserts the correct rule is returned
- `test_behind_returns_none_for_unapproved` — creates a PROPOSED entry, calls `behind()`, asserts None

None of these use `hasattr`, source text search, or token-in-file checks. They drive the real entry points and assert on return values and exceptions.

**How could these pass while the implementation is wrong?** Only if the functions returned correct values for the test inputs but wrong values for other inputs. The test coverage is good for the closed vocabulary (all four statuses, all three surfaces), the guard (two tests), and the consumer check (approved, unapproved, wrong surface, no match). Edge cases like case-insensitive surface matching are implicitly covered by the `.lower()` in `proposal()`.

## Finding 5: Pre-existing failure claim verified

**Status:** VERIFIED

The result block claims one pre-existing failure: `test_emailbison_posts_only_to_routes_it_declares`. Confirmed:
- Fails on the branch: `AssertionError: None is not true : v3 carries no bison_campaign_id...`
- Fails on master (verified independently): same error, same message
- Not caused by this change

**Additional finding:** `test_nothing_was_written_by_that` errors in the worktree with `FileNotFoundError: work/` because the isolated worktree has no `work/` directory. This is a worktree artifact, not a code defect — the test passes on master where `work/` exists. Not counted as a new failure.

## Finding 6: `learning.boost()` classification verified

**Status:** VERIFIED

```
grep -rn "boost" src/ scripts/ --include="*.py" | grep -v test_
→ src/learning.py:31  (docstring reference)
→ src/learning.py:325 (function definition)
→ src/learningrules.py:29 (classification comment)
→ zero callers
```

The result block's classification — "a B that was never promoted" — is accurate. The function computes a priority nudge from measured cohort performance, has tests that pass, and is not dead code. But no production code calls it, and under the A/B/C scheme it is a proposal without a proposal record.

## Finding 7: No scope drift

**Status:** VERIFIED

The branch carries exactly three files: the module, the tests, and the task result file. No unrelated changes, no junk, no configuration edits. Cherry-pick would be clean — in fact, a direct merge would be clean since there are no conflicts with zero deletions.

---

## Disposition summary

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Artifact exists and is functional | FIXED + VERIFIED |
| 2 | Zero production callers | ACCEPTED DEFERRED RISK (by task design) |
| 3 | Approval guard enforced, mark_approved seam | ACCEPTED DEFERRED RISK (naming constraint, not structural) |
| 4 | Tests are falsifiable | FIXED + VERIFIED |
| 5 | Pre-existing failure claim | FALSE POSITIVE (confirmed pre-existing, not caused by this change) |
| 6 | learning.boost() classification | FIXED + VERIFIED |
| 7 | No scope drift | FIXED + VERIFIED |

---

## Recommendation: **MERGE**

The work does what the task asked: it builds the A/B/C representation, enforces the approval guard, classifies `learning.boost()`, and leaves a documented seam. All 25 tests pass and are falsifiable. The merge would delete nothing and introduce no conflicts.

The zero-caller state is intentional and explicitly instructed by the task. The `mark_approved()` seam is a known design choice with a documented risk. Neither rises to rework.

**Owed work (not blocking):**
- A future task must wire the learning doc or scorecard into this scheme when one exists, or the module remains inert.
- A future task should ensure YAML import (when built) is triggered by file change detection, not by code logic that could call `mark_approved()` from a non-human path.
