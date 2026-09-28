PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-481 — GLM independent verification: TASK-325, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-325
    branch          origin/qwen-worker-r60
    branch HEAD SHA 2594a3088814fa0c803afac8a654e9c6b72c6ebc

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`2594a3088814fa0c803afac8a654e9c6b72c6ebc` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`2594a3088814fa0c803afac8a654e9c6b72c6ebc` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-481-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** d9770132
- **TESTS:** `tests.test_cadence_graph_agreement` — 4/4 pass on the reviewed
  SHA. Verification by code inspection, import measurement, and falsification
  of the key claim (li5 only on already-connected branch).
- **FILES CHANGED:**
  - `docs/glm-reviews/TASK-481-verify-task-325.md` (NEW) — the verdict
  - `docs/qwen-tasks/DONE/TASK-481-glm-verify-task-325.md` (moved from RUNNING)
- **FINDINGS:**
  - **VERDICT: MERGE.** The artifact exists, all claims verified against code at
    exact SHA `2594a3088814fa0c803afac8a654e9c6b72c6ebc`, no behavior changed,
    no scope drift (2 files, 364 insertions, 0 deletions), no deletion risk.
  - All claims verified: graph location (cadencelibrary.py:327), step count
    (5 LinkedIn, 10 total), COPY_MAPPING (lines 106-112, li5 → connected_4
    only), two branches in render_preview.py (4 roles each), merge variables
    confirmed, _refuse_missing per-contact, stage() at line 591.
  - Key claim falsified and holds: li5 maps ONLY to connected_4 on the
    already-connected branch. The cold path never uses li5. Code at lines
    395-410 confirms connected_4 only in the `already` branch.
  - Minor: two line numbers slightly off (assemble_linkedin_copy 223 vs 215,
    custom_fields_for 535 vs 525). Not material — functions exist and are
    correctly named.
  - "Existence is not function" not applicable: this is a documentation task,
    the deliverable is the document itself, not a code module with production
    callers.
  - Three operator observations correctly documented in the artifact (li5
    branch-coverage gap, _refuse_missing per-contact scoping, InMail branch
    structurally present but dead).
- **RISKS:** None. No behavior changed. The document is a faithful snapshot.
- **RECOMMENDED CLAUDE ACTION:** Merge. The artifact is accurate and adds
  documentation without changing behavior or introducing risk. The three
  operator observations are waiting for decision.
- **ARTIFACT KIND:** Document (verdict)
