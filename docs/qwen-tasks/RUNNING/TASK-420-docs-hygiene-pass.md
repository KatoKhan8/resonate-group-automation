PRIORITY: P3
SIZE: S
DEPENDS:

# TASK-420 — Docs Hygiene Pass (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `docs-hygiene-pass`.

Docs hygiene: find what's now false in the standing docs (CLAUDE.md,
OPERATING-MODE.md, the most recent PRODUCTION-HANDOFF). For each specific,
checkable claim (a count, a SHA, a "the only X is Y" statement, a task's
stated status), verify against current master or a read-only provider
check. Report every claim found FALSE with the correction and its evidence.
Report only — Claude applies corrections, this task does not edit the
scoped files. Acceptance: a list of every checked claim, PASS or FALSE,
with evidence; do not touch the files yourself.
