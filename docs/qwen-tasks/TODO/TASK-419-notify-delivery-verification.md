PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-419 — Notify Delivery Verification (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `notify-delivery-verification`.

Trace whether a `src/notify.py` GLOBAL-destination notification (e.g.
`failed_job_needs_attention`, the kind `pool.sh`'s CRITICAL alert now
writes) is ever actually delivered to Slack by a live consumer, or whether
it only ever reaches the stored notification queue. Name the consumer if
one exists, with file:line, or report plainly that none was found running.
Acceptance: either a real delivered test notification traced end to end to
Slack, or an honest "no consumer found" with the queue location named.
