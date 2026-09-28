# TASK-476 — Independent verification of TASK-266

**Target task:** TASK-266 (Learnings A/B/C, and the rule that was never promoted)
**Branch:** origin/qwen-worker-r58
**Branch HEAD SHA reviewed:** cf1515fb40730ba47dd134bb54a3ebaceabd5d32
**SHA verified:** `git rev-parse origin/qwen-worker-r58` → cf1515fb40730ba47dd134bb54a3ebaceabd5d32 ✓
**Review worktree:** .qwen/worktrees/task476-review (detached HEAD at cf1515fb)
**Date:** 2026-09-28

---

## Summary

TASK-266 built `src/learningrules.py` — a three-level scheme (observation/proposal/approval) for distinguishing proposed rules from unwired code. The module implements a closed vocabulary, an approval guard that raises unconditionally, and a consumer check (`behind()`, `approved_for()`). 25 tests cover the required properties. All pass.

**The module is DISCONNECTED.** `git grep "learningrules" cf1515fb -- src/ scripts/` returns zero hits. No production code imports, calls, or references the module. The task explicitly chose not to wire it ("do not wire it up"), and the task's scope was to build the shape, not connect it. But the repository rule applies: *a change that is correct and not consumed is a change that did nothing.*

**Disposition: REWORK** — not because the work is wrong, but because it is unfinished. The module exists and works; nothing reads it.

---

## Finding 1: Artifact exists and does what the result block claims

**Status:** VERIFIED

The three files exist on the branch at the exact SHA:
- `src/learningrules.py` (263 lines) — module with A/B/C scheme
- `tests/test_learningrules.py` (246 lines) — 25 tests
- `docs/qwen-tasks/DONE/TASK-266-learnings-a-b-c-and-the-rule-that-was-never-promoted.md` — task file with result block

All 25 tests pass when run in isolation:
```
Ran 25 tests in 0.001s
OK
```

The module implements:
- Closed vocabulary: `STATUSES = (PROPOSED, APPROVED, REJECTED, SUPERSEDED)`, `SURFACES = (COPY, ICP, ROUTING)`
- Unknown values refused with `LearningRuleError`
- `approve()` raises unconditionally
- `behind()` returns the approved rule for a value, or None
- `approved_for()` filters approved rules by surface

**Evidence:** Test run in isolated worktree at cf1515fb. All 25 tests pass.

---

## Finding 2: Existence is not function — zero production callers

**Status:** DISCONNECTED

```
git grep -n "learningrules" cf1515fb -- src/ scripts/
(empty, exit code 1)
```

No file in `src/` or `scripts/` imports or references `learningrules`. The module is entirely isolated. No production code path reaches it.

The task explicitly said "do not wire it up" and the task's scope was to build the shape. But the repository rule is clear: *zero production callers means DISCONNECTED, which is a rework and not a merge.* The module is a correct implementation of a representation layer that nothing consumes.

This is the same shape as the recurring defect: `learning.boost()` (which the task classifies), `slackfollowup.due()`, and the five report sections that rendered and were never assembled. The task correctly identified the defect in FINDINGS ("learning.boost() is a B that was never promoted") but did not close the loop: the new module is itself a B that was never promoted.

**Evidence:** `git grep` on the branch. Zero hits outside the module's own definition and tests.

---

## Finding 3: Tests are falsifiable — mutation test passes

**Status:** VERIFIED

Mutation test: replaced `approve()` with a no-op that returns silently. The test `test_approve_raises` failed with `AssertionError: LearningRuleError not raised`. The mutation was killed — the test correctly catches a broken guard.

```
MUTATION KILLED - test correctly catches a broken guard
```

The tests assert on behavior (raises, returns, filters), not on source text or `hasattr`. They are meaningful.

**Evidence:** Mutation test run in isolated worktree.

---

## Finding 4: `mark_approved()` can bypass the approval guard

