# Cohort design: what the evidence actually supports

Measured 2026-09-15 against `work/queue.snapshot.jsonl`.
**Snapshot stamp: `2026-09-14T21:52:15Z  from master 0ac5e60  300 records`**

Analysis script: `scripts/task140_cohort_analysis.py`

---

## 1. The eligible population

The task title says 248. That number comes from the live queue (550 records):
277 contacts with LinkedIn profiles minus 29 with prior EmailBison outreach
(COHORT-HEADROOM-2026-09-15.md). The snapshot is 300 records, a subset.

**On the snapshot, the eligible population is 92 contacts** with a LinkedIn
profile on a non-dropped record. Of those, 56 are sendable (verified email).
The remaining 36 are in records that have not completed enrichment.

This document analyses all 92. Cohort design must cover the full eligible
pool, not only the 56 who are sendable today, because the 36 will become
sendable as enrichment completes and the cohort boundaries should not need
redrawing for each batch.

---

## 2. Dimension distributions

Every candidate grouping dimension, measured across the 92 eligible contacts.

### 2.1 Dimensions with full coverage (100%)

| Dimension | Distinct values | Distribution |
|-----------|----------------|--------------|
| **persona** | 2 | economic_buyer 72 (78.3%), champion 20 (21.7%) |
| **vertical** | 7 | UNKNOWN 35 (38.0%), Creative/Branding Agency 23 (25.0%), Digital Marketing Agency 14 (15.2%), Performance Marketing Agency 13 (14.1%), Software Dev Agency 4 (4.3%), SEO Agency 2 (2.2%), Consulting 1 (1.1%) |
| **business_model** | 4 | agency 52 (56.5%), UNKNOWN 35 (38.0%), hybrid 4 (4.3%), consultancy 1 (1.1%) |
| **employee_band** | 7 | 10_19: 27 (29.3%), 20_49: 22 (23.9%), 50_99: 17 (18.5%), 1_9: 16 (17.4%), 100_199: 5 (5.4%), 200_499: 3 (3.3%), 1000_PLUS: 2 (2.2%) |
| **persona_strategy** | 4 | founder_led 43 (46.7%), operations_led 43 (46.7%), finance_led 5 (5.4%), delivery_led 1 (1.1%) |
| **industry** | 6 | Advertising Services 54 (58.7%), Marketing & Advertising 18 (19.6%), Marketing Services 16 (17.4%), Design Services 2 (2.2%), Translation 1, Consulting 1 |
| **region** | 12 | Other 61 (66.3%), US East 7 (7.6%), UK 6 (6.5%), US Central 5 (5.4%), DACH 4 (4.3%), rest <3 each |
| **company_maturity** | 5 | established 38 (41.3%), mature 26 (28.3%), UNKNOWN 19 (20.7%), growing 7 (7.6%), startup 2 (2.2%) |
| **distributed** | 2 | False 72 (78.3%), True 20 (21.7%) |
| **office_count** | 6 | 1: 72 (78.3%), 2: 11 (12.0%), 3-10: 9 (9.8%) |

### 2.2 Dimensions with partial coverage

| Dimension | Coverage | Distinct values | Note |
|-----------|----------|----------------|------|
| **angle** | 88.0% (81/92) | 6 | founder 47, operations 23, delivery 7, finance 2, economic_buyer 1, growth 1 |
| **recommended_angles** | 38.0% (35/92) | 7 | (resource_planning, delivery_visibility) 22, (resource_planning,) 6, rest <3 |
| **relevant_pain_categories** | 38.0% (35/92) | 7 | Same distribution as recommended_angles |
| **country_code** | 33.7% (31/92) | 11 | US 13, GB 4, rest <3 each |
| **city** | 33.7% (31/92) | 18 | Too many distinct values for grouping |
| **timezone** | 33.7% (31/92) | 13 | Too many distinct values for grouping |
| **employee_range** (raw) | 19.6% (18/92) | 3 | Too sparse |

### 2.3 Dimensions with zero coverage

| Dimension | Coverage | Why |
|-----------|----------|-----|
| **signal** | 0% (0/92) | Empty on all eligible records |
| **icp_confidence** | 0% (0/92) | Not populated on eligible records |
| **icp_grade** | 0% (0/92) | Not populated on eligible records |
| **subvertical** | 100% but 65.2% UNKNOWN | Not a grouping dimension |

---

## 3. Cross-tabs: which combinations reach usable sizes

### 3.1 vertical x persona

