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
**COMMIT:** b73415408 (rebased on qwen-worker-10-r9)
**TESTS:** Read-only verification; no code changes. All claims verified by code reading in isolated worktree at exact SHA.
**FILES CHANGED:** `docs/glm-reviews/TASK-520-verify-task-412.md` (verdict document)
**ARTIFACT KIND:** Finding (GLM independent verification verdict)

---

### Verdict: REWORK

**Branch reviewed:** `origin/qwen-worker-3-r9-task285`
**Branch HEAD SHA reviewed:** `c8a62f4109f47eb5338f1ef334d68f44dcb989ef` (verified with `git rev-parse`)
**Review worktree:** `.qwen/worktrees/glm-task520` (detached at exact SHA)

---

### What was verified

1. **Artifact exists:** YES — audit document in `docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md` on the branch
2. **Six suppression stores identified:** VERIFIED — all six stores exist and are correctly described (domain suppress.txt, agency DNC, client approval, account suppression, contact suppression, bounce events)
3. **All write paths gated:** VERIFIED — EMAIL_ACTIVATE, EMAIL_RESUME, LINKEDIN_ADD_LEAD, email staging, LinkedIn staging, and leadstop.sweep all check suppression before writing
4. **`eligibility.decide` reads all six stores:** VERIFIED — calls `must_not_contact` (stores 1-5) then `_email_checks` (store 6)
5. **Bounce gap in `_resume_revalidates_suppression`:** VERIFIED — `must_not_contact` does not include `_email_checks`, so bounce is not checked on resume (minor gap, provider will re-bounce)

---

### Findings

1. **Audit mostly accurate** — all functional claims verified, line numbers mostly correct (within a few lines)
2. **One owed item** — the 76 re-verification cannot be done from this worktree (acknowledged in audit, owed from Claude's worktree)
3. **One inaccuracy** — audit says store 1 is checked at `hygiene.check:337` but it's actually checked at `eligibility._suppressed:293`, `channels._suppressed:130`, `discovery.known:205`
4. **Significant scope drift** — branch carries work from 8+ other tasks (7167 insertions across 39 files); TASK-412's contribution is 2 files, 192 insertions
5. **Bounce gap real** — correctly identified as minor gap in finding §4.4

---

### Recommendation

**Cherry-pick only TASK-412's commits:** `5bbf11101..58dcd9fb6` (four commits, 2 files changed). Do NOT merge the entire branch.

**Correct the inaccuracy:** Update the audit to cite the correct locations for store 1 checks.

**Perform the owed item:** Claude should run the fresh read of the 76 from `work/queue.jsonl` in Claude's worktree.

**Decide on the bounce gap:** Low priority — consider whether `_resume_revalidates_suppression` should also check `channels._bounced` for email-channel contacts.

---

### Reproducible commands

```bash
# Create isolated worktree at exact SHA
git worktree add .qwen/worktrees/glm-task520 c8a62f4109f47eb5338f1ef334d68f44dcb989ef --detach

# Verify SHA
git rev-parse c8a62f4109f47eb5338f1ef334d68f44dcb989ef

# Read the audit
git show c8a62f4109f47eb5338f1ef334d68f44dcb989ef:docs/qwen-tasks/REVIEW/TASK-412-suppression-list-audit.md

# Check TASK-412's specific commits
git log --oneline 5bbf11101^..58dcd9fb6

# Check what TASK-412 changed (should be only task file)
git diff 5bbf11101^..58dcd9fb6 --stat

# Verify must_not_contact does not include bounce
cd .qwen/worktrees/glm-task520
sed -n '358,377p' src/eligibility.py
```

---

### RISKS

- The branch has significant scope drift and must not be merged wholesale
- The audit's inaccuracy about store 1 location is minor but should be corrected
- The 76 re-verification is owed and blocks full acceptance of the audit's completeness

### RECOMMENDED CLAUDE ACTION

1. Cherry-pick commits `5bbf11101..58dcd9fb6` to bring TASK-412's audit to master
2. Correct the store 1 location inaccuracy in the audit
3. Run the fresh read of the 76 from `work/queue.jsonl` to confirm they are still suppressed
4. Decide whether to close the bounce gap in `_resume_revalidates_suppression` (low priority)
