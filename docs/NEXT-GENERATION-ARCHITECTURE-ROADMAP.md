# Next-generation architecture roadmap

Operator intent recorded 2026-09-15, for a sprint roughly a week out.

**THIS IS NOT THE CURRENT EXECUTION PLAN.** The current priority is getting
Productive live and beginning real learning, on the architecture that exists.
Nothing here licenses a migration, a deployment, a dependency or a rewrite
today, and no phase below may be started as a side effect of reading it.

It exists so the reasoning survives the week. A roadmap nobody can return to
is scrollback.

---

## 0. WHAT THIS DOCUMENT IS NOT

It is not a replacement for the architecture documents that already exist,
and where it would repeat one it references it instead:

| Question | The document that answers it |
|---|---|
| How a large TAM is processed as a stream rather than a file | `STREAMING-ARCHITECTURE.md` |
| The Postgres entity model, constraints, optimistic locking, what NOT to migrate | `DATABASE-MIGRATION.md` |
| What the record and campaign schemas actually hold | `SCHEMA.md` |
| Where the time goes at 5,000 domains, and the real bottlenecks in order | `PERFORMANCE-READINESS.md` |
| Target runtime, platform, queue, secrets, rollback, backups | `DEPLOYMENT-PLAN.md` |
| What deliberately does not exist yet | `PRODUCT-GAPS.md` |
| The UI surface and its ~20 screens | `WEB-APP.md` |
| What must be proven live before anything is promised | `LIVE-VALIDATION-PLAN.md` |
| The rules that outrank convenience | `CLAUDE.md`, `PLAYBOOK.md` |
| What is live-validated versus fixture-tested | `LIVE-READINESS.md` |

**Three of those already contain most of a phase below**, and the phase
sections say so rather than restating them:

- `DATABASE-MIGRATION.md` is Phase 1's design. It already sets the trigger
  condition - *"when two processes need to write at once"* - names the
  entities, and lists what not to migrate.
- `DEPLOYMENT-PLAN.md` is Phase 2's design, including the reverse proxy, the
  rollback and the backup story.
- `STREAMING-ARCHITECTURE.md` is the scheduling model the whole roadmap
  serves, and it is already the standing product principle rather than a
  future one.

**One contradiction to be aware of, and it is deliberate.**
`DATABASE-MIGRATION.md` opens with "Not now" and pins the migration to a
specific trigger. This document schedules Phase 1 for a sprint. Those agree
on the condition and differ on whether it has been met: the trigger is
concurrent writers, and the worker pool now routinely runs eight agents
against one estate. The trigger is close, not passed. **Phase 1 starts when
concurrent writers are needed in PRODUCTION, not because a date arrived.**

---

## 1. CURRENT

State of the system this roadmap departs from. Recorded so a later reader can
tell what changed from what was always true.

    runtime          Python, minimal dependencies, local Windows/PowerShell
    state            work/queue.jsonl (records), work/campaigns.jsonl
                     (campaigns), advisory-lock single writer
    UI               server-rendered, ~20 read-mostly screens
    providers        ContactOut (primary person enrichment), AI Ark
                     (fallback), Reoon (deep verification for accept_all),
                     Blitz (declared, NOT operational), EmailBison (email),
                     HeyReach (LinkedIn), Apify (scraping), Slack (alerts)
    lanes            revive, cold, domains
    lifecycle        queued -> enriched -> verified -> drafted -> approved
                     -> pushed, with dropped/held where applicable

`work/` is gitignored and is the production ledger. Git is not the database.

### TARGET lifecycle

The streaming lifecycle `STREAMING-ARCHITECTURE.md` already specifies:

    RECEIVED -> NORMALIZED -> FREE_RESEARCH -> PRELIMINARY_ICP -> QUALIFIED
      -> PERSON_DISCOVERY -> ENRICHMENT -> VERIFICATION -> CAMPAIGN_READY
      -> APPROVAL -> LIVE_ELIGIBLE

This is a rename and a refinement of the current lifecycle, not a different
machine. The migration question is whether the current states map onto it
without losing a distinction - answered in Phase 1's exit criteria.

---

## 2. NON-NEGOTIABLE: WHAT INFRASTRUCTURE WORK MAY NOT COST

