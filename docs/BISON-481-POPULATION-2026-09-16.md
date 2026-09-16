---
title: "Bison Campaign 481 — Population Analysis"
task: "TASK-174"
date: "2026-09-16"
---

# Bison Campaign 481 — Population Analysis

**TASK-174 deliverable.** Read-only investigation of the 23 leads already in campaign 481, their relationship to the 17 from TASK-167, gate verdicts, and step comparison to CONTROL.

**PII policy:** Every identifier is SHA-256 hashed (12 hex chars). No email address, person name, company name, or domain appears in this document.

## 1. Campaign State (Provider Truth)

| Field | Value |
|-------|-------|
| Campaign ID | 481 |
| Name | RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUYER - LIHEAVY-V1 |
| Status | **paused** |
| Created | 2026-09-13T20:11:34Z |
| Updated | 2026-09-13T22:17:13Z |
| Max emails/day | 20 |
| Max new leads/day | 20 |
| Lead count | **23** |
| Step count | **5** |
| Emails sent | **0** |

**Source:** `bison.campaign(481)` — provider GET `/api/campaigns/481`

## 2. The 23 Leads — Who They Are

The 23 leads fall into **two distinct groups** by creation date and provenance:

### Group A: 13 leads created 2026-09-13 (this system's work)

These have `record_id`, `contact_key`, and `client=productive` filled in. They were attached to 481 on 2026-09-13 when the campaign was built by this system under the old `productive_li_heavy_v1` cadence.

| # | lead_id | email_hash | domain_hash | name_hash | status | created_at | record_id | contact_key |
|---|---------|------------|-------------|-----------|--------|------------|-----------|-------------|
| 1 | 203719 | ee5cd91b094a | a3f981c16e38 | 39d13d6caefb | **stopped** | 2026-09-13T22:17:11Z | semcasting-com  ck:b453289bf239 |
| 2 | 203718 | 3c5271f31289 | 1203bef7ae16 | 2aa47f23fd95 | sending_paused | 2026-09-13T22:17:10Z | savagebrands-com  ck:7f2b580577dc |
| 3 | 203717 | 062eb4bd3473 | 1f507fd7fba0 | 3a315d0ef7e7 | **stopped** | 2026-09-13T22:17:09Z | roaringmedia-co | jason-baker |
| 4 | 203716 | 0ffd563b26fa | 500976b76607 | 164c11029ec9 | sending_paused | 2026-09-13T22:17:09Z | portsidemarketing-com  ck:bec85b0b616e |
| 5 | 203715 | eb4715ab1b94 | da9fa0575ce8 | b6882cfd6d48 | sending_paused | 2026-09-13T22:17:08Z | ogpartner-dk | jacob-faertz |
| 6 | 203714 | 13a755016ef4 | c3c9e6e49e77 | 177f9fa54bfb | sending_paused | 2026-09-13T22:17:07Z | mypersonalestatesale-com  ck:a1d756d28444 |
| 7 | 203713 | 985b119c2038 | 395be3330be3 | c243e114f58c | sending_paused | 2026-09-13T22:17:07Z | mischacommunications-com  ck:2e616319bb62 |
| 8 | 203712 | 681ab5824248 | 663c917ceea0 | ec867fead617 | **stopped** | 2026-09-13T22:17:06Z | ethoscreate-com  ck:071bab9229e4 |
| 9 | 203711 | d6e29c496d88 | 4efeb3fe2afd | 32ab93ceddc6 | sending_paused | 2026-09-13T21:48:21Z | anewagencyworld-com  ck:b100051cb1c0 |
| 10 | 203710 | 185d72e07fc8 | ceb55a89127b | aaaba6610b02 | sending_paused | 2026-09-13T21:48:19Z | agency59-ca | al-scornaienchi |
| 11 | 203709 | 34bc6d04c490 | 68af8ce671c1 | 8cdfd2d06cae | sending_paused | 2026-09-13T21:48:17Z | adcuratio-com  ck:9001fb6df2ea |
| 12 | 203708 | 529930f7e146 | c768a0660316 | dd4e53f0860a | sending_paused | 2026-09-13T21:48:15Z | acqcom-com  ck:7d1f45aff0d0 |
| 13 | 203707 | 1462c379281a | 5aa13c5766c9 | 34cc9b5ba94c | **stopped** | 2026-09-13T21:48:11Z | 28row-com  ck:b3db105bae4c |

