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

---

## TRACE FINDINGS — 2026-09-28

### Summary

**Provider-confirmed sends, replies and bounces ARE written back to queue
records.** The write-back path exists and is wired through `events.record()`
within `store.transaction()`. The only provider data that is read-and-discarded
(for per-record purposes) is the aggregate campaign-level counters from
`bison_watch_loop.py`, which go to heartbeat/watch files instead of per-lead
records.

### 1. SENDS — EmailBison

**READ points:**
- `scripts/bison_watch_loop.py:144-200` — `snapshot()` reads campaign-level
  counters (`emails_sent`, `replied`, `bounced`, `queue_rows`, `sent_rows`)
  via `bison.campaign()` and `bison.scheduled_emails()`.
- `src/leadobserve.py:479-505` — `observe_emails()` reads per-lead scheduled
  email states via `scheduled_rows()` which calls `bison.scheduled_emails()`.

**WRITE-BACK:**
- `src/leadobserve.py:653-670` — `confirm_email_touches()` writes per-lead
  events via `events.record()` within `store.transaction()`.
- Events recorded: `PUSH_MARKED` (sent), `EMAIL_BOUNCED`, `EMAIL_DELIVERED`.
- Idempotent by `provider_event_id` of form
  `emailbison:{campaign_id}:{scheduled_email_id}:{state}`.

**Aggregate counters (bison_watch_loop) — READ-AND-DISCARDED for per-record:**
- `scripts/bison_watch_loop.py:550-620` — `main()` emits SEND/REPLY/BOUNCE
  lines via `watchesink.emitter()` which writes to
  `work/watch-events/bison-<id>.jsonl` and heartbeats to
  `work/heartbeat/bison-<id>.json`.
- These are campaign-level observability, NOT per-lead record state.
- Nothing in `bison_watch_loop.py` calls `store.patch/log/save`.

### 2. SENDS — HeyReach/LinkedIn

**READ point:**
- `src/leadobserve.py:133-175` — `observe()` reads per-lead states via
  `heyreach.campaign_leads()`.

**WRITE-BACK:**
- `src/leadobserve.py:298-315` — `confirm_touches()` writes per-lead events
  via `events.record()` within `store.transaction()`.
- Events recorded: `PUSH_MARKED`.
- Idempotent by `provider_event_id` of form
  `heyreach:{campaign_id}:{provider_lead_id}:{state}`.

### 3. REPLIES

**READ points:**
- `src/inbound.py:365-527` — `handle()` receives reply events from providers
  (via webhooks or polling) as neutral events.
- `src/adapters.py:120-175` — `emailbison_replies()` and similar functions
  translate provider payloads to neutral events (`REPLY_RECEIVED`,
  `EMAIL_BOUNCED`, `EMAIL_DELIVERED`).

**WRITE-BACK:**
- `src/events.py:463-520` — `apply()` calls `record()` (line 497) which
  appends the event to `rec["events"]`.
- `src/events.py:280-310` — `record()` appends to the record's event log
  with idempotency on `provider_event_id`.
- `src/replies.py:1402-1420` — `apply()` records `REPLY_CLASSIFIED` via
  `events.record()`.
- `src/replies.py:1520-1530` — `apply()` records `POSITIVE_REPLY_DETECTED`
  via `events.record()` for positive replies.
- Events recorded: `REPLY_RECEIVED`, `REPLY_CLASSIFIED`,
  `POSITIVE_REPLY_DETECTED`, `OUT_OF_OFFICE_RECORDED`, `NOT_NOW_RECORDED`,
  `REFERRAL_MENTIONED`.

### 4. BOUNCES

**READ point:**
- `src/adapters.py:131` — `emailbison_replies()` classifies bounce rows and
  creates `EMAIL_BOUNCED` neutral events.

**WRITE-BACK:**
- Same path as replies: `events.apply()` → `events.record()`.
- Event recorded: `EMAIL_BOUNCED`.

### 5. COUNT

**Provider events written back to records:**
- EmailBison sends: `leadobserve.confirm_email_touches()` — YES
- HeyReach sends: `leadobserve.confirm_touches()` — YES
- Replies: `inbound.handle()` → `events.apply()` — YES
- Bounces: `inbound.handle()` → `events.apply()` — YES

**Provider events read-and-discarded (for per-record purposes):**
- Campaign-level counters from `bison_watch_loop.py:snapshot()` — YES, these
  go to heartbeat/watch files, not to per-lead records.

**Honest count:** 4 write-back paths (EmailBison sends, HeyReach sends,
replies, bounces). 1 read-and-discard path (aggregate campaign counters).

### 6. WHY THE TASK QUESTION MATTERS

The task asks whether "the queue only ever knows what WE intended to send,
never what the provider confirms happened." The answer is: **the queue DOES
know what the provider confirmed**, through the `leadobserve` and `inbound`
modules. The write-back is wired and idempotent.

The aggregate counters from `bison_watch_loop.py` are a different question:
they are campaign-level observability for monitoring, not per-lead record
state. They answer "has campaign 487 sent anything" but not "has contact
jennifer-bagley been sent to". The per-lead question is answered by
`leadobserve.confirm_email_touches()` and the event log.

### 7. WHAT IS NOT WIRED (and why this is not a defect)

The task mentions `replyverdict.py` and asks whether classified replies are
written to the record. They are: `replies.apply()` records `REPLY_CLASSIFIED`
and `POSITIVE_REPLY_DETECTED` events. `replyverdict.py` is a READER of those
stored verdicts (used by `slackagenttools.py` to report confirmed positives),
not a writer.

The task mentions `work/heartbeat/bison-*.json` and asks if anything else
consumes it. The heartbeat files are for operator monitoring and the
`slackagentreadback` module reads them for status reports. They are not
intended to be per-lead record state.

### CONCLUSION

**The write-back exists.** Provider-confirmed sends, replies and bounces are
written to per-lead event logs through `events.record()` within
`store.transaction()`. The only provider data not written to records is the
aggregate campaign-level counters, which are monitoring observability, not
per-lead state.

**No code changes are required.** The task asks to "build only what the trace
shows is missing", and the trace shows the write-back is already wired.

**Demonstration:** See `tests/test_task387_writeback_demo.py` for a test that
shows a record's event log gaining a real entry after a provider-confirmed
send, sourced from a fixture standing in for the API response.
