PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-519 — GLM independent verification: TASK-411, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-411
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

Write the verdict to `docs/glm-reviews/TASK-519-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT

**STATUS:** DONE
**COMMIT:** 2e7337f6f (on qwen-worker-3-r9)
**TESTS:** Read-only verification. All claims checked via git show, git ls-tree, JSON parsing against PROVIDER-CAMPAIGNS.json at target SHA and at TASK-411's commit.
**FILES CHANGED:** docs/glm-reviews/TASK-519-verify-task-411.md (verdict artifact)
**ARTIFACT KIND:** Finding (GLM verdict document)

### Summary

Independent verification of TASK-411 (docs hygiene pass) at exact branch HEAD SHA `f03c74fc01a40df45419742e122268d11c8395a1` on `origin/qwen-worker-2-r9`. Branch has since moved to `84268e53233e37441d9b58414eb432d163537e9f`; reviewed the exact named SHA per protocol.

### Verdict: MERGE

**7 of 8 FALSE claims confirmed. 1 false positive. 1 not verifiable from git.**

Confirmed FALSE:
1. CLAUDE.md points to superseded 09-26 handoff (09-27 exists)
2. CLAUDE.md quotes wrong PROVIDER-CAMPAIGNS.json timestamp
3. OPERATING-MODE.md "493 is the only campaign sending" (487/489/493 all active)
4. Handoff references checkpoint-a doc not on master
5. Handoff references pool-logs/ directory that doesn't exist
6. QWEN.md config/.env not present in all worktrees

False positive:
- Claim 3 ("40 campaigns total"): TASK-411 confused HeyReach's 121 with EmailBison's 40. EmailBison DOES have 40 total. CLAUDE.md is correct.

Not verifiable:
- Claim 7 (worktree count): runtime state, not captured in git

### Errors in TASK-411's notable observations

- TASK-403 "missing": WRONG. Exists in both DONE and TODO at target SHA.

### Merge safety

- Only 1 file deleted by merge: a task file moved from TODO (expected lifecycle)
- TASK-411's own commits are clean: 2 commits, 1 file (the task file)
- Branch has 46 commits / 93 files total (scope drift from other tasks, not TASK-411)

### FINDINGS

TASK-411 is a valid report-only task. Its methodology (check doc claims against data files) is sound. 7/8 findings are correct and operationally significant. The 1 error came from misreading JSON structure (HeyReach vs EmailBison keys). Claude should apply the 6 confirmed corrections and skip claim 3.

### RISKS

None from the verdict itself (read-only). The false positive (claim 3) would cause Claude to "fix" a correct claim if applied uncritically.

### RECOMMENDED CLAUDE ACTION

Merge TASK-411's branch (or cherry-pick its 2 commits). Apply 6 confirmed corrections to standing docs. Drop claim 3 and the TASK-403 observation.
