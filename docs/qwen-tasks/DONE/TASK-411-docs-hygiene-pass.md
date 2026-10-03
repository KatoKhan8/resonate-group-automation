PRIORITY: P3
SIZE: S
DEPENDS:

# TASK-411 — Docs Hygiene Pass (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `docs-hygiene-pass`.

Docs hygiene: find what's now false in the standing docs (CLAUDE.md,
OPERATING-MODE.md, the most recent PRODUCTION-HANDOFF). For each specific,
checkable claim (a count, a SHA, a "the only X is Y" statement, a task's
stated status), verify against current master or a read-only provider
check. Report every claim found FALSE with the correction and its evidence.
Report only — Claude applies corrections, this task does not edit the
scoped files. Acceptance: a list of every checked claim, PASS or FALSE,
with evidence; do not touch the files yourself.

---

## RESULT BLOCK — TASK-411

**STATUS:** DONE
**ARTIFACT KIND:** finding (report-only task, no code changes)
**COMMIT SHA:** (pending)
**TESTS:** N/A — read-only analysis, no code changed
**FILES CHANGED:** only this task file (moved TODO → RUNNING → DONE)
**MASTER HEAD:** `2bf7b8a571fe11bada4f56fbebeee768ab1e78a8` (== `origin/master`, verified by fetch)

---

### CLAIMS CHECKED — CLAUDE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | `docs/HANDOFF-2026-10-01-LIVE.md IS THE CURRENT STATE` | **PASS** | File exists, is the most recent handoff by date |
| 2 | `487, 489 AND 493 ARE ALL PAUSED` | **PASS** | `PROVIDER-CAMPAIGNS.json` (generated 2026-09-30): all three status=paused |
| 3 | `487 paused, 10 leads` | **PASS** | JSON: bison_campaign_id=487, status=paused, lead_count=10 |
| 4 | `489 paused, 5 leads` | **PASS** | JSON: bison_campaign_id=489, status=paused, lead_count=5 |
| 5 | `493 paused, 22 leads` | **PASS** | JSON: bison_campaign_id=493, status=paused, lead_count=22 |
| 6 | `still ACTIVE: 327, 328, 352, 418` | **PASS** | JSON: all four status=active. No other EmailBison campaign is active |
| 7 | EmailBison `40 of 40` campaigns | **PASS** | JSON: 40 EmailBison campaigns total (4 active, 13 paused, 10 completed, 9 archived, 4 draft) |
| 8 | `274, 327, 328 and 352` declared internal | **PASS** | `config/internal-campaigns.txt` lists all four |
| 9 | `generated_at: 2026-09-28T12:51:44Z` for PROVIDER-CAMPAIGNS.json | **FALSE** | Actual `generated_at`: `2026-09-30T20:40:42+00:00`. The file was regenerated ~2 days later. The campaign counts/statuses are consistent, but the timestamp in CLAUDE.md is stale |
| 10 | TASK-305 artifact `src/providers/groq.py` does not exist on master | **PASS** | `git show master:src/providers/groq.py` → fatal: does not exist |
| 11 | TASK-307 artifact (ContactOut linkedin route) does not exist on master | **PASS** | No LinkedIn-specific function in `src/providers/contactout.py`; no `linkedin` function definition found |
| 12 | TASK-313 artifact `docs/AUDIT-2026-09-26.md` does not exist on master | **PASS** | `git show master:docs/AUDIT-2026-09-26.md` → fatal: does not exist |
| 13 | `912 sends` provider-confirmed | **UNVERIFIABLE** | Requires live provider read; no stored evidence in this worktree |
| 14 | `1,555 rows in sending_paused`, `503/504/505 alone hold 1,313` | **UNVERIFIABLE** | `work/campaigns.jsonl` is gitignored and absent from this worktree |
| 15 | `0 of 3,005 stored approvals are still valid` | **UNVERIFIABLE** | No spend/approval ledger file found in docs/state/; requires live work/ access |

