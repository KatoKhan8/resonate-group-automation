# Moving off files, when the time comes

Not now. This is the design to build against when the file store stops being
enough, and the point at which that happens is specific rather than vague:
**when two processes need to write at once.**

## Why files are still right today

`work/queue.jsonl` is one JSON object per record, rewritten whole under an
advisory lock. That is crash-safe (temp file plus atomic rename), trivially
inspectable, diffable, and fast enough — 5,000 records is about 35 MB and the
whole pipeline walks it in eleven seconds. Nothing about the current
single-operator workflow is held back by it.

What it cannot do is let two workers enrich different halves of a batch
concurrently, because a write is a whole-file write. That is the constraint,
and it is the only one that matters.

## What makes the migration cheap

Three properties, all already true, and worth protecting deliberately:

1. **Every record is already a self-contained JSON object.** The rows below are
   mostly a normalisation of fields that exist.
2. **Every expensive operation already has a stable idempotency key** —
   `push_id`, `provider_event_id`, `evidence_id`, the Slack interaction id, the
   campaign fingerprint. Those become unique constraints, and the moment they
   are constraints the database enforces what the code currently promises.
3. **Every stage is already resumable.** Checkpoints, cursors and
   `research_state` exist because the file store forced them; a queue-based
   worker model needs exactly the same things.

## Entities

Types are PostgreSQL. `id` columns are surrogate keys; the natural keys are
named as unique constraints, which is where the safety lives.

### clients
```
id              bigserial primary key
slug            text not null unique          -- "productive", "demo"
name            text not null
config          jsonb not null                -- the YAML as loaded
created_at      timestamptz not null default now()
```

### batches
```
id              bigserial primary key
client_id       bigint not null references clients(id)
source          text not null                 -- filename or paste
lane            text not null                 -- revive | cold | domains
created_at      timestamptz not null default now()
created_by      text
```

### companies
```
id              bigserial primary key
client_id       bigint not null references clients(id)
batch_id        bigint references batches(id)
record_key      text not null                 -- the current record id
domain          text not null
domain_norm     text not null                 -- www./mail. stripped
name            text
lane            text not null
state           text not null
drop_reason     text
paused_at       timestamptz
paused_reason   text
company_facts   jsonb not null default '{}'
version         integer not null default 1    -- optimistic locking
created_at      timestamptz not null default now()
updated_at      timestamptz not null default now()

unique (client_id, record_key)
index  (client_id, domain_norm)               -- collision detection
index  (client_id, state)
index  (batch_id)
```

`domain_norm` is indexed rather than computed on read because collision
detection at 5,000 records currently walks every record; an index turns that
into a lookup.

### contacts
```
id              bigserial primary key
company_id      bigint not null references companies(id) on delete restrict
contact_key     text not null
name            text
title           text
persona         text
angle           text
email           text
email_norm      text                          -- lower-cased
email_domain    text                          -- the ADDRESS's own domain
linkedin_url    text
linkedin_canon  text                          -- src/linkedin.canonical()
sendable        boolean not null default false
excluded        boolean not null default false
excluded_reason text
duplicate_of    bigint references contacts(id)
duplicate_scope text
duplicate_reason text
unsubscribed_at timestamptz
version         integer not null default 1

unique (company_id, contact_key)
index  (email_norm)                           -- identity lookup
index  (linkedin_canon)                       -- identity lookup
index  (email_domain)                         -- MX cache join
```

`on delete restrict`, not cascade. Nothing in this system deletes a contact,
and the database should refuse rather than make it easy.

### identities and provider_identities

The bridge that lets one person be recognised across providers, batches and
clients without merging anything automatically.

```
identities
id              bigserial primary key
kind            text not null                 -- email | linkedin | provider
value           text not null                 -- the normalised identifier
first_seen_at   timestamptz not null default now()
unique (kind, value)

contact_identities
contact_id      bigint not null references contacts(id)
identity_id     bigint not null references identities(id)
primary key (contact_id, identity_id)
index (identity_id)                           -- "who else is this person?"

provider_identities
id              bigserial primary key
contact_id      bigint not null references contacts(id)
provider        text not null                 -- contactout | heyreach | bison
external_id     text not null
unique (provider, external_id)
```

`unique (provider, external_id)` is the constraint that makes "the same
HeyReach lead twice" impossible rather than merely unlikely.

