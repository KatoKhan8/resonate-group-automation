# Web readiness

No web framework is installed and none is proposed here. This describes the
service boundary a UI would call, what already exists behind it, and the few
places where the seam is not yet clean.

Nothing in this document authorises sending. A UI can prepare and review; the
live push does not exist in this build.

## What already works without a shell

Every stage is a Python function with a plain return value. The CLIs are thin
wrappers, so a web layer calls the same functions and never parses stdout.

| Operation | Call | Returns |
|---|---|---|
| create a batch from a CSV or a folder | `ingest.run(source, client, lane, suppress_path=None)` | queued ids, dropped with reasons, skipped |
| queue contents | `store.list_records(state=, lane=, client=)` | records |
| one record | `store.get(id)` | record |
| counts by state and lane | `store.stats()` | dict |
| plan enrichment and its cost | `enrich.run(live=False, cap=…)` | per record ops, why, credit exposure |
| enrich for real | `enrich.run(live=True, cap=…)` | same, after spending |
| personas and per-domain export | `personas.run(apply=, do_export=, ids=, lane=)` | kept, excluded with reasons |
| model steps | `generate.run(model=…, live=…)` | per record steps and why |
| lint results for every draft | `lint.check_all()` | status, failures, per step |
| review artefacts | `render.build()` | summary dict, writes `out/` |
| the timeline for a company | `cadence.build(record)` | per contact, per day, per status |
| record a reply or an acceptance | `cadence.record_event(rec, kind, contact_key)` | event, sets the company pause |
| prepare a push | `push.run(day=…)` | ready, skipped with reasons, exact payloads |
| walk the whole pipeline | `run.run(spend=…, cap=…, ids=…, limit=…)` | per stage summary, failures, states |

## Mapping the requested UI to those calls

- **Upload a CSV or paste domains** → write the upload to `batches/`, call
  `ingest.run`. Pasted domains become a one column CSV first.
- **Create a batch** → `ingest.run` stamps every record with a `batch` id, and
  `report.by_dimension("batch")` reports on it.
- **Live batch progress** → poll `store.stats()` and the per record
  `stages` map. Every stage writes its status, so progress is derivable
  without a second store.
- **Queue states, clean / held / dropped counts** → `store.stats()` plus
  `render.build()`'s summary, which already returns clean, held, failed and
  dropped with reasons.
- **Personas** → `record["contacts"]` carries persona, angle and key;
  `record["excluded"]` carries everyone who was not kept, with the reason.
- **Company details** → `record["company_facts"]`, already trimmed. Safe to
  serialise as is: no raw provider payload is ever stored.
- **Review drafts** → `lint.check_all()` gives every generated email with its
  status and failures. `render.build()` writes the same thing as HTML.
- **Approve / reject** → `approve.pending()` lists what is waiting and what is
  blocked with the reason; `approve.approve_step()` / `approve.approve_record()`
  grant it; `approve.revoke()` takes it back. Nothing is push eligible without
  it, and editing a draft invalidates it automatically.
- **Trigger a dry run** → `run.run()` with no `spend`.
- **Later, an explicit live push** → `push.run(live=True)` raises
  `LiveSendNotEnabled` in this build. That is the single place to change when
  sending is built, and it must stay behind an explicit human action.
- **Provider credit estimates** → `enrich.run()` dry returns `spent` as the
  planned exposure and `refused` for anything a cap blocked. `providers.COST`
  holds the per call cost table.
- **Error reasons** → `run.run()` returns `failures` with the record id, the
  stage and the reason. Per record, `record["stages"][stage]["note"]`.
- **Client level data only** → every record carries `client`, and
  `store.list_records(client=…)` filters. See the gaps: this is a filter, not
  yet an enforced boundary.

## Closed since this document was written

- **Approval exists.** `approve.pending()` returns what a human has to look at
  and why anything cannot be looked at; `approve.approve_step()` and
  `approve.approve_record()` are the actions a UI button calls. Nothing is push
  eligible without it, and editing a draft revokes it.
- **Batches exist.** Every record carries `batch`, so "show me batch 14" is now
  expressible and `report.by_dimension("batch")` answers it.
