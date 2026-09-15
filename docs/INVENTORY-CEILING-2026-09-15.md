# Inventory Ceiling Analysis — 2026-09-15

**Snapshot:** `work/queue.snapshot.jsonl` — 300 records, taken 2026-09-14T21:52:15Z from master 0ac5e60

---

## The headline finding: LinkedIn changes everything

**Every one of the 92 primary contacts carries a LinkedIn URL.** The estate is not inventory-limited on the LinkedIn channel. The email verification ceiling that TASK-096 identified matters only for the email channel.

| Channel | Economic buyers reachable | All personas reachable |
|---------|--------------------------|----------------------|
| LinkedIn (HeyReach) | **72** | **92** |
| Email (EmailBison) | 51 | 56 |
| LinkedIn advantage | +21 | +36 |

The 21 economic_buyers who are "lost" to email verification are **not lost at all** for HeyReach. They have LinkedIn profiles and can be reached today.

---

## The complete funnel

```
300 total records
 ├── 106 dropped
 │    ├── 98 rejected at ICP (no person-level enrichment)
 │    └──  8 no contact found at domain
 └── 194 active
      ├── 109 with contacts (92 primary + 896 excluded)
      └──  85 without contacts
           ├── 39 domain unstaffed (people-count = 0)
           ├── 46 ICP-blocked (geo, size, or both)
           └── 12 passed ICP, people found, but no decision-makers run
```

### Contact-level funnel

```
92 primary contacts
 ├── 87 with email address
 │    ├── 56 verified sendable (51 economic_buyer, 5 champion)
 │    ├── 22 unknown verdict (13 economic_buyer, 9 champion)
 │    └──  9 accept_all_uncleared (6 economic_buyer, 3 champion)
 └──  5 without email address (all have LinkedIn)
```

---

## Question 4: LinkedIn reachability (answered first, as instructed)

**92 of 92 primary contacts have a usable LinkedIn URL — 100%.**

This was never measured before because every funnel built so far filtered on email first. The LinkedIn channel bypasses the entire email verification problem.

### LinkedIn-reachable by persona

| Persona | With LinkedIn | Verified email | Gap |
|---------|--------------|----------------|-----|
| economic_buyer | 72 | 51 | +21 |
| champion | 20 | 5 | +15 |

### Excluded contacts with LinkedIn

420 of 896 excluded contacts also carry LinkedIn URLs. These are real people at qualified companies who were excluded because their title was not a target persona. They are not recoverable without changing the persona definition.

---

## Question 1: Verification cost for the 21 economic_buyers

The 21 economic_buyers without verified-sendable email break down as:

| State | Count | Cost to re-verify | Expected recovery |
|-------|-------|-------------------|-------------------|
| Unknown verdict | 13 | 13–26 credits | Moderate — never definitively answered |
| Accept_all_uncleared | 6 | 6–18 credits | Low — domain property, not per-address |
| No email at all | 2 | Requires email discovery first | Unknown — needs a separate waterfall |

### Cost detail

The verification waterfall is ContactOut (1 credit) → Deliverable (1 credit) → Reoon (1 credit), stopping when two providers agree.

- **13 unknown addresses:** ContactOut re-verify at 1 credit each = 13 credits. If still inconclusive, Deliverable second opinion at +13 credits. **Expected: 13–26 credits.** Some of these will resolve to valid; others will remain unknown or become invalid.

- **6 accept_all addresses:** These are on domains that accept all mail. Re-running the waterfall costs 6–18 credits and is **likely waste** — accept-all is a domain property, not a per-address verdict. Spending on these repeatedly buys the same "cannot determine" answer. **Recommendation: do not re-verify these.**

- **2 no-email contacts:** These need email discovery (Blitz email lookup at 1 credit, or AI Ark people search at 2 credits) before verification even starts. **Expected: 2–4 credits for discovery + 2–6 for verification = 4–10 credits**, with no guarantee of finding an address.

### Total estimated cost

