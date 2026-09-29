PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-512 — GLM independent verification: TASK-404, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-404
    branch          origin/qwen-worker-9-r9
    branch HEAD SHA f1b9c357c17f4b557cbdb06f68339c7343ef3e83

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`f1b9c357c17f4b557cbdb06f68339c7343ef3e83` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`f1b9c357c17f4b557cbdb06f68339c7343ef3e83` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-512-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** finding (independent GLM verification review)
**COMMIT SHA:** (pending commit)
**FILES CHANGED:** `docs/glm-reviews/TASK-512-verify-task-219.md` (new), task file moved TODO → REVIEW

### Summary

TASK-404 is a GLM verification of TASK-397 (HeyReach seat-cap check). The
verdict document exists on the branch at `f1b9c357` but verifies phantom state:

1. **The artifact TASK-404 verified does not exist on any current branch.**
   `docs/TASK-397-SEAT-CAP-FINDINGS.md` exists only at orphaned commit
   `44ce1762` (unreachable from any ref). It was lost when `qwen-worker-4-r9`
   was rebased past that commit.

2. **The verdict was written for a different branch/commit** (`qwen-worker-4-r9`
   at `44ce1762`) than the branch it sits on (`qwen-worker-9-r9` at `f1b9c357`).

3. **The verdict's arithmetic "correction" is itself wrong.** It claimed TASK-397
   miscounted throttled seats (said 12, not 13; sum 229, not 694). Independent
   re-count from the source table at orphaned commit `44ce1762` confirms
   TASK-397 was correct: 13 seats, sum 694. The verdict missed seat 175552.

4. **READ-ONLY was honored** and **trace references are accurate** against master,
   but these describe existing code, not task work.

### Disposition

**REWORK.** Do not merge the TASK-404 verdict as evidence of a verified
investigation. The investigation it verified no longer exists on any reachable
branch. Recover `docs/TASK-397-SEAT-CAP-FINDINGS.md` from orphaned commit
`44ce1762` or re-run via TASK-413/TASK-422.

### FINDINGS

- The TASK-397 findings document is orphaned (exists only at unreachable commit `44ce1762`).
- The TASK-404 verdict reviews phantom state — recommends cherry-picking a file that exists on no current branch.
- The verdict's arithmetic re-check introduced the error it claimed to find.
- READ-ONLY was honored on both branches.
- Trace references are accurate against master.
- Branch has 64 changed files (substantial scope beyond TASK-404).
- Merging would delete only two TODO files (moved to REVIEW, not lost).

### RISKS

- The orphaned commit `44ce1762` may be garbage-collected. Recover the findings document before that happens if the data is wanted.
- The seat-cap data is now 8 days old (was 6 days old when written).

### RECOMMENDED CLAUDE ACTION

1. Do not merge TASK-404 verdict as-is.
2. Recover `docs/TASK-397-SEAT-CAP-FINDINGS.md` from `44ce1762` or re-run TASK-413/TASK-422.
3. Drop the arithmetic reservation — TASK-397's numbers were correct.
