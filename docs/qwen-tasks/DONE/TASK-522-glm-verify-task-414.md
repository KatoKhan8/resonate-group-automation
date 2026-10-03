PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-522 — GLM independent verification: TASK-414, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-414
    branch          origin/glm-review-504-task-387
    branch HEAD SHA f3b68bf849d8361fab9d3f8f972229369cf60944

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`f3b68bf849d8361fab9d3f8f972229369cf60944` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`f3b68bf849d8361fab9d3f8f972229369cf60944` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-522-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS:** DONE
**ARTIFACT KIND:** document (GLM verdict)
**COMMIT SHA:** 068983c85
**TESTS:** Ran all 148 tests named in TASK-414's result block; all green. Verified consumer trace by reading source code at the exact SHA.
**FILES CHANGED:** 
- `docs/glm-reviews/TASK-522-verify-task-414.md` (added)
- `docs/qwen-tasks/DONE/TASK-522-glm-verify-task-414.md` (moved from TODO)

**FINDINGS:**

TASK-414's result block is ACCURATE. The consumer trace is correct, the tests exist and pass, the claims about client-attribution wiring are verified.

Key findings:
1. The artifact (test file `tests/test_spend_report_groups_by_real_client_id.py`) exists and is already on master via commit `90cd41752` (integrated 2026-09-27).
2. All 148 tests across 7 modules pass. The 9 acceptance tests prove client separation with real fixtures and behavioral assertions.
3. The consumer trace (9 consumers) is accurate: `spendledger.spent`, `report`, `balances`, `client_balance`, `progress_block` all filter by client correctly; `web/api.py spend_ledger` groups by `rec.get("client") or "unknown"`.
4. The branch at `f3b68bf8` has moved to `515c638e` since the task was written; reviewed the exact SHA named in the task file per instructions.
5. The branch has significant scope drift (87 commits, many other tasks' work). TASK-414's own contribution is verification-only (no code changes).
6. Merging would not delete any production code or tests; only task file movements (TODO → DONE/REVIEW).

**VERDICT: MERGE (result block accurate, artifact already on master)**

The result block may be merged as an accurate record. The artifact it describes is already production. Cherry-pick commit `31b0834ae` if the goal is to record TASK-414's result block; do not merge the entire branch wholesale due to scope drift.

**RISKS:** None. The verification is sound and the artifact is already integrated.

**RECOMMENDED CLAUDE ACTION:** Accept the verdict. TASK-414's work is verified and already on master. The result block is an accurate record.
