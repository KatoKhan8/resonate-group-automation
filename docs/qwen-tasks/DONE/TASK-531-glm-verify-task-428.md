PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-531 — GLM independent verification: TASK-428, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-428
    branch          origin/qwen-worker-11-r9
    branch HEAD SHA c392a8ba4f07208cff6d89ac53c230aa64f4a7d5

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`c392a8ba4f07208cff6d89ac53c230aa64f4a7d5` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`c392a8ba4f07208cff6d89ac53c230aa64f4a7d5` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-531-verify-task-428.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- **STATUS:** DONE
- **COMMIT:** 5652b2b30
- **ARTIFACT KIND:** document (GLM verdict)
- **VERDICT:** REWORK
- **TESTS:**
  - `TestClientEvidenceAllowance`: 6/8 pass, 2 FAIL
    - FAIL: `test_client_domain_outside_evidence_path_is_refused` (Acceptance 2)
    - FAIL: `test_mutation_widening_to_client_domain_in_any_path_fails` (Acceptance 6b)
  - `test_fixture_hygiene` full suite: 23/25 pass (same 2 failures)
  - `offers.load()`: 8 offers, A and B approved at v2 — works
  - `test_an_offer_cannot_be_invented`: 11/11 pass
  - `test_a_dead_cta_link_is_refused`: 22/22 pass
  - `test_a_case_study_claim_must_appear_on_the_page`: 19/19 pass
- **FILES CHANGED:**
  - `docs/glm-reviews/TASK-531-verify-task-428.md` (new, the verdict)
- **FINDINGS:**
  - TASK-428's own commit (5791b9058) was correct: it kept `productive.io` in
    `FORBIDDEN_DOMAINS` and added a path-scoped inner check.
  - TASK-448 (262c11f3a, same branch) removed `productive.io` from
    `FORBIDDEN_DOMAINS` entirely, making the allowance universal and breaking
    the two tests that assert it is refused outside the evidence path.
  - The `_is_client_evidence_file` helper and the inner check are dead code at
    the branch HEAD because `productive.io` is never encountered by the domain
    scan.
  - Fix: restore `productive.io` to `FORBIDDEN_DOMAINS`, keep both TASK-428's
    inner check and TASK-448's `CLIENT_OWN_DOMAINS` email-test allowance.
- **RISKS:**
  - The file rename and `offers.py` path update are correct and should be
    preserved.
  - Merging would not delete anything (verified).
- **RECOMMENDED CLAUDE ACTION:** Rework. Reconcile TASK-428 and TASK-448 by
  restoring `productive.io` to `FORBIDDEN_DOMAINS` with the path-scoped
  exception intact.
