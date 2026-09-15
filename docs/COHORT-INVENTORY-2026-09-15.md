# Cohort Inventory - 2026-09-15

**Snapshot:** `work/queue.snapshot.jsonl` from master `0ac5e60` at 2026-09-14T21:52:15Z  
**Total records:** 300  
**Active records (not dropped):** 194  
**Contacts on active records:** 92  
**Contacts with email:** 87 (94.6%)

This inventory answers: **what cohorts of qualified leads can be honestly assembled from the estate as it stands?**

---

## 1. Field Coverage

Every field that might group a cohort, read through the real entry points against the snapshot. Lookup paths are named so the numbers are checkable.

| Field | Count | % | Lookup Path |
|-------|------:|--:|-------------|
| name | 92 | 100.0% | `contacts[].name` |
| title | 92 | 100.0% | `contacts[].title` |
| company | 92 | 100.0% | record-level `company` |
| domain | 92 | 100.0% | record-level `domain` |
| email | 87 | 94.6% | `contacts[].email` |
| persona | 92 | 100.0% | `contacts[].persona` |
| angle | 81 | 88.0% | `contacts[].angle` |
| specialties | 0 | 0.0% | **field does not exist** in contact or record structure |
| industry | 92 | 100.0% | `company_facts.industry` |
| headcount | 92 | 100.0% | `company_facts.employees` |
| employee_range | 18 | 19.6% | `company_facts.employee_range` |
| revenue | 85 | 92.4% | `company_facts.revenue` |
| sendable | 56 | 60.9% | `contacts[].sendable` |

### What the task description said vs. what the data shows

The task brief stated specialties at 73%. **Specialties is 0%.** The field does not exist in the contact structure (`name`, `title`, `linkedin`, `email`, `email_source`, `persona`, `angle`, `verdict`, `reoon`, `sendable`, `primary`, `key`, `mx`, `verification`, `bison_lead_id`) and does not exist at record level either. This is not a lookup error - the field is absent from the estate. A cohort cannot be built on a field that does not exist.

All other coverage numbers match the task description: first name/title/company/domain/industry/headcount/persona at 100%, email at 94% (87/92), angle at 88% (81/92), employee_range at 19% (18/92).

### Headcount is contested and is NOT safe as a cohort key

The task brief warned: "7 conflicts and 64 range/value disagreements across 300 records." Headcount exists as `company_facts.employees` (100% on active records) but `employee_range` is only 19% populated. The task explicitly states headcount is not safe as a cohort key on the contested records. **This inventory does not use headcount or employee_range as a primary cohort signal.** Company size appears only as a secondary descriptor where `employee_range` is present.

---

## 2. Candidate Cohorts

Sorted by count. A cohort whose signal is null for most of its members is excluded.

### Cohorts with >= 50 leads

**1. Persona: economic_buyer**
- **Count:** 70 leads (with email)
- **Signal:** `persona == 'economic_buyer'`
- **Qualification:** `persona == 'economic_buyer' AND email IS NOT NULL`
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`
- **Coverage:** 100% of contacts have persona; 94.6% have email
- **Verdict:** This is the largest honest cohort. The signal is fully populated and the qualification rule is clean.

**2. Industry: Advertising Services**
- **Count:** 51 leads (with email)
- **Signal:** `company_facts.industry == 'Advertising Services'`
- **Qualification:** `company_facts.industry == 'Advertising Services' AND email IS NOT NULL`
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`
- **Coverage:** 100% of contacts have industry; 94.6% have email
- **Verdict:** This is the second largest honest cohort. Industry is fully populated at the record level and inherited by all contacts.

### Cohorts with >= 25 leads (but < 50)

**3. Angle: founder**
- **Count:** 45 leads (with email)
- **Signal:** `angle == 'founder'`
- **Qualification:** `angle == 'founder' AND email IS NOT NULL`
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`
- **Coverage:** 88% of contacts have angle; 94.6% have email
- **Verdict:** Strong cohort, just below the 50-lead target. Angle is well-populated.

**4. Persona + Industry: economic_buyer | Advertising Services**
- **Count:** 40 leads (with email)
- **Signal:** `persona == 'economic_buyer' AND company_facts.industry == 'Advertising Services'`
- **Qualification:** both fields populated AND email IS NOT NULL
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`
- **Verdict:** This is the intersection of cohorts #1 and #2. It is a more specific cohort but does not reach 50 on its own. It could be merged with a genuinely compatible cohort (e.g., economic_buyer in a related industry) if the hypothesis supports it.

