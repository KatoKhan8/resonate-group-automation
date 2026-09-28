# TASK-528 — GLM independent verification of TASK-421

## Review metadata

| Field | Value |
|---|---|
| Reviewed task | TASK-421 (Suppression List Audit) |
| Review branch | `origin/glm-review-504-task-387` |
| Branch HEAD at dispatch | `f3b68bf849d8361fab9d3f8f972229369cf60944` |
| Branch HEAD at review | `515c638e14423a203e56f3ed3525af8569f72c07` (MOVED) |
| SHA reviewed | `f3b68bf849d8361fab9d3f8f972229369cf60944` (exact, per dispatch) |
| Review worktree | `.qwen/worktrees/task528-review` (detached HEAD at `f3b68bf8`) |
| Reviewer | GLM (TASK-528) |
| Date | 2026-09-28 |

**Branch movement notice:** The branch HEAD has moved from `f3b68bf8` to `515c638e` since dispatch. Per the dispatch instruction, this verdict reviews `f3b68bf8` — the artifact as named. The new commits after `f3b68bf8` are unrelated to TASK-421.

---

## Finding 1: The artifact exists and is in REVIEW

**Status: CONFIRMED**

The TASK-421 result file exists at `docs/qwen-tasks/REVIEW/TASK-421-suppression-list-audit.md` on the reviewed SHA. It was moved from TODO to REVIEW by commit `17f012a7`. The three TASK-421 commits on the branch are:

1. `65e5324e` — claim and move to RUNNING
2. `2070ce01` — the audit result (the artifact)
3. `17f012a7` — move to REVIEW with commit SHA

The artifact is a **finding** (read-only audit report). No code was changed. The task file itself is the deliverable.

---

## Finding 2: Six suppression stores — VERIFIED

The audit names six independent stores. I verified each one at the cited file:line:

| # | Store | Audit cites | Verified at | Status |
|---|---|---|---|---|
| 1 | Domain suppression | `config/suppress.txt`, `ingest.load_suppress()` | `ingest.py:109` (def), 24 call sites | CONFIRMED |
| 2 | Account suppression | `accountpolicy._suppress_account() :549` | `accountpolicy.py:543` (def), line 549 is function body | CONFIRMED (line is function def, not body) |
| 3 | Contact suppression | `accountpolicy._suppress_contact() :479` | `accountpolicy.py:479` | CONFIRMED (exact) |
| 4 | Agency DNC | `agencydnc.add() :131`, `agencydnc.lookup()` | `agencydnc.py:134` (def add), `eligibility.py:299-301` (lookup call) | CONFIRMED (line 134 not 131) |
| 5 | Bounce state | `adapters.py :131`, `channels._bounced() :96` | `adapters.py:131` (EMAIL_BOUNCED), `channels.py:96` (def _bounced) | CONFIRMED (exact) |
| 6 | Record drop | `ingest.py :191`, `eligibility._suppressed() :297` | `ingest.py:191` (load_suppress at import), `eligibility.py:296` (drop_reason check) | CONFIRMED (line 296 not 297) |

**The six-store architecture is real.** They are NOT one canonical list. The audit's honest answer — "several exist, and they CAN disagree" — is correct.

---

## Finding 3: Two gate functions merge all six — VERIFIED

**`eligibility.must_not_contact()` at `eligibility.py:358`:**
Returns a 5-tuple consulting:
1. `_suppressed()` → domain suppress, drop_reason, agency DNC (stores 1, 4, 6)
2. `_client_own_domain()` → client domain
3. `_record_state()` → record state
4. `_replied()` → contact unsubscribed/stopped/paused/replied (store 3)
5. `_paused()` → account pause (store 2)

**`channels.email_verdict()` at `channels.py:136`:**
Checks in order:
1. `_unsubscribed()` → contact + account unsubscribe (stores 2, 3)
2. `_suppressed()` → domain suppress, drop_reason (stores 1, 6)
3. Address presence
4. `_bounced()` → bounce events (store 5)
5. MX, verification

**All six stores are consulted across the two gates.** The priority order the audit describes is accurate.

---

## Finding 4: Write-path suppression checks — VERIFIED with one error

| Write path | Audit cites | Verified | Status |
|---|---|---|---|
| Email send (facing) | `providerwrites.py:2253` → `executionguard.py:985` | Both exact; `revalidate()` calls `store.get()` then `eligibility.decide()` at line 1044 | CONFIRMED |
| Email send auth | `executionguard.py:565` → `eligibility.py:645` | `eligibility.decide()` at line 605, `must_not_contact` call at line 645 | CONFIRMED |
| LinkedIn send | `heyreachfactory.py:1225` | Exact; calls `eligibility.must_not_contact()` | CONFIRMED |
| Email resume | `providerwrites.py:1415-1473` | Exact; `_resume_revalidates_suppression` reads every contact, calls `must_not_contact()` | CONFIRMED |
| Push to provider | `push.py:153` | Exact; calls `eligibility.decide()` | CONFIRMED |
| Killswitch | `killswitch.py:218` | Exact; calls `eligibility.decide()` | CONFIRMED |
| Funnel | `funnel.py:242` | Exact; calls `eligibility.decide()` | CONFIRMED |
| Web API | `web/api.py:1408`, `web/api.py:2113` | Both exact; call `eligibility.decide()` | CONFIRMED |

**One error in the audit's Store 4 reader table:** The audit claims `hygiene.check` reads agency DNC via `agencydnc.Index`. This is WRONG. `hygiene.py` does NOT import or call `agencydnc` — it only mentions it in a comment at line 374. The actual consumers of `agencydnc.Index()` are `web/app.py:1275` and `web/api.py:6304,6364`. The real send-boundary consumer is `eligibility._suppressed()` via `agencydnc.lookup()` at `eligibility.py:299-301`, which IS in the audit's table but under the wrong secondary consumer.

