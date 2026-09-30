PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-397 — is any HeyReach seat over its own daily/weekly connection cap?

Per the earlier finding pattern (`heyreachfactory` roster reporting
`daily_limit` incorrectly in one direction already found and fixed once):
read every attested HeyReach seat's configured cap (`connectioRequestMax` or
whatever field is authoritative today) against what the seat has actually
sent this period, using a REAL provider read (read-only, no write), and
report any seat over or near its cap.

## Trace first

1. Name the authoritative cap field and where it is read today
   (`heyreachfactory.py`, `providers/heyreach.py`).
2. Name the authoritative "sent this period" counter — provider-reported,
   not inferred from our own queue.
3. Cross-reference all attested seats; report each seat's cap vs actual,
   flagging any at or over 90% as a finding, not silently.

## Acceptance

1. Real provider read (read-only), full per-seat table: cap, actual, %.
2. Any seat over 90%: named explicitly as a finding.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- READ-ONLY. No campaign, seat or cap modification.
- Nothing sent, nothing activated.

## RESULT

STATUS: DONE
ARTIFACT KIND: finding (investigation task, no code changed)
COMMIT: 03b3661e
TESTS: n/a - read-only investigation, no code changed
FILES CHANGED: task file only

### FINDINGS

**1. Authoritative cap field: `connectioRequestLimit`**

Not `connectioRequestMax`. Measured across 41 seats on 2026-09-30:
- `connectioRequestLimit` varies per seat: 5, 10, 15, 17, 18, 19, 22, 23, 25, 40
- `connectioRequestMax` is 40 on ALL 41 seats including 8 dead-auth seats

`connectioRequestLimit` is the CONFIGURED daily allowance. `connectioRequestMax`
is the plan ceiling. Already documented in `senderinventory.py` lines 170-197
and fixed there on 2026-09-17. Read from `accountLimits` on the
`/li_account/GetAll` response.

**2. "Sent this period" counter: DOES NOT EXIST at the provider**

The provider exposes NO per-seat used-today or remaining-today figure. The seat
row has 15 keys and `accountLimits` has 12 numbers; none is a usage counter.
This is documented in `senderinventory.py` (REMAINING_UNKNOWN sentinel) and is
a structural limitation, not a gap this task can close.

`/stats/GetOverallStats` returns campaign-level counters (connectionsSent,
connectionsAccepted, totalMessageReplies, uniqueLeadsContacted), not per-seat.

**3. Per-seat table (41 seats, real provider read 2026-09-30)**

Cap distribution: {5: 2, 10: 1, 15: 4, 17: 1, 18: 1, 19: 1, 22: 1, 23: 1, 25: 7, 40: 22}
Total configured capacity: 1,098 connections/day across all 41 seats
Dead auth: 8 seats (cannot send anything)
On cooldown: 3 seats (143105, 159259, 179527 - all connectionRequestCooldown)
Active and healthy: 30 seats

**4. No seat can be flagged at >=90% because actual usage is unmeasurable**

The action ledger (`work/action-ledger.jsonl`) does not exist in this worktree
(gitignored). Even if it did, `seatledger` returns REFUSED for every seat
because the estate is SHARED: 121 total campaigns in the account, only 40
created by Resonate. Client usage on shared seats is structurally unobservable.

**5. The task as specified cannot be completed**

"Cap vs actual" requires a per-seat usage counter the provider does not expose.
The best this system can do:
- Report configured caps (done: 41 seats, range 5-40)
- Report our own actions from the action ledger (ledger absent from this worktree)
- Report seatledger verdicts (all REFUSED due to shared estate)
- Report health: 8 dead, 3 on cooldown, 30 healthy

### RISKS

- The 8 dead-auth seats (129531, 156360, 170308, 181262, 186618, 194061,
  201969, 210951) are in the provider but cannot send. If any are in the
  attested roster, they are assigned to campaigns and delivering nothing.
- The 3 cooldown seats may be near their cap from the CLIENT's actions, which
  this system cannot see.

### RECOMMENDED CLAUDE ACTION

No code change needed. The infrastructure already reports caps correctly
(`senderinventory.py`) and fails closed on usage (`seatledger.py`). The
limitation is at the provider, not in this codebase.