**5. Angle + Industry: founder | Advertising Services**
- **Count:** 27 leads (with email)
- **Signal:** `angle == 'founder' AND company_facts.industry == 'Advertising Services'`
- **Qualification:** both fields populated AND email IS NOT NULL
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`
- **Verdict:** Intersection of cohorts #3 and #2. Below 50. Could be held and accumulated or merged with a compatible cohort.

### Cohorts with >= 10 leads (but < 25)

**6. Angle: operations**
- **Count:** 22 leads
- **Signal:** `angle == 'operations'`
- **Qualification:** `angle == 'operations' AND email IS NOT NULL`
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`

**7. Industry: Marketing & Advertising**
- **Count:** 18 leads
- **Signal:** `company_facts.industry == 'Marketing & Advertising'`
- **Qualification:** `company_facts.industry == 'Marketing & Advertising' AND email IS NOT NULL`
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`

**8. Persona: champion**
- **Count:** 17 leads
- **Signal:** `persona == 'champion'`
- **Qualification:** `persona == 'champion' AND email IS NOT NULL`
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`

**9. Persona + Industry: economic_buyer | Marketing & Advertising**
- **Count:** 16 leads
- **Signal:** `persona == 'economic_buyer' AND company_facts.industry == 'Marketing & Advertising'`
- **Qualification:** both fields populated AND email IS NOT NULL
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`

**10. Industry: Marketing Services**
- **Count:** 14 leads
- **Signal:** `company_facts.industry == 'Marketing Services'`
- **Qualification:** `company_facts.industry == 'Marketing Services' AND email IS NOT NULL`
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`

**11. Company size: 11-50 employees**
- **Count:** 14 leads
- **Signal:** `company_facts.employee_range == '11-50 employees'`
- **Qualification:** `company_facts.employee_range == '11-50 employees' AND email IS NOT NULL`
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL OR employee_range IS NULL`
- **Note:** Only 19.6% of contacts have `employee_range` populated. This cohort excludes the 80% without the field.

**12. Persona + Industry: economic_buyer | Marketing Services**
- **Count:** 13 leads
- **Signal:** `persona == 'economic_buyer' AND company_facts.industry == 'Marketing Services'`
- **Qualification:** both fields populated AND email IS NOT NULL
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`

