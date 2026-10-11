# TASK-997 — the reply ingestion path is inert, and the store persists no verdict

STAGE: AWAITING_REVIEW
BRANCH: task-reply-ingestion-2026-10-12
PRIORITY: P0

## The two defects, measured 2026-10-12

**1. Ingestion reports healthy and ingests zero.** `work/replywatch.json` showed
`healthy: true`, `checkpoint: 2026-10-11T00:33:16Z`, `new_replies_ingested: 0`.
Against that, the provider feed carried 559 inbound replies and **94 were absent
from the local store**, 14 of them since 4 October. The store's newest
`received_at` was 2026-09-22 and its mtime 23 September.

**2. The store persists no verdict.** Row schema was exactly
`{automated, campaign_id, domain, interested, lead_id, received_at, reply_id}` —
no classification, no confidence, no `RULE_HASH`. So classification could not be
measured over time at all, and `replyverdict.is_confirmed` was False for every
stored row by construction.

## What the branch claims, for the reviewer to attack

Root cause claimed: **the consumer was never called.** Specifically
`src/inbound.py:429` (`if applied["status"] != "applied": return outcome`)
returns BEFORE `replies.apply`, so a reply that cannot be attributed to a record
is never classified; and `new_replies_ingested` is `poller.run`'s `applied`
count, which counts attributions only. Evidence offered: 44
`unmatched_reply_needs_review` rows in `work/notifications.jsonl` stamped
2026-10-11T22:23:34, every one `{"why":"no record for this event","held":0}`.

Second root cause claimed: nothing in `src/` wrote the reply store at all. Its
only writer was `scripts/learning_walk_replies.py`, a DESCENDING cursor walk
whose state reads `created_at 2026-02-25, complete: false` — walking backwards
through February and never returning to the head.

Claimed ruled out, with evidence: checkpoint ahead of unread data (the mark is
only ever the newest `created_at` actually read, and `seen_through` is returned
unchanged when the page budget runs out); dedupe rejecting everything
(`duplicates_ignored: 0`); a swallowed exception (`last_error: null`,
`consecutive_failures: 0`).

## Acceptance

- A positive control proving ingestion can **fail loudly** rather than silently
  returning zero: make the store write fail and require the watcher to surface
  unhealthy, NOT `new_replies_ingested: 0` beside `healthy: true`.
- A test proving a real reply IS ingested and counted. A zero never shown able
  to be non-zero is not a result.
- An **unattributed** reply must be stored and counted, not dropped. That is the
  whole defect.
- Our own outgoing mail must never enter the reply store.
- The same reply read twice is stored once.
- Backward compatibility: legacy rows carry no verdict and must not crash a
  reader, and must NOT read as classified. Absent verdict is UNKNOWN, never a
  pass. `src/replyverdict.py` already compares `RULE_HASH`; match what it
  expects rather than inventing a field.
- No reply body, name or address persisted beyond what the schema states.

## Notes for the reviewer

Two claims to attack hardest.

First, **"the consumer was never called"**. It is a claim about control flow and
it is checkable: confirm `inbound.py` really returns before the classify step on
the unattributed path, and that the new call site runs for EVERY inbound reply
rather than only the attributable ones. A fix that stores attributed replies and
still drops unattributed ones would look green and leave the defect.

Second, **the store now has two writers** — the watcher and the historical walk —
against one file. Check the locking actually holds across processes, not just
within one, and that the historical walk and live ingestion agree on the verdict
they store for the same reply. Two writers and one key is how a store comes to
disagree with itself.
