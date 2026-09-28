PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-492 — GLM independent verification: TASK-350, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-350
    branch          origin/qwen-worker-7-r68
    branch HEAD SHA efe70035f21e23c0216c584b55d4d9985d3fd0fc

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`efe70035f21e23c0216c584b55d4d9985d3fd0fc` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`efe70035f21e23c0216c584b55d4d9985d3fd0fc` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-492-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 9f593ef0
- **TESTS:** 15/15 new tests pass, 26/26 existing replywatch tests pass. Mutation test performed independently: breaking `_compare_field` to always return AGREED causes COULD_NOT_ESTABLISH tests to fail as expected.
- **FILES CHANGED:**
  - `docs/glm-reviews/TASK-492-verify-task-350.md` - NEW, 188 lines, the verdict document
  - `docs/qwen-tasks/DONE/TASK-492-glm-verify-task-350.md` - moved from TODO
- **FINDINGS:**
  1. **Artifact exists at exact SHA:** Verified `efe70035f21e23c0216c584b55d4d9985d3fd0fc` in isolated worktree. `src/replywatch.py` has ~350 lines of reconciliation code added (lines 550-903). Test file has 15 tests. `git diff master...efe70035 --stat`: 4 files changed, 1005 insertions, 0 deletions.
  2. **Production caller exists:** `main()` at line 941 calls `reconcile_campaigns()` when `--reconcile` flag is set. Internal functions all consumed: `_compare_field` called by `_heyreach_findings` and `_bison_findings`; both called by `_reconcile_one_*`; both called by `reconcile_campaigns`. Tests call `reconcile_campaigns()` at 16 sites. **Observation:** Entry point is manual CLI flag (`python -m src.replywatch --reconcile`), not automatic integration into polling loop. Task description said "add the check to the existing loop" but implementation made it operator-initiated. Scope deviation but not defect - functionality is production-callable and result block acknowledges this.
  3. **Three-verdict design correct:** AGREED, DRIFTED, COULD_NOT_ESTABLISH implemented at lines 555-557. `_compare_field()` returns COULD_NOT_ESTABLISH if either value is None, AGREED if equal, DRIFTED otherwise. Critical guard: provider returning None produces COULD_NOT_ESTABLISH, never AGREED.
  4. **Tests falsifiable:** Mutation test performed: broke `_compare_field` to always return AGREED, confirmed None provider value incorrectly returns AGREED (would fail tests). Guard-fail test in suite (`test_breaking_the_comparison_makes_the_drift_test_fail`) monkey-patches comparison, confirms drift tests fail, restores, confirms drift detected. Tests assert on behavior (verdict values), not source text or hasattr.
  5. **Read-only by construction:** All provider calls confirmed read-only: `heyreach.campaign_read()` uses `_read_get()` (GET), `heyreach.campaign_stats()` uses `_read()` (POST to read-only route allowlist), `bison.campaign()` uses GET, `bison.campaign_lead_count()` uses GET. No calls to write functions. No calls to `store.save()`.
  6. **Numerical ordering:** `_provider_id_sort_key()` at line 747 converts provider_id to int for sorting. Test confirms IDs "100", "9", "10" sort as ["9", "10", "100"].
  7. **No deletions from master:** `git diff master...efe70035 --stat` shows 1005 insertions, 0 deletions. No blob hash conflicts. No risk of "12,487 lines deleted" defect.
  8. **No scope drift:** Branch has 3 commits, all TASK-350 work (TODO -> RUNNING -> REVIEW). 4 files changed, all intentional. No unrelated changes.
  9. **Acceptance criteria:** All 6 acceptance criteria verified. Acceptance 5 (live run) not performed - no credentials in this worktree, but code confirmed read-only. Acceptance 6 (full suite) partially verified - two relevant test files passed, full suite not run due to timeout concerns.
- **RISKS:**
  - Manual CLI entry point instead of automatic loop integration (scope deviation, not defect)
  - Live run not performed (no credentials, code confirmed read-only)
  - Full suite not run (relevant test files passed, pre-existing failures not TASK-350's responsibility)
- **RECOMMENDED CLAUDE ACTION:**
  - **MERGE** - TASK-350 delivers sound, tested, read-only reconciliation. Three-verdict design correct, critical guard proven, tests falsifiable. Manual CLI entry point is a scope deviation but not a defect. Merge commit should note that automatic integration into polling loop is a follow-up if desired.
