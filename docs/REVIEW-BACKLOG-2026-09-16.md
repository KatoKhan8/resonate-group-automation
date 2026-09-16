# REVIEW BACKLOG — 2026-09-16

TASK-188 verification pass. Twelve tasks sat in REVIEW/; eleven verified and
moved to DONE. One left with findings named.

## Method

For each task in REVIEW/:
1. Does the commit SHA in the result block exist? Is it on master?
2. Do the files it says it changed exist on disk?
3. Do the tests it claims green actually pass now (exit code read off the process)?

## The Eleven — Verified and Moved to DONE

| Task  | Claimed SHA | On master? | Files exist? | Tests pass? | Notes |
|-------|-------------|------------|--------------|-------------|-------|
| 184   | 879364d     | YES        | YES          | 15+35+9+17+9 = 85 green | Counts in result block differ from actual (claimed 17+11+7, actual 9+17+9) but all green |
| 180   | 120f0a6     | YES        | YES          | Script exit 0 | Analysis task, no test suite |
| 175   | 4294cd3     | YES        | YES          | Script exit 0 | Read-only enumeration, no test changes |
| 171   | 2a4a902     | YES        | YES          | Script exit 0 | Analysis task, no test suite |
| 170   | 80c45f5     | YES        | YES          | 35 green (shared with 184) | Script also runs |
| 169   | 6b1f2b4     | NO — stale SHA | YES (via 58f2b28) | Script exit 0 | SHA was amended/rebased; work IS on master under different commit |
| 168   | e9e073e     | YES        | YES          | 36+49+51+80 = 216 green | All claimed test counts match |
| 165   | d7b5302     | YES        | YES          | 42+80 = 122 green | All claimed test counts match |
| 155   | cc2b82c     | YES        | YES          | Script exit 0 | Analysis task, no test suite |
| 162   | a00e877     | YES        | YES          | 17+51 = 68 green | Consumption proven: company_evidence called from context_for at line 598 |
| 158   | 00fde19     | YES        | YES          | 80 invariants green | 1 pre-existing failure in test_the_heyreach_write_contract (reported by task itself, not a regression) |

## The One Left in REVIEW

### TASK-059 — which-email-produced-which-reply

**STATUS:** COMPLETE, NOT INTEGRATED (per its own result block)

**Why not moved:**
- Result block explicitly says "The report contradicts itself in four places"
- "matched" counts 8792 rows that did not match
- Empty body reports 0.0% unreadable against a previous 46.5%
- 1561 of 1570 positives come from rows with no body at all
- 16.14% positive cannot be reconciled with 0.3-0.4% reply rates in BISON-CADENCE-FINDINGS
- TASK-090 carries the rework

**SHA:** f164f8c (on qwen-worker-4, recovered after unplanned shutdown)
**Files:** docs/ESTATE-BISON-OUTCOMES-2026-09-15.md exists on disk
**Tests:** N/A — analysis task with known contradictions

## Findings

### TASK-169 SHA discrepancy
The result block claims SHA 6b1f2b4. That commit exists in the object store
but is NOT on any branch — it is a dangling commit. The files it created
(docs/ENRICHMENT-ORDER-2026-09-16.md, scripts/task169_enrichment_order.py)
landed on master via commit 58f2b28. The SHA was stale from an amend or
rebase. The work is integrated; the result block's SHA is wrong.

### TASK-184 test count discrepancies
The result block claims:
- test_staging_a_campaign_twice_builds_one: 17 tests → actual: 9
- test_a_five_step_campaign_sends_five_different_emails: 11 tests → actual: 17
- test_crash_restart_idempotency: 7 tests → actual: 9

All tests pass. The counts in the result block are wrong but the work is
correct. This is a reporting error, not a code error.

### TASK-158 pre-existing test failure
test_the_heyreach_write_contract has 1 failure:
`/list/AddLeadsToListV2` is in WRITE_ROUTES but not in the test's expected
set. TASK-158 reported this as pre-existing. TASK-164 (d24cfeb) attempted
to fix it but the test's expected set was not updated. This is a known
open defect, not a regression from any of the 11 tasks.

## The Durable Fix

`scripts/task_registry.py` now reports a `verified_on_master` field for every
task in REVIEW. It extracts the SHA from the result block, checks whether
that SHA or any commit touching the task's files is an ancestor of master,
and reports the result. A task in REVIEW with `verified_on_master: true` is
a task whose work has landed and is waiting for result-block review. A task
with `verified_on_master: false` is a task whose work has NOT landed yet.

This replaces the ambiguous AWAITING_REVIEW with actionable information.
