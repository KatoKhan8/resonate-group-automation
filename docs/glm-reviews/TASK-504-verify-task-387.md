# TASK-504 — GLM Independent Verification of TASK-387

**Reviewed task:** TASK-387 — provider write-back of sends and replies  
**Reviewed branch:** origin/qwen-worker-3-r9  
**Target SHA:** 6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c  
**Branch HEAD at review time:** c725f9bc3893234221f716e5a557fa77c5a9e3b0 (MOVED from target SHA)  
**Review date:** 2026-10-04  
**Reviewer:** GLM (independent verification layer)  
**Worktree:** C:\Users\Zvonimir\Desktop\resonate-qwen-10\.qwen\worktrees\review-task-504 (detached HEAD at 6d91146a)

---

## Executive Summary

**DISPOSITION: REWORK** (partial — send write-back paths are DISCONNECTED)

TASK-387 is a read-only trace/investigation task that found provider-confirmed sends, replies, and bounces ARE already written back to queue records. The task added no production code changes — only a demonstration test file (`tests/test_task387_writeback_demo.py`, 257 lines).

**Critical finding:** The previous GLM verdict (commit 60f04b7bf) claimed all four write-back paths have production callers. **This is incorrect for the send write-back paths.** My independent verification found:

1. **Reply/bounce write-back: WIRED** — `poller.py:471` calls `inbound.ingest()` which is a real production caller
2. **Send write-back (EmailBison and HeyReach): DISCONNECTED** — `confirm_email_touches()` and `confirm_touches()` are ONLY called from `leadobserve.main()` which is a CLI entry point with NO automated invocation

This is the "existence is not function" defect the repository warns about. The functions exist and work correctly, but they are not consumed by any production execution stream. A CLI that must be manually invoked is not a production caller.

**Recommendation:** REWORK. The trace findings are correct, but the task must acknowledge that send write-back is DISCONNECTED from production execution. Either:
- Wire `confirm_email_touches()` and `confirm_touches()` into an automated reconciliation loop (e.g., the poller or a scheduled job), OR
- Explicitly state in the result block that send write-back exists but is CLI-only and not automated

---

## Detailed Verification

### 1. Does the artifact exist on this ref?

**YES.** The demo test file exists at SHA 6d91146a:
- `tests/test_task387_writeback_demo.py` — 257 lines, 3 tests

**Verification command:**
```bash
cd .qwen/worktrees/review-task-504
ls -la tests/test_task387_writeback_demo.py
```

**Test execution:**
```bash
python -m unittest tests.test_task387_writeback_demo -v
# Output: Ran 3 tests in 0.182s, OK
```

All three tests pass:
- `test_emailbison_send_is_written_to_record` — demonstrates `leadobserve.confirm_email_touches()` writing PUSH_MARKED
- `test_reply_is_written_to_record` — demonstrates `events.apply()` writing REPLY_RECEIVED
- `test_idempotency_same_event_not_recorded_twice` — demonstrates the provider_event_id idempotency guard

### 2. Do the claimed write-back paths exist at the claimed file:line locations?

**YES.** All four paths verified:

**Path 1: EmailBison sends**
- Claimed: `src/leadobserve.py:653-670` — `confirm_email_touches()` writes via `events.record()`
- Verified: Lines 653-670 contain `events.record()` call within `store.transaction()` block
- Events: PUSH_MARKED, EMAIL_BOUNCED, EMAIL_DELIVERED
- Idempotency: `provider_event_id` of form `emailbison:{campaign_id}:{scheduled_email_id}:{state}`

**Path 2: HeyReach sends**
- Claimed: `src/leadobserve.py:298-315` — `confirm_touches()` writes via `events.record()`
- Verified: Lines 298-315 contain `events.record()` call within `store.transaction()` block
- Events: PUSH_MARKED
- Idempotency: `provider_event_id` of form `heyreach:{campaign_id}:{provider_lead_id}:{state}`

**Path 3: Replies**
- Claimed: `src/inbound.py:365-527` → `src/events.py:463-520` — `inbound.handle()` → `events.apply()`
- Verified: `events.apply()` at lines 463-520 calls `record()` at line 497
- Events: REPLY_RECEIVED, REPLY_CLASSIFIED, POSITIVE_REPLY_DETECTED

