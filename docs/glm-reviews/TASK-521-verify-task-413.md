# TASK-521 — GLM Independent Verification of TASK-413

## Review metadata

| Field | Value |
|---|---|
| Target task | TASK-413 (HeyReach Seat Cap Check) |
| Target branch | `origin/qwen-worker-11-task314` |
| Branch HEAD SHA | `ddc0bc816fed25b327cbe070d0597ba03ae2b67e` |
| Verified SHA | `ddc0bc816fed25b327cbe070d0597ba03ae2b67e` — confirmed via `git rev-parse` |
| Review worktree | `.qwen/worktrees/review-521` (detached HEAD at target SHA) |
| Reviewer | GLM (independent, read-only) |
| Date | 2026-09-29 |
| Filename note | Task file says `TASK-521-verify-task-219.md`; corrected to `task-413` — the target is TASK-413 |

## 1. Does the artifact exist, and does it do what the result block claims?

**Artifacts on this ref — VERIFIED:**

| Artifact | Exists | Path |
|---|---|---|
| Seat cap check script | YES | `scripts/task413_seat_cap_check.py` (190 lines) |
| API probe script | YES | `scripts/task413_seat_cap_probe.py` (76 lines) |
| Per-seat JSON output | YES | `docs/state/TASK-413-SEAT-CAP-CHECK.json` (708 lines, 41 seats) |
| Refreshed SENDER-CAPACITY.json | YES | `docs/state/SENDER-CAPACITY.json` (timestamp 2026-09-27T11:54:25) |
| Task file in REVIEW | YES | `docs/qwen-tasks/REVIEW/TASK-413-heyreach-seat-cap-check.md` |

**Core claim: "No seat is at or over 90% of its daily connection-request cap."**

VERIFIED for connection requests and messages. The JSON data confirms:
- Highest connection-request usage: seat 212356 at 27% (11/40)
- Highest message usage: seat 125748 at 22% (9/40)
- Zero seats at or over 90% for either metric

**However, the result block overclaims.** It states: "NO SEAT IS AT OR OVER 90% OF ANY CAP." The artifact's own JSON data contradicts this — 9 seats are at or over 90% of their **profile view cap**, one at 100%:

| Seat | Profile Views | Cap | Percentage |
|---|---|---|---|
| 116988 | 40 | 40 | **100.0%** |
| 116989 | 39 | 40 | **97.5%** |
| 119588 | 38 | 40 | **95.0%** |
| 125748 | 38 | 40 | **95.0%** |
| 201978 | 38 | 40 | **95.0%** |
| 116968 | 37 | 40 | **92.5%** |
| 129082 | 37 | 40 | **92.5%** |
| 208253 | 37 | 40 | **92.5%** |
| 116973 | 36 | 40 | **90.0%** |

The script collects profile view data (`pv_cap`, `pv_actual`, `pv_pct`) and writes it to the JSON, but the FINDINGS section only checks connection-request and message caps. Profile views are silently excluded. The JSON output has `seats_flagged_connection` and `seats_flagged_message` but no `seats_flagged_profile_view` field.

**The task asked to "Report any seat at or over 90% as a finding."** The task text specifically mentions "connection cap" but the result block's "OF ANY CAP" claim extends the scope to all caps and is factually wrong.

### Mitigating context

The task text says "connection cap" specifically, and the connection-request finding is correct. Profile views are a different resource with different operational implications. The omission may be a reasonable scoping decision that was not documented as such.

## 2. Existence is not function — production callers

**Zero production callers.** `grep -rn "task413" src/` returns nothing. The scripts are standalone CLI utilities in `scripts/` that are not imported, scheduled, or invoked by any production code.

For a one-time read-only audit task, this is acceptable — the script is a measurement tool, not a pipeline component. The result block correctly identifies it as "finding + code (the script is reusable)."

**Disposition: DISCONNECTED but acceptable for task kind.** A reusable audit script does not need production wiring to deliver value. The finding (no seat over 90% connection cap) is the deliverable, not a monitored metric.

## 3. Falsification of result claims

### Connection-request cap claim: NOT FALSIFIED
The JSON data supports the claim. 41 seats read, highest at 27%. Sunday read, consistent with reduced weekend activity.

### "ANY CAP" claim: FALSIFIED
The artifact's own data shows 9 seats at or over 90% profile view cap. The claim is wrong.

### Script correctness for connection/message caps: VERIFIED
- Uses `accountLimits.connectioRequestMax` and `accountLimits.messageLimitMax` for configured caps (note: HeyReach API has a typo `connectioRequestMax` — the script correctly reads this as-is)
- Uses `byDayStats[today].connectionsSent` and `byDayStats[today].messagesSent` for actual usage
- Correctly skips non-functional seats (INACTIVE, AUTH_INVALID)
- Percentage calculation is correct: `(actual / cap) * 100`
- Threshold comparison uses `>= THRESHOLD * 100` (90.0), which is correct

### Data integrity: PARTIALLY VERIFIED
I cannot replay the live provider reads (read-only review, no provider calls). The JSON structure is internally consistent: 41 seats, 33 healthy, 1 auth_invalid, 7 inactive — matching the result block's counts. The per-seat data in the table matches the JSON records.

## 4. Are the tests falsifiable?

**N/A** — TASK-413 is a read-only audit with no src/ code changes and no tests. The result block correctly states "TESTS: N/A — read-only provider audit, no code change to src/."

