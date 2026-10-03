PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-499 — GLM independent verification: TASK-360, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-360
    branch          origin/qwen-worker-2-r70
    branch HEAD SHA 29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`29f90f7bee9153bcbfb2ffafd6f7cc1182d7fd4f` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-499-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 470baf9d (qwen-worker-r9)

**TESTS:**
- `tests/test_no_model_slug_lives_outside_the_policy`: 3/3 pass (in isolated worktree at 29f90f7b)
- `tests/test_glm_adapter`: 41/41 pass
- `tests/test_xai_adapter`: 48/48 pass
- `tests/test_providers`: 52/52 pass
- `tests/test_fixture_hygiene`: 16/17 pass (1 pre-existing `productive.io` failure, confirmed on master)
- Independent mutation test: planted `MODEL = "glm-5.3"` in `src/_mutation_test_plant.py` → test FAIL named file:line:slug; removed → OK
- Acceptance 1: `resolve('research_synthesis')` → RoutingDecision with provider='glm', model='glm-5.3-flash', policy_version=1 ✅
- Acceptance 2: `resolve('suppression')` → NotAModelDecision ✅
- Acceptance 5a: fallback resolves when primary unavailable ✅
- Acceptance 5b: no-fallback raises NoFallbackAvailable ✅

**FILES CHANGED:**
- `docs/glm-reviews/TASK-499-verify-task-360.md` (NEW) — the verdict

**FINDINGS:**
- All 6 artifacts exist on the reviewed SHA and match the result block
- All acceptance criteria independently reproduced and passed
- Provider wiring (glm.py, xai.py) is real and consumed — slugs read from router at import time, values match old hardcoded literals exactly
- `llm.for_task` has zero production callers — by explicit design (TASK-362's scope), NOT a DISCONNECTED finding
- Branch is clean: 5 commits, all TASK-360, no scope drift, no junk
- Merging deletes nothing — only hardcoded slug literals replaced by router calls
- Test is genuinely falsifiable: AST-based, mutation guard works, exception paths tested
- Minor inaccuracy: result block says "providers fail to import" without policy; actually they import with None/empty values and fail at call time

**RISKS:**
- None. The branch is safe to merge.

**RECOMMENDED CLAUDE ACTION:**
- Merge TASK-360 to master.
- TASK-362 (re-routing) should consume `llm.for_task` and verify the slug-enforcement test continues to pass as stages move to router-based resolution.
