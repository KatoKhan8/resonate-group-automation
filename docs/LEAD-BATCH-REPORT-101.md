# Lead Batch Report - TASK-101

**Snapshot:** `2026-09-14T21:52:15Z  from master 0ac5e60  300 records`
**Total records in estate:** 300
**Cohort:** economic_buyer (persona == 'economic_buyer' AND email IS NOT NULL)
**Batch file:** `work/batch-TASK-101.jsonl` (gitignored)

---

## Funnel

| Stage | Count | Drop |
|-------|------:|-----:|
| cohort_selected | 70 | - |
| after_dedupe | 70 | - |
| after_exclusion | 51 | -19 |
| after_personalisation | 51 | - |
| after_greeting_proof | 51 | - |
| after_quality_gates | 26 | -25 |

**Final batch size:** 26 leads

**Total dropped:** 44 of 70 (62.9%)

---

## Stage 1: Dedupe

**Dropped:** 0 - no cross-record duplicates found in the cohort.

---

## Stage 2: Exclusion Check

**Dropped:** 19

**Breakdown by reason:**

- email not verified (unknown): 12
- email not verified (accept_all_uncleared): 6
- email not verified (held): 1

| Record ID (hashed) | Contact Key (hashed) | Reason |
|---|---|---|
| e46dd5323aa3 | d814b9bcb642 | email not verified (state: unknown); contact not sendable; MX excluded: mx_protection:proofpoint |
| c1c4b4de39d3 | b8cf25c80e28 | email not verified (state: accept_all_uncleared); contact not sendable; email unsafe to send (reoon) |
| d2d11b5b2a87 | fdcb8374317f | email not verified (state: unknown); contact not sendable |
| 7fa82eea81a9 | 26e8cead828c | email not verified (state: accept_all_uncleared); contact not sendable; email unsafe to send (reoon) |
| d5541a7c0d51 | 9eb34c7a9f76 | email not verified (state: unknown); contact not sendable |
| 9536bb3a8cd7 | faec57347912 | email not verified (state: accept_all_uncleared); contact not sendable; email unsafe to send (reoon) |
| 8c92231b7a8a | e698a9d8c7cc | email not verified (state: unknown); contact not sendable |
| baf35e64c0dd | 5f52bf0effcb | email not verified (state: unknown); contact not sendable |
| f1f2d9d151cc | ee3b23b4bf72 | email not verified (state: unknown); contact not sendable |
| 7ef6212caf77 | 6e6eea7c0d4f | email not verified (state: unknown); contact not sendable |
| 7e55d09386a9 | 51384e8ed9ec | email not verified (state: accept_all_uncleared); contact not sendable; email unsafe to send (reoon) |
| 49ce56e95739 | e95774cfe317 | email not verified (state: held); contact not sendable; email unsafe to send (reoon) |
| a416462fb1d2 | 05eba4a5a8f0 | email not verified (state: accept_all_uncleared); contact not sendable; email unsafe to send (reoon) |
| 5c2a3cfd7eec | 89979c124227 | email not verified (state: unknown); contact not sendable |
| 6782ab63df5d | 072870173b9c | email not verified (state: unknown); contact not sendable |
| a2e8942303e3 | dea8eb1dade4 | email not verified (state: unknown); contact not sendable |
| 9bffb9cef5a1 | 553baa005cf7 | email not verified (state: unknown); contact not sendable |
| 49447c5db61f | dc399c3f791f | email not verified (state: unknown); contact not sendable |
| cc590e15b3fc | aac0f54a36b2 | email not verified (state: accept_all_uncleared); contact not sendable; email unsafe to send (reoon) |

---

## Stage 3: Personalisation

**Dropped:** 0 - all merge variables resolved for every lead.

---

## Stage 4: Greeting Proof

**Dropped:** 0 - all greetings render correctly.

Sample greetings (first 5, hashed):

- b580268f93f2 / c8b688f83273: greeting OK
- c42f6e944043 / 96950d6cff93: greeting OK
- e3cb63532ad5 / b3db105bae4c: greeting OK
- 13f19e079ea0 / ecfd847755c1: greeting OK
- 1efd9712c579 / 12ffbe29250e: greeting OK

---

## Stage 5: Quality Gates

**Leads needing copy generation:** 3

These leads passed all prior stages but have no generated cadence steps. They need copy generation before they can be included in a campaign.

| Record ID (hashed) | Contact Key (hashed) | Note |
|---|---|---|
| 4b0bc54de0a0 | 27f989bbd3cd | no generated cadence steps - needs copy generation |
| fe1f35998ca8 | 38af59a12220 | no generated cadence steps - needs copy generation |
| 84f5e945edbd | 948db9569b76 | no generated cadence steps - needs copy generation |

**Punctuation normalisation fixes:** 5

