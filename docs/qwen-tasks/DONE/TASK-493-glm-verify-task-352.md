PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-493 — GLM independent verification: TASK-352, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-352
    branch          origin/qwen-worker-4-r9
    branch HEAD SHA 2cb8755afc8ad069ccab24a6d80819d779c57e54

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`2cb8755afc8ad069ccab24a6d80819d779c57e54` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`2cb8755afc8ad069ccab24a6d80819d779c57e54` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-493-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** e5ebe99c1

**TESTS:** All 7 tests in `tests/test_the_spend_report_never_sums_two_units.py` pass. All 15 existing ledger tests in `tests/test_ledger_does_not_sum_across_units.py` also pass. 22 total, all green.

**FILES CHANGED:**
- `docs/glm-reviews/TASK-493-verify-task-352.md` (NEW) — the verdict
- `docs/qwen-tasks/DONE/TASK-493-glm-verify-task-352.md` (MOVED from TODO)

**ARTIFACT TYPE:** Document (GLM verdict)

**FINDINGS:**

**Verdict: MERGE with minor cosmetic findings.**

Reviewed `origin/qwen-worker-4-r9 @ 2cb8755afc8ad069ccab24a6d80819d779c57e54` in an isolated worktree. The SHA was verified with `git rev-parse` and has not moved.

1. **Artifacts exist:** `scripts/spend_report.py` (334 lines) and `tests/test_the_spend_report_never_sums_two_units.py` (305 lines) both exist at the exact SHA, added in commit `84129e4ea`.

2. **Does what the result block claims:** All 6 acceptance criteria verified independently. The mixed-unit tripwire works, all three denominators appear labelled, unpriced providers report null, `_model` rows are separated, the ledger is byte-identical after the report, and the cost-per-lead math is correct (6.29c / 10.15c / 24.20c on 50 leads / $3.1464).

3. **Not disconnected:** The script is a CLI endpoint (`py -3 scripts/spend_report.py --client productive`), not a pipeline module. The operator is the consumer. This is the same pattern as TASK-299's `scripts/qa/check_reconcile.py` and TASK-297's `scripts/qa/check_campaign_heyreach.py`, both merged as READS ONLY CLI tools. Zero `src/` importers is correct for this artifact type.

4. **Tests are falsifiable:** Assertions are on behavior (formatted output strings, exact counts, None checks, byte-identity), not on `hasattr` or source text. Mutation test performed: setting `mixed_units=False` is caught.

5. **No deletion risk:** `git diff master...2cb8755af -- src/ scripts/ tests/` shows only 2 new files, 639 insertions, 0 deletions.

6. **Scope drift (SIGNIFICANT):** The branch carries 24 files total. Only 3 belong to TASK-352 (the two code files + task file movement). The other 21 are 16 GLM verdict task files, TASK-430, TASK-438, OPERATING-MODE changes, and a dry-run brief. Cherry-pick only the TASK-352 files.

**Two cosmetic findings:**
- **A) Label bug:** `format_report()` says `written leads (state='pushed')` but the code counts `{drafted, approved, pushed}` — three states. The label misleads. The result block and code logic are correct; only the display string is wrong. Fix: change label to `written leads (drafted/approved/pushed):`.
- **B) Unused import:** `clients` is imported on line 44 but never used. Fix: remove from import.

Both are fix-during-integration or defer. Neither blocks the merge.

**NOT VERIFIED:** Live run against the real ledger (`py -3 scripts/spend_report.py --client productive`) — requires `work/queue.jsonl` and the live spend ledger, not present in this worktree.

**RISKS:** The label bug could confuse the operator on first read. The data is correct; only the display label is wrong.

**RECOMMENDED CLAUDE ACTION:** Merge with cherry-pick (only the two code files + task file movement). Optionally fix the label bug and unused import during integration, or defer to a follow-up.

**TASK-493 file note:** The task file says to write the verdict to `TASK-493-verify-task-219.md` — this is a copy-paste error from TASK-431. The correct target is TASK-352, and the verdict was written to `TASK-493-verify-task-352.md`.