The current architecture is strong on decision quality. The next phase buys
throughput, and **it may not pay for throughput with any of these.** Each is
load-bearing today and each has an enforcement point in code, named so a
migration can be checked against it rather than promised at.

| # | Property | Enforced today by |
|---|---|---|
| 1 | No prospect-facing draft is pushable until it passes the gates | `lint.py`, `claims.py`, `quality.py`; `generate.store_step` |
| 2 | No email to an address that has not satisfied verification policy | `lint.sendable`, `eligibility.decide`, the double-verification readiness check |
| 3 | Factual claims traceable to evidence | `claims.py` against `rec["research"]`; `heyreachfactory.unsupported_claims` |
| 4 | Personalisation depth is licensed by evidence, not chosen | `ACCOUNT-INTELLIGENCE.md`; `research.for_prompt` / `evidence.select` |
| 5 | Cheap and free evidence before expensive provider calls | `enrich.spend()` waterfall; "company first, no paid person call before an ICP verdict" (`CLAUDE.md`) |
| 6 | A confirmed provider MISS licenses the next provider; an ERROR or TIMEOUT must not become a MISS | the provider-fallback semantics in `enrich.py` |
| 7 | HIGH / MEDIUM / LOW / STOP scheduling; optimise time-to-first-campaign-ready-account, not time-to-finish-the-file | `STREAMING-ARCHITECTURE.md` |
| 8 | Sender and campaign capacity can throttle upstream work | `senders.py`, `docs/SENDER-UTILISATION-2026-09-15.md` |
| 9 | Approval belongs to exact content | `approval.fingerprint`, `campaigns.material`, `providerwrites._require_approved_words` |
| 10 | Historical contact/account/channel state is part of eligibility | `collision.check_account`, `ENGAGEMENT-HYGIENE.md` |
| 11 | Workspace/client isolation survives every migration | every record carries `client`; `_plan` refuses a foreign record; `bison.require_workspace` |
| 12 | Production actions attributable and auditable | `actionledger`, `roles.py`, `PRODUCTION-AUTH.md` |
| 13 | Unknown provider state is never permission to send | `heyreach.campaign_cannot_send`, `providerwrites.CONDITIONAL`, `WriteUnverified` |

**The migration test for each is behavioural, not architectural.** "Postgres
preserves tenancy" is a claim; "a record belonging to client A cannot be
returned by a query scoped to client B, and a test proves the refusal" is a
check. Phase 1's exit criteria are written that way.

### The property most at risk, named

**Fail-closed behaviour is the one a throughput migration erodes first**, and
not by anybody deciding to erode it. A worker pool that retries, a queue that
redelivers, and a job that is re-run after a crash all create a pressure
toward "assume the previous attempt did nothing" - and the one thing this
system must never assume is that an unconfirmed provider write did nothing.
`WriteUnverified` exists to say *it may have happened and we cannot prove
what*. At-least-once delivery must not be allowed to turn that into a retry.

---

## 3. WHY THE NEXT PHASE EXISTS

The current JSONL architecture produces, structurally:

    one primary writer
    limited parallel mutation
    awkward worker coordination
    difficult horizontal scaling
    fragile operational recovery
    unnecessary coupling between compute and state

`PERFORMANCE-READINESS.md` measured the consequence and `DATABASE-MIGRATION.md`
named the trigger. Neither is a throughput complaint: the pipeline walks 5,000
records in eleven seconds. The constraint is **concurrent mutation**, and it
is the only one that matters.

The objective is not records per second. It is:

    HIGH THROUGHPUT
      + HIGH EVIDENCE QUALITY
      + CONTROLLED PROVIDER SPEND
      + SAFE LIVE EXECUTION
      + CONTINUOUS LEARNING

---

## 4. MIGRATION ORDER AND DEPENDENCIES

    Phase 1  PostgreSQL ....................... depends on nothing
    Phase 2  Production runtime / VPS ......... depends on 1
    Phase 3  Inbound event loop ............... depends on 1 (idempotent
                                                event store); 2 for webhooks
    Phase 4  Self-hosted research layer ....... depends on 1 (account-level
                                                research cache); independent
                                                of 2 and 3
    Phase 5  Async / batch AI pipeline ........ depends on 1 (worker-safe
                                                claiming); benefits from 4
    Phase 6  External signal layer ............ depends on 4 (the crawl and
                                                extraction substrate) and on
                                                1 (signal persistence)
    Phase 7  Real authentication .............. depends on 2; REQUIRED before
                                                any broad exposure
    Phase 8  Provider hardening ............... depends on 3 for
                                                reconciliation; the rest is
                                                independent and some of it
                                                could be done today

