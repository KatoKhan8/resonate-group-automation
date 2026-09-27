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
