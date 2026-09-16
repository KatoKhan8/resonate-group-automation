---
title: "Bison Canary Cohort — After the Collision Check"
task: "TASK-177"
date: "2026-09-16"
builds_on:
  - "docs/BISON-CONTROL-PAYLOAD-2026-09-16.md"
  - "docs/BISON-PREWRITE-2026-09-16.md"
---

# Bison Canary Cohort — After the Collision Check

**TASK-177 deliverable.** Per-contact prior-contact counts from the provider, the three survival numbers, the persona=None contacts, the cost of a persona-only canary, and the final recommended cohort.

**Snapshot:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

**PII policy:** Every identifier is SHA-256 hashed (12 hex chars). No email address, person name, company name, or domain appears in this document. The domain `<domain:da9fa0575ce8>` was already reported unhashed in TASK-170's result block; it is hashed here and not propagated further.

**Method:** `scripts/task177_collision_per_contact.py` loads the 17 cohort contacts from the snapshot, groups them by domain (17 unique domains), and calls `collision.leads_for_domain()` for each domain against the provider. For each contact, it checks whether their specific email address appears in the leads returned for their domain, and if so, reports the per-campaign breakdown from `collision.touches_of()`.

**Workspace:** `<workspace:4a44dc153642>` (hashed). The `expect_workspace` guard was satisfied.

## 1. Per-Contact Prior Contact Counts

Each contact's email was looked up in the provider's lead list for their domain. "Prior emails" is the `emails_sent` field from the provider's `overall_stats` for that specific lead row. "In sequence" is whether any `lead_campaign_data` entry has status `in_sequence`.

| # | rec_id_hash | contact_hash | domain_hash | persona | angle | prior_emails | in_sequence | campaigns | verdict |
|---|-------------|--------------|-------------|---------|-------|--------------|-------------|-----------|---------|
| 1 | b580268f93f2 | b6882cfd6d48 | da9fa0575ce8 | economic_buyer | founder | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 2 | 90dc872ce83e | 32ab93ceddc6 | 4efeb3fe2afd | economic_buyer | founder | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 3 | ff930f49050f | dd4e53f0860a | c768a0660316 | economic_buyer | founder | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 4 | d881cb9457f6 | 8cdfd2d06cae | 68af8ce671c1 | economic_buyer | operations | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 5 | 9d2802e5f931 | 33afc169e069 | 63084828d69e | economic_buyer | founder | 0 | no | 0 (not in leads) | PASS |
| 6 | 4b37ea891b56 | 04b2cd185949 | 3afb5e0010d9 | **None** | **None** | 0 | no | 0 (not in leads) | PASS |
| 7 | d00a60562edd | 164c11029ec9 | 500976b76607 | economic_buyer | founder | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 8 | 73636ff041b0 | aaaba6610b02 | ceb55a89127b | economic_buyer | founder | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 9 | 646934233472 | 2aa47f23fd95 | 1203bef7ae16 | economic_buyer | founder | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 10 | 8953a27075c2 | d2844b2886b3 | c3f09366d72f | **None** | **None** | **21** | no | 3 (all sequence_finished; 8+8+5 sent, 0 replies) | **FAIL** |
| 11 | a02d0a715cb8 | c243e114f58c | 395be3330be3 | economic_buyer | founder | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 12 | aa86bcae3d3f | 4c0edf0fb2c4 | f2f4b0d278ed | **None** | **None** | 0 | no | 0 (not in leads) | PASS |
| 13 | b15936a38d71 | 177f9fa54bfb | c3c9e6e49e77 | economic_buyer | founder | 0 | no | 1 (sending_paused, 0 sent) | PASS |
| 14 | 024ba413ded7 | d4cebca2a680 | a3a16ee58d26 | **None** | **None** | 0 | no | 0 (not in leads) | PASS |
| 15 | 9888d6a9d54d | 0955c3c3cc63 | 41da47c0d97b | **None** | **None** | 0 | no | 0 (not in leads) | PASS |
| 16 | 73dff24eb5e8 | 3f3976404204 | ddef577b8d3c | economic_buyer | founder | 0 | no | 0 (not in leads) | PASS |
| 17 | 83cc7c8ac60b | 27c77cac3505 | 947f2f9d81ff | **None** | **None** | 0 | no | 0 (not in leads) | PASS |

### Domain-level context

The collision check pages by domain. Four domains have prior emails at the provider to leads OTHER than the cohort contact:

