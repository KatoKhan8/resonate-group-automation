# What One Fact Unblocks

**Date:** 2026-09-16
**Task:** TASK-199
**Snapshot:** 2026-09-15T17:52:12+00:00 from master cf23154 (550 records)

## 1. The Three Counts and Their Overlap

| Count | Predicate | Number |
|-------|-----------|--------|
| A. Blocked at ICP | `geography` or `company_type` in `unknown_criteria` from `icpstructural.structural()` | **349** |
| B. Blocked at generation | state in (verified, held) AND zero research rows with quality medium/strong | **20** |
| C. Overlap (both) | A AND B | **0** |

**The overlap is zero.** These are sequential pipeline stages, not parallel
gates. A record blocked at ICP sits in `review` and never reaches `verified`
- no person credits are spent on it. A record blocked at generation already
passed ICP (all 20 have `icp_pass_with_uncertainty`) and had person credits
spent, but has no usable research for copy.

**ICP breakdown (349 records):**
- geography UNKNOWN: 335
- company_type UNKNOWN: 291
- both UNKNOWN: 277

The geography criterion is the tighter bottleneck: 14 records have
company_type resolved but geography unknown, while none have geography
resolved but company_type unknown.

## 2. What `check_evidence` Actually Requires

`check_evidence` is in `src/llm.py` line 804. It fires only for the
`persona_angle` step.

### The gate

```python
def check_evidence(evidence, rec):
    facts = fact_strings(rec)
    invented = [e for e in evidence if not traceable(e, facts)]
    if invented:
        raise SchemaError("evidence not traceable to the record: ...")
```

The model produces a JSON object with `angle` (string) and `evidence` (list
of strings). Each evidence string must be **traceable** to the record's fact
pool.

### The fact pool (`fact_strings`, line 585)

Strings are collected from these record fields:
- `company`, `domain`, `context`, `signal`, `sizing` - walked recursively
- `company_facts` - all values, emitted as `"key value"` pairs so the key
  stays adjacent to its value (e.g. `"employees 48"`, `"industry advertising"`)
- `contacts` - walked recursively
- `research[].fact` - the `fact` field of each research entry

**NOT included:** `hook` (model-generated, would self-certify), `diagnosis`
(model-generated free text), research row metadata (`source_url`, `provider`,
`retrieved_at`, `quality`, `field`).

### The traceability test (`traceable`, line 660)

Two rules, both must hold:

1. **Every number** in the claim must appear in some fact string.
2. **Every adjacent pair of content words** in the claim must be adjacent in
   ONE fact string. The claim's phrasing must be accounted for by a single
   fact, not assembled from vocabulary scattered across many.

A claim that says "raised a Series B" needs a fact containing those adjacent
words. A claim that says "48 employees" needs a fact containing "48" and a
fact where "employees" is adjacent to "48".

### What makes a research row "usable"

A research row has these fields:
```
source_url, field, fact, provider, content_hash, http_status, chars,
retrieved_at, record_id, quality
```

The `fact` field is what enters the fact pool. The `quality` field
(strong/medium/weak/unusable) determines whether the row is usable:
- **strong** or **medium**: usable, the fact enters the pool and can support
  traceable claims
- **weak**: not usable for persona_angle (too thin or stale), but the fact
  string IS in the pool via `fact_strings` which does not filter on quality
- **unusable**: boilerplate or navigation text, rejected by `evidence.boilerplate()`

**Critical nuance:** `fact_strings` walks ALL research rows regardless of
quality. So a record with only `weak` research rows still has those fact
strings in the pool. The generation failure for the 20 blocked records is
not that the pool is empty - it is that the pool lacks the SPECIFIC facts
the model needs to construct a traceable persona angle. Several of the 20
have 50-246 strings in their pool from company_facts alone.

### Why the 20 still fail

The 20 generation-blocked records have company_facts (industry, offices,
employees) producing 27-246 fact strings. But persona_angle needs a SPECIFIC
claim about the company tied to a contact's persona. The model tries to
produce evidence like "specializes in outdoor marketing" or "recently opened
a Denver office" - and the adjacent-word-pair test refuses these because no
single fact string in the pool contains that exact phrasing. The company_facts
values are structured data ("Marketing Services", office addresses), not
prose claims. Research rows with quality weak/unusable contain website
boilerplate that was rejected.

