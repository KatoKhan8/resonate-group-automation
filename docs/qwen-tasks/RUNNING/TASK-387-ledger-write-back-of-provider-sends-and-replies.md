PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-387 — does a provider-confirmed send or reply ever reach the queue's own record?

**Operator instruction, 2026-09-26/27 overnight standing order.** Trace
whether a real EmailBison/HeyReach send or reply event is written back to
the record it belongs to (`work/queue.jsonl`, through `src/store.py`), or
whether the queue only ever knows what WE intended to send, never what the
provider confirms happened.

## Trace first — name the current state with file:line, do not assume it

1. `scripts/bison_watch_loop.py`'s `snapshot()` already reads
   `emails_sent`, `replied`, `bounced` per campaign — where does that go
   after it is read? Grep for `store.patch`/`store.log`/`store.save` calls
   near it. Is it written to any per-lead record, or only to a heartbeat
   file (`work/heartbeat/bison-*.json`) that nothing else consumes?
2. `src/replyverdict.py` exists and classifies replies — trace its callers.
   Does a classified reply get written to the record that sent the message
   it replied to (`rec["events"]` or similar), or does it only feed a
   Slack notification?
3. Name every place a provider-confirmed event (send, reply, bounce) is
   currently DISCARDED after being read — the read happened, the write
   never did.

## Build only what the trace shows is missing

If sends/replies are read but never written to the record, add the
write-back through `src/store.py`'s existing `log()`/`patch()` — one
canonical event log per record, matching the pattern `campaigns.log()`
already uses for campaign-level events. Do not invent a second event store.

## Why this matters, stated plainly

Without this, nothing in the queue can answer "has this contact been sent
to" or "did they reply" from OUR OWN state — every question has to re-ask
the provider live, which is exactly the class of problem `docs/state/
PROVIDER-CAMPAIGNS.json` exists to prevent at the campaign level. This is
the same problem one level down, at the per-contact level.

## Acceptance

1. Name, with file:line, every current read of a provider send/reply/bounce
   event and whether it is written back to the record. Report the honest
   count: how many are, how many are read-and-discarded.
2. For whatever you wire: show one record's event log gaining a real entry
   after a provider-confirmed send or reply, sourced from an actual
   provider read (a fixture standing in for the API response is fine — no
   live provider call required for this task).
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- No provider write, no live API call required or permitted for this task.
- Do not invent a send/reply event that did not come from a real provider
  read or an explicit test fixture standing in for one.
- Nothing sent, nothing activated.
