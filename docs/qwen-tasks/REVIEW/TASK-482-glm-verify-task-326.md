PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-482 — GLM independent verification: TASK-326, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-326
    branch          origin/qwen-worker-7-r9
    branch HEAD SHA e6f3f02120df697676f18288f3e8c93ece902729

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`e6f3f02120df697676f18288f3e8c93ece902729` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`e6f3f02120df697676f18288f3e8c93ece902729` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-482-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

STATUS: REVIEW
COMMIT SHA: (see below)
TESTS:
  - tests.test_company_research_is_paid_for_once_per_account: 16/16 PASS
  - tests.test_the_second_brain_returns_only_what_the_task_needs: 24/24 PASS
  - Direct falsification of 3 core claims: all PASS
  - Mutation test (broken cache): test catches it
FILES CHANGED:
  - docs/glm-reviews/TASK-482-verify-task-326.md (CREATED — the verdict)
  - docs/qwen-tasks/TODO/TASK-482-glm-verify-task-326.md (MOVED to REVIEW/)
FINDINGS:
  1. CRITICAL — DISCONNECTED: zero production callers of secondbrain.for_account
     or secondbrain.for_contact in src/. The retrieval layer is built and tested
     but nothing in the production path uses it. grep -rn confirms empty.
  2. MINOR — No-duplication test is trivially true: for_contact returns
     "facts": [], so overlap is always empty. Cannot catch a future regression
     where facts ARE copied into the person layer.
  3. MINOR — _load_account_evidence ignores the domain parameter for fact
     content. All facts come from client ICP config, not from the prospect.
  4. INFO — Branch has 62 commits / 73 files of scope drift, but TASK-326's
     work is cleanly cherry-pickable to 2 files (+399 lines, purely additive).
  NOTE: Branch HEAD moved from e6f3f021 to 7c9f20d2. Review targeted the
  specified SHA per task instruction. Output filename in task (-task-219) was
  a template error; verdict written as TASK-482-verify-task-326.md.
RISKS:
  - Merging the whole branch would pull in 60 other commits. Cherry-pick only.
  - The code is correct but provides zero production value until wired.
RECOMMENDED CLAUDE ACTION:
  REWORK/CLOSE. The retrieval layer is correctly built. Cherry-pick the 2 files
  (fe16ec3e, 64dd1028) only if the wiring task is already queued. If not, this
  should remain REWORK until a wiring task exists with a production-caller
  acceptance criterion. Do NOT merge the whole branch.
