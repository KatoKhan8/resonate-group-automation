PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-505 — GLM independent verification: TASK-389, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-389
    branch          origin/qwen-worker-7-r9
    branch HEAD SHA a47ecb515c7bddc63d256c24b3768d04a3df7133

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`a47ecb515c7bddc63d256c24b3768d04a3df7133` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`a47ecb515c7bddc63d256c24b3768d04a3df7133` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-505-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS:** DONE
**COMMIT:** 9682702d (on qwen-worker-7-r9-glm505, cherry-picked from 1377f5d1)
**TESTS:** Mutation test performed — broke uniqueness guard (`> 1` → `> 99`), confirmed `test_two_contacts_sharing_a_key_is_a_validation_problem` fails for the intended reason. All 9 identity tests pass at reviewed SHA.
**FILES CHANGED:** `docs/glm-reviews/TASK-505-verify-task-389.md` (verdict document)
**ARTIFACT KIND:** Document (GLM review verdict)

### Summary

Reviewed TASK-389 at SHA `a47ecb51` in isolated worktree. Branch has since moved to `723e21fd`. TASK-389 is an investigation task that traced all `contact_key` validation sites and found no inconsistency. All six claims in the result block independently verified:

1. `identity.contact_key()` is the single authority (src/identity.py:79) ✓
2. `contact["key"] = key` appears exactly once (src/identity.py:103) ✓
3. `store._identity_problems()` checks all three invariants (src/store.py:1642) ✓
4. `lint.contact_key()` delegates to identity (src/lint.py:242) ✓
5. All module-local lookups are consistent single-pass comparisons ✓
6. Tests are falsifiable (mutation confirmed) ✓

**Disposition: MERGE.** No code change was needed; the finding is that the code is already correct. Cherry-pick is clean (2 commits, task file only).

### RISKS
None. The investigation is thorough and the conclusion is correct.

### RECOMMENDED CLAUDE ACTION
Merge TASK-389's commits (task file move TODO → REVIEW). No integration needed — the artifact is a finding, not code.