| Vertical | economic_buyer | champion | Total |
|----------|---------------|----------|-------|
| UNKNOWN | 32 | 3 | 35 |
| Creative/Branding Agency | 16 | 7 | 23 |
| Digital Marketing Agency | 10 | 4 | 14 |
| Performance Marketing Agency | 10 | 3 | 13 |
| Software Dev Agency | 2 | 2 | 4 |
| SEO Agency | 2 | 0 | 2 |
| Consulting | 0 | 1 | 1 |

**No combination reaches 25.** The largest is UNKNOWN + economic_buyer at 32,
but UNKNOWN is not a coherent group (see section 4). The largest KNOWN
vertical x persona combination is Creative/Branding Agency + economic_buyer
at 16.

### 3.2 vertical x persona_strategy

| Vertical | founder_led | operations_led | finance_led | delivery_led |
|----------|-------------|----------------|-------------|--------------|
| UNKNOWN | 24 | 11 | 0 | 0 |
| Creative/Branding Agency | 11 | 11 | 0 | 0 |
| Digital Marketing Agency | 3 | 10 | 0 | 0 |
| Performance Marketing Agency | 2 | 9 | 2 | 0 |
| Software Dev Agency | 3 | 0 | 0 | 1 |
| SEO Agency | 0 | 2 | 0 | 0 |

### 3.3 persona x employee_band

| Persona | 1_9 | 10_19 | 20_49 | 50_99 | 100_199 | 200_499 | 1000_PLUS |
|---------|-----|-------|-------|-------|---------|---------|-----------|
| economic_buyer | 16 | 23 | 16 | 9 | 3 | 3 | 2 |
| champion | 0 | 4 | 6 | 8 | 2 | 0 | 0 |

**economic_buyer + 10_19 is the largest cell at 23.** champion contacts are
concentrated in larger companies (50_99: 8, 20_49: 6).

### 3.4 persona x persona_strategy

| Persona | founder_led | operations_led | finance_led |
|---------|-------------|----------------|-------------|
| economic_buyer | 39 | 28 | 4 |
| champion | 4 | 15 | 0 |

**economic_buyer + founder_led at 39 is the largest two-dimension cell in the
entire estate.** This is the default: a founder or CEO at a small agency.

### 3.5 relevant_pain_categories x vertical

| Pain categories | UNKNOWN | Creative/Brand | Digital Mktg | Perf Mktg | Other |
|----------------|---------|----------------|--------------|-----------|-------|
| (none) | 28 | 6 | 6 | 11 | 6 |
| resource_planning, delivery_visibility | 0 | 15 | 7 | 0 | 0 |
| resource_planning | 4 | 0 | 0 | 0 | 2 |
| project_margin, budget_control | 0 | 0 | 0 | 2 | 0 |
| resource_planning, utilization | 2 | 0 | 0 | 0 | 0 |

**The pain categories only fire for Creative/Branding and Digital Marketing
agencies where the website evidence was rich enough.** Performance Marketing
agencies have no pain categories despite 13 contacts, because their websites
did not produce matching signals.

---

## 4. Evidenced vs inferred: the critical split

### 4.1 What is evidenced

| Dimension | Source | What is actually evidenced |
|-----------|--------|--------------------------|
| **persona** | ContactOut person discovery + title match against persona priority list | The TITLE is from LinkedIn (evidenced). The persona label is a classification of the title. |
| **industry** | LinkedIn company page | LinkedIn's own classification. Evidenced but not controlled by us. |
| **employee_band** | LinkedIn headcount or client export, banded by qualify.py | The headcount number is from LinkedIn. The band is derived. 7 conflicts and 64 disagreements across 300 records (PRODUCTION-SCALE-POLICY.md). |
| **region/country/city** | Office address from website or LinkedIn, parsed by qualify.py | The ADDRESS is evidenced where present. The region is a classification of the country. 66% have no usable location evidence. |
| **distributed** | office_count > 1 | Structural fact from office count. |

### 4.2 What is inferred

| Dimension | Source | What is actually inferred |
|-----------|--------|--------------------------|
| **vertical** | Classification of website text by qualify.py | The website text is evidenced; the vertical label is a classification. 38% of contacts have UNKNOWN vertical because no website crawl succeeded. |
| **business_model** | Classified from website text + industry | Agency vs product is a classification. |
| **persona_strategy** | Rule: employee_band -> strategy mapping | founder_led vs operations_led is a system decision based on size. |
| **recommended_angles** | vertical + evidence signal matching | The angles are system recommendations. The underlying signals (delivery_complexity, resource_planning_need) are evidenced from website text, but only fire for 38% of contacts. |
| **relevant_pain_categories** | Same as recommended_angles | Same coverage problem: 38%. |
| **icp_tier/score** | Composite score from multiple signals | A score, not an observable fact. |
| **company_maturity** | Classification from website + LinkedIn signals | established/mature/growing/startup is a classification. |

