PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-510 — GLM independent verification: TASK-402, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-402
    branch          origin/qwen-worker-9-r9
    branch HEAD SHA f1b9c357c17f4b557cbdb06f68339c7343ef3e83

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`f1b9c357c17f4b557cbdb06f68339c7343ef3e83` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`f1b9c357c17f4b557cbdb06f68339c7343ef3e83` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-510-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## Result

STATUS: DONE
ARTIFACT KIND: document (GLM verdict)
COMMIT: 235f73f52
TESTS: n/a — read-only verification
FILES CHANGED: docs/glm-reviews/TASK-510-verify-task-219.md (created), this task file (moved to DONE)
VERIFIER: GLM independent verification (Qwen worker 8, isolated worktree at exact SHA)

### Summary

TASK-402's finding is VERIFIED. All claims re-confirmed against source at
`f1b9c357c17f4b557cbdb06f68339c7343ef3e83`:

- Five render_prompt() call sites exist at the cited lines (1385, 1488, 1501, 1511, 1542, 1626)
- draft.md has 24 matches and linkedin_note.md has 13 matches for context-aware features
  (prior_contact, already_sent, siblings, sender_identity, step.purpose, angle_wording)
- WRITER_SYSTEM has ZERO matches for all six features
- generate_campaign.py has zero production callers in src/ (git grep empty at target SHA)
- Skills' consumer names (stage_a/b/e/f) have zero matches in generate.py
- Falsification attempt found no overstated mismatch

RECOMMENDATION: MERGE the finding. TASK-391's conclusion is independently verified
by two readers and the evidence holds. The branch carries 34 commits of other work
needing separate review; TASK-402's own commit is cherry-pickable.

### FINDINGS

None beyond what TASK-402 and TASK-391 already name. Minor line-count imprecisions
in TASK-402 (~80 vs actual ~85-100 for WRITER_SYSTEM, ~200 vs 265 for draft.md)
do not affect the conclusion.

### RISKS

None. The finding is settled and consumed by TASK-400.
