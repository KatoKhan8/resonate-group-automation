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
**ARTIFACT KIND:** finding (GLM independent verification review)  
**COMMIT SHA:** 368717b0d  
**FILES CHANGED:** `docs/glm-reviews/TASK-512-verify-task-404.md` (new), task file moved TODO → REVIEW  
**TESTS:** N/A (read-only verification, no code changes)

### Verification summary

1. **Artifact exists on this ref.** `docs/glm-reviews/TASK-404-verify-task-397.md` was created in commit `164c940ba` and is present at the target SHA `f1b9c357c17f4b557cbdb06f68339c7343ef3e83`.

2. **READ-ONLY claim verified.** TASK-404 correctly confirmed no provider writes on TASK-397's branch. Independent verification against current HEAD of `qwen-worker-4-r9` (`2cb8755a`) confirms zero `src/` changes and no provider write operations.

3. **Trace references verified.** All line references TASK-404 checked are accurate: `senderinventory.py:198-200` (constants), `:229-237` (li_seat_state), `:312` (daily_limit), `:208` (REMAINING_UNKNOWN), `heyreach.py:2889-2900` (_read), `:2960-2986` (li_accounts).

4. **CRITICAL FINDING: TASK-404's arithmetic verification contains errors.** TASK-404 claimed TASK-397 miscounted throttled seats (12 vs 13), but TASK-397 was right (13). TASK-404 missed seat 175552 in its recount. TASK-404's sum (229) is also wrong; actual sum is 254. TASK-397's sum (694) is also wrong. The verifier introduced defects while trying to catch the original task's defects.

5. **TASK-397's findings document existed at the reviewed commit** (`44ce1762`) but was later removed from `qwen-worker-4-r9` by subsequent rebasing. TASK-404's reference was accurate for the state it reviewed.

6. **Branch has massive scope drift.** 64 files changed, 15 in src/scripts/tests, many other tasks' work mixed in. Cherry-pick required, not merge.

### Disposition

**REWORK** — TASK-404's review is substantive and mostly accurate, but contains arithmetic verification errors that must be corrected before merge.

**Defects:**
- TASK-404 incorrectly "corrected" TASK-397's count from 13 to 12. TASK-397 was right.
- TASK-404's sum (229) is wrong. Actual: 254.
- TASK-404 missed seat 175552.

**Accurate:**
- READ-ONLY confirmation ✓
- Trace verification ✓
- Artifact existence ✓
- Overall assessment ✓

### FINDINGS

- TASK-404 produced a valid, substantive review document.
- READ-ONLY was correctly confirmed.
- Trace references are all accurate.
- **TASK-404's arithmetic verification has errors:** count should be 13 (not 12), sum should be 254 (not 229).
- TASK-397's arithmetic also has errors: sum should be 254 (not 694), naive total should be 1320 (not 1054).
- The branch has significant scope drift (64 files, many tasks). Cherry-pick TASK-404's commits only.

### RISKS

- Merging the whole branch would bring in 63 other files' changes from many other tasks.
- The arithmetic errors in TASK-404's review could mislead Claude if not corrected before integration.

### RECOMMENDED CLAUDE ACTION

1. Cherry-pick TASK-404's commits (`164c940ba`, `27fa4bc0d`) after correcting the arithmetic.
2. Correct the review document: throttled seats = 13 (not 12), sum = 254 (not 229 or 694).
3. Do not merge the whole branch.
4. If reintegrating TASK-397's findings, correct its arithmetic too (sum = 254, not 694).

### Branch HEAD SHA reviewed

`f1b9c357c17f4b557cbdb06f68339c7343ef3e83` (verified with `git rev-parse`, not assumed).
