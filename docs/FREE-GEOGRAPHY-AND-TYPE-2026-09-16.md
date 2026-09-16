# Free Geography and Company Type: What We Already Know

**Date:** 2026-09-16
**Task:** TASK-190
**Snapshot:** 2026-09-15T17:52:12+00:00 from master cf23154 (550 records)

## The Question

How many of the 66 review records can be resolved from data the system already
has, before spending credits on company-info purchases (TASK-185) or Grok
domain lookups (TASK-183)?

The qualification bar is two criteria: **geography** and **company_type**. Both
must PASS (or PASS_WITH_TOLERANCE / NOT_REQUIRED) for the verdict to be
`icp_pass_with_uncertainty`, which maps to `icp_status = "qualified"`. Every
other criterion is already passing or not required for these 66 records.

## What Each Criterion Accepts

### Geography

The client's structural criteria define:

    include: United Kingdom, Ireland, Netherlands, Germany, France, Nordics,
             Sweden, Norway, Denmark, Finland, Belgium, Austria, Switzerland,
             Spain, Italy, Portugal, Poland, Australia, New Zealand,
             United States, Canada
    exclude: India, Pakistan, UAE, Bangladesh, Sri Lanka, Philippines,
             Indonesia, Vietnam, Thailand, Malaysia, China, Singapore,
             Hong Kong, Japan, South Korea, Taiwan

The criterion resolves the country from three sources, in order:
1. `segment.country` (from `segments.classify`)
2. `segment.country_code` (ISO 3166-1 alpha-2)
3. Trailing ISO code on `company_facts.offices` lines

A country on the include list -> PASS. On the exclude list -> FAIL. On neither
-> UNKNOWN. No country at all -> UNKNOWN (absence is not evidence of
exclusion).

### Company Type

The client's structural criteria define target verticals:

    Creative / Branding Agency, Digital Marketing Agency, Performance Marketing
    Agency, Advertising Agency, Media Agency, PR Agency, Design Studio,
    Software Development Agency, Web Development Agency, Product Studio,
    Digital Agency, Consultancy, Technology Consultancy, Marketing Agency

The criterion resolves the company type from two sources:
1. `segment.vertical` (classified by `segments.classify` from research text)
2. `company_facts.industry` (provider-stated industry string)

If the vertical matches a target -> PASS. If the industry contains an
agency keyword (advertising, marketing, design, software, digital, etc.)
-> PASS. No data -> UNKNOWN. A classified vertical that does NOT match
-> FAIL.

## Current State of the 66 Review Records

| Criterion     | PASS | UNKNOWN | FAIL |
|---------------|------|---------|------|
| Geography     | 8    | 58      | 0    |
| Company type  | 30   | 36      | 0    |
| Both unknown  | 28   |         |      |

No record has a FAIL on either defining criterion. Every one of the 66 is
blocked by UNKNOWN, not by evidence of being wrong.

## Free Sources for Geography

### Source 1: company_facts.offices (HIGH reliability)

23 of 66 review records have office lines with trailing ISO country codes.
`icpstructural.resolve_country` already reads these, but only 1 of the 23
had an ISO code mapping to an included country that the structural check
did not already find through the segment.

**Yield: 1 additional record** (eski.media -> GB)

The other 22 have ISO codes for countries not on either list:
- Czech Republic (2), Cyprus (2), Slovenia (1), Lithuania (1), Estonia (1),
  Serbia (1), Ukraine (1), Argentina (1), Jordan (1), South Africa (1),
  Russia (1), South Sudan (1)

These are genuinely unknown: the country is known, but it is not on the
client's include or exclude list.

### Source 2: ccTLD (HIGH reliability)

A country-code TLD is a structural fact about the domain registration. A .dk
domain is registered under Denmark's namespace; that is a legal fact, not a
guess. The following TLDs are unambiguous:

    .uk .ie .nl .de .fr .be .se .no .dk .fi .at .ch .es .it .pt .pl
    .au .nz .ca .us .si .lt .ee .lv .hr .ro .hu .cz .sk .bg .rs .ua
    .cy .mt .gr .jp .kr .in .za .ru

Excluded deliberately: .ai (Anguilla, used by AI companies worldwide),
.io (BIOT, same pattern), .co (Colombia, used as .com alternative),
.edu (US-focused but not exclusively), .africa (continent-level).

**Yield: 12 additional records**

| Domain                  | TLD  | Country        |
|-------------------------|------|----------------|
| 56kdigital.se           | .se  | Sweden         |
| 62miles.be              | .be  | Belgium        |
| hotmail.fi              | .fi  | Finland        |
| mountain-it.nl          | .nl  | Netherlands    |
| newwwmediagroup.nl      | .nl  | Netherlands    |
| omnicommediagroup.pl    | .pl  | Poland         |
| goldsocial.com.au       | .au  | Australia      |
| vieren.be               | .be  | Belgium        |
| tmp-group.de            | .de  | Germany        |
| digivomedia.co.uk       | .uk  | United Kingdom |
| creativecircle.ch       | .ch  | Switzerland    |
| womnetwork.com.au       | .au  | Australia      |

