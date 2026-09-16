PRIORITY: P0
DEPENDS:

# TASK-208 - the free crawler goes before anything paid, and Grok goes fourth

## WHERE THIS SITS

`PROVIDER-ROUTING-POLICY.md` fixes the order:

    1 ContactOut   2 ContactOut cache   3 FREE crawler
    4 Grok / xAI   5 other paid providers   6 Claude

`src/waterfall.py` already puts ContactOut first per stage with reasoned
fallbacks. Two things in it do not match the new order, and one thing is
missing entirely.

**Apify is paid and sits where the free crawler should.** `apify-research`
appears in the `company_information` waterfall. `webfetch` is free. Under the
new order every free attempt precedes every paid one, so the free crawl belongs
ahead of Apify, ahead of Blitz, ahead of everything with a credit cost.

**Grok has no position at all.** `src/providers/xai.py` has 42 tests and, by
design, no caller - `grep -rn "xai" src/` returns only the adapter. Under this
policy it is layer 4: after ContactOut and after the free crawl, licensed only
by a ContactOut confirmed miss or an unsupported capability. TASK-166 measured
it at $0.20 a domain returning industry, offices, employees, specialties and
description with source URLs, and TASK-199 established that `company_facts` is
the field serving both the ICP gate and the copy gate - so Grok's output has a
real place, in fourth.

**The crawl is not cached at company level.** The policy is explicit: one crawl
per company, reused across its contacts. TASK-162 fixed the analogous waste in
what gets sent into prompts - 66.7% of the company context on a 3-contact
record was a duplicate of itself, at roughly 2.5 contacts per domain - and the
crawl itself needs the same treatment.

## THE QUESTION

1. **Establish the current order per stage**, from `waterfall.describe()`, with
   each step's cost and whether it is free. Then state, per stage, what changes
   under the new policy. A stage that already complies needs no change and
   saying so is a result.
2. **Move the free crawl ahead of every paid fallback** in the stages where it
   can answer the question. It needs an `accepted_reasons` entry like any
   fallback - a free call still needs a reason it is being made, and "the
   ContactOut record was missing X" is that reason.
3. **Give Grok its position.** A step in the stages where it can answer,
   marked `is_fallback: true`, with `requires_reason` naming the ContactOut
   confirmed-miss and capability-unavailable classes TASK-207 is introducing -
   and NOT an error or a timeout. Cost `$0.20`-shaped in whatever unit the
   stage uses; the adapter captures `cost_in_usd_ticks`, 10B ticks to the
   dollar.
4. **Wire the adapter to that step** - but do NOT make it callable in a
   production run yet. It must be reachable only through the waterfall, with
   the reason enforced, and it must be off unless explicitly enabled. Say how
   an operator turns it on, and make the default off. TASK-182 moved the
   adapter onto the Responses API; use it, do not call the endpoint directly.
5. **Cache the crawl at COMPANY level.** One crawl per company per pass,
   reused across every contact on that company, with provenance and
   `retrieved_at` preserved. Prove the counterfactual the way TASK-162 did:
   a test showing N contacts on one company produce ONE crawl, and a test
   showing a cleared cache produces N.

## THE TRAP

Reordering a waterfall changes what gets charged, and the wrong direction here
is expensive rather than unsafe: putting a paid step earlier costs money on
every record. Every change must move free EARLIER or paid LATER, never the
reverse. State the direction of each change explicitly in the deliverable.

Second trap: do not let Grok become reachable without a reason just because it
is now in the table. The whole point of its position is that it answers what
ContactOut confirmed it cannot. A step in the waterfall with a permissive
`requires_reason` is worse than no step, because it looks governed.

Third trap: a company-level cache that outlives a pass is a freshness bug.
TASK-162's cache is pass-scoped and cleared at the start of `run()` for exactly
that reason - evidence must not age out mid-pass or persist across passes
pretending to be current. Match that, and say what clears it.

## WHAT YOU MAY NOT DO

- No paid provider calls. No Apify, no xAI, no ContactOut credits. Tests
  against fakes; the ordering is verifiable from the table.
- No provider writes.
- Do not change `accepted_reasons` for an EXISTING paid step - TASK-207 owns
  the reason taxonomy. Add reasons for the steps you add.
- Do not enable Grok in a production run. Off by default, and say how it is
  turned on.
- Do not remove Apify or Blitz from a stage. They move later; they do not
  disappear.
- Never commit a key or PII.

## FILES ALLOWED

    src/waterfall.py   (stage provider ORDER and the new steps)
    src/research.py   (the crawl cache, if that is where it belongs - read
                       first and justify)
    tests/test_waterfall_order.py   (new)
    tests/test_crawl_cache.py   (new)
    docs/ROUTING-ORDER-2026-09-16.md   (new)

## FILES FORBIDDEN

    work/   config/   src/providerwrites.py   src/providers/contactout.py

## DELIVERABLE

The current order per stage with costs, the per-stage change under the new
policy with the direction of each stated, the free crawl moved ahead of every
paid step, Grok in fourth with an enforced reason and off by default with the
switch documented, and the company-level crawl cache with both counterfactual
tests green.
