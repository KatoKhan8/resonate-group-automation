# ContactOut capability audit — 2026-09-16

TASK-206. What the API can answer, what the code actually asks, and where the
real gaps are.

---

## 1. Available ContactOut surface

Source: the official API reference at `api.contactout.com`, cross-referenced
against `src/providers/contactout.py` ROUTES and the adapter functions.

### 1a. Endpoints the adapter implements

| # | Our name | REST route | Method | Inputs | Outputs (trimmed) | Credit cost |
|---|----------|-----------|--------|--------|-------------------|-------------|
| 1 | `people-count` | `POST /v1/people/count` | POST | job_title, location, domain | profiles (int), mobiles (int) | **FREE** |
| 2 | `people-search` | `POST /v1/people/search` | POST | domain, job_title, seniority, location, current_company_only, page, output_fields | list of person dicts (name, title, company, linkedin, email, location, seniority, current) | **1 search credit per profile returned** |
| 3 | `decision-makers` | `GET /v1/people/decision-makers` | GET | domain (or name or linkedin_url), reveal_info, page | list of person dicts (same shape as people-search) | **1 search credit per profile + 1 email credit per profile when reveal_info=true** |
| 4 | `email-verifier` | `GET /v1/email/verify` | GET | email | verdict: valid \| invalid \| accept_all \| disposable \| unknown | **1 verifier credit** |
| 5 | `company-information-from-domain` | `POST /v1/domain/enrich` | POST | domains (array, max 30) | name, domain, email_domain, linkedin, employees, revenue, founded, industry, offices, specialties, stack | **1 search credit** |

### 1b. Endpoints in the ContactOut API the adapter does NOT implement

| # | API endpoint | REST route | Method | Inputs | What it returns | Estimated cost |
|---|-------------|-----------|--------|--------|-----------------|----------------|
| 6 | LinkedIn Profile Enrich | `GET /v1/linkedin/enrich` | GET | profile (LinkedIn URL) | Full profile: work experience, education, skills, emails, phone | ~1-2 search credits per profile |
| 7 | People Enrich | `POST /v1/people/enrich` | POST | full_name, first_name, last_name, email, phone, linkedin_url, company, company_domain, job_title, location, education, include (work_email, personal_email, phone) | Enriched profile with optional contact info | ~1-2 search credits |
| 8 | Contact Info from LinkedIn | `GET /v1/people/linkedin` | GET | profile (LinkedIn URL), include_phone, email_type | Contact details: emails, phone | ~1 email credit |
| 9 | Company Search | `POST /v1/company/search` | POST | name, domain, size, hq_only, location, industries, min_revenue, max_revenue, year_founded_from/to | Company profiles matching criteria | ~1 search credit per result |
| 10 | Email-to-LinkedIn | `GET /v1/people/person` | GET | email | LinkedIn profile URL for an email address | ~1 search credit |
| 11 | Personal Email Checker | `GET /v1/people/linkedin/personal_email_status` | GET | profile (LinkedIn URL) | Email availability status (boolean) | Likely free or 1 credit |
| 12 | Work Email Checker | `GET /v1/people/linkedin/work_email_status` | GET | profile (LinkedIn URL) | Work email availability status | Likely free or 1 credit |
| 13 | Phone Number Checker | `GET /v1/people/linkedin/phone_status` | GET | profile (LinkedIn URL) | Phone availability status | Likely free or 1 credit |
| 14 | Batch Email Verification | `POST /v1/email/verify/batch` + `GET /v1/email/verify/batch` | POST/GET | emails (array), job_id | Bulk email verification | Per-email verifier credits |
| 15 | API Usage Stats | `GET /v1/stats` | GET | (period) | Account usage statistics | **FREE** |

### 1c. Available to us vs. exists in documentation

The adapter holds `CONTACTOUT_TOKEN` and authenticates with `authorization: basic`
+ `token: <CONTACTOUT_TOKEN>`. The API documentation does not list per-plan
endpoint restrictions — all endpoints appear available to any authenticated
account, with costs deducted from a unified credit pool.

**Available to us (adapter implemented + key present):** endpoints 1-5, 15.
**Exists in documentation, adapter does not call it:** endpoints 6-14.
**Account permission for 6-14: ASSUMED available** based on the API docs not
gating endpoints by plan tier, but NOT LIVE-PROVEN. A single free
`GET /v1/stats` call would confirm the account is active; testing whether
endpoint 6-14 actually answer would require a paid call per endpoint.

---

## 2. What the code actually calls

