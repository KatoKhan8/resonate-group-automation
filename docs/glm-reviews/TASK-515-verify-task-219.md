# TASK-515 — GLM Independent Verification of TASK-407

**Reviewed task:** TASK-407 — GLM first-pass verification of TASK-399 (docs hygiene)  
**Reviewed branch:** origin/glm-review-504-task-387  
**Target SHA:** f3b68bf849d8361fab9d3f8f972229369cf60944  
**Branch HEAD at review time:** 515c638e14423a203e56f3ed3525af8569f72c07 (MOVED)  
**Current master:** 2bf7b8a571fe11bada4f56fbebeee768ab1e78a8  
**Review date:** 2026-10-03  
**Reviewer:** Qwen (independent verification layer)

---

## Branch HEAD movement notice

The task file named SHA `f3b68bf849d8361fab9d3f8f972229369cf60944`. Current branch HEAD is `515c638e14423a203e56f3ed3525af8569f72c07`. Per the task's own rule: reviewing the named SHA anyway, because that is the artifact this verdict is about.

---

## Executive Summary

**DISPOSITION: CLOSE**

TASK-407 is a read-only verification report that confirmed 12 FALSE claims from TASK-399 against master as of 2026-09-28. The artifact exists on the target ref (161 lines in `docs/qwen-tasks/REVIEW/TASK-407-glm-verify-task-399.md`). The verification was correct at the time it was performed. However:

1. **The branch carries massive scope drift** — 101 files / 13,033 insertions from dozens of other tasks (TASK-387, TASK-400, TASK-420, TASK-421, TASK-427, TASK-385, and ~20 other GLM verdicts). TASK-407 itself changed only 2 files (the task file moving TODO → REVIEW).
2. **Several of TASK-407's findings are now superseded** by later work on master. Of 13 claims verified, at least 4 have been corrected on master since the review, and one claim (#17/#20 about generate_campaign having no caller) is now factually wrong.
3. **The artifact is a finding, not code.** It has no production callers because it is not code — it is a verification report. Merging it would add a historical document that is now partially stale.
4. **Merging would delete 8 TODO task files** (moved to REVIEW/DONE on the branch), which is expected queue movement but represents state that has likely been superseded.

**Recommendation: CLOSE.** The verification was correct at the time. The branch is not mergeable due to massive scope drift. The findings have been partially superseded by later corrections on master. No action is needed from this artifact.

---

## Detailed Verification

### 1. Does the artifact exist on this ref?

**YES.** `docs/qwen-tasks/REVIEW/TASK-407-glm-verify-task-399.md` exists at SHA f3b68bf, 161 lines.

```
git show f3b68bf:docs/qwen-tasks/REVIEW/TASK-407-glm-verify-task-399.md | wc -l
# Output: 161
```

The artifact was produced by commit `9d1e0bb65` ("TASK-407 GLM first-pass verification of TASK-399: all 12 FALSE claims confirmed, zero false positives"). That commit changed exactly 2 files: the task file (TODO → REVIEW, 161 lines added) and removed the TODO version (29 lines deleted).

### 2. Existence is not function — is the artifact consumed?

**NOT APPLICABLE.** The artifact is a finding/report, not code. It has no production callers because it is not designed to have any. Its purpose was to inform Claude's correction pass on CLAUDE.md and OPERATING-MODE.md. Whether Claude acted on it is a separate question.

### 3. Falsification of the result's own claims

I independently verified each of TASK-407's 13 claim verdicts against current master (`2bf7b8a5`):

| # | Claim | TASK-407 verdict | Current master state | Verification |
|---|-------|------------------|---------------------|--------------|
| 1 | CLAUDE.md handoff ref | FALSE → SUPERSEDED | Now says `HANDOFF-2026-10-01-LIVE.md` | **Correct at time, further superseded** |
| 2 | CLAUDE.md timestamp | FALSE, still FALSE | Now says `2026-09-28T12:51:44Z` | **SUPERSEDED — fixed since review** |
| 7 | CLAUDE.md paused list | FALSE, still FALSE | Now says "NONE OF OUR CAMPAIGNS IS SENDING. 487, 489 AND 493 ARE ALL PAUSED" | **SUPERSEDED — rewritten since review** |
| 10 | OPERATING-MODE SHA stale | FALSE, still stale | Line 35 still says `cad7c7a4` | **CONFIRMED STILL STALE** |
| 11 | OPERATING-MODE chain stale | FALSE, still FALSE | Lines 35-37 still say "TASK-320, running → TASK-321, blocked" | **CONFIRMED STILL STALE** |
| 12 | Skills "not yet integrated" | FALSE, still FALSE | Line 37 still says "Five skills verified ready on branch, not yet integrated" | **CONFIRMED STILL STALE** |
| 13 | "493 only sending" | FALSE, still FALSE | OPERATING-MODE line 46 still says "493 is the only campaign sending" — but CLAUDE.md now says all three paused | **PARTIALLY SUPERSEDED — OPERATING-MODE still wrong, CLAUDE.md corrected** |
| 15 | Launch Blocker #2 stale | FALSE, still listed open | Commit `08af5146` IS on master. OPERATING-MODE line 1226 still lists it as open | **CONFIRMED — fix integrated but doc not updated** |
| 16 | Launch Blocker #7 stale | FALSE, still listed open | Commit `7291131c` IS on master. OPERATING-MODE line 1243 still lists it as open | **CONFIRMED — fix integrated but doc not updated** |
| 17 | copystages no caller | FALSE | `generate_campaign.generate()` called at `src/generate.py:2888` | **NOW WRONG — generate_campaign has callers** |
| 18 | Handoff SHA stale | FALSE → DEFERRED RISK | Historical document | **Still valid as DEFERRED RISK** |
| 20 | No entrypoint in git | FALSE | `src/generate_campaign.py` exists and IS called by `src/generate.py` | **NOW WRONG — entrypoint exists AND has callers** |
| 21 | Handoff task statuses | STALE → DEFERRED RISK | Historical document | **Still valid as DEFERRED RISK** |

