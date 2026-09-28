PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-485 — GLM independent verification: TASK-335, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-335
    branch          origin/qwen-worker-12-r9-sync
    branch HEAD SHA 3da4a246ee2536760d04dfc4d1d94b649160c2fa

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`3da4a246ee2536760d04dfc4d1d94b649160c2fa` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`3da4a246ee2536760d04dfc4d1d94b649160c2fa` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-485-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS:** DONE
**COMMIT SHA:** `c9f05362` on `origin/qwen-worker-7-r9`
**ARTIFACT KIND:** Document (GLM verdict)

**TESTS:**
  - Verified artifact existence on target ref via `git cat-file -e` (6 checks)
  - Import checks on recovery branch: groq imports clean, contactout.linkedin_from_email present
  - `tests.test_groq_openrouter_adapters`: 19/19 pass (on recovery branch)
  - `tests.test_contactout_linkedin_from_email`: 26/26 pass (on recovery branch)
  - Production caller search: `git grep` for groq.complete and linkedin_from_email in src/ — zero callers

**FILES CHANGED:**
  - `docs/glm-reviews/TASK-485-verify-task-219.md` — verdict document (185 lines)
  - `docs/qwen-tasks/REVIEW/TASK-485-glm-verify-task-335.md` — moved from TODO

**FINDINGS:**

1. **Artifacts NOT on reviewed ref.** The branch `qwen-worker-12-r9-sync` at `3da4a246` contains NONE of the TASK-335 recovered artifacts (AUDIT doc, groq.py, openrouter.py, test files, linkedin_from_email function). The task file was moved to REVIEW but the work lives on a separate `origin/task-335-recovery` branch.

2. **groq.complete() has zero production callers.** `src/llm.py` classifies "groq" as a provider name but never imports or calls `groq.complete()`. The adapter is DISCONNECTED.

3. **linkedin_from_email has zero production callers.** `src/enrich.py` has the cost entry and route mapping but never calls `contactout.linkedin_from_email()`. The function is DISCONNECTED.

4. **Recovery branch not merged to master.** `origin/task-335-recovery` is not an ancestor of master.

5. **AUDIT document is real and complete** (on recovery branch): 700 lines, 16 sections, matches result block claims.

6. **Tests pass on recovery branch** but cannot run on the reviewed branch (files absent).

7. **No master deletions.** Only task file queue movements.

8. **Scope drift:** Branch carries 46 files / +4298/-492 from 8+ other tasks. TASK-335's only presence is the task file.

**VERDICT:** REWORK — artifacts are on the wrong branch, and both code artifacts lack production callers even on the recovery branch.

**RISKS:**
  - The AUDIT document is high-value and could be merged independently as a document-only change.
  - The groq adapter and contactout linkedin route are well-implemented and tested but orphaned.

**RECOMMENDED CLAUDE ACTION:**
  1. Merge the AUDIT document from `origin/task-335-recovery` to master (low risk, high value).
  2. Wire production callers for groq.complete() and contactout.linkedin_from_email() before merging the code artifacts.
  3. The recovery branch needs to be the merge source, not `qwen-worker-12-r9-sync`.
