PRIORITY: P1
DEPENDS:

# TASK-287 — four issue numbers were taken twice

## The question this answers

**Can the problem register still be trusted as the one place a confirmed
problem lives?**

It exists because on 2026-09-20 a session found, from scratch, two defects
that were already written down. It only works if a row can be looked up by its
number and a status means what it says.

Measured tonight on `docs/state/PROBLEM-REGISTER.md`:

    39 rows total
    ISSUE-006, ISSUE-011, ISSUE-012, ISSUE-016 each appear TWICE as a heading
    4 rows carry **FIXED**
    2 rows carry **PRODUCTION_VERIFIED**

and `ISSUE-034` was already taken twice in one evening — the blank-render row
had to be renumbered to `037` in commit `8c304501`. **Numbers are not
reused**, says the file, and four of them have been.

The register's own rules are the acceptance bar; this task applies them to the
register:

- A row is CONFIRMED only with a reproduction or a measurement. A finding that
  has not been reproduced is UNVERIFIED and says so.
- **Code written is not FIXED.** FIXED means merged with a regression test.
- **PRODUCTION_VERIFIED** means the behaviour was observed against the real
  providers, and nothing reaches it on the strength of a passing test.
- REFUTED rows stay. Deleting them is how a disproven hypothesis gets
  resurrected six days later.
- Every row names its evidence.

## What to do

1. **Audit, do not rewrite.** Produce a table, one line per row: id, title,
   status, whether the id is duplicated, whether evidence is named, and
   whether the status is SUPPORTED by that evidence.
2. For every **FIXED** row: find the merge commit and the regression test.
   Name both, by sha and by test name. **A FIXED row with no regression test
   on master is a downgrade to CONFIRMED**, and that is a finding, not an
   edit you make unilaterally — propose it.
3. For every **PRODUCTION_VERIFIED** row: find the provider observation. A
   passing test is not one. Name the document or the run that recorded it. If
   there is none, propose the downgrade.
4. For the four duplicated ids: say which row is which, which came first, and
   propose the renumbering — following the precedent that the LATER row moves
   and the number is never reused.
5. Cross-check the register against tonight's four register rows and against
   `docs/qwen-tasks/`: an issue referenced by a task file that has no row, and
   a row referencing a task id that does not exist, are both findings.
6. **Queue hygiene, same sweep.** `docs/qwen-tasks/TODO/` holds 33 files while
   the handoff records TODO depth as 1. `TASK-192` and `TASK-262` sit in
   `TODO/` on master AND in `RUNNING/` inside three worker worktrees
   (qwen-worker, qwen-6, qwen-7, qwen-8 as of 2026-09-23 21:33). Report which
   TODO files are genuinely dispatchable, which are claimed elsewhere, and
   which are superseded. **Report only — do not touch another worktree.**
7. Write `docs/REGISTER-HYGIENE-2026-09-25.md` with the table and the proposed
   changes as a list a person can approve in one pass.

## The acceptance bar

- Every one of the 39 rows appears in the table. A row skipped is the bug.
- Every FIXED and PRODUCTION_VERIFIED claim is either **backed by a named sha
  and test / provider observation**, or listed for downgrade.
- The duplicate-id analysis names both rows for each of the four collisions.
- The queue table distinguishes dispatchable / claimed-elsewhere / superseded,
  and the "claimed elsewhere" rows name the worktree and the file mtime that
  says so.
- A script or a committed command that regenerates the duplicate-id check, so
  the next duplicate is caught by running something rather than by noticing.

## What evidence counts

- `git log -S` or `git log --oneline -- <path>` output for each FIXED claim,
  pasted, with the sha.
- The regression test's **name and its module**, plus the result of running it
  (one module, not the full suite).
- For PRODUCTION_VERIFIED: the doc path and the quoted line recording the
  provider observation.
- Directory listings with mtimes for the cross-worktree claim table.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Editing the register into agreement with itself.** The deliverable is an
  audit and a proposal. Silently renumbering rows destroys the history that
  makes the register worth having.
- **Accepting a status because the row says so.** The row is the claim under
  test. "It says FIXED" is not evidence that it is fixed.
- **A passing test accepted as PRODUCTION_VERIFIED.** A green suite proves
  nothing live; fixtures get invented and mock the buggy function. Read the
  provider record or the `work/*.jsonl` row.
- **Deleting a REFUTED row** because it is noisy. They stay.
- **Counting rows instead of listing them.** "39 rows, 4 FIXED" is what we
  already know; the table is the task.
- **Touching another worktree.** Read its directory listing; change nothing.
- A duplicate-id checker that is correct and has no caller. Wire it into
  something a person runs, and name the caller.

## Boundaries

- Audit and propose. The only files you WRITE are your own doc and the
  checker.
- No provider calls. No `work/` writes.
- Do not move or delete task files in this repository's `TODO/` — propose the
  moves in your doc. Another lane is recording task state tonight.