**Phase 1 is first because everything after it needs concurrency that files
cannot give.** Phases 4 and 8 contain work that does not, and that is where to
look if the sprint needs an early independent win.

---

## 5. THE PHASES

Each phase states its exit criteria as things that can be checked, its
rollback, and its risks. A phase without a passing exit criterion is not done,
whatever has been built.

### PHASE 1 - POSTGRESQL

`DATABASE-MIGRATION.md` is the design. It already carries the entities, the
constraints, optimistic locking, the migration approach and - importantly -
what NOT to migrate. This section adds only what that document does not.

**What it adds:** worker-safe claiming. `SELECT ... FOR UPDATE SKIP LOCKED`
or equivalent, idempotent jobs keyed on the stable identifiers that already
exist (`push_id`, `provider_event_id`, `evidence_id`, the Slack interaction
id), retry semantics, stale-job recovery, and **exactly-once business
semantics even where delivery is at-least-once**.

That last one is the phase's real content. See §2's note on fail-closed: the
job runner must be able to distinguish "this job did not run" from "this job
ran and we did not see the result", and must refuse the second rather than
retrying it.

**Do not throw away JSONL immediately.** Compatibility layer, rollback path,
deterministic migration verification.

**Exit criteria**

1. Two workers enrich disjoint halves of one batch concurrently, and a test
   proves neither lost the other's writes. This is the trigger condition; if
   it does not pass, the phase bought nothing.
2. Every state in the current lifecycle maps onto the TARGET lifecycle with
   no distinction lost, demonstrated by round-tripping the real estate.
3. A full export from Postgres and a full import back is byte-identical on
   the fields `campaigns.material` fingerprints. If the fingerprint moves,
   every approval in the system silently invalidates.
4. A cross-tenant query returns nothing, proven by a test that asks for
   client A's records with client B's scope.
5. `refuse_evidence_loss` and `refuse_history_loss` have equivalents that run
   on every write path, and a deliberate violation is refused.
6. An interrupted migration leaves a readable system on either side.

**Rollback:** JSONL stays authoritative until exit criterion 3 passes on the
real estate twice, a week apart. Rollback is "stop reading Postgres", not
"restore a backup".

**Risks:** the fingerprint risk in criterion 3 is the serious one - a field
reordered or a null normalised differently moves every campaign fingerprint
and invalidates every approval at once. Bulk re-approval would be the worst
possible remediation, because approval is the gate that means a person read
the words.

### PHASE 2 - PRODUCTION RUNTIME / VPS

`DEPLOYMENT-PLAN.md` is the design, including platform, secrets, domain,
health checks, rollback and backups.

    Internet -> Caddy/TLS -> web (1..n) -> worker (1..n)
                          -> scheduler (exactly one logical scheduler)
                          -> PostgreSQL

**Never expose Python `http.server` to the public internet.**

**Keep the server-rendered UI.** It is not a placeholder. ~20 read-mostly
screens is exactly the shape server rendering is good at, and a rewrite would
spend the sprint on the part of the system that is not the bottleneck. See
ADR-2.

**Exit criteria**

1. Web and worker scale independently; killing a worker mid-job loses no
   work and duplicates no provider action.
2. Exactly one scheduler runs, and a second instance starting refuses rather
   than double-scheduling.
3. TLS terminated at the proxy; no direct app port reachable from outside.
4. Rollback exercised, not just documented - a deploy rolled back on a
   staging estate with no state loss.
5. Backups restored into a scratch environment and verified, at least once.

**Rollback:** local execution stays working throughout. If the VPS is
unavailable, the operator can run the pipeline locally the way it runs today.

**Risks:** secrets reaching the VPS. `CLAUDE.md`'s rule is absolute - never
commit a credential, store the variable NAME - and a deployment is where that
rule is most often broken by convenience.