### evidence
```
id              bigserial primary key
evidence_id     text not null                 -- the content-derived id
company_id      bigint not null references companies(id)
contact_id      bigint references contacts(id)   -- null for company evidence
subject         text not null                 -- company | person
fact            text not null
source_type     text not null
source_url      text
provider        text not null
published_at    date
retrieved_at    timestamptz not null
freshness_bucket text not null
relevance_score numeric(4,3)
quality         text not null
unique (evidence_id)
index (company_id, quality)
```

### verification_results and mx_results
```
verification_results
id              bigserial primary key
contact_id      bigint not null references contacts(id)
provider        text not null                 -- contactout | deliverable | reoon
status          text not null
raw_status      text
checked_at      timestamptz not null
index (contact_id, checked_at desc)

mx_results
id              bigserial primary key
email_domain    text not null
mx_records      text[] not null
security_provider text
status          text not null
checked_at      timestamptz not null
unique (email_domain)                         -- domain-level cache, one row
```

`mx_results` is keyed by domain, not by contact. Fifty contacts at one company
share one row, which is what the JSON cache already does and what the index
makes explicit.

### cadence_steps
```
id              bigserial primary key
contact_id      bigint not null references contacts(id)
campaign_id     bigint references campaigns(id)
step_key        text not null                 -- day1, day3, ...
channel         text not null                 -- email | linkedin
day             integer not null
status          text not null                 -- src/stepstate.STATES
push_id         text                          -- record:contact:step:channel
prepared_at     timestamptz
pushed_at       timestamptz
skipped_reason  text
version         integer not null default 1

unique (contact_id, step_key)
unique (push_id)                              -- THE constraint that matters
index  (campaign_id, status)
index  (status, day)                          -- "what is due"
```

**`unique (push_id)`** is the single most valuable line in this document. It
turns "we are careful about not sending twice" into "sending twice is a
constraint violation", and it holds across processes, restarts and races that
no amount of application logic covers.

### drafts and approvals
```
drafts
id              bigserial primary key
cadence_step_id bigint not null references cadence_steps(id)
subject         text
body            text
note            text
generated       boolean not null
template        text
fingerprint     text not null                 -- src/approval.fingerprint()
created_at      timestamptz not null default now()
index (cadence_step_id, created_at desc)

draft_evidence
draft_id        bigint not null references drafts(id)
evidence_id     bigint not null references evidence(id)
primary key (draft_id, evidence_id)

approvals
id              bigserial primary key
scope           text not null                 -- draft | campaign
draft_id        bigint references drafts(id)
campaign_id     bigint references campaigns(id)
fingerprint     text not null
action          text not null                 -- approve | reject
actor           text not null
source          text not null                 -- slack | cli | web
interaction_id  text
created_at      timestamptz not null default now()
unique (interaction_id) where interaction_id is not null
index (campaign_id, created_at desc)
```

`unique (interaction_id)` is the durable half of the Slack replay defence that
currently lives in a per-process cache plus the campaign's own event list.

### campaigns
```
id              bigserial primary key
client_id       bigint not null references clients(id)
campaign_key    text not null
name            text not null
status          text not null                 -- src/campaigns.STATUSES
fingerprint     text
approved_fingerprint text
bison_campaign_id  text
heyreach_campaign_id text
daily_volume    jsonb not null default '{}'
senders         jsonb not null default '{}'
launch_state    text not null default 'not_launched'
version         integer not null default 1
unique (client_id, campaign_key)

campaign_companies
campaign_id     bigint not null references campaigns(id)
company_id      bigint not null references companies(id)
primary key (campaign_id, company_id)
index (company_id)                            -- "which campaigns is this in?"
```

`index (company_id)` answers the conflicting-campaign question — the same
person enrolled twice — which is currently a scan.

### events, replies, suppressions, provider_calls
```
events
id              bigserial primary key
company_id      bigint references companies(id)
contact_id      bigint references contacts(id)
campaign_id     bigint references campaigns(id)
type            text not null
provider        text
provider_event_id text
channel         text
payload         jsonb not null default '{}'   -- trimmed, never raw
occurred_at     timestamptz not null
unique (provider, provider_event_id) where provider_event_id is not null
index (company_id, occurred_at)
index (type, occurred_at)

replies
id              bigserial primary key
event_id        bigint not null references events(id)
contact_id      bigint not null references contacts(id)
classification  text not null
confidence      numeric(4,3)
classifier      text not null
excerpt         text                          -- trimmed; never the full body
index (contact_id, id)

suppressions
id              bigserial primary key
client_id       bigint references clients(id)  -- null = global
scope           text not null                  -- global | client | campaign
kind            text not null                  -- domain | email | linkedin
value           text not null
reason          text not null
created_at      timestamptz not null default now()
unique (client_id, kind, value)
index (kind, value)

provider_calls
id              bigserial primary key
provider        text not null
operation       text not null
company_id      bigint references companies(id)
credits         integer
status          text not null
occurred_at     timestamptz not null
index (provider, occurred_at)
```

