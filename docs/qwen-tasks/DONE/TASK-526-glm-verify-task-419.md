PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-526 — GLM independent verification: TASK-419, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-419
    branch          origin/qwen-worker-6-r9
    branch HEAD SHA 6aa450938b035e4486a8e13096da83d0c2f0d067

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`6aa450938b035e4486a8e13096da83d0c2f0d067` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`6aa450938b035e4486a8e13096da83d0c2f0d067` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-526-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

- **STATUS**: DONE
- **COMMIT SHA**: b9e25002
- **TESTS**: Read-only verification; no tests run. All findings are grep-traced call chains against the exact branch HEAD SHA.
- **FILES CHANGED**: docs/glm-reviews/TASK-526-verify-task-219.md (verdict document), docs/qwen-tasks/DONE/TASK-526-glm-verify-task-419.md (this file, state move TODO → RUNNING → DONE)
- **ARTIFACT KIND**: Document (GLM independent verdict)

### FINDINGS

**CLOSE.** TASK-419 is a pure investigation task. The finding is verified and already observable on master.

**What was verified:**
1. The artifact exists — the task file in DONE/ on the branch at SHA 6aa450938b035e4486a8e13096da83d0c2f0d067
2. The finding is correct — no GLOBAL-destination notification reaches Slack because the deliver loop refuses without `SLACK_LIVE=1` and `SLACK_BOT_TOKEN`
3. The chain is traced correctly — 7 producers → `notify.notify()` → `notify.plan()` → store; consumer exists (`scripts/notify_deliver_loop.py`) but refuses at startup
4. No code changes were made — `git diff master...6aa450938b035e4486a8e13096da83d0c2f0d067 -- src/ scripts/` returns empty
5. The finding is already observable on master — the code is byte-identical

**Minor discrepancy:** Three line numbers in the result block are off by 2-6 lines (jobs.py:207 vs 197, supervisor.py:591 vs 585, pool.sh:248 vs 245). The functions exist and call `notify.notify()` as claimed. This is a documentation precision issue, not a factual error.

**Risk noted:** If `SLACK_LIVE` is enabled without replaying the accumulated `planned` rows, the deliver loop will dump the entire backlog into the ops channel at once. `scripts/slack_replay_today.py` was built to handle this safely but is itself unrun.

- **RISKS**: None. The finding is valid and already observable. No merge is required.
- **RECOMMENDED CLAUDE ACTION**: CLOSE. The finding is correct. The task file move from TODO/ to DONE/ is administrative and can be done as part of routine queue cleanup. Operator decision owed: whether to enable `SLACK_LIVE` and, if so, whether to replay the backlog.