### PHASE 3 - INBOUND EVENT LOOP

Real outcome ingestion, EmailBison and HeyReach first. Webhook where
reliable, bounded polling and reconciliation where not.

Normalise to internal events:

    EMAIL_SENT, EMAIL_DELIVERED, EMAIL_BOUNCED, EMAIL_REPLY,
    POSITIVE_REPLY, NEGATIVE_REPLY, UNSUBSCRIBE
    LINKEDIN_INVITE_SENT, LINKEDIN_CONNECTED, LINKEDIN_MESSAGE_SENT,
    LINKEDIN_REPLY, LINKEDIN_POSITIVE_REPLY

Idempotency on `provider_event_id` or equivalent stable provider identity.

**What is already known and must not be re-derived.**
`docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` established where EmailBison's
proof ends: a reply carries `campaign_id` and `lead_id` as FACT; the step is a
RECONSTRUCTION through `reply.scheduled_email_id -> sequence_step_id`; and
variant identity IS recoverable and durable, because a scheduled email carries
the VARIANT step's id rather than the parent's. The events route's
`sequence_step_variant` index expires after 10 days; the step id does not.
Phase 3 implements against those boundaries and does not relitigate them.

**Exit criteria**

1. A replayed webhook changes nothing the first delivery did not, proven by
   sending the same `provider_event_id` twice.
2. Every normalised event names which of PROVIDER FACT / RESONATE
   RECONSTRUCTION / ATTRIBUTION HYPOTHESIS it is, and the distinction is
   queryable rather than a comment.
3. An UNKNOWN reply is never counted as negative, proven by a test.
4. A reply stops the sequence for that contact through the existing
   `eligibility` path, not a new one.
5. Outcome ingestion runs unattended for a week without an operator
   reconciling it by hand.

**Rollback:** ingestion is additive. Turning it off returns the system to
manual reconciliation, which is where it is today.

**Risks:** a webhook is an unauthenticated inbound path unless it is signed.
Verify signatures before parsing, and treat the body as untrusted data.

### PHASE 4 - SELF-HOSTED FREE RESEARCH / CRAWLER LAYER

**The crawler that exists must be the baseline, not an afterthought.**
`src/webfetch.py` is free, stdlib-only, and already runs as the free leg
before the paid Apify crawl - real crawls of real pages. Any candidate is
measured against it, not against nothing.

Candidates to evaluate: crawl4ai, a Playwright-based crawler, or another
evidence-backed open-source crawler if technically superior. **Benchmark
against our own estate**, not a README. Choosing one because it is fashionable
is the failure mode this phase is most exposed to.

Pages worth retrieving when useful: homepage, `/about`, `/services`,
`/solutions`, `/products`, `/customers`, `/case-studies`, `/blog` or `/news`,
`/careers` or `/jobs`.

Research must be per account, cacheable, timestamped, source-attributed,
reusable across contacts, and stale-aware. Extract structured evidence;
**do not dump whole websites into LLM context.**

**What is already known.** Two measurements from 2026-09-15 bound this phase's
value and it should be planned against them rather than around them:

- 236 of 695 research rows are unusable page furniture, and 47 records' first
  three rows are all junk (`docs/RESEARCH-QUALITY-IMPACT-2026-09-15.md`).
- **A draft references an evidence fact 7.3% of the time when the evidence is
  good, and 0.0% when it is junk.** That 7.3% is the ceiling on what better
  evidence buys through the current prompt. The constraint is the prompt's use
  of evidence, not the evidence's quality.

So a crawler that returns better pages is a correctness improvement with a
small measured envelope, and **the prompt work is the larger lever.** Plan
both or neither.

TTL semantics landed on 2026-09-15 (`research.ttl_for`, `stale_evidence`):
short-lived fields - team, careers, hiring, news, launches - at 3 days,
long-lived positioning at 30. Phase 4 inherits that rather than inventing it.

Apify stays where it earns its cost. **The goal is not "remove Apify".**

**Exit criteria**

1. Crawling one company once serves every contact at that company, proven by
   a cache-hit count on a real multi-contact account.
2. Every extracted fact carries source URL, retrieved-at and a quality
   classification, and `evidence.select` ranks on them.
