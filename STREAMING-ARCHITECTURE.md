# Streaming architecture

The standing product principle for how Resonate OS processes a large TAM.
Recorded 2026-09-08 as a decision, not as a plan for tonight. Nothing here
outranks the rules in `CLAUDE.md` or `PLAYBOOK.md`: streaming is a scheduling
model, and no part of it licenses a live action that approval, suppression,
tenancy, verification or the no-live-send restriction would otherwise refuse.

## The decision

A 30,000 domain upload must produce value continuously. The first excellent
accounts must be able to reach campaign readiness while the long tail is
still being researched.

This shape is **rejected**:

    upload 30,000 -> process all -> enrich all -> wait -> launch

This shape is **required**:

    upload 30,000
      batch A: normalise -> free evidence -> preliminary ICP -> strongest
               accounts continue -> people -> ContactOut -> Blitz ->
               verification -> campaign -> approval -> launch when safe
      while batch B enriches, C qualifies, D does free research, E waits

## The unit of execution is the account, never the file

The uploaded file is an input source. It must not become the unit of work.
Each account progresses independently through canonical states, and accounts
are not synchronised with each other without a reason:

    RECEIVED -> NORMALIZED -> FREE_RESEARCH -> PRELIMINARY_ICP
      -> QUALIFIED -> PERSON_DISCOVERY -> ENRICHMENT -> VERIFICATION
      -> CAMPAIGN_READY -> APPROVAL -> LIVE_ELIGIBLE

with real branches, not just the happy path:

    PRELIMINARY_ICP -> CLEAR_NON_ICP -> STOP
    PRELIMINARY_ICP -> BORDERLINE -> WAIT_FOR_RESEARCH
    QUALIFIED -> NEEDS_MORE_EVIDENCE

Later: person and campaign eligibility become units in their own right.

## Micro-batches, sized by what the estate can bear

Batch size is configurable and derived, never a global constant. No hardcoded
100 or 500. The scheduler weighs provider concurrency and rate limits,
workspace credit budgets, daily spend, queue pressure, state throughput,
research and verification cost, campaign capacity and sender capacity.

## Priority, not FIFO

The objective is **time to first campaign-ready account**, not time to finish
the file.

| Band | Shape |
| --- | --- |
| HIGH | strong ICP, high confidence, decision maker likely reachable, low remaining cost, good campaign fit |
| MEDIUM | reasonable ICP, needs one more evidence source |
| LOW | weak fit, high uncertainty, expensive to resolve |
| STOP | clear non-ICP, suppressed, invalid domain, explicit exclusion |

A high-priority account may overtake an earlier low-priority one.

## Progressive spend

Paid resource consumption becomes more selective deeper in the funnel, never
less. The waterfall order is unchanged and ContactOut remains first:

    domain -> free/cheap evidence -> ICP likelihood
    only if worth pursuing        -> person discovery
    selected person               -> ContactOut
    confirmed ContactOut miss     -> Blitz
    confirmed Blitz miss          -> AI Ark / configured fallback
    candidate email               -> verification

A confirmed miss is what licenses the next provider. An error, a timeout or an
unknown is not a miss, and must not buy a fallback call.

## Continuous launch, under backpressure

Ten campaign-ready accounts do not wait for four thousand still in research.
They proceed to approval, canary and launch subject to every canonical safety
gate.

But readiness must not outrun what the sending estate can safely consume.
Backpressure inputs: email and LinkedIn sender capacity, campaign capacity,
daily limits, warmup and sender health, account fatigue, cadence spacing,
workspace policy, approval capacity. When sending is saturated, ready accounts
wait in a READY queue **and expensive upstream enrichment slows down** - buying
people for a queue nobody can send to is the most expensive way to be idle.

## Personalisation depth

More personalisation is not automatically better. Specificity must be
evidence-backed, and depth is a consequence of evidence quality rather than a
setting:

| Level | Licensed by |
| --- | --- |
| 1 | domain + person/title |
| 2 | industry + company size + persona |
| 3 | company facts, services, product lines |
| 4 | strong account-specific business signal |
| 5 | person-specific relevant signal |

Knowing only "marketing services, ~50 people, COO" licenses safe persona copy
and nothing more. Growth, hiring, margin pressure, office locations, tooling
and internal initiatives are not inferable from that and must not appear.
Every personalised factual claim traces to evidence, which is the existing
claim-licensing rule applied to depth.

