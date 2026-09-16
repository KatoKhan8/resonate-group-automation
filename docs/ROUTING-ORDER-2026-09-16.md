# Routing order, 2026-09-16

TASK-208. The free crawler goes before anything paid, and Grok goes fourth.

## The policy order

    1  CONTACTOUT                      first whenever capable
    2  CONTACTOUT CACHE / EXISTING     reuse aggressively
    3  FREE / SELF-HOSTED CRAWLER      incremental public-web evidence
    4  GROK / xAI                      still-missing, current, ambiguous
    5  OTHER PAID PROVIDERS            genuine capability gaps only
    6  CLAUDE                          reasoning and escalation, never bulk

Source: `PROVIDER-ROUTING-POLICY.md`.

## Current order per stage, with costs

### company_information

| # | Provider  | Call                          | Cost                 | Free? | Direction |
|---|-----------|-------------------------------|----------------------|-------|-----------|
| 1 | contactout| company-information-from-domain| 1 credit            | No    | unchanged |
| 2 | webfetch  | webfetch-crawl                | 0 (free HTTP read)   | YES   | NEW       |
| 3 | xai       | xai-research                  | 2B ticks (~$0.20)    | No    | NEW       |
| 4 | blitz     | blitz-domain-to-linkedin      | 1 record             | No    | unchanged |
| 5 | blitz     | blitz-linkedin-to-domain      | 1 record             | No    | unchanged |
| 6 | blitz     | blitz-company                 | 1 record             | No    | unchanged |
| 7 | apify     | apify-research                | 0 credits (compute units) | No | unchanged |

**Changes:** webfetch inserted at position 2 (after ContactOut, before every paid
step). xai inserted at position 3 (after free crawl, before paid providers).
Direction: free EARLIER, paid LATER. Apify moved from position 5 to position 7.

### people_discovery

| # | Provider  | Call                          | Cost        | Free? | Direction |
|---|-----------|-------------------------------|-------------|-------|-----------|
| 1 | contactout| people-count                  | 0 credits   | YES   | unchanged |
| 2 | contactout| decision-makers               | 10 credits  | No    | unchanged |
| 3 | blitz     | blitz-employee-finder         | 5 records   | No    | unchanged |
| 4 | aiark     | aiark-people-search           | 2 credits   | No    | unchanged |

**Changes:** None. This stage already complies - ContactOut first, then paid
fallbacks with reasons. No free crawler applies to people discovery.

### linkedin_url

No changes. ContactOut first, then paid fallbacks.

### email_discovery

No changes. ContactOut first, then paid fallbacks.

### email_verification

No changes. ContactOut first, then paid verifiers.

### company_research

| # | Provider  | Call                          | Cost                 | Free? | Direction |
|---|-----------|-------------------------------|----------------------|-------|-----------|
| 1 | contactout| company-information-from-domain| 1 credit            | No    | unchanged |
| 2 | webfetch  | webfetch-crawl                | 0 (free HTTP read)   | YES   | NEW       |
| 3 | apify     | apify-research                | 0 credits (compute units) | No | unchanged |

**Changes:** webfetch inserted at position 2 (after ContactOut, before Apify).
Direction: free EARLIER. Apify moved from position 2 to position 3.

### person_research

No changes. ContactOut first, then paid crawl.

## What changed and why

### 1. Free crawl before every paid fallback

`webfetch` is free (HTTP read, no credit cost). Under the policy, every free
attempt precedes every paid one. webfetch was already implemented in
`src/webfetch.py` and called from `src/research.py._from_the_site_itself`, but
it was not a named step in the waterfall table. Now it is, in both
`company_information` and `company_research`, positioned after ContactOut and
before every paid provider.

Direction: **free EARLIER**. No paid provider was moved forward.

### 2. Grok in fourth

`xai` (Grok) is now a step in `company_information`, positioned after the free
crawl and before every paid provider. It is:

- Marked `is_fallback: true`
- Gated by `requires_reason: contactout_missing_company_data`
- Costed at 2,000,000,000 ticks (~$0.20 per domain, 10B ticks per USD)
- **Off by default** - no production caller exists

The reason is a ContactOut confirmed miss (`contactout_missing_company_data`),
NOT an error or timeout. This matches the policy: Grok is licensed by what
ContactOut confirmed it cannot supply, never by a transient failure.

Direction: **paid LATER** (Grok is cheaper than Apify and Blitz for the
questions it answers, but it is still paid and sits after free).

### 3. Grok is off by default

`grep -rn "xai" src/` returns only the adapter (`src/providers/xai.py`). No
production module imports or calls it. The waterfall table declares the step
so the audit can reason about it, but the step is unreachable in a production
run unless an operator explicitly enables it.

**How to turn it on:** Set `xai.enabled: true` in the workspace client config.
The adapter uses the Responses API (`/v1/responses`), not the deprecated Chat
Completions endpoint. The key is `XAI_API_KEY` in `config/.env`.

### 4. Company-level crawl cache

One crawl per company per pass, reused across every contact on that company.
Implemented in `src/research.py`:

- `crawl_cache_get(domain)` - returns cached evidence or None
- `crawl_cache_set(domain, evidence)` - stores crawl result
- `crawl_cache_clear()` - empties the cache

**What clears it:** `enrich.run()` calls `crawl_cache_clear()` at the start of
each pass. The cache is pass-scoped: evidence must not age out mid-pass or
persist across passes pretending to be current.

**Counterfactual (proved by tests):**
- 3 contacts on one domain → ONE `webfetch.research` call (cache hit for 2nd and 3rd)
- After clearing the cache → each contact triggers its own crawl

Provenance (source_url, content_hash, retrieved_at) is preserved from the
original crawl. Each contact gets its own `record_id`.

## The trap that was avoided

Every change moves free EARLIER or paid LATER, never the reverse:

- webfetch (free) was inserted BEFORE Blitz and Apify (paid) in company_information
- webfetch (free) was inserted BEFORE Apify (paid) in company_research
- xai (paid, ~$0.20) was inserted AFTER webfetch (free) and BEFORE Blitz/Apify

No paid provider was moved forward. The direction is uniformly toward cheaper.

## Files changed

    src/waterfall.py       - stage provider order, new steps
    src/enrich.py          - cost entries, CALL_STAGE routing, cache clear
    src/research.py        - company-level crawl cache
    tests/test_waterfall.py          - updated free-step exception
    tests/test_invariants.py         - added webfetch-crawl to free set
    tests/test_waterfall_order.py    - new: ordering assertions
    tests/test_crawl_cache.py        - new: cache counterfactual tests
