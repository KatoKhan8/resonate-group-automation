PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-442 — GLM independent verification: TASK-285, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-285
    branch          origin/qwen-worker-4-r9
    branch HEAD SHA e05f401e6b3126bd248a7a54c14b3ba86828c73a

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`e05f401e6b3126bd248a7a54c14b3ba86828c73a` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`e05f401e6b3126bd248a7a54c14b3ba86828c73a` anyway, because that is the artifact this verdict is about.

## What the verdict must establish

1. **Does the artifact exist on this ref, and does it do what the result block
   claims?** "DONE, artifact verified" is not proof. Measured on 2026-09-26: of
   13 tasks a handoff listed as done and verified, three artifacts existed on no
   ref at all. Check with `git log --diff-filter=A --all -- <path>`.
2. **Existence is not function.** A module, test, config key, report or
   paragraph proves nothing alone. Trace the chain and prove every link is
   CONSUMED: is there a production caller? **Zero production callers means
   DISCONNECTED, which is a rework and not a merge.** The recurring defect in
   this repository is a thing computed correctly that nothing downstream reads.
3. **Falsify the result's own claims rather than confirming them.** If it claims
   a mutation test, perform the mutation yourself and confirm the intended test
   fails for the intended reason — and that a different guard did not fire
   first. If it claims a measurement, re-derive the number.
4. **Are its tests falsifiable?** Ask: how could these pass while the
   implementation is still wrong? Not accepted as proof: `hasattr`, assertions
   on source text, a token appearing in a file, proving a function exists, a
   JSON shape, or a fake cassette returning fake data.
5. **Would merging it DELETE anything?** `git diff master...e05f401e6b3126bd248a7a54c14b3ba86828c73a --stat`. This
   repo has been burned: one branch's files were byte-identical to master's and
   merging would have deleted 12,487 lines; another would have deleted the
   classification answering 33 ambiguous holds; and one would have reverted
   provider truth by a day. Compare blob hashes, not task-file stages.
6. **Scope drift:** does the branch carry junk beside the work? Say what would
   have to be cherry-picked. Merging pollution to save time is forbidden here.

## Disposition

One of the protocol's eight, with evidence for each finding, plus an explicit
**MERGE / REWORK / CLOSE** recommendation and the reason. A CLOSE with a good
reason is a real result and is progress — do not recommend a merge to reduce a
queue. Where you could not verify something, say "not verified" rather than
assuming it holds; a confident wrong verdict is the expensive outcome.

## Boundaries

Read-only with respect to production. **Provider writes = 0**, never call a real
provider, and do not run anything that would. The production freeze is in force:
no launch, activation, enrolment, attachment, resume or send. Do not touch
campaigns 487, 489 or 493. `sending.live` is off for `productive` and stays off.
Do not merge anything — the verdict is the deliverable and Claude merges.

Write the verdict to `docs/glm-reviews/TASK-442-verify-task-285.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

**STATUS:** DONE
**COMMIT:** 67d3e5d8
**TESTS:** 15/15 pass in `tests/test_a_refused_domain_is_never_clear.py` (unittest)
**FILES CHANGED:**
- `docs/glm-reviews/TASK-442-verify-task-285.md` (new, 156 lines)
- `docs/qwen-tasks/REVIEW/TASK-442-glm-verify-task-285.md` (moved from TODO/)

**FINDINGS:**

**REWORK recommended.** Three artifacts exist and are correct (report document, report script, 15 tests), but:

1. **Tests do not prove the wiring.** The test suite imports `classify()` from `scripts/collision_walk_report`, not `collision_cleared()` from `scripts/batch_eligibility`. Two tests re-implement the eligibility logic inline. Mutation test: deleting lines 118-126 of `batch_eligibility.py` (the walk-file read) leaves all 15 tests green. The wiring is untested. This is the "test the text, not the behavior" defect (TASK-029, TASK-028, TASK-019 on 2026-09-14).

2. **Wiring is pre-existing on master.** Both `scripts/s6_collision_walk.py` (writer) and `scripts/batch_eligibility.py` (consumer) exist on master with zero diff. TASK-285 did not add the wiring; it added the report and tests. The wiring claim in the result block ("deleting the read changes eligibility") was a manual check, not a test.

3. **Scope drift is severe.** The branch carries 69 files changed (14,648 insertions, 3,115 deletions) across 15+ tasks (TASK-245, 264, 279, 285, 298, 326, 408, 410, 414, 422, 423, 425, 426, 427, 428, 429). Only 3 files belong to TASK-285. The branch cannot be merged; only cherry-pick is viable.

4. **`batch_eligibility.py` has zero `src/` callers.** It is a standalone script, not imported by the generation pipeline. Whether it is called by automation is not visible in the code.

**What is correct:**
- Walk report is thorough (four verdicts, counted, summing to input; three COLLIDES rows with ownership evidence; one REFUSED row with response shape; eligibility counts present/absent; staleness field; resume proof)
- `classify()` function is correct
- 10 tests pinning `classify()` are valid
- No production code deleted (only TODO/ task files moved)

**What needs rework:**
- Tests must import and test `batch_eligibility.collision_cleared()` directly, not re-implement its logic
- A mutation test that deletes the walk-file read and asserts the cleared set changes would prove the wiring is load-bearing
- Branch must be split: TASK-285's 3 files cherry-picked to a clean branch

**RISKS:** The walk was run on 2026-09-22 (5 days old at review time). The report claims live provider state, but I cannot independently re-run it (no access to production `work/` or provider credentials). The report is internally consistent and the numbers add up.

**RECOMMENDED CLAUDE ACTION:** Cherry-pick the 3 TASK-285 files (`docs/COLLISION-WALK-2026-09-25.md`, `scripts/collision_walk_report.py`, `tests/test_a_refused_domain_is_never_clear.py`) to a clean branch. Rework the tests to pin `collision_cleared()` directly. Leave the other 15+ tasks' work on separate branches.