3. Measured against `webfetch.py` on the real estate: pages reached, usable
   facts per account, cost per account. A candidate that does not beat the
   stdlib baseline on usable facts per account is not adopted.
4. Crawl volume per account drops relative to today, measured.
5. No self-certifying loop: a model-generated sentence can never become
   evidence for a claims check. This is checked by a test, because it is the
   one failure here that would be invisible and catastrophic.

**Rollback:** the free leg is already optional. Disable the new worker and
`webfetch.py` plus Apify is what runs today.

**Risks:** robots, rate limits and being a good citizen of other people's
websites. A self-hosted crawler removes the vendor who was absorbing that
responsibility.

### PHASE 5 - ASYNC / BATCH AI PIPELINE

Bounded concurrency against provider rate limits, model rate limits, sender
capacity, available evidence and downstream queue pressure.

**Model routing, not one model for everything:**

    rules / deterministic Python
      -> small or local model
        -> cheap API model
          -> strong model for difficult synthesis and reasoning

Evaluate local Qwen workers, API execution, and the Anthropic Batch API where
it is economically appropriate. Claude increasingly orchestrates, reviews and
does hard reasoning rather than processing every account personally - which is
already how the worker pool is run.

**Exit criteria**

1. A deterministic classification that currently calls a model is served by
   rules or a small model, with equal or better measured accuracy on a held-out
   set.
2. Cost per campaign-ready account is measured before and after, and the
   comparison is published.
3. Concurrency is bounded by the real limit, and hitting a provider rate limit
   slows the pipeline rather than failing records.
4. A batch job that dies mid-run loses at most the work in flight - the
   property `store.transaction` gives today, preserved.

**Rollback:** routing is configuration. Route everything to the strong model
and the system behaves as it does today, more expensively.

**Risks:** a cheaper model that is quietly worse on the cases that matter.
Accuracy must be measured on the hard cases, not the average.

### PHASE 6 - EXTERNAL SIGNAL LAYER

Job postings, funding, growth, leadership changes, new offices, product
launches, technology adoption and removal, website changes, news, new customer
evidence, hiring by department, intent and change events.

Every signal carries: source, `observed_at`, confidence, account, type, raw
evidence, normalised value, and expiry/staleness semantics.

**A signal is evidence for targeting and personalisation. It is not
automatically permission to make a claim.** That separation is the same one
`ACCOUNT-INTELLIGENCE.md` already draws between a priority score and a licence
to write, and it is the whole reason this phase is not simply "add more data".

**Exit criteria**

1. A signal can raise an account's priority without licensing any sentence
   about it, proven by a test where the claims gate refuses the claim while
   the account still ranks.
2. Every signal type has a stated shelf life and the TTL layer enforces it.
3. A stale signal is refused for personalisation, not silently used.
4. Signals are per account and reused across contacts.

**Rollback:** signals are additive to ranking. Turning them off returns
current ICP behaviour.

**Risks:** signal-driven copy is where unsupported claims come from. The
claims gate must see the signal's evidence, not the signal's label.

### PHASE 7 - REAL AUTHENTICATION

Replace the development sign-in with a real identity provider before any broad
exposure. `PRODUCTION-AUTH.md` already draws the line this must preserve: an
identity provider proves the address, the membership table decides what it may
do, **and neither is allowed to learn the other's job.**

Preserve workspace isolation, RBAC and audit attribution.

**Do not invent password or auth cryptography.**

**Exit criteria**

1. An authenticated identity with no membership row can do nothing.
2. Every production action remains attributable to a real identity in
   `actionledger`.
3. RBAC decisions still come from the membership table, not from the token's
   claims.
4. Session revocation takes effect immediately.

**Rollback:** none once exposed. This phase gates exposure rather than the
other way round, which is why it is listed as REQUIRED before broad access.

**Risks:** the migration itself is where an identity is silently trusted for
an authorisation decision it was never meant to make.

### PHASE 8 - PROVIDER HARDENING

- an operational Blitz path (declared today, not operational)
- HeyReach provider-side prior-contact history checks
- EmailBison historical interaction checks
- sender and inbox capacity modelling
- provider reconciliation, retries, rate-limit handling
- dead-letter and error review
- phone and `personal_email` modelling
- per-person provider-cost attribution

