# Research Worklist — 2026-09-15

**Snapshot:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
**Generated:** 2026-09-15 by TASK-154

---

## The Four Counts

### Q1: Records with NO evidence at all

**343 of 550 records (62.4%) have zero research evidence.**

Of those 343, only **17 would `research.why()` fire for**. The other 326 do not trigger research because:

| Reason | Count |
|--------|-------|
| `domains` lane, all contacts already have an angle | 342 |
| `domains` lane, has structured specialties or industry | 80 |
| ICP verdict already `rejected` | 56 |
| Has structured `notable` or `specialties` facts | 49 |
| ICP verdict already `qualified` | 20 |

(Counts overlap — one record can match multiple reasons.)

All 343 no-evidence records are in the `domains` lane. None have an ICP verdict yet.

**`research.why()` fires for 17 records, all for one reason:**
- `public_evidence_required_for_icp_dimensions` — 17 records

These 17 are queued records whose ICP verdict is `review` or `unknown` because the six prose-reading ICP dimensions (resource planning, profitability, utilisation, time tracking, operational complexity, delivery complexity) cannot score without web evidence. ContactOut's structured data does not carry these signals.

### Q2: Records with STALE evidence (under TTL)

**6 records have at least one stale evidence row.**

| Field | TTL | Stale rows |
|-------|-----|------------|
| `team` | 3 days | 6 |

All 6 stale rows are `team` pages that have outlived the 3-day short-lived TTL. Four of these records are `dropped`, two are `queued`.

### Q3: Evidence present but UNUSABLE (boilerplate)

**703 total research rows across all records. Only 3 are boilerplate (0.4%).**

| Category | Count |
|----------|-------|
| Total research rows | 703 |
| Boilerplate rows | 3 |
| Usable rows | 700 |
| Records with ONLY boilerplate (nothing usable) | 0 |
| Records with mixed usable + boilerplate | 2 |

`evidence.select` filters boilerplate out of the prompt. After filtering, **343 records have nothing usable** — but that is because they have nothing at all, not because everything was filtered.

The boilerplate rate (0.4%) is far below the 236/695 (34%) measured earlier. The filter is working.

### Q4: ICP qualification of records needing research

**23 records need research. 0 are ICP-qualified.**

| ICP verdict | Count |
|-------------|-------|
| qualified | 0 |
| review | 0 |
| unknown | 0 |
| rejected | 0 |
| no verdict yet | 23 |

This is expected: the 17 ICP-dimension records need research precisely BECAUSE their ICP verdict cannot be settled without prose evidence. The 6 stale-evidence records have not been through ICP scoring yet.

Of the 23: **17 are `queued`** (active, would benefit from research), **6 are `dropped`** (research would not change their state).

---

## Prioritised Research Worklist

### Tier 1: Queued, needs ICP-dimension evidence (17 records)

These are the highest value: research directly enables an ICP verdict, which gates all downstream spend.

| # | Record ID | Domain | Reason |
|---|-----------|--------|--------|
| 1 | australo-org | australo.org | ICP dimensions |
| 2 | hotmail-fi | hotmail.fi | ICP dimensions |
| 3 | tateshvili-com | tateshvili.com | ICP dimensions |
| 4 | consolidated-net | consolidated.net | ICP dimensions |
| 5 | grueandbleen-com | grueandbleen.com | ICP dimensions |
| 6 | twornia-pl | twornia.pl | ICP dimensions |
| 7 | zedi-africa | zedi.africa | ICP dimensions |
| 8 | omnicommediagroup-pl | omnicommediagroup.pl | ICP dimensions |
| 9 | goldsocial-com-au | goldsocial.com.au | ICP dimensions |
| 10 | vieren-be | vieren.be | ICP dimensions |
| 11 | angletech-ai | angletech.ai | ICP dimensions |
| 12 | fvdsonline-com | fvdsonline.com | ICP dimensions |
| 13 | availlabs-com | availlabs.com | ICP dimensions |
| 14 | digivomedia-co-uk | digivomedia.co.uk | ICP dimensions |
| 15 | troystar-com | troystar.com | ICP dimensions |
| 16 | creativecircle-ch | creativecircle.ch | ICP dimensions |
| 17 | e-deocom-com | e-deocom.com | ICP dimensions |

