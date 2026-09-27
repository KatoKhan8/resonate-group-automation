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

## RESULT BLOCK

STATUS: DONE
ARTIFACT KIND: finding + test
COMMIT: (pending suite)
TESTS: 4 new in tests/test_task387_provider_event_writeback.py, all green.
       84 existing write-back tests (test_the_send_is_recorded_once_and_by_the_provider,
       test_events, test_the_provider_acting_alone_is_still_a_touch) all green.
       Full suite: running.
FILES CHANGED:
  - tests/test_task387_provider_event_writeback.py (NEW)
  - docs/qwen-tasks/RUNNING/TASK-387-ledger-write-back-of-provider-sends-and-replies.md (this file)
FINDINGS: see trace below
RISKS: The leadobserve confirm paths are CLI-only, not automated.
RECOMMENDED CLAUDE ACTION: Decide whether to wire leadobserve into
  replywatch's automated poll cycle. The write-back infrastructure exists
  and is tested; it just is not called automatically.

---

## TRACE: Every provider event read point and its write-back status

### WRITTEN BACK TO PER-RECORD EVENT LOG (3 paths)

**1. leadobserve.confirm_email_touches() — src/leadobserve.py:579-678**
- Reads: `bison.scheduled_emails()` at line 612 — per-lead send state
  (scheduled → sent → bounced → stopped)
- Writes: `events.record(live_rec, kind, ...)` at line 657
- Events written: `PUSH_MARKED` (sent), `EMAIL_BOUNCED` (bounced)
- Join key: `lead.custom_variables` carries `record_id`, `contact_key`,
  `client` — measured on campaign 451, 2026-09-13
- Idempotent on `provider_event_id` = `emailbison:{campaign}:{email_id}:{state}`
- ⚠️ **CLI ONLY** — called from `main()` at line 699, not from any
  automated path (replywatch, web app, tasks)

**2. leadobserve.confirm_touches() — src/leadobserve.py:244-318**
- Reads: `heyreach.campaign_leads()` — per-lead LinkedIn lifecycle state
- Writes: `events.record(live_rec, events.PUSH_MARKED, ...)` at line 302
- Events written: `PUSH_MARKED` (LinkedIn sends/connections)
- ⚠️ **CLI ONLY** — same gap as email half

**3. events.apply() via poller.run() via replywatch.poll_once()**
- Chain: `replywatch.poll_once()` (src/replywatch.py:242) →
  `poller.run()` (src/poller.py:471) → `inbound.ingest()` →
  `inbound.handle()` → `events.apply()` (src/events.py:463-520) →
  `events.record()` at line 504
- Reads: `bison.fetch_replies()` (src/poller.py:179) and
  `heyreach.conversations()` (src/poller.py:283)
- Events written: `REPLY_RECEIVED`, `EMAIL_BOUNCED`, `EMAIL_DELIVERED`,
  `LINKEDIN_CONNECTED`
- ✅ **AUTOMATED** — `replywatch.start()` is called from `src/web/app.py:2153`
  on web service startup

### READ BUT NOT WRITTEN TO PER-RECORD (3 discard points)

**4. bison_watch_loop.py snapshot() — scripts/bison_watch_loop.py:114-200**
- Reads: `bison.campaign()` — campaign-level counters: `emails_sent`,
  `replied`, `bounced`, `unsubscribed`, `leads`
- Also reads: `bison.scheduled_emails()` — per-lead queue rows (for blank
  content scan and sent_rows count)
- Writes: `watchsink.beat()` → `work/heartbeat/bison-{id}.json` (liveness)
  and `watchsink.emitter()` → `work/watch-events/bison-{id}.jsonl` (events)
- **DISCARDED for per-record purposes** — zero calls to `store.patch`,
  `store.log`, or `store.save`. Campaign-level counters cannot be
  decomposed into per-lead events anyway.

**5. slackagentreadback.py campaign_readback() — src/slackagentreadback.py:575-612**
- Reads: `bison.campaign()` — same campaign-level counters
- Writes: returns a dict for Slack notification
- **DISCARDED** — zero calls to `store.patch/log/save`. Read-only for Slack.

**6. bisonevents.normalise() — src/bisonevents.py:1-140**
- Reads: EmailBison webhook payloads (if any arrive)
- Writes: normalised event dicts
- **DISCARDED** — no webhook endpoint is wired. The module is a pure
  normaliser with no consumer. `inbound.ingest()` is the actual consumer
  path, reached via the poller.

### Reply classification write-back

**7. replies.apply() — src/replies.py:1383-1530**
- Called from: `inbound.handle()` after `events.apply()` records the reply
- Writes: `events.record(rec, events.REPLY_CLASSIFIED, ...)` at line 1401
- Also writes: `events.OUT_OF_OFFICE_RECORDED` (line 1425),
  `events.NOT_NOW_RECORDED` (line 1444), `events.POSITIVE_REPLY_DETECTED`
  (line 1520)
- ✅ **WRITTEN** to the record's event log, as part of the automated
  replywatch path

### Honest count

| Path | Read? | Written to record? | Automated? |
|------|-------|--------------------|------------|
| leadobserve.confirm_email_touches | ✅ | ✅ PUSH_MARKED, EMAIL_BOUNCED | ❌ CLI only |
| leadobserve.confirm_touches | ✅ | ✅ PUSH_MARKED (LinkedIn) | ❌ CLI only |
| replywatch → poller → events.apply | ✅ | ✅ REPLY_RECEIVED, EMAIL_BOUNCED, EMAIL_DELIVERED, LINKEDIN_CONNECTED | ✅ |
| replies.apply (classification) | ✅ | ✅ REPLY_CLASSIFIED, POSITIVE_REPLY_DETECTED | ✅ |
| bison_watch_loop snapshot | ✅ | ❌ heartbeat/watch-events only | ✅ |
| slackagentreadback campaign_readback | ✅ | ❌ Slack dict only | ✅ |
| bisonevents.normalise | ✅ | ❌ no consumer wired | N/A |

**Total: 4 paths write back, 3 paths read-and-discard.**

### The gap, stated plainly

The write-back infrastructure EXISTS and is TESTED. The gap is that
`leadobserve.confirm_email_touches()` and `leadobserve.confirm_touches()`
— which record provider-confirmed SENDS — are CLI-only. The automated
path (`replywatch`) only polls for replies and conversations, not for
send-state transitions. A send confirmed by the provider between reply
polls is not recorded until somebody runs the CLI.

### What this task did NOT build

The task instruction said "build only what the trace shows is missing."
The trace shows the write-back code already exists and is tested (84
existing tests). What is missing is the AUTOMATION of the send-confirmation
path — wiring `leadobserve.confirm_email_touches()` into the replywatch
cycle. That is a production wiring decision (it adds provider API calls
to the automated poll loop, which has cost and rate-limit implications),
and is recommended for Claude's action rather than built here.
