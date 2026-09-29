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
- **COMMIT SHA**: b64b05e9 (verdict pushed to origin/qwen-worker-8-r9)
- **TESTS**: Read-only verification — grep-traced call chains in isolated worktree at 6aa45093
- **FILES CHANGED**: docs/glm-reviews/TASK-526-verify-task-219.md (verdict), docs/qwen-tasks/DONE/TASK-526-glm-verify-task-419.md (this file, state move TODO → DONE)
- **ARTIFACT KIND**: Document (GLM verdict)

### FINDINGS

**VERDICT: MERGE.** TASK-419's core finding is correct and verified against the exact branch HEAD at 6aa450938b035e4486a8e13096da83d0c2f0d067.

**What was verified:**
1. Branch HEAD SHA matches: `git rev-parse origin/qwen-worker-6-r9` → 6aa45093 ✅
2. All 7 named producers exist at the cited file:line locations (one minor offset: pool.sh:248 actual is 245)
3. `notify.notify()` → `plan()` chain confirmed — `notify()` never calls `deliver()`
4. `scripts/notify_deliver_loop.py` is the only automated delivery path (confirmed by grep)
5. The refusal at `notify_deliver_loop.py:106-109` checks `slack.live()` which requires BOTH `SLACK_LIVE=1` AND `SLACK_BOT_TOKEN`
6. `slack.post()` has an independent second guard raising `SlackPostingNotEnabled`
7. Queue location `work/notifications.jsonl` confirmed at `src/notify.py:299-302`

**Minor gap found:** The producer list is incomplete — 10 GLOBAL-destination producers exist, the result block names 7. Omitted: `src/web/api.py:4961` (REPORT_GENERATED), `scripts/bison_watch_loop.py:348` (CAMPAIGN_STOPPED_EXTERNALLY), `scripts/bison_watch_loop.py:438` (CAMPAIGN_BLANK_CONTENT). This does NOT change the conclusion — all 10 are blocked by the same `SLACK_LIVE` refusal.

**Deletion risk:** The branch deletes 3 TODO files (TASK-391, TASK-419, TASK-439 moved to DONE/REVIEW). Legitimate state moves. TASK-419 itself only changed its own task file.

**Scope drift:** The branch carries extensive work beyond TASK-419 (43 files, +5887/-413 lines). TASK-419's own contribution is clean — cherry-pickable as just the task file move.

- **RISKS**: If `SLACK_LIVE` is enabled without replaying the accumulated `planned` rows, the deliver loop will dump the entire backlog at once. The result block correctly identifies this and names `slack_replay_today.py` as the safe replay path.
- **RECOMMENDED CLAUDE ACTION**: Merge TASK-419. The finding is correct, the risk is documented, and the plumbing is ready pending the operator's decision on `SLACK_LIVE`.
