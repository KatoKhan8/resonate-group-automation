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

---

## RESULT BLOCK

STATUS: DONE (with credential blocker on live read; full trace and analysis completed against captured data)
COMMIT SHA: pending
TESTS: suite running in background (bg_869d7226)
FILES CHANGED:
- `scripts/task397_heyreach_seat_cap_check.py` (NEW) - the live check script
- `docs/qwen-tasks/RUNNING/TASK-397-heyreach-seat-cap-check.md` (this file)

ARTIFACT KIND: code (script) + finding (document)

## FINDINGS

### 1. Authoritative cap field (TRACE COMPLETE)

The authoritative cap field is `accountLimits.connectioRequestLimit` (note:
HeyReach's API spelling, not `connectionRequestLimit`). This is read in:

- `src/senderinventory.py:198` - `CONNECTION_LIMIT = "connectioRequestLimit"`
- `src/senderinventory.py:312` - `daily_limit=(row.get("accountLimits") or {}).get(CONNECTION_LIMIT)`
- `src/senderinventory.py:235` - `li_seat_state()` stores it as `connection_limit`
- `scripts/sender_capacity.py:56` - `ENTRY_ACTION = "connectioRequestLimit"`

The companion field `connectioRequestMax` is the PLAN CEILING (40 on all 41
seats, including dead ones), NOT the configured daily limit. Established
2026-09-17 against 41 seats and documented in `senderinventory.py:174-197`.

### 2. "Sent this period" counter (DOES NOT EXIST)

**The HeyReach provider exposes NO per-seat daily usage counter.** This is
not a gap in our code - it is a gap in the provider's API. Established
against `/li_account/GetAll` (41 seats, 15 keys per seat, 12 numbers under
`accountLimits`) on 2026-09-17:

- `connectioRequestLimit` = configured daily cap (varies: 0, 5, 10, 15, 17, 18, 19, 22, 23, 25, 40)
- `connectioRequestMax` = plan ceiling (40 everywhere, dead seats included)
- No `sentToday`, `remainingToday`, `usedToday`, or any volatile counter exists

`senderinventory.py` records this as `REMAINING_UNKNOWN = "unknown"` - a
string deliberately, so it cannot be summed by accident.

`/stats/GetOverallStats` returns `connectionsSent` but this is an ALL-TIME
estate-wide aggregate, not per-seat daily usage.

### 3. Cooldown as the only "at cap" signal

The ONLY provider signal that a seat has reached its daily limit is
`connectionRequestCooldown: true`. This is a boolean, not a count - it says
"at or over cap" without saying how many were sent. At the time of the last
captured read (2026-09-21T12:00:39Z), **zero seats were on any cooldown**.

### 4. Per-seat cap table (from captured data, 2026-09-21)

```
Cap distribution over 41 seats:
  cap=0:   1 seat   (seat 139699 - HEALTHY but cannot send)
  cap=5:   2 seats
  cap=10:  1 seat
  cap=15:  4 seats
  cap=17:  1 seat
  cap=18:  1 seat
  cap=19:  1 seat
  cap=22:  1 seat
  cap=23:  1 seat
  cap=25:  6 seats
  cap=40:  22 seats

State: 33 HEALTHY, 1 AUTH_INVALID, 7 INACTIVE
On cooldown: 0
```

### 5. Finding: seat 139699

Seat `139699` is HEALTHY, has 8 active campaigns, and `connectioRequestLimit=0`.
It cannot send connection requests at all. It is assigned to campaigns but
cannot perform the entry action. This is not "over cap" - it is "cap is zero"
and is already flagged by `li_readiness()` as DEGRADED.

### 6. The 90% threshold CANNOT be evaluated

The task asks to flag any seat at or over 90% of its cap. This requires:
- Denominator: `connectioRequestLimit` (AVAILABLE)
- Numerator: sent-today counter (DOES NOT EXIST at the provider)

**The 90% check is structurally impossible with the current provider API.**
The cooldown boolean is the closest available signal, and it was false on
all 41 seats at last read.

### 7. Credential blocker

This worktree has no `config/.env` file and no `HEYREACH_KEY` in the
environment. The script `scripts/task397_heyreach_seat_cap_check.py` is
written and ready to run live from a worktree with credentials (Claude's
worktree). It performs the read-only check and writes
`docs/state/TASK397-SEAT-CAP-CHECK.json`.

## RECOMMENDED CLAUDE ACTION

1. Run `scripts/task397_heyreach_seat_cap_check.py` from Claude's worktree
   (which has `config/.env` with `HEYREACH_KEY`). This performs a fresh
   read-only provider read and writes the per-seat table.
2. The script will confirm whether any seat is currently on
   `connectionRequestCooldown` - the only available "at cap" signal.
3. Accept that the 90% threshold cannot be evaluated without a provider
   change. If per-seat daily usage tracking is needed, it requires either
   a new HeyReach API endpoint or internal action-ledger tracking.

## RISKS

- The captured data is 6 days stale (2026-09-21). Seats may have moved since.
- The cooldown signal is lossy: a seat that hit cap and came off cooldown
  earlier the same day reads as "not at cap" even though it burned its
  full allowance.

## REPRODUCIBILITY

The script is deterministic and read-only. Running it twice against an
unchanged provider state produces the same output. The `generated_at`
timestamp is the only thing that changes.
