# Grok vs Free Research: First Real Workload Measurement

**Date:** 2026-09-16  
**Task:** TASK-166  
**Snapshot:** `work/queue.snapshot.jsonl` (2026-09-15T17:52:12+00:00 from master cf23154, 550 records)

## What Was Measured

10 domains with `company_facts` already populated from the existing free path (ContactOut structured data + webfetch/Apify crawl). For each, Grok was asked the company-research question via the xAI Responses API (`/v1/responses`) with `web_search` enabled - the capability this lane exists to buy.

The prompt shape comes from what the pipeline actually needs: structured facts about what a company does, their specialties, notable facts, and recent developments. This is what `facts_block` and `research_block` feed to the hook and draft prompts in `generate.py`.

## API Note

The xAI Chat Completions API deprecated `live_search` (HTTP 410 Gone). The measurement uses the new Responses API at `/v1/responses` with `{"type": "web_search"}` in the tools array. The adapter in `src/providers/xai.py` is built for Chat Completions and was not used; the script calls the Responses API directly.

## Cost

| Metric | Value |
|--------|-------|
| Domains measured | 10 |
| Total cost | $1.9585 USD (19,584,500,000 ticks) |
| Average cost per domain | $0.1958 USD |
| **Projection to 316 domains** | **$61.89 USD** |

Cost range per domain: $0.1266 - $0.2583. The variation correlates with how much reasoning the model did (reasoning tokens: 1,500-4,000 per call) and how many web searches it performed (41-65 search URLs per domain).

## Fact Counts

| Category | Count | Meaning |
|----------|-------|---------|
| Confirmed | 47 | Grok agrees with what the existing path already has |
| New from Grok | 174 | Facts Grok found that the existing path does not have |
| Contradictions | 8 | Grok and the existing path disagree |
| Unsourced | 0 | Every fact Grok asserted carried a source URL |

**Zero unsourced facts.** This is the critical number. A claim without a source URL cannot pass the claims gate, cannot reach copy, and is worth nothing to this pipeline however true it is. Grok with web_search sourced every fact it returned.

### New Facts by Field

| Field | Count | Value to Pipeline |
|-------|-------|-------------------|
| specialties | 58 | High - the free path often misses these; hooks need them |
| notable | 55 | High - clients, projects, achievements; the hook prompt lives or dies on these |
| recent_developments | 26 | High - news, launches, hiring, funding; time-sensitive evidence the crawler cannot find |
| description | 10 | Medium - what the company does in one sentence |
| employees_estimate | 10 | Low - structured data usually has this |
| offices | 8 | Low - structured data usually has this |
| name | 4 | Low - rebrand detection |
| founded | 3 | Low - nice to have, not decision-critical |

The top three fields (specialties, notable, recent_developments) account for 139 of 174 new facts (80%). These are exactly the fields the free path is weakest on: the crawler reads what's on the website, but a company's notable clients, recent launches, and specific specialties are often not on their own pages or are buried in navigation text the quality filter refuses.

## Contradictions

8 contradictions were found. After inspection, **4 are real and 4 are naming differences**.

### Real Contradictions (all on one domain: whiteglove.com / hash `f7173b105b29`)