- **Concurrent writes are safe.** `store.lock()` and `store.transaction()` make
  two processes serialise rather than overwrite. See the migration note below.
- **Events exist.** `events.ingest()` takes provider-neutral events, is
  idempotent on the provider's own event id, and drives the company pause.

## What a record screen can now show

Every provider decision is on the record, with its reason, so a UI can render
this without asking the backend a second question:

```
RECORD          Example Company (example.test)

ENRICHMENT
  ContactOut    used      people-count, decision-makers
  AI Ark        skipped   ContactOut was sufficient
  Apify         skipped   structured evidence is sufficient

VERIFICATION
  ContactOut    accept_all
  Deliverable   not called: the primary was not ambiguous enough to need it
  Reoon         safe_to_send true
  FINAL         SENDABLE, because the catch-all was cleared by reoon

COST
  ContactOut    11 credits estimated
  Deliverable   0
  Reoon         1
  Apify         no run
```

The calls behind it: `report.by_provider()` for the first block,
`report.by_verifier()` and `contact["verification"]` for the second,
`report.by_provider()[provider]["estimated_credits"]` for the third. Every
provider carries a used-or-skipped reason: `provider_call_planned`,
`provider_call_skipped` and `provider_call_completed` events on the record, and
`verification.evidence[].reason` for the verifiers.

Actual credits are deliberately absent. No provider reports per-call spend, so
the UI should show estimates and label them as estimates.

## Gaps a web layer would need closed

1. **Client isolation is a filter, not a boundary.** Everything reads the one
   `work/queue.jsonl`. For multi client use, either partition the queue per
   client or enforce the filter in a service layer that never hands a caller
   another client's records.
2. **The file lock is a CLI mechanism, not a server one.** It is correct for a
   handful of processes on one machine and wrong for anything else. When the
   web version arrives:

   - the lock does not work across machines or across a network share, and it
     serialises the whole queue rather than one record, so throughput is one
     writer at a time by design
   - replacing it means moving `work/queue.jsonl` into a real database: one row
     per record, `SELECT ... FOR UPDATE` or an optimistic version column in
     place of `store.transaction()`, and the append-only `events` list becoming
     its own table with a unique index on `provider_event_id`
   - `store.py` is the only module that touches the file, so the migration is
     rewriting one module and its tests, not the pipeline
   - keep the invariants that the file gave you for free: never delete a record,
     always write a `drop_reason`, and make the write atomic
3. ~~**The record `approved` state is still unused.**~~ **Closed.** It is now
   *derived* from the steps rather than set: `approve.sync_state()` recomputes
   it from the per-step fingerprints, so a record reaches `approved` when every
   step a human could approve carries a current signature, and drops back to
   `drafted` the moment one is edited or revoked. Derived rather than latched
   on purpose — a latched flag has to be remembered to un-latch, and a
   recomputation cannot be forgotten. A UI must still never write it.
4. **Progress is derivable, not pushed.** There are no events to subscribe to.
   Polling `stats()` is adequate at batch sizes of a few hundred.
5. **Long operations are synchronous.** `run.run` on 500 records with `spend`
   will block for a long time. A web layer needs a job runner; the work is
   already resumable, so a job can be killed and restarted safely.

## What must not move to the web layer

- Lint. It is the release valve, and it must stay in front of every push path.
- Sendability. It is recomputed from the verdict every time and must never be
  read from a UI supplied flag.
- The suppression check. It belongs at ingest, before anything is spent.
- The credit cap. A UI may choose the number; it must not be able to remove it.


## Campaign orchestration and the Slack control layer

A campaign is now a first-class object with its own state file,
`work/campaigns.jsonl`, and its own approval. This is the part a UI will spend
most of its time on, so the boundary is worth stating precisely.

