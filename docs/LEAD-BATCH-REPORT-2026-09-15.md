# Lead Batch Preparation Report

**Date:** 2026-09-15
**Snapshot:** `work/queue.snapshot.jsonl`
**Snapshot stamp:** 2026-09-14T21:52:15Z  from master 0ac5e60  300 records
**Cohort:** COHORT-001 (persona=economic_buyer)

---

## Funnel Summary

| Stage | Count | Drop Count | Drop-off |
|-------|------:|-----------:|---------:|
| Cohort members (with email) | 70 | 0 |  |
| After dedupe | 53 | 17 | 17 (24.3%) |
| After exclusion check | 36 | 17 | 17 (32.1%) |
| After personalisation | 33 | 3 | 3 (8.3%) |
| After greeting proof | 33 | 0 | 0 (0.0%) |
| After quality gates | 26 | 7 | 7 (21.2%) |

---

## Stage Details

### Stage 1: DEDUPE

**Dropped:** 17 leads already in campaigns

Sample drops (hashed):
  - record: `b580268f93f2`, contact: `c8b688f83273`
  - record: `e46dd5323aa3`, contact: `d814b9bcb642`
  - record: `e3cb63532ad5`, contact: `b3db105bae4c`
  - record: `c1c4b4de39d3`, contact: `b8cf25c80e28`
  - record: `90dc872ce83e`, contact: `b100051cb1c0`

### Stage 2: EXCLUSION CHECK

**Dropped:** 17 leads

Breakdown by reason:
  - not_sendable: 17
  - verification_not_sendable: 17
  - mx_not_eligible: 4

Sample drops (hashed):
  - record: `d2d11b5b2a87`, contact: `fdcb8374317f`, email: `58504dc133aa`
    Reasons: not_sendable, verification_not_sendable, mx_not_eligible
  - record: `7fa82eea81a9`, contact: `26e8cead828c`, email: `8101ba005650`
    Reasons: not_sendable, verification_not_sendable
  - record: `d5541a7c0d51`, contact: `9eb34c7a9f76`, email: `bebde1148089`
    Reasons: not_sendable, verification_not_sendable
  - record: `9536bb3a8cd7`, contact: `faec57347912`, email: `0f49d47e0696`
    Reasons: not_sendable, verification_not_sendable
  - record: `8c92231b7a8a`, contact: `e698a9d8c7cc`, email: `aed9d63cc783`
    Reasons: not_sendable, verification_not_sendable

### Stage 3: PERSONALISATION

**Dropped:** 3 leads with missing merge variables

Sample drops (hashed):
  - record: `4b0bc54de0a0`, contact: `27f989bbd3cd`
    Issues: missing_merge_vars:angle
  - record: `fe1f35998ca8`, contact: `38af59a12220`
    Issues: missing_merge_vars:angle
  - record: `84f5e945edbd`, contact: `948db9569b76`
    Issues: missing_merge_vars:angle

### Stage 4: GREETING PROOF

**Dropped:** 0 leads with greeting issues

Sample greetings (hashed):
  - 7a59d5bd0a5c: `Hi izabelle,`
  - 8c59221eed4b: `Hi claudia,`
  - 96950d6cff93: `Hi rachele,`
  - 8cc5337f15d9: `Hi agnieszka,`
  - ecfd847755c1: `Hi sam,`


### Stage 5: QUALITY GATES

**Dropped:** 7 leads with lint/claims issues

Sample drops (hashed):
  - record: `c42f6e944043`, contact: `96950d6cff93`
    Issues: claims_failed:em1
  - record: `d49d802aed9f`, contact: `8cc5337f15d9`
    Issues: claims_failed:em3, claims_failed:em5
  - record: `6306b13a53c8`, contact: `c80bea930ec4`
    Issues: claims_failed:em1, claims_failed:em2, claims_failed:em4, claims_failed:em5
  - record: `bdc49e5f95a3`, contact: `b2ca0edc8c66`
    Issues: claims_failed:em4
  - record: `e1255ffcfecf`, contact: `e73149cb0f1a`
    Issues: claims_failed:em2, claims_failed:em4, claims_failed:em5

---

## Final Batch

**Total leads:** 26
**Batch file:** `work/lead_batch_economic_buyer.json` (gitignored)

### Lead Summary (hashed)

| Contact | Record | Email | Company | Persona |
|---------|--------|-------|---------|---------|
| `7a59d5bd0a5c` | `7408ea3640b8` | `4a07f83f5590` | `a11803222925` | economic_buyer |
| `8c59221eed4b` | `b0440fdce73b` | `371573ad6633` | `027b4066cfa6` | economic_buyer |
| `ecfd847755c1` | `13f19e079ea0` | `df0bdf7c94c5` | `db32f98e24da` | economic_buyer |
| `12ffbe29250e` | `1efd9712c579` | `b6b9c7c7a550` | `678b322775ee` | economic_buyer |
| `887370cfb81e` | `abcb9b215ce2` | `536eb9e9148a` | `48dac5bf22a7` | economic_buyer |
| `4c7714c190e9` | `f9a91ff9420b` | `f77070512e5f` | `39e3e396bb04` | economic_buyer |
| `6df44dfabec1` | `4cf2ffc9cafa` | `5f271a10e673` | `f0d95f23d854` | economic_buyer |
| `b877c58af1ce` | `829974e38e7c` | `d78386013354` | `5a6078df375f` | economic_buyer |
| `07d8a93255b3` | `a50f329f37f1` | `5de53b4a8e2a` | `71adcb61885a` | economic_buyer |
| `7d22234d9236` | `9d2802e5f931` | `1e8b00e31c98` | `63084828d69e` | economic_buyer |
| ... | ... | ... | ... | ... |
| *16 more leads* | | | | |

---

## What the Operator Would Be Authorising

If the operator enables `heyreach.add_leads`, they would be authorising:

  - **26 leads** to be added to a HeyReach campaign
  - All leads are **persona=economic_buyer**
  - All leads have **verified email** (sendable=True)
  - All leads have **passed dedupe** (not in existing campaigns)
  - All leads have **passed exclusion checks** (no DNC, no bounce, no reply)
  - All leads have **resolved merge variables** (no undefined/null)
  - All leads have **valid greetings** (no 'Hi undefined,' or 'Hi ,')
  - All leads have **passed quality gates** (lint, claims)

**This is a reads-only preparation. No provider write has occurred.**

---

**Prepared by:** TASK-101
**Date:** 2026-09-15