**13. Persona + Industry: champion | Advertising Services**
- **Count:** 11 leads
- **Signal:** `persona == 'champion' AND company_facts.industry == 'Advertising Services'`
- **Qualification:** both fields populated AND email IS NOT NULL
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`

**14. Angle + Industry: operations | Advertising Services**
- **Count:** 10 leads
- **Signal:** `angle == 'operations' AND company_facts.industry == 'Advertising Services'`
- **Qualification:** both fields populated AND email IS NOT NULL
- **Exclusion:** `drop_reason IS NOT NULL OR email IS NULL`

### Cohorts with < 10 leads

The remaining cohorts are too small to operate as standalone campaigns under the policy's ~50-lead target. They are listed for completeness but are not candidates for immediate campaign creation.

- angle + industry: founder | Marketing & Advertising: 9 leads
- angle + industry: founder | Marketing Services: 9 leads
- angle + industry: operations | Marketing & Advertising: 7 leads
- angle: delivery: 5 leads
- angle + industry: operations | Marketing Services: 4 leads
- angle + industry: delivery | Advertising Services: 3 leads
- persona + industry: champion | Design Services: 2 leads
- persona + industry: champion | Marketing & Advertising: 2 leads
- angle: finance: 2 leads
- angle + industry: finance | Advertising Services: 2 leads
- industry: Design Services: 2 leads
- persona: economic_buyer (remaining industries): 1 lead each
- angle: economic_buyer: 1 lead
- angle: growth: 1 lead
- angle + industry: champion | Marketing Services: 1 lead
- angle + industry: champion | Translation and Localization: 1 lead
- angle + industry: delivery | Design Services: 1 lead
- angle + industry: operations | Design Services: 1 lead
- persona + industry: economic_buyer | Business Consulting and Services: 1 lead
- industry: Translation and Localization: 1 lead
- industry: Business Consulting and Services: 1 lead

---

## 3. Honest Verdict on Size

### How many cohorts of >= 50 can be assembled?

**Two.**

1. **Persona: economic_buyer** - 70 leads
2. **Industry: Advertising Services** - 51 leads

These are the only two cohorts that meet the policy's ~50-lead target without fabricating similarity.

### How many cohorts of >= 25 can be assembled?

**Five.**

The two above plus:
3. **Angle: founder** - 45 leads
4. **Persona + Industry: economic_buyer | Advertising Services** - 40 leads
5. **Angle + Industry: founder | Advertising Services** - 27 leads

### What is the largest honest cohort?

**Persona: economic_buyer** at 70 leads. This is the largest cohort the estate can honestly assemble.

### What would it take to reach 50 for the cohorts that are close?

- **Angle: founder** (45 leads): needs 5 more leads. This could come from discovery (finding more founders in the estate), enrichment (contacts whose angle is currently null but who are actually founders), or a merge with a genuinely compatible cohort (e.g., founders in a related industry or with a related persona).
- **Persona + Industry: economic_buyer | Advertising Services** (40 leads): needs 10 more leads. This is the intersection of the two largest cohorts. It could be grown by discovering more economic buyers in Advertising Services, or by merging with a genuinely compatible cohort (e.g., economic buyers in Marketing & Advertising, which is a related industry).
- **Angle + Industry: founder | Advertising Services** (27 leads): needs 23 more leads. This is a more specific cohort and would require significant discovery or a merge with a compatible cohort (e.g., founders in Marketing & Advertising or Marketing Services).

### What the estate cannot do

The estate **cannot** support dozens of cohorts of 50+. It supports two, maybe three with stretching. The policy says "where inventory supports it" - and the inventory supports two clear cohorts of 50+, with several more in the 25-45 range that could be held, accumulated, or merged.

**Do not fabricate cohort similarity to reach 50.** A signal with 17 qualified leads is held and accumulated, merged with a genuinely compatible cohort, or run explicitly as a small exploratory cohort with its sample size recorded. Forcing unrelated leads together to hit a number destroys the attribution the cohort exists to produce.

---

## 4. Cohort Definitions

The top candidates are defined in `docs/state/COHORTS.json` with the fields the policy names:

    COHORT_ID        SIGNAL           ICP FILTER       QUALIFICATION RULE
    EXCLUSION RULE   LEAD COUNT       MESSAGE HYPOTHESIS
    CAMPAIGN         VARIANTS         SENDERS          START DATE
    OUTCOMES         CONFIDENCE       LEARNING

CAMPAIGN, OUTCOMES and LEARNING are empty - they are not this inventory's to fill.

See `docs/state/COHORTS.json` for the machine-readable definitions.

---

## 5. What This Inventory Does Not Do

- **It does not create campaigns.** It answers whether cohorts of the policy's target size can be honestly assembled.
- **It does not fabricate similarity.** The two cohorts of 50+ are real. The cohorts of 25-45 are real. Smaller cohorts are listed but not dressed up as a plan.
- **It does not use contested fields as primary signals.** Headcount is contested and is not a cohort key. Specialties does not exist in the estate.
- **It does not count dropped records or contacts without email.** The 92 contacts are on not-dropped records. The 87 with email are the ones that can be reached.

---

## 6. What Comes Next

1. **Define the message hypothesis for each cohort.** What is the outreach saying, and to whom? This is not a field coverage question - it is a product and positioning question.
2. **Decide which cohorts to run first.** The two cohorts of 50+ are the obvious starting points. The cohorts of 25-45 could be held and accumulated, or merged with compatible cohorts if the hypothesis supports it.
3. **Assign senders.** The sender estate is measured (`docs/state/SENDER-CAPACITY.json`): 33 healthy seats, zero uncommitted. Every healthy seat is already attached to at least one campaign. Adding senders to a cohort is a question about reassigning seats that are already working.
4. **Generate copy and variants.** At least five meaningful variants at experimentable positions where supported.
5. **Run the gates.** No campaign pushes without passing the established gates. `pushable` was retired as the promotion criterion.
6. **Measure outcomes.** Reply, positive reply, acceptance by step, delay performance, drop-off, incremental replies from later steps, sender, cohort and variant effects.

---

**Prepared by:** TASK-096  
**Date:** 2026-09-15  
**Snapshot:** `work/queue.snapshot.jsonl` from master `0ac5e60` at 2026-09-14T21:52:15Z