These leads had curly apostrophes or dashes that are fixed by `normalise_punctuation` (same preprocessing as production `lint.py`). They pass lint after normalisation.

**Dropped by quality gates:** 25

**Breakdown:**

- Banned phrase (primary): 23
- Unsupported claim (primary, no banned phrase): 2

| Record ID (hashed) | Contact Key (hashed) | Reason |
|---|---|---|
| 7408ea3640b8 | 7a59d5bd0a5c | step li5: banned phrase 'just checking in' |
| b0440fdce73b | 8c59221eed4b | step li5: banned phrase 'just checking in' |
| d49d802aed9f | 8cc5337f15d9 | step li5: banned phrase 'just checking in'; step em5: claims prior contact but none recorded |
| 6306b13a53c8 | c80bea930ec4 | step li5: banned phrase 'just checking in'; step em5: claims prior contact but none recorded |
| bdc49e5f95a3 | b2ca0edc8c66 | step li5: banned phrase 'just checking in' |
| e1255ffcfecf | e73149cb0f1a | step li5: banned phrase 'just checking in'; step em5: claims prior contact but none recorded |
| df55afeb266e | b75be85649a8 | step em5: claims prior contact but none recorded |
| 9d951805970f | 56021aeda339 | step em5: claims prior contact but none recorded |
| f9a91ff9420b | 4c7714c190e9 | step li5: banned phrase 'just checking in' |
| d881cb9457f6 | 9001fb6df2ea | step li5: banned phrase 'just checking in' |
| d00a60562edd | bec85b0b616e | step li5: banned phrase 'just checking in' |
| 720c8fc2abd3 | bc3a31fb868d | step li5: banned phrase 'just checking in' |
| c819ee7e35b4 | fd1da8a1d889 | step li5: banned phrase 'just checking in' |
| 0b979dc94800 | aa5762d7626a | step li5: banned phrase 'just checking in' |
| a02d0a715cb8 | 2e616319bb62 | step li5: banned phrase 'just checking in' |
| 908c05b93f4a | 932786f1390a | step li5: banned phrase 'just checking in' |
| b15936a38d71 | a1d756d28444 | step li5: banned phrase 'just checking in' |
| 23d0976b3c62 | 9f3c4b960dce | step li5: banned phrase 'just checking in' |
| 9ae06a22bcba | 6f5621435b58 | step li5: banned phrase 'just checking in' |
| 3d9ff6a09535 | aac9c7f4da93 | step li5: banned phrase 'just checking in' |
| 2c416dea559e | e1bfefed4a7e | step li5: banned phrase 'just checking in' |
| 3bd3f94a3bcd | 0db6382c871a | step li5: banned phrase 'just checking in' |
| 8588e6289d0b | e5e382f7b558 | step li5: banned phrase 'just checking in' |
| 1c71295e36e6 | 59332b9d097a | step li5: banned phrase 'just checking in' |
| 73dff24eb5e8 | 065ea0eefea9 | step li5: banned phrase 'just checking in' |

**Structural diversity:** No warnings.

---

## Final Batch Composition

### Industry distribution

- Advertising Services: 15
- Marketing & Advertising: 6
- Marketing Services: 4
- Business Consulting and Services: 1

### Angle distribution

- founder: 15
- operations: 7
- None: 3
- economic_buyer: 1

### Approval status

- approved: 16
- not_approved: 10

---

## What the Operator Would Be Authorising

If the operator enables `heyreach.add_leads` in `providerwrites.SUPPORTED`, they would be authorising:

- **26 leads** to be added to a HeyReach campaign
- All 26 leads are economic buyers with verified, sendable emails
- All leads have resolved personalisation (no undefined merge variables)
- All greetings render correctly (no 'Hi undefined,' or 'Hi null,')
- 23 leads have generated cadence copy that passes lint
- 3 leads need copy generation before they can receive outreach
- 25 leads were dropped by quality gates (banned phrases in existing generated copy)

**What is NOT authorised by this batch alone:**

- No campaign activation (that requires `heyreach.activate`, also not in SUPPORTED)
- No sequence assignment (requires `heyreach.set_sequence`, which IS in SUPPORTED)
- No sender assignment (no documented route)
- No sending of any kind to real prospects

**The decision is:** add 26 verified, personalised leads to a HeyReach campaign that cannot yet send. The sequence can be written (SUPPORTED), but activation remains blocked. This is the safe intermediate step: populate the campaign, verify the sequence renders correctly at the provider, THEN decide on activation.

**To recover the dropped leads:** their existing generated copy contains banned phrases (mostly 'just checking in' and 'i wanted to reach out'). Regenerating the copy for those leads through the normal generation pipeline would make them batch-eligible.

---

**Prepared by:** TASK-101
**Date:** 2026-09-15
**Snapshot:** `2026-09-14T21:52:15Z  from master 0ac5e60  300 records`