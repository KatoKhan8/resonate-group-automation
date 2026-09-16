# ContactOut: ten endpoints we do not call

TASK-212 analysis. 2026-09-16. No live API calls made; all claims derived from
the official ContactOut API reference at api.contactout.com cross-referenced
against `src/providers/contactout.py`, `src/waterfall.py`, `src/enrich.py`,
`src/llm.py` and the TASK-206 capability audit.

---

## 1. The ten endpoints

The adapter implements five paid endpoints (people-count, people-search,
decision-makers, email-verifier, company-information-from-domain) plus the
free stats check. The ContactOut API exposes at least fifteen distinct
operations. The ten below are documented, not implemented, and not called.

### 1a. LinkedIn Profile Enrich

| Field | Value |
|-------|-------|
| REST route | `GET /v1/linkedin/enrich` |
| Method | GET |
| Input | `profile` (LinkedIn URL, required), `profile_only` (boolean, optional) |
| Returns | Full profile: `full_name`, `headline`, `company`, `location`, `experience` (work history with dates), `education`, `skills`, `certifications`, `summary`, `languages`, `seniority`, `job_function`, `followers`, `profile_picture_url`, `updated_at`. With contact info: `email`, `work_email`, `personal_email`, `phone`, `github`, `twitter`. |
| Cost | 1 email credit if email found; 1 phone credit if phone found; 1 search credit if `profile_only=true` or no contact info found |
| Available to us | **Assumed yes.** The API docs do not gate endpoints by plan tier. All endpoints draw from a unified credit pool. NOT LIVE-PROVEN — a single call would confirm. |

### 1b. People Enrich

| Field | Value |
|-------|-------|
| REST route | `POST /v1/people/enrich` |
| Method | POST |
| Input | One of: `linkedin_url`, `email`, `phone` (required). Optionally: `full_name` or `first_name`+`last_name`, `company`, `company_domain`, `education`, `location`, `job_title`. `include` array: `work_email`, `personal_email`, `phone`. |
| Returns | Enriched profile: `email`, `workEmail`, `phone`, `fullName`, `headline`, `industry`, `linkedinUrl`, `company`, `location`, `summary`, `experience`, `education`, `skills`, `certifications`, `confidenceLevel`, `altMatches`. |
| Cost | 1 search credit if profile found; 1 email credit per email found; 1 phone credit per phone found |
| Available to us | **Assumed yes.** Same unified credit pool. NOT LIVE-PROVEN. |

### 1c. Contact Info from LinkedIn (Single)

| Field | Value |
|-------|-------|
| REST route | `GET /v1/people/linkedin` |
| Method | GET |
| Input | `profile` (LinkedIn URL, required), `include_phone` (boolean), `email_type` (`personal`, `work`, `personal,work`, `none`) |
| Returns | `email`, `work_email`, `work_email_status`, `personal_email`, `phone`, `github` |
| Cost | 1 email credit if email found; 1 phone credit if phone found |
| Available to us | **Assumed yes.** NOT LIVE-PROVEN. |

### 1d. Company Search

| Field | Value |
|-------|-------|
| REST route | `POST /v1/company/search` |
| Method | POST |
| Input | `name`, `domain`, `size`, `hq_only`, `location`, `industries`, `technologies`, `min_revenue`, `max_revenue`, `year_founded_from`, `year_founded_to`, `page`, `page_size` |
| Returns | Company profiles: `name`, `url`, `domain`, `email_domain`, `overview`, `type`, `size`, `country`, `revenue`, `founded_at`, `industry`, `headquarter`, `website`, `logo_url`, `specialties`, `technologies`, `locations`, `employees`, `followers`, `funding` |
| Cost | 1 search credit per company returned |
| Available to us | **Assumed yes.** NOT LIVE-PROVEN. |

### 1e. Email-to-LinkedIn

| Field | Value |
|-------|-------|
| REST route | `GET /v1/people/person` |
| Method | GET |
| Input | `email` (required) |
| Returns | `email`, `linkedin` (LinkedIn profile URL) |
| Cost | 1 email credit if profile found |
| Available to us | **Assumed yes.** NOT LIVE-PROVEN. |

### 1f. Personal Email Checker

| Field | Value |
|-------|-------|
| REST route | `GET /v1/people/linkedin/personal_email_status` |
| Method | GET |
| Input | `profile` (LinkedIn URL, required) |
| Returns | `email` (boolean — whether a personal email is available) |
| Cost | Not explicitly stated in API docs. Contact checker APIs have a 150 req/min rate limit (vs. 1000 for others), suggesting low or zero credit cost. **Unconfirmed.** |
| Available to us | **Assumed yes.** NOT LIVE-PROVEN. |

