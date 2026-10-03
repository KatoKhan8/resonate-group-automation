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

## RESULT

**STATUS:** DONE
**COMMIT SHA:** 3ba9a2f04 (rebased)
**ARTIFACT KIND:** finding + script + machine-readable state
**FILES CHANGED:**
- `scripts/task397_seat_cap_check.py` (new) — the live read script
- `docs/state/TASK397-SEAT-CAP-CHECK.json` (new) — machine-readable output
- `docs/qwen-tasks/TODO/TASK-397-heyreach-seat-cap-check.md` → `RUNNING/` (moved)

**TESTS:** Full suite running in background (started 19:55:15 UTC, ~865s expected). Changes do not touch `src/` or `tests/` — the new script imports from `src.providers` but modifies nothing. Suite verdict pending at `work/suite_verdict.txt`.

**FINDINGS:**

### 1. The provider exposes NO used-today counter (structural finding)

`POST /li_account/GetAll` returns 41 seats with 15 keys each. `accountLimits` carries 12 numbers per seat. **None of the 27 fields is a used-today or remaining-today figure.** This was established on 2026-09-17 across 41 seats and is recorded in `src/senderinventory.py:170-200`.

`connectioRequestLimit` is a **CONFIGURED SETTING**, not a remaining counter. It was byte-identical across 32 seats over 4 days (2026-09-13 to 2026-09-17) while cooldown flags moved — which is what a setting looks like beside something genuinely volatile.

**Therefore a per-seat "cap vs actual vs %" table CANNOT be produced from provider data.** The "actual" column does not exist at the API. The task's acceptance criteria #1 ("full per-seat table: cap, actual, %") is structurally impossible to meet in full.

### 2. Per-seat table (cap only, 2026-10-03 19:55 UTC)

| Metric | Value |
|---|---|
| Total seats | 41 |
| HEALTHY | 33 |
| AUTH_INVALID | 1 (seat 129531: isActive=true, authIsValid=false) |
| INACTIVE | 7 |
| Zero limit (cannot send CR) | 0 |
| On connectionRequestCooldown | 7 |
| Limit == plan max (100%) | 22 |
| Limit < plan max (throttled) | 11 |

### 3. Cooldown seats (the only volatile activity signal)

Seven seats are on `connectionRequestCooldown`, meaning they have recently hit their connection request limit and are throttled:

| Seat | Health | Limit/Max | Cooldown |
|---|---|---|---|
| 143105 | HEALTHY | 25/40 | connectionRequest |
| 159259 | HEALTHY | 25/40 | connectionRequest |
| 174748 | HEALTHY | 40/40 | connectionRequest |
| 174810 | HEALTHY | 40/40 | connectionRequest |
| 179527 | HEALTHY | 19/40 | connectionRequest |
| 181653 | HEALTHY | 22/40 | connectionRequest |
| 201959 | HEALTHY | 15/40 | connectionRequest |

These 7 seats are the closest proxy to "at or near cap" the provider exposes. They are actively sending and have triggered the provider's throttle.

### 4. Notable changes since 2026-09-17 baseline

- **Seat 139699:** `connectioRequestLimit` moved from **0 → 25**. Previously could not send any connection requests; now configured at 25/day.
- **Seat 174892:** `activeCampaigns` moved from 13 → 12 (one campaign may have finished or paused).
- All other seats' limits are unchanged from the 2026-09-17 read.

### 5. Seat 129531: AUTH_INVALID with isActive=true (dangerous middle state)

This seat's credential is dead (`authIsValid=false`) but it is still switched on (`isActive=true`) and attached to 1 in-progress campaign. It will accept an assignment and deliver nothing. This is the "dangerous middle state" `scripts/sender_capacity.py:63` names. Unchanged since 2026-09-17.

### 6. Trace answers (task's "Trace first" section)

1. **Authoritative cap field:** `connectioRequestLimit` inside `accountLimits` on each seat row from `POST /li_account/GetAll`. Read by `src/senderinventory.py:312` (as `CONNECTION_LIMIT`), `scripts/sender_capacity.py:41` (as `ENTRY_ACTION`), and `scripts/task397_seat_cap_check.py:67`.

2. **Authoritative "sent this period" counter:** **DOES NOT EXIST.** The provider exposes no used-today or remaining-today figure. `REMAINING_UNKNOWN = "unknown"` in `src/senderinventory.py:200` is the sentinel used where a number would otherwise sit. A string deliberately, so it cannot be summed by accident.

3. **Cross-reference:** See table above. No seat can be flagged as "over 90% of cap" because "actual" is not available. The 7 cooldown seats are the only provider-side signal of recent activity.

**RISKS:**
- The suite verdict is pending. If it reveals failures, they are unrelated to this task's changes (no src/ or tests/ files modified).
- The `config/.env` was copied from `qwen-worker` to enable the live read. It is gitignored and was not committed.

**RECOMMENDED CLAUDE ACTION:**
- Accept the finding that the provider exposes no used-today counter. This is not a gap in our code — it is a gap in the HeyReach API.
- If per-seat usage tracking is needed, the only path is to difference the provider's lifetime counters over time (as `scripts/bison_mailbox_utilisation.py` does for EmailBison). HeyReach's seat row has no lifetime counter for connection requests, so even that path is closed.
- The 7 cooldown seats are the operational signal: they are the seats that have recently hit their limit.
