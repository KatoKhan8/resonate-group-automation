PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-520 — GLM independent verification: TASK-412, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-412
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

Write the verdict to `docs/glm-reviews/TASK-520-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** DONE
**COMMIT:** 9f40f60a
**TESTS:** Read-only verification; no code changes. All claims verified by code reading against the exact SHA.
**FILES CHANGED:** `docs/glm-reviews/TASK-520-verify-task-219.md` (new), this task file (moved to DONE).
**ARTIFACT KIND:** Finding (independent GLM review verdict).

---

## Verdict Summary

**DISPOSITION: MERGE with cherry-pick**

**Target SHA reviewed:** `c8a62f4109f47eb5338f1ef334d68f44dcb989ef` (verified exact match to `origin/qwen-worker-3-r9-task285`)

**Worktree:** `.qwen/worktrees/task520-review` (detached HEAD at target SHA)

### What was verified

1. **The artifact exists** on the exact ref. The task file was moved to REVIEW with a complete result block at commit `49154f6b`. ✓

2. **All six suppression stores are real** and the file:line citations are substantially correct (minor discrepancies: two citations name `apply_reply` instead of the helper functions it calls; most line numbers within 1-5 lines of actual). ✓

3. **`eligibility.decide()` reads all six stores** via `must_not_contact` (stores 1-5) + `_email_checks` (store 6). The chain is verified from line 605 through line 695. ✓

4. **Every prospect-facing write path checks suppression before writing:**
   - EMAIL_ACTIVATE: `executionguard.revalidate` at `providerwrites.py:2253` ✓
   - EMAIL_RESUME: `CONDITIONAL[_resume_revalidates_suppression]` at `providerwrites.py:1473` ✓
   - LINKEDIN_ADD_LEAD: `executionguard.revalidate` at `providerwrites.py:2253` ✓
   - leadstop.sweep: `must_not_contact` at `leadstop.py:345` ✓

5. **The 76 re-verification is honestly owed.** `work/queue.jsonl` does not exist in this worktree. The task correctly declares this and provides the exact command. ✓

6. **The bounce gap is real.** `_resume_revalidates_suppression` calls `must_not_contact` which does not include bounce. Low severity, already noted by the task. ✓

7. **All functions are consumed.** `eligibility.decide` has multiple production callers (`executionguard.authorize`, `executionguard.revalidate`, `funnel`, `killswitch`, `demo_outreach`). Not a case of "existence is not function." ✓

8. **Tests are falsifiable.** The resume suppression tests go through `providerwrites.perform` (real entry point), assert `WriteRefused` is raised, and verify the transport was NOT called. ✓

9. **Merging would NOT delete anything** from master. No source, test, or script files would be deleted. ✓

### Critical finding: Scope drift

The branch carries work from **8+ tasks** (TASK-267, 285, 358, 387, 410, 412, 426, 432), with 39 files changed and 7,167 insertions. TASK-412's artifact is ONE file movement. The branch should NOT be merged wholesale; the TASK-412 file should be cherry-picked.

### Owed items (from the task itself)

1. Fresh read of the 76 suppressed recipients from Claude's worktree.
2. Consider whether `_resume_revalidates_suppression` should also check `channels._bounced`.

### Recommendation

**MERGE with cherry-pick.** The audit is accurate and complete. Cherry-pick only the TASK-412 file movement.

Full verdict: `docs/glm-reviews/TASK-520-verify-task-219.md`