## 3. Do ICP and `check_evidence` Want the Same Evidence?

**Partially. They share company_facts but diverge on research.**

| Field | Serves ICP? | Serves check_evidence? |
|-------|-------------|----------------------|
| company_facts.industry | YES (company_type) | YES (fact pool) |
| company_facts.offices | YES (geography via ISO code) | YES (fact pool) |
| company_facts.employees | YES (employees criterion) | YES (fact pool) |
| company_facts.specialties | no | YES (fact pool) |
| company_facts.notable | no | YES (fact pool) |
| company_facts.revenue | no | YES (fact pool) |
| segment.country | YES (geography) | no (not in fact pool) |
| segment.business_model | YES (services, tracks_time) | no |
| research[].fact | no (ICP ignores research) | YES (fact pool, if quality >= medium) |

**One purchase CAN serve both gates** if it populates company_facts with
industry, offices, and employee data. Grok does this: it returns industry,
offices, employees_estimate, specialties, notable - all of which enter
company_facts and the fact pool. ContactOut company-info also does this in
principle, but TASK-185 measured it returning null for the 25 domains that
needed it most.

**But there is a gap:** company_facts provides structured data (an industry
string, an address, a headcount number). The persona_angle gate needs PROSE
claims - specific, phrased facts the model can cite. A record with
`company_facts.industry = "Advertising Services"` and
`company_facts.offices = ["7010 Santa Monica Blvd, Hollywood, CA, 90038, US"]`
passes ICP's geography and company_type, but the fact pool contains
`"industry advertising services"` and `"offices 7010 santa monica blvd..."` -
and the model must construct a persona angle whose adjacent word pairs match
those exact strings. This is achievable for generic claims ("advertising
agency in Hollywood") but fragile for specific ones.

Research rows with quality medium/strong provide the prose claims that make
persona_angle robust. They are the evidence check_evidence was designed
around, and company_facts alone is a partial substitute.

## 4. The Minimum Evidence to Unblock Both Ends

For a record with nothing (no company_facts, no research, no segment data):

### What ICP needs to move from review to qualified

The minimum eligible verdict is `icp_pass_with_uncertainty`, which requires
both DEFINING criteria (geography + company_type) to be PASS or
PASS_WITH_TOLERANCE.

| Field needed | Source | Cheapest provider | Cost |
|-------------|--------|-------------------|------|
| Country (ISO code or name matching include list) | Office address with trailing ISO code | Grok (returns offices with country) | $0.20/domain |
| Industry or vertical matching target list | Industry string containing agency keyword | Grok (returns industry) | included above |

**Minimum for ICP: one Grok call at $0.20**, returning offices and industry.

### What check_evidence needs to move persona_angle from fail to pass

The model needs fact strings it can construct traceable claims from. The
minimum is one research row with quality medium/strong containing a specific
prose fact about the company.

| Field needed | Source | Cheapest provider | Cost |
|-------------|--------|-------------------|------|
| Specific prose fact (specialty, notable achievement, recent development) | Grok returns specialties[], notable[], description | Grok | $0.20/domain |
| OR: populated company_facts with specialties/notable | Same Grok response, written to company_facts | included above | included |

**Minimum for check_evidence: the same Grok call at $0.20.**

### Combined minimum

| Record state | What it needs | Cheapest source | Per-record cost |
|-------------|---------------|-----------------|-----------------|
| Nothing at all | industry + offices + specialties/notable | Grok | **$0.20** |
| Has company_facts, no research | research rows with quality >= medium | Grok or webfetch | $0.20 or $0 |
| Has research (weak/unusable) | better research or company_facts expansion | Grok | $0.20 |

**The cheapest combination is one Grok call per record at $0.20.** It returns
industry, offices, employees_estimate, specialties, notable, description, and
source URLs for each - satisfying both ICP's geography/company_type criteria
and providing the prose facts check_evidence needs.

For the 349 ICP-blocked records: 349 x $0.20 = **$69.80**
For the 20 generation-blocked records: 20 x $0.20 = **$4.00**
Overlap is zero, so no double-counting adjustment needed.
Total to unblock everyone: **$73.80**

But TASK-185 showed ContactOut company-info (1 credit/record) moved zero
verdicts on 50 records because it returned null for the domains that needed
it. Grok's advantage is that it searches the web rather than looking up a
database, so it reaches domains ContactOut does not know. TASK-192 is
measuring whether Grok actually moves verdicts on 25 records.

### webfetch: the free leg

`src/webfetch.py` reads the company's own website directly, follows internal
links, classifies pages, and produces research rows. It is free (no provider
credits, no Apify compute units) and same-domain-only. TASK-166 found that 6
of 10 domains had zero usable free-crawl evidence - the free path cannot
reach news articles, registries, or directories.

For the 20 generation-blocked records: many already HAVE research rows from
webfetch, but they are quality weak/unusable (boilerplate, navigation text).
The free path has already been tried and produced insufficient evidence for
these domains. Grok's advantage is third-party sources.

## 5. How 20 Records Reached Verified With No Research

**The ordering defect.**

The pipeline is: `queued -> enriched -> verified -> drafted -> approved -> pushed`

The transition to `verified` is decided by `enrich.outcome()` (line 787):
```python
if any(c.get("sendable") for c in contacts):
    return "verified", None
```

This checks ONLY whether at least one contact has a confirmed sendable email
address. It does NOT check:
- Whether research rows exist or are usable
- Whether company_facts has industry, offices, or employees
- Whether the ICP verdict is qualified
- Whether fact_strings has enough material for traceable claims

**The sequence that produced the defect:**

1. Record enters `queued` with a domain
2. `enrich.run()` calls ContactOut for people-count (free) and
   decision-makers (10 credits + email verification)
3. ContactOut finds contacts and emails at the domain
4. Email verification passes (deliverable/reoon, 1 credit each)
5. `outcome()` sees sendable contacts -> returns `verified`
6. Person credits spent: ~12+ per record (decision-makers + verifications)
7. No research was gathered. No company_facts beyond ContactOut's basic
   structured data. No prose facts for persona_angle.
8. Record sits in `verified` with contacts but nothing to write about.

**This is confirmed by the data:** all 20 generation-blocked records have
`icp_pass_with_uncertainty` (geography and company_type both PASS from
ContactOut's structured data), and all have zero usable research rows. The
ContactOut company-info call returned industry and offices (enough for ICP)
but no prose facts (nothing for persona_angle).

**The cheapest fix is an ordering change, not a purchase.**

Before spending person credits on decision-makers, check whether the record
has enough evidence to support copy:
- At least one research row with quality >= medium, OR
- company_facts with at least one of: specialties, notable (prose facts)

If neither condition holds, the record should not advance to person-level
enrichment. It should either:
1. Get a research call first (webfetch for free, Grok for $0.20)
2. Be held until evidence is available

**Cost of the ordering fix: zero provider credits.** It is a gate in
`enrich.run()` that checks evidence before calling decision-makers. The
existing `research.why()` function already computes whether a record needs
public evidence - the gate just needs to enforce it before person credits
are spent rather than after.

**The scale of the waste:** 20 records x ~12 credits each = ~240 credits
spent on contacts at companies where copy cannot be generated. TASK-169
measured that two thirds of enrichment spend produces nothing campaign-ready;
this is one mechanism by which that happens.

## Summary

| Question | Answer |
|----------|--------|
| Records blocked at ICP | 349 (geography or company_type UNKNOWN) |
| Records blocked at generation | 20 (verified/held, 0 usable research) |
| Overlap | 0 (sequential stages, not parallel gates) |
| What check_evidence requires | Each evidence string traceable to fact_strings: adjacent word pairs in ONE fact, every number in some fact |
| Do ICP and check_evidence want the same evidence? | Partially: company_facts serves both, research serves only check_evidence |
| Minimum to unblock both ends | One Grok call at $0.20/domain (industry + offices + specialties) |
| How 20 reached verified with no research | Ordering defect: person credits spent before evidence gathered |
| Cheapest fix | Gate person-level enrichment on evidence availability (costs nothing) |