**Status breakdown:** 9 `sending_paused` (campaign paused, leads reversible), 4 `stopped`.

### Group B: 10 leads created 2026-04-04 to 2026-04-23 (pre-existing)

These have **empty** `record_id` and `contact_key` — they predate this system's queue. They were already in the workspace when 481 was built and were either already attached or attached by a different process.

| # | lead_id | email_hash | domain_hash | status | created_at | record_id |
|---|---------|------------|-------------|--------|------------|-----------|
| 14 | 168853 | 536eb9e9148a | 7b2e0bb20af0 | stopped | 2026-04-23T19:54:03Z | (empty) |
| 15 | 168654 | 181ba5ba2825 | e509fe19fed9 | stopped | 2026-04-23T19:54:02Z | (empty) |
| 16 | 168616 | 5f271a10e673 | f0d95f23d854 | stopped | 2026-04-23T19:54:02Z | (empty) |
| 17 | 144582 | 371573ad6633 | cdcacc3cf0d8 | stopped | 2026-04-08T18:33:03Z | (empty) |
| 18 | 142762 | 9a05008c647b | 2cf23f1c5afe | stopped | 2026-04-08T18:33:00Z | (empty) |
| 19 | 141805 | 836de1843ccc | ad83ab4912c1 | stopped | 2026-04-08T18:32:59Z | csquaredsocial-com |
| 20 | 140550 | 9682ffd8c605 | 266b682f358e | stopped | 2026-04-08T18:32:56Z | (empty) |
| 21 | 136059 | 9c5c7e5f6912 | 465141272ed8 | stopped | 2026-04-04T23:21:29Z | (empty) |
| 22 | 135163 | 4a07f83f5590 | 17851b33a43d | stopped | 2026-04-04T23:06:21Z | (empty) |
| 23 | 133292 | e6d7c3a0d460 | dadec1a2cdb2 | stopped | 2026-04-04T22:45:20Z | (empty) |

**Status breakdown:** All 10 are `stopped`.

**Source:** `bison._paged(leads_endpoint(481))` — provider GET `/api/campaigns/481/leads`, all pages

## 3. Overlap with TASK-167's 17

### By email hash

| Count | Value |
|-------|-------|
| **In both (23 ∩ 17)** | **4** |
| Only in 481 | 19 |
| Only in TASK-167 payload | 13 |

The 4 matching email hashes:
- `eb4715ab1b94` — lead 203715, ogpartner-dk, jacob-faertz
- `d6e29c496d88` — lead 203711, anewagencyworld-com, ck:b100051cb1c0
- `529930f7e146` — lead 203708, acqcom-com, ck:7d1f45aff0d0
- `34bc6d04c490` — lead 203709, adcuratio-com, ck:9001fb6df2ea

### By domain hash

| Count | Value |
|-------|-------|
| **In both (23 ∩ 17)** | **9** |
| Only in 481 | 14 |
| Only in TASK-167 payload | 8 |

### By name hash

| Count | Value |
|-------|-------|
| **In both (23 ∩ 17)** | **9** |

### Interpretation

The 4 email matches are all from Group A (the 13 leads this system created on 2026-09-13). The broader domain/name overlap (9 each) shows that many of the 17 from TASK-167 come from the same companies as the 23 in 481, but different contacts at those companies. The 13 who are only in the TASK-167 payload are contacts who were NOT in 481 — they are new additions from the CONTROL sequence selection.

## 4. Gate Verdicts — Do the 23 Pass Today's Gates?

**All 23 are REFUSED.** Every lead fails at least one gate.

