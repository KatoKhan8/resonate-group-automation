PRIORITY: P0
DEPENDS:

# TASK-147 - the EmailBison cohort, resolved against the LIVE queue rather than a snapshot

## WHY THIS IS P0 AND NOT A LATER PHASE

The operator has made both channels P0. EmailBison is not a thing that starts
when LinkedIn finishes: the two share an estate, a suppression model and an
account-collision rule, and nothing else. Neither blocks the other.

TASK-145 designed the cohort against `work/queue.snapshot.jsonl` and found:

    cold email (verified address, no bison_lead_id)      26
    prior outreach, no reply                             29
    unverified, neither                                 245

That was 300 records. **The live queue is now 550 and the snapshot is stale.**
This task re-resolves those numbers and answers the questions the design left
open, so Claude can build the campaign without re-deriving any of it.

## THE SNAPSHOT PROBLEM, AND WHAT TO DO ABOUT IT

`work/queue.jsonl` is production and you must not write to it. The snapshot in
your worktree is old. So:

**Ask Claude to refresh the snapshot before you start**, by writing a line
under FINDINGS saying you need it and committing that immediately. Then work
against whatever `work/queue.snapshot.STAMP` says, and QUOTE THE STAMP in
every number you report. A measurement against a snapshot is a measurement at
a moment.

If the stamp is older than the numbers above, say so and report both.

## THE FOUR QUESTIONS

### 1. Who is actually cold on email, right now?

Partition the live-ish estate exactly as TASK-145 did, and say what moved:

    verified address AND no bison_lead_id          -> cold cohort
    bison_lead_id present                          -> needs question 2
    no verified address                            -> not eligible, and the
                                                      standing rule is that no
                                                      email is generated for
                                                      an unverified address

### 2. Were the 29 with a `bison_lead_id` ever actually EMAILED?

TASK-145 found the honest answer is probably no, and it matters enormously:

    campaign 481   PAUSED, 23 leads, 0 emails sent
    campaign 451   COMPLETED, 1 email sent

A `bison_lead_id` is assigned at LEAD CREATION. Campaign 481 never sent. So
most of those 29 have a provider-side lead row and have received nothing - they
are effectively cold, and they are currently being held out of BOTH channels
on the assumption that they are not.

**Settle it from the provider.** You hold real EmailBison credentials and the
rule is READS ONLY - no write, no send, no campaign mutation, no resume, no
pause. Per lead, determine whether any email was actually sent, using the
routes `docs/BISON-API-CAPABILITY-MAP-2026-09-14.md` and
`docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` already establish.

If they were never emailed, say so with the field that proves it. That
potentially returns 29 contacts to BOTH the email and the LinkedIn cohorts,
which is a larger result than the cohort design itself.

### 3. What does the account-collision rule do to the email cohort?

The LinkedIn side measured this and it was brutal: 151 of 248 contacts
rejected at the ACCOUNT level - somebody at that company is mid-sequence, has
already replied, or a campaign there ended ambiguously.
`docs/COHORT-HEADROOM-2026-09-15.md` has the numbers.

The email cohort faces the same rule from the other side. Run
`collision.check_account` over the cold cohort's domains - cached per domain,
it is the account that is the unit - and report how many survive.

**Do not run `check_address` per contact for this.** That is a per-person read
and the account verdict answers the cohort question.

### 4. What cohorts fall out, and are they worth separating?

Group by whatever dimension the evidence ACTUALLY supports - TASK-140 found
signal was 100% null on the LinkedIn side and that angle was inferred from
title rather than evidenced. Do not assume email is richer; check.

For each proposed cohort: size, dimension values, and whether it is a CONTROL
cohort (the validated fallback copy, which asserts nothing specific, so the
cohort is for READING the result) or a CHALLENGER cohort (copy that asserts
something, which needs per-contact evidence and must clear the claims gate).

`PRODUCTION-SCALE-POLICY.md` is the contract: a campaign is a COHORT and never
a person, ~50 where inventory supports it, consolidation over proliferation.

