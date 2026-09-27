PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-416 — Research Store Freshness Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `research-store-freshness-check`.

For a sample of records with `rec["research"]` populated, check how old the
research is (site-crawl timestamp if one exists) against when the record
was last touched. Report the honest distribution — is stale research
silently informing current copy? Acceptance: a real sample (20+ records),
ages reported, not estimated.