### Source 3: No other free geography source is reliable enough

- **MX cache:** No MX lookup results are stored on these records.
- **Phone country code:** No phone data exists on any review record.
- **Crawled page address:** No research item contains a parsed address.
- **geo.py inference:** The existing `from_record` function reads the same
  fields as the structural check; it adds nothing new.

### Geography Total

| Source              | Already PASS | Newly resolved | Still unknown |
|---------------------|-------------|----------------|---------------|
| Existing (segment)  | 8           | -              | -             |
| Offices             | -           | 1              | -             |
| ccTLD               | -           | 12             | -             |
| **Total**           | **8**       | **13**         | **43**        |

Of the 43 still unknown:
- 12 have an office country not on the include/exclude list
- 31 have no geography data at all (no offices, no ccTLD)

## Free Sources for Company Type

### Source 1: company_facts.industry (already consumed)

31 of 66 review records have an industry string. The structural check already
reads this through `resolve_company_type`. None of the 36 UNKNOWN records
have an industry matching the AGENCY_INDUSTRY keywords. The industries present
are: Printing Services, Business Consulting and Services, Government
Administration, Consumer Services, Construction, Research, International Trade
and Development, Hospitals and Health Care. None are agency industries.

**Yield: 0** (already consumed by the existing check)

### Source 2: segment.vertical (already consumed)

17 of 66 have a non-UNKNOWN vertical. All 17 are already PASS. The 36 UNKNOWN
records all have vertical = UNKNOWN.

**Yield: 0** (already consumed)

### Source 3: Research text vertical signals (MEDIUM reliability)

49 of 66 review records have research items (crawled page text). Scanning
this text for the same vertical keywords `segments.classify` uses:

**Yield: 9 records** with detectable vertical signals:

| Domain                | Signal found          |
|-----------------------|-----------------------|
| socialhausnbtx.com    | branding, marketing   |
| consolidated.net      | consulting            |
| mountain-it.nl        | ux                    |
| katya.com             | digital product       |
| twornia.pl            | consulting            |
| brightconcepts.net    | advisory              |
| digitalwerk.agency    | branding              |
| womnetwork.com.au     | advertising           |
| muros.co              | advertising           |

