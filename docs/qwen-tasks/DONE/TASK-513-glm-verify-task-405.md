PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-513 — GLM independent verification: TASK-405, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-405
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

Write the verdict to `docs/glm-reviews/TASK-513-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS**: DONE  
**ARTIFACT_KIND**: finding (independent verification verdict)  
**COMMIT_SHA**: db660233  
**VERDICT_FILE**: `docs/glm-reviews/TASK-513-verify-task-405.md`  
**TARGET_SHA REVIEWED**: 3da4a246ee2536760d04dfc4d1d94b649160c2fa (confirmed via `git rev-parse`)  
**TASK-405 COMMIT**: 9e607efdb93252c0091f9a989254553b9010d4f3  

**TESTS**: 9/9 pass in `test_identity_survives_exclusion.py` at target SHA. All assert on behavior (what `store.validate()` returns), not source text or hasattr. Falsifiable: removing any of the three invariant checks in `_identity_problems()` would cause the corresponding test to fail.

**FILES CHANGED**: 
- `docs/glm-reviews/TASK-513-verify-task-405.md` (new — the verdict)
- `docs/qwen-tasks/RUNNING/TASK-513-glm-verify-task-405.md` (result block added)

**FINDINGS**:

1. **Artifact exists and is correct.** TASK-405's verdict document (192 lines) exists at the target SHA. It is a pure investigation artifact — no code changes. The verdict correctly concludes that contact-key validation is centralized and no inconsistency exists.

2. **All code references verified.** `identity.py:79-106` (key generation), `lint.py:242-254` (lookup), `store.py:1642-1676` (validation), `store.py:1769-1793` (enforcement) — all accurate at target SHA. Only `identity.py:103` assigns `contact["key"]` in all of `src/`.

3. **Provenance partially verified.** TASK-394's commit `c5d61dee` exists in the object store but is orphaned (not reachable from any branch). TASK-405's claim that TASK-389 "never started" was accurate at verdict time (2026-09-27 16:04) but TASK-389 was later completed (2026-09-28).

4. **Scope drift: SIGNIFICANT.** The branch carries 46 changed files from 15+ other tasks. TASK-405's own contribution is 2 files (commit `9e607efd` only). Cherry-pick that commit, not the branch.

5. **No deletion risk.** Merging TASK-405's commit would not delete any production code, tests, or configuration. Only task lifecycle files (TODO→REVIEW transitions).

6. **New finding (out of scope):** `store.transaction()` provides raw record access without calling `validate()`. 14 callers in `src/` use this path. A caller could theoretically introduce identity problems without being caught. Not TASK-405's responsibility but a real enforcement gap.

**RECOMMENDATION**: **CLOSE** — TASK-405's verdict is correct. The contact-key guard is centralized, tests verify the invariants, and no code change is needed. Cherry-pick only commit `9e607efd`.

**RISKS**: None from TASK-405 itself. The `store.transaction()` bypass gap is a separate concern.

**FILES FORBIDDEN**: None touched.  
**PROVIDER WRITES**: 0.