**Path 4: Bounces**
- Claimed: Same path as replies via `events.apply()`
- Verified: Same path, events: EMAIL_BOUNCED

### 3. Are the write-back paths CONSUMED by production callers?

**PARTIALLY NO.** This is the critical finding.

**Reply/bounce write-back: WIRED**
```bash
grep -rn "inbound.handle\|inbound.ingest" src/ scripts/
# Output:
# src/poller.py:471: outcomes.extend(inbound.ingest(page, provider, recs=recs, config=config, ...))
# src/replaysim.py:132: outcome = inbound.handle(event, recs, rows=rows, config=config, ...)
```
- Caller: `poller.py:471` — this is a REAL production caller (webhook/polling handler)
- Status: **WIRED**

**Send write-back (EmailBison and HeyReach): DISCONNECTED**
```bash
grep -rn "confirm_email_touches\|confirm_touches" src/ scripts/
# Output:
# src/leadobserve.py:244:def confirm_touches(campaign_id, recs=None, live=False):
# src/leadobserve.py:579:def confirm_email_touches(campaign_id, recs=None, live=False):
# src/leadobserve.py:699:    out = confirm_email_touches(a.campaign, live=a.live)
# src/leadobserve.py:701:    out = confirm_touches(a.campaign, live=a.live)
```

The only callers are at lines 699-701, which is `leadobserve.main()` — a CLI entry point.

```bash
grep -rn "from src import leadobserve\|import leadobserve" src/ scripts/
# Output: (empty)
```

**No module imports leadobserve.** The functions are only callable via:
```bash
python -m src.leadobserve --campaign <id> --provider emailbison --confirm --live
```

This is NOT a production caller. This is a manual CLI invocation. There is no scheduled job, no automation, no script that invokes this. The functions exist and work correctly, but they are DISCONNECTED from the production execution stream.

**Status: DISCONNECTED** — zero production callers for send write-back

**Why this matters:** The task asks whether "the queue only ever knows what WE intended to send, never what the provider confirms happened." For replies and bounces, the answer is: the queue DOES know, through `poller.py` → `inbound.ingest()`. But for sends, the answer is: the queue CAN know, but only if a human manually runs the CLI. This is not automated write-back.

### 4. Are the tests falsifiable?

**YES.** The tests are falsifiable.

**Test 1: `test_emailbison_send_is_written_to_record`**
- Mocks `leadobserve.scheduled_rows` and `leadobserve.match_scheduled`
- Calls `leadobserve.confirm_email_touches()` directly
- Asserts that `result["recorded"]` has length 1
- If `confirm_email_touches()` were disabled (early return), this test would fail with `AssertionError: 0 != 1`

**Test 2: `test_reply_is_written_to_record`**
- Creates a fixture neutral event
- Calls `events.apply()` directly
- Asserts that the record's event log gains a REPLY_RECEIVED entry
- If `events.apply()` were disabled, this test would fail

**Test 3: `test_idempotency_same_event_not_recorded_twice`**
- Applies the same event twice
- Asserts that only one event is recorded
- If idempotency were broken, this test would fail with `AssertionError: 1 != 2`

**Interpretation:** The tests are falsifiable and would catch regressions. However, they test the functions in isolation, not through a production entry point. Test 1 calls `confirm_email_touches()` directly, not through `leadobserve.main()` or any automated path. This is testing the seam, not the production wiring.

### 5. Would merging delete anything?

**NO.** Comparison with master:

```bash
git diff master...HEAD --stat
# Output: 100 files changed, 12725 insertions(+), 594 deletions(-)
```

The branch carries 100 files from many tasks (TASK-385, TASK-396, TASK-400, TASK-420, TASK-421, TASK-427, TASK-433, TASK-435, TASK-436, TASK-442, TASK-444, TASK-449, TASK-451, TASK-454, TASK-460, TASK-465, TASK-468, TASK-471, TASK-472, TASK-473, TASK-475, TASK-476, TASK-481, TASK-482, and many GLM verdicts).

**Files that would be deleted:**
```bash
git diff master...HEAD --diff-filter=D --name-only
# Output:
# docs/qwen-tasks/TODO/TASK-319-five-skills-as-executable-sops.md
# docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md
# docs/qwen-tasks/TODO/TASK-396-training-pair-capture-check.md
# docs/qwen-tasks/TODO/TASK-407-glm-verify-task-399.md
# docs/qwen-tasks/TODO/TASK-408-glm-verify-task-319.md
# docs/qwen-tasks/TODO/TASK-414-spend-report-wiring-check.md
# docs/qwen-tasks/TODO/TASK-420-docs-hygiene-pass.md
# docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md
```

