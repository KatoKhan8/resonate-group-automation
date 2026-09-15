PRIORITY: P1
DEPENDS:

# TASK-153 - the historical estate, and the two findings that already moved production

## WHY THIS IS NOT A REPEAT OF TASK-139

TASK-139 measured relationship state and found the machinery wired but unfed.
Two things have happened since that change the question:

1. **13 of 29 contacts carrying a `bison_lead_id` were NEVER EMAILED.**
   Campaign 481 was paused before it sent anything; a lead id is assigned at
   lead creation. Proving field: `overall_stats.emails_sent` on
   `GET /leads/{id}`. Those 13 are cold and are currently held out of BOTH
   channels on a false assumption.
2. **A contact was refused at the provider gate for 4 prior LinkedIn messages**
   from the client's own seat, last 2026-07-18, never replied to.
   `collision.check_linkedin_profile` sees that; nothing in cohort selection
   did until it was moved there.

So the estate knows more than the pipeline reads. This task finds the rest.

## WHAT TO MEASURE

Against the snapshot - **quote the STAMP** - plus READ-ONLY provider reads:

1. Re-run the never-emailed check across every contact carrying a
   `bison_lead_id` and confirm the 13/16 split holds at 550 records.
2. For every contact in the eligible pool, how many have LinkedIn conversation
   history on one of the client's 33 seats? This is the check that caught one
   at the gate. Count them BEFORE they reach a gate.
3. Which accounts carry a prior REPLY, positive or negative, and where is that
   recorded? A positive reply is not a reason to exclude somebody - it is a
   reason to treat them as warm - and the two are currently conflated.
4. What is the honest total: of the eligible pool, how many are genuinely cold,
   how many are warm, how many must never be contacted?

## WHAT YOU MAY NOT DO

- READS ONLY at every provider. No write, no send, no campaign mutation.
- Do not write to `work/`. Do not change `eligibility.must_not_contact`.
- Hash prospect identifiers in the document.

## FILES ALLOWED

    docs/HISTORICAL-ESTATE-2026-09-15.md   (new)
    scripts/task153_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The 13/16 split re-confirmed at 550, the LinkedIn-history count across the
eligible pool, the prior-reply inventory with the field that proves each, and
the cold/warm/never split with its evidence.

## RESULT BLOCK

**STATUS:** DONE

**SNAPSHOT STAMP:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

**COMMIT SHA:** 78e9807

**TESTS:** No code changes in src/. Measurement scripts: `scripts/task153_snapshot_analysis.py`, `scripts/task153_provider_reads.py`. Findings document: `docs/HISTORICAL-ESTATE-2026-09-15.md`.

**FILES CHANGED:**
- `docs/HISTORICAL-ESTATE-2026-09-15.md` (new) — full findings
- `scripts/task153_snapshot_analysis.py` (new) — snapshot-only measurement
- `scripts/task153_provider_reads.py` (new) — provider reads (READ ONLY)
- `docs/qwen-tasks/RUNNING/TASK-153-*.md` (moved from TODO, result block added)

**FINDINGS:**

1. **13/16 split confirmed at 550 records.** Re-checked all 29 bison_lead_id
   contacts via `GET /leads/{id}`. 13 have `overall_stats.emails_sent = 0`
   (all campaign 481, paused before sending). 16 have 1-21 emails across
   older campaigns. Zero replies at the provider on either side.

2. **LinkedIn conversation history: 7 of 68 verified contacts have prior
   conversations** on the client's 41 seats (org_unit 118832, 50 campaigns).
   - 1 REPLIED: h:e196bb262403, 2 messages, last 2026-05-07, they replied.
     NOT in canonical state.
   - 6 TOUCHED: 1-9 messages, various seats, last 2026-06-12 to 2026-09-04.
   - 59 CLEAR, 2 broad match (name too common to certify).

3. **Prior reply inventory:** Zero `reply_received` events in canonical
   state. Zero replies at EmailBison across all 29 bison contacts. One
   LinkedIn reply at HeyReach NOT imported. The proving fields:
   `events[]` type `reply_received` (0), `overall_stats.replies` (0/29),
   HeyReach `lastMessageSender = CORRESPONDENT` (1/68).

4. **Cold/warm/never split (277 contacts on 425 active records):**
   - Cold: 49 (36 verified no-history + 13 never-emailed bison)
   - Warm: 19+2 (16 emailed, 3 LinkedIn-only, 1 LinkedIn reply, 2 broad)
   - Must never contact: 0
   - Unverified: 209
   - Suppressed: 0

**RISKS:**
- The sender inventory (`work/senders.jsonl`) is absent in this worktree,
  so the LinkedIn check bypasses `collision.check_linkedin_profile` and
  establishes tenant scope directly from campaigns + `all_li_accounts`.
  The algorithm is identical but the code path differs from production.
- 2 broad-match contacts could not be certified either way.
- The one LinkedIn reply (h:e196bb262403) is at the provider and not in
  canonical state. Until imported, `eligibility._replied()` will not block.

**RECOMMENDED CLAUDE ACTION:**
- Review `docs/HISTORICAL-ESTATE-2026-09-15.md` for accuracy
- Import the HeyReach reply for h:e196bb262403 into canonical state
- Release the 13 never-emailed bison contacts from the hold-out
- Decide whether the 3 LinkedIn-only warm contacts need different copy