**Note:** `hotmail.fi` is almost certainly an email domain, not a company website. It should be skipped or investigated as a data-quality issue before crawling.

### Tier 2: Queued, needs stale refresh (2 records)

| # | Record ID | Domain | Stale field |
|---|-----------|--------|-------------|
| 1 | villagepress-com | villagepress.com | team |
| 2 | mymail-pomona-edu | mymail.pomona.edu | team |

### Tier 3: Dropped, stale refresh — do not crawl (4 records)

| # | Record ID | Domain | Stale field |
|---|-----------|--------|-------------|
| 1 | 22visioncg-com | 22visioncg.com | team |
| 2 | 30lines-com | 30lines.com | team |
| 3 | halconmarketing-com | halconmarketing.com | team |
| 4 | barkingspider-ca | barkingspider.ca | team |

These are dropped. Crawling them would be spend with no downstream consumer.

---

## Free vs Paid Split

### Reachability Probes (5 domains)

Five domains were probed with `webfetch.research()` (the free leg):

| Domain | Outcome | Pages | Fallback-worthy | Seconds |
|--------|---------|-------|-----------------|---------|
| australo.org | RESEARCH_FAILED | 0 | Yes | 0.61 |
| hotmail.fi | RESEARCH_FAILED | 0 | Yes | 0.10 |
| tateshvili.com | RESEARCH_FAILED | 0 | Yes | 0.16 |
| 22visioncg.com | HTTP_INSUFFICIENT | 0 | No | 1.07 |
| 30lines.com | BLOCKED | 0 | Yes | 0.80 |

**Result: 0 of 5 succeeded with the free leg.** 4 of 5 are fallback-worthy (would benefit from a paid Apify crawl). The one that was not fallback-worthy (22visioncg.com) responded but served a page exceeding the 512KB size limit.

**Implication:** The free leg's success rate on this cohort is likely to be low. Of the 19 actionable records (17 ICP + 2 stale), expect most to require the paid Apify leg. The free leg should still be tried first per the waterfall design — it costs nothing — but budget planning should assume Apify for the majority.

### Expected split

| Category | Records | Likely free | Likely paid |
|----------|---------|-------------|-------------|
| ICP dimensions (queued) | 17 | ~2-3 | ~14-15 |
| Stale refresh (queued) | 2 | ~0-1 | ~1-2 |
| **Total actionable** | **19** | **~2-4** | **~15-17** |

The free-leg estimate is based on 0/5 probe success, adjusted slightly upward because the probe sample was small and included `hotmail.fi` (not a real company site).

---

## Key Findings

1. **The research gap is smaller than it looks.** 343 records have no evidence, but 326 of them do not need it — structured data from ContactOut already covers their hook, angle, or ICP verdict. Only 23 records genuinely need research.

2. **All 23 are pre-ICP.** None have been qualified or rejected. Research is the input that enables the ICP verdict, not a nice-to-have for companies already decided.

3. **6 dropped records should not be crawled.** They have stale `team` evidence but are dropped, so research would produce no downstream consumer.

4. **The free leg is unlikely to suffice.** 0/5 probe domains returned usable pages. The domains in this cohort appear to be small companies with poor web presence, JS-heavy sites, or domains that do not resolve. Budget for Apify.

5. **`hotmail.fi` is a data-quality issue.** It is an email domain, not a company website. It should be investigated before spending credits on it.

6. **The boilerplate filter is working.** 0.4% of rows are boilerplate, down from the 34% measured before `evidence.boilerplate()` was deployed.

---

## Recommended Claude Action

1. Run the free leg (`webfetch`) for all 19 actionable records first — it costs nothing.
2. Run Apify for the records where the free leg fails (expected: ~15-17 records).
3. Skip `hotmail.fi` until its domain is verified as a company site.
4. Do not crawl the 4 dropped records.
5. After research, re-run ICP scoring on the 17 ICP-dimension records to settle their verdicts.
