PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-525 — GLM independent verification: TASK-418, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-418
    branch          origin/qwen-worker-r9-t391
    branch HEAD SHA d4effa8d82c50fc4166fd6e6780f069d728eda00

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`d4effa8d82c50fc4166fd6e6780f069d728eda00` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`d4effa8d82c50fc4166fd6e6780f069d728eda00` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-525-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

**STATUS:** REVIEW  
**ARTIFACT KIND:** finding (GLM independent verification verdict)  
**COMMIT SHA:** f45b1fa2d828fa872261b6725fd0d938585f715b (pushed to origin/qwen-worker-10-r9)  
**TESTS:** n/a (read-only review)  
**FILES CHANGED:** docs/glm-reviews/TASK-525-verify-task-219.md

### Summary

Reviewed branch `origin/qwen-worker-r9-t391` at exact SHA `d4effa8d82c50fc4166fd6e6780f069d728eda00` in isolated worktree `worktree-glm-525-review`.

**DISCREPANCY:** Task file names TASK-418, but branch HEAD is TASK-391. Branch carries both tasks' artifacts plus 6+ other tasks' work (scope drift).

### Findings

**TASK-391 (skills wired into generate.py): MERGE**
- Artifact exists: `src/generate.py` + 267-line sentinel test file
- Production callers: 6 (`render_prompt()` calls at lines 1422, 1525, 1538, 1548, 1579, 1663)
- Falsifiable: mutation test (disabled `_STAGE_TO_SKILL` mapping) confirmed tests fail for the right reason
- Tests drive real entry point: `generate.draft()` and `generate.linkedin_note()`, not direct skill calls
- Isolated: 2 files, +305 lines, no dependencies

**TASK-418 (offer config audit): MERGE**
- Artifact exists: task file moved to DONE with 12-check result table
- Spot-check: 3 of 12 checks independently verified (CTA link consistency, composes references, file length)
- Audit was performed, not fabricated
- Isolated: task file move only, no code changes

**Branch scope drift: DO NOT MERGE AS-IS**
- 46 files changed, +5285/-212 lines
- Carries work from TASK-271, TASK-294, TASK-302, TASK-311, TASK-391, TASK-418, TASK-463, TASK-464
- TASK-302 task file deleted (lifecycle violation: not moved to DONE/REVIEW/BLOCKED)
- Recommendation: cherry-pick TASK-391 (d4effa8d) and TASK-418 (d2637481) individually

### Verdict

Both artifacts under review are correct, consumed, and falsifiable. Branch should not be merged as-is due to scope drift. Cherry-pick the two commits individually.

**FINDINGS:** Two mergeable artifacts (TASK-391, TASK-418), one scope-drift warning  
**RISKS:** Branch carries 8+ tasks' work; TASK-302 lifecycle anomaly  
**RECOMMENDED CLAUDE ACTION:** Cherry-pick d4effa8d (TASK-391) and d2637481 (TASK-418) individually. Investigate TASK-302 deletion.
