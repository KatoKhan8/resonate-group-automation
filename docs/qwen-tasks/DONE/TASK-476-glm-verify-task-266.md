PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-476 — GLM independent verification: TASK-266, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-266
    branch          origin/qwen-worker-r58
    branch HEAD SHA cf1515fb40730ba47dd134bb54a3ebaceabd5d32

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`cf1515fb40730ba47dd134bb54a3ebaceabd5d32` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`cf1515fb40730ba47dd134bb54a3ebaceabd5d32` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-476-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 77b0429c

**TESTS:**
- 25 tests in `tests/test_learningrules.py` — all pass
- Mutation test: `approve()` replaced with no-op → test fails as expected (mutation killed)
- `test_invariants` run: 1 pre-existing failure (emailbison), 1 worktree environment error — neither caused by TASK-266

**FILES CHANGED:**
- `docs/glm-reviews/TASK-476-verify-task-266.md` — verdict document

**FINDINGS:**

1. **Artifact exists and does what it claims.** `src/learningrules.py` (263 lines) implements the A/B/C scheme with closed vocabulary, approval guard, and consumer check. All 25 tests pass. VERIFIED.

2. **Zero production callers — DISCONNECTED.** `git grep "learningrules" cf1515fb -- src/ scripts/` returns zero hits. No production code imports or references the module. The task explicitly chose not to wire it ("do not wire it up"), but the repository rule applies: zero production callers means DISCONNECTED, which is a rework.

3. **Tests are falsifiable.** Mutation test: replaced `approve()` with a no-op → test correctly fails. The tests assert on behavior, not source text. VERIFIED.

4. **`mark_approved()` can bypass the approval guard.** `approve()` raises unconditionally (the guard), but `mark_approved()` can set status to APPROVED without raising. The success path is not directly tested. This is a potential bypass when the module is wired. FINDING.

5. **Merging would not delete anything.** All three files are additions (573 insertions, 0 deletions). VERIFIED.

6. **No scope drift.** Branch carries exactly three files, all named by the task. VERIFIED.

7. **`learning.boost()` classification is correct.** Zero production callers, correctly classified as "a B that was never promoted." VERIFIED.

**RISKS:**
- The module is disconnected by design. The task's scope was to build the shape, not connect it. But the repository rule treats zero callers as a rework, not a merge.
- `mark_approved()` is a potential bypass of the approval guard. When the module is wired, this needs to be addressed.

**RECOMMENDED CLAUDE ACTION:**
- REWORK: wire `learningrules` into at least one consumer (e.g., `behind()` called by a copy/ICP/routing reader).
- Test `mark_approved()` success path and decide whether it is a bypass or a seam.
- Then merge.

**DISPOSITION:** REWORK

The work is correct, the tests are meaningful, and the module does what it claims. But it is DISCONNECTED: zero production callers, no consumer, no downstream effect. The module is the same shape as the defect it identifies: a thing computed correctly that nothing downstream reads.