A depth score should be explainable, and computed from source quality,
freshness, diversity, useful fact count, signal confidence, person-specific
evidence, contradictions and unknowns. Three pages of one website are one
source, not three. `published_at` is never derived from `retrieved_at`. Volume
of weak website copy is not confidence.

## Campaign archetypes

Neither one generic campaign for 30,000 accounts nor 10,000 independently
written ones. Archetypes derived from vertical x persona x company size x
pain/angle x signal class x personalisation depth, with per-account rendering
where evidence supports it. Controlled personalisation at scale.

Construction stays separable - strategy/archetype, persona angle, account
evidence, person evidence, rendering - so the system can answer why this
person, why this angle, why this claim, why this campaign, and which evidence
was used. One opaque prompt cannot answer those.

## Waves, feedback and learning

Progressive release, not a fixed wave schedule. Campaign results may influence
later prioritisation and campaign selection: reply quality, positive and
negative rates, persona, angle and vertical performance, sender health, bounce
rate.

**Performance never edits safety.** "Catch-all got replies, therefore
catch-all is safe" is exactly the inference that is forbidden. Safety and
performance are separate layers; learning is explainable, reversible, and
never rewrites historical evidence.

Optimise toward cost per qualified account, per campaign-ready person, per
verified email, per positive reply, per meeting - not records enriched or
provider calls completed.

## Resume

Every stage is resumable. A restart does not begin at domain 1. Accounts that
reached QUALIFIED, ENRICHED, VERIFIED or CAMPAIGN_READY stay there unless
evidence or policy invalidates them, and purchase history prevents re-spend.

## Observability

Stage-level counts an operator can read at a glance: uploaded, valid unique
domains, then per stage waiting / processing / complete, ICP split across
strong, borderline, clear non-ICP and unresolved, provider hit counts by
waterfall position, verification, campaign-ready, live, and spend today.

---

## Where this repository actually stands

Verified by reading the code on 2026-09-08, not assumed.

**The rejected shape is what `src/run.py` does today.** `run()` calls
`stage_enrich(targets)`, then `stage_qualify(targets)`, then
`stage_personas(targets)`, then `stage_generate(targets)` - each a complete
pass over every record before the next begins. That is four global barriers in
one function, and it is the file-driven, stage-major model this document
rejects.

**The canonical per-account state already exists, and that is the good news.**
Every record carries `rec["stages"][name]["status"]`, and `run.needs(rec,
stage)` already decides per record whether a stage applies.
`qualify.needs_work` goes further and re-runs a verdict when a fingerprint of
the facts it was derived from has changed, which is an evidence-driven
transition rather than a positional one. So the streaming model needs a
scheduler that reads state per account - not a new data model, and not a
rewrite of the stages themselves. The barrier is the loop, not the state.

**Two things would make the future architecture expensive or unsafe, and both
are recorded in `PRODUCT-GAPS.md` rather than fixed here:**

1. `src/run.py:292` persists with a single `store.save(recs)` after all four
   per-record stages, and `enrich.run` does the same at `src/enrich.py:723`.
   Progress is therefore not durable per account. A crash at record 9,000 of
   30,000 loses every stage mark from that pass, and because the evidence is
   not written either, the paid calls are re-spent on resume. This contradicts
   the resume requirement directly and gets worse in exact proportion to TAM
   size.

2. Selection is positional. `run()` slices `targets[:limit]` in queue order,
   so there is no priority band and no way for a strong account to overtake a
   weak earlier one. `limit` is a truncation, not a scheduler.

**Compatible as-is:** the waterfall and `enrich.spend()` ledger already make
progressive spend auditable and already require a confirmed miss before a
fallback; approval, suppression, DNC, reply protection and tenancy are all
per-account gates already, so streaming does not weaken them.

## What must be proven before this is called done

Offline and synthetic, no live action:

- batch 1 reaches campaign-ready while later batches are still pending
- a slow account does not block an unrelated fast one
- a provider failure on one account does not stop its batch
- a provider rate limit creates backpressure, not a global failure
- campaign capacity saturation pauses expensive upstream progression
- resume repeats no completed paid call
- a high-priority account advances ahead of an earlier low-priority one
- ready accounts never wait for the whole TAM
- no live action bypasses approval or any safety gate because streaming is on

## Scope

This is the design constraint for the next scale phase. It does not reorder
the current critical path, which remains: overnight safety work, Blitz,
HeyReach correctness, final validation, Productive one-person canary. Current
work makes decisions compatible with this model and adds no new batch-wide
coupling; where a change would make this architecture impossible or
dangerously expensive, the generic issue gets fixed or documented rather than
worked around.