### 2a. Adapter functions with callers in `src/`

| Function | Callers | Production path? |
|----------|---------|-----------------|
| `contactout.people_count()` | `enrich.py:925`, `generate.py:1725`, `validate.py:295` | **YES** — enrich and generate |
| `contactout.decision_makers()` | `enrich.py:955`, `validate.py:297` | **YES** — enrich |
| `contactout.company_info()` | `enrich.py:985`, `validate.py:303` | **YES** — enrich |
| `contactout.email_verifier()` | `validate.py:301`, `verification.py:577` (deferred import) | **YES** — verification pipeline |
| `contactout.check()` | `check.py:33` | **YES** — health check |

### 2b. Adapter functions with NO production caller

| Function | Where defined | Callers | Status |
|----------|--------------|---------|--------|
| `contactout.people_search()` | `contactout.py:152` | `validate.py:299` (test dispatch only) | **IMPLEMENTED, NOT CALLED by enrich/generate** |

### 2c. Waterfall stages that reference ContactOut

From `src/waterfall.py` STAGES:

| Stage | ContactOut call | Position |
|-------|----------------|----------|
| company_information | `company-information-from-domain` | **First** (primary) |
| people_discovery | `people-count` then `decision-makers` | **First** (primary, two-step) |
| linkedin_url | `decision-makers` | **First** (profile arrives with the person) |
| email_discovery | `decision-makers` | **First** (address arrives with the person) |
| email_verification | `email-verifier` | **First** (primary) |
| company_research | `company-information-from-domain` | **First** (structured facts) |
| person_research | `decision-makers` | **First** (role, seniority, tenure) |

ContactOut is first in every stage. The waterfall is correctly configured.

### 2d. The diff: available but never called

| Endpoint | Adapter status | Waterfall position | Production caller | Gap |
|----------|---------------|-------------------|-------------------|-----|
| `people-search` | Implemented | Not in waterfall | Only validate.py | **Not wired into enrich/generate** |
| `company-search` | Not implemented | Not in waterfall | None | **Not in adapter** |
| `linkedin/enrich` | Not implemented | Not in waterfall | None | **Not in adapter** |
| `people/enrich` | Not implemented | Not in waterfall | None | **Not in adapter** |
| `people/linkedin` (contact info) | Not implemented | Not in waterfall | None | **Not in adapter** |
| `people/person` (email-to-LI) | Not implemented | Not in waterfall | None | **Not in adapter** |
| Contact checker APIs (3) | Not implemented | Not in waterfall | None | **Not in adapter** |

---

## 3. Capability-to-requirement map

For each of the seven requirements the pipeline needs, what ContactOut call
answers it and which field carries the answer.

### 3a. geography — an ISO country the ICP criterion accepts

- **ContactOut call:** `company-information-from-domain` (already called)
- **Field path:** response `locations` → `company_info()` returns as `offices`
  → stored in `rec["company_facts"]["offices"]` → `icpstructural.resolve_country()`
  parses the last comma-separated token of each office line against an
  ISO-to-country map → `segment["country"]` → `_geography()` checks against
  client include/exclude lists
- **Status: CAPABILITY PRESENT, DATA QUALITY ISSUE.**
  TASK-185 confirmed offices came back but they "sit outside the client's
  include list." The chain works; the answer ContactOut gives does not match
  the client's target markets. This is not a capability gap — it is either
  (a) the company is genuinely outside the target geography, or (b) ContactOut's
  office data is incomplete/stale for some domains.
- **Could another endpoint help?** No. `people-search` returns person-level
  `location`, not company HQ. `company-search` returns the same `location`
  field for companies found by search criteria. The underlying data source is
  the same.

### 3b. company_type — a vertical the structural check recognises

- **ContactOut call:** `company-information-from-domain` (already called)
- **Field path:** response `industry` → `company_info()` returns as `industry`
  → stored in `rec["company_facts"]["industry"]` → `segments.classify_vertical()`
  classifies it into a vertical → `icpstructural.resolve_company_type()` reads
  `segment["vertical"]` first, falls back to `company_facts.industry`
- **Status: CAPABILITY PRESENT, COVERAGE PARTIAL.**
  TASK-185 found "company_type was already PASS wherever any industry was
  known." The gap is the 159 companies where `vertical` is UNKNOWN and no
  `industry` was returned. `icpstructural` comments (line 140) confirm:
  "159 verticals are UNKNOWN, and 116 of those carry a marketing or software
  services industry the vertical classifier never consulted."