### The flow a UI would drive

    Create campaign
      -> upload or paste domains        ingest.run(...)
      -> processing                     run.run(...)  (enrich, verify, generate)
      -> review                         render.build(), lint.check_all()
      -> approve drafts                 approve.approve_step(...)
      -> campaign approval              orchestrator.request_approval(...)
                                        orchestrator.decide(...)
      -> launch-ready                   orchestrator.launch_readiness(...)
      -> launch                         orchestrator.launch(...)   [refuses: live off]
      -> live progress                  campaigns.dry_run(...), report.daily_summary()
      -> replies and positives          inbound.ingest(...)
      -> reporting                      report.campaign_rows(), report.daily_summary()

### Calls a UI needs

| Operation | Call | Returns |
|---|---|---|
| create a campaign | `orchestrator.create(campaign_id, client, name, record_ids=…)` | the campaign |
| list campaigns | `campaigns.load()` | rows |
| one campaign | `campaigns.require(campaign_id)` | the campaign |
| set the population | `orchestrator.set_records(campaign, ids)` | campaign, approval invalidated if it moved |
| map external campaigns | `orchestrator.map_external(campaign, bison_campaign_id=…, heyreach_campaign_id=…)` | campaign |
| set senders | `orchestrator.set_senders(campaign, email=[…], linkedin=[…])` | campaign |
| set daily volume | `orchestrator.set_daily_volume(campaign, email=…, linkedin=…)` | campaign |
| the review numbers | `orchestrator.summarise(campaign)` | domains, contacts, sendable, held, dropped, senders, estimate, fingerprint |
| ask for approval | `orchestrator.request_approval(campaign)` | summary, Slack payload, notification plan |
| apply a decision | `orchestrator.decide(campaign, actor, "approve" or "reject", fingerprint=…, interaction_id=…)` | approved / rejected / stale / duplicate |
| the launch checklist | `campaigns.validate(campaign_id)` | 17 checks, each with a reason |
| readiness, and the status move | `orchestrator.launch_readiness(campaign)` | same, and sets `launch_ready` |
| dry run | `campaigns.dry_run(campaign_id, day=…)` | contacts, channels, senders, payloads, estimate |
| launch | `orchestrator.launch(campaign, live=True)` | raises `LiveSendNotEnabled` |
| pause / resume | `orchestrator.pause(...)` / `orchestrator.resume(...)` | campaign |
| inbound events | `inbound.ingest(payload, provider)` | per event: applied, paused, classification, notification |
| a typed reply | `inbound.manual(record_id, contact_key, text)` | a neutral event for `inbound.handle` |
| daily numbers | `report.daily_summary()` | only metrics with a real source |
| approval latency | `report.approval_latency()` | measured pairs, plus who is still waiting |

### What a UI must not do

- **Never write `sendable`, `approval` or `status` directly.** Each has one
  writer: `verification.apply`, `orchestrator.decide`, `campaigns.set_status`.
  A form that sets them turns a safety check into a checkbox.
- **Never trust its own copy of the fingerprint.** Send back the one the
  payload carried; the server recomputes and compares. This is what makes
  "approve" mean "approve *this*".
- **Never offer launch to a role without `launch_campaign`.** `src/roles.py`
  holds the table; `roles.may(role, permission)` is the only question to ask.

### Authentication, which does not exist yet

`roles.role_of(config, actor)` maps an actor to a role from client config. A
web layer supplies *who the user is*; it does not get to decide what that role
may do. When real auth arrives, only `role_of` changes.

### Still not clean

- There is no HTTP surface at all. Every call above is in-process.
- A UI would want per-campaign progress while a run is in flight; the runner
  reports per stage, not per record, so a progress bar would need polling
  `store.stats()`.
- Slack interactions arrive over HTTP in real life. `slack.interaction(...)`
  defines the neutral shape a webhook handler would build; the handler itself
  is not written, because nothing may post yet.


## Inbound transport: the three endpoints a deployment will need

None of these exists yet. What exists is everything behind them, so the HTTP
layer, when it is built, is thin by construction.

    POST /webhooks/emailbison
    POST /webhooks/heyreach
    POST /webhooks/slack

### The rule for all three

**No business logic in the HTTP layer.** A handler reads the raw body and the
headers, calls one function, and returns a status. That is the whole
responsibility. Every decision - is this real, is it a duplicate, does it pause
a company, may this person approve - already lives in a module that is tested
offline. A handler that starts making decisions is a handler that behaves
differently from the CLI, and then there are two systems.