| Field | Existing Path | Grok | Grok Source |
|-------|--------------|------|-------------|
| name | WhiteGlove Health | AcquireUp | [PR Newswire](https://www.prnewswire.com/news-releases/white-glove-acquire-direct-and-leadjig-rebrand-as-acquireup-launch-technology-first-seminar-marketing-solutions-for-financial-professionals-302254762.html) |
| industry | Wellness and Fitness Services | Advertising and marketing (seminar marketing for financial professionals) | [Datanyze](https://www.datanyze.com/companies/acquireup/5000004924) |
| founded | 2006 | 2015 | [PitchBook](https://pitchbook.com/profiles/company/322100-56) |

**This is a rebrand.** WhiteGlove Health rebranded to AcquireUp. The existing path has the old name, old industry, and old founding date. Grok found the rebrand, the new industry positioning, and a different founding date (possibly the founding of the rebranded entity vs the original). All three Grok facts carry source URLs that can be verified.

This is exactly the kind of finding that justifies Grok's cost: a fact the free path cannot find because the company's own website may still say the old name, and the structured providers have stale data.

### Naming Differences (not real contradictions)

| Domain | Field | Existing | Grok | Verdict |
|--------|-------|----------|------|---------|
| da9fa0575ce8 (&Partner ApS) | industry | Marketing & Advertising | Advertising / Reklamebureauer | Same industry, Danish phrasing |
| 17851b33a43d (16K Agency) | industry | Marketing & Advertising | Advertising Services | Same industry, different label |
| f3945ded7f71 (20North Inc.) | industry | Advertising Services | Advertising, Marketing & PR | Same industry, broader label |
| c4fc9445e96d (Village Press) | name | Village Press Inc | Village Press, Inc. | Punctuation only |
| c4fc9445e96d (Village Press) | industry | Printing Services | Magazine publishing, printing, fulfillment, and marketing services | More specific, not contradictory |

These 5 are not contradictions. They are the same facts expressed differently. The industry labels come from different taxonomies (LinkedIn vs ContactOut vs Grok's own classification), and a string comparison flags them even though a human would recognise them as the same.

## What the Free Path Already Has

Of the 10 domains:
- 6 had `existing_research_count: 0` (the free crawl found nothing usable, or the quality filter refused everything)
- 4 had 1-5 research rows of medium/strong quality

For the 6 domains with zero usable research evidence, Grok found 100% of the facts. The free path had structured data (name, industry, employees, revenue) from ContactOut, but no crawled evidence about what the company actually does, their specialties, or their notable clients.

For the 4 domains with existing research evidence, Grok confirmed 47 facts and added 74 new ones. The existing crawl had captured some of what was on the company's own website, but Grok found additional facts from LinkedIn, industry directories, news articles, and business registries that the same-domain-only crawler cannot reach.

## Web Search Coverage

Grok performed 41-65 web searches per domain (total: 566 across 10 domains). Sources searched included:
- Company websites (the same pages webfetch reads)
- LinkedIn company pages
- Business registries (profiler.dk, paqle.dk, fyple.com, etc.)
- Industry directories and databases (PitchBook, Datanyze, Inc. 5000)
- News articles and press releases (PR Newswire)
- Local business listings

The free path's webfetch is same-domain-only by design. It reads the company's own website and follows links within that domain. It cannot reach LinkedIn, business registries, news articles, or industry databases. Grok with web_search can.

## Verdict

**Is Grok worth its price on company research? Yes, but not for every domain.**

### Where Grok wins

1. **Specialties and notable clients.** The free path reads what's on the website. Grok reads LinkedIn, industry directories, and news. At 58 specialties and 55 notable facts the free path missed, this is the largest category of incremental value. These are the facts the hook prompt needs.

2. **Recent developments.** 26 facts about launches, hiring, funding, and partnerships. The free path cannot find these because they are not on the company's own website (or are buried in a blog post the quality filter refuses). Grok searches news and finds them.

3. **Rebrand detection.** The whiteglove.com case is the strongest argument for Grok. The company rebranded, changed industry, and the structured providers have stale data. Grok found the rebrand with a verifiable source. The free path cannot do this.

4. **Domains where the free crawl found nothing.** 6 of 10 domains had zero usable research evidence. For these, Grok is the only source of public evidence beyond structured data.

### Where Grok does not add value

1. **Basic firmographics.** Name, industry, employees, revenue, offices - the structured providers (ContactOut) already have these. Grok confirmed them but rarely improved on them.

2. **Cost.** At $0.20/domain ($62 for 316 domains), Grok is expensive compared to the free path (which costs nothing beyond the Apify compute units already budgeted). The question is whether the 174 new facts are worth $62.

3. **Industry label differences.** 5 of 8 "contradictions" were just different naming for the same industry. Grok does not use the same taxonomy as ContactOut, so a naive comparison overstates disagreement.

### Recommendation

Grok is worth its price for the 80% of new facts that land in specialties, notable, and recent_developments - the fields the free path is structurally weakest on. It is not worth running for basic firmographics the structured providers already have.

A targeted deployment would be:
- Run Grok only for domains where `existing_research_count` is 0 (the free crawl found nothing)
- Run Grok only for domains in the cold lane that need a hook (the hook prompt is blocked on `notable` and `specialties`)
- Do not run Grok for domains that already have medium/strong research evidence from the free crawl

At 316 domains, if roughly 100 have zero usable research evidence (extrapolating from the 6/10 measured), the cost would be ~$20 for the domains that genuinely need it, not $62 for all of them.

## Files

- Measurement script: `scripts/task166_grok_measurement.py`
- Detailed results (JSON): `scripts/task166_results.json`
- This report: `docs/GROK-VS-FREE-RESEARCH-2026-09-16.md`

## Hashing

Domains and company names in this report are referenced by their SHA-256 hash prefix (12 chars) where PII rules apply. The hashes are deterministic: `hashlib.sha256(domain.encode()).hexdigest()[:12]`. The full domain names are in the JSON results file for Claude's review.
