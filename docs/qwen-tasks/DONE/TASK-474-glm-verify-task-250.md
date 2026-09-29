PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-474 — GLM independent verification: TASK-250, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-250
    branch          origin/qwen-worker-9-r61
    branch HEAD SHA 3efcc9683f2a3dd23b1096ef1824d70d78f5cb33

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`3efcc9683f2a3dd23b1096ef1824d70d78f5cb33` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`3efcc9683f2a3dd23b1096ef1824d70d78f5cb33` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-474-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

# RESULT

STATUS: DONE
COMMIT SHA: a230ae4b
TESTS: Falsification confirmed — removing the verification pin causes test_the_clean_domain_verifies to fail with 'held' != 'approved' and 5 test_enrich tests to fail; test_productive_verification_roles passes with or without the pin (correctly independent)
FILES CHANGED:
  - docs/glm-reviews/TASK-474-verify-task-219.md: verdict document

FINDINGS:
  1. VERDICT: MERGE. The artifact exists at the exact SHA, does what it claims, and the pin is load-bearing (falsified by mutation). No deletion risk, no scope drift, shared fixtures untouched.

  2. The pin in fixture_config flows through pin_client_config to 20+ test modules. This is not a disconnected function.

  3. One gap acknowledged honestly in the result block: the full suite name diff (before/after) was not completed due to runtime constraints. Claude should run this from their worktree before merging.

  4. The approach is correct: pinning verification roles in fixture_config avoids the trap that killed attempt 1 (editing shared fixtures). test_productive_verification_roles remains an independent assertion of the live policy.

RISKS:
  - Full suite name diff owed before merge (same gap that let attempt 1's 47 failures through)
  - The pin couples test expectations to fixture evidence; if fixtures are updated to live roles, the pin must be removed

RECOMMENDED CLAUDE ACTION:
  1. Run full suite from Claude's worktree and diff by name against baseline
  2. Merge to master if clean
  3. Note: the verdict file is named TASK-474-verify-task-219.md (the task file said "219" — likely a typo for 250, but written as specified)