### POST /webhooks/slack

The only one of the three with a verifiable signature, and the only one that
can change a campaign, so it is the one that matters.

    body      = raw request body, read BEFORE any parsing
    timestamp = X-Slack-Request-Timestamp
    signature = X-Slack-Signature

    ts, sig = interactions.headers_from(request.headers)
    try:
        result = interactions.handle(request.raw_body, ts, sig)
    except interactions.Rejected:
        return 401                  # never retried, never explained further
    return 200

`interactions.handle()` does, in this order: verify the signature, check the
timestamp is within five minutes, check the interaction id has not been seen,
parse, check the actor is a configured approver, check the fingerprint still
matches, then apply through the orchestrator. The body is not parsed until the
signature passes, so a forged payload never reaches code that trusts it.

Return 401 with no detail. An error message that explains *why* a signature
failed is a tool for the person forging the next one.

### POST /webhooks/emailbison and /webhooks/heyreach

Neither provider signs its webhooks. EmailBison's self-hosted instance exposes
no webhook management endpoint at all (`/api/webhooks` answers 404) and the
product documents no signature; HeyReach's webhook management is not on the
confirmed surface either.

An unsigned webhook is an open door: anyone who learns the URL can pause every
company you have, or worse, name a record and pause a competitor's. So the
handler for these two must **not** treat the payload as evidence. It should:

    1. verify a shared secret carried in the URL path, since there is no
       signature to verify - a long random path segment, rotated like a key
    2. count `webhook_received` and return 200 immediately
    3. trigger a poll, and let the poll be the source of truth

That is deliberately underwhelming. The webhook becomes a latency optimisation:
it tells us to look now rather than in five minutes. What actually decides
anything is `poller.run(provider, live=True)`, which reads the provider's own
API with our own credentials. Nothing an attacker posts can fabricate a reply
that way.

If either provider adds signed webhooks, the payload can be promoted from hint
to evidence by pointing the handler at `inbound.ingest()` instead - the mapping
is already written and tested against real responses.

### What the poller does, and why it is safe to run on a timer

    poller.run("emailbison", live=True)
    poller.run("heyreach", live=True)

  - resumes from a durable cursor in `work/checkpoints.json`, so it never
    rescans history and never re-pauses a company that was unpaused by hand
  - is bounded by `max_pages`, so a provider that hands back cursors for ever
    stops rather than spinning
  - retries a transport error at most three times with a finite backoff, and
    never retries a malformed payload
  - is idempotent end to end: every event carries the provider's own id, and
    applying the same page twice changes nothing

### Idempotency, stated once

| Layer | Key | Behaviour on a repeat |
|---|---|---|
| provider event | `provider_event_id` (`emailbison:<uuid>`, `heyreach:<thread>:<ts>`) | second application is a no-op |
| Slack interaction | derived from message ts + action + user | second click is `duplicate` |
| campaign approval | the interaction id, recorded on the campaign | survives a restart |
| push | `record:contact:day:channel` | never prepared twice |

### The trap both feeds share

Both providers return **our own outgoing messages** alongside the replies.
EmailBison marks them `type: "Outgoing Email"` in folder `Sent`; HeyReach
leaves `lastMessageSender` as us. Read either naively and the engine pauses
every company the moment it contacts them. `src/adapters.py` allowlists what
counts as inbound, and `tests/test_transport.py` exists mostly to keep it that
way.


## The next real test: five domains, no send

The whole point of the preview is that this sequence ends in a decision rather
than a send. Nothing below is authorised yet - the enrichment steps spend real
credits and need saying so first.

    # 1. a batch of five real domains you have chosen
    python -m src.ingest --source batches/five.csv --client <client> --lane cold

    # 2. what enrichment would cost, before it costs it
    python -m src.enrich                      # dry run: plan and exposure
    python -m src.enrich --live --cap 40      # ~8 credits per domain, capped

    # 3. verification, through the central resolver
    python -m src.run --stage verify

    # 4. research: free to plan, and it will refuse where nothing is missing
    python -m src.personalization --plan
    python -m src.research --plan

    # 5. drafts, personas, cadence
    python -m src.personas --apply
    python -m src.generate --live
    python -m src.lint

    # 6. the campaign
    python -m src.orchestrator create five-real --client <client> --name "Five"
    python -m src.campaigns validate five-real

    # 7. the deliverable
    python -m src.preview five-real
    # -> out/campaign-preview.html

    # 8. nothing else. There is no step 9 in this build.
    python -m src.campaigns dry-run five-real   # payloads, sent nowhere

