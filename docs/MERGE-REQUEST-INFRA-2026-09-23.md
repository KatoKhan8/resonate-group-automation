# Merge request — `infra`, 2026-09-23 · increment 1: the overnight recovery and TASK-265

**For the main session.** Branch `infra`, worktree `../resonate-infra`.
Master has moved to `c8a8744c` under you; nothing here touches a file on it.

    b3e92327  Merge TASK-265: nightly backup and a restore drill
    182e8304  TASK-265 review: four ways the backup reported success
    d3fdb7ae  The restore drill, run against estates that carry records

Nothing under `config/.env`, `src/providers/`, `scripts/*_watch_loop.py` or
`work/` was read-modified or written. `work/` was listed, read-only, by the
drill at 550/5,000/20,000 records in a temp directory — never the live one.

---

## 0. THE OVERNIGHT SHUTDOWN COST NOTHING, AND HERE IS THE PROOF

Checked every worktree rather than assuming, because "the workers died" and
"the work died" are different claims.

    261  qwen-2  MERGED       infra..branch = 0 commits
    262  qwen-3  PARTIAL      merged at 7b0f92e3; still RUNNING/, no result
    263  qwen-4  MERGED       infra..branch = 0 commits
    264  qwen-5  NEVER STARTED  no commits, NO WORKER LOG, still TODO/
    265  qwen-6  STRANDED     3 commits on the branch only — recovered here

**TASK-264 was never dispatched.** There is no `.qwen-264.out` anywhere on
the machine and `qwen-5` has been idle since TASK-257. It is not a task the
shutdown interrupted; it is a task that never ran, and it is increment 2.

**TASK-262's worker was not killed by the shutdown either.** Its two logs end
in `turn_tool_call_cap` and `Repetitive tool calls detected` — it looped and
was halted at 20:32, three hours before the machine went down. Worth knowing
before it is redispatched unchanged.

**No worktree holds uncommitted source.** Every untracked file across qwen-2
to qwen-8 and qwen-worker is a dead worker's stdout/stderr, plus qwen-2's six
`bench_*.txt`. I diffed those against
`docs/BENCHMARK-PASS-WALL-CLOCK-2026-09-22.md`: the 19.3x, 11.8x and 10.7x
intermediate runs are already recorded there. Nothing was discarded and the
logs are left where they are.

**One thing that is yours, untouched:** the master worktree
`../resonate-group-automation` has `scripts/suite_verdict.txt` modified and
uncommitted. Your file, your branch, not read-modified here.

---

## 1. TASK-265 WAS DONE, ITS EIGHT TESTS WERE GREEN, AND IT WAS WRONG IN FIVE PLACES

The worker's own result block is accurate about what it built and honest
about what it could not do. The defects are all one shape — **the thing
reports success while not doing the work** — which is this register's
recurring finding arriving inside the task written to make a backup
trustworthy.

### 1.1 The archive could silently omit a state file

`collect_state_files` built an expected set from `store.STATE_OVERRIDES`,
assigned it to a local, and **never used it**. What it returned was
`os.listdir(work_dir)`. Any override resolving outside `work/` — which is
exactly what `spendledger` and `observability` do when a stale env var is
left set, the defect TASK-264 exists to remove — was omitted from the archive
with no error and no mention, and the script printed a success.

Its companion `_default_basename` carried a hand-written table of 30
filenames, and the brief had said in as many words: *the set is
`store.STATE_OVERRIDES` plus the queue — do not enumerate them by hand, ask
the module.* The table was both dead code **and already wrong**:
`SUPERVISOR_LOCKS` and `SUPERVISOR_STATE` landed with TASK-263 the same
evening, two hours before 265 was written. A list that has to be maintained
is a list that is already stale.

Fixed: the table is deleted, the directory listing is kept for the normal
case, and every `STATE_OVERRIDES` entry that IS set and resolves outside the
work directory is archived and **named in a findings list**. A missing queue
or a missing ledger is a finding, and findings make the exit code non-zero —
otherwise nightly cron reports success forever.

### 1.2 The lock was held across the listing, not the archive

    with store.lock():
        files = collect_state_files(work_dir)      # lock released here
    archive = create_archive(files, ...)           # the actual snapshot

The archive window is the zip. A checkpoint landing mid-archive gives a torn
backup, which is the one failure mode a backup may not have. The brief asked
for the lock across the archive window and released before the ship; it is
now held across listing and zip, and released before the prune.

Proven by observation rather than by reading the source: the test replaces
`create_archive` with a wrapper that checks whether the lock file exists
while it runs.

### 1.3 The prune deleted the last copy that existed

`prune_old_archives` removed every archive older than the retention age. If
backups stop for a month — which is precisely when you need one — the run
that notices begins by deleting all of them. "Retention 14 days" is a rule
about how much history to keep, not permission to reach zero. The newest now
survives whatever its age.