### 4.3 What this means for cohorts

**A cohort can be defined on inferred dimensions for the purpose of READING
an experiment result (CONTROL arm).** The question "do Creative/Branding
Agency founders respond differently from Performance Marketing Agency COOs?"
is a legitimate question even though both labels are classifications, because
the result is read at the cohort level, not asserted in copy.

**A cohort cannot be defined on inferred dimensions for the purpose of
CHANGING the message (CHALLENGER arm) unless the copy references only what is
evidenced per-contact.** Copy may reference a person's title (evidenced from
LinkedIn) but not their persona label. Copy may reference what a company does
(from their website) but not the vertical label. Copy may not reference a
pain category unless the underlying signal was extracted from that company's
own evidence.

---

## 5. The UNKNOWN vertical problem

35 of 92 eligible contacts (38.0%) have vertical = UNKNOWN. These are not a
cohort. They are the absence of one.

**Why they are UNKNOWN:** 32 of 35 have no research_outcome at all - the
website crawl never succeeded or was never attempted. The remaining 3 have
HTTP_SUCCESS but the text did not contain enough signal to classify.

**What we know about them:**
- All 35 are in Advertising Services, Marketing & Advertising, or Marketing Services (LinkedIn industry)
- 24 are founder_led, 11 are operations_led
- 32 are economic_buyer, 3 are champion
- They are spread across all employee bands

**They cannot be grouped by what the company does** because the evidence does
not exist. They CAN be grouped by persona, size, and region - but those
dimensions do not say what the company does.

**For CONTROL arm:** The UNKNOWN verticals can be included in a "vertical
unknown" cohort for reading the result. The question becomes "do companies
where we don't know the vertical respond differently?" - which is a useful
baseline.

**For CHALLENGER arm:** The UNKNOWN verticals cannot receive copy that
asserts anything about the company's business. The CONTROL fallback copy
(which asserts nothing) is the only honest option for these contacts until
research fills the gap.

---

## 6. Cohort proposal

### 6.1 The honest answer

No single dimension produces a cohort of 50. The largest coherent group on
any one dimension is:

- **economic_buyer**: 72 contacts (but this is 78% of the pool - it is the
  default, not a cohort)
- **Creative/Branding Agency**: 23 contacts (the largest vertical, but well
  below 50)
