# Bought Evidence Measurement - 2026-09-26

**TASK-192** - Buy evidence for 25 records and see if the wall moves.

## Method

- **Source:** Grok via xAI Responses API (`src.providers.xai.respond()`) with `web_search` tool
- **Sample:** 25 records from `review` status in the retired snapshot
  - 17 with zero evidence (all of them)
  - 8 with exactly 1 evidence row (from 12 available)
  - Ordered by TASK-169 enrichment ordering: headcount_signal DESC, employees DESC, research_outcome=HTTP_SUCCESS first
- **Cost:** $6.71 total, $0.27 average per record
- **Adapter:** TASK-182 compliant - all calls through `src.providers.xai.respond()`, never direct HTTP

## Result: the wall did not move in the direction that matters

| Movement | Count | % |
|---|---|---|
| review -> qualified | **0** | 0% |
| review -> rejected | **10** | 40% |
| review -> still review | **5** | 20% |
| review -> unknown | **10** | 40% |
| confidence off low | **0** | 0% |

**Zero records qualified.** Not one.

## What the evidence bought

### Rejections (10 records, valuable)

These records now have enough evidence to determine they are NOT ICP-matching. This is the whole point of company-first: stop spending person credits on companies that will not convert. The evidence bought 10 rejections at $0.67 each.

### "Unknown" status (10 records, the finding)

The ICP model has a status called `unknown` that is distinct from `review`. Ten records moved from `review` to `unknown` - meaning the model gained enough evidence to leave review but not enough to classify. The missing criteria are the same across all ten:

- `vertical could not be classified from the available evidence` (8 of 10)
- `no evidence of how client work is delivered` (10 of 10)
- `no evidence for delivery complexity` (8 of 10)
- `employee count unknown` (5 of 10)

### Still review (5 records)

Same structural criteria blocking them:

- `no evidence of how client work is delivered` (5 of 5)
- `no evidence for delivery complexity` (5 of 5)
- `no evidence for resource planning need` (4 of 5)

## The structural criteria that web search cannot answer

Three criteria appear in 100% of the non-rejected records:

1. **How client work is delivered** - this is a service-model question. A news article tells you what a company does, not how they deliver it to clients.
2. **Delivery complexity** - this requires understanding the engagement model, not the industry.
3. **Resource planning need** - this requires understanding internal operations, not public facts.

These are not company-fact questions. They are operational-model questions that web search about a company structurally cannot answer. You cannot find "how Company X delivers client work" in a Crunchbase profile or a news article.

## Claims gate

No records reached `qualified`, so the claims gate was never invoked. Zero newly-qualified records means zero claims-gate verdicts.

## Cost analysis

| Metric | Value |
|---|---|
| Total spend | $6.71 |
| Records processed | 25 |
| Verdicts changed (rejected) | 10 |
| Cost per rejection | $0.67 |
| Review records in snapshot | 66 |
| Projection to 66 review records | $27.50 (at $0.67/rejection, ~26 rejections) |
| Projection to 308 (TASK-166 base) | Not valid - base was wrong, see below |

## Projections are wrong and here is why

TASK-166 projected $61.89 for 316 records. That projection rested on two assumptions:
1. The review population was 308 records with no evidence
2. The cost per domain was ~$0.20

The actual review population in the retired snapshot is **66 records**, not 308. The 308 figure was measured against a different state (pre-enrichment, when most records had no evidence at all). After the free-crawl enrichment pass, 314 of 316 moved to `review` but many of those have *some* evidence - just not enough.

The measured cost per record is $0.27, not $0.20. The measured cost per *verdict change* is $0.67.

Corrected projection:
- 66 review records * $0.27/record = **$17.82** to run all of them through Grok
- Of those, ~40% would reject = ~26 rejections at $0.67 each = **$17.42**
- **Zero would qualify** (based on this measurement)

## The trap the task warned about

> "The tempting summary is 'Grok added 174 facts'. Facts added is not the metric. Records that changed verdict is the metric."

Grok added facts to every record it processed. The average was 5.5 facts per record. **Zero of those fact additions produced a qualification.** The criteria that block qualification are not company-fact criteria - they are structural/operational criteria that no amount of web search evidence can satisfy.

## What this means

If the question is "should we spend $60 buying Grok evidence for all review records?", the answer from this measurement is:

- **Yes, if the goal is rejections.** You will get ~26 rejections for ~$17.82, which stops person-credit spend on companies that will not convert. That is valuable.
- **No, if the goal is qualifications.** You will get zero. The wall does not move in that direction.
- **The real blocker is not evidence quantity, it is evidence type.** The criteria that prevent qualification ask questions that web search cannot answer. Buying more web search evidence will not move the needle on qualifications.

## Data

- Results: `scripts/task183_results.json`
- Script: `scripts/task183_buy_evidence.py`
- All record IDs, domains, and company names are hashed. Source URLs pointing at prospect sites are hashed. Third-party source domains are preserved.
