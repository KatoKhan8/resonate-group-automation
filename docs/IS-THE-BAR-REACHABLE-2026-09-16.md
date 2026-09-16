# Is `icp_pass` reachable at all?

**TASK-187** | 2026-09-16 | Snapshot: `work/queue.snapshot.jsonl`
**Snapshot stamp:** 2026-09-15T17:52:12+00:00 from master cf23154, 550 records

---

## 1. The exact `verdict_of` rule

Quoted from `src/icpstructural.py` lines 490-499:

```python
def verdict_of(criteria):
    statuses = {name: answer["status"] for name, answer in criteria.items()}
    if FAIL in statuses.values():
        return ICP_FAIL
    if all(status in PASSING for status in statuses.values()):
        return ICP_PASS
    if all(statuses.get(name) in PASSING for name in DEFINING):
        return ICP_PASS_WITH_UNCERTAINTY
    return ICP_REVIEW
```

Where:

| Constant | Value | Meaning |
|----------|-------|---------|
| `PASSING` | `(PASS, PASS_WITH_TOLERANCE, NOT_REQUIRED)` | A criterion that does not block |
| `DEFINING` | `("geography", "company_type")` | The two that decide what KIND of company this is |
| `FAIL` | `"fail"` | Affirmative evidence against a criterion |
| `UNKNOWN` | `"unknown"` | Could not be established |

**The rule in English:**

1. **Any FAIL → `icp_fail`** — affirmative evidence against any client criterion is a rejection, however good the rest looks.
2. **All five PASSING → `icp_pass`** — every criterion satisfied or not required.
3. **Both DEFINING (geography + company_type) PASSING → `icp_pass_with_uncertainty`** — the company is the right kind, in the right place, but something else is unknown.
4. **Otherwise → `icp_review`** — the defining criteria are not both established.

**`icp_pass` does NOT require all five to PASS in the sense the task feared.** It does require all five PASSING for the *pure* form, but the *uncertainty* form requires only the two defining criteria, and BOTH forms map to `icp_status = "qualified"` downstream.

### The FROM_STRUCTURAL mapping

From `src/icp.py` lines 826-831:

```python
FROM_STRUCTURAL = {
    icpstructural.ICP_PASS: QUALIFIED,
    icpstructural.ICP_PASS_WITH_UNCERTAINTY: QUALIFIED,
    icpstructural.ICP_REVIEW: REVIEW,
    icpstructural.ICP_FAIL: REJECTED,
}
```

Both `icp_pass` and `icp_pass_with_uncertainty` produce `icp_status = "qualified"`. The pipeline does not distinguish between them downstream.

---

## 2. How the 113 qualified records got there

**All 113 qualified records reached qualification via `icp_pass_with_uncertainty`.** Zero reached `icp_pass`. The contradiction in the task — "32 records reached CAMPAIGN_READY but the bar seems unsatisfiable" — is resolved: the bar is `icp_pass_with_uncertainty`, not `icp_pass`, and it is satisfiable.

### Traced verdicts of five qualified records

| # | Domain | Geo | Type | Svc | Emp | TT | Verdict |
|---|--------|-----|------|-----|-----|----|---------|
| 1 | ogpartner.dk | pass | pass | pass | unknown | unknown | icp_pass_with_uncertainty |
| 2 | px-355075e3f546 | pass | pass | pass | pass | unknown | icp_pass_with_uncertainty |
| 3 | 16kagency.com | pass | pass | pass | pass | unknown | icp_pass_with_uncertainty |
| 4 | 25wat.com | pass | pass | unknown | pass_with_tolerance | unknown | icp_pass_with_uncertainty |
| 5 | px-6a518e690008 | pass | pass | pass | pass | unknown | icp_pass_with_uncertainty |

**Pattern:** Every qualified record has `geography=pass` and `company_type=pass` (the DEFINING criteria). `tracks_time` is `unknown` on all 113. Other criteria vary: `services_business` and `employees` are sometimes unknown or pass_with_tolerance, but never fail.

### Criteria combinations across all 113 qualified records