- **founder_led**: 43 contacts (but this is a restatement of "companies under
  50 people", which is 70.6% of the pool)

The estate is too homogeneous on some dimensions (95.7% advertising/marketing
services) and too sparse on others (38% UNKNOWN vertical, 66% region Other)
for any single dimension to produce a meaningful cohort of 50.

### 6.2 Proposed cohorts for CONTROL arm

The CONTROL arm uses fallback copy that asserts nothing about the recipient.
Cohorts here are for READING the result, not for changing the message.

**Cohort C1: Creative/Branding Agency - economic_buyer**
- Size: 16 contacts
- Dimensions: vertical = Creative/Branding Agency, persona = economic_buyer
- Evidence: vertical is inferred from website text; persona is classified from title
- What this cohort reads: do founder/CEO contacts at creative agencies respond
  differently from the baseline?
- Arm: CONTROL

**Cohort C2: Creative/Branding Agency - champion**
- Size: 7 contacts
- Dimensions: vertical = Creative/Branding Agency, persona = champion
- Evidence: same as C1
- What this cohort reads: do operations/delivery contacts at creative agencies
  respond differently from economic buyers at the same type of company?
- Arm: CONTROL
- Note: 7 is below the 10 minimum for a readable batch. Hold until accumulated
  or merge with C1 for a combined Creative/Branding read at 23.

**Cohort C3: Digital Marketing Agency**
- Size: 14 contacts (10 economic_buyer, 4 champion)
- Dimensions: vertical = Digital Marketing Agency
- Evidence: vertical inferred from website text
- What this cohort reads: do digital marketing agencies respond differently
  from creative agencies?
- Arm: CONTROL

**Cohort C4: Performance Marketing Agency**
- Size: 13 contacts (10 economic_buyer, 3 champion)
- Dimensions: vertical = Performance Marketing Agency
- Evidence: vertical inferred from website text
- What this cohort reads: do performance marketing agencies respond differently?
- Arm: CONTROL
- Note: These 13 have NO recommended_angles and NO pain categories despite
  having a vertical. Their websites did not produce matching signals. Copy
  cannot assert anything about their pains.

**Cohort C5: Vertical UNKNOWN**
- Size: 35 contacts (32 economic_buyer, 3 champion)
- Dimensions: vertical = UNKNOWN
- Evidence: none for vertical. persona and size are present.
- What this cohort reads: do companies where we don't know the vertical
  respond differently? This is the baseline for "what happens when the
  evidence is missing?"
- Arm: CONTROL (only - the fallback copy asserts nothing, which is honest
  for this group)
- Note: This is the largest single group. It is NOT a coherent cohort in the
  sense of "companies that share a characteristic." It is a cohort defined by
  the absence of knowledge. That is a legitimate CONTROL cohort for reading
  the result, but it must be labelled as such.

**Cohort C6: Software Dev + SEO + Consulting (the rest)**
- Size: 7 contacts (4 + 2 + 1)
- Dimensions: vertical = Software Dev Agency / SEO Agency / Consulting
- Evidence: vertical inferred from website text
- What this cohort reads: too few to read. Hold until accumulated.
- Arm: CONTROL
- Note: 7 is below the 10 minimum. These must be held or merged into a
  broader "non-agency or specialist agency" bucket.

### 6.3 Proposed cohorts for CHALLENGER arm

The CHALLENGER arm uses copy that asserts something about the recipient.
This requires per-contact evidence that clears the claims gate.

**Cohort CH1: Evidenced pains - resource_planning + delivery_visibility**
- Size: 22 contacts (12 economic_buyer, 10 champion)
- Dimensions: relevant_pain_categories = (resource_planning, delivery_visibility)
- Evidence: The underlying signals (delivery_complexity, resource_planning_need)
  were extracted from these companies' own websites. 15 are Creative/Branding
  Agency, 7 are Digital Marketing Agency.
- What copy may assert: "your projects" (delivery), "who's working on what"
  (resource planning) - because the website evidence supports these pains.
- Arm: CHALLENGER
- Note: This is the ONLY group where copy may assert a specific pain. The
  other 70 contacts have no evidenced pain for copy to reference.

**Cohort CH2: Evidenced pains - resource_planning only**
- Size: 6 contacts (5 economic_buyer, 1 champion)
- Dimensions: relevant_pain_categories = (resource_planning,)
- Evidence: resource_planning_need fired but delivery_complexity did not.
- What copy may assert: "who's working on what" but not "where a project is"
- Arm: CHALLENGER
- Note: 6 is below the 10 minimum. Hold until accumulated or merge with CH1
  for a combined "resource planning" read at 28.

**Cohort CH3: Evidenced pains - project_margin + budget_control**
- Size: 2 contacts
- Dimensions: relevant_pain_categories = (project_margin, budget_control)
- Evidence: project_margin signal fired from website text.
- What copy may assert: "whether a project made money"
- Arm: CHALLENGER
- Note: 2 is far below the 10 minimum. Hold.

### 6.4 Size bands as an alternative cohort key

If vertical is too sparse (38% UNKNOWN) and pain categories are too sparse
(38% coverage), the next most evidenced dimension is **employee_band**, which
has 100% coverage.

**Cohort S1: Micro (1_9 employees)**
- Size: 16 contacts
- Evidence: LinkedIn headcount (evidenced but contested on some records)
- Arm: CONTROL
- Note: These are solo practitioners or very small teams. The persona is
  always economic_buyer (the founder IS the company).

**Cohort S2: Small (10_19 employees)**
- Size: 27 contacts
- Evidence: LinkedIn headcount
- Arm: CONTROL
- Note: The largest size band. Still founder-led.

**Cohort S3: Medium (20_49 employees)**
- Size: 22 contacts
- Evidence: LinkedIn headcount
- Arm: CONTROL
- Note: Transition zone. 16 economic_buyer, 6 champion.

**Cohort S4: Mid-market (50_99 employees)**
- Size: 17 contacts
- Evidence: LinkedIn headcount
- Arm: CONTROL
- Note: champion-heavy: 9 economic_buyer, 8 champion. The persona split
  flips here.

**Cohort S5: Large (100+ employees)**
- Size: 10 contacts
- Evidence: LinkedIn headcount
- Arm: CONTROL
- Note: 5 economic_buyer, 4 champion, 1 unknown. Too few to read alone.

Size bands have the advantage of 100% coverage and a clear operational
meaning (who the decision-maker is). They have the disadvantage of saying
nothing about what the company does, which is what the copy would ideally
reference.

---

## 7. What is left over

### 7.1 Contacts not assigned to any proposed cohort

All 92 contacts are assigned to a CONTROL cohort (C1-C6) or a CHALLENGER
cohort (CH1-CH3). There are no leftovers in the sense of "contacts that fit
no cohort." The issue is the opposite: **the UNKNOWN vertical cohort (C5, 35
contacts) is a cohort defined by the absence of knowledge, and the three
known verticals (C1-C4, 53 contacts) are each too small to read
individually at the 50-contact batch size.**

