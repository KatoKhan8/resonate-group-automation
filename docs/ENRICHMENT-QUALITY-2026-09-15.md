# Enrichment Quality Report — 2026-09-15

**TASK-112.** Read-only measurement of enrichment field coverage, correctness,
staleness, and a per-field verdict. No provider calls. No data repaired.

## Sample

- **Source:** `work/queue.snapshot.jsonl`
- **Stamp:** `2026-09-14T21:52:15Z from master 0ac5e60, 300 records`
- **Records:** 300
- **Non-dropped:** 194 (state ≠ dropped)
- **Dropped:** 106 (98 rejected at ICP, 8 no contact found)
- **Contacts:** 92 across 300 records (223 records have zero contacts)
- **Lookup path:** All fields read directly from the JSONL record structure.
  `company_facts.*` for company-level enrichment, `contacts[*].*` for
  contact-level, `qualification.segment.*` for derived segmentation.
  `sizing` is confirmed null on all 300 records — it is NOT the lookup path
  for industry or headcount. The correct paths are `company_facts.industry`
  and `company_facts.employees` / `company_facts.headcount_signal`.

---

## Per-Field Verdict Table

| Field | Coverage | Lookup Path | Verdict | Notes |
|-------|----------|-------------|---------|-------|
| **domain** | 300/300 (100%) | `rec.domain` | **SAFE TO PERSONALISE** | Identity field. Every record has one. |
| **company name** | 300/300 (100%) | `rec.company` | **NOT SAFE** | 281/300 hold a domain string, not a name. Cannot personalise with. |
| **contact name** | 92/92 (100%) | `contact.name` | **SAFE TO PERSONALISE** | First + last name present on every contact. |
| **contact title** | 92/92 (100%) | `contact.title` | **SAFE WITH FALLBACK** | 100% coverage but provider-sourced; no cross-check against evidence. |
| **contact email** | 87/92 (94.6%) | `contact.email` | **SAFE WITH FALLBACK** | 5 contacts have a gmail.com address, not at the record domain. |
| **contact linkedin** | 92/92 (100%) | `contact.linkedin` | **SAFE WITH FALLBACK** | Stored as bare vanity slug. Provider-sourced, no cross-check. |
| **persona** | 92/92 (100%) | `contact.persona` | **SAFE TO PERSONALISE** | Assigned by qualification. Two values: economic_buyer (72), champion (20). |
| **angle** | 81/92 (88.0%) | `contact.angle` | **SAFE WITH FALLBACK** | 11 contacts have no angle. Values: founder (47), operations (23), delivery (7), finance (2), economic_buyer (1), growth (1). |
| **email verdict** | 68/92 (73.9%) | `contact.verdict` | **SAFE TO PERSONALISE** | valid (57), None (24), accept_all (11). A contact with no verdict has not been verified. |
| **sendable** | 56/92 (60.9%) | `contact.sendable` | **SAFE TO PERSONALISE** | Boolean gate. 36 contacts are not sendable. |
| **industry** | 259/300 (86.3%) | `company_facts.industry` | **SAFE WITH FALLBACK** | 41 records have no industry. Top values: Advertising Services (147), Marketing Services (64), Marketing & Advertising (25). |
| **employees** | 261/300 (87.0%) | `company_facts.employees` | **NOT SAFE as exact number** | Integer, but 25 of 261 come from recovered client exports where the value is the LOWER BOUND of a band (e.g., "11-50" → 11). Not a measured headcount. |
| **headcount_signal** | 252/300 (84.0%) | `company_facts.headcount_signal` | **NOT SAFE as headcount** | This is the number of LinkedIn profiles ContactOut found at the domain, NOT a company headcount. Median ratio to `employees` is 0.88 but ranges from 0.00 to 7.12. 55/261 records diverge >50%. |
| **employee_range** | 25/300 (8.3%) | `company_facts.employee_range` | **EXCLUDE THE RECORD** | Only 25 records have it. All 25 are recovered client exports. Cannot be used as a cohort key. |
| **revenue** | 198/300 (66.0%) | `company_facts.revenue` | **SAFE WITH FALLBACK** | String values like "$3.0M". 3 records report "N/A". No cross-check possible. |
| **company linkedin** | 264/300 (88.0%) | `company_facts.linkedin` | **SAFE TO PERSONALISE** | Full LinkedIn company URL. |
| **offices** | 235/300 (78.3%) | `company_facts.offices` | **SAFE WITH FALLBACK** | Free-text address strings. 65 records have none. |
| **specialties** | 164/300 (54.7%) | `company_facts.specialties` | **SAFE WITH FALLBACK** | List of strings. When present: min=1, median=10, max=39. 136 records have none. |
| **vertical** | 144/300 (48.0%) | `qualification.segment.vertical` | **SAFE WITH FALLBACK** | 156/300 are "UNKNOWN". When present: Creative/Branding Agency (49), Digital Marketing Agency (31), Performance Marketing Agency (31). |
| **subvertical** | 52/300 (17.3%) | `qualification.segment.subvertical` | **EXCLUDE THE RECORD** | 248/300 are "UNKNOWN". Cannot be used as a cohort key. |
| **country** | 73/300 (24.3%) | `qualification.segment.country` | **SAFE WITH FALLBACK** | 227 records have no country. |
| **timezone** | 73/300 (24.3%) | `qualification.segment.timezone` | **SAFE WITH FALLBACK** | When present: confidence is "high", source is "city" (71) or "country_single_zone" (2). 227 records have none. A guessed timezone is worse than a missing one; these are evidenced but sparse. |
| **business_model** | 300/300 (100%) | `qualification.segment.business_model` | **SAFE TO PERSONALISE** | Always present. |
| **company_maturity** | 194/300 (64.7%) | `qualification.segment.company_maturity` | **SAFE WITH FALLBACK** | 106/300 are "UNKNOWN". When present: established (80), mature (61), growing (34), startup (19). |
| **delivery_model** | 17/300 (5.7%) | `qualification.segment.delivery_model` | **EXCLUDE THE RECORD** | 283/300 are "UNKNOWN". Cannot be used as a cohort key. |
| **region** | 300/300 (100%) | `qualification.segment.region` | **SAFE WITH FALLBACK** | 227/300 are "Other". When specific: US West (14), US East (13), UK (10). |
| **messaging.vertical** | 113/300 (37.7%) | `qualification.messaging.vertical` | **SAFE WITH FALLBACK** | Only present for qualified records with messaging analysis. |
| **messaging.recommended_angles** | 33/300 (11.0%) | `qualification.messaging.recommended_angles` | **SAFE WITH FALLBACK** | Very sparse. Only 33 records have angles. |
| **research quality** | 695 items | `rec.research[*].quality` | **NOT SAFE for claims** | unusable (236), weak (156), medium (155), strong (114), UNKNOWN (34). 56% of research items are unusable or weak. |
| **research freshness** | 695 items | `rec.research[*].freshness_bucket` | **NOT SAFE** | 661/695 (95%) have freshness_bucket="unknown" despite having `retrieved_at` timestamps. Freshness scoring is not producing usable buckets. |