`python -m src.preview --demo` builds the same page from fictional data and
needs no credentials, which is the right way to see the shape of it first.

### What to look at in that first real preview

In rough order of how much it would cost to get wrong:

1. **The evidence, before the copy.** For each contact, read the "Why this
   message?" block and ask whether *you* would believe the claim from the
   source shown. If the signal is real but the sentence overstates it, the
   generator is the problem; if the signal itself is thin, the research policy
   is.
2. **The dates.** Anything marked `unknown` freshness is a fact with no date
   behind it. Decide whether you are comfortable sending it at all.
3. **The fallbacks.** Companies with no signal should read as competent and
   plain, not as personalisation with the specifics filed off. If the
   no-signal message is embarrassing, the fallback needs work before scale
   does.
4. **The addresses.** Every `not sendable` is a contact you paid to find and
   cannot write to. If that count is high, verification policy is where the
   money is going.
5. **The provider waterfall.** AI Ark or Apify appearing on companies where
   ContactOut already answered means the gap analysis is too eager.
6. **The cadence as a whole.** Read all seven steps for one contact in order,
   as the recipient would over three weeks. That is the only way to notice
   that two steps make the same point.
7. **The lint failures and pending approvals.** These are the ones that will
   silently shrink the campaign at launch.


## Service boundaries for a web product

No framework is proposed. What follows is the API surface a UI would need, and
every row already exists as an in-process function — which is the point: the
HTTP layer stays a translation of arguments to JSON and never grows a decision
of its own.

### Upload

    POST /api/batches              ingest.run(source, client, lane)
    GET  /api/batches/{id}         store.list_records(...)

A drag-and-drop upload posts a CSV or a pasted list; the response is the
ingest summary that `ingest.run` already returns, including what was dropped
and why. Suppression happens here, not later.

### Campaign

    POST /api/campaigns            orchestrator.create(...)
    GET  /api/campaigns            campaigns.load()
    GET  /api/campaigns/{id}       campaigns.require(id)
    PATCH /api/campaigns/{id}      orchestrator.set_records / set_senders /
                                   set_daily_volume / map_external

Every PATCH may invalidate the approval, and the response must say so rather
than leaving the UI to notice: return the fingerprint before and after.

### Status

    GET  /api/campaigns/{id}/status    store.stats() + campaign.status
    GET  /api/campaigns/{id}/progress  per-stage counts

Progress is per stage, not per record — the runner reports stages, and a
per-record progress bar would need polling `store.stats()` on a timer.

### Preview

    GET  /api/campaigns/{id}/preview        preview.gather(...)  -> JSON
    GET  /api/campaigns/{id}/preview.html   preview.build(...)   -> HTML

`gather()` returns everything the HTML page is built from, so a richer UI can
render the same data without scraping the page. Both are read-only; neither can
approve, launch or call a provider.

### QA

    GET  /api/campaigns/{id}/qa      qa.report(...)

Returns the verdict, six sub-scores, counts and the ordered review queue. A
BLOCK here should disable the approve control in the UI, and the API should
refuse the approval independently anyway.

### Approval

    POST /api/campaigns/{id}/approve   orchestrator.decide(campaign, actor,
                                                           "approve",
                                                           fingerprint=...)
    POST /api/campaigns/{id}/reject    same, "reject"

The fingerprint the UI holds must be sent back and is compared server-side.
This is the same contract the Slack path uses, and for the same reason: a
button that posts a stale fingerprint is refused.

### Eligibility and launch

    GET  /api/campaigns/{id}/readiness  orchestrator.launch_readiness(...)
    POST /api/campaigns/{id}/launch     orchestrator.launch(...)  [refuses]

