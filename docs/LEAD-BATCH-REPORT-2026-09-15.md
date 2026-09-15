# Lead Batch Report - economic_buyer cohort

**Date:** 2026-09-15
**Snapshot:** `work/queue.snapshot.jsonl` from master `0ac5e60` at 2026-09-14T21:52:15Z
**Cohort signal:** `persona == 'economic_buyer'`
**Batch file:** `work/lead-batch-economic-buyer.json` (gitignored, operational artefact)

---

## Funnel

| Stage | Count | Drop | Drop reason |
|-------|------:|-----:|-------------|
| Cohort (economic_buyer + email) | 70 | 0 |  |
| After dedupe | 53 | 17 | already_in_campaign: 17 |
| After exclusion | 36 | 17 | not_sendable:unknown: 7; not_sendable:accept_all_uncleared: 5; not_sendable:never_verified: 4; not_sendable:held: 1 |
| After personalisation | 30 | 6 | no_email_copy: 6 |
| After greeting proof | 30 | 0 |  |
| After quality gates | 23 | 7 | em5:claim('our previous discussions' asserts we have contacted this person before, and no confirmed touch says we have): 2; em1:claim('profitability' is asserted about them and nothing stored supports it): 1; em3:claim('profitability' is asserted about them and nothing stored supports it);em5:claim('our previous discussions' asserts we have contacted this person before, and no confirmed touch says we have): 1; em1:claim('utilization' is asserted about them and nothing stored supports it);em2:claim('utilisation' is asserted about them and nothing stored supports it);em4:claim('utilisation' is asserted about them and nothing stored supports it): 1; em4:claim('capacity' is asserted about them and nothing stored supports it): 1 |

**Final batch size: 23 leads**

---

## Stage Details

### 1. Deduplication

Records already claimed by an existing campaign are excluded. A prospect already in one of 11 campaigns must not enter another.

**17 contacts removed:**

- `b580268f93f2` / `c8b688f83273` - already_in_campaign
- `e46dd5323aa3` / `d814b9bcb642` - already_in_campaign
- `e3cb63532ad5` / `b3db105bae4c` - already_in_campaign
- `c1c4b4de39d3` / `b8cf25c80e28` - already_in_campaign
- `90dc872ce83e` / `b100051cb1c0` - already_in_campaign
- `ff930f49050f` / `7d1f45aff0d0` - already_in_campaign
- `d881cb9457f6` / `9001fb6df2ea` - already_in_campaign
- `06e296b9eb12` / `dd1146b816ab` - already_in_campaign
- `d00a60562edd` / `bec85b0b616e` - already_in_campaign
- `73636ff041b0` / `2da1e5722575` - already_in_campaign
- `720c8fc2abd3` / `bc3a31fb868d` - already_in_campaign
- `646934233472` / `7f2b580577dc` - already_in_campaign
- `a02d0a715cb8` / `2e616319bb62` - already_in_campaign
- `b15936a38d71` / `a1d756d28444` - already_in_campaign
- `361967c27122` / `071bab9229e4` - already_in_campaign
- `2c416dea559e` / `e1bfefed4a7e` - already_in_campaign
- `1facb2457f55` / `b453289bf239` - already_in_campaign

### 2. Exclusion Check

Suppression list, sendable status, MX security provider, Reoon safety.

**Suppression list:** `config/suppress.txt` contains only reserved-TLD examples. No local suppression file exists. No agency DNC file found.

**17 contacts removed:**

| Reason | Count |
|--------|------:|
| not_sendable:unknown | 7 |
| not_sendable:accept_all_uncleared | 5 |
| not_sendable:never_verified | 4 |
| not_sendable:held | 1 |

Hashed identifiers of excluded contacts:

- `fdcb8374317f` - not_sendable:never_verified
- `26e8cead828c` - not_sendable:accept_all_uncleared
- `9eb34c7a9f76` - not_sendable:unknown
- `faec57347912` - not_sendable:accept_all_uncleared
- `e698a9d8c7cc` - not_sendable:unknown
- `5f52bf0effcb` - not_sendable:unknown
- `ee3b23b4bf72` - not_sendable:never_verified
- `6e6eea7c0d4f` - not_sendable:never_verified
- `51384e8ed9ec` - not_sendable:accept_all_uncleared
- `e95774cfe317` - not_sendable:held
- `05eba4a5a8f0` - not_sendable:accept_all_uncleared
- `89979c124227` - not_sendable:unknown
- `072870173b9c` - not_sendable:unknown
- `dea8eb1dade4` - not_sendable:never_verified
- `553baa005cf7` - not_sendable:unknown
- `dc399c3f791f` - not_sendable:unknown
- `aac0f54a36b2` - not_sendable:accept_all_uncleared

