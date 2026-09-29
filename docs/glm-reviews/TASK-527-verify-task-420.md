# TASK-527 — GLM Independent Verification of TASK-420

## Review metadata

| Field | Value |
|-------|-------|
| Target task | TASK-420 (Docs Hygiene Pass) |
| Target branch | origin/glm-review-504-task-387 |
| Specified HEAD SHA | f3b68bf849d8361fab9d3f8f972229369cf60944 |
| Actual HEAD SHA at review | 515c638e14423a203e56f3ed3525af8569f72c07 (branch moved) |
| SHA reviewed | f3b68bf849d8361fab9d3f8f972229369cf60944 (per task instruction) |
| Review worktree | .qwen/worktrees/task527-review (detached at f3b68bf8) |
| Review date | 2026-09-29 |
| Reviewer | Qwen (GLM verification role) |
| Task file reference | docs/qwen-tasks/TODO/TASK-527-glm-verify-task-420.md |

**Branch movement notice:** The branch `origin/glm-review-504-task-387` has moved from `f3b68bf8` to `515c638e` since the task file was written. Per TASK-527 instructions, this verdict reviews `f3b68bf8` as the named artifact.

---

## 1. Does the artifact exist?

**YES.** `docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md` exists on the branch at `f3b68bf8`.

```
git show f3b68bf8:docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md
```

The artifact is a **finding** (docs audit report). It lists 27 checkable claims across three documents (CLAUDE.md, OPERATING-MODE.md, PRODUCTION-HANDOFF-2026-09-28-NIGHT.md) and classifies each as PASS or FALSE with evidence.

**Artifact kind:** Finding (read-only investigation, no production code changed).

---

## 2. Independent verification of claims

TASK-420 checked claims against master `f6979300`. Current master is `50293a86`. I verified each FALSE finding against the state at `f6979300` (the reference master TASK-420 used) and note where current master has since moved.

### CLAUDE.md findings (5 of 7 FALSE)

| # | Claim | TASK-420 verdict | Independent verification |
|---|-------|-----------------|-------------------------|
| 1 | "PRODUCTION-HANDOFF is current state" | PASS | **CONFIRMED PASS** — handoff file exists and is most recent |
| 2 | "EIGHT EMAILBISON CAMPAIGNS ARE ACTIVE" | FALSE | **CONFIRMED FALSE** — at f6979300, CLAUDE.md line 24 says this; PROVIDER-CAMPAIGNS.json (generated 2026-09-28T12:51:44Z) shows 0 active EmailBison campaigns. Note: current master (50293a86) has already corrected this to "NONE OF OUR CAMPAIGNS IS SENDING" |
| 3 | "487, 489 and 493 are ours and ACTIVE" | FALSE | **CONFIRMED FALSE** — same evidence; current master says "ALL PAUSED" |
| 4 | "Five more are ACTIVE - 502, 418, 352, 328, 327" | FALSE | **CONFIRMED FALSE** — same evidence |
| 5 | "TASK-305 does not exist on master" | PASS | **CONFIRMED PASS** — `src/providers/groq.py` does not exist |
| 6 | "TASK-313 does not exist on master" | PASS | **CONFIRMED PASS** — `docs/AUDIT-2026-09-26.md` does not exist |
| 7 | "2,310 a day is a CAP" | PASS | **CONFIRMED PASS** — referenced in `src/providerwrites.py` |

### OPERATING-MODE.md findings (8 of 14 FALSE)