**Some of this is available today and does not need a phase.**
`docs/SENDER-UTILISATION-2026-09-15.md` already measured the LinkedIn seat
estate and found `LINKEDIN_ASSIGN_SENDER`'s "no documented route" note stale -
both routes exist and are implemented. Provider reconciliation has
`scripts/provider_truth.py`.

**Exit criteria**

1. Blitz either works on a real lookup or is removed from the declared
   provider list. A declared provider that has never answered is worse than an
   absent one.
2. A provider error is never recorded as a MISS, proven by a test that
   injects a timeout and asserts the fallback does NOT fire.
3. Per-person cost attribution reconciles to the spend ledger total.
4. Every provider write has a dead-letter path a person can review.

**Rollback:** per item; none of this is a one-way door.

**Risks:** §2 property 6 is the one to watch. An error becoming a MISS licenses
the next provider and spends money on a false premise.

---

## 6. THROUGHPUT DESIGN PRINCIPLE

An anecdotal community benchmark reports ~2,000 leads/minute on a VPS with
Postgres, a React frontend, LLM enrichment and free multi-page scraping.

**Treat it as anecdote, not requirement.** Do not optimise Resonate OS to win
a synthetic records/minute benchmark. The intended advantage is *their
infrastructure throughput plus our quality, safety, evidence and learning
system* - and the second half is what a records/minute number cannot see.

Measure, at minimum:

    accounts received/min          accounts free-researched/min
    accounts qualified/min         contacts discovered/min
    verified contacts/min          campaign-ready contacts/min
    provider credits/account       LLM cost/account
    research cache hit rate        time-to-first-campaign-ready account
    campaign deployment throughput sender utilisation
    reply rate                     positive reply rate
    meeting conversion             false-positive ICP rate
    collision prevention rate      provider error rate

**Time-to-first-campaign-ready-account is the headline**, because it is the
one that distinguishes a streaming system from a batch one. Today's measured
figure should be recorded before Phase 1 starts, or there is nothing to
compare against.

---

## 7. STANDING ARCHITECTURAL PRINCIPLES

### Account-centric research

Research belongs to the ACCOUNT. Do not repeat expensive company research per
employee.

    acme.com -> crawl once -> structured evidence -> signals -> ICP decision
             -> personas -> multiple contacts -> individual message synthesis

Reduces crawl volume, LLM tokens, provider credits and latency at once. This
is already the shape `research.for_prompt` and `evidence.select` assume; Phase
4 makes the cache real.

### Continuous streaming

Not "upload 30,000, process all, then start campaigns". Domain 1 reaches
production while domains 2..30,000 are still in the pipeline. This is
`STREAMING-ARCHITECTURE.md`'s decision and it is already standing policy.

### Closed-loop learning

    ACCOUNT -> RESEARCH -> SIGNALS -> ICP -> PERSONA -> CONTACT -> CHANNEL
      -> ANGLE -> COPY/VARIANT -> CAMPAIGN -> SEND -> OUTCOME -> ATTRIBUTION
      -> LEARNING -> NEXT DECISION

Learning dimensions: client, industry, persona, seniority, company size,
signal, channel, angle, opening, CTA, cadence, sender, message length,
personalisation depth, evidence type, time and day.

**Do not confuse correlation with causation.** PROVIDER FACT, RESONATE
RECONSTRUCTION and ATTRIBUTION HYPOTHESIS stay distinguishable - the boundary
is already drawn for EmailBison in
`docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md`.

### Scale target

30 clients x ~5,000 domains each should be operationally reasonable without
redesigning the core again. That is **not** processing 150,000 at once. It
needs fair scheduling between clients, per-client budgets, provider limits,
sender capacity, priority, backpressure, worker concurrency, retry queues and
observability.

**A large client must not starve a small one.** That is a scheduling
requirement with a test, not an aspiration.

### Cost principle

The system should know when NOT to spend money:

    internal evidence -> cached research -> free website research
      -> deterministic qualification -> cheap/local AI -> person discovery
      -> paid enrichment -> verification -> expensive AI synthesis
      -> provider send

**Never enrich 5,000 people merely because 5,000 people exist.** This is
`CLAUDE.md`'s "company first" rule generalised: rejected, review and unknown
all mean zero person credits.