| Count | Geography | Company Type | Services | Employees | Tracks Time |
|-------|-----------|-------------|----------|-----------|-------------|
| 36 | pass | pass | pass | pass | unknown |
| 24 | pass | pass | unknown | pass | unknown |
| 21 | pass | pass | unknown | unknown | unknown |
| 18 | pass | pass | pass | unknown | unknown |
| 8 | pass | pass | unknown | pass_with_tolerance | unknown |
| 6 | pass | pass | pass | pass_with_tolerance | unknown |

**Every single one** has `tracks_time=unknown`. This is not a coincidence — it is because zero records in the estate carry billing/time-tracking phrases in their structured text.

---

## 3. The `tracks_time` criterion

### How it resolves

From `src/icpstructural.py` lines 431-453:

```python
def _tracks_time(rec, segment, rules):
    if not rules["tracks_time_required"]:
        return NOT_REQUIRED
    model = _norm(segment.get("business_model"))
    if model in {_norm(m) for m in NOT_SERVICES}:
        return FAIL    # product/ecommerce doesn't bill time
    found = tracks_time_evidence(rec)
    if found:
        return PASS    # billing phrases found
    return UNKNOWN     # absence of evidence is not evidence of absence
```

The evidence phrases (`TIME_EVIDENCE`) are: "billable", "timesheet", "time tracking", "time-tracking", "hourly rate", "per hour", "utilisation", "utilization", "chargeable", "logged hours", "retainer", "day rate", "time and materials".

### Current distribution across 300 processed records

| Status | Count |
|--------|-------|
| unknown | 294 |
| fail | 6 |
| pass | **0** |

The 6 fails are all product/ecommerce businesses (4imprint.com, arian.com, theapexagencyagency.com, gavipop.com, vsblty.net, platinumstorage.com). They are rejected, not qualified.

**Zero records have `tracks_time=pass`.** Not one record in 550 carries billing phrases in the structured text fields (`company_facts.industry`, `description`, `tagline`, `specialties`, `services`).

---

## 4. How many of 550 can reach `icp_pass`?

### If every purchasable fact were bought (processed 300 only)

| Scenario | Qualified | icp_pass (pure) | icp_pass_with_uncertainty |
|----------|-----------|-----------------|---------------------------|
| Current state | 113 | 0 | 113 |
| tracks_time → PASS for all UNKNOWN | 113 | 113 | 0 |
| ALL unknowns → PASS (theoretical max) | 179 | 179 | 0 |

**Key insight:** Resolving `tracks_time` changes the *form* of qualification (from `icp_pass_with_uncertainty` to `icp_pass`) but NOT the *count* of qualified records. The 113 records are already qualified. The 66 review records are blocked by geography/company_type unknowns, not by tracks_time.

### The 250 unprocessed records

These records have **zero data** — no `company_facts`, no waterfall calls, no segment classification. Every criterion is unanswerable from current data. They need:

- `company-info` (domain) for industry, employees, location
- Website text for business model and time-evidence phrases
- Headcount resolution for the employee floor

The theoretical maximum from these 250 is 250 qualified (if every record happened to pass every criterion). The practical maximum depends entirely on what the data says after enrichment.

### Total reachability

| Pool | Current qualified | Max qualified (all unknowns resolved) |
|------|-------------------|---------------------------------------|
| Processed (300) | 113 | 179 |
| Unprocessed (250) | 0 | 250 (theoretical) |
| **Total (550)** | **113** | **429 (theoretical)** |

---

## 5. What actually gates person-credit spend

### The gate chain

```
enrich.person_level_allowed(rec)
  → qualify.state_of(rec) in (dmplan.QUALIFIED, dmplan.DM_APPROVED)
    → qualification.verdict.icp_status == "qualified"
      → FROM_STRUCTURAL[structural.verdict] == QUALIFIED
        → structural.verdict in (ICP_PASS, ICP_PASS_WITH_UNCERTAINTY)
          → DEFINING criteria (geography, company_type) both PASSING
            → no criterion FAILs
```

### The real predicate

**`geography=PASS` AND `company_type=PASS` AND no FAIL on any criterion.**

That is the bar. Not `tracks_time=PASS`. Not `employees=PASS`. Not all five. The two defining criteria and the absence of affirmative counter-evidence.

