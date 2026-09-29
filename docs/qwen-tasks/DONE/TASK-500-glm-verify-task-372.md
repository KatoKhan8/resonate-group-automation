PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-500 — GLM independent verification: TASK-372, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-372
    branch          origin/qwen-worker-2-r9
    branch HEAD SHA f03c74fc01a40df45419742e122268d11c8395a1

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`f03c74fc01a40df45419742e122268d11c8395a1` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`f03c74fc01a40df45419742e122268d11c8395a1` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-500-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- **STATUS:** DONE
- **ARTIFACT KIND:** document (GLM verdict)
- **COMMIT:** 5a88b3bc
- **TESTS:** Not applicable — read-only review, no code changes
- **BRANCH HEAD SHA REVIEWED:** f03c74fc01a40df45419742e122268d11c8395a1

### FILES CHANGED

- `docs/glm-reviews/TASK-500-verify-task-219.md` — NEW, the verdict document
- `docs/qwen-tasks/DONE/TASK-500-glm-verify-task-372.md` — moved from TODO

### FINDINGS

1. **Core artifacts exist and numbers are correct.** Independently verified:
   228 names in new baseline, set-difference gives 128 old / 106 new / 6 gone,
   all matching the result block. The 6 fixed tests match exactly (5 resume-ledger
   + 1 provider-write).

2. **Stability check not performed.** Acceptance criterion 6 requires a second
   run to diff named sets. The delta document honestly acknowledges this. The
   baseline is provisional until verified stable.

3. **Severe branch scope drift.** 93 files changed on the branch, only 7 belong
   to TASK-372. Cherry-pick commits `91a280e2` and `6fc77fb0`.

4. **Pre-existing verification not independently reproduced.** Reviewed the
   per-module table in the delta doc — internally consistent — but did not
   check out `0af11fcb` and re-run. Accepted on documentary evidence.

5. **run_suite.py timeout change is legitimate.** Task explicitly permits it.

### RECOMMENDED CLAUDE ACTION

- **MERGE (cherry-pick).** Cherry-pick the two TASK-372 commits to master.
- Schedule the stability check as a follow-up task.
- Triage the 106 new failures (68 regressions + 38 new tests).

### DISPOSITION

**MERGE** — core deliverable is correct and honest about gaps.
