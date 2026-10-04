PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-532 — GLM independent verification: TASK-429, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-429
    branch          origin/qwen-worker-7-r9
    branch HEAD SHA 8acee2e8bb6a9dc447cf7ee387888f613124cdb1

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`8acee2e8bb6a9dc447cf7ee387888f613124cdb1` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`8acee2e8bb6a9dc447cf7ee387888f613124cdb1` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-532-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

STATUS: DONE
COMMIT SHA: c3608726d
TESTS: N/A — read-only verification task, no code changed.
FILES CHANGED:
  docs/glm-reviews/TASK-532-verify-task-429.md  (new) — the GLM verdict

FINDINGS:

  1. ARTIFACT EXISTS at target SHA 8acee2e8b. docs/WORKFORCE-REPORT-2026-09-27.md
     is 356 lines, created by commit 89ca42f65. The report is honest, well-sourced,
     and answers the operator's question.

  2. BRANCH HEAD HAS MOVED. Task file named 8acee2e8b; current origin/qwen-worker-7-r9
     points to 206a0739e. Verdict reviewed 8acee2e8b per task instruction.

  3. THREE NUMBERS RE-DERIVED. DONE count (268) and GLM tokens (31,227) verified at
     report commit 89ca42f65. Remote branch count (372) was time-dependent and correct
     at time of writing (now 445).

  4. ACCEPTANCE CRITERION 5 NOT MET. Croatian summary written but not posted to
     #resonate-os (no Slack access). Acknowledged in TASK-429 RESULT block. Operator
     action required, not a task defect.

  5. STAGE MISMATCH (minor). TASK-429 file is in REVIEW/ but RESULT says STATUS: DONE.
     Correct state for a verdict target awaiting Claude's integration decision.

  6. NO DESTRUCTIVE DELETIONS. Branch diff shows 4 TODO files "deleted" but all were
     moved to REVIEW/DONE. TASK-429's own footprint is 2 files added.

  7. NO SCOPE DRIFT. TASK-429's commits (89ca42f65, eb776e6ef) are clean: 2 files,
     both intentional. Branch carries 93 commits of other work.

  8. EXISTENCE IS NOT FUNCTION (document task). No production caller exists because
     none is expected. The report's function is to be read by the operator and to
     honestly say what cannot be measured. It does this.

RISKS:
  - The report's headline finding (project cannot measure its own workforce) is correct.
    If the operator expected per-worker breakdowns, the gap is in measurement
    infrastructure, not in the report.
  - The spend ledger is gitignored and not accessible from worker worktrees. This is
    a structural gap, not a TASK-429 defect.

RECOMMENDED CLAUDE ACTION:
  - MERGE TASK-429. Cherry-pick commits 89ca42f65 and eb776e6ef from qwen-worker-7-r9.
  - Post the Croatian summary to #resonate-os manually after merge.
  - If per-worker attribution is a priority, the fix is a WORKER: field in the RESULT
    block template and a durable claim log (separate task).
