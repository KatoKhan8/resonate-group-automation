# Geography Discarded: Office Data That Produced No Verdict

**Date:** 2026-09-16  
**Task:** TASK-193  
**Snapshot:** 2026-09-15T19:52:12+00:00 from master cf23154 (550 records)

## Executive Summary

TASK-185 bought company-info for 25 records and moved zero verdicts. One line of its result explained why:

> geography: 0 resolved. Offices returned are in countries not on the client's include list (UA, CY, RU, etc.)

This report traces the code path, confirms whether it is a defect or design, and counts what it is worth.

**The answer: it is a design decision, not a defect. The code deliberately treats "country not on include list" as UNKNOWN rather than FAIL. There is also a secondary data gap: 17 ISO codes are missing from the lookup table, affecting 21 records.**

**The count: if office data were allowed to produce FAIL, 23 records would be cleanly rejected. Of those, 0 are currently in icp_review (8 are already dropped, 15 are in queued state).**

## The Code Path

### 1. resolve_country() at lines 165-175 of icpstructural.py

```python
def resolve_country(rec, segment):
    """(name, source). The segment first, then the office lines."""
    if segment.get("country"):
        return segment["country"], "segment.country"
    code = _norm(segment.get("country_code")).upper()
    if code in ISO_TO_NAME:
        return ISO_TO_NAME[code], "segment.country_code"
    for line in (rec.get("company_facts") or {}).get("offices") or ():
        token = str(line).strip().rstrip(".").split(",")[-1].strip().upper()
        if token in ISO_TO_NAME:
            return ISO_TO_NAME[token], "company_facts.offices"
    return None, None
```

The function:
1. Checks `segment.country` first
2. Then `segment.country_code` (mapped through ISO_TO_NAME)
3. Then iterates `company_facts.offices`, extracting the last token (ISO code) from each office line
4. Returns `(country_name, source)` or `(None, None)`

### 2. _geography() at lines 291-313 of icpstructural.py

```python
def _geography(rec, segment, rules):
    include = {_norm(g) for g in rules["include_geos"]}
    exclude = {_norm(g) for g in rules["exclude_geos"]}
    if not include and not exclude:
        return _answer(NOT_REQUIRED, "this client declares no geography rule")
    country, source = resolve_country(rec, segment)
    region = segment.get("region")
    pairs = ((country, source), (region, "segment.region"))
    for label, where in pairs:
        if label and _norm(label) in exclude:
            return _answer(FAIL, "%r is on the client's exclude list" % label,
                           source=where)
    for label, where in pairs:
        if label and _norm(label) in include:
            return _answer(PASS, "%r is a market this client sells to" % label,
                           source=where)
    if not country and not _norm(region):
        return _answer(UNKNOWN, "no usable location evidence anywhere on the "
                                "record; absence of a country is not evidence "
                                "of an excluded one")
    return _answer(UNKNOWN,
                   "%r is on neither list, so it is unestablished rather than "
                   "excluded" % (country or region),
                   source=source or "segment.region")
```

The logic:
- Lines 298-301: If country in EXCLUDE list → **FAIL**
- Lines 302-305: If country in INCLUDE list → **PASS**
- Lines 306-309: If no country found → **UNKNOWN**
- Lines 310-313: If country found but NOT on either list → **UNKNOWN** with message "is on neither list, so it is unestablished rather than excluded"

## The Findings

### Finding 1: Two Issues, Not One

**Issue A: 17 ISO codes are missing from ISO_TO_NAME**

The ISO_TO_NAME dictionary at lines 149-163 includes 34 country codes but is missing 17 that appear in the office data:

- CZ (Czech Republic): 4 records
- GR (Greece): 3 records
- CY (Cyprus): 3 records
- RS (Serbia): 2 records
- SS (South Sudan): 2 records
- UA (Ukraine): 1 record
- AR (Argentina): 1 record
- HU (Hungary): 1 record
- JO (Jordan): 1 record
- SI (Slovenia): 1 record
- LT (Lithuania): 1 record
- EE (Estonia): 1 record
- ZA (South Africa): 1 record
- MC (Monaco): 1 record
- RU (Russia): 1 record
- TN (Tunisia): 1 record
- MX (Mexico): 1 record

**Total: 21 records affected.** Offices in these countries do not resolve to a country at all, because the ISO code is not in the lookup table.

**Issue B: Design decision - "not on include list" → UNKNOWN, not FAIL**

Even when a country IS resolved (e.g., China, India, UAE), if it is not on the client's include list, the code returns UNKNOWN rather than FAIL. The reasoning is in the module docstring:

> UNKNOWN is not FAIL, and that is the whole point.
>
> A criterion this system could not establish leaves the company eligible with uncertainty. Only affirmative evidence of a violation fails it.
>
> FAIL     we know this company does not fit  
> UNKNOWN  we could not establish it

The code also notes:

> location_why: no usable location evidence is not evidence of being in an excluded country

### Finding 2: Defect or Design?

**DESIGN.** The code is doing exactly what it was designed to do.

The rationale is that an office list may be incomplete, a company headquartered outside the include list may still deliver inside it, and a single office in Cyprus may be a holding company. The system prefers to leave the company eligible with uncertainty rather than reject it on partial or inferred data.

This is consistent with the rule from TASK-190: "an inference may move a criterion from UNKNOWN to PASS and never to FAIL" - though TASK-190 is about free evidence, the principle is the same.

### Finding 3: Which of the Four Discard Shapes?

The task asked: if it IS a defect, was the office data:
1. Never written to `company_facts`?
2. Written under a key the criterion does not read?
3. Written in a shape it could not parse?
4. Read and deliberately ignored?