These are task files being moved from TODO to REVIEW/DONE, which is expected lifecycle. No production code would be deleted.

**TASK-387 specifically:**
```bash
git show f5db204e --stat
# Output:
# docs/qwen-tasks/REVIEW/TASK-387-ledger-write-back-of-provider-sends-and-replies.md | 138 ++++++
# tests/test_task387_writeback_demo.py | 257 ++++++
# 2 files changed, 395 insertions(+)
```

TASK-387 added only:
1. The task file with trace findings (moved to REVIEW)
2. The demo test file

No production code was changed.

### 6. Scope drift: does the branch carry junk beside the work?

**YES.** The branch carries 86 commits and 100 files from many tasks. This is massive scope drift.

**TASK-387's contribution is limited to:**
- `tests/test_task387_writeback_demo.py` (257 lines, new file)
- `docs/qwen-tasks/REVIEW/TASK-387-ledger-write-back-of-provider-sends-and-replies.md` (273 lines, task file with trace findings)

**Recommendation:** Cherry-pick only TASK-387's commits (`5d88cf82`, `f5db204e`, `c0ebd287`, `342c3211`), not the entire branch.

---

## Findings

### Finding 1: Reply/bounce write-back is WIRED

**Severity:** Informational  
**Confidence:** High  
**Evidence:** 
- `src/poller.py:471` calls `inbound.ingest()`
- `src/inbound.py:371` calls `events.apply()`
- `src/events.py:497` calls `events.record()`

**Status:** CONFIRMED — this path has a real production caller

### Finding 2: Send write-back is DISCONNECTED

**Severity:** Critical  
**Confidence:** High  
**Evidence:**
- `src/leadobserve.py:699-701` — `confirm_email_touches()` and `confirm_touches()` are only called from `leadobserve.main()` (CLI)
- `grep -rn "from src import leadobserve\|import leadobserve" src/ scripts/` returns empty
- No scheduled job, no automation, no script invokes the CLI

**Status:** CONFIRMED — zero production callers for send write-back. This is the "existence is not function" defect.

**Why this is critical:** The task claims "the write-back exists and is wired", but for sends, it's only wired to a CLI. A CLI that must be manually invoked is not automated write-back. The queue CAN know about provider-confirmed sends, but only if a human runs the CLI. This is not the same as the reply/bounce path, which is automatically invoked by the poller.

### Finding 3: Demo tests are falsifiable but test the seam, not production wiring

**Severity:** Suggestion  
**Confidence:** High  
**Evidence:** 
- Tests call `confirm_email_touches()` and `events.apply()` directly
- Tests would catch regressions in the functions themselves
- Tests do NOT verify that the functions are called from production code

**Status:** CONFIRMED — tests are falsifiable, but they test the seam, not the production wiring. A test that calls `confirm_email_touches()` directly does not prove that `confirm_email_touches()` is called from production code.

### Finding 4: Aggregate campaign counters are read-and-discarded (by design)

**Severity:** Informational  
**Confidence:** High  
**Evidence:** `scripts/bison_watch_loop.py:144-200` reads campaign-level counters (emails_sent, replied, bounced) which go to heartbeat/watch files, not per-lead records. This is campaign-level observability for monitoring, not per-lead record state.

**Status:** CONFIRMED — this is by design, not a defect. The per-lead question is answered by `leadobserve.confirm_email_touches()` and the event log.

### Finding 5: No code changes were required

**Severity:** Informational  
**Confidence:** High  
**Evidence:** TASK-387's commits show only test file and task file additions. No production code was modified.

**Status:** CONFIRMED — the write-back already exists on master

### Finding 6: Previous GLM verdict miscounted production callers

**Severity:** Critical  
**Confidence:** High  
**Evidence:** The previous GLM verdict (commit 60f04b7bf) stated: "All four paths have production callers (not disconnected)" and listed `leadobserve.main()` as a production caller. This is incorrect. A CLI entry point that is not invoked by any automated process is NOT a production caller. This is the exact defect the repository warns about: "existence is not function."

**Status:** CONFIRMED — previous verdict was wrong on this point

