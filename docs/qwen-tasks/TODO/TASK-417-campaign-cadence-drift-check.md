PRIORITY: P2
SIZE: M
DEPENDS:

# TASK-417 — Campaign Cadence Drift Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `campaign-cadence-drift-check`.

For every ACTIVE campaign per the latest `docs/state/PROVIDER-CAMPAIGNS.json`,
confirm its actual send cadence (real provider timestamps between sends)
matches the canonical cadence library's declared days, not an assumption.
READ-ONLY. Acceptance: real per-campaign timing measured against the
canonical cadence, named drift if any.
