PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-480 — GLM independent verification: TASK-314, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-314
    branch          origin/qwen-worker-11-task314
    branch HEAD SHA ddc0bc816fed25b327cbe070d0597ba03ae2b67e

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`ddc0bc816fed25b327cbe070d0597ba03ae2b67e` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`ddc0bc816fed25b327cbe070d0597ba03ae2b67e` anyway, because that is the artifact this verdict is about.

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
5. **Would merging it DELETE anything?** `git diff master...dff854cf8fce75dfe4d6d2ed973fd68f7b8fab0e --stat`. This
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

Write the verdict to `docs/glm-reviews/TASK-480-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS**: DONE
**COMMIT SHA**: 6cb5edf7
**REMOTE**: https://github.com/KatoKhan8/resonate-group-automation.git (branch: qwen-worker-7-r9)
**TESTS**: `python -m unittest tests.test_no_cadence_step_is_silently_dropped -v` — 3 tests, all pass
**VERDICT DOCUMENT**: `docs/glm-reviews/TASK-480-verify-task-314.md`

**RECOMMENDATION**: MERGE with cherry-pick

**KEY FINDINGS**:
1. The fix TASK-314 claims is already on master (identical code at `src/cadence.py:909-910`). TASK-314's actual deliverable is the regression test alone.
2. The regression test is genuine, falsifiable, and load-bearing. I independently reverted the fix and confirmed the test catches the exact bug through the real production entry point (`cadence.build()`).
3. The test uses real fixture data, asserts on behavior (not structure), and has 38 production callers consuming the function it tests.
4. Significant scope drift: the branch carries work from 6+ tasks. Cherry-pick only `tests/test_no_cadence_step_is_silently_dropped.py` and the task file movement.
5. No deletion risk — only task files are deleted (moved from TODO to DONE/REVIEW).

**FILES CHANGED**:
- `docs/glm-reviews/TASK-480-verify-task-314.md` (new)
- `docs/qwen-tasks/DONE/TASK-480-glm-verify-task-314.md` (moved from TODO)

**RISKS**: None. The verdict is read-only analysis.

**RECOMMENDED CLAUDE ACTION**: Cherry-pick the regression test from `origin/qwen-worker-11-task314` at `ddc0bc816fed25b327cbe070d0597ba03ae2b67e`. Do not merge the whole branch — it carries 18 other files from TASK-296, TASK-364, TASK-398, TASK-413, TASK-410, and infrastructure work.
