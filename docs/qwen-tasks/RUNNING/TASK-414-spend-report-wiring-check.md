PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-414 — Spend Report Wiring Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `spend-report-wiring-check`.

Does the spend report read what the ledger's client-attribution work now
writes? Trace every consumer of spendledger that reports a number to a
human; confirm each groups by the now-real client ids correctly, not still
folding everything into "unattributed". Acceptance: run the report against
a fixture with mixed client-attributed and unattributed rows; confirm the
client total is correct, not folded in.
