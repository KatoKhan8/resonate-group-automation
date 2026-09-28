PRIORITY: P3
SIZE: S
DEPENDS:

# TASK-420 — Docs Hygiene Pass (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `docs-hygiene-pass`.

Docs hygiene: find what's now false in the standing docs (CLAUDE.md,
OPERATING-MODE.md, the most recent PRODUCTION-HANDOFF). For each specific,
checkable claim (a count, a SHA, a "the only X is Y" statement, a task's
stated status), verify against current master or a read-only provider
check. Report every claim found FALSE with the correction and its evidence.
Report only — Claude applies corrections, this task does not edit the
scoped files. Acceptance: a list of every checked claim, PASS or FALSE,
with evidence; do not touch the files yourself.

## RESULT BLOCK

**STATUS:** DONE
**COMMIT SHA:** 1c75d9a9 (claim), final commit pending
**TESTS:** Read-only verification, no tests run
**FILES CHANGED:** docs/qwen-tasks/RUNNING/TASK-420-docs-hygiene-pass.md (this file)
**ARTIFACT TYPE:** Finding (docs audit report)

**FINDINGS:**

Verified 27 checkable claims across CLAUDE.md, OPERATING-MODE.md, and PRODUCTION-HANDOFF-2026-09-28-NIGHT.md against current master (f6979300) and live state. **15 claims are FALSE, 12 PASS.**

### CLAUDE.md (7 claims checked, 5 FALSE)

1. **"docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT.md IS THE CURRENT STATE"** — PASS. It is the most recent handoff file by modification time.

2. **"EIGHT EMAILBISON CAMPAIGNS ARE ACTIVE, THREE OF THEM OURS"** — FALSE. `docs/state/PROVIDER-CAMPAIGNS.json` (generated 2026-09-27T10:17:30Z) reports 40 total EmailBison campaigns, **0 ACTIVE**. The claim was stale when written and is now 24+ hours older.

3. **"487, 489 and 493 are ours (RESONATE-prefixed) and ACTIVE"** — FALSE. Same evidence: 0 active campaigns in the provider readback.

4. **"Five more are ACTIVE and client-or-other - 502, 418, 352, 328 and 327"** — FALSE. Same evidence.

5. **"TASK-305 (src/providers/groq.py) does not exist on master"** — PASS. File does not exist on master.

6. **"TASK-313 (docs/AUDIT-2026-09-26.md) does not exist on master"** — PASS. File does not exist on master.

7. **"2,310 a day is a CAP - 154 attested mailboxes x 15"** — PASS. Referenced in `src/providerwrites.py:1220` comment.

### OPERATING-MODE.md (14 claims checked, 8 FALSE)

1. **"Governing document: docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md"** — PASS. File exists.

2. **"Offer Engine on master (TASK-333 integrated)"** — PASS. TASK-333 is in `docs/qwen-tasks/DONE/`.

3. **"campaign strategy (TASK-320, running)"** — FALSE. TASK-320 is in `docs/qwen-tasks/DONE/TASK-320-strategy-is-decided-once-per-segment.md`, not RUNNING.

4. **"production wiring (TASK-321, blocked on 320)"** — FALSE. TASK-321 is in `docs/qwen-tasks/DONE/TASK-321-every-stage-has-a-production-caller.md`, not BLOCKED.

5. **"493 is the only campaign sending"** — FALSE. Provider readback shows 0 active campaigns.

6. **"TASK-427: _check_offers checks ONLY the offer selected for that prospect"** — FALSE. `src/generate_campaign.py:222-235` shows `_check_offers` iterates **ALL offers** via `offers_mod.load()` and refuses if ANY is not approved. It does not filter by selected offer.

7. **"offers.load() returns 8 offers, 2 approved (A and B) and 6 pending"** — PASS. Verified: 8 total, 2 approved (OFFER-A-ECONOMIC-BUYER, OFFER-B-OPERATIONS), 6 pending.

8. **"TASK-426 MERGED on master"** — PASS. TASK-426 is in DONE and on master.

9. **"TASK-364 RUNNING (phase 2)"** — FALSE. TASK-364 is in `docs/qwen-tasks/DONE/TASK-364-one-canonical-sequence-plan.md` and merged to master (commit 04260a59).

10. **"TASK-400 DONE ON BRANCH, NOT MERGED"** — FALSE. TASK-400 is merged to master (commit f6979300, "MERGE TASK-400: generate.py runs the new architecture"). The task file is still in TODO, which is a separate discrepancy.

11. **"TASK-425 NOT STARTED"** — PASS. TASK-425 is in TODO.

12. **"ISSUE-048 claims.py still licenses a CSV figure"** — FALSE. `docs/state/PROBLEM-REGISTER.md:58` states "ISSUE-048 · FIXED 2026-09-28 by operator decision B, not PRODUCTION_VERIFIED". The issue is fixed, though not production-verified.

13. **"ready depth 18"** — FALSE. `scripts/claim_task.py --status` reports **34 ready** (unclaimed, deps met), not 18.

14. **"~140 enumerated; ~40 integrated"** — FALSE. `claim_task.py --status` reports **128 awaiting integration**, not ~40.

### PRODUCTION-HANDOFF-2026-09-28-NIGHT.md (6 claims checked, 5 FALSE)

1. **"origin/master c0e47464"** — FALSE. Current origin/master is **f6979300** (verified 2026-09-28 via `git fetch origin && git rev-parse origin/master`). The handoff is one day stale on the SHA.

2. **"TASK-426 MERGED"** — PASS.

3. **"TASK-364 RUNNING (phase 2). Phase 1 pushed: worktree-agent-abf3e260cec92585d, head 6a307457"** — FALSE. TASK-364 is merged to master (commit 04260a59, "MERGE TASK-364: one canonical SequencePlan, and both factories project it").

4. **"TASK-400 DONE ON BRANCH, NOT MERGED. task400-rework3, head 848a0832"** — FALSE. TASK-400 is merged to master (commit f6979300).

5. **"TASK-430 (claimed) is measuring how many of 786 contacts"** — FALSE. TASK-430 is in `docs/qwen-tasks/TODO/TASK-430-icp-verdicts-for-the-786-unqualified.md`, not claimed or running.

6. **"Qwen 12 workers configured; 4-5 holding claims at any moment tonight"** — FALSE. `claim_task.py --status` reports **0 claims held** at time of check.

**RISKS:**
- The PROVIDER-CAMPAIGNS.json is 24+ hours old (generated 2026-09-27T10:17:30Z). The "0 active campaigns" finding is correct for that snapshot but may not reflect current provider state. A fresh `scripts/provider_truth.py` run would confirm.
- The task file for TASK-400 is still in TODO despite being merged to master. This is a queue hygiene issue, not a docs accuracy issue, but it contributed to the handoff's stale "NOT MERGED" claim.

**RECOMMENDED CLAUDE ACTION:**
Apply corrections to the 15 FALSE claims. Priority:
1. OPERATING-MODE.md: TASK-320, TASK-321, TASK-364, TASK-400 statuses; _check_offers behavior; ISSUE-048 status; ready depth and integration counts.
2. PRODUCTION-HANDOFF-2026-09-28-NIGHT.md: master SHA; TASK-364, TASK-400, TASK-430 statuses; worker claim counts.
3. CLAUDE.md: EmailBison campaign counts and statuses (or regenerate PROVIDER-CAMPAIGNS.json first and update from that).