---

## Fields That Must NOT Be Used as a Cohort Key

These fields have coverage too low or too many UNKNOWN/placeholder values to
serve as a reliable cohort key. A cohort keyed on one of these will silently
group records that share nothing meaningful.

1. **employee_range** — 8.3% coverage. 275 records have no value.
2. **subvertical** — 82.7% are "UNKNOWN". Only 52 records have a real value.
3. **delivery_model** — 94.3% are "UNKNOWN". Only 17 records have a real value.
4. **company name** (`rec.company`) — 93.7% hold a domain string, not a name.
5. **headcount_signal** — Not a headcount. It is a LinkedIn profile count from
   ContactOut's people-count API. Using it as a size proxy produces wrong
   cohorts: median ratio to `employees` is 0.88 but the range is 0.00–7.12.
6. **employees** (as an exact number) — 25 of 261 values are the lower bound
   of a band from a recovered client export, not a measured count. The band
   information is lost; only the floor survives.

---

## Correctness Findings

### Headcount: two fields, two sources, expected divergence

`headcount_signal` and `employees` are NOT two measurements of the same thing.

- `headcount_signal` = number of LinkedIn profiles ContactOut found at the
  domain (from the free people-count API). Source: `enrich.py` line 923:
  `facts = dict(facts, headcount_signal=count.get("profiles"))`.
- `employees` = company-reported headcount, or the lower bound of a band from
  a client CSV export. Source: `company_facts.recovered_from.confidence` says
  "medium: firmographics are the export's own, and `employees` is the LOWER
  BOUND of a band, not a measured headcount".

55 of 261 records where both exist diverge by more than 50%. This is not a
bug — they measure different things. But using either one as "the headcount"
without naming which is a correctness error.

### Company field is a domain string

281 of 300 records have `rec.company` set to a domain string (e.g.,
"academyxi.com") rather than a company name. The real company name lives at
`company_facts.name` (when populated by company-information-from-domain).
Personalising with `rec.company` would insert a domain where a name is
expected.

### Email domain mismatch

