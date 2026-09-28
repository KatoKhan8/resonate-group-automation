PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-473 — GLM independent verification: TASK-249, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-249
    branch          origin/qwen-worker-8-r61
    branch HEAD SHA 8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-473-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 5dde25ce
- **TESTS:** Verified 22 new tests pass, 279 existing Slack agent tests pass
  (301 total), import-graph test passes (10 tests). All falsification attempts
  failed — privacy rule is structural and robust.
- **FILES CHANGED:**
  - docs/glm-reviews/TASK-473-verify-task-249.md: verdict document (244 lines)
  - docs/qwen-tasks/REVIEW/TASK-473-glm-verify-task-249.md: task file moved from TODO
- **FINDINGS:**
  - Artifact exists at SHA 8e6ee5ed on origin/qwen-worker-8-r61. All claimed
    files present: 7 tool functions, 7 keyword routes, 22 tests.
  - Production chain is fully wired: message → plan() → keyword_plan() →
    REGISTRY → run() → tool function. Every link is consumed.
  - Privacy rule is structural: _is_dm() checks source.startswith("dm:"),
    edge cases (None, no colon, "channel: dm:") all return False (safe default).
  - DM answer scrubbing strips email, name, contact_name, first_name, and any
    field matching EMAIL_SHAPE or STATUS_FORBIDDEN_FIELDS. Verified against
    realistic record with multiple PII fields — no leaks.
  - Not-found answers do not echo the identifier.
  - Tests are falsifiable: assert on ABSENCE of PII in JSON output, not on
    presence of fields. Mutation that removed scrubbing would fail.
  - Diff is purely additive: 948 lines added, 0 removed. No deletions.
  - No scope drift: only the two named source files and test file changed.
  - Import-graph test confirms no write path introduced.
  - Three findings in verdict (F1, F2, F3) are not defects: F1 is correct
    architecture (loop logs, not tools), F2/F3 are documented limitations.
- **RISKS:** None identified. The work is correct and safe to merge.
- **RECOMMENDED CLAUDE ACTION:** Merge origin/qwen-worker-8-r61 at SHA
  8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29 into master.
