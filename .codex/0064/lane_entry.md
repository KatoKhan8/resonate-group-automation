## 2026-10-15 — TASK 0064 — the detached worktree: what 0055 did, and the 406 attributed

Brief: `queue/glm/RUNNING/0064-the-detached-worktree.md` (GLM-A). `_STANDING-RULES.md`
read first, as ordered. No push, no merge, no lock release, no other lane's worktree, no
production `work/` read. All measurements in `wt-glm-review-2026-10-14` unless a path says
otherwise. Analysis scripts and raw outputs kept in `.codex/0064/` (q3_analysis.py,
q3_tracebacks.py, q3_out.txt, q3_trace_out.txt, dangling.txt).

### Q1 — what `1ea8105bf` is

`1ea8105bf` (`1ea8105bf1aaf21446bbfb0475e710fa42b13be6`) is the cherry-pick of TASK 0020's
born-red commit `6caa9ea58` ("born-red test - the halt's pause fails OPEN without a
GateToken") onto `a942a4b4a`, then the tip of `task-glm-halt-failopen-2026-10-15`. Reflog
of this worktree (`.git/worktrees/wt-glm-review-2026-10-14/logs/HEAD`, +0200):

- 11:05:59 commit `93162471d` TASK 0060, on `task-glm-review-2026-10-14`
- 11:19:12 checkout `task-glm-review-2026-10-14` -> `task-glm-halt-failopen-2026-10-15`
- 11:19:12 cherry-pick of `6caa9ea58` creates `1ea8105bf` — the nine same-second file
  mtimes at 11:19:12 are this checkout plus the cherry-pick's one file, not nine edits
- 11:22:08 commit `b77cd4b20` "TASK 0055: the blank-email halt fails OPEN - bison.pause
  needs no GateToken" (parent `1ea8105bf`)
- 11:22:28 checkout DETACHED at `1ea8105bf`
- 14:20:01 checkout back to `task-glm-review-2026-10-14` (TASK 0063's restore);
  14:36:36 -> 14:37:04 detach to `9718023a6` and back was 0063's Run B, not a regression

Contained ONLY in `task-glm-halt-failopen-2026-10-15` (local = origin; it is the parent of
tip `b77cd4b20`). Not on `task-glm-review-2026-10-14`, not on any master.

Why 0055 moved there: YES — the red-test reason. Its ordered fix targets the halt defect
that exists only on a lineage carrying the `providerwrites.GateToken` sink demand. Measured:
`grep -c GateToken` on `src/providerwrites.py` is 0 at `93162471d` and 6 at `1ea8105bf`.
The born-red test's own docstring names that lineage — "MEASURED on
`task-pilotcaps-enforcer-2026-10-14` (`4d2d19b9b`), the branch that added
`providerwrites.GateToken`" — and the test file is blob-identical at `93162471d` and
`1ea8105bf` (absent from the 36-file diff between them), so the red comes from the src
side of that lineage, exactly as designed. On `task-glm-review-2026-10-14` the same test
is green and the defect does not reproduce.

The detach itself (11:22:28, 20 s after committing the fix) was 0055 standing on the
PRE-FIX tree `1ea8105bf` to launch the "before" leg of the both-directions name diff its
brief demanded: the 11:22-12:00 suite ran AT `1ea8105bf`. Its session died before the
suite finished — the standing-rules loss pattern — and the tree stayed detached until
0063 restored it at 14:20:01.

### Q2 — uncommitted work in the detached tree: none; 0055's work is durable

- `git status --porcelain` today: only `?? .codex/` (0063's artifacts, untracked by
  design). 0063's checkout at 14:20:01 could only have succeeded onto a clean tree, and
  nothing dirty was carried over — so nothing was uncommitted in the detached tree either.
- The 11:22 suite's outputs (`scripts/suite_run.log`, `scripts/suite_verdict.txt`) are
  gitignored (`.gitignore:32` `*.log`, `:110` `suite_verdict*.txt`) — the run left no
  tracked dirt.
- `git stash list`: one stale entry, `WIP on qwen-worker-5-r9: 2bf7b8a57` (10-14, another
  worktree). Untouched.
- `git fsck --dangling`: 346 dangling commits, all dated 2026-09-13..2026-10-13. ZERO
  from 2026-10-15, so none is 0055's. Nothing of 0055's was ever uncommitted-preserved
  because nothing needed it: `1ea8105bf` (the cherry-pick) and `b77cd4b20` (the fix) are
  on `task-glm-halt-failopen-2026-10-15`, local AND origin (rev-parse local = origin).
- `ORIG_HEAD` still reads `2bf7b8a57` (worktree birth, stale, cosmetic — no action).
- `scripts/bison_watch_loop.py` mtime 02:05:14 and untouched: confirmed — it is not among
  the 36 files in `git diff --name-status 93162471d 1ea8105bf`.

### Q3 — the 406 names: measured by name-set, attributed

The run itself belongs to `1ea8105bf` in this worktree: reflog window 11:22:28 -> 14:20:01
has the tree at exactly `1ea8105bf`; `scripts/suite_verdict.txt` (mtime 12:00:35) reads
status=FAIL, exit_code=1, wall_seconds=2279.9, failures=406, result_line "FAILED - 271
failure(s), 139 error(s) of 14888", results_reached=14847. Wall arithmetic puts the start
at ~11:22:35, 7 s after the detach; glm-c's 0110 entry records this run acquiring the
machine lock at 11:22:34.

Independent re-derivation from the two sanctioned verdict files (this tree's, and
`resonate-ops/ref-2bf7b8a57/scripts/suite_verdict.txt`, the frozen reference at `2bf7b8a57`):

- review 406 vs master 228 (at `2bf7b8a57`): **NEW 180, GONE 2, BOTH 226** — reproduces
  pilotcaps 0100's arithmetic exactly.
- GONE 2, named: `test_invariants.TestNothingCanSend.test_no_module_issues_an_http_post_outside_the_named_ones`,
  `test_secrets.TestNoRealCredentialInTheRepository.test_no_tracked_file_contains_a_credential_shaped_assignment`
  — both already verified positively as PASSING in this run's log by pilotcaps 0100
  (unittest prints docstrings between name and outcome; a one-line reader calls a passing
  test missing). Not re-derived here.

NOT the 10:34 suppression write in production `work/`:

- `work/` is per-tree; this suite read THIS tree's `work/`, never the production one.
- The suppression tree's own 04:22 run — BEFORE the 10:34 write — is name-set identical
  to master's 228 (pilotcaps 0100).
- The only suppression-adjacent failing name,
  `test_fixture_hygiene.TestTheSuppressionRosterIsNotInGit.test_the_real_roster_is_ignored_so_it_cannot_be_added_by_accident`,
  fails in this run's log with `AssertionError: 3221225794 != 0 : config/suppress.local.txt
  is not gitignored` — the `git check-ignore` subprocess never started (0xC0000142 =
  STATUS_DLL_INIT_FAILED) and its exit code was read as the answer. The test learned
  nothing about the roster; it got no answer from git.

What the 180 NEW are made of (my classifier over this run's own log; 405/406 tracebacks
recovered, all 180 NEW classified):

- 81 class A — raw `3221225794` in the traceback; subprocess never started.
- 39 class B — subprocess produced nothing (empty output read as a result).
- 120/180 process-creation failure. The remaining 60 class C include whole modules whose
  tests ARE subprocesses (supervisor, systemd units, deploy, backup, migration,
  `test_task920`'s PreservedGreen re-runs of other suites) and 3
  `test_one_full_suite_at_a_time` names that are literally about the lock.
- Cross-branch corroboration (pilotcaps 0100, glm-c 0110): 146 of the 180 NEW also fail
  on glm-c's candidate at `38c0db9c4` — a different branch, which no branch's code can
  cause. The two full suites overlapped 11:22:34-11:28:01 (this run took the lock while
  glm-c's candidate, holder since 10:48:56, still had it — enabled by the suitelock
  false-DEAD theft, `src/suitelock.py:156`, GLM-A 0050 forensics).

The lineage share, bounded by measurement on this run:

- NEW names inside a test module ABSENT at `2bf7b8a57`: exactly 1.
- NEW names inside a test module whose content differs `2bf7b8a57` -> `1ea8105bf`:
  exactly 1. Same name both times:
  `test_a_safety_pause_fails_open.TheHaltPausesWithoutAGateToken.test_the_pause_is_performed_with_no_gatetoken_presented`
- 406 names inside any module whose content differs `93162471d` <-> `1ea8105bf`: 0.

Every NEW failure except that one ran byte-identical test code that already existed at
master ref `2bf7b8a57`. The one exception is the born-red halt test — red BY DESIGN on
the GateToken lineage, and its traceback in this run's log is the defect itself (the
assertion wanted `paused: 497` and got the HALT-REFUSED branch). Measured green at the
branch tip `93162471d`: twice by 0063 (Run A 14:35, Run B 14:36) and once by me today
(`py -3 -m unittest tests.test_a_safety_pause_fails_open -v` at `93162471d`: 1 test,
OK, 0.044s). That name belongs to `1ea8105bf` and its lineage by construction; no other
name in the 406 is proven to.

Residues left open, named as UNKNOWN:

- 59 class-C NEW names (60 minus the born-red one) are not individually attributed. The
  deciding measurement is ONE uncontended full run, and it cannot happen under the
  current lock. **The lock is not released by this task**: still held by dead pid 83600
  (glm-c 0110's reference run, died 14:38:31). A `run_suite` launch takes a dead
  holder's lock over loudly — that decision belongs to the next legitimate full-suite
  lane, not to 0064.
- 41 results not reached in this run (14888 total - 14847 reached) — same shape as
  glm-c's 40-unreached anomaly; cause unknown.
- The 34 review-only names (in the 406, not in glm-c's 385) cannot be decomposed from
  sanctioned sources: the candidate 385 name-list lives in
  `wt-glm-c-2026-10-14/work/suite_0100_candidate.out`, outside this lane's sanction.
  They fall inside the 406-at-`1ea8105bf` attribution and the class analysis above.

### Q4 — the worktree is back on its branch

Accomplished by TASK 0063 at 14:20:01 (reflog checkout `1ea8105bf` ->
`task-glm-review-2026-10-14`), before this task ran. Re-verified at this task's end:
worktree HEAD file reads `ref: refs/heads/task-glm-review-2026-10-14`; `git rev-parse
HEAD` = `93162471d` = branch tip = 0060's commit; `git status --porcelain` clean apart
from `?? .codex/`. No checkout was performed by 0064 — the end state was already true,
per 0063's entry, and forcing a redundant checkout would only add reflog noise.

### Close

Fixing the halt is TASK 0065's, not this one's — no code was changed in this task and
nothing was committed. Nothing this task depends on is running; nothing was launched in
the background. Next: `queue/glm/0065-fix-the-halt-in-the-foreground.md`.
