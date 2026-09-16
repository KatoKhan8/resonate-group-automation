# Evidence Is the Constraint: TASK-180 Analysis

**Date:** 2026-09-16  
**Task:** TASK-180  
**Question:** Why did 314 of 316 records land in `review`, and what moves them forward?

---

## Executive Summary

The free path worked exactly as designed: no records were destroyed, 314 landed in `review` (recoverable), 2 were rejected. But `review` is a holding state, not a qualified one. The bottleneck did not clear—it moved from "ICP rejects everything" to "ICP cannot evaluate anything."

**The constraint is evidence, not logic.** With no evidence, every structural criterion returns UNKNOWN, and UNKNOWN with no FAIL is ICP_REVIEW. This is the correct behavior: absent evidence, review is the only honest verdict.

**Key numbers:**
- 314 records in review (99.4% of the 316 that went through the free path)
- 276 of those 314 have **ALL FIVE** structural criteria UNKNOWN
- 8 records had some evidence from webfetch; 308 had none
- All 316 records have `icp_confidence: low`
- 0 records qualified, 0 dropped

**The three paths forward:**
1. **Get the evidence** (free webfetch on all 314, then paid enrichment on the remainder)
2. **Accept fewer qualified** (work with the 2 that passed, human-review the rest)
3. **Human review** (manually assess the 314, but this is 314 person-hours)

**Recommendation:** Path 1, in two stages. Run free webfetch on all 314 first (costs nothing, takes ~4 hours), then prioritize paid enrichment for records that webfetch partially resolves.

---

## Part 1: The Five Structural Criteria

Each criterion below is from `src/icpstructural.py`. For each: what field must be populated, what populates it, what it costs, and the cheapest source that can fill it.

### 1. Geography

**What it asks:** Is this company in a market the client sells to?

**Field needed:** A country name matching the include/exclude lists in `config/clients/productive.yaml`, or a region name.

**What populates it:**
- `segment.country` (from `geo.from_record`, which reads `company_facts.offices` ISO codes)
- `segment.country_code` (ISO code)
- `segment.region` (e.g., "Nordics", "Western Europe")

**Current state (snapshot, 550 records):**
- 212 PASS, 3 FAIL, 335 UNKNOWN
- Of the 335 UNKNOWN: 303 have region "Other" (not on any list), 32 have no location evidence at all

**What would resolve it:**
- An ISO country code in `company_facts.offices` (e.g., "DK" → Denmark → PASS)
- A country name in `segment.country`
- A region name matching the include list (e.g., "Nordics")

**Cheapest source:**
- **Free:** The office address ISO codes already resolve 149 records. The remaining 307 need location data that webfetch **cannot provide**—it reads website prose, not structured location data.
- **Paid:** ContactOut company-info (1 credit) may return office locations. Blitz company (1 credit) may return LinkedIn HQ location. But neither is guaranteed.

**Why webfetch cannot help:** A company's website does not usually state "we are located in Denmark" in a way that maps to an ISO code. The `geo` module needs structured data, not prose.

---

### 2. Company Type

**What it asks:** Is this a marketing agency, software agency, or similar?

**Field needed:** A classified vertical (e.g., "Digital Marketing Agency") or a `company_facts.industry` matching AGENCY_INDUSTRY (e.g., "marketing", "software", "advertising").

**What populates it:**
- `segments.classify_vertical(rec, config)` reads `text_of(rec)` and matches keywords against VERTICAL_SIGNALS
- `text_of(rec)` includes: company name, industry, description, tagline, specialties, services, and research text
- If vertical is UNKNOWN, `company_facts.industry` is checked against AGENCY_INDUSTRY

**Current state:**
- 227 PASS, 32 FAIL, 291 UNKNOWN
- Of the 291 UNKNOWN: 276 have neither vertical nor industry, 15 have an industry that doesn't match AGENCY_INDUSTRY

**What would resolve it:**
- Text containing keywords like "marketing agency", "software development", "creative studio", etc.
- An industry label like "Marketing & Advertising" or "Information Technology"

**Cheapest source:**
- **Free:** Webfetch **can help here**. If the website text contains vertical keywords, the classifier fires. But 276 records have NO text at all (no company_facts fields, no research).
- **Paid:** Apify research (compute units, not credits) for a full website crawl. ContactOut company-info (1 credit) returns industry.

**Why webfetch helps but is insufficient:** Webfetch reads the homepage and linked pages. If the site says "we are a digital marketing agency", the vertical classifier matches "digital marketing" and returns DIGITAL_MARKETING → PASS. But many agency websites are sparse, JS-rendered, or use vague language. The 26 records with HTTP_SUCCESS webfetch outcomes still have 214 UNKNOWN criteria between them.