**Key finding:** TASK-407's claims #17 and #20 were correct when checked (master `37c12335`) but are now factually wrong on current master. `generate_campaign.generate()` is called at `src/generate.py:2888`, and `src/generate.py` is the production entrypoint that calls it. The chain `src/run.py → src/generate.py → src/generate_campaign.py` is now wired.

### 4. Are the tests falsifiable?

**NOT APPLICABLE.** TASK-407 produced no tests. It is a read-only verification report.

### 5. Would merging delete anything?

**YES — 8 task files would be deleted from TODO/:**

```
docs/qwen-tasks/TODO/TASK-319-five-skills-as-executable-sops.md
docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md
docs/qwen-tasks/TODO/TASK-396-training-pair-capture-check.md
docs/qwen-tasks/TODO/TASK-407-glm-verify-task-399.md
docs/qwen-tasks/TODO/TASK-408-glm-verify-task-319.md
docs/qwen-tasks/TODO/TASK-414-spend-report-wiring-check.md
docs/qwen-tasks/TODO/TASK-420-docs-hygiene-pass.md
docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md
```

These are queue movements (TODO → REVIEW/DONE) and are expected. However, the branch also carries massive production code changes from other tasks that would land simultaneously.

### 6. Scope drift

**CRITICAL.** The branch carries 101 files changed, 13,033 insertions, 594 deletions vs master. TASK-407's own contribution is 2 files (161 lines added, 29 deleted). The remaining 99 files / ~12,800 lines are from:

- TASK-387 (provider write-back demo test, 257 lines)
- TASK-400 (generate.py campaign pipeline wiring, ~2,500 lines across src/ and tests/)
- TASK-420 (docs hygiene pass)
- TASK-421 (suppression list audit)
- TASK-427 (offer selection)
- TASK-385 (pool_status.py, 422 lines)
- ~20 other GLM verdict documents
- Multiple test files (test_task400_rework2.py: 992 lines, test_task400_rework3.py: 530 lines, test_only_the_last_subject_may_claim_finality.py: 550 lines, test_only_the_selected_offer_is_validated.py: 417 lines)
- Production code changes in src/generate.py (721+ lines), src/generate_campaign.py (517+ lines), src/copylint.py, src/approve.py, src/run.py, src/bisonfactory.py, src/heyreachfactory.py

**This branch is not mergeable as a unit.** Only TASK-407's own artifact (the REVIEW task file) could be cherry-picked, and even that is now partially stale.

---

## Dispositions

| Finding | Disposition | Evidence |
|---------|-------------|----------|
| TASK-407 artifact exists | **EXISTS** | `git show f3b68bf:docs/qwen-tasks/REVIEW/TASK-407-glm-verify-task-399.md` — 161 lines |
| TASK-407's verification was correct at time | **CONFIRMED** | 11 of 13 claims verified correct against master `37c12335` as of 2026-09-28 |
| Claims #17, #20 now wrong | **SUPERSEDED** | `generate_campaign.generate()` called at `src/generate.py:2888` on current master |
| Claims #2, #7 superseded | **SUPERSEDED** | CLAUDE.md timestamp updated, paused list rewritten on current master |
| Claims #10-13, #15-16 still valid | **EXISTING TASK** | OPERATING-MODE.md lines 35-37, 46, 1226, 1243 still stale on current master |
| Branch scope drift | **BLOCKER** | 101 files / 13,033 lines from dozens of tasks; not mergeable as unit |
| No production code from TASK-407 | **CONFIRMED** | TASK-407 changed only the task file (TODO → REVIEW) |

---

## Recommendation

**CLOSE.**

Reasons:
1. TASK-407's artifact is a finding (verification report), not code. It has served its purpose — confirming TASK-399's FALSE claims before Claude's correction pass.
2. The branch is not mergeable due to massive scope drift (101 files from dozens of tasks).
3. Several findings are now superseded by later work on master.
4. The remaining stale claims (#10-13, #15-16 in OPERATING-MODE.md) are known and can be addressed directly without reference to this artifact.
5. No production code was added or changed by TASK-407. There is nothing to integrate.

The verification was honest and correct at the time. Zero false positives were found (TASK-407 did not waste Claude's correction pass with false alarms). The artifact is a valid historical record of the docs-hygiene state as of 2026-09-28.