### 1.4 THE DRILL RETURNED ok:true HAVING RESTORED NOTHING

    result["ok"] = stats_match and manifest_matches is not False

Zero records restored, compared against a live store that also holds zero,
satisfies `stats_match` perfectly. An absent manifest gives
`manifest_matches = None`, and `None is not False`. So **an empty archive
with no manifest passed.**

This is the vacuous pass `docs/STORE-SQLITE-DESIGN-2026-09-22.md` §11 is
written to refuse, in the same repository that has now shipped it three
times — F-003's `coverage()` against nothing, `leadstop.sweep` never
incrementing its counter, and this. §11's own words are *read the count
before believing the silence*, and the drill did not.

The drill now refuses on zero restored and refuses on an absent manifest —
the manifest is in git precisely so a restore is checked against something
that is **not** in the backup, and without it the drill checks the archive
against itself. A control test proves the refusals still let a real restore
through.

### 1.5 And it shipped the defect of the task queued right after it

`run_drill` called `store.use_directory(tmp)` — which sets `QUEUE` and clears
every `STATE_OVERRIDES` entry, process-wide — then deleted `tmp` in its
`finally` and never put the environment back. The module is imported by
tests, so under full discovery every module after it inherited a `QUEUE`
pointing at a directory that no longer exists.

That is TASK-264's class exactly, shipped by TASK-265, on the same branch, on
the same day the two failing `test_invariants` classes were fixed for it.
Saved and restored unconditionally now.

### Verified not vacuous

12 new tests in
`tests/test_the_backup_cannot_report_success_while_missing_state.py`. Every
one except the deliberate control fails against the pre-fix code — run in a
detached worktree at the merge commit rather than by reverting in place, so
the branch was never in a half-state. 20 tests green across both backup
modules.

---

## 2. THE DRILL NOW HAS AN ARTIFACT, AND IT SAYS WHAT IT IS NOT

`docs/RESTORE-DRILL-AT-SCALE-2026-09-23.md`. The worker's own drill restored
zero records and correctly called itself `ok: false`; that is an honest
report and it is not a drill.

    records   queue MB   backup s   restore+verify s   verdict
        550        7.9       0.04              0.109   ok
      5,000       71.5       0.26              0.937   ok
     20,000      286.0       2.04              9.374   ok

**The lock is held for 2.0 seconds at 20,000 records** — that is how long a
live loop waits behind a nightly backup, and it is the number that decides
whether this can run unattended.

Three things the doc states before the numbers can be quoted, because a
benchmark measured at the wrong record size is already ISSUE-017:

- **Synthetic estate, not the live one.** The live 550 are in your worktree
  on `master`. This session does not read or lock the live queue. **The
  production drill is still owed** and it is two commands, in the doc.
- **The archive sizes are not plannable.** The filler deflates ~125x;
  production JSON will not. Treat them as a floor.
- **14,299 bytes mean against production's 19,819** — 28% low, so the
  timings are optimistic by about that, against four orders of magnitude of
  headroom.

---

## 3. TWO DECISIONS THIS TASK CANNOT MAKE, AND THEY ARE ONE DECISION

Raised by the worker, unresolved, and they are not independent:

**Encryption.** Stdlib has none; `zipfile` supports none. `cryptography`
(~3 MB wheel, C extension) or `pyage` (pure Python) — both third-party,
against this repo's zero-dependency rule. The worker correctly wrote the
finding instead of adding the dep.

**Off-machine destination.** None configured, no credential, and the worker
correctly refused to invent one.

They are one decision because an unencrypted archive shipped off-machine is
worse than no off-machine copy. `work/` in full carries the action ledger,
the spend ledger and client approval: a stolen archive is a client data
breach, not an inconvenience. Until both are answered the backup is
**local-only and unencrypted**, which protects against disk loss and against
nothing else.

`config/.env` is excluded by construction and asserted in two places.

---

## 4. WHAT IS NOT DONE

- **The production drill against the live 550.** Yours; the command is in the
  doc and it holds the lock for about two seconds.
- **The nightly schedule.** `backup_state.py` is a script, not a cron entry.
  It belongs with the systemd units in increment F and is written to move to
  Linux unchanged.
- **TASK-262.** Still `RUNNING/`, partial work merged, its worker halted on a
  tool-call cap rather than finishing. Not touched this increment.
- **The supervisor adoption.** See below.

---

## 5. THE SUPERVISOR (TASK-263) IS BUILT AND NOT ADOPTED

`git ls-tree master` has no `src/supervisor.py`, `scripts/supervise.py` or
`tests/test_supervisor.py`. Master's head is `c8a8744c` at 00:54, and its
handoff lists supervisor adoption as item 2 for the no-send window — *"after
23:00 and before 07:00: merge its merge request, move monitors under it ONE
AT A TIME starting with the least critical, never two instances of one, then
post `--status` showing all UP."* The machine went down first.

It is merged, tested and waiting on `infra`. The adoption is yours and the
one-at-a-time rule in that handoff is the right one.
