PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-534 — GLM independent verification: TASK-432, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-432
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

Write the verdict to `docs/glm-reviews/TASK-534-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT

**TASK:** TASK-534 — GLM independent verification of TASK-432

**STATUS:** DONE

**COMMIT:** fea91a22 (on branch `qwen-worker-3-r9-task534`)

**TESTS:** 
- 8/8 journal index tests pass on TASK-226 branch (SHA 36a4ce61)
- 18/19 journal tests pass (1 environmental failure: missing `work/` dir in worktree)
- Mutation test confirmed: first-vs-last offset mutation causes `test_index_points_at_last_entry_not_first` to fail with `AssertionError: 'verified' != 'dropped'`

**FILES CHANGED:**
- `docs/glm-reviews/TASK-534-verify-task-219.md` — the verdict

**FINDINGS:**

1. **TASK-432's verdict document exists and is accurate.** All factual claims about TASK-226 independently verified: artifact exists, production callers confirmed in `store.py` (lines 836, 1050, 1051, 1052, 1394), tests are falsifiable, no production files deleted.

2. **Mutation test is reproducible.** Performed the first-vs-last offset mutation in both `_build_index()` and `_append_locked()`. The correctness test fails for the intended reason. The consistency test does not fail (as TASK-432 noted).

3. **TASK-432's disposition (MERGE with cherry-pick) is sound.** TASK-226 artifacts exist, are consumed, have falsifiable tests, and do not delete production files. Scope drift (TASK-231 on same branch) is cleanly separable.

4. **TASK-432 is a verdict document only.** It does not carry production code. Branch `origin/qwen-worker-3-r9-task285` at `c8a62f41` contains multiple tasks (TASK-285, TASK-267, TASK-358, TASK-387, TASK-412, TASK-410, TASK-432).

5. **No production files would be deleted by merge.** `git diff --diff-filter=D` returns only task file moves (TODO → REVIEW).

**DISPOSITION: CLOSE** — TASK-432's verdict is accurate and its recommendation is sound.

**RISKS:**
- None. TASK-432 is a read-only review artifact.

**RECOMMENDED CLAUDE ACTION:**
1. Merge TASK-226 separately from TASK-231 by cherry-picking commits `590c35ef`, `a2f49494`, `67d79e49`, `8b50d8e4` from branch `qwen-worker-8-r28`.
2. Decide whether to turn QUEUE_JOURNAL on (performance case: 0.55x at 500 records).
3. Decide whether the index file needs explicit write-barrier coverage.
4. TASK-432's verdict document can be merged as-is (commit `7fee1321` on `origin/qwen-worker-3-r9-task285`) or left on the branch.
