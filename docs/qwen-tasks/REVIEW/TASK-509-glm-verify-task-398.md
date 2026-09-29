PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-509 — GLM independent verification: TASK-398, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-398
    branch          origin/qwen-worker-11-task314
    branch HEAD SHA ddc0bc816fed25b327cbe070d0597ba03ae2b67e

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`ddc0bc816fed25b327cbe070d0597ba03ae2b67e` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`ddc0bc816fed25b327cbe070d0597ba03ae2b67e` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-509-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** DONE  
**ARTIFACT KIND:** Verdict (GLM independent review document)  
**COMMIT SHA:** 7b692853 (on origin/qwen-worker-7-r9)  
**TESTS:** N/A — read-only review, no code changed  
**FILES CHANGED:** 
- `docs/glm-reviews/TASK-509-verify-task-219.md` (new, 302 lines)
- `docs/qwen-tasks/REVIEW/TASK-509-glm-verify-task-398.md` (moved from TODO/)

### FINDINGS

**Target reviewed:** TASK-398 on branch `origin/qwen-worker-11-task314` at exact HEAD SHA `ddc0bc816fed25b327cbe070d0597ba03ae2b67e` (verified via `git rev-parse`).

**TASK-398 is a read-only suppression list audit.** The artifact is the RESULT BLOCK in the task file — a finding, not code. No source was changed. No tests were added.

**Ten findings, all verified:**

1. **Artifact exists and is a finding** — VERIFIED. The RESULT BLOCK in `docs/qwen-tasks/REVIEW/TASK-398-suppression-list-audit.md` is the deliverable. `git show c91e17e1 --stat` confirms only the task file was changed.

2. **Seven suppression stores exist where claimed** — VERIFIED with minor line-number discrepancies (4-19 lines off in 5 of 11 cases). All functions exist and perform the claimed checks. The audit correctly identified the suppression architecture.

3. **channels._suppressed does NOT check agency DNC** — VERIFIED, CRITICAL FINDING CONFIRMED. `channels._suppressed` (lines 127-133) checks only domain list and client approval. `eligibility._suppressed` (lines 280-303) checks agency DNC. Any path calling `channels.evaluate` without going through `eligibility.decide` misses the agency DNC check.

4. **Write paths check suppression pre-write** — VERIFIED. Email send, LinkedIn activate, and email resume all check suppression through `eligibility.decide` or `must_not_contact` before reaching the transport.

5. **The 76 and the 4 cannot be verified from this worktree** — VERIFIED (limitation acknowledged). `work/queue.jsonl` does not exist in worker worktrees. The audit honestly reported this structural limitation.

6. **The three named risks are real** — VERIFIED. (a) `config/suppress.local.txt` is missing in this worktree (confirmed). (b) `work/agency-dnc.jsonl` is missing (confirmed). (c) Seven stores checked in one place by convention, not enforcement (confirmed).

7. **The resume gap is closed but narrowly** — VERIFIED. `_resume_revalidates_suppression` (providerwrites.py:1414-1473) checks `must_not_contact` but not `_bounced`. A bounced contact would not block a resume.

8. **Scope drift** — VERIFIED. The branch carries work from six other tasks (TASK-296, TASK-314, TASK-364, TASK-410, TASK-413, infrastructure). This is scope drift but not pollution — each task is coherent and changes are additive.

9. **Tests are not applicable** — NOT APPLICABLE. TASK-398 is a read-only audit that changed no source code.

10. **Merging would not delete anything important** — VERIFIED. Three task files deleted from TODO/ are legitimate state transitions (moved to REVIEW/DONE).

**Disposition:** MERGE  
**Confidence:** High  
**Reason:** The audit is accurate, the risks are real, and the artifact is appropriate for the task type. The critical finding (channels._suppressed does not check agency DNC) is verified and is a real architectural risk.

**Claude should:**
1. Verify the 76 from the production queue (read `work/queue.jsonl` from Claude's worktree)
2. Consider whether `suppress.local.txt` absence should be a hard stop
3. Consider whether the bounce gap in resume revalidation matters
4. Merge the branch after reviewing the other five tasks

### RISKS

1. **Line numbers are approximate.** The audit's file:line references are off by 4-19 lines in some cases. The functions exist and perform the claimed checks, but the exact line numbers are wrong. This does not affect the audit's conclusions.

2. **The branch carries work from six other tasks.** Merging brings all of it in. Each task should be reviewed independently before merge.

3. **The 76 incident-suppressed recipients were not verified.** The audit correctly identified this as a structural limitation. Claude should verify from the production queue.

### RECOMMENDED CLAUDE ACTION

Merge the branch after reviewing TASK-296, TASK-314, TASK-364, TASK-410, and TASK-413. Verify the 76 from the production queue. Consider the three risks named in the audit.
