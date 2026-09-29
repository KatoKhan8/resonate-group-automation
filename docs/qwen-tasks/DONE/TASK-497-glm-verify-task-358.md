PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-497 — GLM independent verification: TASK-358, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-358
    branch          origin/qwen-worker-3-r9-task285
    branch HEAD SHA c8a62f4109f47eb5338f1ef334d68f44dcb989ef

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`c8a62f4109f47eb5338f1ef334d68f44dcb989ef` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`c8a62f4109f47eb5338f1ef334d68f44dcb989ef` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-497-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: e7e73896 (verdict committed and pushed on qwen-worker-3-r9)
TESTS: N/A — read-only review task. Mutation test performed on worktree: 8/10 tests
  fail when CheapVerifier registration is removed, for the correct reason
  (WaterfallViolation). 10 tests pass on the branch at c8a62f41.

FILES CHANGED:
  docs/glm-reviews/TASK-497-verify-task-219.md   NEW — the verdict

FINDINGS:
  1. BRANCH HEAD SHA VERIFIED: c8a62f4109f47eb5338f1ef334d68f44dcb989ef matches
     the task file. Branch has not moved.

  2. ARTIFACT EXISTS AND REGISTRATION IS CORRECT: cheapverifier.py (1,141 lines)
     imports cleanly. waterfall.py registers it second in EMAIL_VERIFICATION
     (after ContactOut). enrich.py has COSTS and CALL_STAGE entries. describe()
     reports: ['contactout', 'cheapverifier', 'deliverable', 'reoon'].

  3. TESTS ARE FALSIFIABLE: mutation test (removing the registration) causes
     8/10 tests to fail with the exact WaterfallViolation the task claims to fix.
     The 2 that still pass are independent checks (COST_UNITS and ContactOut-first).

  4. ZERO PRODUCTION CALLERS — DISCONNECTED: no file in src/ imports cheapverifier.
     verification.py (the dispatch module) was NOT modified on this branch. The
     other verifiers (deliverable, reoon) ARE imported and called there. The task's
     claim that "this is the same state as the other verifiers before they were
     wired" is factually wrong.

  5. SCOPE DRIFT: the branch carries 6 other tasks (TASK-267, 285, 387, 412, 426,
     432). TASK-358's files are 5 specific paths that would need cherry-picking.

  6. NO DELETIONS: merging would not delete any production code in src/.

  7. TEST COUNT DISCREPANCY: result block claims 12 tests, file contains 10.

RISKS:
  - The registration is safe and non-destructive but non-functional. No production
    code path can reach CheapVerifier through verification.call().
  - The branch carries significant scope drift from 6 other tasks.

RECOMMENDED CLAUDE ACTION:
  REWORK. The standing rule applies: "Zero production callers means DISCONNECTED,
  which is a rework and not a merge." Wiring into verification.py is owed. The
  registration alone is safe to cherry-pick if Claude wants to stage it separately.
  Verdict artifact: docs/glm-reviews/TASK-497-verify-task-219.md
