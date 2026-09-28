PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-459 — GLM independent verification: TASK-310, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-310
    branch          origin/qwen-worker-11-r9
    branch HEAD SHA 39561261f0ad4dcf71817da28669022a84d77043

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`39561261f0ad4dcf71817da28669022a84d77043` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`39561261f0ad4dcf71817da28669022a84d77043` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-459-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## Result block

    STATUS: DONE
    COMMIT SHA: f9ab3957
    TESTS: 8/8 training capture tests pass. 13/13 activation refusal tests pass.
      test_invariants has 2 failures: 1 pre-existing (emailbison, confirmed
      unrelated), 1 environmental (no work/ dir in worktree). Mutation test
      confirms falsifiability.
    FILES CHANGED:
      docs/glm-reviews/TASK-459-verify-task-310.md  NEW (verdict, 227 lines)
      docs/qwen-tasks/REVIEW/TASK-459-...md  MOVED from TODO/
    FINDINGS:
      Artifact kind: verification (finding).
      Branch HEAD moved: task specified 39561261, current HEAD is c392a8ba.
      Reviewed the specified SHA as instructed.
      DISPOSITION: REWORK — DISCONNECTED.
      The training capture module (src/training.py) exists and works correctly.
      The hook in reviewapproval._capture_training() is correctly wired to
      reviewapproval.record(). Tests pass and are falsifiable (mutation test
      confirmed). BUT reviewapproval.record() has ZERO production callers.
      The production path uses reviewapproval.require() to CHECK approvals
      (bison.py:1463, bison.py:1910, heyreach.py:1725), but nothing in src/
      RECORDS approvals through reviewapproval.record(). The Slack handlers
      reference approval (step-level) and clientapproval (account-level), not
      reviewapproval.record(). Therefore training capture is DISCONNECTED from
      any production path and will never capture anything.
      This is the same defect pattern as TASK-283 (reviewed on the same branch
      by TASK-441, same REWORK verdict for the same reason) and the recurring
      defect QWEN.md warns about: "a thing computed correctly that nothing
      downstream reads."
      No deletions: merging would not delete any production files. Only task
      file moves (TODO→REVIEW/DONE).
      Scope drift: branch has 48 files changed across many tasks. TASK-310 is
      5 files, ~300 lines. Cherry-pick is straightforward.
      What must be done: wire reviewapproval.record() into the production
      approval path (Slack handler or agent tool), add a test that proves the
      wiring through the real entry point.
    RISKS:
      The artifact is safe to merge as-is (does not break anything), but is
      not functional until the production caller is wired.
    RECOMMENDED CLAUDE ACTION:
      Wire reviewapproval.record() into the production approval path, or
      decide that approval recording is manual/CLI-only and document that.