---

## 8. ADRs

Short records of why, so the sprint does not relitigate them.

### ADR-1: PostgreSQL before horizontal workers

**Decision.** Migrate state before scaling compute.

**Why.** Horizontal workers against a whole-file-rewrite store do not scale -
they corrupt. `DATABASE-MIGRATION.md` names the trigger as "when two processes
need to write at once", which is precisely the condition adding workers
creates. Doing compute first would mean building coordination machinery around
a store that cannot support it, then throwing that machinery away.

**Rejected alternative.** File locking with finer granularity - per-record
files, or a lock per shard. It moves the problem rather than solving it, and
it forfeits the transactional guarantees `store.transaction` currently gives
for free within one process.

### ADR-2: The server-rendered UI stays

**Decision.** Do not rewrite the frontend. Specifically, do not introduce
React during this roadmap.

**Why.** ~20 read-mostly screens is the shape server rendering handles well.
The UI is not the bottleneck; concurrent mutation is. A rewrite would consume
the sprint that Phase 1 needs and deliver no throughput. "Another system uses
React" is not a requirement.

**Revisit when.** A measured requirement the current UI cannot meet - real-time
collaborative editing, or an interaction latency budget it demonstrably
misses. The UI evolves independently of backend scalability.

### ADR-3: Account-centric research

**Decision.** Research is keyed to the account, cached, and reused across
contacts.

**Why.** A company's positioning does not differ per employee. Crawling per
prospect multiplies cost by contacts-per-account for identical output - at the
estate's measured 2.5 contacts per domain, that is 2.5x the crawl bill for no
additional information.

**Rejected alternative.** Per-contact research. The only per-contact facts are
the person's own, and those come from enrichment providers rather than the
company website.

### ADR-4: Self-hosted crawler with paid fallback

**Decision.** Self-host cheap repeatable research. Keep Apify where it earns
its cost.

**Why.** Most of what is needed is fetching a handful of public pages, which
`webfetch.py` already does for free. Paid scraping earns its place on the
pages that defeat a simple fetch - JavaScript rendering, anti-bot, scale
bursts. "Remove Apify at all costs" would trade money for reliability in the
wrong direction.

**Rejected alternative.** All-Apify, for operational simplicity. It prices
routine research at a paid rate forever.

### ADR-5: Closed-loop outcome ingestion

**Decision.** Ingest provider outcomes as normalised, idempotent events keyed
on provider event identity.

**Why.** Without it the learning loop is open and every conclusion is
reconstructed by hand. Provider event ids give idempotency for free, which is
what makes at-least-once delivery safe.

**Rejected alternative.** Periodic full reconciliation only. It is O(estate)
per cycle, it loses the ordering that attribution needs, and it cannot
distinguish "not yet seen" from "did not happen".

### ADR-6: Model routing instead of Claude-for-everything

**Decision.** Route by task difficulty. Deterministic work gets rules; simple
classification gets a small or cheap model; hard synthesis gets the strong
model.

**Why.** Using the most capable model for a deterministic classification is
paying reasoning prices for a lookup. Cost per campaign-ready account is a
headline metric, and this is the largest lever on it.

**Rejected alternative.** One model everywhere, for consistency. Consistency
is worth something, but not the multiple.

**Guard.** Accuracy is measured on the hard cases before a route is demoted, or
this ADR becomes a quality regression with a cost saving attached.

---

## 9. NON-GOALS

Explicitly out of scope for this roadmap:

- a records/minute benchmark score
- a React or SPA frontend
- removing Apify entirely
- processing 150,000 domains simultaneously
- custom authentication cryptography
- replacing the gate architecture with generic LLM enrichment
- refactoring working production code for elegance
- **any of the above starting today**

---

## 10. WHAT HAPPENS BEFORE ANY OF THIS

Current priority, unchanged: **get Productive live and begin real learning.**

Do not migrate to PostgreSQL today. Do not deploy a VPS today. Do not install
crawl4ai today. Do not rewrite the web UI today. Do not introduce React today.

Finish the current Productive execution path on the current architecture.
This document exists so the infrastructure reasoning can be picked up later
without being rediscovered.