`unique (provider, provider_event_id)` is what currently lives in
`events.record()`'s duplicate check. As a constraint it survives concurrency.

## Constraints worth stating separately

| Constraint | What it prevents |
|---|---|
| `unique (push_id)` on cadence_steps | the same logical send twice, across processes |
| `unique (provider, provider_event_id)` on events | a webhook replay changing state twice |
| `unique (interaction_id)` on approvals | a Slack retry approving twice |
| `unique (provider, external_id)` on provider_identities | one provider lead becoming two contacts |
| `unique (kind, value)` on identities | one mailbox becoming two identities |
| `unique (email_domain)` on mx_results | fifty lookups for one domain |
| `on delete restrict` throughout | anything being deleted rather than marked |

## Optimistic locking

`version integer` on companies, contacts, cadence_steps and campaigns. A writer
reads a version, writes with `where version = :seen`, and retries on zero rows
affected. This is the file lock's replacement, and it is per row rather than
per file — which is the entire point of the migration.

The campaign fingerprint is a natural fencing token on top of that: a worker
holding a stale fingerprint must not push, which is already enforced in
`eligibility.decide()` and would become a `where approved_fingerprint = :seen`
clause.

## Migration approach

1. Stand the schema up alongside the files. Write to both; read from files.
2. Backfill from `work/queue.jsonl` — every field above exists in it today.
3. Move reads over one module at a time, starting with reporting, which is
   read-only and where an index helps most.
4. Move writes last, and `push` last of all, because that is where a mistake
   sends something.
5. The files stay as an export format. They are a good one.

## What NOT to migrate

Checkpoints (`work/checkpoints.json`), the MX cache and the observability log
are all process-local, regenerable, and cheap. They can stay files indefinitely,
and making them rows adds contention for no benefit.


---

## Sender identity, assignment and touch history

Four objects were added after this document was first written, and all four
were shaped so the migration stays the cheap one this document describes.

### The tables they become

```
sender              (workspace_id, sender_id) PK
                    display_name, title, team, active, colleague_language

email_account       (workspace_id, account_id) PK
                    sender_id FK, provider, provider_account_id,
                    email_address, domain, active, daily_limit NULL, health

linkedin_account    (workspace_id, account_id) PK
                    sender_id FK, provider, provider_account_id,
                    profile_url, active, daily_limit NULL, health

sender_pairing      (workspace_id, email_sender_id, linkedin_sender_id,
                     campaign_id NULL)
```

Every one is keyed by `(workspace_id, ...)` rather than by a bare id. That is
not decoration: it is what makes row-level security a `WHERE workspace_id = ?`
and what stops a provider's own account id - which is *their* namespace, with
no cross-tenant uniqueness guarantee - from being usable as a global key.
`senderidentity.by_provider_account` already takes a workspace for the same
reason.

`daily_limit` is nullable and must stay nullable. A `NOT NULL DEFAULT 50`
would turn "nobody has told us" into "fifty a day", which is a number somebody
will plan against.

### Assignment lives on the contact, and that is deliberate

`contact["sender_assignment"]` is a per-contact fact, so in a relational model
it is a row keyed by `(workspace_id, record_id, contact_key, channel)` with the
sender, the account, the allocation reason and the roster digest. The `history`
array becomes `sender_reassignment`, append-only, one row per move with the
actor and the reason - the same shape the audit log already has.

Nothing about it depends on the file store. The first allocation is a pure
function of the contact key and the eligible pool; everything after it is a
read of one stored row.

### Touch history is derived, never stored twice

This is the one that would have been easy to get wrong. There is no
`touch_history` table, because the history is *derived from the event log* -
`push_marked`, `email_delivered`, `linkedin_connected` on the record's own
event stream. Materialising it would create a second answer to "did this
happen", and the second one is the one that goes stale.

In a relational model the events are already the append-only table this design
wants. `touch.history` becomes a query over it, and the only index that matters
is `(record_id, contact_key, step)`.

The one field that had to be *added* to the event is the sender:

```
    events.record(rec, PUSH_MARKED, ..., sender_id=..., account_id=...)
```

recorded at send time and never resolved from the current assignment. A schema
that left it out would make the cross-channel reference unattributable, and one
that resolved it by join at read time would let a reassignment rewrite history.