### 7.2 Cohorts below the readable minimum

| Cohort | Size | Minimum | Gap |
|--------|------|---------|-----|
| C2 (Creative/Branding champion) | 7 | 10 | -3 |
| C6 (Software Dev + SEO + Consulting) | 7 | 10 | -3 |
| CH2 (resource_planning only) | 6 | 10 | -4 |
| CH3 (project_margin + budget_control) | 2 | 10 | -8 |
| S5 (100+ employees) | 10 | 10 | 0 |

These must be held until accumulated or merged with a compatible cohort.

### 7.3 The 66% region=Other problem

61 of 92 contacts have region = "Other" because no location evidence was
found. Geography cannot be used as a cohort key for this estate until
research fills the gap. The 31 contacts with known geography are spread
across 11 countries and 12 regions, with no region reaching 10 contacts
except "Other."

---

## 8. Summary: the honest answer

**The estate does not support a single cohort of 50 on any evidenced
dimension.** The largest coherent group is economic_buyer at 72, but that is
78% of the pool and is the default, not a meaningful cohort.

**The largest meaningful cohorts are by vertical (where known):**
- Creative/Branding Agency: 23
- Digital Marketing Agency: 14
- Performance Marketing Agency: 13
- UNKNOWN: 35 (not a cohort, a gap)

**The largest evidenced CHALLENGER cohort is 22 contacts** with
resource_planning + delivery_visibility pains. The remaining 70 contacts
have no evidenced pain for copy to assert.

**The batch progression 3 -> 10 -> 25 -> 50 must fit inside 92 contacts on
the snapshot** (or 97 deployable on the live queue after account collision).
A ~50-contact cohort is reachable only by combining verticals or by using
size bands, neither of which produces a cohort where the copy can say
something specific about what the company does.

**The CONTROL arm is the honest arm for 70 of 92 contacts.** Only 22 have
evidenced pains that copy may assert. The other 70 receive the fallback copy
that says nothing specific, which is correct because the evidence does not
support anything specific.

**The cohort question at 50 is not "which 50 contacts" but "which dimension
are we reading the result on."** A campaign of 50 contacts mixing four
verticals and two personas produces a reply rate that means nothing unless
the cohort is defined BEFORE the send and the result is read against that
definition.

---

## 9. Recommendations

1. **For the first canary of 3:** Use the CONTROL arm. Pick 3 from C1
   (Creative/Branding Agency economic_buyer) or S2 (10_19 employees). The
   copy asserts nothing, which is honest for all of them.

2. **For the batch of 10:** Use CONTROL. Pick 10 from C1 + C3 (Creative +
   Digital Marketing = 37 available). The result is read against vertical.

3. **For the batch of 25:** Use CONTROL. Combine C1 + C3 + C4 (Creative +
   Digital + Performance = 53 available). The result is read against
   vertical, with the caveat that Performance Marketing has no evidenced
   pains.

4. **For the batch of 50:** Use CONTROL. Combine C1 + C3 + C4 + C5 (all
   known verticals + UNKNOWN = 88 available). The result is read against
   vertical, with UNKNOWN as a separate read.

5. **For the CHALLENGER arm:** Wait until CH1 accumulates to 10+ contacts
   (currently 22, so it is ready). Use the 22 contacts with evidenced
   resource_planning + delivery_visibility pains. Copy may assert these
   pains because the website evidence supports them.

6. **Do not merge UNKNOWN verticals into a known vertical cohort.** They are
   not Creative/Branding or Digital Marketing agencies as far as the evidence
   says. They are companies in advertising/marketing industries where the
   website crawl failed. Merging them into a known vertical cohort would
   produce a cohort wearing two names.

7. **Do not use persona_strategy as a cohort key.** It is a restatement of
   employee_band (founder_led = 1_9 + 10_19, operations_led = 20_49 + 50_99).
   Using both would be double-counting the same dimension.

8. **The 38% UNKNOWN vertical is a research gap, not a cohort design
   problem.** Fixing it requires website crawls, not a different grouping
   dimension. Until then, UNKNOWN is a legitimate CONTROL cohort for reading
   the result, labelled as "vertical unknown."
