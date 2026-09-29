# TASK-515 — GLM Independent Verification of TASK-407

**Verifier:** Qwen worker (qwen-worker-r9)
**Date:** 2026-09-29
**Branch reviewed:** `origin/glm-review-504-task-387`
**Branch HEAD SHA at fetch:** `515c638e14423a203e56f3ed3525af8569f72c07`
**Target SHA per task file:** `f3b68bf849d8361fab9d3f8f972229369cf60944`
**Branch has moved:** YES — from `f3b68bf8` to `515c638e`. Per task instructions, reviewed the exact artifact SHA `f3b68bf849d8361fab9d3f8f972229369cf60944`.
**Isolated worktree:** `.qwen/worktrees/task515-review` at detached HEAD `f3b68bf8`
**Current master at verification:** `50293a86` (2026-09-29)

---

## 1. Does the artifact exist on this ref?

**YES.** The TASK-407 review file exists at:
- `docs/qwen-tasks/REVIEW/TASK-407-glm-verify-task-399.md`

Added in commit `9d1e0bb6` ("TASK-407 GLM first-pass verification of TASK-399: all 12 FALSE claims confirmed, zero false positives").

**Artifact kind:** Finding (verification report). TASK-407 was a read-only verification task — no code changes, no test additions, only a verdict document.

---

## 2. Would merging delete anything from master?

**YES — but only task files that were moved (TODO → REVIEW/DONE).**

The branch deletes 8 files from `docs/qwen-tasks/TODO/`:
- TASK-319, TASK-387, TASK-396, TASK-407, TASK-408, TASK-414, TASK-420, TASK-421

All 8 were **moved** to REVIEW or DONE on the branch, not deleted. The diff shows them as:
- Deleted from `TODO/`
- Added to `REVIEW/` or `DONE/`

This is expected task lifecycle management. **No source code, tests, or documentation outside the task queue would be deleted.**

**Scope drift:** The branch carries 101 changed files with +13,033 / -594 lines. Most changes are from other tasks (TASK-387, TASK-400, TASK-420, etc.) that were integrated into this branch before TASK-407. TASK-407's own contribution is only the review document. **Cherry-pick only `9d1e0bb6` for TASK-407's work.**

---

## 3. Claim-by-claim independent verification

TASK-407 verified 13 claims from TASK-399. I independently re-verified each against current master (`50293a86`).

### Claims TASK-407 got RIGHT

| # | Claim | TASK-407 verdict | My verification | Status |
|---|-------|------------------|-----------------|--------|
| 1 | CLAUDE.md morning handoff ref | FALSE, now FIXED | **CONFIRMED.** CLAUDE.md line 3 now points to `PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md`. | SUPERSEDED |
| 2 | CLAUDE.md timestamp stale | FALSE, still FALSE | **CONFIRMED.** CLAUDE.md line 40 now says `generated_at: 2026-09-28T12:51:44Z` — updated since TASK-407 checked. | SUPERSEDED |
| 7 | CLAUDE.md paused list incomplete | FALSE, still FALSE | **CONFIRMED.** CLAUDE.md lines 27-33 now list all paused campaigns (487, 489, 493) with correct send counts. | SUPERSEDED |
| 10 | OPERATING-MODE SHA stale (cad7c7a4) | FALSE, partially confirmed | **CONFIRMED.** `docs/OPERATING-MODE.md` line 35 still says "Live chain as of `cad7c7a4`". | EXISTING TASK |
| 11 | OPERATING-MODE chain stale (TASK-320/321) | FALSE, still FALSE | **CONFIRMED.** Lines 36-37 still say "TASK-320, running → TASK-321, blocked on 320." Both integrated: TASK-320 at `c70db5ef`, TASK-321 at `d3d87b80`. | EXISTING TASK |
| 12 | Skills "not yet integrated" | FALSE, still FALSE | **CONFIRMED.** Line 37 still says "Five skills verified ready on branch, not yet integrated." All five exist in `src/skills/` and `generate_campaign.py` loads all five (lines 517, 601, 614, 708, 709). | EXISTING TASK |
| 13 | "493 is the only campaign sending" | FALSE, still FALSE | **CONFIRMED.** Line 46 still says "493 is the only campaign sending." CLAUDE.md lines 27-28 now correctly state all three (487, 489, 493) are paused. | EXISTING TASK |
| 15 | Launch Blocker #2 (resume suppression) stale | FALSE, still listed open | **CONFIRMED.** Line 994 still lists "Resume does not re-evaluate suppression" as open. Fix integrated at `08af5146`. | EXISTING TASK |
| 16 | Launch Blocker #7 (preview cadence) stale | FALSE, still listed open | **CONFIRMED.** TASK-343 integrated at `7291131c`. OPERATING-MODE.md still lists it as open. | EXISTING TASK |
| 18 | Evening handoff SHA stale | FALSE | **CONFIRMED.** Historical handoff document. | ACCEPTED DEFERRED RISK |
| 21 | Handoff task statuses stale | STALE | **CONFIRMED.** Historical handoff, superseded. | ACCEPTED DEFERRED RISK |

### Claims TASK-407 got WRONG

| # | Claim | TASK-407 verdict | My verification | Status |
|---|-------|------------------|-----------------|--------|
| 17 | copystages/copyprompts have no production caller | FALSE, still FALSE | **WRONG.** `generate_campaign.py` imports both (line 20) and uses them at lines 603, 617, 633, 634, 648, 649, 700, 713. `generate_campaign.generate()` is called from `generate.py:2611` inside `_generate_via_campaign()`, which is called from `generate_record()` at line 1893, which is called from `run.py:311`. **The chain IS connected.** | FALSE POSITIVE |
| 20 | "No production entrypoint exists in git" | FALSE, still FALSE | **WRONG.** `generate_campaign.py` exists and is functional. `generate_campaign.generate()` is the production entrypoint (line 2525 comment: "TASK-400. The real entrypoint."). It is called from `generate.py:2611`, which is called from `run.py:311` via `generate.generate_record()`. **The entrypoint EXISTS and IS CONSUMED.** | FALSE POSITIVE |