---

## Finding 5: The 76 re-verification — HONESTLY OWED

The audit correctly states it cannot perform a fresh read of the 76 suppressed recipients because `work/queue.jsonl` is not present in this worktree. I confirmed: `work/queue.jsonl` does not exist at the reviewed SHA.

The audit's analysis of the DURABILITY mechanism is correct:
- `_suppress_contact()` at `accountpolicy.py:479` sets `contact["unsubscribed"] = True`
- `channels._unsubscribed()` at `channels.py:90` reads it
- `eligibility._replied()` at `eligibility.py:398` reads it
- No code path clears `unsubscribed` without explicit operator action

The fresh read is genuinely owed from a worktree with live queue access.

---

## Finding 6: PRODUCT-GAPS.md contradiction — NOT IN AUDIT, found during review

PRODUCT-GAPS.md:1084-1085 states: *"Nothing can write the agency DNC list. `agencydnc.add` has no caller in `src/`. The list is read at intake by `hygiene`, and **is not consulted at the send boundary at all**."*

The second sentence is STALE. `agencydnc.lookup()` IS consulted at the send boundary through: `revalidate()` → `decide()` → `must_not_contact()` → `_suppressed()` → `agencydnc.lookup()`. This chain was verified at the code level. The audit correctly identifies `eligibility._suppressed() :291` as a reader but does not flag the contradiction with PRODUCT-GAPS.md.

This is a documentation defect, not a safety gap — the code is more protective than the documentation claims.

---

## Finding 7: Test falsifiability

TASK-421 is a read-only audit. It produced no new code and no new tests. Its claims are about existing code paths, verified by source inspection.

**How could the audit be wrong while its claims look right?**
- If a gate function listed in the audit did NOT actually call the suppression check it claims → I verified each call at the cited line; all are real.
- If `executionguard.revalidate()` did NOT re-read from disk → I verified it calls `store.get(authorization.rec_id)` at line 1032 before calling `eligibility.decide()`.
- If the resume guard did NOT actually check suppression → I verified `_resume_revalidates_suppression` iterates every contact and calls `must_not_contact()`.

The audit's claims are falsifiable by reading the source at the cited lines. I did so and they held.

---

## Finding 8: Would merging delete anything?

The branch deletes 8 files from `docs/qwen-tasks/TODO/`:

| Deleted | Added to REVIEW/DONE |
|---|---|
| TASK-319 | REVIEW/TASK-319 |
| TASK-387 | REVIEW/TASK-387 |
| TASK-396 | DONE/TASK-396 |
| TASK-407 | REVIEW/TASK-407 |
| TASK-408 | REVIEW/TASK-408 |
| TASK-414 | REVIEW/TASK-414 |
| TASK-420 | DONE/TASK-420 |
| TASK-421 | REVIEW/TASK-421 |

All 8 are task lifecycle moves (TODO → REVIEW/DONE), not destructive deletions. Every file has a corresponding addition. **No production code, tests, or documentation would be lost.**

The branch adds 101 files changed with +13,033/-594 lines. The code changes (src/generate.py, src/generate_campaign.py, tests, etc.) are from OTHER tasks on this branch, not TASK-421.

---

## Finding 9: Scope drift

This branch carries work from many tasks (TASK-231, TASK-246, TASK-264, TASK-285, TASK-290, TASK-301, TASK-311, TASK-319, TASK-325, TASK-326, TASK-387, TASK-396, TASK-400, TASK-420, TASK-421, and others). TASK-421's own contribution is exactly three commits touching only the task file. If cherry-picking, the three TASK-421 commits (`65e5324e`, `2070ce01`, `17f012a7`) are clean and self-contained.

---

## Disposition summary

| # | Finding | Disposition | Evidence |
|---|---|---|---|
| 1 | Artifact exists in REVIEW | CONFIRMED | `docs/qwen-tasks/REVIEW/TASK-421-suppression-list-audit.md` at `f3b68bf8` |
| 2 | Six stores named correctly | CONFIRMED | All six verified at cited file:line |
| 3 | Two gates merge all six | CONFIRMED | `must_not_contact` and `email_verdict` traced |
| 4 | Write paths check pre-write | CONFIRMED with one error | 8/8 paths verified; `hygiene.check` is NOT an agency DNC reader |
| 5 | 76 re-verification owed | CONFIRMED | No `work/queue.jsonl` in this worktree; mechanism is durable |
| 6 | PRODUCT-GAPS.md stale on DNC | NOT IN AUDIT | Send boundary DOES consult agency DNC via `eligibility._suppressed()` |
| 7 | No destructive merge | CONFIRMED | 8 TODO→REVIEW/DONE moves, all paired |
| 8 | Scope drift | PRESENT but cherry-pickable | TASK-421's 3 commits are clean |

---

## Recommendation: MERGE (cherry-pick)

TASK-421 is a competent read-only audit that honestly names what it found and what it could not verify. The six-store architecture is real, the write-path checks are confirmed, and the 76 re-verification is correctly flagged as owed.

One factual error: the audit claims `hygiene.check` reads `agencydnc.Index`. It does not. The real agency DNC consumer at the send boundary is `eligibility._suppressed()` via `agencydnc.lookup()`, which the audit also correctly names — so the error is in the secondary consumer table, not in the primary analysis.

One missed finding: PRODUCT-GAPS.md:1085 claims the agency DNC "is not consulted at the send boundary at all," which is stale. The code DOES consult it. This is a documentation fix, not a code fix.

The artifact is the task file. Cherry-pick the three TASK-421 commits (`65e5324e`, `2070ce01`, `17f012a7`) or integrate the REVIEW file. The 76 re-verification remains owed from a worktree with live queue access.
