PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-413 — Heyreach Seat Cap Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `heyreach-seat-cap-check`.

Is any HeyReach seat over its own daily/weekly connection cap? Read every
attested seat's configured cap against actual sends this period via a REAL
read-only provider read. Report any seat at or over 90% as a finding.
READ-ONLY. No campaign, seat or cap modification. Acceptance: a real
per-seat table (cap, actual, %); anything over 90% named explicitly.

---

## RESULT

**STATUS:** DONE
**COMMIT SHA:** (see git log)
**TESTS:** N/A — read-only provider audit, no code change to src/
**FILES CHANGED:**
  - `scripts/task413_seat_cap_check.py` — the probe that reads the provider
  - `scripts/task413_seat_cap_probe.py` — initial API surface probe
  - `docs/state/TASK-413-SEAT-CAP-CHECK.json` — per-seat JSON output
  - `docs/state/SENDER-CAPACITY.json` — refreshed by `scripts/sender_capacity.py`

**ARTIFACT KIND:** finding + code (the script is reusable)

### Method

Two read-only HeyReach routes, both on the existing allowlist:

1. `POST /li_account/GetAll` — 41 seats, `totalCount` 41. Returns
   `accountLimits` per seat: `connectioRequestMax`, `messageLimitMax`, etc.
   These are the configured daily caps.
2. `POST /stats/GetOverallStats` with `accountIds: [<seat_id>]` — one call
   per seat. Returns `byDayStats` keyed by date, carrying `connectionsSent`,
   `messagesSent`, `profileViews`. This is actual usage.

The stats route AGGREGATES across multiple accountIds, so one call per seat
is required to get per-seat granularity. 41 seats = 41 + 1 = 42 API calls,
all free reads.

### Per-seat table (2026-09-27, Sunday)

| seat_id | state | campaigns | conn cap | conn actual | conn % | msg cap | msg actual | msg % |
|---|---|---|---|---|---|---|---|---|
| 116968 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 8 | 20% |
| 116973 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 3 | 7% |
| 116988 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 3 | 7% |
| 116989 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 4 | 10% |
| 119588 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 3 | 7% |
| 125748 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 9 | 22% |
| 125775 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 4 | 10% |
| 129082 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 0 | 0% |
| 129531 | AUTH_INVALID | 1 | 40 | - | n/a | 40 | - | n/a |
| 139699 | HEALTHY | 9 | 40 | 6 | 15% | 40 | 0 | 0% |
| 143105 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 1 | 2% |
| 156360 | INACTIVE | 0 | 40 | - | n/a | 40 | - | n/a |
| 159259 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 0 | 0% |
| 169600 | HEALTHY | 9 | 40 | 8 | 20% | 40 | 2 | 5% |
| 170308 | INACTIVE | 0 | 40 | - | n/a | 40 | - | n/a |
| 174332 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 6 | 15% |
| 174742 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 8 | 20% |
| 174748 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 3 | 7% |
| 174797 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 4 | 10% |
| 174803 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 8 | 20% |
| 174810 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 3 | 7% |
| 174822 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 8 | 20% |
| 174845 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 4 | 10% |
| 174892 | HEALTHY | 14 | 40 | 0 | 0% | 40 | 5 | 12% |
| 175455 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 3 | 7% |
| 175552 | HEALTHY | 9 | 40 | 3 | 7% | 40 | 5 | 12% |
| 177751 | HEALTHY | 9 | 40 | 1 | 2% | 40 | 2 | 5% |
| 179527 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 0 | 0% |
| 181262 | INACTIVE | 0 | 40 | - | n/a | 40 | - | n/a |
| 181653 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 1 | 2% |
| 181658 | HEALTHY | 9 | 40 | 4 | 10% | 40 | 1 | 2% |
| 186618 | INACTIVE | 0 | 40 | - | n/a | 40 | - | n/a |
| 191848 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 2 | 5% |
| 194061 | INACTIVE | 0 | 40 | - | n/a | 40 | - | n/a |
| 201959 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 0 | 0% |
| 201969 | INACTIVE | 0 | 40 | - | n/a | 40 | - | n/a |
| 201978 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 1 | 2% |
| 208242 | HEALTHY | 13 | 40 | 0 | 0% | 40 | 6 | 15% |
| 208253 | HEALTHY | 9 | 40 | 0 | 0% | 40 | 3 | 7% |
| 210951 | INACTIVE | 0 | 40 | - | n/a | 40 | - | n/a |
| 212356 | HEALTHY | 9 | 40 | 11 | 27% | 40 | 3 | 7% |

### Findings

**NO SEAT IS AT OR OVER 90% OF ANY CAP.**

- Connection requests: highest is seat 212356 at 27% (11/40).
- Messages: highest is seat 125748 at 22% (9/40).
- 33 healthy seats, 1 auth_invalid (129531), 7 inactive.
- 8 non-functional seats excluded from usage check (no stats queried).

### Context

Today is Sunday 2026-09-27. Most seats show 0 connection requests sent today,
which is consistent with reduced weekend activity. The message counts (0-9 per
seat) suggest some campaigns are still running follow-up messages. The data
is a point-in-time read at 11:54 UTC; weekday figures will be higher.

### Estate summary

- 41 seats total, 33 healthy, 1 auth_invalid, 7 inactive
- All healthy seats have `connectioRequestMax: 40` and `messageLimitMax: 40`
- Estate-wide daily ceiling: 1,320 connection requests, 1,320 messages (33 × 40)
- No cooldown flags were observed on any seat at read time

### FINDINGS

- No seat is at or over 90% of its daily connection-request cap.
- No seat is at or over 90% of its daily message cap.
- The HeyReach API exposes per-seat daily usage via `/stats/GetOverallStats`
  with a single `accountId`, and configured caps via `/li_account/GetAll`.
- The existing `accountLimits.connectioRequestLimit` field is a CONFIGURED
  SETTING, not a remaining-today counter. The actual usage counter is
  `byDayStats[today].connectionsSent` from the stats route.

### RISKS

- This is a Sunday read. Weekday usage will be higher. A weekday re-check
  is warranted before any capacity decision.
- The 8 non-functional seats (7 inactive + 1 auth_invalid) reduce the
  effective estate. Seat 129531 is `isActive: true` but `authIsValid: false`
  and is still attached to 1 campaign — it will accept assignments and
  deliver nothing.

### RECOMMENDED CLAUDE ACTION

Accept. No seat is over 90%. The script `scripts/task413_seat_cap_check.py`
is reusable for future checks. A weekday re-run is recommended.