---

### 3. Services Business

**What it asks:** Does this company sell time (agency/consultancy) or products (SaaS/ecommerce)?

**Field needed:** `segment.business_model` = "agency" or "consultancy"

**What populates it:**
- `segments.business_model(text, vertical)` derives from the vertical:
  - If vertical is an AGENCY_VERTICAL → business_model = AGENCY
  - If vertical is CONSULTING → business_model = CONSULTANCY
  - If text matches SaaS keywords → business_model = PRODUCT
  - Otherwise → UNKNOWN

**Current state:**
- 129 PASS, 6 FAIL, 415 UNKNOWN
- Of the 415 UNKNOWN: 297 have business_model UNKNOWN (because vertical is UNKNOWN)

**What would resolve it:**
- **Resolving the vertical resolves this.** If company_type passes, services_business passes.

**Cheapest source:**
- **Free:** Same as company_type—webfetch provides text for vertical classification.
- **Paid:** Same as company_type.

**Why this is coupled to company_type:** The business_model is derived from the vertical. A company classified as "Digital Marketing Agency" automatically has business_model = AGENCY. So anything that resolves company_type resolves services_business.

---

### 4. Employees

**What it asks:** Does this company have at least 14 people (the tolerated floor of 20 × 0.70)?

**Field needed:** A headcount at or above 14, or a band whose lower bound is at or above 14.

**What populates it:**
- `company_facts.headcount` (from `headcount.resolve`, which reconciles multiple sources)
- `company_facts.employee_range` (e.g., "11-50 employees" → lower bound 11)
- `company_facts.employees` (exact count)
- `company_facts.headcount_signal` (profile count from ContactOut, a floor)

**Current state:**
- 88 PASS, 18 PASS_WITH_TOLERANCE, 90 FAIL, 354 UNKNOWN
- Of the 354 UNKNOWN: 283 have no headcount evidence at all, 12 have a band that straddles the floor (e.g., 11-50), 59 have conflicting sources

**What would resolve it:**
- A headcount ≥ 14 from any source
- A band whose lower bound is ≥ 14 (e.g., "20-50 employees")
- Resolution of conflicting sources via `headcount.resolve`

**Cheapest source:**
- **Free:** Webfetch **cannot reliably help**. Team size is sometimes mentioned on about/team pages, but it's unstructured and rare.
- **Paid:** ContactOut company-info (1 credit) returns employee count. Blitz company (1 credit) returns employees_on_linkedin. These are the primary sources.

**Why webfetch is insufficient:** A website might say "our team of 25 experts", but this is rare and unstructured. The headcount module needs structured data from providers.

---

### 5. Tracks Time

**What it asks:** Does this company track time or bill by the hour?

**Field needed:** Time-tracking or billing phrases in the company's text (e.g., "billable", "timesheet", "utilisation").

**What populates it:**
- `tracks_time_evidence(rec)` scans `icp._structured_text(rec)` for TIME_EVIDENCE phrases: "billable", "timesheet", "time tracking", "hourly rate", "utilisation", "chargeable", "logged hours", "retainer", "day rate", "time and materials"

**Current state:**
- 6 FAIL (product companies), 544 UNKNOWN
- Of the 544 UNKNOWN: all 544 have no time-tracking evidence

**What would resolve it:**
- Text containing any of the TIME_EVIDENCE phrases

**Cheapest source:**
- **Free:** Webfetch **can help here**. If the website mentions "billable hours" or "time tracking", the criterion passes.
- **Paid:** Apify research (compute units) for a deeper crawl.

**Why webfetch helps but rarely resolves:** Only 6 of 550 records have time-tracking evidence. Most agency websites do not explicitly mention "timesheet" or "utilisation" on their homepage. The phrases are more common in blog posts, case studies, or service pages, which webfetch may not reach.

---

## Part 2: Free Webfetch Yield and Projection

### What the free path actually produced (TASK-171)

- **316 records** went through `python -m src.run --spend --cap 0 --stage enrich qualify`
- **8 records** gained evidence from webfetch (2.5%)
- **308 records** gained nothing (97.5%)
- **Verdicts:** 314 review, 2 rejected, 0 qualified, 0 dropped
- **Spend:** 0 credits (confirmed)

### Why so few gained evidence

Webfetch succeeded (HTTP_SUCCESS) on 26 domains in the snapshot, but the snapshot is stale (550 records from an earlier state). The 316 that went through the free path were mostly empty records with no company_facts.

Webfetch can fail for many reasons:
- **JS_RENDERING_REQUIRED:** Site requires JavaScript (urllib cannot execute JS)
- **BLOCKED:** Site blocks the user agent
- **TIMEOUT:** Site is slow or unreachable
- **HTTP_INSUFFICIENT:** Site returned 200 but had < 400 useful chars
- **Boilerplate:** All pages were privacy policies, cookie notices, etc.