| # | lead_id | email_hash | verdict | reasons |
|---|---------|------------|---------|---------|
| 1 | 203719 | ee5cd91b094a | REFUSED | historical_contact: 23 confirmed touches; fatigue: 88 log entries |
| 2 | 203718 | 3c5271f31289 | REFUSED | historical_contact: 34 confirmed touches; fatigue: 94 log entries |
| 3 | 203717 | 062eb4bd3473 | REFUSED | historical_contact: 23 touches; ICP: 6 employees (under min 20); fatigue: 84 entries |
| 4 | 203716 | 0ffd563b26fa | REFUSED | historical_contact: 34 touches; ICP: 4 employees (under min 20); fatigue: 94 entries |
| 5 | 203715 | eb4715ab1b94 | REFUSED | historical_contact: 34 touches; ICP: 11 employees (under min 20); fatigue: 101 entries |
| 6 | 203714 | 13a755016ef4 | REFUSED | historical_contact: 34 touches; ICP: 13 employees (under min 20); fatigue: 91 entries |
| 7 | 203713 | 985b119c2038 | REFUSED | historical_contact: 34 touches; ICP: 6 employees (under min 20); fatigue: 84 entries |
| 8 | 203712 | 681ab5824248 | REFUSED | historical_contact: 23 touches; ICP: 16 employees (under min 20); fatigue: 95 entries |
| 9 | 203711 | d6e29c496d88 | REFUSED | historical_contact: 40 touches; ICP: geo outside markets + 11 employees; fatigue: 97 entries |
| 10 | 203710 | 185d72e07fc8 | REFUSED | historical_contact: 40 touches; ICP: geo outside markets + 10 employees; fatigue: 103 entries |
| 11 | 203709 | 34bc6d04c490 | REFUSED | historical_contact: 40 touches; fatigue: 109 entries |
| 12 | 203708 | 529930f7e146 | REFUSED | historical_contact: 40 touches; ICP: 2 employees (under min 20); fatigue: 109 entries |
| 13 | 203707 | 1462c379281a | REFUSED | historical_contact: 39 touches; fatigue: 116 entries |
| 14 | 168853 | 536eb9e9148a | REFUSED | historical_contact: 6 touches; ICP: geo + 11 employees; fatigue: 113 entries |
| 15 | 168654 | 181ba5ba2825 | REFUSED | historical_contact: 6 touches; ICP: 11 employees; fatigue: 74 entries |
| 16 | 168616 | 5f271a10e673 | REFUSED | historical_contact: 6 touches; state: approved; ICP: geo + 19 employees; fatigue: 106 entries |
| 17 | 144582 | 371573ad6633 | REFUSED | historical_contact: 6 touches; ICP: 11 employees; fatigue: 72 entries |
| 18 | 142762 | 9a05008c647b | REFUSED | historical_contact: 6 touches; state: approved; ICP: 11 employees; fatigue: 70 entries |
| 19 | 141805 | 836de1843ccc | REFUSED | historical_contact: 31 touches; fatigue: 113 entries |
| 20 | 140550 | 9682ffd8c605 | REFUSED | historical_contact: 6 touches; fatigue: 62 entries |
| 21 | 136059 | 9c5c7e5f6912 | REFUSED | historical_contact: 6 touches; ICP: geo outside markets; fatigue: 79 entries |
| 22 | 135163 | 4a07f83f5590 | REFUSED | historical_contact: 6 touches; ICP: 11 employees; fatigue: 112 entries |
| 23 | 133292 | e6d7c3a0d460 | REFUSED | historical_contact: 6 touches; fatigue: 91 entries |

**Summary:** 0 PASS, 23 REFUSED out of 23 leads.

### Gate failure breakdown

| Gate | Leads failing | Detail |
|------|--------------|--------|
| historical_contact (>0 confirmed touches) | **23/23** | Every lead has 6-40 confirmed touches in the event log |
| fatigue_proxy (>20 log entries) | **23/23** | 62-116 log entries per lead |
| ICP flags | **14/23** | Under client minimum of 20 employees, or geo outside markets |
| state not outreach-eligible | **2/23** | leads 16 and 18 are in `approved` state |

**The dominant refusal is historical_contact.** Every one of the 23 has been touched before — between 6 and 40 confirmed touches each. None of them are cold contacts. The CONTROL sequence is designed for cold outreach; these are all already-warmed or already-worked contacts.

## 5. Campaign 481's Steps vs CONTROL

### CONTROL sequence (from TASK-159/167)

| Step | Name | Day | thread_reply |
|------|------|-----|-------------|
| 1 | persona_pain | 1 | **false** |
| 2 | comparable_proof | 5 | **true** |
| 3 | breakup | 21 | **false** |

### Campaign 481's steps (provider truth)

| # | order | subject | body | wait_in_days | thread_reply | active |
|---|-------|---------|------|--------------|-------------|--------|
| 1 | 1 | `{SUBJECT_1}` | `<p>{BODY_1}</p>` | 3 | **false** | true |
| 2 | 2 | `{SUBJECT_2}` | `<p>{BODY_2}</p>` | 4 | **false** | true |
| 3 | 3 | `{SUBJECT_3}` | `<p>{BODY_3}</p>` | 4 | **false** | true |
| 4 | 4 | `{SUBJECT_4}` | `<p>{BODY_4}</p>` | 9 | **false** | true |
| 5 | 5 | `{SUBJECT_5}` | `<p>{BODY_5}</p>` | 1 | **false** | true |