The script could silently produce wrong numbers if the HeyReach API response shape changed, but this is a runtime concern, not a test-design concern.

## 5. Would merging delete anything?

**Three task files are deleted** (moved from TODO to REVIEW/RUNNING):
- `docs/qwen-tasks/TODO/TASK-314-where-the-heyreach-steps-are-lost.md` → moved to REVIEW
- `docs/qwen-tasks/TODO/TASK-398-suppression-list-audit.md` → moved to REVIEW
- `docs/qwen-tasks/TODO/TASK-413-heyreach-seat-cap-check.md` → moved to REVIEW

These are task lifecycle moves, not data deletions. No production code, configuration, or documentation is deleted.

**SENDER-CAPACITY.json is modified** (timestamp refresh + `active_campaigns` count updates from 8→9 and `connection_requests` capacity from 1054→1079). Master's version is from 2026-09-21; the branch's is from 2026-09-27. This is a strictly newer read.

## 6. Scope drift

**SIGNIFICANT.** The branch carries work from at least 7 tasks beyond TASK-413:

| Task | Files | Status |
|---|---|---|
| TASK-314 | `tests/test_no_cadence_step_is_silently_dropped.py`, `tests/test_step_counts_agree_while_the_keys_do_not.py`, `src/sequenceplan.py` | On this branch, not on master |
| TASK-398 | `docs/qwen-tasks/REVIEW/TASK-398-suppression-list-audit.md` | On this branch |
| TASK-296 | `scripts/qa/check_campaign_bison.py`, `scripts/qa/__init__.py`, `docs/QA-CAMPAIGN-BISON-2026-09-25.md` | On this branch |
| TASK-364 | `src/bisonfactory.py`, `src/heyreachfactory.py`, tests | On this branch, master has divergent newer versions |
| TASK-410 | `docs/qwen-tasks/TODO/TASK-410-glm-verify-task-400-critical-path.md` | On this branch |
| stage_work_to_host | `scripts/stage_work_to_host.sh` | On this branch |
| TASK-423/424/425 | (via merge commit) | On this branch |

**The src/ files are a conflict risk.** All three (`src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`) have different blobs on master and the branch, with master having newer changes from TASK-913, TASK-908, and others. Merging the full branch would require conflict resolution.

**Cherry-pick path for TASK-413 only:** Commits `73eee6e7`, `da084739`, `3508b7d0` are self-contained and touch only scripts/, docs/state/, and task files. They can be cherry-picked without touching src/.

## Findings

### Finding 1: Profile view cap omission (MEDIUM)

**Summary:** The script collects profile view data and the JSON records it, but the findings section and result block silently exclude profile views. Nine seats are at or over 90% of their profile view cap (one at 100%), contradicting the "OF ANY CAP" claim.

**Category:** correctness / reporting completeness

**Evidence:** `docs/state/TASK-413-SEAT-CAP-CHECK.json` — seats 116988 (100%), 116989 (97.5%), 119588/125748/201978 (95%), 116968/129082/208253 (92.5%), 116973 (90%).

**Disposition:** The task text says "connection cap" specifically, so the core deliverable is met. But the result block's "OF ANY CAP" claim is factually wrong and should be corrected to "OF ANY CONNECTION-REQUEST OR MESSAGE CAP."

### Finding 2: No production wiring (LOW — acceptable for task kind)

**Summary:** The scripts are standalone CLI utilities with zero production callers.

**Category:** wiring / consumption

**Evidence:** `grep -rn "task413" src/` returns nothing. No scheduler, no import, no caller.

**Disposition:** Acceptable for a one-time audit. The finding is the deliverable, not a monitored metric. If this should become a recurring check, it needs scheduling and integration.

### Finding 3: Branch scope drift (INFORMATIONAL)

**Summary:** The branch carries 23 changed files from 7+ tasks. Only 5 files belong to TASK-413.

**Category:** merge hygiene

**Evidence:** `git diff master...ddc0bc81 --stat` shows 23 files, +4441/-200 lines. TASK-413 commits touch 5 files.

**Disposition:** Cherry-pick the TASK-413 commits (`73eee6e7`, `da084739`, `3508b7d0`) rather than merging the full branch.

## Recommendation

**CLOSE — with a correction to the result block.**

The core finding is correct: no seat is at or over 90% of its connection-request cap (the task's primary ask). The script works, the data is internally consistent, and the JSON is a reusable artifact.

The profile view omission is real but does not invalidate the connection-request finding. The result block should be corrected from "NO SEAT IS AT OR OVER 90% OF ANY CAP" to "NO SEAT IS AT OR OVER 90% OF ITS CONNECTION-REQUEST OR MESSAGE CAP" and should note the profile view data as an observed side-finding.

The branch carries significant scope drift from other tasks. Cherry-pick only the TASK-413 commits if the artifacts are wanted on master.

### Disposition summary

| Finding | Severity | Disposition |
|---|---|---|
| Profile view cap omission | MEDIUM | Result block correction needed |
| No production wiring | LOW | Acceptable for task kind |
| Branch scope drift | INFORMATIONAL | Cherry-pick, don't merge |

**Final verdict: CLOSE.** The task's core question ("Is any HeyReach seat over its connection cap?") is correctly answered. The overclaim in the result block is a documentation defect, not a measurement defect. The artifacts are useful and the script is reusable. No merge is recommended — cherry-pick if desired.
