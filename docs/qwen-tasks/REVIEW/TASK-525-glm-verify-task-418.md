PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-525 — GLM independent verification: TASK-418, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-418
    branch          origin/qwen-worker-r9-t391
    branch HEAD SHA d4effa8d82c50fc4166fd6e6780f069d728eda00

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`d4effa8d82c50fc4166fd6e6780f069d728eda00` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`d4effa8d82c50fc4166fd6e6780f069d728eda00` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-525-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

**STATUS:** DONE  
**ARTIFACT KIND:** document (GLM verdict)  
**COMMIT SHA:** 74ec77a54  
**TESTS:** n/a — read-only verification  
**FILES CHANGED:** docs/glm-reviews/TASK-525-verify-task-418.md  

### What was verified

TASK-418 audited `config/clients/productive-offers.yaml` (504 lines) for internal contradictions and reported "none found." The audit performed 12 checks covering CTA link consistency, composes references, mechanism references, AI page_text verbatim matches, traces_to resolution, approval statuses, SHA consistency, persona consistency, no-dash rule, and three potential contradictions that turned out not to be contradictions.

### What was falsified

**Check #9 (no-dash rule) is false.** Line 107 (OFFER-RP-001, `concrete_deliverable`) contains "forward-looking" with a dash. Line 249 (OFFER-B-OPERATIONS, which composes OFFER-RP-001) contains "forward looking" with no dash. The file's own comment at line 162 states the no-dash rule is a "standing rule" and that "`14 day` rather than the hyphenated form is deliberate, not a typo." The component offer violates the rule the composed offer follows. This is an internal contradiction the audit missed.

**Reproduction:**
```bash
git show d4effa8d8:config/clients/productive-offers.yaml | grep -n "forward"
# 107:    concrete_deliverable: a forward-looking view of who is booked where and where the next hire goes
# 249:    concrete_deliverable: ... and a forward looking view of who is booked where
```

### Other findings

- **Artifact exists:** The task file moved from TODO to DONE on the branch. No code was produced (read-only audit).
- **Existence is not function:** Not applicable — no code, no chain to trace.
- **Deletion check:** Two task files deleted from TODO (TASK-302, TASK-418) but both were moved to BLOCKED/DONE, not content-deleted. No production code deleted.
- **Scope drift:** The branch carries 46 files changed across multiple tasks (TASK-391, TASK-311, TASK-464, etc.). TASK-418's artifact is a single task file move and can be cherry-picked cleanly.

### Disposition

**REWORK** — The result block's claim of "none found" is incorrect. One contradiction exists: OFFER-RP-001 has "forward-looking" (dashed) while OFFER-B correctly removed the dash. The audit should have reported this.

**Required action:**
1. Fix OFFER-RP-001's `concrete_deliverable` to remove the dash
2. Update TASK-418's result block to report the finding

**Merge recommendation:** Do not merge the branch for TASK-418. The task produced no code; the task file move can be replicated on master directly. The branch carries substantial unrelated work.

**FINDINGS:** One missed contradiction in TASK-418's audit (dash inconsistency, lines 107 vs 249).  
**RISKS:** Minor data quality issue, not a safety or architectural defect.  
**RECOMMENDED CLAUDE ACTION:** Rework TASK-418 to fix the dash and report the finding, or accept the finding and fix the dash in a separate commit.
