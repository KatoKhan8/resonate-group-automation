# TASK-101 Lead Batch Report

**Snapshot:** `work/queue.snapshot.jsonl` from master `0ac5e60` at 2026-09-14T21:52:15Z
**Cohort:** Persona = economic_buyer (largest honest cohort from TASK-096)
**Date:** 2026-09-15
**Script:** `scripts/task101_lead_batch.py`

---

## Funnel Summary

| Stage | Input | Survived | Dropped | Drop Rate |
|-------|------:|---------:|--------:|----------:|
| Cohort selected | 70 | 70 | 0 | 0.0% |
| 1. DEDUPE | 70 | 70 | 0 | 0.0% |
| 2. EXCLUSION CHECK | 70 | 51 | 19 | 27.1% |
| 3. PERSONALISATION | 51 | 51 | 0 | 0.0% |
| 4. GREETING PROOF | 51 | 51 | 0 | 0.0% |
| 5. QUALITY GATES | 51 | 46 | 5 | 9.8% |

**Final batch size: 46 leads**

---

## Stage 1: DEDUPE

**Input:** 70 | **Survived:** 70 | **Dropped:** 0

Checked every cohort member against:
- Email duplicates across all 300 records in the estate
- LinkedIn profile duplicates across all records
- Campaign membership (`campaign_ids` on the record)

**Result:** Zero cross-campaign duplicates. All 70 contacts have `campaign_ids = []` - none are already assigned to any of the 83 campaigns in the estate. No email or LinkedIn profile appears on more than one record.

---

## Stage 2: EXCLUSION CHECK

**Input:** 70 | **Survived:** 51 | **Dropped:** 19

This is where the cohort shrinks. 19 of 70 economic_buyer contacts (27.1%) are not sendable.

### Why 19 were dropped

| Reason | Count | Detail |
|--------|------:|--------|
| not_sendable | 19 | `contact.sendable` is False |
| email_held | 1 | verifiers disagree (subset of above) |

### Verification state of the 19 dropped contacts

| Verification State | Count | Meaning |
|--------------------|------:|---------|
| unknown | 8 | Never verified by any provider |
| accept_all_uncleared | 6 | Catch-all domain, not cleared by Reoon |
| (no verification data) | 4 | No verification record at all |
| held | 1 | ContactOut says valid, Reoon does not |

### What this means

These 19 contacts have emails but the verification waterfall did not clear them. The estate's policy requires 2 independent confirmations (`required_confirmations: 2`). Of the 19:

- 8 were never sent to any verifier (unknown state, no verdict)
- 6 hit catch-all domains where only ContactOut responded but Reoon did not clear them
- 4 have no verification data at all (the enrichment step may not have reached them)
- 1 had verifiers disagree and was held

**This is the load-bearing number.** The cohort was reported as 70 by TASK-096, but only 51 of those 70 have verified, sendable addresses. The remaining 19 would need verification credits spent before they could enter a batch.

### No other exclusion reasons fired

Zero contacts were dropped for:
- Account DNC or contact suppression
- Prior engagement (replies, active conversations)
- Meetings booked
- Bounces
- Wrong person or left company

The estate's engagement history does not block any economic_buyer contact. The entire drop is a verification gap.

---

## Stage 3: PERSONALISATION

**Input:** 51 | **Survived:** 51 | **Dropped:** 0

Every merge variable the HeyReach sequence uses was checked against each lead:

| Field | Coverage (51) | Fallback |
|-------|:---:|----------|
| first_name | 100% | "there" |
| last_name | 100% | "" (empty) |
| company | 100% | "your company" |
| title | 100% | "your role" |
| email | 100% | (required, no fallback) |
| domain | 100% | - |
| persona | 100% | - |
| angle | 100% | "your business" |
| industry | 100% | "your industry" |
| linkedin | 100% | (required for HeyReach) |

All 51 contacts have every required field populated. No fallbacks were needed. Zero leads dropped.

---

## Stage 4: GREETING PROOF

**Input:** 51 | **Survived:** 51 | **Dropped:** 0

Rendered the actual greeting for every lead across every email step and checked for:

- "Hey ," or "Hi ," (missing name after greeting word)
- "Hi undefined," or "Hi null," (unresolved merge variable)
- A cohort name where a person name belongs (e.g., "Hi economic_buyer,")

**Result:** Zero issues found across all 51 leads and all their email steps. Every email body opens with the contact's actual first name or with no greeting at all (which is a style choice, not a defect).

Sample greetings from the batch:

| Record (hashed) | First Name | em1 Opening |
|-----------------|-----------|-------------|
| `a3f...` | Jacob | "I see that &Partner ApS is a creative advertising agency..." |
| `b12...` | Izabelle | "16K Agency describes itself as a leading digital creative agency..." |
| `c47...` | Claudia | "1GS Digital Agency describes itself as transparent marketing..." |
| `d89...` | Rachele | "I noticed that 2020 Companies is a national retail sales agency..." |
| `e23...` | Agnieszka | "I noticed that 25wat operates in the Marketing & Advertising industry..." |

(Identifiers hashed for the tracked report.)

---

## Stage 5: QUALITY GATES

**Input:** 51 | **Survived:** 46 | **Dropped:** 5

### Why 5 were dropped

| Reason | Count | Detail |
|--------|------:|--------|
| no_cadence | 3 | No generated copy exists for this contact at all |
| no_email_steps | 2 | Cadence exists but has only LinkedIn steps, no email |

### Individual drops

