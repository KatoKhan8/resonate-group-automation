PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-384 — the dispatcher cannot see "do not dispatch," only file location

**Operator instruction, 2026-09-26/27 overnight standing order.** Measured
twice tonight: TASK-309 (operator-forbidden, "permanently merge-blocked")
and TASK-334 (its own header said "ABSORBED BY TASK-369... do not dispatch
while TASK-369 is open") were both auto-dispatched by `scripts/pool.sh`'s
sweep, because `scripts/claim_task.py`'s `ready_tasks()` only checks file
location (TODO/RUNNING/REVIEW/DONE) and a `DEPENDS:` header field — it has
no concept of a task file's own prose saying "do not run this," or of one
task superseding another by content rather than by the DEPENDS field.

`pool.sh` grew a hand-maintained `FORBIDDEN_TASKS` array tonight as an
emergency patch (one entry: `TASK-309`). That does not scale and does not
read the task files themselves — a human has to remember to add every new
forbidden id by hand, in a second file, forever.

## Build

    scripts/claim_task.py   MODIFY

1. Parse a structured `STATUS: BLOCKED` or `ABSORBED_BY: TASK-nnn` field
   from a task file's own header (alongside the existing `PRIORITY:`,
   `SIZE:`, `DEPENDS:` lines) — do not parse prose for keywords, add an
   explicit field the header convention already has room for.
2. `ready_tasks()` excludes any task carrying `STATUS: BLOCKED` unconditionally,
   and excludes `ABSORBED_BY: TASK-nnn` when TASK-nnn is DONE on master (the
   absorbing task finished, so this one is moot) — but INCLUDES it if the
   absorbing task is not yet done (matches TASK-334's own instruction: "do
   not dispatch this task WHILE TASK-369 is open").
3. Retrofit the two known cases: add `STATUS: BLOCKED` to TASK-309's header
   (it is `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md`-adjacent and
   permanently blocked, not conditionally); TASK-334 no longer needs the
   field since it is already closed (DONE).
4. Remove `FORBIDDEN_TASKS` from `scripts/pool.sh` once `claim_task.py`
   enforces this itself — one source of truth, not two.

## Acceptance

1. `py -3 scripts/claim_task.py --status` no longer lists TASK-309 as ready,
   with no hand-maintained blocklist in `pool.sh`.
2. Add a temporary `STATUS: BLOCKED` header to a throwaway TODO task, confirm
   it drops out of `ready_tasks()`, remove the header, confirm it reappears.
3. Add a temporary `ABSORBED_BY: TASK-999` (a task that does not exist / is
   not DONE) to a throwaway TODO task, confirm it STAYS ready (matches
   TASK-334's own "do not dispatch WHILE open" semantics — absence of the
   absorbing task being done means still dispatchable). Then fake TASK-999 as
   DONE and confirm it drops out.
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the current baseline.

## What this task may NOT do

- Do not remove the existing DEPENDS mechanism — this is additive.
- Do not silently reinterpret prose headers as structured fields — require
  the explicit `STATUS:`/`ABSORBED_BY:` line; a task file without one is
  unaffected.
- Nothing sent, nothing activated.
