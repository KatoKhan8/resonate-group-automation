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
COMMIT SHA: 6c8f3b5d4 (GLM verdict committed and pushed to qwen-worker-10-r9)
TESTS: N/A (read-only review, no code changes)
ARTIFACT: docs/glm-reviews/TASK-497-verify-task-219.md (code review finding)

FILES CHANGED:
  docs/glm-reviews/TASK-497-verify-task-219.md    NEW - GLM verdict document

FINDINGS:
  1. DISPOSITION: REWORK — DISCONNECTED. CheapVerifier is registered in the
     waterfall but has zero production callers. src/verification.py does not
     import it, does not list it in verifiers(), and does not invoke it. The
     module exists, the waterfall knows about it, the tests pass, but no
     production code path calls cheapverifier.verify_single() through the
     waterfall. This is the exact defect documented in QWEN.md: "Existence is
     not function... a thing computed correctly that nothing downstream reads."

  2. Artifact exists and is partially verified:
     - src/providers/cheapverifier.py (1,142 lines) cherry-picked correctly
     - src/waterfall.py registers CheapVerifier second in EMAIL_VERIFICATION
     - src/enrich.py adds COSTS and CALL_STAGE entries
     - tests/test_cheapverifier_is_part_of_the_waterfall.py has 10 tests, all green
     - Waterfall order is correct: ['contactout', 'cheapverifier', 'deliverable', 'reoon']
     - ContactOut is first (PROVIDER-ROUTING-POLICY.md invariant holds)

  3. Tests are not falsifiable: The tests prove registration but not consumption.
     They call record_step() directly but never call verification.verify(), which
     is the production entry point. A mutation test that deletes the CheapVerifier
     entry from verification.verifiers() (which does not exist) would still pass
     the tests. The tests are testing the wrong seam.

  4. Scope drift confirmed: The branch carries work from TASK-285, TASK-267,
     TASK-358, TASK-387, TASK-412, TASK-410, TASK-426, and TASK-432. Total scope:
     39 files changed, 7,167 insertions(+), 223 deletions(-). Only 15 files are
     TASK-358 specific (cheapverifier module, waterfall/enrich modifications,
     test file, 10 cassettes). Do not merge the branch; cherry-pick only the
     TASK-358 files.

  5. Merging would not delete anything: The deletions are task files moving from
     TODO to REVIEW (renamed/moved). No production code would be deleted.

  6. The result block's FINDINGS section is accurate: It correctly identifies
     that CheapVerifier is registered but not wired into any caller. However, it
     classifies this as a RISK rather than a blocker. This is the defect.

RECOMMENDED CLAUDE ACTION:
  REWORK. Cherry-pick only the TASK-358 files to a clean branch:
  - src/providers/cheapverifier.py (new file)
  - src/waterfall.py (modifications)
  - src/enrich.py (modifications)
  - tests/test_cheapverifier_is_part_of_the_waterfall.py (new file)
  - tests/cassettes/cheapverifier/* (10 new files)

  Then add the missing wiring in src/verification.py:
  - Import: from .providers import contactout, deliverable, reoon, cheapverifier
  - Add to verifiers(): return {..., "cheapverifier": cheapverifier}
  - Add to CALL_NAMES: "cheapverifier": "cheapverifier-verify"
  - Add to LEDGER_REASONS: "cheapverifier": "verification_contradiction"
  - Add a branch in call() for provider == "cheapverifier"

  Add a test that calls verification.verify() and asserts CheapVerifier is invoked.
  Re-run the full suite. Then this is MERGE-ready.

RISKS:
  - The branch has significant scope drift and should not be merged as-is.
  - The CheapVerifier registration is disconnected from the production caller
    chain and will not be invoked until verification.py is updated.
  - The tests pass but do not prove the production chain is connected.

VERIFICATION:
  Branch reviewed: origin/qwen-worker-3-r9-task285
  Branch HEAD SHA: c8a62f4109f47eb5338f1ef334d68f44dcb989ef (verified with git rev-parse)
  TASK-358 artifact commit: e19b7b94b (move to REVIEW)
  Core work commit: b27c8452b (cherry-pick)
  Enrich fix commit: 5f6d83d78 (COSTS/CALL_STAGE registration)
  Worktree: glm-verify-task-358 (detached HEAD at c8a62f41)
  Review date: 2026-10-12
  Reviewer: GLM (independent verification layer)