| domain_hash | leads at domain | total emails at domain | cohort contact's emails | notes |
|-------------|-----------------|------------------------|-------------------------|-------|
| da9fa0575ce8 | 2 | 13 | 0 (sending_paused) | The 13 emails are to a different person at the same domain. This is the domain TASK-170's check 7 flagged. |
| 63084828d69e | 2 | 42 | 0 (not in leads) | The 42 emails are to a different person. Cohort contact is not in the provider's leads at all. |
| c3f09366d72f | 1 | 21 | **21** (3 campaigns) | The cohort contact IS the lead. 21 emails across 3 finished campaigns, 0 replies. |
| a3a16ee58d26 | 1 | 5 | 0 (not in leads) | The 5 emails are to a different person. Cohort contact is not in the provider's leads. |

Nine domains have exactly 1 lead at the provider (the cohort contact) with 0 emails sent, status `sending_paused`. These are leads loaded into the provider's estate but never emailed.

Four domains have no leads at the provider at all.

## 2. The Three Numbers

| Category | Count | Meaning |
|----------|-------|---------|
| **Zero prior provider contact** | **16** | The specific email address has never been emailed by this provider. Either not found in the provider's leads at all (7 contacts), or found as a lead with 0 emails sent (9 contacts, all `sending_paused`). |
| **Some prior provider contact** | **1** | Contact #10 (`<rec:8953a27075c2>`) at domain `<domain:c3f09366d72f>`: 21 prior emails across 3 campaigns, all `sequence_finished`, 0 replies. |
| **Undetermined** | **0** | Every domain was checked successfully. No paging failure, no timeout, no unresolvable domain. |

**No contact falls into the undetermined category.** Every domain was paged successfully and every contact's email was either found or not found in the results. There is no "could not check" group to fold into the "clean" group.

## 3. The persona=None Contacts

TASK-167 reported seven contacts with `persona=None`. The data shows **six**, not seven. TASK-167's result block lists six contact numbers (#6, #10, #12, #14, #15, #17) but says "seven" in the text. The snapshot confirms six contacts with `persona=None` and `angle=None`:

| # | rec_id_hash | contact_hash | domain_hash | collision verdict |
|---|-------------|--------------|-------------|-------------------|
| 6 | 4b37ea891b56 | 04b2cd185949 | 3afb5e0010d9 | PASS (not in leads) |
| 10 | 8953a27075c2 | d2844b2886b3 | c3f09366d72f | **FAIL** (21 prior emails) |
| 12 | aa86bcae3d3f | 4c0edf0fb2c4 | f2f4b0d278ed | PASS (not in leads) |
| 14 | 024ba413ded7 | d4cebca2a680 | a3a16ee58d26 | PASS (not in leads) |
| 15 | 9888d6a9d54d | 0955c3c3cc63 | 41da47c0d97b | PASS (not in leads) |
| 17 | 83cc7c8ac60b | 27c77cac3505 | 947f2f9d81ff | PASS (not in leads) |

Five of the six persona=None contacts survive the collision check. Contact #10 does not.

These six receive the champion persona's finance angle regardless of their actual role. The configured fallback behaviour, not a defect, but it means they get finance-oriented copy for a role that was not classified.

## 4. The Cost of a Persona-Only Canary

The task asks: if the canary is restricted to contacts whose angle is their own (persona != None), how many survive?

**11 contacts have persona != None.** All 11 survive the collision check:

| # | rec_id_hash | persona | angle | collision verdict |
|---|-------------|---------|-------|-------------------|
| 1 | b580268f93f2 | economic_buyer | founder | PASS |
| 2 | 90dc872ce83e | economic_buyer | founder | PASS |
| 3 | ff930f49050f | economic_buyer | founder | PASS |
| 4 | d881cb9457f6 | economic_buyer | operations | PASS |
| 5 | 9d2802e5f931 | economic_buyer | founder | PASS |
| 7 | d00a60562edd | economic_buyer | founder | PASS |
| 8 | 73636ff041b0 | economic_buyer | founder | PASS |
| 9 | 646934233472 | economic_buyer | founder | PASS |
| 11 | a02d0a715cb8 | economic_buyer | founder | PASS |
| 13 | b15936a38d71 | economic_buyer | founder | PASS |
| 16 | 73dff24eb5e8 | economic_buyer | founder | PASS |

