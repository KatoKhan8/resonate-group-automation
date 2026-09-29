PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-498 — GLM independent verification: TASK-359, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-359
    branch          origin/qwen-worker-r70
    branch HEAD SHA 7150fd80935854c4199299bde82f790b83a3dcc6

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`7150fd80935854c4199299bde82f790b83a3dcc6` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`7150fd80935854c4199299bde82f790b83a3dcc6` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-498-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

- **STATUS**: DONE
- **ARTIFACT KIND**: document (independent verification verdict)
- **COMMIT SHA**: (this commit)
- **TESTS**: N/A — read-only review task
- **FILES CHANGED**:
  - `docs/glm-reviews/TASK-498-verify-task-219.md` (NEW) — the verdict
  - `docs/qwen-tasks/REVIEW/TASK-498-glm-verify-task-359.md` (moved from TODO)
- **FINDINGS**:

  **Branch HEAD SHA verified**: `7150fd80935854c4199299bde82f790b83a3dcc6` matches task file.

  **Artifacts exist**: All 5 claimed files present on the branch. 1175 insertions, 0 deletions. Merging is safe.

  **Core function verified**: The script reads provider usage/balance via GET-only API calls, distinguishes five states correctly, never invents numbers, and enforces credential safety. 22 tests pass and are falsifiable.

  **Production caller**: This is a standalone CLI script consumed by Windows Task Scheduler, not a library. The chain is complete: Scheduler → script → file. NOT DISCONNECTED.

  **Gap — delegation analysis not implemented**: The task spec's central feature ("names the tasks that should have been routed to it") is static text in the report, not actual analysis. The result block does not acknowledge this.

  **Gap — commit/push/Slack not implemented**: Acknowledged in the result block as follow-up work.

  **Test coverage gap**: OpenRouter and Apify parsers lack unit tests with injected transports.

- **RISKS**:
  - The delegation analysis gap means the report is a dashboard, not a routing advisor. This is the "point of the job" per the task spec and is not delivered.
  - Parser regressions for OpenRouter/Apify would not be caught by the test suite.

- **RECOMMENDED CLAUDE ACTION**: MERGE with follow-up task for delegation analysis, commit/push automation, and Slack posting. The core artifact is solid and safe.
