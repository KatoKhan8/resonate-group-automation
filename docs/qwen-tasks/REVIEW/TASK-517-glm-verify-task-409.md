PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-517 — GLM independent verification: TASK-409, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-409
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

Write the verdict to `docs/glm-reviews/TASK-517-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

- **STATUS:** DONE
- **BRANCH:** `qwen-worker-7-r9`
- **COMMIT SHA:** (pending commit)
- **TESTS:** 25/25 pass on `de44644e` (the surviving TASK-294 artifact on `qwen-worker-r9-t391`); falsification confirmed (monkey-patched `identity_of` → tests fail for the intended reason)
- **FILES CHANGED:** `docs/glm-reviews/TASK-517-verify-task-219.md` (new), task file moved to REVIEW
- **ARTIFACT KIND:** Document (GLM verdict)

### FINDINGS

1. **TASK-409's revised verdict ("SAFE TO MERGE") is VOID.** It claims artifacts exist on `origin/qwen-worker-r9` — they do not. Verified with `git show origin/qwen-worker-r9:<path>` for all three files: all fatal.
2. **The artifacts exist on `qwen-worker-r9-t391`** (commit `de44644e`), not reachable from the target branch `3da4a246`.
3. **TASK-409 cited orphaned commits** (`41d2a0ba` etc.) that are not on ANY branch.
4. **The surviving implementation is sound**: 25 tests pass, identity not presence, 50-of-71 shape caught, falsification confirms wiring, `packfacts.pack_for` has production caller (`src/bisonfactory.py:559`).
5. **The original BLOCKED verdict on master was CORRECT** for this branch.
6. **Merging the target branch would not delete source code** — only task file stage movements.

### RISKS

- The TASK-294 work is real but stranded on a separate branch. It needs separate evaluation for integration.
- TASK-409's test count (32) does not match the surviving artifact (25), confirming it reviewed the orphaned version.

### RECOMMENDED CLAUDE ACTION

1. Do NOT merge TASK-409's revised verdict — it is void.
2. Evaluate TASK-294 artifacts from `qwen-worker-r9-t391` separately if integration is desired.
3. The target branch carries other work (TASK-245, TASK-355, TASK-272) that may be cherry-picked independently.