**Status:** FINDING — not tested, not wired, potential future bypass

`approve()` raises unconditionally (the guard). But `mark_approved()` can set status to APPROVED without raising:

```python
entry = learningrules.proposal('p1', observation_ids=['obs1'], surface='copy', what='test')
result = learningrules.mark_approved('p1', entry)
# result['status'] == 'approved' — no exception
```

The docstring says "NOT an approval - a record of one" and "This is the seam a hand-edit reaches." But the function is callable from code, and the hard rule says "nothing in `src/` or `scripts/` may write an approval." `mark_approved()` writes an approval.

The tests only exercise `mark_approved()` on superseded and rejected proposals (where it raises). The success path — calling it on a PROPOSED proposal — is not directly tested. It is indirectly exercised by `test_behind_returns_approved_rule`, which constructs an APPROVED entry by passing `status=APPROVED` to `proposal()`, not by calling `mark_approved()`.

This is not a blocker today because the module has zero production callers. But when the module is wired (the owed rework), `mark_approved()` becomes a bypass path unless it is also guarded or its use is constrained.

**Evidence:** Direct function call in isolated worktree. `mark_approved()` returns `{'status': 'approved'}` without raising.

---

## Finding 5: Merging would not delete anything

**Status:** VERIFIED

```
git diff origin/master...cf1515fb --stat
 src/learningrules.py                               | 263 +++++
 tests/test_learningrules.py                        | 246 +++++
 docs/qwen-tasks/DONE/TASK-266-...md                | 151 +++++
 3 files changed, 573 insertions(+)
```

All three files are additions. No deletions. Merging is safe from the deletion perspective.

**Evidence:** `git diff --stat` on the branch.

---

## Finding 6: No scope drift

**Status:** VERIFIED

The branch carries exactly three files, all named by the task. No unrelated changes, no pollution, no scratch output. Cherry-picking would be clean.

**Evidence:** `git diff --stat` and `git log --oneline origin/qwen-worker-r58 --not origin/master` (3 commits, all TASK-266).

---

## Finding 7: `learning.boost()` classification is correct

**Status:** VERIFIED

```
git grep -n "learning.boost\|boost(" cf1515fb -- src/ scripts/
src/learning.py:31:  (docstring)
src/learning.py:325:def boost(cohort, config=None):
src/learningrules.py:29:  (docstring reference)
```

`learning.boost()` has zero production callers. Only its own definition and docstring references appear. The task correctly classified it as "a B that was never promoted — unwired code, not dead code." The function works and has tests, but nothing calls it.

**Evidence:** `git grep` on the branch.

---

## Finding 8: Pre-existing test failure is unrelated

**Status:** VERIFIED

`test_invariants` run shows:
- 1 failure: `test_emailbison_posts_only_to_routes_it_declares` — pre-existing, confirmed failing on master baseline
- 1 error: `FileNotFoundError` for `work/` directory — worktree environment issue (work/ is gitignored)

Neither is caused by TASK-266's changes.

**Evidence:** Test run in isolated worktree.

---

## Disposition

**REWORK**

The work is correct, the tests are meaningful, and the module does what it claims. But it is DISCONNECTED: zero production callers, no consumer, no downstream effect. The task explicitly chose not to wire it, and the task's scope was to build the shape. But the repository rule applies, and the module is the same shape as the defect it identifies: a thing computed correctly that nothing downstream reads.

The owed work is:
1. Wire `learningrules` into at least one consumer — e.g., `behind()` called by a copy/ICP/routing reader, or `proposal()` used to wrap `learning.boost()`'s output.
2. Test `mark_approved()` success path, and decide whether it is a bypass or a seam.
3. Then merge.

The module is a good foundation. It is not yet a function.

---

## Recommendation

**REWORK** — wire the module into one consumer, test the `mark_approved()` success path, and re-submit. The shape is right; the wiring is owed.

**MERGE / REWORK / CLOSE:** REWORK
