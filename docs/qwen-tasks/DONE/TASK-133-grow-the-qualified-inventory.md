PRIORITY: P1
DEPENDS: 

# TASK-133 - how much more qualified inventory is actually reachable?

## THE CEILING NOBODY HAS PUSHED ON

The largest honest cohort is 51 verified-sendable economic_buyers, out of 92
contacts on 300 not-dropped records. TASK-096 said the estate supports roughly
one cohort, and it was right.

That number is a CEILING SET BY ENRICHMENT, not by qualification:

    economic_buyer cohort              72
    with a verified sendable email     51    <- 21 lost HERE
    of the 19 originally excluded      12 unknown, 6 accept_all_uncleared, 1 held

**21 qualified people are unreachable because their address was never
verified**, not because they failed a gate. That is the largest single loss in
the funnel and nobody has costed recovering it.

## WHAT TO ESTABLISH

**Answer item 4 FIRST. It is the one most likely to change the plan.**

1. **What would verification cost?** For the 21: what does the waterfall charge
   per address, which providers are in it, and what is the expected recovery
   rate for `unknown` versus `accept_all_uncleared`? Those are different
   problems - an accept-all domain may never resolve, and spending on it
   repeatedly is waste.

2. **What is in the 300 records that is NOT yet a contact?** 300 records carry
   only 92 contacts. Are the rest contactless because nobody was found, because
   discovery never ran, or because they were dropped? Report the split. If 200
   records have never had person-discovery run, the ceiling is a DISCOVERY
   question rather than an enrichment one, and the answer is completely
   different.

3. **Which other cohorts sit just under the line?** TASK-096 found founder at
   45 and champion at 20. With verification recovered, does any reach 50?

4. **LINKEDIN REACHABILITY IS A SEPARATE GATE FROM EMAIL.** A HeyReach cohort
   needs a LinkedIn profile, not a verified email. How many of the 92 - and how
   many contacts across all 300 records - carry a usable LinkedIn URL?

   **That number may be larger than 51 and has never been reported**, because
   every funnel built so far filtered on email first. If it is materially
   larger, the LinkedIn cohort is not inventory-limited at all and the whole
   costing exercise above matters less than it appears to.

## WHAT NOT TO DO

- **Do not spend credits.** This is a costing exercise. Report what recovery
  would cost and what it would yield; the spend is the operator's decision.
- Do not count a contact as reachable on an unverified address.
- Do not lower the ICP bar to grow the number. Qualification decides
  ELIGIBILITY, inventory decides BATCH SIZE, and they are different questions -
  confusing them is how a cohort gets padded with people who should not be in
  it.
- Hash every identifier. Report counts, not people.

## DELIVERABLE

`docs/INVENTORY-CEILING-2026-09-15.md`: the funnel with every loss named and
counted, **the LinkedIn-reachable number stated separately from the
email-reachable one**, the verification cost and expected yield for the 21, and
a plain answer to "how many qualified leads could this estate support if we
spent what it takes".

## RESULT

STATUS: DONE
COMMIT: 19250c0
TESTS: N/A — analysis task, no code changes to production modules
FILES CHANGED:
  - docs/INVENTORY-CEILING-2026-09-15.md (deliverable)
  - scripts/task133_inventory_ceiling.py (analysis script)
  - scripts/task133_detail.py (detailed breakdown script)
  - scripts/task133_12records.py (12 contactless records script)

FINDINGS:

**THE KEY FINDING: LinkedIn changes the entire picture.**

All 92 primary contacts carry a LinkedIn URL (100%). The estate is NOT
inventory-limited on the LinkedIn channel. The email verification ceiling
TASK-096 identified matters only for email.

| Channel | Economic buyers | All personas |
|---------|----------------|-------------|
| LinkedIn (HeyReach) | 72 | 92 |
| Email (EmailBison) | 51 | 56 |

**The 21 "lost" economic_buyers are not lost for HeyReach.**

The 21 break down as: 13 unknown verdict, 6 accept_all_uncleared, 2 no email.
Re-verifying the 13 unknowns costs 13-26 credits and may recover 5-10.
The 6 accept_all are a domain property and re-spending is likely waste.
The 2 with no email need email discovery first (additional cost).

**85 records have no contacts:**
- 39 domain unstaffed (people-count=0) — nobody to find
- 46 ICP-blocked (geo, size, or both) — structurally ineligible
- 12 passed ICP, people exist, decision-makers never run — recoverable at
  ~120 credits (12 × 10 for decision-makers)

**Champion cohort cannot reach 50** by any mechanism (5 sendable + 9 unknown = 14 max).

**Plain answer:** The estate supports 72 economic_buyers on LinkedIn today
and 51 on email. With ~133-146 credits of spend, email could reach ~60-69.
LinkedIn is already at 72 and is not limited by verification.

RISKS:
- Recovery estimates (5-10 from 13 unknowns) are extrapolated, not measured
- The 12 contactless records may produce zero economic_buyers from discovery
- Accept-all domains may partially resolve with Reoon, but evidence is thin

RECOMMENDED CLAUDE ACTION:
- Use the LinkedIn-reachable 72 as the HeyReach cohort ceiling
- Decide whether the 13-26 credit verification spend is worth it for email
- The 12 contactless ICP-passed records are low-hanging fruit for discovery
  if person-discovery budget allows (~120 credits)