### 1g. Work Email Checker

| Field | Value |
|-------|-------|
| REST route | `GET /v1/people/linkedin/work_email_status` |
| Method | GET |
| Input | `profile` (LinkedIn URL, required) |
| Returns | Work email availability (boolean) |
| Cost | Not explicitly stated. Same rate limit tier as personal email checker. **Unconfirmed.** |
| Available to us | **Assumed yes.** NOT LIVE-PROVEN. |

### 1h. Phone Number Checker

| Field | Value |
|-------|-------|
| REST route | `GET /v1/people/linkedin/phone_status` |
| Method | GET |
| Input | `profile` (LinkedIn URL, required) |
| Returns | Phone number availability (boolean) |
| Cost | Not explicitly stated. Same rate limit tier. **Unconfirmed.** |
| Available to us | **Assumed yes.** NOT LIVE-PROVEN. |

### 1i. Batch Email Verification

| Field | Value |
|-------|-------|
| REST route | `POST /v1/email/verify/batch` (submit) + `GET /v1/email/verify/batch/{job_id}` (poll) |
| Method | POST then GET |
| Input | `emails` (array) on submit; `job_id` on poll |
| Returns | Per-email verdicts (same shape as single email-verifier) |
| Cost | Per-email verifier credits, same as single verification |
| Available to us | **Assumed yes.** NOT LIVE-PROVEN. |

### 1j. Bulk Contact Info (v1 and v2)

| Field | Value |
|-------|-------|
| REST route | `POST /v1/people/linkedin/batch` (v1, sync, max 100) or `POST /v2/people/linkedin/batch` + `GET /v2/people/linkedin/batch/{job_id}` (v2, async, max 1000) |
| Method | POST (+ GET for v2) |
| Input | `profiles` (array of LinkedIn URLs), `include_phone`, `email_type` |
| Returns | Per-profile contact info: emails, personal_emails, work_emails, phones |
| Cost | 1 email credit per profile if email found; 1 phone credit per profile if phone found |
| Available to us | **Assumed yes.** NOT LIVE-PROVEN. |

### Summary table

| # | Endpoint | Input shape | Returns | Cost | Available |
|---|----------|-------------|---------|------|-----------|
| 1 | LinkedIn Profile Enrich | LinkedIn URL | Full profile + optional contact | 1 search / 1 email / 1 phone | Assumed |
| 2 | People Enrich | email/phone/LinkedIn URL | Enriched profile + optional contact | 1 search + email/phone | Assumed |
| 3 | Contact Info (Single) | LinkedIn URL | Emails + phone | 1 email / 1 phone | Assumed |
| 4 | Company Search | firmographic filters | Company profiles | 1 search per result | Assumed |
| 5 | Email-to-LinkedIn | email address | LinkedIn URL | 1 email | Assumed |
| 6 | Personal Email Checker | LinkedIn URL | boolean | Unconfirmed | Assumed |
| 7 | Work Email Checker | LinkedIn URL | boolean | Unconfirmed | Assumed |
| 8 | Phone Checker | LinkedIn URL | boolean | Unconfirmed | Assumed |
| 9 | Batch Email Verify | email array | Per-email verdicts | Per-email verifier | Assumed |
| 10 | Bulk Contact Info | LinkedIn URL array | Per-profile contacts | Per-profile email/phone | Assumed |

All ten are **assumed available to our plan/key** based on the API docs not
gating by plan tier. None are live-proven. Confirming availability would
require one call per endpoint; confirming return shapes would require paid
calls where credits are consumed.

---

## 2. Does any of the ten close the prose-evidence gap?

### What `check_evidence` accepts

`check_evidence` in `src/llm.py:804` requires every evidence string to be
**traceable** to `fact_strings(rec)`. `traceable` (line 660) enforces two rules:

1. **Every adjacent pair of content words** in the claim must appear as an
   adjacent pair in **one** fact string. Not scattered across multiple facts —
   one fact must carry the claim's phrasing.
2. **Every number** in the claim must appear in some fact.

`fact_strings` (line 585) walks: `company`, `domain`, `context`, `signal`,
`company_facts` (key-value pairs emitted as `"key value"`), `contacts`,
`sizing`, and `research[].fact`.

The gap is that ContactOut's structured firmographics (industry, offices,
employees, tech stack, specialties) produce short fact strings like `"industry
SaaS"` or `"employees 48"`. The model cannot construct a traceable prose claim
from these because the adjacency rule requires the claim's phrasing to match a
single fact's phrasing. `"Acme helps teams ship faster"` needs a fact that
contains those words in that order — and no ContactOut field produces prose.