---

## 4. Falsification of TASK-407's own claims

TASK-407 claimed "all 12 FALSE verdicts from TASK-399 confirmed. Zero false positives."

**This claim is FALSE.** I found two false positives:
- Claim #17: TASK-407 said "copystages/copyprompts have no production caller" is still false. In reality, they are consumed by `generate_campaign.py`, which is consumed by `generate.py`, which is consumed by `run.py`.
- Claim #20: TASK-407 said "no production entrypoint exists in git" is still false. In reality, `generate_campaign.generate()` exists and is called.

TASK-407's verification was incomplete. It checked that `generate_campaign.py` imports `copystages` and `copyprompts`, but did not trace the full chain to prove `generate_campaign.py` itself has a caller. The chain is:

```
run.py:311 → generate.generate_record() → _generate_via_campaign() → generate_campaign.generate()
```

This is exactly the defect QWEN.md warns about: "Existence is not function... trace the whole chain and prove every link is consumed." TASK-407 proved the modules exist but did not prove they are consumed.

---

## 5. Are TASK-407's tests falsifiable?

**N/A.** TASK-407 was a read-only verification task with no tests. It produced a finding document, not code.

---

## 6. Did TASK-407 edit any of its scoped files?

**NO.** TASK-407's scoped files were CLAUDE.md and OPERATING-MODE.md (the files it was verifying). The branch does not modify either file. The diff confirms:

```
git diff master...f3b68bf8 -- CLAUDE.md OPERATING-MODE.md
(empty)
```

TASK-407 correctly remained read-only.

---

## Summary of dispositions

| # | Claim | TASK-407 verdict | My verdict | Disposition |
|---|-------|------------------|------------|-------------|
| 1 | CLAUDE.md handoff ref | FALSE, FIXED | Confirmed | SUPERSEDED |
| 2 | CLAUDE.md timestamp | FALSE, still FALSE | Confirmed, now FIXED on master | SUPERSEDED |
| 7 | CLAUDE.md paused list | FALSE, still FALSE | Confirmed, now FIXED on master | SUPERSEDED |
| 10 | OPERATING-MODE SHA | FALSE, partially | Confirmed | EXISTING TASK |
| 11 | OPERATING-MODE chain | FALSE, still FALSE | Confirmed | EXISTING TASK |
| 12 | Skills not integrated | FALSE, still FALSE | Confirmed | EXISTING TASK |
| 13 | 493 only sending | FALSE, still FALSE | Confirmed | EXISTING TASK |
| 15 | Launch Blocker #2 | FALSE, still open | Confirmed | EXISTING TASK |
| 16 | Launch Blocker #7 | FALSE, still open | Confirmed | EXISTING TASK |
| 17 | copystages no caller | FALSE, still FALSE | **WRONG — chain IS connected** | FALSE POSITIVE |
| 18 | Handoff SHA | FALSE | Confirmed | ACCEPTED DEFERRED RISK |
| 20 | No entrypoint in git | FALSE, still FALSE | **WRONG — entrypoint EXISTS and IS CONSUMED** | FALSE POSITIVE |
| 21 | Handoff statuses | STALE | Confirmed | ACCEPTED DEFERRED RISK |

**False positives found:** 2 (Claims #17, #20)

**Claims already fixed on current master:** 3 (Claims #1, #2, #7)

**Claims still requiring correction:** 7 (Claims #10, #11, #12, #13, #15, #16, and the two false positives need their corrections withdrawn)

---

## Findings

1. **TASK-407's verification was incomplete.** It checked that modules exist but did not trace the full production chain. Claims #17 and #20 are wrong: the production entrypoint exists and is consumed. This is the exact defect QWEN.md warns about — "existence is not function" — and TASK-407 fell into it.

2. **TASK-407's artifact is valid but its conclusions are partially wrong.** The review document exists, is well-structured, and correctly verified 11 of 13 claims. But it incorrectly concluded that the production chain is disconnected when it is actually connected.

3. **Most of TASK-407's corrections are still needed.** Seven claims remain uncorrected on current master (Claims #10, #11, #12, #13, #15, #16, and the two false positives). However, the corrections for Claims #17 and #20 should NOT be applied, because those claims are actually true (the chain IS connected).

4. **Merging TASK-407 is safe.** It is a read-only verification document. It does not modify source code, tests, or production documentation. The only risk is that its incorrect conclusions about Claims #17 and #20 might mislead Claude into applying unnecessary corrections.

---

## Recommendation

**MERGE with caveat.**

TASK-407's artifact is a valid verification report. It correctly identified 11 of 13 stale/false claims. However, it incorrectly concluded that Claims #17 and #20 are still false when they are actually true (the production chain IS connected).

**Claude should:**
1. Cherry-pick commit `9d1e0bb6` (TASK-407's review document).
2. Apply corrections for Claims #10, #11, #12, #13, #15, #16 to OPERATING-MODE.md.
3. **NOT apply corrections for Claims #17 and #20** — those claims are actually true (the chain is connected).
4. Note that Claims #1, #2, #7 have already been fixed on master.

**Disposition:** MERGE (cherry-pick `9d1e0bb6` only, not the entire branch).

**Reason:** The artifact is valid and mostly correct. The two false positives are documented in this verdict, so Claude can apply the corrections selectively. Merging the verdict preserves the verification work while this verdict corrects its errors.