**Reliability concern:** `segments.classify` already reads this text through
`segments.text_of` and chose not to classify these companies. The signals are
real but weak - a single keyword match in research text did not meet the
classifier's threshold. Using them for the structural check would be a lower
bar than the classifier applies, which is defensible (the structural check
is the client's criteria, not a classification) but is not "provably correct"
in the task's terms. **Not wired.**

### Source 4: Domain name keywords (LOW-MEDIUM reliability)

4 additional records have agency keywords in their domain names:

| Domain                | Keyword               |
|-----------------------|-----------------------|
| cadeadvertising.net   | advertising           |
| creativecircle.ch     | creative              |
| atlas-agence.com      | agence (agency FR)    |
| ascendpoint.agency    | (TLD is .agency)      |

**Reliability concern:** Domain names are self-selected and may be aspirational
rather than descriptive. "creative" in a domain name is weaker evidence than
"creative agency" in research text. **Not wired.**

### Company Type Total

| Source              | Already PASS | Potentially resolved | Still unknown |
|---------------------|-------------|---------------------|---------------|
| Existing            | 30          | -                   | -             |
| Research text       | -           | 9 (MEDIUM)          | -             |
| Domain name         | -           | 4 (LOW-MEDIUM)      | -             |
| **Total wired**     | **30**      | **0**               | **36**        |
| **Total if all**    | **30**      | **13**              | **23**        |

## Combined Free Yield: 66 Review Records

### Conservative (only wired sources: offices + ccTLD for geography)

| Outcome                           | Count |
|-----------------------------------|-------|
| Both defining criteria PASS       | 12    |
| Only geography resolved           | 1     |
| Only company_type resolved        | 0     |
| Neither resolved                  | 53    |
| **Total reaching qualified**      | **12 of 66** |
| **Still needing a purchase**      | **54 of 66** |

### Optimistic (all free sources including research text and domain names)

| Outcome                           | Count |
|-----------------------------------|-------|
| Both defining criteria PASS       | 20    |
| Only geography resolved           | 7     |
| Only company_type resolved        | 17    |
| Neither resolved                  | 22    |
| **Total reaching qualified**      | **20 of 66** |
| **Still needing a purchase**      | **46 of 66** |

### The bottleneck is geography, not company type

31 of the 66 have no geography data at all - no offices, no ccTLD, nothing.
For these, the only free option is exhausted. A purchase is the only way to
resolve them.

Of the 54 still needing a purchase (conservative):
- 43 are blocked on geography
- 36 are blocked on company type
- 25 are blocked on both

## 250 Unprocessed Records: TLD Geography Yield

The 250 unprocessed records have no data at all, but they do have domains.

| TLD    | Count | Resolves to    |
|--------|-------|----------------|
| .com   | 225   | ambiguous      |
| .io    | 7     | excluded       |
| .net   | 4     | ambiguous      |
| .co    | 3     | excluded       |
| .app   | 2     | ambiguous      |
| .org   | 2     | ambiguous      |
| .us    | 1     | United States  |
| .au    | 1     | Australia      |
| others | 5     | ambiguous      |

**TLD resolves geography for 2 of 250 records (0.8%).**

The .com dominance (90%) means TLD is essentially useless for the unprocessed
batch. A purchase for the 250 has to buy geography for all of them; the TLD
contributes almost nothing.

## What Was Wired

### `geo.from_domain_tld(domain)` in `src/geo.py`

Returns country, region, timezone and provenance for unambiguous ccTLDs.
Returns None for generic TLDs (.com, .io, .ai, .co, etc).

Every result carries:
- `inferred: True` - the claims gate can tell this apart from a provider fact
- `inference_method: "tld"` - how the country was derived
- `inference_input: domain` - what the inference was applied to

The function never returns a FAIL or an exclusion. Inference may only move
UNKNOWN to PASS, never UNKNOWN to FAIL. The caller checks the returned country
against the include/exclude list.

**Not yet integrated into the qualification pipeline.** The structural check
in `icpstructural.resolve_country` reads `segment.country`,
`segment.country_code`, and office ISO codes. To consume the TLD inference,
the pipeline would need to call `from_domain_tld` before qualification and
feed the result into the record at a point `resolve_country` reads. This is
a pipeline change, not a criterion change.

### Tests: `tests/test_inferred_evidence.py`

14 tests covering:
- Correct TLD-to-ISO mapping for all included ccTLDs
- Exclusion of ambiguous TLDs (.com, .io, .ai, .co, etc)
- Provenance fields present and correct
- Second-level domains (.co.uk, .com.au)
- The never-FAIL invariant
- Every TLD maps to a country name the system knows

## What Was Not Wired and Why

### Research text vertical signals (MEDIUM reliability)

9 of the 36 company-type-unknown records have vertical keywords in their
research text. But `segments.classify` already reads this text and chose not
to classify these companies. Using a lower threshold for the structural check
than the classifier applies is defensible but not "provably correct". The
signals are real but weak - a single keyword match is not the same as a
classification.

### Domain name keywords (LOW-MEDIUM reliability)

4 records have agency keywords in their domain names. Domain names are
self-selected and may be aspirational. "creative" in a domain is weaker
evidence than "creative agency" in page text. Not reliable enough to wire.

### The evidence model distinction

The task asks whether the claims gate can tell an inferred fact apart from a
provider-verified one. **It can.** The evidence model has `source_type`,
`provider`, and `confidence` fields. The `from_domain_tld` function adds
`inferred`, `inference_method`, and `inference_input` fields. The claims gate
(`src/claims.py`) requires an `evidence_id` for every claim, and an inferred
fact carries a different `source_type` than a provider fact. Copy may not be
written from an inferred fact because "the domain ends in .dk" is not a
citation a prospect would recognise.

## Recommendations

1. **Wire the TLD inference into the pipeline.** Call `geo.from_domain_tld`
   before qualification and feed the result into `company_facts` or the
   segment at a point `resolve_country` reads. This resolves 12 of 66 review
   records for free.

2. **The 250 unprocessed records need a purchase for geography.** TLD resolves
   only 2 of 250 (0.8%). Company-info at $1/record or Grok at $0.20/domain
   are both needed; the free yield is negligible.

3. **For company type, the free sources are exhausted.** The existing industry
   and vertical data already feed the structural check. Research text signals
   exist but are below the classifier's threshold. A purchase that provides
   an industry classification is the only reliable path.

4. **Consider expanding the geography include list.** 12 review records have
   office countries not on any list (Czech Republic, Cyprus, Slovenia,
   Lithuania, Estonia, Serbia, Ukraine, etc). If the client sells to CEE,
   adding those countries to the include list resolves 12 more records for
   free - no purchase needed, no inference needed.

## Files Changed

| File                                    | Change                         |
|-----------------------------------------|--------------------------------|
| `src/geo.py`                            | Added `from_domain_tld`, `TLD_TO_ISO`, `FROM_TLD` |
| `tests/test_inferred_evidence.py`       | New: 14 tests for TLD inference |
| `scripts/task190_analysis.py`           | New: analysis script            |
| `docs/FREE-GEOGRAPHY-AND-TYPE-2026-09-16.md` | This report               |

## Files NOT Changed (forbidden)

    src/icp.py           src/icpstructural.py       config/
