PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-418 — Offer Config Consistency Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `offer-config-consistency-check`.

Read `config/clients/productive-offers.yaml` end to end and check for
internal contradictions the way TASK-382's GLM review found one (a "THE
ONLY allowed link" comment coexisting with a different link elsewhere in
the same file). Report every such contradiction found, file:line, quoting
both sides. Acceptance: a clean pass reports "none found" honestly; any
contradiction found is quoted exactly, both sides.