### Reporting

    GET  /api/reports/client/{slug}     report.for_client(slug)
    GET  /api/reports/campaign/{id}     report.funnel_for(recs, campaign)
    GET  /api/reports/persona           report.by_persona()
    GET  /api/reports/angle             report.by_angle()
    GET  /api/reports/daily             report.daily_summary()

### Events

    GET  /api/campaigns/{id}/events     the record and campaign event streams
    POST /api/webhooks/{provider}       see the inbound transport section above

### Rules for whoever builds this

- **The HTTP layer holds no business logic.** Arguments in, JSON out, status
  code from the exception type. Every rule already has a home.
- **Never trust a client-supplied verdict.** Not `approved`, not `sendable`,
  not `eligible`. The server recomputes; `eligibility.decide()` exists for
  exactly this.
- **Every mutating endpoint takes the fingerprint it was rendered from.**
  That is optimistic concurrency for humans, and it is already implemented.
- **Read endpoints must not spend.** Nothing behind a GET may call a paid
  provider — preview, QA and reporting are all pure functions over stored state
  today, and that property is worth protecting with a test.

## Worker and job architecture

Not built. The design, for when the single-writer queue is replaced:

| Job | Idempotency key | Bounded by | Retry |
|---|---|---|---|
| ingest | batch id + source hash | rows in the file | no — a parse failure is permanent |
| company enrichment | record id | credit cap, per-domain | transport errors only |
| contact enrichment | record id | credit cap | transport errors only |
| verification | contact id + provider | one call per contact per provider | transport errors only |
| research | record id / contact key | `max_sources_per_company` | transport errors only |
| generation | record + contact + step | steps per contact | model errors, bounded |
| render | campaign id | — | yes, pure |
| reply polling | provider cursor | `max_pages` | transport errors only |
| scheduled outbound | `push_id` | daily volume, sender caps | never blindly |
| reporting | campaign id | — | yes, pure |

Four properties every job needs, and all four already exist in some form:

- **Idempotent**: each has a natural key above, and every one is already
  computed somewhere in this codebase.
- **Bounded**: a job that can run forever will. Every ceiling above is
  configurable and none is invented from a provider's undocumented limits.
- **Retryable, selectively**: transport errors retry with finite backoff;
  malformed payloads, bad signatures, unauthorised approvals and stale
  fingerprints never do. `poller.with_retry()` already draws that line.
- **Observable**: `src/observability.py` counts what happened without storing
  payloads, and the event log carries the rest.

The one job that must never be parallelised carelessly is scheduled outbound.
It is the only one where a race sends something twice, and `unique (push_id)`
in DATABASE-MIGRATION.md is the constraint that makes that structurally
impossible rather than merely unlikely.


## The pre-production surface

Added with the simulator. Everything below is read-only and offline: no
endpoint here can send, launch, mutate a provider campaign, or spend a credit,
and that is a property worth a test rather than a convention.

### Batch lifecycle

    POST /api/batches                  ingest.run(source, client, lane)
    GET  /api/batches/{id}/validate    campaigns.validate(...)  [read-only]
    GET  /api/batches/{id}/estimate    plan.size() + scalesim provider counts
    POST /api/batches/{id}/enrich      enrich.run(...)          [spends]
    POST /api/batches/{id}/generate    generate.run(...)        [spends]

Only the last two spend anything, and both are POSTs for exactly that reason.
`validate` and `estimate` are GETs and must stay that way.

### Simulation and preview

    GET  /api/preview?client=&batch=        simulator.simulate(...)  -> JSON
    GET  /api/preview.html                  previewpage.page(...)
    GET  /api/preview/files                 previewpage.write_all(...)
    GET  /api/preview/qa                    simulator.qa_metrics(...)
    GET  /api/preview/slack                 simulator.slack_preview(...)
    GET  /api/preview/report                simulator.reporting_preview(...)

`simulate()` returns everything the page renders, so a richer UI never has to
scrape HTML. `would_send` is in the response and is always 0; a client that
ever sees anything else should refuse to render.

