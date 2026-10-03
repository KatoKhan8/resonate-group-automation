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

Write the verdict to `docs/glm-reviews/TASK-500-verify-task-372.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- **STATUS:** DONE
- **ARTIFACT KIND:** document (GLM verdict)
- **COMMIT:** e1274d9be (qwen-worker-8-r9)
- **TESTS:** Not applicable — read-only review, no src/ changes.

### FILES CHANGED

- `docs/glm-reviews/TASK-500-verify-task-372.md` — NEW, the verdict document

### FINDINGS

1. **Branch has moved:** named SHA `f03c74fc01`, current HEAD `84268e53`.
   Reviewed the named SHA as instructed.

2. **Baseline artifact is CORRECT.** 228 unique names, set difference
   independently recomputed: 122 still failing + 106 new + 6 gone = 228.
   Old baseline: 122 + 6 = 128. All numbers match.

3. **Three defects in delta document narrative:**
   - two_campaigns has 24 new failures, not 18 as claimed
   - "test classes that did not exist at baseline" is false — all 12 classes
     exist at baseline commit 0af11fcb
   - Breakdown is 63 regressions + 24 new-in-existing-module, not 68+19

4. **Stability check NOT performed** (acknowledged in result block). Owed
   before baseline becomes authoritative merge gate.

5. **Massive scope drift:** 46 commits, 93 files on branch; TASK-372 owns
   ~6 files. Cherry-pick recommended over full merge.

6. **No dangerous deletions.** Only TODO→REVIEW task file move.

### RISKS

- The delta document's categorisation errors are misleading but do not
  corrupt the baseline data itself.
- Stability check gap means flaky tests may be in the baseline.

### RECOMMENDED CLAUDE ACTION

REWORK: fix the three narrative defects in the delta document (counts and
class-existence claims). Cherry-pick the 6 TASK-372 files from the branch.
Run a second suite pass for stability verification before accepting the
baseline as the merge gate.
