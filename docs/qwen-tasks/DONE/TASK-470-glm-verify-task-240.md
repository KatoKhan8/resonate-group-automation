PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-470 — GLM independent verification: TASK-240, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-240
    branch          origin/qwen-worker-r55
    branch HEAD SHA 8f4406e1bb2a4f9ce273b16785011c88da26b4f1

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`8f4406e1bb2a4f9ce273b16785011c88da26b4f1` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`8f4406e1bb2a4f9ce273b16785011c88da26b4f1` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-470-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

STATUS: DONE
COMMIT SHA: c1875a87
TESTS: 11 TASK-240 direct tests pass, 78 gate tests pass. Mutation test (bypass
  _owner_for) causes 6 gate tests to fail, confirming falsifiability. 5 invariant
  test failures are pre-existing (branch is 920 files behind master).

FILES CHANGED:
  docs/glm-reviews/TASK-470-verify-task-240.md (new)
    - Full GLM verdict document
    - Notes task file typo: task said "verify-task-219.md" but target is TASK-240

FINDINGS:
  1. CRITICAL: Work already integrated. Master has TASK-240's work via TASK-241
     (commit 90bd119b). The branch is 920 files and ~195,000 lines behind master.
     Master also has additional improvements (compliance gate, gate trace wrapper).
     Merging would be redundant.

  2. Artifact verified at exact SHA 8f4406e1:
     - _owner_for defined at src/executionguard.py:1115-1184
     - Consumed by authorize() at line 653 (production entry point)
     - _sender_for deprecated, zero production callers
     - All 5 required protections preserved (unowned, uninventoried, deactivated,
       unhealthy, another client)
     - providerwrites.SUPPORTED unchanged (0 diff)

  3. Tests are falsifiable. Mutation test (bypass _owner_for in authorize) causes
     6 gate tests to fail: two-humans, unowned, uninventoried, deactivated,
     unhealthy, another-client. Tests drive through real entry point, assert on
     behavior (NotAuthorized at gate "sender"), not on hasattr/source text/tokens.

  4. No scope drift. Exactly 4 files changed, all within FILES ALLOWED. No
     forbidden files touched. No junk files.

  5. Test inversion verified. test_a_seat_with_no_human_owner_is_refused now
     asserts refusal where the old test asserted passing. This is the single
     clearest measure that the change is a strengthening.

RISKS:
  - None. The work is already on master. The branch is obsolete.

RECOMMENDED CLAUDE ACTION:
  Do not merge. The branch can be deleted. The work is done and verified on
  master via TASK-241.

DISPOSITION: CLOSE
  Reason: Work already integrated into master via TASK-241 (90bd119b). Branch
  is obsolete. No merge needed.
