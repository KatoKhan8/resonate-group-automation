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

## FINDINGS

### BLOCKED — no provider credentials in this worktree

The task requires a **real read-only provider read** against both EmailBison
(`bison.sender_emails()`) and HeyReach (`heyreach.all_li_accounts()`). Both
calls require API keys loaded from `config/.env`:

- `BISON_KEY` — for EmailBison `/sender-emails`
- `HEYREACH_KEY` — for HeyReach `/li_account/GetAll`

**Neither key is present:**

    config/.env            NOT FOUND in this worktree (qwen-worker-12-r9)
    BISON_KEY env var      NOT SET
    HEYREACH_KEY env var   NOT SET

`config/.env` exists in Claude's worktree (`C:\Users\Zvonimir\Desktop\
resonate-group-automation\config\.env`) but QWEN.md forbids touching Claude's
directory. The file is gitignored and cannot be pulled from git.

### What the internal record looks like (without live provider read)

- **HeyReach:** `docs/state/SENDER-CAPACITY.json` (generated 2026-09-21)
  records 41 seats: 33 HEALTHY, 1 AUTH_INVALID, 7 INACTIVE. Sender IDs:
  116968, 116973, 116988, 116989, 119588, 125748, 125775, 129082, 129531,
  139699, 143105, 156360, 159259, 169600, 170308, 174332, 174742, 174748,
  174797, 174803, 174810, 174822, 174845, 174892, 175455, 175552, 177751,
  179527, 181262, 181653, 181658, 186618, 191848, 194061, 201959, 201969,
  201978, 208242, 208253, 210951, 212356.
  This snapshot is 6 days old and NOT a substitute for a live read.

- **EmailBison:** No internal state file exists. `PRODUCTION-DASHBOARD.md`
  confirms: "no EmailBison state file to read." The only path to an
  EmailBison sender diff is a live `bison.sender_emails()` call.

- **`work/senders.jsonl`** (the canonical sender identity store) does not
  exist in this worktree's `work/` directory.

### What is needed to unblock

Claude (or a worker with `config/.env` populated) must run the drift check
from a worktree that has provider credentials. The code is fully wired:
`src/senderinventory.py:reconcile_linkedin()` already computes both
directions of the diff (`missing_at_provider` and `unrostered_seats`), and
`bison.sender_emails()` returns the full EmailBison inbox list. A script
that calls both and formats the diff would satisfy the acceptance criteria.

## RESULT BLOCK

- **STATUS:** BLOCKED (external — no provider credentials)
- **COMMIT SHA:** (none — no code changes)
- **TESTS:** (none run)
- **FILES CHANGED:** task file only (moved to BLOCKED)
- **FINDINGS:** `config/.env` absent from qwen-worker-12-r9; neither
  BISON_KEY nor HEYREACH_KEY available; live provider read impossible.
  HeyReach internal snapshot exists (41 seats, 2026-09-21) but is stale.
  EmailBison has no internal state file at all.
- **RISKS:** The 6-day-old HeyReach snapshot may already be wrong — seats
  can go AUTH_INVALID or be removed between reads. The drift this task was
  designed to catch may already be happening unseen.
- **RECOMMENDED CLAUDE ACTION:** Run the drift check from Claude's worktree
  where `config/.env` is present, or copy `config/.env` into this worktree
  (the file is gitignored and safe to duplicate for read-only workers).
- **ARTIFACT KIND:** finding (no code or test artifact; the blocker is
  environmental)