| Scenario | Credits | Expected new sendable |
|----------|---------|----------------------|
| Unknowns only (conservative) | 13 | 5–10 (estimate) |
| Unknowns + full waterfall | 26 | 8–13 (estimate) |
| Everything including accept-all and no-email | 44–54 | 8–13 (accept-all unlikely to resolve) |

**The honest answer:** spending 13–26 credits on the 13 unknowns might recover 5–10 email-sendable economic_buyers. But the LinkedIn channel already reaches all 72, making this investment relevant only if email outreach is specifically needed.

---

## Question 2: What is in the 300 records that is NOT yet a contact?

Of 194 active records, 85 have zero contacts. The split:

| Reason | Count | Recoverable? |
|--------|-------|-------------|
| Domain unstaffed (people-count = 0) | 39 | No — nobody works there on LinkedIn |
| ICP-blocked (geo, size, or both) | 46 | No — does not meet client criteria |
| Passed ICP, people exist, but decision-makers never run | 12 | **Yes — person-discovery would find them** |

### The 12 recoverable records

These records passed ICP, have people on LinkedIn (people-counts range from 5 to 739), but the paid decision-makers call was never made. They are the only records where running discovery would add new contacts.

Notable: 4imprint.com has 739 LinkedIn profiles and 501+ employees — a large company that passed ICP but was never worked.

### The 46 ICP-blocked

| Block reason | Count |
|-------------|-------|
| Geo outside client markets only | 7 |
| Size under minimum only | 16 |
| Both geo AND size | 11 |
| Other ICP flags | 12 |

These are structurally ineligible. Lowering the ICP bar to include them would violate the qualification rules and is explicitly out of scope.

### The 39 unstaffed domains

People-count was 0. There is nobody to find. These records are dead ends for person-discovery.

---

## Question 3: Which cohorts sit just under the line?

| Persona | Verified sendable | + Unknown | Potential | Gap to 50 |
|---------|------------------|-----------|-----------|-----------|
| economic_buyer | 51 | +13 | 64 | **Already past 50** |
| champion | 5 | +9 | 14 | 36 |

**Economic_buyer already exceeds 50** on LinkedIn (72) and would exceed 50 on email (64) with full verification recovery.

**Champion cannot reach 50** by any available mechanism. Even recovering all 9 unknowns and adding the 12 contactless records' worth of discovery yields at most 14 + an unknown number from discovery — and the 12 records may not produce any champions.

---

## The plain answer

**How many qualified leads could this estate support if we spent what it takes?**

| Channel | Economic buyers | All personas | Bottleneck |
|---------|----------------|-------------|------------|
| LinkedIn (HeyReach) | **72** | **92** | None — every contact has a LinkedIn URL |
| Email (EmailBison) | 51 (current) / 64 (with verification spend) | 56 / ~70 | Email verification: 22 unknown + 9 accept-all + 5 no-email |
| Both channels combined | 72 unique people | 92 unique people | The same 92 people either way |

### What the spend buys

| Investment | Credits | Yield |
|-----------|---------|-------|
| Re-verify 13 unknown economic_buyers | 13–26 | ~5–10 additional email-sendable |
| Run decision-makers on 12 ICP-passed contactless records | ~120 (12 × 10 for decision-makers) | Unknown new contacts, possibly 4–8 economic_buyers |
| Total for maximum email recovery | ~133–146 | ~9–18 additional email-sendable |

### What does NOT help

- **Re-verifying the 6 accept_all addresses** — domain property, not per-address. Spending here is waste.
- **Lowering the ICP bar** — the 46 blocked records are blocked for stated reasons. Padding cohorts with ineligible people is how a campaign sends to the wrong audience.
- **Running discovery on the 39 unstaffed domains** — people-count is 0. There is nobody there.

### The real ceiling

The estate supports **72 economic_buyers on LinkedIn** and **51 on email** today. With ~37–50 credits of verification and discovery spend, email could reach ~60–69. LinkedIn is already at 72 and is not limited by verification at all.

**The LinkedIn channel is the larger and more accessible pool.** The email verification question is real but secondary — it matters only if the campaign strategy requires email as the primary channel.