The Slack endpoint returns the payload that *would* be posted, with
`delivered: false`. It is a rehearsal, not a send, and nothing about it should
be wired to a "post now" button without a separate approval path.

### Per-contact detail

    GET  /api/records/{id}/contacts/{key}/dossier    dossier.build(...)
    GET  /api/records/{id}/contacts/{key}/channels   channels.evaluate(...)
    GET  /api/records/{id}/contacts/{key}/quality    quality.assess(...)
    GET  /api/records/{id}/contacts/{key}/audit      audit.why_contacted(...)

These four answer the four questions a reviewer asks about one person: what do
we know, can we reach them, is the message actually personal, and how did they
get here.

### Waterfall and spend

    GET  /api/waterfall                 waterfall.describe()
    GET  /api/records/{id}/waterfall    waterfall.audit(record)

`describe()` is static and cacheable - it is the policy, not the data. The
per-record audit names any step taken without a reason the waterfall accepts,
which is the endpoint to watch if provider spend ever surprises anybody.

### Reply rehearsal

    POST /api/records/{id}/simulate-reply    replaysim.simulate(...)

A POST because it mutates the in-memory record, and it is the one endpoint here
that should be gated to non-production data: it exercises the pause path, and a
rehearsal that paused a live company would be a real outage caused by a test.

### Rules, restated for this surface

- **`would_send` is part of the contract.** Any preview response missing it, or
  carrying anything but 0, is a bug in the server, not a state to render.
- **No GET spends.** Preview, QA, dossier, quality, waterfall and reporting are
  pure functions over stored state today. Keep them that way; the moment one
  calls a provider, a page refresh costs money.
- **The Slack preview is not a send.** `delivered: false` travels with it, and
  the reason is in the payload.
- **Masking is the default.** Addresses are masked unless the caller asks, and
  asking should be a permission rather than a query parameter.
- **The preview page is capped.** 200 cards, with the omission stated on the
  page. A UI paginating the JSON is welcome to show all of them; a page that
  silently shows the first slice is not.


## The qualification surface

Added with the ICP engine. Everything here runs *before* a person costs
anything, which is the property that makes it safe to expose: no endpoint on
this surface can spend a credit, and the one that unlocks spending is a POST
that a human has to make deliberately.

### Batch qualification

    POST /api/batches/{id}/qualify        qualify.run(...)
    GET  /api/batches/{id}/qualification  qualify.summarise(...)
    GET  /api/batches/{id}/explore        explorer.batch_view(...)

`qualify` is a POST because it writes verdicts onto records; it still spends
nothing. Re-running it is safe and cheap: companies whose facts have not
changed are skipped by fingerprint.

### The segment explorer

    GET /api/batches/{id}/companies       explorer.list_companies(...)
    GET /api/batches/{id}/facets          explorer.facets(...)
    GET /api/segments/{key}               explorer.segment_view(...)
    GET /api/companies/{id}               explorer.company_view(...)
    GET /api/companies/{id}/personas      explorer.persona_view(...)
    GET /api/explorer/contract            explorer.contract()

`contract()` is the endpoint a UI developer reads first: it returns the valid
filters with their allowed values, the facets, the sorts and the drill path, as
data rather than as documentation that can drift.

### The spend gate

    GET  /api/batches/{id}/dm-plan        dmplan.for_batch(...)
    POST /api/batches/{id}/dm-plan/approve
                                          dmplan.approve(batch, companies, by)
    GET  /api/batches/{id}/dm-plan/status dmplan.is_current(...)

The plan is a GET and costs nothing to look at. The approval is the only thing
on this surface that unlocks spending, and it carries a fingerprint of the
qualification result it was given for - so a UI holding a stale plan is refused
rather than allowed to approve something that has changed underneath it.

### Local-time scheduling

    GET /api/companies/{id}/schedule       schedule.for_record(rec, start)
    GET /api/batches/{id}/schedule         schedule.for_batch(segments, start)

Returns every cadence step as a local time and the UTC instant it would fire
at, plus the UTC span the batch covers — which is the number a person planning
sender capacity actually needs, since the same "09:30 local" is a fourteen-hour
window across London, New York, Zagreb and Sydney.

