# Performance readiness: 5,000-domain batches

Measured offline with fake providers, so every number below is *our* overhead.
Nothing here predicts how long a real run takes — that is dominated by provider
latency and rate limits, and this document deliberately does not invent either.

Reproduce with:

    python -m src.benchmark
    python -m src.costsim

## Measured

| domains | seconds | records/sec | selected contacts | email steps | LinkedIn steps |
|---:|---:|---:|---:|---:|---:|
| 10 | 0.03 | ~357 | 20 | 220 | 120 |
| 50 | 0.12 | ~420 | 100 | 1,100 | 600 |
| 100 | 0.24 | ~423 | 200 | 2,200 | 1,200 |
| 5,000 | 10.9 | ~457 | 10,000 | 110,000 | 60,000 |

Throughput is flat-to-improving as the batch grows, which is the point: the
pipeline is linear in records. A 5,000-domain batch costs about eleven seconds
of our own computation. Whatever makes a real run slow, it is not this.

## The quadratic term that was there, and is not now

`cadence.build()` asked "is any other record for this company paused?" by
scanning the whole queue — once per record. At 5,000 domains that is 25 million
checks and about 15 seconds; at 20,000 it is 400 million and minutes, for an
answer that does not change during a batch.

It now takes a `paused_set` computed once by the caller. `push.collect()` and
the benchmark do that; the 5,000-domain run dropped from 15.7s to 10.9s and
became genuinely linear. Anything else that builds many timelines in a loop
should pass it too — that is the one place in this codebase where forgetting
costs asymptotically rather than constantly.

## Where the time actually goes at 5,000

| stage | seconds | share |
|---|---:|---:|
| cadence | 10.4 | 95% |
| build records | 0.39 | 4% |
| select and plan | 0.08 | <1% |
| lint (200-record sample) | 0.05 | <1% |

Cadence dominates because it expands seven steps for every selected contact and
runs template rendering, lint and approval checks on each. It is linear, so it
is not urgent; if it ever needs to be faster, the expansion of *template* steps
is pure and cacheable per (client, persona, angle).

## What the architecture already does right

**Person research happens after selection, never before.** ContactOut returns
about six people per company; personas select two. Researching before selection
would waste two thirds of every person-level call — at 5,000 domains that is
roughly 20,000 wasted lookups. `personalization.selected_contacts()` is the
gate, and `tests/test_personalization.py` proves an excluded contact triggers
no research.

**Company research happens once per domain.** The careers page is the same page
for every contact there. `research_state.company_done` records it, so a re-run
reuses it rather than rediscovering that a company has nothing worth keeping.

**The free call gates the paid ones.** ContactOut's people-count costs nothing
and runs first; a domain with zero people never reaches decision-makers.

**Email credits are spent only on selected contacts.** This is the single
biggest cost lever in the system: revealing contact info for every profile
found rather than every profile used would roughly triple ContactOut spend.

## Concurrency

Every value below is configurable, and none of them is a provider's published
rate limit — this project has confirmed rate limits for exactly one provider and
will not invent the others.

| knob | where | default | note |
|---|---|---|---|
| `--cap` | `enrich.run` | client config | credit ceiling, checked before the first call |
| `max_pages` | `poller.run` | 5 | bounded polling |
| `MAX_ATTEMPTS` / `BACKOFF_SECONDS` | `poller` | 3 / (1,4) | finite, never a loop |
| `max_people_per_company` | client config | 2 | person-research fan-out |
| `max_sources_per_company` | client config | 10 | Apify page ceiling |
| `max_posts_per_person` | client config | 3 | downstream evidence ceiling |
| `daily_volume` | campaign | per client | send-side pacing |
| sender `daily_limit` | campaign | 50 | per-account ceiling |

**Confirmed rate limit:** HeyReach caps a page at 100 items (limit=200 answers
HTTP 400) and its published limit is 300 requests/minute. EmailBison's
`/api/replies` ignores `per_page` entirely and always returns 15, so pagination
there is the cursor's job alone. ContactOut, AI Ark, Reoon, Deliverable and
Apify rate limits are **not known** and are not guessed at anywhere in this
codebase.

## The real bottlenecks, in order

1. **Provider latency and rate limits**, none of which this benchmark measures.
   A 5,000-domain batch is ~5,000 free counts, ~5,000 company lookups and
   ~3,500 decision-maker calls. At one request per second that is over three
   hours regardless of how fast our code is.
2. **The single-writer queue.** `work/queue.jsonl` is rewritten whole under a
   lock. That is correct and crash-safe, and it is fine at 5,000 records
   (~10 MB), but it is a whole-file write: two processes cannot enrich
   different halves of a batch concurrently. This is the first thing that has
   to change for parallelism, not the algorithms.
3. **LLM generation**, at roughly two calls per selected contact — ~14,000 for
   a 5,000-domain batch. Concurrency here is the obvious win and is bounded by
   whatever the model provider allows.
4. **Verification**, one per selected contact plus fallbacks.

## What a worker queue would need

Not built, and not needed below a few thousand domains. When it is:

- records move to a store that supports row-level updates rather than a
  whole-file rewrite — the schema is already one JSON object per record, so
  this is a storage swap and not a redesign
- the checkpoint model already exists (`work/checkpoints.json`) and generalises
  to per-stage cursors
- every stage is already idempotent and keyed (`push_id`, `provider_event_id`,
  `evidence_id`), so re-running a partial batch is safe by construction — that
  is the property that makes a queue possible at all
- the campaign fingerprint gives a natural fencing token: a worker holding a
  stale fingerprint must not push

## Memory

A 5,000-record batch is held entirely in memory during a run. Each record with
two selected contacts, seven steps and one piece of evidence is roughly 6–8 KB
serialised, so ~35 MB of JSON plus Python object overhead. Comfortable on any
machine that runs the tests. It stops being comfortable somewhere around
50,000–100,000 records, which is the same point the single-writer queue has to
go.

`resource.getrusage` is unavailable on Windows, so the benchmark reports memory
only where the platform will say; it prints nothing rather than a guess.