---

## Disposition

**DISPOSITION: REWORK** (partial — send write-back paths are DISCONNECTED)

**Reason:** TASK-387 correctly identified that provider-confirmed sends, replies, and bounces CAN be written back to queue records, and the reply/bounce path IS wired through `poller.py` → `inbound.ingest()`. However, the send write-back paths (`confirm_email_touches()` and `confirm_touches()`) are DISCONNECTED from production execution. They exist and work correctly, but they are only callable via a manual CLI invocation with no automated scheduling.

This is the "existence is not function" defect. The previous GLM verdict miscounted this as "all four paths have production callers", but a CLI entry point that is not invoked by any automated process is NOT a production caller.

**What needs to be reworked:**

1. **Option A: Wire send write-back into production.** Add `confirm_email_touches()` and `confirm_touches()` to an automated reconciliation loop. For example:
   - Call them from `poller.py` after polling for replies
   - Add a scheduled job that runs `python -m src.leadobserve --confirm --live` periodically
   - Wire them into the existing `outcomes.py` reconciliation path

2. **Option B: Explicitly acknowledge the gap.** If send write-back is intentionally CLI-only (e.g., because it's expensive or because the poller already handles it indirectly), the task file should state this explicitly:
   - "Send write-back exists but is CLI-only and not automated"
   - "The queue CAN know about provider-confirmed sends, but only via manual CLI invocation"
   - "This is a known gap and is tracked in TASK-XXX"

3. **Update the result block.** The current result block states: "the write-back exists and is wired" and "Callers verified: `leadobserve.confirm_email_touches()` is called by `leadobserve.main()` (CLI) and can be called by reconciliation scripts". This is misleading. It should state:
   - "Reply/bounce write-back: WIRED (poller.py:471 → inbound.ingest)"
   - "Send write-back: DISCONNECTED (CLI-only, no automated invocation)"

**Recommendation:** REWORK. The trace findings are correct and the demo test is a useful addition, but the task must acknowledge that send write-back is DISCONNECTED from production execution. Either wire it into an automated loop, or explicitly state the gap.

---

## Verification Commands

All commands are read-only and reproducible:

```bash
# Verify worktree is at exact SHA
git worktree add .qwen/worktrees/review-task-504 6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c --detach
cd .qwen/worktrees/review-task-504
git log --oneline -1
# Output: 6d91146a TASK-482: GLM verdict for TASK-326 — REWORK (disconnected)

# Verify demo test exists
ls -la tests/test_task387_writeback_demo.py

# Run demo tests
python -m unittest tests.test_task387_writeback_demo -v
# Output: Ran 3 tests in 0.182s, OK

# Verify write-back paths exist
sed -n '653,670p' src/leadobserve.py  # EmailBison
sed -n '298,315p' src/leadobserve.py  # HeyReach
sed -n '463,520p' src/events.py       # Replies/bounces

# Verify production callers — THIS IS THE CRITICAL CHECK
grep -rn "confirm_email_touches\|confirm_touches" src/ scripts/
# Output: only leadobserve.py:699-701 (CLI)
grep -rn "from src import leadobserve\|import leadobserve" src/ scripts/
# Output: (empty) — NO IMPORTS

grep -rn "inbound.handle\|inbound.ingest" src/ scripts/
# Output: src/poller.py:471 — REAL production caller

# Verify TASK-387's changes
git show f5db204e --stat

# Compare with master
git diff master...HEAD --stat
```

---

## Boundary Compliance

- **Provider writes:** 0 (read-only verification)
- **Live API calls:** 0 (demo tests use fixtures)
- **Campaign mutations:** 0 (no campaigns touched)
- **Production state:** unchanged (read-only review)

---

## Conclusion

TASK-387 correctly identified that provider-confirmed sends, replies, and bounces CAN be written back to queue records. The reply/bounce path IS wired through `poller.py` → `inbound.ingest()`. However, the send write-back paths are DISCONNECTED from production execution — they exist and work correctly, but are only callable via a manual CLI invocation with no automated scheduling.

This is the "existence is not function" defect. The previous GLM verdict miscounted this as "all four paths have production callers", but a CLI entry point that is not invoked by any automated process is NOT a production caller.

**DISPOSITION: REWORK.** The task must either wire send write-back into an automated reconciliation loop, or explicitly acknowledge the gap in the result block.