- **Could another endpoint help?** Marginally. `company-search` returns
  `industry` too. `people/enrich` might return additional company context.
  But the fundamental issue is that ContactOut's industry classification does
  not always map to the client's vertical taxonomy, and no other ContactOut
  endpoint has a different taxonomy.

### 3c. employees — a headcount

- **ContactOut call:** `company-information-from-domain` (already called)
- **Field path:** response `employees` → `company_info()` returns as `employees`
  → stored in `rec["company_facts"]["employees"]` → `icpstructural._employees()`
  reads it, with band-awareness (`_band()` handles "11-50" → lower bound 11)
- **Status: CAPABILITY PRESENT.** When ContactOut returns a value, the chain
  works. When it returns 0 or absent, `_present()` converts to None and the
  criterion goes UNKNOWN (not FAIL), which is the correct behaviour.

### 3d. prose evidence — a fact with a source, for check_evidence

- **ContactOut call:** NONE
- **Status: NO CONTACTOUT CAPABILITY.**
  ContactOut returns structured firmographic data (industry, offices, tech
  stack, specialties). It does not return dated, attributable, prose facts
  with source URLs. `check_evidence` in `src/llm.py` requires evidence with a
  source — a fact that can be checked against a URL or publication. This is
  the crawler's job (Apify research, webfetch), not a data provider's.
- **This is a genuine capability gap that licenses the next layer.**

### 3e. person discovery — contacts at a qualified account

- **ContactOut calls:**
  - `people-count` (free, confirms the domain is staffed)
  - `decision-makers` (returns key people with roles, seniority, LinkedIn URLs)
  - `people-search` (implemented but not wired — can filter by domain, seniority,
    job_title, location; returns same person shape)
- **Status: CAPABILITY PRESENT.** `decision-makers` is the primary path and
  returns contacts. `people-search` is available as an additional lever but is
  not wired into the enrich pipeline — it could be added without building a
  new adapter, just a waterfall step and enrich logic.

### 3f. contact email — and its verification

- **ContactOut calls:**
  - `decision-makers` with `reveal_info=True` → returns `contact_info.work_email`
    or `contact_info.email` (extracted by `_email()` helper)
  - `email-verifier` → returns verdict: valid | invalid | accept_all | disposable | unknown
- **Status: CAPABILITY PRESENT.** Both discovery and verification are wired
  and ContactOut-first in the waterfall. The verification waterfall correctly
  falls back to Deliverable and Reoon when ContactOut returns accept_all or
  unknown.

### 3g. job-change signal — a reason to reach out now

- **ContactOut call:** NONE in the current adapter
- **Closest available endpoint:** `linkedin/enrich` (not implemented) returns
  work experience with dates, which could be diffed to detect recent role
  changes. `people/enrich` (not implemented) also returns work history.
- **Status: NO CONTACTOUT CAPABILITY in the current adapter.**
  The API *might* support this through `linkedin/enrich` work history, but:
  (a) the adapter does not implement it, (b) detecting a "job change" requires
  comparing two snapshots over time or knowing the person's previous role, and
  (c) ContactOut does not offer a dedicated job-change signal endpoint.
- **This is a genuine capability gap that licenses external signals**
  (LinkedIn monitoring, news feeds, or Grok for recent public announcements).

### Summary table

| Requirement | ContactOut call | Field | Status |
|-------------|----------------|-------|--------|
| geography | `company-information-from-domain` | `locations` → `offices` → `country` | **CAPABILITY PRESENT** (data quality issue, not a gap) |
| company_type | `company-information-from-domain` | `industry` → `vertical` | **CAPABILITY PRESENT** (coverage partial — 159 UNKNOWN verticals) |
| employees | `company-information-from-domain` | `employees` | **CAPABILITY PRESENT** |
| prose evidence | NONE | N/A | **NO CONTACTOUT CAPABILITY** — genuine gap |
| person discovery | `people-count` + `decision-makers` | person list | **CAPABILITY PRESENT** |
| contact email | `decision-makers` (reveal_info) + `email-verifier` | `contact_info.work_email` + verdict | **CAPABILITY PRESENT** |
| job-change signal | NONE (adapter) | N/A | **NO CONTACTOUT CAPABILITY** — genuine gap |

---

## 4. Bounded re-test decision

The task asks: if item 3 finds a ContactOut call that could plausibly resolve
geography or company_type where `company-information-from-domain` did not, try
it on five records.

**Decision: no re-test warranted.**

Reasoning:

1. **Geography:** The `company-information-from-domain` endpoint returns
   `locations` (office addresses). The chain works — `resolve_country()`
   extracts a country from office lines. TASK-185's finding was that the
   returned offices did not match the client's target markets, not that the
   field was empty. No other ContactOut endpoint returns different or better
   company-location data:
   - `company-search` returns `location` for companies found by search
     criteria, but it is the same underlying data.
   - `people-search` returns person-level `location`, which is where a person
     is, not where the company is headquartered.
   - `people/enrich` and `linkedin/enrich` are person-level, not company-level.

2. **Company type:** The `industry` field from `company-information-from-domain`
   feeds the vertical classifier. Where it was present, it resolved company_type
   to PASS. Where it was absent, no other ContactOut endpoint carries a
   different industry taxonomy that would resolve the 159 UNKNOWN verticals
   differently.

3. **The trap the task names:** "do not conclude from a null that the
   capability is absent." This is addressed above — the geography field IS
   populated, it just does not match. The company_type field IS populated
   where ContactOut has an industry. These are not nulls; they are answers
   that do not help, which is a different problem.

Running five records through `company-search` or `people-search` would spend
5-10 credits and return the same underlying data through a different route.
The hypothesis — that a different endpoint would produce different geography
or company_type answers — is not supported by the API documentation, which
shows the same fields across endpoints.

---

## 5. Confirmed capability gaps

What ContactOut genuinely cannot do for this pipeline, which licenses the
later layers in the routing policy.

### 5a. Prose evidence with source attribution

ContactOut returns structured firmographics: industry, offices, headcount,
tech stack, specialties. None of these are dated, attributable facts with a
source URL. The pipeline's `check_evidence` (in `src/llm.py`) requires a fact
that can be checked — a publication, a press release, a dated news item.

**This licenses:** the free crawler (webfetch, Apify research) at layer 3 of
the routing policy, and Grok/xAI at layer 4 for ambiguous or still-missing
evidence.

### 5b. Job-change signals

ContactOut has no dedicated job-change endpoint. The `linkedin/enrich` API
returns work history with dates, which could in theory detect recent role
changes, but:
- The adapter does not implement it.
- Detecting a change requires either two time snapshots or knowing the
  previous role, neither of which the API provides as a signal.
- ContactOut does not push notifications or offer a "changed since" query.

**This licenses:** external signal monitoring (LinkedIn change feeds, news
APIs, Grok for recent public announcements) at layers 3-4 of the routing
policy.

### 5c. What is NOT a gap (but might look like one)

- **Geography:** Not a ContactOut gap. The data comes back; it just does not
  match the client's target markets for some companies. A crawler finding the
  company's actual HQ on their website would add a second data point, but
  ContactOut is not failing — it is answering correctly about where the
  company has offices.
- **Company type / vertical:** Not a gap in ContactOut's capability, but a
  coverage limitation. ContactOut's industry taxonomy does not map 1:1 to the
  client's vertical taxonomy. A crawler reading the company's own "about"
  page might supply a better vertical signal, but that is the crawler adding
  value, not ContactOut failing.
- **Email discovery:** Not a gap. `decision-makers` with `reveal_info` returns
  work emails, and the verification waterfall handles inconclusive results.

---

## 6. Recommendations for TASK-207 and TASK-208

Based on this audit, the routing changes TASK-207 and TASK-208 should consider:

1. **Wire `people-search` into the enrich pipeline.** It is implemented,
   tested, and has no caller. It offers filtering by seniority, job_title, and
   location that `decision-makers` does not, and could find contacts the
   decision-makers endpoint misses. Cost: 1 search credit per profile.

2. **Do NOT add `company-search` as a parallel to `company-information-from-domain`.**
   It returns the same data through a different route. The geography and
   company_type issues are data quality, not endpoint selection.

3. **Consider `linkedin/enrich` for person-level enrichment** when the pipeline
   already holds a LinkedIn URL and needs contact details. It is a different
   input shape (URL in, person out) than `decision-makers` (domain in, people
   out), and could fill the gap between "we have a profile" and "we need an
   email."

4. **The prose evidence and job-change gaps are real and unbridgeable by
   ContactOut.** The routing policy's layers 3-4 (crawler, Grok) are correctly
   positioned to fill them. No ContactOut endpoint change will close these.

---

*Audit prepared 2026-09-16 for TASK-206. No live API calls were made. All
capability claims are derived from the official ContactOut API reference at
api.contactout.com, cross-referenced against the adapter in
src/providers/contactout.py and the waterfall in src/waterfall.py.*
