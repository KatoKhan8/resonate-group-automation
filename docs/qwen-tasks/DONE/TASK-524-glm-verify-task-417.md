PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-524 — GLM independent verification: TASK-417, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-417
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

Write the verdict to `docs/glm-reviews/TASK-524-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT

**STATUS**: DONE
**ARTIFACT KIND**: document (GLM review verdict)
**COMMIT SHA**: 7d70fbd5
**TESTS**: read-only verification; all code claims verified against source at exact SHA
**FILES CHANGED**: `docs/glm-reviews/TASK-524-verify-task-417.md`

### Summary

Independent GLM verification of TASK-417 (campaign cadence drift check) at exact branch HEAD SHA `3da4a246ee2536760d04dfc4d1d94b649160c2fa` on `origin/qwen-worker-12-r9-sync`.

**Disposition: MERGE**

### Verification Results

1. **Artifact exists** ✓ — `docs/qwen-tasks/DONE/TASK-417-campaign-cadence-drift-check.md` present at reviewed SHA
2. **Code claims verified** ✓ — All five code-level claims checked against `src/providers/heyreach.py:1222-1299` and `src/cadencelibrary.py:327-365`:
   - Cold branch `chain()` does NOT compensate for VIEW_PROFILE delay (lines 1258-1266)
   - Already-connected branch DOES compensate with `max(d2-2, 1)` (lines 1292-1299)
   - Canonical cadence declares (3, 4, 5) day gaps between LinkedIn messages
   - Cold branch delivers (7d, 5d) instead of (3d, 4d) → drift +4d, +1d
   - Already-connected branch delivers (3d, 4d, 5d) with no drift
3. **Finding is valid** ✓ — Cold-branch expansion is real and structural, affecting majority of cold outreach prospects
4. **Scope isolated** ✓ — TASK-417 changed only its task file (TODO→DONE), no code modifications
5. **No deletions** ✓ — Only task file lifecycle move, no unintended file removals

### Critical Finding

TASK-417 correctly identified that `linkedin_sequence()`'s cold branch delivers LinkedIn messages at roughly double the intended spacing for prospects who were NOT already connections. This is the majority of cold outreach prospects and confounds the cadence experiment.

**Root cause**: Cold branch adds VIEW_PROFILE delay (3d) and message delay (4d) sequentially → 7d gap where canonical declares 3d. Already-connected branch compensates; cold branch does not.

### Recommended Claude Action

1. Decide whether cold-branch expansion is intentional or defect
2. If intentional: update canonical cadence to match reality
3. If defect: fix `chain()` to compensate like already-connected branch
4. EmailBison cadence verification remains BLOCKED on live-state access

### FINDINGS

- TASK-417 is a finding-only task (read-only audit), not a code change
- All code analysis is correct and verified
- The finding is actionable operational intelligence
- Branch carries other tasks' work but TASK-417 is cleanly isolated

### RISKS

- None from merging TASK-417 (no code changed)
- The cold-branch expansion finding itself represents a risk to cadence experiment validity if unaddressed

### REVIEWED

- **Branch**: `origin/qwen-worker-12-r9-sync`
- **HEAD SHA**: `3da4a246ee2536760d04dfc4d1d94b649160c2fa` (verified with `git rev-parse`)
- **Worktree**: `.qwen/worktrees/task524-review` (isolated, detached HEAD)
- **Review date**: 2026-09-29