`would_send` is in the batch response and is always 0. A company whose timezone
is unknown comes back `schedulable: false` with every step held and no time
attached; a UI must render the reason rather than substituting a default hour.

### Campaign review

    GET /api/campaigns/{id}/review        demo_outreach.gather()   [shape]
    GET /api/campaigns/{id}/review.html   outreachpage.page(...)

`src/demo_outreach.py` builds this for five fictional contacts, and
`out/demo-outreach.html` is the working prototype of the Campaign Review
screen. The shape `gather()` returns is what a real review endpoint would
return: one card per contact, each carrying the ten blocks the screen renders -
why this company, why this person, contact and verification, evidence,
personalisation, the full expanded cadence, QA and coherence, both provider
payloads, and the event/pause state.

Two properties a UI must not lose. The payloads on that page are built by
`push.payloads()`, the sender's own function, not redrawn by the renderer - a
payload the review screen shapes itself is a payload nobody has tested. And
`would_send` is 0 in the response; a client that ever sees anything else should
refuse to render.

    GET /api/records/{id}/contacts/{key}/coherence   coherence.for_contact(...)

Returns the cross-channel verdict and every finding, each naming the two steps
it is about so the screen can show them side by side. It reports and never
blocks - `qa.report()` is where a blocker becomes a campaign verdict.

### Email verification

    GET /api/records/{id}/contacts/{key}/verification
                                          verification.resolve(contact, policy)
    GET /api/reports/verification         report.by_confirmation(...)

`resolve()` returns the recomputed decision: the state, the reason, the
confirmation count against the requirement, which providers confirmed, whether
they disagree, and the per-provider results with their timestamps. It reads
nothing from the stored state, so a UI cannot be shown a clearance no provider
gave.

Three rules for whoever renders this:

- **Never read `verification.state` or `contact.sendable`.** They are a cached
  projection. `is_sendable` recomputes, and so must the screen.
- **Show the count, not just the verdict.** "1 of 2" and "no verifier could
  answer" are different problems with different fixes, and a screen that shows
  only HELD sends people looking for the wrong one.
- **A disagreement is not a hold to be cleared.** Two providers reached
  different conclusions; the fix is a third opinion or a better address, never
  a button that overrides it.

### Qualification reporting

    GET /api/reports/qualification         report.qualification_report(...)
    GET /api/reports/qualification/funnel  report.qualification_funnel(...)
    GET /api/reports/qualification/mix     report.qualification_distribution(...)
    GET /api/reports/qualification/dm      report.decision_makers(...)
    GET /api/reports/qualification/credits report.credit_exposure(...)
    GET /api/reports/qualification/segments report.campaign_segments(...)

Everything here is derived from what qualification stored, so it is available
before a single person has been looked up. Three kinds of number live on this
surface and a UI must not mix them:

| Kind | Example | Rendered as |
|---|---|---|
| planned | `planned_contacts`, `expected_credits` | a forecast, labelled |
| actual | `found_contacts` | a result |
| unavailable | `actual_credits` | absent, never 0 |

`found_contacts` is 0 on a qualified batch because nobody has been looked up,
not because nobody exists. `actual_credits` is `None` because no provider in
this stack reports per-call spend. Both are named in `report.unavailable()`,
and a tile built for either without reading that is a tile that lies.

### Rules for this surface

- **No GET spends.** Qualification, segmentation, routing, planning and the
  whole explorer are pure functions over stored records.
- **An unknown filter raises.** `explorer.apply_filters` refuses a filter name
  it does not recognise instead of returning everything, because a UI that
  silently ignores a typo produces a confident wrong number.
- **Totals travel with pages.** Every list response carries `total`; a UI that
  shows "20 results" for 4,000 matches teaches people to distrust the product.
- **Contacts are a declared level.** `persona_view` returns an empty
  `contacts` list with `contacts_available: false` and the reason, so the drill
  path does not change shape when enrichment eventually runs.
- **The approval is the boundary.** Everything before it is free and
  re-runnable; everything after it costs money and needs the fingerprint.
