PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-471 — GLM independent verification: TASK-243, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-243
    branch          origin/qwen-worker-2-task-243
    branch HEAD SHA d0f49d12d1990264b3fc847a8b31c0b3e42fb018

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`d0f49d12d1990264b3fc847a8b31c0b3e42fb018` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`d0f49d12d1990264b3fc847a8b31c0b3e42fb018` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-471-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- STATUS: DONE
- COMMIT SHA: 88657a68 (verdict), b1a07eb7 (task move to REVIEW)
- TESTS: 24/24 TASK-243 tests pass. 218/218 affected-module tests pass.
  83 test_invariants: 3 pre-existing failures (worktree env, ProviderError
  imports, bison_campaign_id) — unrelated to TASK-243. Mutation test on
  eligibility.decide: 3 tests correctly fail when gate removed. Mutation
  test on S5 script: test PASSES with gate disabled (proves S5 test is weak).
- FILES CHANGED:
  - `docs/glm-reviews/TASK-471-verify-task-219.md` — the verdict (artifact)
  - `docs/qwen-tasks/REVIEW/TASK-471-glm-verify-task-243.md` — task moved
    from TODO to REVIEW
- ARTIFACT KIND: Document (GLM review verdict)
- FINDINGS:
  1. **S5 test is source-text, not behavioral.** `inspect.getsource` + `assertIn`
     on `clientapproval.is_approved`. Mutated the S5 script to disable the gate
     entirely (left the name in a comment) — test still passed. This is the
     exact anti-pattern CLAUDE.md warns about.
  2. **FILES FORBIDDEN violation.** `is_active()` added to `src/clientapproval.py`
     which the task says "Claude owns." The function is a reasonable helper but
     is a design decision Claude should triage.
  3. **`is_active` weakens "fail-closed" claim.** Four of five gates are dormant
     until at least one decision record exists. Before that, unapproved accounts
     pass freely. S5 is the exception — it always filters.
  4. **Scope drift.** `.qwen-TASK.err` and `.qwen-TASK.out` in the diff.
- VERDICT: **REWORK** — fix S5 test, remove scratch files, Claude decides on
  `is_active` and the fail-closed qualification.
- RISKS: None. The implementation is structurally sound; all four gates have
  real production callers and the mutation test confirms the wiring.
- RECOMMENDED CLAUDE ACTION: Triage the four findings. The S5 behavioral test
  is the most important fix.
