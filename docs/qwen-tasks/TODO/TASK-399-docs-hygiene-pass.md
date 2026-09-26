PRIORITY: P3
SIZE: S
DEPENDS:

# TASK-399 — docs hygiene: find what's now false in the standing docs

Tonight alone corrected two stale claims found by direct measurement:
CLAUDE.md's "ONE CAMPAIGN IS SENDING, NOT EIGHT" (it was eight, three ours)
and a superseded canary disposition table. Sweep the standing docs for more
of the same class of drift.

## Scope

    CLAUDE.md
    docs/OPERATING-MODE.md
    docs/PRODUCTION-HANDOFF-2026-09-26-EVENING.md
    docs/state/PROBLEM-REGISTER.md (if referenced elsewhere as current)

For each specific, checkable claim (a count, a SHA, a "the only X is Y"
statement, a task's stated status), verify it against current master or a
read-only provider check. Report every claim found FALSE, with the
correction and its evidence — do not fix silently; a status doc changes
based on evidence, and the correction itself is the deliverable here, listed
for Claude to apply, not applied directly by this task (these are
operator-visible standing docs).

## Acceptance

1. A list of every checked claim, PASS or FALSE, with evidence for each.
2. For every FALSE claim: the correct current value, sourced (git SHA,
   provider read, file:line) — not a guess.
3. Do not touch the files yourself; report only. Claude applies the
   corrections.

## What this task may NOT do

- Do not edit any of the scoped files directly - report only.
- Read-only toward providers if a provider check is needed for one claim.
- Nothing sent, nothing activated.

---

## RESULT BLOCK

**STATUS:** DONE
**COMMIT SHA:** (report only — no code changes)
**TESTS:** N/A (read-only investigation)
**FILES CHANGED:** This task file only (moved TODO → REVIEW)
**ARTIFACT KIND:** finding (report)
**FINDINGS:** Below.
**RISKS:** None — report only, no edits to scoped files.
**RECOMMENDED CLAUDE ACTION:** Apply the corrections listed under FALSE claims.

---

## CLAIM-BY-CLAIM VERIFICATION

Current master at time of check: **`b46bba78`** (`git rev-parse origin/master`, 2026-09-27).

---

### CLAUDE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | "docs/PRODUCTION-HANDOFF-2026-09-26-MORNING.md IS THE CURRENT STATE" | **FALSE** | The evening handoff exists (`docs/PRODUCTION-HANDOFF-2026-09-26-EVENING.md`) and its section 1 says "It supersedes the 2026-09-26 morning handoff on everything it covers." CLAUDE.md's own first line points to the wrong document. **Correction:** First line should reference the evening handoff, or both should be replaced by whatever is now current. |
| 2 | PROVIDER-CAMPAIGNS.json `generated_at: 2026-09-26T18:29:43Z` | **FALSE** | The actual file says `generated_at: 2026-09-26T18:56:41+00:00` (line 3 of PROVIDER-CAMPAIGNS.json). **Correction:** Update the timestamp in CLAUDE.md's first paragraph. |
| 3 | "EIGHT EMAILBISON CAMPAIGNS ARE ACTIVE, THREE OF THEM OURS" | **PASS** | PROVIDER-CAMPAIGNS.json confirms 8 active: 493, 489, 487 (resonate) + 502, 418, 352, 328, 327 (client_or_other). |
| 4 | "40 campaigns total in the workspace" | **PASS** | `campaigns_total: 40` in PROVIDER-CAMPAIGNS.json. |
| 5 | "493 (22 leads, 22 sent), 489 (5 leads, 10 emails sent), 487 (10 leads, 0 sent)" | **PASS (lead counts)** | PROVIDER-CAMPAIGNS.json: 493 lead_count=22, 489 lead_count=5, 487 lead_count=10. Sent counts require a live provider read to re-verify. |
| 6 | "Five more are ACTIVE and client-or-other - 502, 418, 352, 328 and 327" | **PASS** | All five confirmed active, client_or_other in PROVIDER-CAMPAIGNS.json. |
| 7 | "491, 492, 494 and 496 are PAUSED; 495 is archived; 497 and 498 are completed" | **INCOMPLETE** | Omits our paused campaigns: 503, 504, 505, 500, 481. Also omits our draft campaigns: 484, 485. Also omits our completed: 451, 506. The sentence reads as a comprehensive list of non-active ours but only covers 487-498. **Correction:** Either scope to "among 487-498" or list all. |
| 8 | "77 emails with an empty subject" / "64 emails carrying a different agency's pitch" / "76 recipients are suppressed" | **NOT VERIFIED** | Incident claims from 09-23. Require a live provider read to re-verify. No reason to doubt but no file evidence either. |
| 9 | "154 attested mailboxes x 15 = 2,310" | **NOT VERIFIED** | Repeated across multiple docs from 09-21/22. No current source file confirms the mailbox count is still 154. Structural claim about the cap formula. |

---

### OPERATING-MODE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 10 | "Last verified: **cad7c7a4** on origin/master" | **FALSE** | Current master is `b46bba78`, **45 commits later**. `git rev-list --count cad7c7a4..b46bba78` = 45. **Correction:** Update to `b46bba78` (or derive live). |
| 11 | "Live chain as of cad7c7a4: Offer Engine on master (TASK-333 integrated) → campaign strategy (TASK-320, running) → production wiring (TASK-321, blocked on 320)" | **FALSE** | TASK-320 is integrated (commit c70db5ef). TASK-321's finding is integrated (commit d3d87b80). The chain has moved well beyond this snapshot. **Correction:** Update the chain to reflect current state — TASK-369 (entrypoint) is on master, TASK-375 (skill loading) is on master, etc. |
| 12 | "Five skills verified ready on branch, not yet integrated" | **FALSE** | Five skills are on master in `src/skills/` (account_research, campaign_strategy, cold_email_writing, linkedin_writing, signal_verification). `generate_campaign.py` calls `skills.load()` for all five (lines 152, 228, 240, 301, 302). **Correction:** Remove "on branch, not yet integrated" — they are integrated and consumed. |
| 13 | "493 is the only campaign sending and stays as it is" (PRODUCTION FREEZE section) | **FALSE** | CLAUDE.md's own corrected figures say 489 has 10 emails sent and is ACTIVE. 487 is ACTIVE with 0 sent. Three of ours are active, not one. **Correction:** "493, 489 and 487 are ACTIVE; 489 has sent, 487 has not yet" or equivalent. |
| 14 | "128 named failures" / "12,737 tests" | **PASS** | SUITE-BASELINE-2026-09-26.txt: "Ran 12737 tests", "128 distinct fully-qualified failing names". |
| 15 | Launch Blocker #2: "Resume does not re-evaluate suppression — EMAIL_RESUME is facing=False" | **STALE** | Commit 08af5146 "Close the resume P0: a resume now re-reads the stops from disk and refuses by name" — integrated on master. The blocker is addressed. **Correction:** Remove from LAUNCH BLOCKERS or mark resolved. |
| 16 | Launch Blocker #7: "Preview duplicates cadence — hardcoded LinkedIn days 1/3/8/14 against canonical 1/3/6/10/15" | **STALE** | Commit 7291131c "Integrate TASK-343 (retargeted): the HeyReach provider payload now derives its delays from the canonical cadence, not literals" — integrated on master. **Correction:** Remove from LAUNCH BLOCKERS or mark resolved. |
| 17 | "NOT on master: the v2 copy pipeline (copyengine, copystages, copyprompts have no production caller)" (section 3, handoff claim repeated in OPERATING-MODE context) | **FALSE** | `copystages` and `copyprompts` are consumed by `generate_campaign.py` (20+ references) and `campaignstrategy.py` (4 references). `copyengine` does not exist as a module. `generate_campaign.py` itself has no caller in src/ — so the top-level chain is still disconnected, but the specific claim about copystages/copyprompts is wrong. **Correction:** "generate_campaign.py consumes copystages and copyprompts but has no production caller itself." |

---

### PRODUCTION-HANDOFF-2026-09-26-EVENING.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 18 | "origin/master = **b3336974**" | **FALSE** | Current master is `b46bba78`, **36 commits later**. `git rev-list --count b3336974..b46bba78` = 36. **Correction:** Update to `b46bba78`. |
| 19 | "30 commits integrated today" | **STALE** | Was true when written. 36 commits have been added since. |
| 20 | "no production entrypoint exists in git" (section 3) | **FALSE** | TASK-369 built one (commit 6ca3b94c "Integrate TASK-369: the production entrypoint exists in git"). TASK-375 confirmed it loads five skills (commit bcdfccf4). However, TASK-375 also found it has no caller — so it EXISTS but is DISCONNECTED. **Correction:** "A production entrypoint exists in git (`generate_campaign.py`) but has no production caller." |
| 21 | Task statuses in section 4 | **STALE** | Many tasks listed as "awaiting review" or "queued" have been integrated: TASK-366 (commit 73937797), 354 (f3552959), 365 (86564e0b), 369 (6ca3b94c), 346 (2fdb5568), 343 (7291131c), 321 finding (d3d87b80), 368 reconciliation (d3d87b80), 374 (a8b21a2e), 375 (bcdfccf4), 376 (149a3730), 377 (c20ebbd8). |
| 22 | Campaign state in section 1 | **PASS (self-corrected)** | The handoff's own section 1 corrects the original numbers and matches PROVIDER-CAMPAIGNS.json. |

---

### PROBLEM-REGISTER.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 23 | ISSUE statuses and structure | **PASS** | The register's rules, numbering, and REFUTED-keeping policy are sound. Individual ISSUE claims are time-stamped measurements. No specific claim is verifiably FALSE against current state without a live provider check. |

---

## SUMMARY OF FALSE/STALE CLAIMS REQUIRING CORRECTION

1. **CLAUDE.md line 1:** Morning handoff referenced as current → evening handoff is current
2. **CLAUDE.md:** PROVIDER-CAMPAIGNS.json timestamp wrong (18:29:43Z → 18:56:41Z)
3. **CLAUDE.md:** Paused campaign list incomplete (omits 500, 481, 503-505, 484-485, 451, 506)
4. **OPERATING-MODE:** Master SHA stale (cad7c7a4 → b46bba78, 45 commits behind)
5. **OPERATING-MODE:** Critical path chain stale (TASK-320/321 both integrated, chain has moved on)
6. **OPERATING-MODE:** "Five skills on branch, not integrated" → they are on master and consumed
7. **OPERATING-MODE:** "493 is the only campaign sending" → 489 has also sent
8. **OPERATING-MODE:** Launch blockers #2 and #7 are resolved (commits 08af5146, 7291131c)
9. **OPERATING-MODE / handoff:** "copystages/copyprompts have no production caller" → they are consumed by generate_campaign.py
10. **Handoff:** Master SHA stale (b3336974 → b46bba78, 36 commits behind)
11. **Handoff:** "no production entrypoint exists in git" → TASK-369 built one; it exists but has no caller
12. **Handoff:** Task statuses in section 4 are stale (12+ tasks integrated since)
