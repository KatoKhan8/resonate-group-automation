PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-504 — GLM independent verification: TASK-387, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-387
    branch          origin/qwen-worker-3-r9
    branch HEAD SHA 6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-504-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 7e7736ac2

**TESTS:**
- Demo tests executed: `python -m unittest tests.test_task387_writeback_demo -v`
- Result: 3 tests passed in 0.182s
- Tests are falsifiable (verified by inspection)

**FILES CHANGED:**
- `docs/glm-reviews/TASK-504-verify-task-387.md` — GLM verdict (new file, 347 lines)
- `docs/qwen-tasks/DONE/TASK-504-glm-verify-task-387.md` — task file moved from TODO to DONE

**FINDINGS:**

**Critical finding: Send write-back paths are DISCONNECTED from production execution.**

The previous GLM verdict (commit 60f04b7bf) claimed all four write-back paths have production callers. This is incorrect. Independent verification found:

1. **Reply/bounce write-back: WIRED** — `poller.py:471` calls `inbound.ingest()` which is a real production caller. This path is correctly wired and automated.

2. **Send write-back (EmailBison and HeyReach): DISCONNECTED** — `confirm_email_touches()` and `confirm_touches()` are ONLY called from `leadobserve.main()` which is a CLI entry point. There are NO imports of leadobserve from other modules in src/ or scripts/. No scheduled job, no automation, no script invokes this CLI. The functions exist and work correctly, but they are not consumed by any production execution stream.

This is the "existence is not function" defect the repository warns about. A CLI that must be manually invoked is not a production caller.

**Other findings:**
- Artifact exists at the exact SHA (6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c)
- All four write-back paths exist at claimed file:line locations
- Demo tests are falsifiable and would catch regressions
- Branch has moved from target SHA (current HEAD: c725f9bc3893234221f716e5a557fa77c5a9e3b0)
- Branch carries 86 commits and 100 files from many tasks (massive scope drift)
- TASK-387 itself is clean (one test file + task file)
- Merging would not delete production code (only task files moving between queues)

**DISPOSITION: REWORK** (partial — send write-back paths are DISCONNECTED)

**Reason:** The trace findings are correct and the demo test is a useful addition, but the task must acknowledge that send write-back is DISCONNECTED from production execution. Either:
- Wire `confirm_email_touches()` and `confirm_touches()` into an automated reconciliation loop (e.g., the poller or a scheduled job), OR
- Explicitly state in the result block that send write-back exists but is CLI-only and not automated

**RISKS:**
- The previous GLM verdict miscounted production callers and recommended MERGE based on incorrect analysis
- If merged as-is, the send write-back gap will remain undiscovered
- The queue will not automatically know about provider-confirmed sends unless a human manually runs the CLI

**RECOMMENDED CLAUDE ACTION:**
- Review the verdict at `docs/glm-reviews/TASK-504-verify-task-387.md`
- Decide whether to wire send write-back into production or explicitly acknowledge the gap
- Do not merge TASK-387 until the send write-back disconnect is resolved
- Cherry-pick only TASK-387's commits (5d88cf82, f5db204e, c0ebd287, 342c3211), not the entire branch