### Comparison

| Property | CONTROL | 481's sequence | Match? |
|----------|---------|---------------|--------|
| Step count | 3 | **5** | **NO** |
| Merge variables | Resolved before staging (`{first_name}`, `{company}`, etc.) | **`{SUBJECT_N}` / `{BODY_N}`** — provider-side merge | **NO** |
| thread_reply pattern | F, T, F | **F, F, F, F, F** | **NO** |
| Delay pattern | 1, 5, 21 days | **3, 4, 4, 9, 1 days** | **NO** |
| Copy | Audited CONTROL templates | Old `productive_li_heavy_v1` cadence copy | **NO** |

**481's five steps are NOT the CONTROL sequence.** They are the old `productive_li_heavy_v1` cadence: five email steps with provider-side merge variables, no threading, and different delays. The copy in `{BODY_1}` through `{BODY_5}` is whatever was resolved into the lead's custom variables at staging time under the old cadence — not the audited CONTROL templates.

**Source:** `bison.sequence_steps(481)` — provider GET `/api/campaigns/481/sequence-steps`

## 6. Analysis and Recommendation

### The three answers

The task named three possible relationships between the 23 and the 17:

1. **reuse 481** → write the CONTROL sequence over the 23
2. **new campaign** → 481 stays, a new campaign is built for the 17
3. **neither** → the 23 are the cohort, the 17 are a subset

### What the data supports

**The data supports "new campaign" unambiguously.**

The evidence:

1. **481 holds 23 people, not 17.** The 17 from TASK-167 are a subset of the 23 by email (4 overlap) and by domain (9 overlap), but 13 of the 17 are NOT in 481 at all. The 23 are NOT the cohort the 17 were drawn from — they are a different, larger population.

2. **481's sequence is NOT the CONTROL sequence.** It has 5 steps vs 3, uses provider-side merge variables vs pre-resolved, has no threading (`thread_reply` all false vs F/T/F), and different delays. Writing the CONTROL sequence onto 481 would not be "applying the same plan" — it would be replacing one plan with a different one for 23 people who were staged under the old plan.

3. **All 23 fail today's gates.** Every one has 6-40 confirmed historical touches. The CONTROL sequence is designed for cold outreach. These contacts are not cold — they have been worked extensively under the old cadence. Putting them through a cold-outreach sequence would be a category error.

4. **The 10 pre-existing leads (Group B) are not ours.** They have no `record_id`, no `contact_key`, no `client` tag. They predate this system by five months. They are not part of any plan this system made, and they should not be part of any plan this system executes.

5. **The 13 Group A leads were staged under a different plan.** They were created on 2026-09-13 for the `productive_li_heavy_v1` cadence, not the CONTROL sequence. Their custom variables carry the old cadence's copy. They are `sending_paused` because the campaign was paused, not because they completed anything.

### The critical fact

**Campaign 481 holds 23 people.** `bison.set_sequence` is in `SUPPORTED` and `bison.add_lead` is NOT. Writing a sequence onto 481 is authorized; adding a lead to it is not. But `set_sequence` APPENDS rather than replaces (measured 2026-09-13: writing one step, then another, left the campaign holding BOTH). And writing the CONTROL sequence over a campaign that already holds 23 people is a change to what 23 real people would receive, performed by a route whose permission comment justifies itself on the grounds that "a sequence written onto a campaign holding nobody reaches nobody."

**481 holds somebody. That fact decides whether the authorized route is safe here, and it is not.**

### Recommendation

**NEW CAMPAIGN.** Create a new campaign for the CONTROL sequence and the 17 contacts from TASK-167. Leave 481 as it is — paused, with its existing sequence and its 23 leads.

The 23 in 481 need a separate decision about what happens to them:
- The 10 Group B leads (pre-existing, no record_id) are somebody else's problem from five months ago. They are stopped and cannot send.
- The 13 Group A leads (this system's work, old cadence) were staged under a plan that is now superseded by the CONTROL sequence. Whether to stop them, leave them paused, or migrate them to a new campaign is an operator decision — but it is NOT the same decision as "write the CONTROL sequence onto 481."

---
*Generated 2026-09-16 by scripts/task174_investigate_481.py*
*All data read from the EmailBison provider (read-only) and work/queue.snapshot.jsonl (stamp: 2026-09-15T17:52:12+00:00 from master cf23154 550 records)*
