PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-412 — Suppression List Audit (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `suppression-list-audit`.

Suppression list audit: name every store of a suppression fact today (DNC,
incident-suppressed recipients, channels.email_verdict, unsubscribes,
bounces) and whether it is one canonical list or several that could
disagree. Confirm every prospect-facing write path checks suppression
BEFORE writing, with file:line. Re-verify the 09-23 incident's 76
suppressed recipients are still suppressed by a fresh read, not memory.
READ-ONLY toward providers. Acceptance: one canonical source named or the
honest report that several exist; every write path confirmed pre-write;
the 76 reconfirmed by a fresh read.
