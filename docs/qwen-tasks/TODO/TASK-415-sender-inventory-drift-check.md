PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-415 — Sender Inventory Drift Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `sender-inventory-drift-check`.

Compare the attested sender/mailbox inventory (EmailBison sender_emails,
HeyReach seat roster) against whatever this repo's own internal record of
"our senders" claims, via a real read-only provider read. Report any
mailbox/seat present at the provider but not in our internal record, and
vice versa. READ-ONLY. Acceptance: a real diff, both directions, named by
id, not a count.