**The answer: the third shape - "written in a shape it could not parse" - but only for the 21 records with missing ISO codes.**

- The office data IS written to `company_facts.offices` ✓
- The criterion DOES read it (resolve_country iterates offices) ✓
- The ISO code extraction FAILS for 17 codes not in ISO_TO_NAME ✗

For the remaining records (where the ISO code IS in the map), the data is read and deliberately treated as UNKNOWN rather than FAIL - which is the fourth shape, but is a design decision, not a defect.

### Finding 4: The Count

**Current state (as-is):**
- PASS: 212 records
- FAIL: 3 records
- UNKNOWN: 335 records

**Hypothetical: if missing ISO codes were added AND office data could produce FAIL:**
- 23 records would FAIL (of 550 total)
- 0 of those are in icp_review
- 8 are already dropped
- 15 are in queued state

**Breakdown by reason:**
- 20 records: country not on include list
- 3 records: country on exclude list (already FAIL)

**Countries that would cause rejection:**
- Greece: 2 records
- Cyprus: 2 records
- Czech Republic: 2 records
- Ukraine: 1 record
- China: 1 record
- Argentina: 1 record
- Hungary: 1 record
- United Arab Emirates: 1 record
- Jordan: 1 record
- Slovenia: 1 record
- Lithuania: 1 record
- Estonia: 1 record
- South Africa: 1 record
- Monaco: 1 record
- India: 1 record
- Serbia: 1 record
- Russia: 1 record
- South Sudan: 1 record
- England: 1 record (note: "england" is not in the include list, only "United Kingdom")

### Finding 5: How This Differs from TLD Inference Producing FAIL

**It does not differ.** The principle is the same: "an inference may move a criterion from UNKNOWN to PASS and never to FAIL."

Office data is inference (the company has an office there, but may operate elsewhere), just like a TLD is inference (the domain is .ua, but the company may operate elsewhere).

The difference is that office data is MORE concrete than a TLD - a physical office is a stronger signal than a domain registration. But the principle still applies: a company with an office in Ukraine may still deliver services in Germany, and rejecting it permanently on the strength of one office record is the risk the design avoids.

## The Value

If office data were allowed to produce FAIL:
- 23 records would be cleanly rejected
- 0 would move from icp_review to icp_fail (none of the 23 are in review)
- 8 are already dropped (no throughput gain)
- 15 are in queued state (would be rejected before entering the pipeline)

**The throughput gain is 15 records that would be rejected earlier in the pipeline, saving the cost of processing them.**

But the risk is that a company with an office in Ukraine may still deliver services in the client's target markets, and rejecting it permanently on the strength of one office record is a loss the design avoids.

## Conclusion

1. **The code path:** `resolve_country()` reads `company_facts.offices`, extracts ISO codes, and `_geography()` uses the resolved country.

2. **Defect or design:** DESIGN. The code deliberately treats "country not on include list" as UNKNOWN, not FAIL.

3. **Which discard shape:** The third shape (written in a shape it could not parse) for 21 records with missing ISO codes. The fourth shape (read and deliberately ignored) for the rest, but that is a design decision.

4. **The count:** 23 records would FAIL if office data could produce FAIL. Of those, 0 are in icp_review, 8 are dropped, 15 are queued.

5. **Not fixed in this task**, as instructed. A change that lets a criterion produce FAIL from inferred or partial data can reject a good company permanently, and `icp_fail` is terminal.

6. **How this differs from TLD inference producing FAIL:** It does not. The principle is the same.

## Recommendations

1. **Add the missing 17 ISO codes to ISO_TO_NAME.** This is a data gap, not a design decision, and fixing it allows the criterion to resolve more countries. This does not change the UNKNOWN-vs-FAIL behavior.

2. **Do not change the UNKNOWN-vs-FAIL behavior** without operator approval. The design avoids rejecting companies on partial data, and `icp_fail` is terminal.

3. **Consider whether "england" should map to "United Kingdom"** in the geography logic. One record has offices in England (GB) but the segment.country is "england", which is not in the include list. This is a separate issue from the ISO codes.

4. **The 15 queued records that would FAIL** represent throughput gain if the design changes. But the risk of false rejection is real, and the operator should decide.

## Appendix: TASK-185 Round 2 Records

The 25 records TASK-185 processed with company-info:

| Domain | Offices | Countries | Geography |
|--------|---------|-----------|-----------|
| px-bbb9723646bc | England, GB | United Kingdom | UNKNOWN (segment.country="england") |
| ontario.ca | Ontario, CA; Toronto, CA | Canada | PASS |
| puffandfluffspa.com | 4 offices in Arizona, US | United States | PASS |
| directarrowgroup.com | La Jolla, CA, US | United States | PASS |
| sanders-plumbing.com | Powell, Wyoming, US | United States | PASS |
| brightconcepts.net | Aurora, CO, US; Elkridge, MD, US | United States | PASS |
| muros.co | Chicago, IL, US | United States | PASS |
| (18 more) | (various) | (various) | (various) |

Of the 25 records:
- 7 are shown above (all PASS except px-bbb9723646bc)
- 18 more were processed but not shown in the output
- 0 moved from UNKNOWN to FAIL
- 1 (px-bbb9723646bc) has offices in the UK but segment.country="england", which is not in the include list

## Script Output

The analysis scripts are in `scripts/task193_*.py`:
- `task193_geography_analysis.py` - initial analysis
- `task193_missing_iso_codes.py` - missing ISO codes
- `task193_comprehensive_analysis.py` - comprehensive scenario analysis