### 3. Personalisation

Every email step's copy is checked for unresolved merge variables (`{VAR}` patterns), broken greetings, and missing company names.

**6 contacts removed:**

- `ecfd847755c1` - no_email_copy
- `27f989bbd3cd` - no_email_copy
- `38af59a12220` - no_email_copy
- `f31e32e0655e` - no_email_copy
- `aac9c7f4da93` - no_email_copy
- `948db9569b76` - no_email_copy

### 4. Greeting Proof

The first line of each lead's em1 body is rendered and checked for 'undefined', 'null', 'None', cohort names where a person belongs, and empty salutations.

No contacts removed at this stage.

**Opening line proof summary (30 leads):**

- All opening lines reference a resolved company: **yes**
- Opening line length: 88..501 chars
- No opening line contains 'undefined', 'null', 'None', or template variables
- No body contains the cohort name 'economic_buyer'

Sample (structural properties only, no PII):

| Hash | Opening length | Has company | Company hash |
|------|---------------:|-------------|--------------|
| `7a59d5bd0a5c` | 88 | yes | `a11803222925` |
| `8c59221eed4b` | 211 | yes | `027b4066cfa6` |
| `96950d6cff93` | 298 | yes | `0fb43b621019` |
| `8cc5337f15d9` | 237 | yes | `ce440adcc1dc` |
| `12ffbe29250e` | 281 | yes | `678b322775ee` |
| `c80bea930ec4` | 219 | yes | `465141272ed8` |
| `887370cfb81e` | 224 | yes | `48dac5bf22a7` |
| `b2ca0edc8c66` | 278 | yes | `b25dfb9a70e2` |
| `e73149cb0f1a` | 270 | yes | `5dd99dc0b509` |
| `b75be85649a8` | 271 | yes | `b4516d6f8b8a` |

### 5. Quality Gates

Structural lint (word count 40-180, subject <= 60 chars, no substituted punctuation, no banned phrases) and claims check (no unsupported assertions about the prospect).

**7 contacts removed:**

- `96950d6cff93` - em1:claim('profitability' is asserted about them and nothing stored supports it)
- `8cc5337f15d9` - em3:claim('profitability' is asserted about them and nothing stored supports it), em5:claim('our previous discussions' asserts we have contacted this person before, and no confirmed touch says we have)
- `c80bea930ec4` - em1:claim('utilization' is asserted about them and nothing stored supports it), em2:claim('utilisation' is asserted about them and nothing stored supports it), em4:claim('utilisation' is asserted about them and nothing stored supports it)
- `b2ca0edc8c66` - em4:claim('capacity' is asserted about them and nothing stored supports it)
- `e73149cb0f1a` - em2:claim('utilisation' is asserted about them and nothing stored supports it), em4:claim('utilisation' is asserted about them and nothing stored supports it), em5:claim('our previous discussions' asserts we have contacted this person before, and no confirmed touch says we have)
- `b75be85649a8` - em5:claim('our previous discussions' asserts we have contacted this person before, and no confirmed touch says we have)
- `56021aeda339` - em5:claim('our previous discussions' asserts we have contacted this person before, and no confirmed touch says we have)

---

## What the Operator Would Be Authorising

If the operator enables `heyreach.add_leads` or the EmailBison attach-leads route, they would be authorising:

- **23 leads** added to a new campaign
- Cohort: economic buyers (persona == 'economic_buyer')
- Channel: email (em1..em5 steps)
- Every lead has verified email, passing MX, safe Reoon, approved copy, and no unsupported claims
- No lead is already in another campaign
- No lead is on any suppression list

**This task does NOT write to any provider.** The batch file is prepared; the write is the operator's decision.

---

## Observations

- The estate has 300 records, 194 active, 92 contacts, 87 with email.
- 70 contacts match the economic_buyer cohort with email.
- 17 of those are already in campaigns (dedup removes them).
- The largest drop is at the exclusion step: 17 contacts are not sendable.
- Not-sendable breaks down into: never verified (no verification data), verification unknown, accept-all uncleared, and verification held.
- Of the 23 surviving leads, all have em1 copy with resolved personalisation.

## Proven Learnings

- The sendable filter is the most impactful exclusion. 17 of 53 post-dedup contacts fail it. The verification estate is uneven: some contacts have full waterfall verification, others have none.
- No reply events exist in the estate, so positive-reply protection removes zero contacts. This is an absent measurement, not evidence that nobody replied.
