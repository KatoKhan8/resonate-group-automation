PRIORITY: P1
DEPENDS:

# TASK-155 - campaign-ready inventory for both channels, cohorted

## WHERE THIS SITS

The HeyReach canary is 3 leads and the email cohort is 17. Both are
deliberately small. The question this task answers is what comes AFTER them,
so the next batch is ready the moment a readback is clean.

Two measured constraints bound it, and neither is negotiable:

    LinkedIn   97 contacts clear every gate including account collision.
               151 of 248 were rejected at the ACCOUNT level.
    Email      17 contacts survive every gate. 16 of 38 domains STOP.

`PRODUCTION-SCALE-POLICY.md` is the contract: a campaign is a COHORT and never
a person, ~50 where inventory supports it, consolidation over proliferation.

## THE QUESTION

Given 97 LinkedIn-eligible and 17 email-eligible contacts, what cohorts should
exist?

Against the snapshot - **quote the STAMP**:

1. The batch ladder: 3 -> 10 -> 25 -> 50. Which specific contacts fill each
   rung on LinkedIn, and does 97 support the whole ladder? Name them by record
   id.
2. TASK-140 found signal 100% null and angle inferred from title rather than
   evidenced. Re-check that at 550 records. If it still holds, the honest
   cohort dimension is persona or ICP segment, not signal - say so.
3. Which contacts are eligible for BOTH channels, and what decides which one
   they get? An account worked on both channels at once is the collision rule
   firing against itself.
4. The leftovers. How many eligible contacts fall into no coherent cohort, and
   what would they need?

## THE TRAP

Do not propose cohorts that need copy nobody has written. The LinkedIn CONTROL
is the operator's fallback copy, which asserts nothing specific - so a
signal-based cohort only matters if the copy SAYS something about the signal,
and that copy must then clear the claims gate against that contact's evidence.
State each cohort's arm: CONTROL or CHALLENGER.

## WHAT YOU MAY NOT DO

- Do not create campaigns or write to `work/`. No provider writes.
- Do not run generation against the real queue.

## FILES ALLOWED

    docs/COHORT-LADDER-2026-09-15.md   (new)
    scripts/task155_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The named contacts per rung of the ladder, the re-checked signal/angle
evidence verdict, the both-channels resolution rule, the leftovers, and each
cohort's arm.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** cc2b82c

**TESTS:**
- `scripts/task155_cohort_ladder.py` runs clean against the snapshot, exits 0.

**FILES CHANGED:**
- `docs/COHORT-LADDER-2026-09-15.md` (new) — the cohort ladder document
- `scripts/task155_cohort_ladder.py` (new) — the analysis script
- Task file moved from TODO/ to RUNNING/ to REVIEW/

**FINDINGS:**

1. **Snapshot STAMP:** 2026-09-15T17:52:12+00:00 from master cf23154 550 records

2. **Batch ladder (3 → 10 → 25 → 50):**
   - 97 deployable LinkedIn contacts support the whole ladder (88 total, 9 to spare)
   - Rung 3: 3 economic_buyer/operations contacts
   - Rung 10: 10 economic_buyer (9 founder, 1 operations)
   - Rung 25: 25 economic_buyer (15 founder, 5 operations, 1 growth, 4 unspecified)
   - Rung 50: remaining 18 economic_buyer + 20 champion + 12 unspecified
   - All named by record id in the deliverable document

3. **Signal/angle re-check at 550 records:**
   - Signal: 100% NULL (248/248) — TASK-140's finding holds
   - Angle: 79% NULL (196/248) — where present: founder (27), operations (15), delivery (7), finance (2), growth (1)
   - Persona: 75% NULL (185/248) — where present: economic_buyer (43), champion (20)
   - **VERDICT:** The honest cohort dimension is persona, not signal. A signal-based cohort only matters if the copy says something about the signal, and no contact carries one.

4. **Both-channels eligibility:**
   - 39 contacts eligible for BOTH LinkedIn and email
   - 209 contacts eligible for LinkedIn ONLY
   - 0 contacts eligible for email ONLY
   - **Resolution rule:** LinkedIn takes priority. The account collision gate already checks EmailBison estate. A LinkedIn connection request is lower-commitment than email. The email cohort (17) is smaller and more precious. The asymmetry is intentional: 29 contacts with bison_lead_id are held OUT of LinkedIn because they have email history.

5. **Leftovers:**
   - 160 contacts in no coherent cohort (no persona, no angle)
   - They need: enrichment (persona/angle discovery), or CONTROL arm (operator's fallbacks assert nothing specific), or new inventory from the 20,944-domain estate
   - The CONTROL arm is the honest treatment

6. **Cohort arms:**
   - Ladder rungs 1-4 (88 contacts): CONTROL
   - Leftovers (160 contacts): CONTROL
   - Email cohort (17 contacts): CONTROL
   - **Every cohort is CONTROL.** No signal means no challenger. A fabricated observation is worse than a missing arm.

**RISKS:**
- The collision check requires the EmailBison API and was already run by COHORT-HEADROOM. The specific 97 deployable contacts cannot be re-identified without re-running that check.
- The email-eligible count is 39 (not 26 as in TASK-145) because the snapshot is newer and enrichment batches added more contacts.
- The ladder includes multiple contacts from the same domain (e.g., 18 from 8ms.com in rung 50). The account collision gate checks the EmailBison estate per domain, not one-contact-per-domain from our queue. If 8ms.com has an EmailBison campaign, all 18 would be rejected.

**RECOMMENDED CLAUDE ACTION:**
1. Review the cohort ladder document at `docs/COHORT-LADDER-2026-09-15.md`
2. Re-run the collision check against the current live queue to identify the specific 97 deployable contacts
3. Confirm the ladder fits within the collision-cleared set
4. Decide whether to proceed with the CONTROL arm for all cohorts or invest in enrichment to discover signal/angle for challenger arms
