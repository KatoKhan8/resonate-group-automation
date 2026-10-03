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
COMMIT SHA: dea2e132 (verdict committed and pushed)
TESTS: Verified TASK-358's claims independently:
  - cheapverifier.py imports correctly ✓
  - Waterfall registration correct (ContactOut first, CheapVerifier second) ✓
  - enrich.py COSTS and CALL_STAGE entries present ✓
  - 10 tests in test_cheapverifier_is_part_of_the_waterfall.py all pass ✓
  - record_step does not raise WaterfallViolation ✓
  - spend() sees the CheapVerifier row ✓
  FILES CHANGED:
  - docs/glm-reviews/TASK-497-verify-task-358.md (NEW - verdict document)

FINDINGS:
  1. DISCONNECTED: Zero production callers exist. grep for "cheapverifier.verify|cheapverifier.stored_lookup" in src/ returns zero matches outside cheapverifier.py itself. The module exists, the waterfall knows it, but no production code path calls it. This is the exact defect CLAUDE.md warns against: "Existence is not function... Zero production callers means DISCONNECTED, which is a rework and not a merge."
  
  2. The task's own result block admits this: "CheapVerifier is registered but NOT wired into any caller in src/. The module exists, the waterfall knows it, but no production code path calls verify_single() through the waterfall. This is the same state as the other verifiers before they were wired - the registration is necessary but not sufficient."
  
  3. SCOPE DRIFT: The branch carries 21 commits from 7 other tasks (TASK-267, TASK-285, TASK-387, TASK-412, TASK-426, TASK-432, TASK-410). Only 5 files belong to TASK-358. Merging the entire branch would introduce unrelated changes. Cherry-pick by path.
  
  4. Test count discrepancy: Result block claims 12 tests, file contains 10. Minor, but noted.

RISKS:
  - Low risk. The registration is correct and does not break anything. But merging a disconnected component sets a bad precedent and adds 1,141 lines of dead code.
  - The branch carries scope drift from 6 other tasks. Merging the entire branch would pollute master with unrelated work.

RECOMMENDED CLAUDE ACTION:
  REWORK. Cherry-pick ONLY the TASK-358 files (cheapverifier.py, waterfall.py registration, enrich.py COSTS/CALL_STAGE, test file, cassettes). Create a follow-up task to wire CheapVerifier into the production call path (validate.py or enrich.py). The follow-up task must prove the wiring with a test that fails when the call site is deleted. Do NOT merge the entire branch.
