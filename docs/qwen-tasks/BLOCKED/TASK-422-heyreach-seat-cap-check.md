PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-422 — Heyreach Seat Cap Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `heyreach-seat-cap-check`.

Is any HeyReach seat over its own daily/weekly connection cap? Read every
attested seat's configured cap against actual sends this period via a REAL
read-only provider read. Report any seat at or over 90% as a finding.
READ-ONLY. No campaign, seat or cap modification. Acceptance: a real
per-seat table (cap, actual, %); anything over 90% named explicitly.

## RESULT BLOCK

STATUS: BLOCKED
COMMIT SHA: c5a100b4 (branch: qwen-worker-6-r9-task422)
TESTS: n/a - no code changed
FILES CHANGED: docs/qwen-tasks/RUNNING/TASK-422-heyreach-seat-cap-check.md (this file)
ARTIFACT KIND: finding

### FINDINGS

**Two independent blockers prevent the acceptance-criteria table from being
produced. Neither is solvable from this worktree.**

#### Blocker 1: No credentials

`config/.env` is absent from this worktree. Without `HEYREACH_KEY`, no
provider read of any kind is possible. The file is gitignored (`.gitignore`
line 5: `config/.env`) and was not placed in this worktree before the
session started. QWEN.md states credentials are present in all eight
worktrees; in this one they are not.

#### Blocker 2: The per-seat actual-usage endpoint does not exist

Even with credentials, the HeyReach API surface mapped by this codebase
exposes **configured caps but no per-seat usage counters**. This is
documented in the code, not discovered here:

- `src/providers/heyreach.py`: `/li_account/GetAll` returns 15 keys per
  seat including `accountLimits` (with `connectioRequestLimit`,
  `connectioRequestMax`, `messageLimit`) but no used-today or
  remaining-today field.
- `src/senderinventory.py` (lines 174-207) establishes this definitively:
  "NEITHER IS A REMAINING-TODAY COUNTER, and the provider exposes none.
  The seat row has fifteen keys and `accountLimits` twelve numbers; not
  one of the twenty-seven is a used-today or left-today figure."
- `/stats/GetOverallStats` accepts `accountIds` as a filter but returns
  aggregate `overallStats`, not per-account breakdowns. It is also
  campaign-scoped (`campaignIds` required), so it only covers campaigns
  this system can see (40 of 121 total in the account).

The configured caps from cached state (`docs/state/SENDER-CAPACITY.json`,
generated 2026-09-21, now 7 days stale) are:

| Metric | Value |
|--------|-------|
| Total seats | 41 |
| Healthy (auth valid, active) | 33 |
| Auth invalid | 1 |
| Inactive | 7 |
| Connection request capacity/day (healthy) | 1,054 |
| Message capacity/day (healthy) | 1,143 |

Per-seat configured connection limits vary: 0, 5, 10, 15, 17, 18, 19,
22, 23, 25, 40. Seat `li-139699` is configured at 0 (cannot send
connection requests at all). But **actual sends per seat this period
cannot be read from any endpoint on the allowlist**.

#### What would be needed

1. `config/.env` placed in this worktree (or the measurement run from
   Claude's worktree where credentials exist).
2. A HeyReach per-seat usage endpoint, which does not exist today. The
   alternatives are:
   - Derive from `/stats/GetOverallStats` per campaign per seat - but
     this covers only Resonate's 40 of 121 campaigns, and the client's
     81 campaigns on shared seats are invisible.
   - Use the action ledger (`seatledger.py`) as a lower bound - but
     `work/action.jsonl` is in Claude's worktree and is only populated
     when real sends happen through this system.
   - Ask the vendor whether a per-seat usage route exists that has not
     been discovered yet.

#### Recommendation

This standing backlog entry cannot be fulfilled as written until either
HeyReach exposes per-seat usage or the operator accepts a campaign-level
aggregate as a proxy. The task should be re-scoped or deferred until the
API surface changes.

### RISKS

The cached `SENDER-CAPACITY.json` is 7 days stale. Seat limits, health
status and campaign assignments may have changed since 2026-09-21.

### RECOMMENDED CLAUDE ACTION

Re-scope this standing backlog entry. The acceptance criteria (a
per-seat table with cap, actual, %) cannot be met because "actual" has
no provider-side source. Either:
1. Remove `heyreach-seat-cap-check` from the standing backlog template
   until the API changes, or
2. Re-scope to "report per-seat configured caps and health from a fresh
   `/li_account/GetAll` read" (which IS achievable), dropping the
   actual-usage column.
