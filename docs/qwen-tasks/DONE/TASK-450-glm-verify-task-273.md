PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-450 — GLM independent verification: TASK-273, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-273
    branch          origin/qwen-worker-r9
    branch HEAD SHA e456c6128774cfd00960ac50d7b39c6e99a3f8cd

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`e456c6128774cfd00960ac50d7b39c6e99a3f8cd` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`e456c6128774cfd00960ac50d7b39c6e99a3f8cd` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-450-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 3c5753e0 (verdict committed and pushed to origin/qwen-worker-7-r9)
- **TESTS:** Verified TASK-273's 33 tests all pass at target SHA e456c612. Spot-checked existing provider test modules (test_nothing_writes_to_a_provider, test_provider_body, test_provider_name) — all pass.
- **FILES CHANGED:** `docs/glm-reviews/TASK-450-verify-task-219.md` (new, verdict document)
- **ARTIFACT KIND:** document (GLM independent review verdict)

### What was verified

1. **Artifact exists at target SHA**: `tests/test_provider_conformance.py` exists at e456c6128774cfd00960ac50d7b39c6e99a3f8cd, added in commit 17839f72. ✓
2. **Tests pass**: All 33 tests pass. Minor miscount in result block (claims 13 in Group 1, actual is 14) — cosmetic only. ✓
3. **Behavioral, not just existence**: Groups 1, 3, 4 are behavioral (call real functions, assert exceptions/return values). Group 2 is existence-only but honestly labeled as "convention, not contract" per task spec. ✓
4. **Falsifiable**: Signature tests use `inspect.signature()` and pin exact parameter names. Write door tests call actual functions. Authorization tests call `perform()` through real production entry point. All verified independently. ✓
5. **No deletions**: Branch diff vs master shows only task file stage moves (TODO → DONE/REVIEW), no source/test deletions. ✓
6. **Scope drift**: Branch has 75 files changed vs master (significant), but TASK-273's own commits touch only the test file. Cherry-pick commit 17839f72 to integrate cleanly. ✓

### Findings

1. **Minor miscount** (Low): Result block says "13 tests" in Group 1, actual is 14. Cosmetic.
2. **Convention group weakness** (Low): Group 2 tests are existence-only (`callable(getattr(...))`), but task spec explicitly categorizes them as non-contractual. Accepted.
3. **Branch scope drift** (Informational): 75 files vs master, but TASK-273's commits are clean. Cherry-pick, don't wholesale merge.

### Disposition

**MERGE** via cherry-pick of commit 17839f726e7cb5da0c8146e1b5e63ccd90d7e728.

The artifact exists, does what it claims, and the important tests are behavioral and falsifiable. The suite pins declared differences so future convergence is loud, and tests the authorization door through the real production entry point.

### RISKS

None identified. The suite is purely offline, adds no source changes, and touches no forbidden files.

### RECOMMENDED CLAUDE ACTION

Cherry-pick commit 17839f72 to integrate `tests/test_provider_conformance.py`. Do not merge the branch wholesale due to scope drift.

### NOT VERIFIED

Full suite run to confirm the "130 provider-related tests green" claim and pre-existing failure count. Spot-checks of provider test modules all pass.
