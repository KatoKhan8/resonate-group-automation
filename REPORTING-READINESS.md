# Reporting readiness

What the engine can already report on, what phases 7 and 8 added, and what can
only come from outside. No dashboard is built. Nothing here invents a number a
provider does not give us.

## Status

The event model in this document is now implemented: `src/events.py` holds the
vocabulary and the neutral ingestion interface, `src/report.py` derives every
number from the event stream, and both are covered offline. What follows still
describes the boundary, and the "external" rows are still external.

## The honest boundary

This engine prepares and records. It does not send, and it does not receive.
So it can report everything up to the moment of sending, and nothing after it,
until EmailBison and HeyReach are wired up to report back.

Anything below marked **external** is not derivable from `work/queue.jsonl` at
any point in this build. Showing an invented number there would be worse than
showing nothing.

## Company qualification level

Added with the ICP engine, and available *before* anything has been spent —
which is the only reporting surface in this system that can say anything useful
about a batch nobody has paid for yet.

| Metric | Available | Where from |
|---|---|---|
| companies uploaded / classified | yes | `report.qualification_funnel()` |
| qualified / review / rejected / unknown | yes | the stored ICP verdict |
| tier and confidence distribution | yes | the stored ICP verdict |
| vertical, subvertical, industry, business model | yes | `report.qualification_distribution()` |
| country, region, timezone | yes | the stored segment |
| employee band, maturity, delivery model | yes | the stored segment |
| companies needing manual review | yes | review plus unknown |
| campaign segments and their sizes | yes | `report.campaign_segments()` |
| decision makers **planned** | yes | the persona plan's contact cap |
| decision makers **found** | yes, and 0 until enrichment runs | `len(contacts)` |
| expected / maximum / fallback credits | yes | `report.credit_exposure()` |
| companies costing zero person credits | yes | `companies_skipped` |
| **actual** credits spent | **external** | no provider reports per-call spend |

The distinction that matters on this surface is planned against actual.
`planned_contacts` is a forecast and `found_contacts` is a result, and on a
qualified batch the second is legitimately 0 — because nobody has been looked
up, not because nobody is there. `enrichment_has_run` is on the response so a
dashboard can say which of those it is looking at.

`actual_credits` is `None` rather than `0`, for the same reason it is `None`
everywhere else in this document: a zero there reads as "we spent nothing",
which is a claim, and we do not have the evidence for it.

## Campaign level

| Metric | Available | Where from |
|---|---|---|
| domains uploaded | yes | records ingested, count of the batch |
| contacts found | yes | `len(record["contacts"])` across the batch |
| verified | yes | contacts where `lint.sendable` is true |
| held | yes | records in state `held` |
| dropped | yes | records in state `dropped`, each with `drop_reason` |
| suppressed | yes | dropped with reason `suppressed (live account)` |
| duplicates | yes | dropped with reason `duplicate domain` |
| sent | partial | steps with `status: pushed` are what we handed over. Actual delivery is **external** |
| delivered | **external** | EmailBison |
| replies | partial | recorded through `events.ingest()`, by hand or by a future webhook. Automatic capture is **external** |
| positive replies | **external** | requires classification of a reply body we never see |
| meetings booked | **external** | CRM or calendar |

## Persona level

Persona is on every contact, so counts and send counts are already exact:

| Metric | Available |
|---|---|
| persona counts | yes, `contacts[].persona` |
| send counts | yes, pushed steps grouped by the contact's persona |
| reply rate | only from recorded reply events, so partial until reply ingestion exists |
| positive reply rate | **external** |
| meeting rate | **external** |

## Angle level

Same shape. `contacts[].angle` is set by phase 6 or the `persona_angle` step,
and the evidence behind it is on the record's log, so an angle's performance
can be traced back to why it was chosen.

| Metric | Available |
|---|---|
| angle counts | yes |
| reply rate | partial, as above |
| positive reply rate | **external** |
| meeting rate | **external** |

## Channel level

| Metric | Available | Where from |
|---|---|---|
| email versus LinkedIn activity | yes | pushed steps carry the channel in the `push_id` |
| reply source | yes | `events[].type` is `email_reply` or `linkedin_reply` |
| company-wide pause source | yes | `paused` carries `reason` and `by` (the contact key) |
| connection accepted | yes | `events[].type` is `connection_accepted` |

## Process level

All of this is already recorded, per record, on the queue:

| Metric | Where from |
|---|---|
| current stage | `record["stages"]`, per stage status and timestamp |
| failures | `record["stages"][stage]["note"]` where status is `failed`; `run.run()` collects them |
| provider calls | `record["log"]` entries from the enrich and verify steps |
| estimated credits | `enrich.run()` dry, using `providers.COST` |
| actual credits | **partial**: ContactOut's `get-api-usage-stats` reports account usage per month. Per record attribution is not available from the provider |
| lint failures | `lint.check_all()`, and `summary.json` carries `lint_failed` per step |
| retries | `record["log"][].attempts` and `[].rejected` for model steps |
| LLM retries | same fields, written by `llm.ask` through `generate` |

## What phases 7 and 8 newly record

