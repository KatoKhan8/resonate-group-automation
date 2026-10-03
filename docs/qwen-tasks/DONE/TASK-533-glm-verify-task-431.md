PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-533 — GLM independent verification: TASK-431, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-431
    branch          origin/qwen-worker-7-r9
    branch HEAD SHA 8acee2e8bb6a9dc447cf7ee387888f613124cdb1

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`8acee2e8bb6a9dc447cf7ee387888f613124cdb1` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`8acee2e8bb6a9dc447cf7ee387888f613124cdb1` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-533-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- **STATUS**: DONE
- **COMMIT SHA**: 70cd55294
- **TESTS**: Verdict committed and pushed. All verification tests passed in
  isolated worktree at target SHA 8acee2e8b. Tests confirm basic TASK-219
  implementation exists (28+43+92 tests pass), but fingerprint enhancement
  TASK-431 claims to have reviewed does NOT exist at this SHA.
- **FILES CHANGED**:
  - `docs/glm-reviews/TASK-533-verify-task-431.md` - NEW, the verdict document
- **FINDINGS**:
  1. **CRITICAL DEFECT: TASK-431's verdict reviews code that does not exist at
     the commit SHA.** The verdict document exists at `8acee2e8b` on
     `qwen-worker-7-r9`, but the code it claims to have verified (`skip_subject`,
     `campaign`, `threaded_follow_up` parameters) exists only on `qwen-worker-r51`
     at `dff854cf8fce75dfe4d6d2ed973fd68f7b8fab0e`, NOT at `8acee2e8b`. The verdict
     and the code are on different branches.
  2. **The verdict is a false verification.** TASK-431 claims "All test counts
     verified. All functional claims verified." But the functional claims are about
     code that does not exist at the SHA where the verdict was committed. At
     `8acee2e8b`: `grep -rn "skip_subject" src/` returns empty, `grep -rn
     "threaded_follow_up" src/` returns empty, `fingerprint(step)` has no
     `skip_subject` parameter, `is_approved()` has no `campaign` parameter.
  3. **Basic TASK-219 implementation exists and tests pass.** The threaded
     sequence invariant (phase 1) exists at `8acee2e8b` and 28+43+92 tests pass.
     But the fingerprint enhancement (phase 2) that TASK-431 claims to have
     reviewed does NOT exist.
  4. **Scope drift is massive.** The branch has 113 files changed: 25 GLM review
     documents, 47 task files, 8 other docs, 33 source/test files. This is a GLM
     verification accumulation branch, not a single-task branch.
  5. **Merge safety verified.** Only 4 TODO task files deleted (expected). No
     conflict markers. No production code deleted.
  6. **The verdict is void.** It violates the GLM Review Protocol's core
     requirement: a verdict must review code at the SHA where it is committed, not
     code on a different branch.
- **RISKS**: Merging TASK-431's verdict without the code it reviewed would commit
  a false verification. The verdict claims to have verified code that does not
  exist at the commit SHA.
- **RECOMMENDED CLAUDE ACTION**: Do NOT merge TASK-431's verdict from
  `qwen-worker-7-r9`. If the fingerprint enhancement is still wanted, it exists
  on `qwen-worker-r51` at `dff854cf8` and a new GLM verdict should be dispatched
  against that branch. The basic TASK-219 implementation is already on master and
  does not need TASK-431's verdict.
- **VERDICT DOCUMENT**: `docs/glm-reviews/TASK-533-verify-task-431.md`
- **DISPOSITION**: **CLOSE** — TASK-431's verdict reviews code that does not exist
  at the commit SHA, making it a false verification.