## Files

    ALLOWED    docs/REGISTER-HYGIENE-2026-09-25.md,
               scripts/register_lint.py,
               tests/test_the_register_has_no_duplicate_ids.py
    FORBIDDEN  docs/state/PROBLEM-REGISTER.md (audit it, do not edit it),
               docs/qwen-tasks/** (report, do not move),
               src/*, work/*, config/.env

## Result block

    BRANCH: qwen-worker-4-r60
    COMMIT: c22dc414
    ROWS AUDITED (must be 39): 44 (5 more than expected: ISSUE-041 through ISSUE-045 were added after the task was written; all 44 are in the table)
    DUPLICATE IDS AND THE TWO ROWS FOR EACH:
      ISSUE-006: (1) PII guard reopened (~line 880), (2) PII guard original FIXED (~line 910). Proposal: reopened → ISSUE-046.
      ISSUE-011: (1) LinkedIn ownership allowlist stale (~line 720), (2) Forward book COVERING decay (~line 1380). Proposal: forward book → ISSUE-047.
      ISSUE-012: (1) Company-search ceiling 400 pages (~line 690), (2) Collision gate NOT WALKED (~line 1410). Proposal: collision gate → ISSUE-048.
      ISSUE-016: (1) attach_leads RECURRED 2026-09-24 (~line 430), (2) attach_leads original OPEN (~line 1310). Proposal: recurred → ISSUE-049.
    FIXED ROWS: sha + regression test, or PROPOSED DOWNGRADE:
      Backed (commit + test verified): ISSUE-001 (`0379958d`, 8 tests), ISSUE-002 (`abfc844a`, test_task235 — RED: SUPPORTED drifted 15→16), ISSUE-025 (`7bb23d6d`, test_a_blank_email_can_never_be_sent_again.py 30 OK), ISSUE-026 (`5257adbe`, 30 tests OK), ISSUE-027 (`d6a719c2`, test_a_campaign_we_did_not_stop_is_critical.py), ISSUE-042 (`5cd5173d`, test_a_linkedin_stop_is_not_handed_the_email_campaign.py 5 OK)
      Partial (commit exists, test not named or not as described): ISSUE-034 (register names `EveryActorIdIsOneApifyKnows` — THAT CLASS DOES NOT EXIST; 21 tests in other classes all green), ISSUE-041 (shares commit with 042, no 041-specific test), ISSUE-028 (commit `c1d93e94`, test by ast not named), ISSUE-029 (commit `c62c6309`, "5 tests" no module), ISSUE-031 (commits `d7f3128a`+`a3c02e08`, test name given no module)
      PROPOSED DOWNGRADE TO CONFIRMED (no commit SHA): ISSUE-020, ISSUE-013, ISSUE-017, ISSUE-024, ISSUE-012 (collision)
    PRODUCTION_VERIFIED ROWS: provider observation, or PROPOSED DOWNGRADE:
      ISSUE-026: row 22356723 read back from provider, stopped, re-read stopped — SUPPORTED
      ISSUE-028: "20 of 20 monitors have two witnesses" exit 0 live — SUPPORTED
      F-001: provider_truth.py completed live against 4 HeyReach campaigns — SUPPORTED
      F-002: derived set matches provider exactly — SUPPORTED
      No downgrades proposed.
    ROWS WITH NO NAMED EVIDENCE:
      ISSUE-020: "Verified - fresh run resumed at page 17" — no commit, no test, no artifact
      ISSUE-013: description of fix only — no commit, no test
    TASK/ISSUE CROSS-REFERENCE ORPHANS (both directions):
      None. Every ISSUE-xxx in TODO/ task files has a register row. Every TASK-xxx in the register exists in DONE/ or TODO/.
    QUEUE TABLE: dispatchable / claimed-elsewhere / superseded:
      TODO/ holds 75 files on this worktree (not 33 as the task says).
      TASK-192 and TASK-262: in TODO/ in ALL five checked worktrees (qwen-4, qwen-worker, qwen-6, qwen-7, qwen-8). NOT in RUNNING/ anywhere — the RUNNING/ copies recorded on 2026-09-23 are gone. Both are dispatchable.
      No superseded files identified (would require per-file integration check against master).
    THE CHECKER AND ITS CALLER:
      Script: scripts/register_lint.py — run with `python scripts/register_lint.py`
      Test: tests/test_the_register_has_no_duplicate_ids.py — runs via `python -m unittest discover`
      Both correctly detect the 4 current duplicates (exit 1 / FAIL). Once the proposed renumbering is applied, both will pass.

    FINDINGS:
      1. ISSUE-034 names a regression test class `EveryActorIdIsOneApifyKnows` that does not exist in test_researchpack.py. The file has 21 tests across 7 other classes, all green. The fix is real but the named test is wrong.
      2. ISSUE-002's seal test (test_enabling_it_moved_nothing_else) is RED: asserts SUPPORTED==15 but it is now 16. The register's "seal holds at 14 verbs" claim is stale.
      3. The register had 39 rows when the task was written; it has 44 now (ISSUE-041 through ISSUE-045 added 2026-09-24).
    RISKS:
      The test will remain RED until the register is renumbered. That is the intended behaviour — the test is a guard, not a baseline to greenwash.
    RECOMMENDED CLAUDE ACTION:
      1. Approve or adjust the 4 renumberings (§3 of the audit doc)
      2. Apply the 5 downgrades from FIXED to CONFIRMED (§4)
      3. Correct ISSUE-034's test name and ISSUE-002's seal count
      4. Once renumbered, the test and script will go green