## WHAT YOU MAY NOT DO

- No provider WRITES. No campaign creation, no sequence write, no lead
  creation, no resume, no pause. Reads only.
- Do not write to `work/` in any worktree.
- Do not run `py -3 -m src.generate --live`. Generation against the real queue
  is Claude's; a run here writes to an isolated worktree queue.
- Do not quote an open rate - `open_tracking` is False estate-wide.
- Do not count an UNKNOWN reply as negative.

## FILES ALLOWED

    docs/BISON-COHORT-LIVE-2026-09-15.md   (new)
    scripts/task147_*.py
    the task file itself

## FILES FORBIDDEN

    src/    work/    config/

## DELIVERABLE

The four answers with the snapshot stamp on every number, the per-lead
send-or-not verdict for the 29 with its proving field, the account-collision
survival count, and the cohort proposal with each cohort's arm.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** ccf5a20

**TESTS:**
- `scripts/task147_cohort_live.py` runs clean against the snapshot. Four-way
  partition sums to 550. All 29 bison_lead_id contacts checked against the
  live provider. All 38 cold-cohort domains checked via collision.check_account.
- `scripts/task147_never_emailed_collision.py` runs clean. All 13 never-emailed
  bison contacts checked against the live provider.

**FILES CHANGED:**
- `docs/BISON-COHORT-LIVE-2026-09-15.md` (new) — the deliverable
- `scripts/task147_cohort_live.py` (new) — main analysis script
- `scripts/task147_never_emailed_collision.py` (new) — supplementary collision
- `scripts/task147_results.json` (new) — machine-readable results
- Task file moved from TODO/ to RUNNING/

**FINDINGS:**

Snapshot stamp: `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

1. **Q1 — Who is cold:** 38 records (39 contacts) verified with no
   bison_lead_id. 29 records (29 contacts) with bison_lead_id. 483
   unverified. Estate grew from 300 to 550; all 250 new records are
   unverified.

2. **Q2 — Were the 29 emailed:** Split. 13 NEVER emailed (all campaign 481,
   proven by `overall_stats.emails_sent = 0`). 16 ACTUALLY emailed across
   older campaigns (265, 274, 327, 328, 330, 331, 352, 451). The 13 are
   effectively cold; the 16 are not. TASK-145's assumption that "probably
   no" was wrong for 16 of 29.

3. **Q3 — Account collision:** Cold cohort: 8 ALLOW, 16 STOP, 14 HOLD out
   of 38 domains. 31 of 39 contacts rejected (79.5%). Never-emailed bison:
   9 ALLOW, 0 STOP, 4 HOLD out of 13. Combined: **17 contacts survive all
   gates** (8 from cold cohort + 9 from never-emailed).

4. **Q4 — Cohort proposal:** One CONTROL cohort of 17. Signal is 100% null
   on the cold cohort (same as LinkedIn side). No CHALLENGER arm is
   supportable because no dimension carries evidence to assert on. The
   cohort is "nobody rejected them" — necessary but not a hypothesis.

**RISKS:**
- 17 contacts is below the ~50 target in PRODUCTION-SCALE-POLICY. Enough
  for a canary, not enough for a meaningful cohort.
- 14 HOLD domains in the cold cohort could become ALLOW if stopped-campaign
  ambiguity is resolved. That is a data question, not engineering.
- The snapshot is from 17:52 UTC on 2026-09-15. Provider reads (Q2, Q3) are
  live, but cohort membership is from the snapshot.

**RECOMMENDED CLAUDE ACTION:**
1. Review `docs/BISON-COHORT-LIVE-2026-09-15.md`
2. The 17 surviving contacts are the addressable email cohort
3. Decide whether to proceed with a 17-contact CONTROL canary or wait for
   more inventory (discovery/enrichment to populate signal, or
   stopped-campaign resolution to release HOLD domains)
4. The 16 actually-emailed contacts are excluded from any cold cohort