5 of 92 contacts have an email address at gmail.com, not at the record's
domain. These are personal addresses, not work addresses. The `enrich.same_company`
module has a `FREE_MAIL` set that recognises this; the contacts passed through
because the address was already on the record before the free-mail check.

### Research freshness is broken

661 of 695 research items (95%) have `freshness_bucket = "unknown"` despite
having `retrieved_at` timestamps. The freshness scoring pipeline is not
producing usable buckets. Research items cannot be assessed for staleness
through the freshness field.

### Recovery timestamps: all 178 days old

All 25 records with `company_facts.recovered_from` have an
`original_timestamp` that is exactly 178 days old (2026-03-20). These are
firmographics from a client CSV export, not from a provider call. The data
is from March 2026 and has not been refreshed.

---

## Staleness Summary

| Evidence Type | Median Age | Range | Notes |
|---------------|-----------|-------|-------|
| Waterfall entries | 2 days | 1–7 days | Recent enrichment activity |
| Qualification scoring | 2 days | 1–2 days | Very recent |
| Recovered firmographics | 178 days | 178 days | All from 2026-03-20 client export |
| Research retrieved_at | Present on all 695 | — | But freshness_bucket is "unknown" on 95% |

---

## Contact Pipeline Summary

| Stage | Count | Notes |
|-------|-------|-------|
| Total contacts | 92 | Across 300 records |
| With email | 87 (94.6%) | |
| With verdict | 68 (73.9%) | 24 have no verdict |
| Sendable | 56 (60.9%) | |
| MX checked | 82 (89.1%) | known_allowed: 72, unknown_provider: 9, known_blocked: 1 |
| Reoon checked | 68 (73.9%) | |
| Verification state: verified | 56 | |
| Verification state: unknown | 14 | |
| Verification state: accept_all_uncleared | 10 | |
| Verification state: held | 2 | |

---

## ICP and Qualification Summary

| ICP Status | Count | With Contacts | With Sendable | With Messaging Angles |
|------------|-------|---------------|---------------|----------------------|
| qualified | 113 | 74 | 54 | 33 |
| rejected | 121 | — | — | — |
| review | 66 | — | — | — |

Of 113 qualified records, 81 have enrichment stage "partial" and only 31
are "done". The messaging analysis (angles, pain categories) has run on only
33 of 113 qualified records.

---

## OBSERVATIONS

1. **The task's pre-stated coverage numbers were wrong.** The task stated
   employee_range at 19% and specialties at 73%. Actual measurement:
   employee_range at 8.3% (25/300) and specialties at 54.7% (164/300). The
   earlier numbers were not reproduced.

2. **100% coverage is not 100% usable.** `contact.title` is present on all 92
   contacts but is a provider-sourced string with no cross-check. `rec.company`
   is present on all 300 records but is a domain string on 281 of them.

3. **The qualified cohort is smaller than it looks.** 113 records are ICP-
   qualified, but only 54 have a sendable contact and only 33 have messaging
   angles. The personalisable cohort for a campaign is ~33 records, not 113.

4. **Research is mostly unusable.** 56% of research items are rated unusable
   or weak. The remaining 44% (medium + strong) cannot be assessed for
   freshness because the freshness pipeline produces "unknown" for 95% of
   items.

5. **The `sizing` field is null everywhere.** 0/300 records have it. Any code
   path that reads `sizing` for industry or headcount reads nothing. The
   correct paths are `company_facts.industry` and
   `company_facts.employees` / `company_facts.headcount_signal`.

---

## HYPOTHESES

1. The `employees` field on recovered records understates actual headcount
   because it is the lower bound of a band. The true headcount is somewhere
   between `employees` and the upper bound of the band, but the upper bound
   is not stored on the record.

2. The research freshness pipeline is not wired to the `retrieved_at`
   timestamp, or the scoring function returns "unknown" when it cannot
   classify. This needs investigation in the research module.

3. The 5 gmail.com contacts passed through enrichment because the address
   was on the record before the free-mail guard ran. The guard exists in
   `enrich.same_company` but is an identity check, not an address-quality
   filter.

---

## PROVEN LEARNINGS

Nothing survives a sample-size objection at this measurement depth. The
hypotheses above need targeted investigation before they become learnings.

---

## Fields That Must NOT Be Used as a Cohort Key (Summary)

| Field | Reason |
|-------|--------|
| `employee_range` | 8.3% coverage |
| `subvertical` | 82.7% UNKNOWN |
| `delivery_model` | 94.3% UNKNOWN |
| `rec.company` | 93.7% is a domain string, not a name |
| `headcount_signal` | Not a headcount — it is a LinkedIn profile count |
| `employees` (exact) | 25/261 are band lower bounds from a March 2026 export |