**A persona-only canary costs nothing in collisions.** All 11 survive. The one contact that fails the collision check (#10) is already a persona=None contact.

The task asks whether a ten-contact canary is still a canary. The actual number is **11**, not 10 (because there are 6 persona=None contacts, not 7). Eleven contacts with their own angle, all clean against the provider, is a viable canary. It is not two cohorts — it is one cohort of 11 with classified personas and assigned angles.

Whether to include the 5 surviving persona=None contacts is a separate question. They add 5 more contacts with generic finance copy. They do not collide with provider history. But they do not test the persona-matching path — they test the fallback path.

## 5. Final Recommended Cohort

### Contacts that MUST be excluded

| # | rec_id_hash | reason |
|---|-------------|--------|
| 10 | 8953a27075c2 | 21 prior emails at the provider across 3 campaigns. The specific contact was emailed. This is the collision the check exists to catch. |

### Contacts with domain-level history (operator decision required)

Three contacts are clean at the person level but their domain has prior email history at the provider. The contact themselves was not emailed, but another person at the same domain was.

| # | rec_id_hash | domain_hash | domain-level history | person-level status |
|---|-------------|-------------|---------------------|---------------------|
| 1 | b580268f93f2 | da9fa0575ce8 | 13 emails to another lead | 0 emails to this contact (sending_paused) |
| 5 | 9d2802e5f931 | 63084828d69e | 42 emails to another lead | not in provider leads |
| 14 | 024ba413ded7 | a3a16ee58d26 | 5 emails to another lead | not in provider leads |

TASK-170's check 7 flagged domain `<domain:da9fa0575ce8>` at the domain level. Claude has already decided to remove contact #1 on that basis. If the same standard is applied consistently, contacts #5 and #14 should also be removed.

`account_policy` in `src/collision.py` would classify all three as ALLOW: emails were sent at the domain in finished campaigns with no reply — "history, not a live conflict." But check 7 in the pre-write script is stricter: it fails if ANY email was sent at the domain.

**This is an operator decision, not an engineering one.** The task says "do not propose loosening a gate." The gate (check 7) flags domain-level history. Whether to exclude on that basis is Claude's call.

### The recommended cohort (contact-level clean only)

If the standard is "the specific contact has zero prior provider contact":

**16 contacts survive.** Per contact, the gates passed and the reason for inclusion:

| # | rec_id_hash | persona | angle | gates passed | reason |
|---|-------------|---------|-------|--------------|--------|
| 1 | b580268f93f2 | economic_buyer | founder | collision PASS, lint PASS, claims PASS | 0 prior emails to this contact. Domain has history (13 emails to another lead). |
| 2 | 90dc872ce83e | economic_buyer | founder | collision PASS, lint PASS, claims PASS | 0 prior emails, sending_paused at provider. |
| 3 | ff930f49050f | economic_buyer | founder | collision PASS, lint PASS, claims PASS | 0 prior emails, sending_paused at provider. |
| 4 | d881cb9457f6 | economic_buyer | operations | collision PASS, lint PASS, claims PASS | 0 prior emails, sending_paused at provider. |
| 5 | 9d2802e5f931 | economic_buyer | founder | collision PASS, lint PASS, claims PASS | Not in provider leads. Domain has history (42 emails to another lead). |
| 6 | 4b37ea891b56 | None | None | collision PASS, lint PASS, claims PASS | Not in provider leads. persona=None, receives finance fallback. |
| 7 | d00a60562edd | economic_buyer | founder | collision PASS, lint PASS, claims PASS | 0 prior emails, sending_paused at provider. |
| 8 | 73636ff041b0 | economic_buyer | founder | collision PASS, lint PASS, claims PASS | 0 prior emails, sending_paused at provider. |
| 9 | 646934233472 | economic_buyer | founder | collision PASS, lint PASS, claims PASS | 0 prior emails, sending_paused at provider. |
| 11 | a02d0a715cb8 | economic_buyer | founder | collision PASS, lint PASS, claims PASS | 0 prior emails, sending_paused at provider. |
| 12 | aa86bcae3d3f | None | None | collision PASS, lint PASS, claims PASS | Not in provider leads. persona=None, receives finance fallback. |
| 13 | b15936a38d71 | economic_buyer | founder | collision PASS, lint PASS, claims PASS | 0 prior emails, sending_paused at provider. |
| 14 | 024ba413ded7 | None | None | collision PASS, lint PASS, claims PASS | Not in provider leads. Domain has history (5 emails to another lead). persona=None, receives finance fallback. |
| 15 | 9888d6a9d54d | None | None | collision PASS, lint PASS, claims PASS | Not in provider leads. persona=None, receives finance fallback. |
| 16 | 73dff24eb5e8 | economic_buyer | founder | collision PASS, lint PASS, claims PASS | Not in provider leads. |
| 17 | 83cc7c8ac60b | None | None | collision PASS, lint PASS, claims PASS | Not in provider leads. persona=None, receives finance fallback. |

### If domain-level history is also exclusionary

If the standard is "neither the contact nor the domain has prior provider contact":

**13 contacts survive.** Contacts #1, #5, and #14 are removed in addition to #10.

| # | rec_id_hash | persona | angle | gates passed | reason |
|---|-------------|---------|-------|--------------|--------|
| 2 | 90dc872ce83e | economic_buyer | founder | collision PASS (domain clean), lint PASS, claims PASS | 0 prior emails, sending_paused. Domain has no other leads. |
| 3 | ff930f49050f | economic_buyer | founder | collision PASS (domain clean), lint PASS, claims PASS | 0 prior emails, sending_paused. Domain has no other leads. |
| 4 | d881cb9457f6 | economic_buyer | operations | collision PASS (domain clean), lint PASS, claims PASS | 0 prior emails, sending_paused. Domain has no other leads. |
| 6 | 4b37ea891b56 | None | None | collision PASS (domain clean), lint PASS, claims PASS | Not in provider leads. Domain has no other leads. persona=None. |
| 7 | d00a60562edd | economic_buyer | founder | collision PASS (domain clean), lint PASS, claims PASS | 0 prior emails, sending_paused. Domain has no other leads. |
| 8 | 73636ff041b0 | economic_buyer | founder | collision PASS (domain clean), lint PASS, claims PASS | 0 prior emails, sending_paused. Domain has no other leads. |
| 9 | 646934233472 | economic_buyer | founder | collision PASS (domain clean), lint PASS, claims PASS | 0 prior emails, sending_paused. Domain has no other leads. |
| 11 | a02d0a715cb8 | economic_buyer | founder | collision PASS (domain clean), lint PASS, claims PASS | 0 prior emails, sending_paused. Domain has no other leads. |
| 12 | aa86bcae3d3f | None | None | collision PASS (domain clean), lint PASS, claims PASS | Not in provider leads. Domain has no leads at all. persona=None. |
| 13 | b15936a38d71 | economic_buyer | founder | collision PASS (domain clean), lint PASS, claims PASS | 0 prior emails, sending_paused. Domain has no other leads. |
| 15 | 9888d6a9d54d | None | None | collision PASS (domain clean), lint PASS, claims PASS | Not in provider leads. Domain has no leads at all. persona=None. |
| 16 | 73dff24eb5e8 | economic_buyer | founder | collision PASS (domain clean), lint PASS, claims PASS | Not in provider leads. Domain has no leads at all. |
| 17 | 83cc7c8ac60b | None | None | collision PASS (domain clean), lint PASS, claims PASS | Not in provider leads. Domain has no leads at all. persona=None. |

### Is the cohort too small?

The task warns: "a canary that shrinks toward zero stops being able to tell us anything."

- **16 contacts** (person-level clean): not too small. This is a viable canary.
- **13 contacts** (person + domain clean): not too small. Still viable.
- **11 contacts** (persona-only): not too small. All have their own angle.

None of these are approaching zero. The honest recommendation is **not to widen intake to pad the numbers** — the contacts that were removed were removed for good reasons. But if a larger canary is needed, the path is to classify more contacts (giving them personas and angles), not to loosen the collision check.

## 6. What Changed From TASK-170

TASK-170's check 7 ran against campaign 481's existing 23 leads and flagged one domain. This task ran the same check against the 17-contact cohort's 17 domains and found:

- **1 contact** with direct prior provider contact (21 emails to the specific person)
- **3 contacts** with domain-level history only (other people at the same domain were emailed)
- **9 contacts** present as leads at the provider with 0 emails sent (sending_paused)
- **4 contacts** not present in the provider's leads at all

The nine `sending_paused` contacts are in the provider's estate but were never emailed. They are not a collision. They are a fact: the provider knows about them. Whether that matters for a canary is an operator decision.

## 7. Script Notes

`scripts/task177_collision_per_contact.py` was written for this task. It:
- Reads the snapshot (not the live queue)
- Calls `collision.leads_for_domain()` per unique domain (17 calls)
- Checks each contact's email against the returned leads
- Hashes all PII before printing or writing
- Makes no provider writes

No changes were made to `scripts/bison_prewrite_check.py`. Its 32 tests are unaffected.
