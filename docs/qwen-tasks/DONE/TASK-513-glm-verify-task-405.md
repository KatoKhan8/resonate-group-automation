PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-513 — GLM independent verification: TASK-405, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-405
    branch          origin/qwen-worker-12-r9-sync
    branch HEAD SHA 3da4a246ee2536760d04dfc4d1d94b649160c2fa

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`3da4a246ee2536760d04dfc4d1d94b649160c2fa` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`3da4a246ee2536760d04dfc4d1d94b649160c2fa` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-513-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT

**STATUS**: DONE  
**COMMIT SHA**: 9d095ba8e
**TESTS**: N/A (read-only verification task)
**FILES CHANGED**: docs/glm-reviews/TASK-513-verify-task-405.md (added)

**FINDINGS**:

1. **TASK-405's technical finding is CORRECT.** Contact-key validation is centralized in `identity.contact_key()` (generation), `store._identity_problems()` (validation), and `store.patch()` (enforcement). All 9 identity tests pass. No inconsistency exists. No code change is needed.

2. **TASK-405's provenance claim is WRONG.** The verdict says "TASK-389 never started" and "No commits on any branch reference TASK-389 doing work." This is factually incorrect. TASK-389 did work:
   - Commit `d18ae03d8` on `qwen-worker-7-r9-task518`: "TASK-389: contact-key guard trace complete, no inconsistency found"
   - Commit `818ad59ec`: "TASK-389: claim contact-key guard cleanup"
   - TASK-505 (commit `e0ae599b0`) is a GLM verdict on TASK-389 saying MERGE
   
   TASK-389's work is not on master and not on the reviewed branch, but it exists.

3. **TASK-389 and TASK-394 reached the same conclusion independently.** Both traced contact_key validation and found no inconsistency. This is independent confirmation, not duplication.

4. **The branch has significant scope drift.** 46 files changed, but TASK-405's own contribution is 2 files (verdict document). Cherry-pick commit 9e607efdb in isolation.

5. **Merging would not delete content.** The 6 task files "deleted" from TODO/ are moved to REVIEW/DONE/BLOCKED/ — expected state transitions.

**VERDICT**: MERGE (cherry-pick with provenance correction)

**RECOMMENDED CLAUDE ACTION**:

1. Cherry-pick commit 9e607efdb (TASK-405 verdict) from origin/qwen-worker-12-r9-sync
2. Correct the provenance record: TASK-389 did work (commit d18ae03d8)
3. Decide TASK-389 vs TASK-394 disposition (both did the work, both reached the same conclusion)
4. Consider merging TASK-389's verdict as well (from qwen-worker-7-r9-task518)
5. Do NOT merge the other 44 files from this branch without reviewing their own tasks

**RISKS**: None for the technical finding. The provenance error is a documentation issue, not a technical defect.

**ARTIFACT TYPE**: Document (GLM verdict)