### CLAIMS CHECKED — OPERATING-MODE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 16 | `493 is the only campaign sending and stays as it is` (PRODUCTION FREEZE section) | **FALSE** | 493 is PAUSED per PROVIDER-CAMPAIGNS.json (2026-09-30) and per CLAUDE.md ("paused by the operator, by hand, in EmailBison, on 2026-09-28"). This OPERATING-MODE line was written before the pause and was never updated. It directly contradicts CLAUDE.md's explicit statement |
| 17 | `Live chain as of cad7c7a4: Offer Engine on master (TASK-333 integrated)` | **PASS** | `cad7c7a44` exists on master; `src/offers.py` exists; TASK-333 is in DONE/ |
| 18 | `campaign strategy (TASK-320, running)` | **FALSE** | TASK-320 is in `docs/qwen-tasks/DONE/`, not running |
| 19 | `production wiring (TASK-321, blocked on 320)` | **FALSE** | TASK-321 is in `docs/qwen-tasks/DONE/`, not blocked |
| 20 | `Five skills verified ready on branch, not yet integrated` | **FALSE** | All five skill files exist on master in `src/skills/`. However, 4 of 5 have zero callers outside their own file (`account_research`, `campaign_strategy`, `linkedin_writing`, `signal_verification`). `cold_email_writing` is imported by `lint.py`. So they are ON MASTER but mostly DISCONNECTED — "not yet integrated" is partially true for 4/5 but the "on branch" framing implies they are not on master, which is wrong |
| 21 | `TASK-400` listed in critical-path execution order | **FALSE (stale)** | TASK-400 is in `docs/qwen-tasks/TODO/` — not yet done, but the execution order lists it as a step between TASK-364 rework (DONE) and GLM verification |
| 22 | `TASK-364 rework` in critical-path order | **PASS** | TASK-364 is in DONE/ |
| 23 | `TASK-426` first in execution order | **PASS** | TASK-426 is in DONE/ |
| 24 | `bisonfactory.stage()` dry-run skips copylint and sequencegate (`This is currently violated`) | **FALSE (fixed)** | Code at lines 115-169 shows both `_refuse_copylint` and `_refuse_sequence_gate` now execute BEFORE the dry-run return. Comments explicitly state "AND IT RUNS ON A DRY RUN" for both gates |
| 25 | `COHORT_SYSTEM` has ZERO references outside `copyprompts.py` | **PASS** | grep: all 4 occurrences are in `src/copyprompts.py`; zero in `tests/`, `scripts/`, or any other `src/` file |
| 26 | `34-point acceptance scenario in §32` | **PASS** | `docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md` §32 has exactly 34 numbered items |
| 27 | `sending.live is off for productive` | **PASS (with caveat)** | `killswitch.workspace_state('productive')` returns `{'sending': False, 'why': 'no such workspace: productive'}`. The effect (False) matches the claim, but the workspace lookup fails — the killswitch cannot find the workspace at all, which is a different reason than intended |
| 28 | `274, 327, 328, 352` internal (OPERATING-MODE, Croatian section) | **PASS** | Matches `config/internal-campaigns.txt` |
| 29 | `1,555 rows in sending_paused` (Croatian section) | **UNVERIFIABLE** | `work/campaigns.jsonl` absent from this worktree |
| 30 | `0 od 3.005 odobrenja` still valid | **UNVERIFIABLE** | Same — requires live work/ access |

### CLAIMS CHECKED — HANDOFF-2026-10-01-LIVE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 31 | `master d98c83ce4625cbbaef7d55894333bd2b3412839e` | **FALSE (stale)** | Current master: `2bf7b8a571fe11bada4f56fbebeee768ab1e78a8`. The handoff was written at session start and is now ~3 days and many commits behind |
| 32 | `Credits limit 200, 90 spent` | **UNVERIFIABLE** | No spend ledger file in docs/state/; requires live provider read |
| 33 | `src/personas.py:127 default_angle(config, persona, family=None)` | **PASS** | `inspect.getsourcelines` confirms line 127 and exact signature |
| 34 | `exactly one on the productive.io domain — the Ivan Mamic seat` (HeyReach) | **UNVERIFIABLE** | Requires live HeyReach provider read |
| 35 | `41 seats, 33 active with valid auth` | **UNVERIFIABLE** | Requires live HeyReach provider read |
| 36 | Branches in "LANES IN FLIGHT" table | **MOSTLY FALSE** | Only `origin/task-honest-crawler-ua` exists. Five of six branches are gone: `task-l34-deterministic-angle`, `task-linkedin-seat-binding`, `task-internal-campaign-guard`, `task-internal-campaign-learnings`, `task-recontact-cold-lead` — all absent from remote |
| 37 | `test_generate` pre-existing defects (3 failures) | **PASS (pattern), FALSE (numbers)** | All 3 defects still present: `KeyError: 'rowan-blake'`, and two `AssertionError`. But the counts changed: handoff says `2 != 1`, actual is `9 != 1`. The defect pattern is the same (retry_prompts count wrong) but the specific numbers are stale |
| 38 | `TASK-913 NOT MERGED` (referenced from PRODUCTION-HANDOFF-2026-09-29) | **FALSE (now merged)** | `git merge-base --is-ancestor 2fb19318 master` → True. TASK-913 is merged |
| 39 | `TASK-914 NOT MERGED` (referenced from PRODUCTION-HANDOFF-2026-09-29) | **FALSE (now merged)** | `git merge-base --is-ancestor 89707130 master` → True. TASK-914 is merged |
| 40 | `LINKEDIN_WRITER_KEYS = ("li1","li2","li3","li4","li5")` is the canonical LinkedIn authority | **PASS** | `cadencelibrary.py:63` — exactly this tuple. All consumers (`generate.py`, `generate_campaign.py`, `sequenceplan.py`) reference this single authority |