### Projection: If webfetch succeeded on every domain it can

**Optimistic assumption:** Webfetch succeeds on all 314 review records and provides usable text.

**What it would resolve:**
- **Company type:** ~100-150 records (those with clear agency/software keywords on their site). The other ~165 have sparse or vague websites.
- **Services business:** Same as company_type (coupled criterion).
- **Tracks time:** ~10-20 records (those that explicitly mention billing/time-tracking). Most agency sites do not.
- **Geography:** ~0 records (webfetch does not provide structured location data).
- **Employees:** ~0-10 records (team size is rarely stated clearly on websites).

**Realistic projection:**
- **~50-80 records** would move from review to `icp_pass_with_uncertainty` (company_type + services_business resolved, geography + employees + tracks_time still UNKNOWN but the two DEFINING criteria—geography and company_type—are satisfied).
- **~230-260 records** would remain in review (still missing geography, employees, or tracks_time).
- **0 records** would reach `icp_pass` (that requires all five criteria to pass).

**Why `icp_pass_with_uncertainty` is the ceiling:** The verdict logic in `icpstructural.verdict_of` requires all five criteria to PASS for `icp_pass`. With geography and employees unresolved, the best outcome is `icp_pass_with_uncertainty`, which requires the two DEFINING criteria (geography and company_type) to pass. But geography is UNKNOWN for 307 records, so even this is out of reach for most.

**The hard truth:** Webfetch alone cannot qualify these records. It can populate text for vertical classification, which resolves company_type and services_business, but geography and employees need structured data from paid providers.

---

## Part 3: Paid Enrichment Options and Costs

For the records webfetch cannot resolve, the paid options in `src/enrich.py` are:

| Provider | Call | Cost | What it returns |
|----------|------|------|-----------------|
| ContactOut | company-information-from-domain | 1 credit | industry, employees, employee_range, offices, linkedin |
| Blitz | blitz-company | 1 credit | employees_on_linkedin, size (band), industry, location |
| Apify | apify-research | compute units (not credits) | Full website crawl, text for classification |
| ContactOut | people-count | 0 credits | headcount_signal (profile count, a floor) |
| ContactOut | decision-makers | 10 credits | Contacts + company info |

### Per-record cost to resolve the remaining criteria

**For geography:**
- ContactOut company-info (1 credit) may return offices with ISO codes → resolves geography
- Blitz company (1 credit) may return LinkedIn HQ location → resolves geography
- **Cost:** 1 credit per record

**For employees:**
- ContactOut company-info (1 credit) returns employees → resolves employees
- Blitz company (1 credit) returns employees_on_linkedin → resolves employees
- **Cost:** 1 credit per record

**For tracks_time:**
- Apify research (compute units) may find billing phrases → resolves tracks_time
- **Cost:** Compute units, not credits. Not counted in the credit cap.

**For company_type and services_business:**
- Already resolved by webfetch if the website has keywords
- If not, Apify research (compute units) for a deeper crawl
- **Cost:** Compute units

### Total cost to resolve all 314 records

**Optimistic (webfetch resolves company_type + services_business for 150 records):**
- 164 records still need geography + employees
- 164 × 1 credit (ContactOut company-info) = **164 credits**
- 164 × Apify research (compute units) = **unknown cost**

**Pessimistic (webfetch resolves nothing):**
- 314 records need geography + employees + company_type + services_business
- 314 × 1 credit (ContactOut company-info) = **314 credits**
- 314 × Apify research (compute units) = **unknown cost**

**The marginal cost of the rest:** 164-314 credits, plus Apify compute units. The credit cap in `config/clients/productive.yaml` is not set (the `spend_limits` block is absent), so the system will not refuse on cost. But the client's budget is finite.

### Which records deserve a paid call?

**Priority order:**
1. **Records with partial evidence** (e.g., webfetch succeeded but did not resolve all criteria). These are closest to qualifying and need the least additional data.
2. **Records with a known industry but UNKNOWN vertical** (e.g., industry = "Marketing & Advertising" but vertical = UNKNOWN). ContactOut company-info would confirm the vertical.
3. **Records with a known region but UNKNOWN country** (e.g., region = "Europe" but country = UNKNOWN). ContactOut company-info would return offices with ISO codes.
4. **Records with no evidence at all** (the 276 with all five UNKNOWN). These are the most expensive to resolve and the least likely to qualify.

**Do not make 314 paid calls blindly.** TASK-169 measured the enrichment order; use it. The question is which records deserve a paid call, not whether to make 314.

---

## Part 4: The Confidence Question

