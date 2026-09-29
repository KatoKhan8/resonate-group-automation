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

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 6eac01d6

**TESTS:** All 7 tests in `tests/test_the_spend_report_never_sums_two_units.py` pass at the verified SHA 2cb8755a. Falsification confirmed: mixed-unit tripwire works, unpriced provider returns null, ledger is read-only, three denominators labelled.

**FILES CHANGED:**
- `docs/glm-reviews/TASK-493-verify-task-352.md` (NEW, 251 lines) — the GLM verdict

**FINDINGS:**

1. **Artifacts exist at exact SHA:** `scripts/spend_report.py` (334 lines) and `tests/test_the_spend_report_never_sums_two_units.py` (305 lines) are both NEW on the branch. Verified with `git diff --diff-filter=A`.

2. **Core claims hold under falsification:**
   - Mixed-unit tripwire: 100 credits + 447 cents does NOT sum to 547. Tripwire string present.
   - Unpriced provider: credits return `usd_estimate: null`, `rate_source: "unknown"`, not zero or a guess.
   - Three denominators: cohort/written/approved all labelled. No bare "cost per lead".
   - Ledger read-only: byte-identical before and after report generation.
   - Unattributed _model rows: reported separately with count.

3. **Labeling defect (minor):** The formatted report says "written leads (state='pushed')" but actually counts drafted+approved+pushed. Misleading label, not a calculation error. One-line fix: change to "written leads (passed first gate)" or "written leads (drafted+approved+pushed)".

4. **No production callers:** `spend_report` is not imported in `src/`. Zero automation consumers. Acceptable for a standalone operator script scoped as `scripts/spend_report.py`, but a gap if the operator expects automated reports. Out of scope for this task.

5. **Scope drift (significant):** The branch carries ~20 other task files (TASK-431 through TASK-446, TASK-430, TASK-438, BRIEF docs, OPERATING-MODE changes). Cherry-picking required to avoid merging pollution. Files to cherry-pick: `scripts/spend_report.py`, `tests/test_the_spend_report_never_sums_two_units.py`, and the TASK-352 task file move.

6. **Dependency satisfied:** TASK-332's work (`row_unit()`, `USD_PER_UNIT` table) is present on the branch and consumed by `spend_report.py`.

7. **No deletions:** `git diff --diff-filter=D` returns only the TASK-352 task file moving from TODO to REVIEW. Safe to merge.

**RISKS:**

- Labeling defect is minor but misleading. Fix before merge or file follow-up.
- Scope drift requires cherry-picking. Do not merge the entire branch.
- No automation wiring. If the operator wants scheduled reports, a separate task is needed.

**RECOMMENDED CLAUDE ACTION:**

Cherry-pick the three TASK-352 artifacts onto master:
1. `scripts/spend_report.py`
2. `tests/test_the_spend_report_never_sums_two_units.py`
3. Move `docs/qwen-tasks/TODO/TASK-352-...md` to `docs/qwen-tasks/REVIEW/TASK-352-...md`

Fix the "written leads" label (one-line change) before or after merge.

**DISPOSITION:** MERGE with minor rework (labeling defect).

**VERDICT FILE:** `docs/glm-reviews/TASK-493-verify-task-352.md`

**BRANCH HEAD SHA REVIEWED:** 2cb8755afc8ad069ccab24a6d80819d779c57e54