### Endpoint by endpoint

| Endpoint | Returns prose? | Could satisfy check_evidence? | Reason |
|----------|---------------|-------------------------------|--------|
| **LinkedIn Profile Enrich** | `summary` field is prose (a person's own LinkedIn summary). `experience` includes dated role descriptions. | **Partially.** The `summary` field is free-text prose that could contain adjacent-word-pair matches for claims about the person. But it is self-reported marketing copy, not a sourced fact about the company, and `check_evidence` is applied to `persona_angle` evidence about the company or the person's role — not their self-description. The `experience` field could supply traceable claims about role history ("VP Engineering at Acme since 2023") but this is structured data, not the "dated, attributable fact with a source URL" the gate is designed to require. |
| **People Enrich** | Same `summary`, `experience` shape as LinkedIn Enrich. | **Partially.** Same analysis. The `confidenceLevel` field is metadata, not evidence. |
| **Contact Info (Single)** | No. Emails and phone numbers only. | **No.** |
| **Company Search** | `overview` field is prose — a company description. | **Yes, potentially.** The `overview` field is a company description that could contain adjacent-word-pair matches. If it reads "Acme is a compliance platform for EU banks", then a claim "Acme builds compliance tools for European banks" would be traceable. However: (a) `overview` is the same field `company-information-from-domain` already returns as `description` (confirmed in the API docs for `/v1/domain/enrich`), and our adapter already trims it — it just does not include `description` in the current trim. (b) Company Search finds companies by filter criteria; we already have the company by domain. The same `overview` text comes from the same underlying data. |
| **Email-to-LinkedIn** | No. Just a URL. | **No.** |
| **Email/Phone Checkers (3)** | No. Booleans only. | **No.** |
| **Batch Email Verify** | No. Verdicts only. | **No.** |
| **Bulk Contact Info** | No. Contact details only. | **No.** |

### Verdict

**None of the ten endpoints close the prose-evidence gap in a way the current
adapter does not already partially hold.** The key finding:

- `company-information-from-domain` already returns a `description` field in
  the API response. The adapter's `company_info()` function does NOT include it
  in the trim — it returns `name`, `domain`, `email_domain`, `linkedin`,
  `employees`, `revenue`, `founded`, `industry`, `offices`, `specialties`,
  `stack`. Adding `description` to the trim would put company prose into
  `company_facts` and therefore into `fact_strings`, at zero additional credit
  cost. This is a **one-line adapter change**, not a new endpoint.

- `linkedin/enrich` returns `summary` (person-level prose), but this is
  self-reported LinkedIn copy, not the sourced, dated fact `check_evidence`
  is designed to require. It could help `persona_angle` for person-level
  claims but does not address the company-level evidence gap.

- The prose-evidence gap is genuinely closed by layers 3-4 of the routing
  policy (free crawler, Grok), which return sourced, dated prose with URLs.
  No ContactOut endpoint is designed for this.

---

## 3. Does any of the ten close the job-change gap?

### What the job-change gap requires

The pipeline needs a signal that a person recently changed roles — a reason to
reach out now rather than later. This requires either:

(a) A dedicated "changed since" query (ContactOut does not offer one), or
(b) Work history with dates that can be diffed against a previous snapshot to
    detect a change.

### Endpoint analysis

| Endpoint | Returns work history? | Can detect job changes? |
|----------|----------------------|------------------------|
| **LinkedIn Profile Enrich** | Yes — `experience` array with date ranges per role | **In theory, partially.** Returns current and past roles with start/end dates. A role with a recent start date (e.g., started 2 weeks ago) is a job-change signal. However: (1) it is a point-in-time snapshot, not a diff — you would need to store the previous snapshot and compare, which requires persistent state per person; (2) ContactOut does not offer a "changed since timestamp T" query; (3) the pipeline has no person-level state store for snapshot diffing. |
| **People Enrich** | Yes — same `experience` shape | **Same analysis.** Same limitations. |
| **People Search** (already implemented) | `experience` field available in search results | **Same analysis.** Already available but not wired, and the same snapshot-diff limitation applies. |
| All others | No work history | **No.** |

### Verdict

**`linkedin/enrich` and `people/enrich` return work history that could in
principle detect recent role changes, but the pipeline has no mechanism to
diff snapshots over time.** A job-change signal requires either:

1. A persistent person-level store with previous-role state (not built), or
2. An external push signal (LinkedIn change feeds, news APIs) that does not
   depend on snapshot diffing.

ContactOut does not offer a dedicated job-change endpoint. The gap is genuine
and is not closed by any of the ten unimplemented endpoints without
significant additional infrastructure. This confirms the TASK-206 finding that
the job-change gap licenses external signal monitoring (layers 3-4 of the
routing policy).

---

## 4. `people_search`: wire it or delete it

### What it does that `decision-makers` does not

`people_search` is already implemented in the adapter (`contactout.py:218`).
It takes a domain and optional filters (job_title, seniority, location) and
returns person profiles. `decision-makers` takes a domain and returns
decision-maker profiles. Both return the same person shape via `_people()`.

The differences:

| Aspect | `decision-makers` | `people_search` |
|--------|-------------------|-----------------|
| Input | domain (or name, or LinkedIn URL) | domain + optional filters |
| Filtering | None — returns all decision makers | job_title, seniority, location, skills, experience, etc. |
| Pagination | `page` parameter | `page` + `page_size` (1-25) |
| Contact info | `reveal_info` boolean | `reveal_info` boolean + `data_types` array |
| Cost | 1 search + 1 email per profile | 1 search + 1 email per profile |
| Production caller | `enrich.py:988` | **NONE** (only `validate.py:299`) |

### What it would add over `decision-makers`

The only functional advantage is **filtering**. `people_search` can ask for
"VPs of Engineering in Berlin" while `decision-makers` returns all decision
makers and lets the pipeline filter. But the pipeline does not need this:

1. The enrich pipeline calls `decision-makers` to find contacts at a
   qualified account. The account has already passed ICP qualification.
2. `personalization.py` selects from the returned contacts by persona match.
3. Adding `people_search` with seniority/title filters would pre-filter
   before personalization, but the same filtering happens downstream anyway.

### Where it would go if wired

If wired, `people_search` would sit in the `people_discovery` stage between
`decision-makers` and the Blitz fallback:

```
1. people-count (free)
2. decision-makers (primary)
3. people-search (optional refinement — same provider, same data)
4. Blitz fallback (different index)
5. AI Ark fallback (different index)
```

But step 3 adds nothing: it queries the same data source as step 2 with
different filters, at the same per-profile cost. A domain where
`decision-makers` found nobody is a domain where `people_search` will also
find nobody — the underlying index is the same.

### Recommendation: DELETE

`people_search` is an orphan method. It is implemented, tested, and called by
nothing in production. The pipeline does not need its filtering capability
because `decision-makers` returns the same people and `personalization.py`
handles selection downstream. Wiring it would add a step that costs credits
and returns a subset of what the previous step already returned.

The adapter method should be deleted. The `validate.py:299` dispatch case
should be removed. The `people-search` ROUTES entry should be removed. The
COSTS entry (if one exists — it does not, which is further evidence it was
never wired) needs no change.

**If Claude disagrees and wants to keep it:** it should remain as a dormant
adapter method with a comment explaining it is reserved for a future pipeline
that needs domain-scoped people search with filters. But the repository's rule
— "existence is not function" — says an uncalled method proves nothing and
should go.

---

## 5. Recommendations for the ten

### 5a. Worth adding: `linkedin/enrich` (endpoint 1)

| Aspect | Recommendation |
|--------|---------------|
| **Stage** | `email_discovery` |
| **Position** | After `decision-makers` (ContactOut primary), after Blitz email fallback, as a new ContactOut step before AI Ark |
| **Position (alternative)** | Could also sit in `people_discovery` as a person-level enrichment when the pipeline already holds a LinkedIn URL but no email |
| **Cost** | 1 email credit if email found, 1 search credit otherwise |
| **Licensing reason** | The pipeline holds a LinkedIn URL (from `decision-makers` or Blitz) but `decision-makers` returned no email. `linkedin/enrich` takes the URL we already have and asks ContactOut for contact info against it — same provider, different input shape (URL in, person out vs. domain in, people out). This is NOT the same call twice; it is a different query path. |
| **What it adds** | A second ContactOut contact-info path addressed by LinkedIn URL rather than by domain. Where `decision-makers` asks "who works at this domain" and gets people with emails, `linkedin/enrich` asks "what contact info do you have for this specific profile". The hit rate may differ because the lookup path is different. |
| **Caveat** | The cost is the same email credit as `decision-makers` already spends. The value is only in the different lookup path. This should be live-proven on 5-10 records before wiring, at a cost of ~5-10 email credits. |

**Wiring sketch (not implementation — for TASK-207/208):**

```python
# In waterfall.py, EMAIL_DISCOVERY stage, after Blitz email:
{"provider": CONTACTOUT, "call": "linkedin-enrich",
 "why": "the pipeline holds a LinkedIn URL and decision-makers returned no "
        "email; linkedin/enrich takes the URL we already have and asks "
        "ContactOut for contact info against it — a different lookup path",
 "requires_reason": enrich.CONTACTOUT_INCOMPLETE,
 "sufficient_when": "a work address came back"}
```

### 5b. Worth considering: `description` field from existing endpoint

Not a new endpoint, but a gap in the existing trim. `company_info()` in
`contactout.py` does not include the `description` field from the
`/v1/domain/enrich` response. Adding it would put company-level prose into
`company_facts`, which flows into `fact_strings`, which is the pool
`check_evidence` checks against.

| Aspect | Recommendation |
|--------|---------------|
| **Cost** | Zero additional credits — the data is already returned |
| **Change** | One line in `company_info()`: add `"description": _present(first(raw, "description", "overview"))` to the return dict |
| **Impact on prose-evidence gap** | Partial. A company description is prose and could supply traceable claims. But it is typically one sentence of marketing copy, not a dated, sourced fact. It helps but does not close the gap. |
| **Risk** | Low. The field is already in the API response; the adapter just drops it. |

This is a one-line change that should be done regardless of whether any new
endpoints are added. It is NOT in scope for this task (which recommends, not
implements), but it is the single highest-value change identified.

### 5c. Not worth adding: the remaining eight

| Endpoint | Why not |
|----------|---------|
| **People Enrich** | Same data as `linkedin/enrich` but with a different input shape (name+company instead of URL). The pipeline always has a URL by the time it needs contact info. Adding a second path to the same data is redundancy, not capability. |
| **Contact Info (Single)** | Subset of `linkedin/enrich`. Returns only contact details without the profile. If we already have the LinkedIn URL, `linkedin/enrich` gives us both the profile and the contact info for the same email credit. |
| **Company Search** | Returns the same firmographic data as `company-information-from-domain`. The geography and company_type issues are data quality, not endpoint selection (confirmed by TASK-206 section 4). A search-by-filter interface does not help when we already have the domain. |
| **Email-to-LinkedIn** | The pipeline starts from domains, not emails. There is no stage where we have an email address and need a LinkedIn URL — the flow is the other direction. |
| **Personal Email Checker** | Returns a boolean. The pipeline needs the actual email, not a prediction of whether one exists. A boolean "yes, there is a personal email" without the address is not actionable. |
| **Work Email Checker** | Same as personal email checker. We need the address, not a boolean. |
| **Phone Checker** | The pipeline does not use phone numbers. Outreach is email-only. |
| **Batch Email Verify** | The pipeline verifies emails one at a time as they are discovered. Batch verification would only help at scale, and the per-email cost is identical. The current single-verify path is simpler and already works. |
| **Bulk Contact Info (v1/v2)** | Same analysis as batch verify. The pipeline discovers contacts one domain at a time. Bulk endpoints are for a different usage pattern — uploading a list of LinkedIn URLs and getting contacts back. The pipeline does not have a list of URLs waiting; it discovers them one at a time. |

---

## 6. Summary

| Question | Answer |
|----------|--------|
| Does any of the ten close the prose-evidence gap? | **No.** `company-search` returns an `overview` field, but the same data is already in the `company-information-from-domain` response as `description` — the adapter just does not include it in the trim. Adding `description` to the trim is a one-line change at zero additional credit cost and partially addresses the gap. The rest of the gap is genuinely unbridgeable by ContactOut and is correctly assigned to layers 3-4 (crawler, Grok). |
| Does any close the job-change gap? | **No.** `linkedin/enrich` and `people/enrich` return work history with dates, but detecting a change requires snapshot diffing over time, which the pipeline does not support. ContactOut offers no "changed since" query. The gap is genuine. |
| Wire or delete `people_search`? | **Delete.** It is an orphan method with no production caller. It queries the same data as `decision-makers` at the same cost, and the pipeline does not need its filtering capability. |
| Which endpoints are worth adding? | **One: `linkedin/enrich`** in the `email_discovery` stage, as a second ContactOut path addressed by LinkedIn URL. And **one adapter change: add `description` to the `company_info()` trim** at zero additional cost. |
| What should be live-proven before wiring? | Whether `linkedin/enrich` returns contact info for profiles where `decision-makers` did not. 5-10 records, ~5-10 email credits. |

---

*Prepared 2026-09-16 for TASK-212. No live API calls were made. All capability
claims are derived from the official ContactOut API reference at
api.contactout.com, cross-referenced against the adapter in
`src/providers/contactout.py`, the waterfall in `src/waterfall.py`, the enrich
pipeline in `src/enrich.py`, and the evidence gate in `src/llm.py`.*