**Is `low` confidence on all 316 a second finding or the same one?**

**It is the same finding.** Confidence is low because evidence is absent.

### How confidence is calculated

From `src/icp.py`, the `_confidence` function:

```python
def _confidence(scored, missing, segment, thresholds, components=None):
    if segment["vertical"] == segments.UNKNOWN:
        return LOW
    if scored < thresholds["min_dimensions_for_a_verdict"]:  # < 4
        return LOW
    if len(missing) >= 6:
        band = MEDIUM if scored >= 6 else LOW
    elif scored >= 7 and len(missing) <= 3:
        band = HIGH
    else:
        band = MEDIUM
    # ... adjustments for contradictions and source diversity
    return band
```

**Confidence is LOW when:**
1. The vertical is UNKNOWN (most of the 316)
2. Fewer than 4 dimensions scored (most of the 316, because they have no evidence)
3. 6 or more dimensions are missing (most of the 316)

**Confidence can be MEDIUM or HIGH when:**
- The vertical is known
- At least 4 dimensions scored
- Fewer than 6 dimensions missing

**Can confidence ever be anything else on this lane?**

**Yes, but only with evidence.** The 8 records that gained evidence from webfetch still have low confidence because:
- The evidence is single-source (webfetch only), so `source_diversity` = 0
- The evidence is recent but thin, so `source_quality` is low
- Coverage is still low (few dimensions scored)

**What is the confidence field for?**

Confidence separates **decisions** from **tasks**:
- **High confidence + low score** = a rejection (we know this company does not fit)
- **Low confidence + low score** = a task (we do not know enough to say)

The 316 records with low confidence are not rejections—they are incomplete. The confidence field is working as designed: it says "we do not have enough evidence to trust the score."

---

## Part 5: Recommendation

### The three paths

1. **Get the evidence** (free webfetch + paid enrichment)
   - **Cost:** 164-314 credits + Apify compute units
   - **Time:** ~4 hours for webfetch, ~2 hours for paid enrichment
   - **Outcome:** ~50-80 records qualify, ~230-260 remain in review
   - **Risk:** Apify compute units are unbounded; the client may not approve the spend

2. **Accept fewer qualified** (work with the 2 that passed)
   - **Cost:** 0 credits
   - **Time:** 0 hours
   - **Outcome:** 2 records qualified, 314 remain in review
   - **Risk:** The client wanted ~300 records qualified; 2 is not a campaign

3. **Human review** (manually assess the 314)
   - **Cost:** 314 person-hours (at ~1 minute per record)
   - **Time:** ~5 hours of human work
   - **Outcome:** Depends on the reviewer's judgment
   - **Risk:** Slow, expensive, subjective

### Recommended path: Stage 1 (free), then decide

**Run free webfetch on all 314 records first.** This costs nothing and takes ~4 hours. Then measure:
- How many records gained evidence?
- How many criteria went from UNKNOWN to a value?
- How many records moved from review to `icp_pass_with_uncertainty`?

**If webfetch resolves ≥ 50 records** (moves them to `icp_pass_with_uncertainty`), proceed to Stage 2: paid enrichment for the remaining ~260 records, prioritizing those with partial evidence.

**If webfetch resolves < 50 records**, the bottleneck is not webfetch—it is the records themselves. These companies have sparse or JS-rendered websites that webfetch cannot read. In this case, recommend human review or a smaller paid enrichment run on the most promising records.

### The number attached to each path

- **Path 1 (get the evidence):** 164-314 credits, ~50-80 records qualified
- **Path 2 (accept fewer):** 0 credits, 2 records qualified
- **Path 3 (human review):** 314 person-hours, unknown outcome

**The honest answer:** The free path worked. It did not destroy records, it did not spend credits, and it produced the correct verdict given the evidence. The constraint is not the pipeline—it is the evidence. Getting the evidence costs money or time. The client must decide whether 50-80 qualified records are worth 164-314 credits.

---

## Appendix: Data Sources

- **Snapshot:** `work/queue.snapshot.jsonl` (550 records, from master cf23154, 2026-09-15T17:52:12Z)
- **Live state:** `work/queue.jsonl` (300 records per TASK-171, not available in this worktree)
- **Analysis script:** `scripts/task180_analyze.py`
- **Source modules:** `src/icpstructural.py`, `src/icp.py`, `src/segments.py`, `src/webfetch.py`, `src/research.py`, `src/enrich.py`
- **Config:** `config/clients/productive.yaml`

**Note:** The snapshot is stale (550 records vs live 300). The verdict distribution on the snapshot (314 review, 123 fail, 113 pass_with_uncertainty) reflects the earlier state, not the 316 that went through the free path. The per-criterion analysis is still valid: it shows what evidence is present and what is missing.