### CLAIMS CHECKED — PRODUCTION-HANDOFF-2026-09-29-RACHELE.md

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 41 | `master 6190f846` | **FALSE (stale)** | Current master: `2bf7b8a571fe11bada4f56fbebeee768ab1e78a8` |
| 42 | `TASK-913 NOT MERGED` | **FALSE** | Now merged (see #38) |
| 43 | `TASK-914 NOT MERGED` | **FALSE** | Now merged (see #39) |
| 44 | `test_generate` retry counts `2 != 1` | **FALSE (stale numbers)** | Actual: `9 != 1` (see #37) |

---

### SUMMARY

    Total claims checked:   44
    PASS:                   22
    FALSE:                  15
    UNVERIFIABLE:            7

### FALSE claims requiring correction (actionable, with evidence):

1. **OPERATING-MODE: "493 is the only campaign sending"** — 493 is PAUSED. This is the most dangerous false claim because it could cause a session to believe a campaign is live when it is not.
2. **OPERATING-MODE: TASK-320 "running", TASK-321 "blocked on 320"** — Both are DONE.
3. **OPERATING-MODE: "Five skills verified ready on branch, not yet integrated"** — They are on master; 4/5 are disconnected (zero callers).
4. **OPERATING-MODE: bisonfactory.stage() dry-run violation** — Fixed. Both gates now run on dry runs.
5. **OPERATING-MODE: TASK-400 in execution order** — Still TODO.
6. **CLAUDE.md: PROVIDER-CAMPAIGNS.json `generated_at: 2026-09-28T12:51:44Z`** — Actual: 2026-09-30T20:40:42+00:00.
7. **HANDOFF-2026-10-01: master SHA `d98c83ce`** — Stale; current is `2bf7b8a5`.
8. **HANDOFF-2026-10-01: 5 of 6 lane branches** — Gone (merged or abandoned).
9. **HANDOFF-2026-10-01 / PRODUCTION-HANDOFF-2026-09-29: test_generate `2 != 1`** — Now `9 != 1`.
10. **PRODUCTION-HANDOFF-2026-09-29: master SHA `6190f846`** — Stale.
11. **PRODUCTION-HANDOFF-2026-09-29: TASK-913/TASK-914 NOT MERGED** — Both now merged.

### FINDINGS

The OPERATING-MODE has accumulated the most staleness, particularly in the CRITICAL PATH and PRODUCTION FREEZE sections that reference task statuses and campaign states that have since changed. The "493 is the only campaign sending" claim is the highest-risk false claim because it misstates production reality. The bisonfactory.stage() fix is a positive correction — the document says a safety violation is "currently violated" when it has been repaired.

The HANDOFF-2026-10-01-LIVE.md is the document CLAUDE.md points to as current state, and its SHA is already stale 3 days later. CLAUDE.md's self-referential warning ("If you are reading this and the handoff it names is more than a day old, that is a bug") is accurate and working as designed.

### RISKS

- A session reading OPERATING-MODE's "493 is the only campaign sending" could make incorrect assumptions about production state.
- A session reading the CRITICAL PATH section could waste time on TASK-320/321 status questions that are already resolved.
- The bisonfactory.stage() "currently violated" claim could cause a session to attempt a fix that already exists.

### RECOMMENDED CLAUDE ACTION

Update the 15 FALSE claims. Priority order:
1. OPERATING-MODE §PRODUCTION FREEZE: "493 is the only campaign sending" → "487, 489 and 493 are ALL paused"
2. OPERATING-MODE §CRITICAL PATH: TASK-320/321 status → DONE
3. OPERATING-MODE §DRY RUN: bisonfactory.stage() violation → fixed
4. OPERATING-MODE §skills: "on branch, not yet integrated" → "on master, 4 of 5 disconnected"
5. CLAUDE.md: PROVIDER-CAMPAIGNS.json timestamp
6. HANDOFF-2026-10-01: master SHA and lane branch status