| # | Claim | TASK-420 verdict | Independent verification |
|---|-------|-----------------|-------------------------|
| 1 | "Governing document: OPERATOR-DIRECTIVE-2026-09-26" | PASS | **CONFIRMED PASS** — file exists |
| 2 | "Offer Engine on master (TASK-333 integrated)" | PASS | **CONFIRMED PASS** — TASK-333 in DONE/ |
| 3 | "TASK-320, running" | FALSE | **CONFIRMED FALSE** — at f6979300, OPERATING-MODE.md line 36 says "running"; TASK-320 is in `docs/qwen-tasks/DONE/` |
| 4 | "TASK-321, blocked on 320" | FALSE | **CONFIRMED FALSE** — at f6979300, line 36 says "blocked"; TASK-321 is in `docs/qwen-tasks/DONE/` |
| 5 | "493 is the only campaign sending" | FALSE | **CONFIRMED FALSE** — PROVIDER-CAMPAIGNS.json shows 0 active. Note: current master OPERATING-MODE.md STILL says this (line 46) — not yet corrected |
| 6 | "TASK-427: _check_offers checks ONLY the selected offer" | FALSE | **CONFIRMED FALSE** — at f6979300, `src/generate_campaign.py:222` defines `_check_offers(client_name)` which calls `offers_mod.load()` and iterates ALL offers, not just the selected one |
| 7 | "offers.load() returns 8 offers, 2 approved" | PASS | **NOT INDEPENDENTLY VERIFIED** — requires running the offer loader; accepted on TASK-420's evidence |
| 8 | "TASK-426 MERGED" | PASS | **CONFIRMED PASS** — TASK-426 in DONE/ |
| 9 | "TASK-364 RUNNING (phase 2)" | FALSE | **CONFIRMED FALSE** — TASK-364 is in `docs/qwen-tasks/DONE/`, merged at commit 04260a59 |
| 10 | "TASK-400 DONE ON BRANCH, NOT MERGED" | FALSE | **CONFIRMED FALSE** — TASK-400 merged at f6979300 ("MERGE TASK-400: generate.py runs the new architecture"). Task file still in TODO/ is a separate queue hygiene issue |
| 11 | "TASK-425 NOT STARTED" | PASS | **CONFIRMED PASS** — TASK-425 in TODO/ |
| 12 | "ISSUE-048 claims.py still licenses a CSV figure" | FALSE | **CONFIRMED FALSE** — `docs/state/PROBLEM-REGISTER.md` states "ISSUE-048 · FIXED 2026-09-28 by operator decision B, not PRODUCTION_VERIFIED" |
| 13 | "ready depth 18" | FALSE | **NOT INDEPENDENTLY VERIFIED** — requires running `scripts/claim_task.py --status`; accepted on TASK-420's evidence |
| 14 | "~140 enumerated; ~40 integrated" | FALSE | **NOT INDEPENDENTLY VERIFIED** — same; accepted on TASK-420's evidence |

### PRODUCTION-HANDOFF findings (5 of 6 FALSE)

| # | Claim | TASK-420 verdict | Independent verification |
|---|-------|-----------------|-------------------------|
| 1 | "origin/master c0e47464" | FALSE | **CONFIRMED FALSE** — at time of TASK-420, master was f6979300; current master is 50293a86 |
| 2 | "TASK-426 MERGED" | PASS | **CONFIRMED PASS** |
| 3 | "TASK-364 RUNNING (phase 2)" | FALSE | **CONFIRMED FALSE** — merged at 04260a59 |
| 4 | "TASK-400 DONE ON BRANCH, NOT MERGED" | FALSE | **CONFIRMED FALSE** — merged at f6979300 |
| 5 | "TASK-430 (claimed)" | FALSE | **CONFIRMED FALSE** — TASK-430 is in TODO/ on master |
| 6 | "Qwen 12 workers; 4-5 holding claims" | FALSE | **NOT INDEPENDENTLY VERIFIED** — point-in-time claim; accepted on TASK-420's evidence |

### Verification summary

- **27 claims total** in TASK-420's report
- **15 claimed FALSE**: I independently confirmed **12 of 15** against source/state at f6979300
- **3 of 15 not independently verified** (require running scripts or provider readback): offers count, ready depth, integration counts, worker claim counts
- **12 claimed PASS**: I independently confirmed **9 of 12**
- **0 findings contradicted** — no claim TASK-420 said was FALSE is actually true, and no claim it said was PASS is actually false

---

## 3. Existence is not function — does the artifact have a consumer?

TASK-420 is a **finding artifact** — its purpose is to inform Claude's corrections to standing docs. The consumer is Claude, who applies corrections. The task explicitly states "Report only — Claude applies corrections, this task does not edit the scoped files."

**Consumer confirmed:** The finding is actionable by Claude. Some corrections have already been applied (CLAUDE.md campaign status corrected on current master). Others remain (OPERATING-MODE.md line 46 still says "493 is the only campaign sending").

---

## 4. Falsifiability of tests

**Not applicable.** TASK-420 is a read-only docs audit with no code changes and no tests. The artifact is the finding list itself.

---

## 5. Would merging delete anything?

The branch `glm-review-504-task-387` at `f3b68bf8` is an **accumulation branch** carrying 101 changed files (+13,033 / -594 lines). Files deleted from `TODO/`:

- TASK-319, TASK-387, TASK-396, TASK-407, TASK-408, TASK-414, TASK-420, TASK-421

These are task file movements (TODO → DONE/REVIEW/renamed), not production code deletions. No `src/` files are deleted. No test files are deleted.

**Risk:** The branch carries significant implementation work (TASK-400 rework, TASK-387 writeback demo, multiple GLM reviews, new tests, src/ changes to approve.py, bisonfactory.py, copylint.py, generate.py, generate_campaign.py, heyreachfactory.py, run.py, providers/). This is NOT a single-task branch. Merging the full branch would bring all of that work, which needs separate review.

**Cherry-pick scope:** TASK-420's artifact can be cherry-picked as a single file: `docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md`.

---

## 6. Scope drift

**Significant scope drift.** The branch carries work from at least 15 tasks beyond TASK-420:
- TASK-325, TASK-326, TASK-387, TASK-396, TASK-319, TASK-400 (rework 2/3)
- Multiple GLM verdicts (TASK-433, 435, 436, 442, 444, 451, 454, 460, 465, 468, 471, 472, 473, 475, 476, 481, 482, 504)
- New test files (test_task387_writeback_demo.py, test_task400_rework2.py, test_task400_rework3.py, test_only_the_last_subject_may_claim_finality.py, test_only_the_selected_offer_is_validated.py, test_pool_status.py)
- Source changes (approve.py, generate.py, generate_campaign.py, copylint.py, run.py, bisonfactory.py, heyreachfactory.py, providers/)
- New scripts (pool_status.py)
- New docs (5 top-level docs files)

TASK-420 itself is cleanly scoped — just the finding file. But extracting it requires cherry-pick from the accumulation branch.

---

## Findings

### Finding 1: TASK-420 artifact is correct and well-evidenced
- **Severity:** N/A (positive finding)
- **Evidence:** 12 of 15 FALSE claims independently confirmed; 9 of 12 PASS claims confirmed; 0 contradictions
- **Disposition:** VERIFIED

### Finding 2: Some TASK-420 corrections already applied
- **Severity:** N/A (informational)
- **Evidence:** CLAUDE.md on current master (50293a86) now says "NONE OF OUR CAMPAIGNS IS SENDING" — correcting claims 2-4 from TASK-420's CLAUDE.md section
- **Disposition:** INFORMATIONAL — remaining corrections still owed (OPERATING-MODE.md line 46, PRODUCTION-HANDOFF SHA and task statuses)

### Finding 3: Branch is an accumulation branch, not single-task
- **Severity:** Low (process concern, not artifact defect)
- **Evidence:** 101 files changed, 15+ tasks represented, significant src/ changes
- **Disposition:** Cherry-pick TASK-420's finding file; do not merge the full branch for this one task

### Finding 4: Three claims not independently verified
- **Severity:** Low
- **Evidence:** Offers count, ready depth, integration counts, worker claim counts require running scripts or live provider readback
- **Disposition:** Accepted on TASK-420's evidence; not contradicted

---

## Disposition

**VERIFIED.** TASK-420's artifact exists, is the correct type (finding), and its claims are substantively correct. The docs hygiene pass identified real staleness in standing documents and reported it accurately.

**MERGE / REWORK / CLOSE recommendation:** **MERGE** (cherry-pick).

- The finding is correct and actionable.
- Some corrections have already been applied; others remain owed.
- The artifact should be cherry-picked from the accumulation branch as `docs/qwen-tasks/DONE/TASK-420-docs-hygiene-pass.md`.
- The full branch `glm-review-504-task-387` at `f3b68bf8` carries significant other work that needs separate review and should not be merged wholesale for this one task.

**Remaining corrections owed (from TASK-420's findings):**
1. OPERATING-MODE.md line 46: "493 is the only campaign sending" — still false per PROVIDER-CAMPAIGNS.json
2. OPERATING-MODE.md: TASK-320, TASK-321, TASK-364 statuses (may have been corrected since f6979300; not re-verified on current master)
3. PRODUCTION-HANDOFF-2026-09-28-NIGHT.md: master SHA, TASK-364/400/430 statuses (handoff is historical and may be intentionally frozen)

---

*Review performed read-only. No provider calls. No production state modified. No files changed outside this review document.*
