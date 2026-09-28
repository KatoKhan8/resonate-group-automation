# TASK-504 — GLM Independent Verification of TASK-387

**Reviewed task:** TASK-387 — provider write-back of sends and replies  
**Reviewed branch:** origin/qwen-worker-3-r9  
**Target SHA:** 6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c  
**Branch HEAD at review time:** 835132f9c378ee49c640724e1a6237894513f31b (moved)  
**Review date:** 2026-09-28  
**Reviewer:** GLM (independent verification layer)

---

## Executive Summary

**DISPOSITION: MERGE** (cherry-pick TASK-387 commits only)

TASK-387 is a read-only trace/investigation task that found provider-confirmed sends, replies, and bounces ARE already written back to queue records through existing production code. The task added no production code changes — only a demonstration test file (`tests/test_task387_writeback_demo.py`, 257 lines) that verifies the write-back paths exist and are wired.

**Key findings:**
1. All four claimed write-back paths exist and have production callers
2. The demo tests are falsifiable — mutation testing confirmed they fail when the write-back is removed
3. No production code was changed; the write-back already exists on master
4. The branch carries 100 files / 12,725 lines from other tasks, but TASK-387 itself is clean (one test file)
5. Merging would not delete anything except move task files between queues (expected)

**Recommendation:** Cherry-pick commits `5d88cf82`, `f5db204e`, `c0ebd287`, `342c3211` (TASK-387's four commits) to add the demo test to master. The trace findings are correct and the test is a useful addition.

---

## Detailed Verification

### 1. Does the artifact exist on this ref?

**YES.** The demo test file exists at this SHA:
- `tests/test_task387_writeback_demo.py` — 257 lines, 3 tests

**Verification command:**
```bash
git show 6d91146a:tests/test_task387_writeback_demo.py | wc -l
# Output: 257
```

**Test execution:**
```bash
python -m unittest tests.test_task387_writeback_demo -v
# Output: Ran 3 tests in 0.087s, OK
```

All three tests pass:
- `test_emailbison_send_is_written_to_record` — demonstrates `leadobserve.confirm_email_touches()` writing PUSH_MARKED
- `test_reply_is_written_to_record` — demonstrates `events.apply()` writing REPLY_RECEIVED
- `test_idempotency_same_event_not_recorded_twice` — demonstrates the provider_event_id idempotency guard

---

### 2. Existence is not function — are there production callers?

**YES.** All claimed write-back functions exist on master at identical line numbers and have production callers.

#### Write-back path 1: EmailBison sends
- **Function:** `src/leadobserve.py:579` — `confirm_email_touches(campaign_id, recs=None, live=False)`
- **Caller:** `src/leadobserve.py:699` — called from `leadobserve.main()` (CLI entry point)
- **CLI invocation:** `python -m src.leadobserve emailbison <campaign> --confirm --live`
- **Writes:** PUSH_MARKED, EMAIL_BOUNCED, EMAIL_DELIVERED via `events.record()` within `store.transaction()`

#### Write-back path 2: HeyReach/LinkedIn sends
- **Function:** `src/leadobserve.py:244` — `confirm_touches(campaign_id, recs=None, live=False)`
- **Caller:** `src/leadobserve.py:701` — called from `leadobserve.main()` (CLI entry point)
- **CLI invocation:** `python -m src.leadobserve heyreach <campaign> --confirm --live`
- **Writes:** PUSH_MARKED via `events.record()` within `store.transaction()`

#### Write-back path 3: Replies
- **Function:** `src/inbound.py:365` — `handle(event, recs, ...)`
- **Caller chain:** `src/poller.py:471` → `inbound.ingest()` → `src/inbound.py:528` → `inbound.handle()` → `src/inbound.py:371` → `events.apply()`
- **CLI invocation:** `python -m src.poller <provider> --live` (production polling loop)
- **Writes:** REPLY_RECEIVED, REPLY_CLASSIFIED, POSITIVE_REPLY_DETECTED via `events.apply()` → `events.record()`

#### Write-back path 4: Bounces
- **Same path as replies** — `inbound.handle()` → `events.apply()` → `events.record()`
- **Writes:** EMAIL_BOUNCED

**Verification commands:**
```bash
# Check functions exist on master at same line numbers
git show origin/master:src/leadobserve.py | grep -n "def confirm_email_touches\|def confirm_touches"
# Output: 244:def confirm_touches(...)
#         579:def confirm_email_touches(...)

git show origin/master:src/events.py | grep -n "def apply\|def record"
# Output: 280:def record(...)
#         463:def apply(...)

git show origin/master:src/inbound.py | grep -n "def handle\|def ingest"
# Output: 365:def handle(...)
#         528:def ingest(...)

# Check production callers
git grep -n "confirm_email_touches\|confirm_touches" origin/master -- src/ | grep -v "def confirm"
# Output: src/leadobserve.py:699: out = confirm_email_touches(a.campaign, live=a.live)
#         src/leadobserve.py:701: out = confirm_touches(a.campaign, live=a.live)

git grep -n "inbound.ingest" origin/master -- src/
# Output: src/poller.py:471: outcomes.extend(inbound.ingest(page, provider, recs=recs, config=config, ...))
```

**Conclusion:** All write-back paths are wired to production entry points. The trace findings are correct.

---

### 3. Are the tests falsifiable?

**YES.** Mutation testing confirmed the tests fail when the write-back is removed.

**Mutation performed:**
- Commented out the `events.record()` call in `src/leadobserve.py:657` (within `confirm_email_touches()`)
- Replaced with `written = None` to simulate a broken write-back

**Result:**
```bash
python -m unittest tests.test_task387_writeback_demo.TestProviderWriteback.test_emailbison_send_is_written_to_record -v
# Output: FAIL
# AssertionError: 0 != 1 : one send should be recorded
```

**Why it failed:**
- The mutation caused `written = None`, which triggered the `if written is None:` branch at line 662
- This called `recorded.pop()`, removing the entry from the result list
- The test asserted `len(result["recorded"]) == 1`, which failed because the list was empty
- The test also asserts on the actual record's event log (`updated_rec["events"]`), which would be empty if `events.record()` were not called

**Conclusion:** The test genuinely verifies the write-back path, not just the return value. It would fail if the write-back were broken.

---

### 4. Would merging delete anything?

**NO.** The branch deletes 8 TODO files, but these are legitimate task state transitions:

| Deleted from TODO/ | Moved to |
|-------------------|----------|
| TASK-319-five-skills-as-executable-sops.md | REVIEW/ |
| TASK-387-ledger-write-back-of-provider-sends-and-replies.md | REVIEW/ |
| TASK-396-training-pair-capture-check.md | DONE/ |
| TASK-407-glm-verify-task-399.md | REVIEW/ |
| TASK-408-glm-verify-task-319.md | REVIEW/ |
| TASK-414-spend-report-wiring-check.md | REVIEW/ |
| TASK-420-docs-hygiene-pass.md | DONE/ |
| TASK-421-suppression-list-audit.md | REVIEW/ |

**Verification command:**
```bash
git diff origin/master...6d91146a --diff-filter=D --name-only
# Output: 8 files, all in docs/qwen-tasks/TODO/

for f in TASK-319 TASK-387 TASK-396 TASK-407 TASK-408 TASK-414 TASK-420 TASK-421; do
  git ls-tree -r --name-only 6d91146a | grep "$f"
done
# Output: all 8 files exist in REVIEW/ or DONE/ on the branch
```

**Conclusion:** No destructive deletion. The "deleted" files are task queue state transitions (TODO → REVIEW/DONE), which is expected queue mechanics.

---

### 5. Scope drift — does the branch carry junk?

**YES, but TASK-387 itself is clean.**

The branch has 100 files changed and 12,725 insertions because it's a long-lived branch carrying work from many tasks (TASK-387, TASK-396, TASK-400, TASK-414, TASK-421, TASK-427, TASK-433, TASK-435, TASK-436, TASK-442, TASK-444, TASK-449, TASK-451, TASK-454, TASK-460, TASK-465, TASK-468, TASK-471, TASK-472, TASK-473, TASK-475, TASK-476, TASK-481, TASK-482, and others).

**TASK-387's specific contribution:**
- 1 new test file: `tests/test_task387_writeback_demo.py` (257 lines)
- 4 commits: `5d88cf82`, `f5db204e`, `c0ebd287`, `342c3211`
- 0 production code changes

**Verification command:**
```bash
git diff origin/master...6d91146a --stat -- tests/test_task387_writeback_demo.py
# Output: tests/test_task387_writeback_demo.py | 257 +++++++++++++++++++++++++++++++++++
#         1 file changed, 257 insertions(+)

git diff origin/master...6d91146a -- src/leadobserve.py src/events.py src/inbound.py src/store.py
# Output: (empty) — no production code changes
```

**Recommendation:** Cherry-pick only TASK-387's commits to avoid pulling in other tasks' work. The TASK-387 artifact is isolated and clean.

---

### 6. Trace findings verification

The task's trace findings claim:

**Claim 1:** "Provider-confirmed sends, replies and bounces ARE written back to queue records."  
**Verdict:** VERIFIED. All four write-back paths exist and have production callers (see section 2).

**Claim 2:** "Four write-back paths: EmailBison sends, HeyReach sends, replies, bounces."  
**Verdict:** VERIFIED. All four paths traced and confirmed (see section 2).

**Claim 3:** "One read-and-discard path: campaign-level counters from bison_watch_loop.py."  
**Verdict:** VERIFIED. `scripts/bison_watch_loop.py` reads aggregate counters via `bison.campaign()` and `bison.scheduled_emails()` but writes them to heartbeat/watch files (`work/heartbeat/bison-<id>.json`, `work/watch-events/bison-<id>.jsonl`), not to per-lead records. This is campaign-level observability, not per-lead state.

**Claim 4:** "No code changes are required."  
**Verdict:** VERIFIED. The write-back already exists on master. TASK-387 added no production code.

**Claim 5:** "The demo test demonstrates the write-back path."  
**Verdict:** VERIFIED. The test passes, is falsifiable, and actually exercises the real write-back path (see sections 1 and 3).

---

## Line Number Discrepancies

The task file claims specific line numbers that are slightly off:

| Claimed | Actual | Function |
|---------|--------|----------|
| `leadobserve.py:653-670` | `leadobserve.py:579-680` | `confirm_email_touches()` |
| `leadobserve.py:298-315` | `leadobserve.py:244-315` | `confirm_touches()` |
| `events.py:463-520` | `events.py:463-520` | `apply()` ✓ |
| `events.py:280-310` | `events.py:280-310` | `record()` ✓ |
| `inbound.py:365-527` | `inbound.py:365-527` | `handle()` ✓ |

The line numbers for `leadobserve` functions are off by ~75-50 lines, but the functions exist and are correct. This is a minor documentation issue, not a substantive defect.

---

## Test Limitations

The demo tests have one limitation worth noting:

**Test 1 (`test_emailbison_send_is_written_to_record`)** mocks both `scheduled_rows()` (the provider read) and `match_scheduled()` (the matching logic). This means:
- It does NOT test that `scheduled_rows()` actually reads from the provider API
- It does NOT test that `match_scheduled()` correctly matches provider data to records
- It DOES test that IF those return correct data, THEN `events.record()` is called and the event is written

This is within the task's scope ("a fixture standing in for the API response is fine"), but it's worth noting that the test proves the write-back mechanism works given pre-digested input, not that the full chain from provider API response to record is wired.

**Tests 2 and 3** are stronger — they test the canonical `events.apply()` path with no mocking of core logic.

---

## Risks

1. **Line number drift:** The task file's line numbers are slightly off. This is a documentation issue, not a functional defect, but it could confuse future readers.

2. **Test coverage gap:** Test 1 mocks the provider read and matching logic, so it doesn't prove the full chain. However, this is within the task's scope and the write-back mechanism itself is correctly tested.

3. **Branch scope:** The branch carries 100 files / 12,725 lines from other tasks. If merged as a whole, it would pull in all that work. Cherry-pick only TASK-387's commits.

---

## Recommendation

**MERGE** (cherry-pick TASK-387 commits only).

**Rationale:**
1. The trace findings are correct — the write-back paths exist and are wired
2. The demo test is a useful addition — it verifies the write-back mechanism and is falsifiable
3. No production code was changed, so there's no risk of breaking existing functionality
4. The artifact is clean and isolated — one test file, four commits

**Cherry-pick commits:**
```bash
git cherry-pick 5d88cf82 f5db204e c0ebd287 342c3211
```

**Do NOT merge the entire branch** — it carries work from 20+ other tasks that have not all been verified.

---

## Verification Commands (Reproducible)

```bash
# Check out the exact SHA in an isolated worktree
git worktree add /tmp/glm-504 6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c --detach

# Verify the demo test exists
git show 6d91146a:tests/test_task387_writeback_demo.py | wc -l
# Expected: 257

# Run the demo tests
cd /tmp/glm-504
python -m unittest tests.test_task387_writeback_demo -v
# Expected: 3 tests, OK

# Verify write-back functions exist on master
git show origin/master:src/leadobserve.py | grep -n "def confirm_email_touches\|def confirm_touches"
git show origin/master:src/events.py | grep -n "def apply\|def record"
git show origin/master:src/inbound.py | grep -n "def handle\|def ingest"

# Verify production callers
git grep -n "confirm_email_touches\|confirm_touches" origin/master -- src/ | grep -v "def confirm"
git grep -n "inbound.ingest" origin/master -- src/

# Check TASK-387's specific changes
git diff origin/master...6d91146a --stat -- tests/test_task387_writeback_demo.py
git diff origin/master...6d91146a -- src/leadobserve.py src/events.py src/inbound.py src/store.py

# Mutation test (optional — to verify falsifiability)
# Comment out events.record() in src/leadobserve.py:657, run test, expect FAIL
```

---

## Conclusion

TASK-387 is a well-executed trace/investigation task. The write-back paths exist, are wired to production entry points, and the demo test correctly verifies the mechanism. The task added no production code (because none was needed) and the artifact is clean.

**Disposition: MERGE** (cherry-pick TASK-387 commits only).