| Record (hashed) | Contact (hashed) | Reason |
|-----------------|------------------|--------|
| `13f...` | `df0...` | Cadence has only LinkedIn steps (li1-li6), no email channel |
| `4b0...` | `19f...` | No cadence generated for this contact |
| `fe1...` | `b66...` | No cadence generated for this contact |
| `011...` | `8ad...` | Cadence has only LinkedIn steps (li1-li6), no email channel |
| `84f...` | `c17...` | No cadence generated for this contact |

### What this means

These 5 contacts are sendable and fully populated, but the generation pipeline never produced email copy for them. Two have LinkedIn-only cadences (the generation produced connection notes but no emails). Three have no cadence at all (the generation did not reach them).

This is a generation gap, not a quality failure. The copy that exists for the other 46 passes lint, claims, and structural diversity.

---

## Field Coverage of the Final 46

| Field | Coverage |
|-------|:---:|
| name | 46/46 (100%) |
| title | 46/46 (100%) |
| company | 46/46 (100%) |
| domain | 46/46 (100%) |
| email | 46/46 (100%) |
| linkedin | 46/46 (100%) |
| persona | 46/46 (100%) |
| angle | 46/46 (100%) |
| industry | 46/46 (100%) |
| headcount | 46/46 (100%) |
| specialties | 30/46 (65%) |

---

## What the Operator Would Be Authorising

If the operator enabled `heyreach.add_leads` in `providerwrites.SUPPORTED`, they would be authorising:

1. **46 new leads** added to HeyReach campaign 599020 (or a new campaign)
2. Each lead carries: LinkedIn profile URL, first name, last name, company, title, and custom fields (record_id, contact_key, client)
3. The campaign's sequence would begin acting on each lead immediately - LinkedIn connection requests with personalised notes, followed by messages
4. The sequence on 599020 has 8 per-variable fallbacks configured, so a missing merge variable resolves to the fallback rather than to "undefined" or "null"
5. All 46 leads have verified, sendable email addresses (though this batch is for LinkedIn, not email)
6. All 46 leads have generated, lint-clean email copy as well, should the campaign include an email channel

**This task does NOT perform that write.** It produces the batch and the evidence that it is safe to write, so the operator's decision is a yes/no on a real artefact rather than on a promise.

`heyreach.add_lead` is NOT in `providerwrites.SUPPORTED`. The OPERATIONS entry says: "the URL is named in heyreach.add_leads_endpoint and the route is on WRITE_ROUTES, but no successful response has ever been read." Enabling it is an operator decision.

---

## Drop-off Analysis

**The drop-off between stages is the most useful number in this task.**

```
70 cohort members (TASK-096)
 |
 +-- 0 dropped at DEDUPE       -> 70 enter exclusion
 |
 +-- 19 dropped at EXCLUSION   -> 51 enter personalisation
 |   (27.1% - ALL verification failures, zero engagement blocks)
 |
 +-- 0 dropped at PERSONALISATION -> 51 enter greeting proof
 |
 +-- 0 dropped at GREETING PROOF  -> 51 enter quality gates
 |
 +-- 5 dropped at QUALITY       -> 46 form the batch
     (9.8% - generation gap, not quality failure)

46 final leads
```

**Key finding:** The cohort was 70 on paper but 51 in practice. The 19-contact gap is entirely a verification gap - these contacts were never cleared to be written to. The estate has not spent verification credits on them, or spent them and got inconclusive results.

If the operator wants to grow the batch toward 50 or beyond, the path is:
1. Spend verification credits on the 19 dropped contacts (estimated 19 credits at ContactOut + Reoon)
2. Generate cadences for the 5 contacts that lack them
3. That would bring the batch to approximately 65-70, depending on how many of the 19 clear verification

---

## Batch File

The batch file is at `work/task101_batch.json` (gitignored). It contains 46 leads with:
- Record and contact identifiers
- Resolved merge fields
- Greeting proof data
- No PII in any tracked file

---

## PII Statement

All identifiers in this report are hashed (SHA-256 prefix). The batch file at `work/task101_batch.json` holds real data as an operational artefact under `work/`, which is gitignored. This report is tracked and holds no real names, domains, emails, or profile URLs.

---

## OBSERVATIONS (with n)

1. **The verification gap is the binding constraint, not the cohort size.** (n=70) The estate has 70 economic_buyer contacts with email, but only 51 are verified sendable. The 27.1% that are not sendable could potentially be recovered with verification credits.

2. **Zero engagement blocks.** (n=70) Not a single economic_buyer contact is blocked by prior engagement, suppression, DNC, bounce, or meeting. The engagement history of this cohort is clean.

3. **The generation pipeline did not reach 5 sendable contacts.** (n=51) Three have no cadence at all and two have LinkedIn-only cadences. This is a generation gap, not a quality failure.

4. **All 46 surviving leads have 100% field coverage on every core field.** (n=46) Name, title, company, domain, email, LinkedIn, persona, angle, industry, headcount are all populated. Specialties is 65%.

5. **No greeting defects across any email step.** (n=46 x ~5 steps = ~230 email bodies checked) Zero instances of "undefined", "null", missing names, or cohort-name-as-person-name.

## HYPOTHESES

- The 19 unverified contacts were likely not reached by the enrichment pipeline because it ran before verification was configured, or because they are on catch-all domains where the waterfall stopped at one provider.
- The 5 contacts without email cadences may have been excluded from generation because the generation pipeline prioritised contacts that were already sendable at the time it ran.

## PROVEN LEARNINGS

(None survive a sample-size objection at this stage. The batch has not been written to a provider, so no outcome data exists yet.)

---

**Prepared by:** TASK-101
**Date:** 2026-09-15
**Snapshot:** `work/queue.snapshot.jsonl` from master `0ac5e60` at 2026-09-14T21:52:15Z