- `cadence[contact][day].status` — pending, eligible, waiting, paused, blocked, pushed
- `cadence[contact][day].push_id` — `record:contact:day:channel`, the idempotency key
- `cadence[contact][day].pushed_at`
- `events[]` — append only, the full vocabulary above
- `paused` — company level, with cause and origin contact
- `stages{}` — per stage status, timestamp and note

Those are enough to answer "what happened to this company, and why did it
stop", which is the question a client actually asks.

## What future ingestion is needed

1. **EmailBison webhook or polling**: delivered, bounced, opened if available,
   replied. Keyed back to `push_id`, which is why `push_id` is stable and
   carries the record, contact, day and channel.
2. **HeyReach webhook or polling**: connection accepted, replied, keyed the
   same way. `connection_accepted` is already an event this engine understands
   and acts on, so wiring it up changes reporting and behaviour at once.
3. **Reply classification**: positive, negative, out of office, wrong person.
   This needs the reply body, which means an inbox integration, and it is the
   only place where a model would be reading someone else's words. It should be
   a separate decision.
4. **Meetings**: calendar or CRM. Out of scope for this engine.

## The stable event names, as implemented

These are the names in `src/events.py`. They are the vocabulary: renaming one
breaks longitudinal reporting, so nothing invents a variant.

```
batch_ingested         record_suppressed      record_dropped
enrichment_started     enrichment_completed   contact_found
verification_result    persona_selected       draft_generated
lint_failed            draft_approved         cadence_prepared
push_prepared          push_marked            company_paused
email_delivered        email_bounced          reply_received
linkedin_connected
```

The first fifteen are produced by the pipeline. The last four can only arrive
from outside, through `events.ingest()`.

Every one of them keys on `record_id` plus, where relevant, `contact_key` and
`push_id`. Those three identifiers are already stable and deterministic across
re-runs, which is what makes longitudinal reporting possible at all.

## By provider, verifier and research source

Implemented in `src/report.py`, all derived from the event stream:

| Question | Call |
|---|---|
| calls planned, started, completed, skipped, failed per provider | `report.by_provider()` |
| estimated credits per provider | same, `estimated_credits` |
| actual credits per provider | same, `actual_credits`, and it is `None` on purpose |
| what each verifier said | `report.by_verifier()["per_verifier"]` |
| final verification states and how many are sendable | `report.by_verifier()["final"]` |
| how often verifiers contradicted each other | `report.by_verifier()["disagreements"]` |
| where the evidence came from | `report.by_research_source()` |

`actual_credits` stays `None` because no provider reports per-call spend.
ContactOut reports account usage per month, which is a different number and
must not be presented as a per-record cost.

## Client isolation

Every record carries `client`. Reporting must filter on it at the query
boundary, not in the presentation layer, and no aggregate shown to one client
may be computed across another's records. The queue is a single file today, so
this is currently a convention rather than an enforced boundary: see
`WEB-READINESS.md`, gap 2.


## Campaign, Slack and reply reporting

### Available now, from this system's own events

| Report | Source |
|---|---|
| campaigns by status | `report.campaign_rows()` |
| campaign approval latency | `report.approval_latency()` - requested vs decided, and who is still waiting |
| who approved what, and against which fingerprint | the campaign's `approval` block and `campaign_approved` event |
| approvals invalidated, and why | `campaign_approval_invalidated` events |
| replies by classification | `reply_classified` events, broken down in `report.daily_summary()` |
| positive replies | `positive_reply_detected` events |
| companies paused, and by which channel | `company_paused` events |
| Slack notifications planned, sent, failed | the three `slack_notification_*` events |
| sender assignment | `sender_assigned` events |
| held and dropped counts | record state |
| persona, angle and channel breakdowns | as before, `report.by_dimension(...)` |

Note what the three Slack events give you: planned-but-not-sent is a real
number, and it is the one that tells you a channel is misconfigured rather than
quiet.

### Available once live sending is enabled

| Report | Blocked on |
|---|---|
| emails actually sent | nothing pushes yet; `push_marked` exists but is never written live |
| sends per sender account | the same, plus the account each push used |
| daily volume actually achieved vs configured | live pushes |
| time from launch-ready to first send | a launch that happens |

### Available once provider events are connected

| Report | Blocked on |
|---|---|
| delivered, bounced | an EmailBison webhook or polling contract - **not confirmed**, see `bison.events_contract()` |
| connection accepted | a HeyReach webhook or inbox contract - **not confirmed**, see `heyreach.events_contract()` |
| reply response time | a reply timestamp we can trust, which needs the above |
| sender performance (reply rate per inbox) | delivery plus reply events |
| provider spend | ContactOut reports usage per account, not per call; Apify bills compute units |

### Deliberately not reported

- **meetings booked** - nothing observes a calendar. The Slack alert offers a
  "Mark meeting booked" action, so the number will exist once someone presses
  it, and not before. `report.daily_summary()` returns `None`, never `0`.
- **opens** - unreliable wherever they are reported at all.

The rule this file has followed from the start still holds: a metric with no
source is absent, not zero. A zero reads as "it happened and there were none".
