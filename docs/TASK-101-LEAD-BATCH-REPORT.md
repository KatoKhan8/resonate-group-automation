# TASK-101 - Lead Batch Report

**Snapshot:** `2026-09-14T21:52:15Z  from master 0ac5e60  300 records`
**Cohort:** persona == 'economic_buyer' (largest honest cohort from TASK-096)
**Date:** 2026-09-15

---

## Funnel

| Stage | Count | Drop |
|-------|------:|-----:|
| cohort_selection | 70 | 0 |
| dedupe | 70 | 0 |
| exclusion | 51 | 19 |
| personalisation | 51 | 0 |
| greeting_proof | 51 | 0 |
| quality_gates | 51 | 0 |

## Drop-off Analysis

**Total dropped:** 19 of 70 (27.1%)
**Surviving:** 51 of 70 (72.9%)

### Drop Reasons by Stage

#### exclusion

- **unverified_no_reoon_clearance; verification_state:unknown**: 12
  - record `e46dd5323aa3`, contact `d814b9bcb642`
  - record `d2d11b5b2a87`, contact `fdcb8374317f`
  - record `d5541a7c0d51`, contact `9eb34c7a9f76`
  - record `8c92231b7a8a`, contact `e698a9d8c7cc`
  - record `baf35e64c0dd`, contact `5f52bf0effcb`
  - record `f1f2d9d151cc`, contact `ee3b23b4bf72`
  - record `7ef6212caf77`, contact `6e6eea7c0d4f`
  - record `5c2a3cfd7eec`, contact `89979c124227`
  - record `6782ab63df5d`, contact `072870173b9c`
  - record `a2e8942303e3`, contact `dea8eb1dade4`
  - record `9bffb9cef5a1`, contact `553baa005cf7`
  - record `49447c5db61f`, contact `dc399c3f791f`
- **email_accept_all_and_reoon_unsafe**: 6
  - record `c1c4b4de39d3`, contact `b8cf25c80e28`
  - record `7fa82eea81a9`, contact `26e8cead828c`
  - record `9536bb3a8cd7`, contact `faec57347912`
  - record `7e55d09386a9`, contact `51384e8ed9ec`
  - record `a416462fb1d2`, contact `05eba4a5a8f0`
  - record `cc590e15b3fc`, contact `aac0f54a36b2`
- **not_sendable**: 1
  - record `49ce56e95739`, contact `e95774cfe317`

---

## What the Operator Would Be Authorising

If the operator enables `heyreach.add_leads` (NOT in `providerwrites.SUPPORTED`),
they would be authorising:

- **51 leads** added to a HeyReach campaign
- Each lead carries: profileUrl, firstName, lastName, companyName, position
- Plus customUserFields: note, record_id, contact_key
- The campaign's sequence would then act on each lead immediately
- This is **prospect-facing** and irreversible at the provider

### What is NOT authorised by this report

- No campaign creation (no documented HeyReach route)
- No sequence configuration (separate operator decision)
- No sender assignment (separate operator decision)
- No activation or unpausing

---

## Batch File

The batch is at `work/task101_batch.json` (51 rows).
This file is under `work/` which is gitignored. It contains real data
as an operational artefact. The report above hashes all identifiers.

---

## Observations

- **Angle coverage in surviving batch:** {'founder': 34, 'economic_buyer': 1, 'operations': 13, '(none)': 3}
- **No fallback fields needed** - all merge variables resolved
- **Company diversity:** 51 unique domains across 51 leads

## Hypotheses

- The 19 not-sendable contacts are split between unverified (no reoon check)
  and accept_all domains where reoon says unsafe. A targeted re-verification
  pass could recover some of these.

## Proven Learnings

(empty - this is a preparation task, not an outcome measurement)