### `dmplan.may_enrich` (the "single gate")

From `src/dmplan.py` lines 291-335:

- `icp_status == REJECTED` → refused, always
- `human_review.decision == "reject"` → refused, always
- `icp_status in (REVIEW, UNKNOWN)` → refused unless `allow_review_enrichment` is true AND a human has reviewed and accepted
- `icp_status == QUALIFIED` → allowed (if the batch fingerprint is current)

---

## 6. Is the bar unsatisfiable?

**No.** The bar is being satisfied. 113 records are qualified. The system is working as designed.

The task feared that `tracks_time=UNKNOWN` blocks qualification. It does not. The code explicitly handles this case:

> "UNKNOWN is not FAIL, and that is the whole point. A criterion this system could not establish leaves the company eligible with uncertainty. Only affirmative evidence of a violation fails it."

The `icp_pass_with_uncertainty` verdict was designed for exactly this situation — the right kind of company, in the right place, with some criteria not yet established — and it maps to `qualified` for pipeline purposes.

### The actual bottlenecks

| Bottleneck | Records affected | What would unblock |
|------------|-----------------|-------------------|
| 250 records with zero data | 250 | Company-info enrichment (domain → industry, employees, location, business model) |
| 66 review records blocked on defining criteria | 66 | Location evidence (geography) and/or vertical classification (company_type) |
| `tracks_time` unknown on all 300 processed | 113 qualified but at uncertainty | Billing-phrase evidence from website crawl or job postings — changes form but not count |

### If the operator wants `icp_pass` (the pure form)

The options, with record counts:

| Option | Records it would move to icp_pass | Cost | Risk |
|--------|-----------------------------------|------|------|
| A. Find billing phrases in existing data | 0 (avenue exhausted) | None | Already checked |
| B. Apify website crawl for billing language | Up to 113 (unknown how many carry phrases) | 113 Apify credits | Agencies may not publish billing language on websites |
| C. Job postings as evidence source | Unknown (new source needed) | Development + provider credits | PSA/time-tracking terms may not appear in job postings either |
| D. Accept `icp_pass_with_uncertainty` as the gate | 0 (already the case) | None | This is what the code already does |

**Option D is already in effect.** The 113 qualified records are eligible for person-credit spend right now. The system is not blocked on `tracks_time`.

---

## 7. The review records: why they are stuck

All 66 review records have the defining criteria not both PASS:

| Unknown combination | Count |
|--------------------|-------|
| All five unknown | 27 |
| geography + employees + tracks_time | 13 |
| geography + services_business + employees + tracks_time | 9 |
| geography + services_business + tracks_time | 5 |
| company_type + services_business + employees + tracks_time | 4 |
| company_type + services_business + tracks_time | 4 |
| geography + tracks_time | 3 |
| company_type + geography + services_business + tracks_time | 1 |

**Every single review record has geography or company_type unknown.** Zero review records are blocked solely by `tracks_time`. Resolving `tracks_time` would change the qualification count by exactly zero.

---

## Summary

| Question | Answer |
|----------|--------|
| Does `icp_pass` require all five to PASS? | Yes, for the pure form. But `icp_pass_with_uncertainty` requires only the two defining criteria, and BOTH map to `qualified`. |
| How did the 113 qualified records get there? | Via `icp_pass_with_uncertainty`: geography=pass, company_type=pass, no fails, tracks_time=unknown. |
| How many of 550 can reach `icp_pass`? | Currently 0. Theoretically 179 from processed 300 (if all unknowns resolved to PASS). 250 unprocessed records are unevaluable. |
| How many can reach `qualified`? | Currently 113. Theoretically 179 from processed 300. |
| What actually gates person-credit spend? | `qualify.state_of(rec) in (QUALIFIED, DM_APPROVED)`, which requires `icp_status == "qualified"`, which is reached by `icp_pass_with_uncertainty`. |
| Is the bar unsatisfiable? | **No.** 113 records are qualified. The bar is `icp_pass_with_uncertainty`, not `icp_pass`. |
| What is the real bottleneck? | 250 records with zero data, and 66 review records blocked on geography/company_type — not tracks_time. |
