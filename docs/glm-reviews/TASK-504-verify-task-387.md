# GLM Independent Verification: TASK-387

**Review date:** 2026-09-29  
**Reviewer:** GLM (independent verification)  
**Task:** TASK-387 — Ledger write-back of provider sends and replies  
**Branch:** origin/qwen-worker-3-r9  
**Branch HEAD at review time:** 02eb130e7dc22bb24344a352ee71778e260b599e  
**Target SHA reviewed:** 6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c  
**Note:** Branch has moved since task file was written. Reviewed the exact SHA named in TASK-504.

---

## Verdict Summary

**DISPOSITION: MERGE with one important clarification**

TASK-387 is a trace/investigation task that correctly concludes provider-confirmed sends, replies, and bounces ARE written back to queue records. The write-back path exists and is wired. However, the review reveals an important distinction the task file does not emphasize:

- **Replies and bounces**: Fully automated via `poller.run()` → `inbound.ingest()` → `events.apply()`
- **Sends (EmailBison and HeyReach)**: Manual CLI only via `python -m src.leadobserve --confirm --live`

The write-back exists for all three event types, but sends are not automatically reconciled. An operator must invoke the CLI. This is not a defect in TASK-387's work - the task asked to trace what exists, and the trace is accurate - but it is a operational characteristic worth naming.

---

## Detailed Findings

### 1. Does the artifact exist on this ref?

**YES.** The artifact is `tests/test_task387_writeback_demo.py`, added at commit `f5db204e`.

```bash
$ git log --diff-filter=A --all -- tests/test_task387_writeback_demo.py
commit f5db204e74cff0a6e687fc8bf27cf86556578d1d
Author: Zvonimir Beslic <zvonimir@resonategroup.co>
Date:   Mon Sep 28 02:21:21 2026 +0200

    TASK-387: trace shows provider write-back exists, demo test passes
```

The file exists at the target SHA and contains three tests demonstrating the write-back path.

### 2. Existence is not function — are there production callers?

**YES, with an important distinction.**

#### Replies and Bounces (automated)

The chain is fully automated:

```
poller.run() [src/poller.py:414]
  → inbound.ingest() [src/poller.py:470-471]
    → inbound.handle() [src/inbound.py:551]
      → events.apply() [src/inbound.py:371]
        → events.record() [src/events.py:497]
```

**Verification:**
- `src/poller.py:470-471`: `outcomes.extend(inbound.ingest(page, provider, ...))`
- `src/inbound.py:551`: `outcomes = [handle(e, recs, ...) for e in neutral]`
- `src/inbound.py:371`: `applied = events.apply(recs, event)`
- `src/events.py:463`: `def apply(recs, event):`
- `src/events.py:497`: `record(rec, event["type"], ...)`

The poller has a CLI entry point (`src/poller.py:487 def main()`) and is invoked by watch loops (`scripts/reply_watch_loop.py`).

#### Sends (manual CLI only)

```
CLI: python -m src.leadobserve --campaign <id> --confirm --live
  → confirm_email_touches() [src/leadobserve.py:699]
  → confirm_touches() [src/leadobserve.py:701]
    → events.record() [src/leadobserve.py:653-670]
```

**Verification:**
- `src/leadobserve.py:699`: `out = confirm_email_touches(a.campaign, live=a.live)`
- `src/leadobserve.py:701`: `out = confirm_touches(a.campaign, live=a.live)`
- These are called from the CLI argument parser in `leadobserve.main()` (line 690+)

**No automated caller found.** Grep for `confirm_email_touches` and `confirm_touches` in `src/` returns only:
- The function definitions themselves
- The CLI calls at lines 699 and 701
- Test files

No production pipeline, watch loop, or scheduled task invokes these functions automatically. An operator must run the CLI.

**This is not a defect.** The task asked to trace what exists, and the write-back exists. The task did not ask whether it is automated. But the operational characteristic is worth naming: sends require manual reconciliation, while replies/bounces are automatic.

### 3. Are the tests falsifiable?

**YES.** The tests are well-constructed and falsifiable.

**Test 1: `test_emailbison_send_is_written_to_record`**
- Mocks `scheduled_rows()` to return a fixture standing in for the API response
- Mocks `match_scheduled()` to return the test record
- Calls `confirm_email_touches(live=True)` through the real function
- Asserts the record's event log gained a `PUSH_MARKED` event with correct fields
- **Falsification path:** If `confirm_email_touches` did not call `events.record()`, the assertion `self.assertGreater(len(updated_rec["events"]), 0)` would fail.

**Test 2: `test_reply_is_written_to_record`**
- Creates a fixture neutral event via `events.neutral()`
- Calls `events.apply()` through the real function
- Asserts the record's event log gained a `REPLY_RECEIVED` event
- **Falsification path:** If `events.apply` did not call `events.record()`, the event would not appear in the log.

**Test 3: `test_idempotency_same_event_not_recorded_twice`**
- Applies the same event twice
- Asserts the second application returns `"duplicate"` status
- Asserts only one event was recorded
- **Falsification path:** If the idempotency guard on `provider_event_id` were removed, the assertion `self.assertEqual(len(reply_events), 1)` would fail.

**Tests are not fake.** They mock the provider read (appropriate - no live API calls) but drive through the real write-back logic. The mocks replace the external input, not the internal logic.

**Test execution:**
```bash
$ python -m unittest tests.test_task387_writeback_demo -v
test_emailbison_send_is_written_to_record ... ok
test_idempotency_same_event_not_recorded_twice ... ok
test_reply_is_written_to_record ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.203s

OK
```

### 4. Would merging delete anything?

**NO.** The diff shows:

```bash
$ git diff master...6d91146a --diff-filter=D --name-only
docs/qwen-tasks/TODO/TASK-319-five-skills-as-executable-sops.md
docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md
docs/qwen-tasks/TODO/TASK-396-training-pair-capture-check.md
docs/qwen-tasks/TODO/TASK-407-glm-verify-task-399.md
docs/qwen-tasks/TODO/TASK-408-glm-verify-task-319.md
docs/qwen-tasks/TODO/TASK-414-spend-report-wiring-check.md
docs/qwen-tasks/TODO/TASK-420-docs-hygiene-pass.md
docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md
```

Only task files would be deleted (moved from TODO to REVIEW/DONE). No production code, tests, or documentation would be deleted.

**Full diff stats:**
```
100 files changed, 12725 insertions(+), 594 deletions(-)
```

The branch carries work from many tasks (86 commits), but TASK-387 itself only touched:
- `docs/qwen-tasks/REVIEW/TASK-387-ledger-write-back-of-provider-sends-and-replies.md` (moved from TODO)
- `tests/test_task387_writeback_demo.py` (added)

### 5. Scope drift

**NO.** TASK-387's commits are clean:

```bash
$ git log --oneline 6d91146a --not master | grep -i "TASK-387"
342c3211 TASK-387: move to REVIEW, suite running
c0ebd287 TASK-387: add RESULT BLOCK with trace findings
f5db204e TASK-387: trace shows provider write-back exists, demo test passes
5d88cf82 TASK-387: move to RUNNING
```

Files changed by TASK-387:
```bash
$ git diff 5d88cf82^..342c3211 --name-only
docs/qwen-tasks/REVIEW/TASK-387-ledger-write-back-of-provider-sends-and-replies.md
docs/qwen-tasks/TODO/TASK-387-ledger-write-back-of-provider-sends-and-replies.md
tests/test_task387_writeback_demo.py
```

No junk, no unrelated changes. The branch carries other tasks' work, but TASK-387 is isolated and clean.

### 6. Accuracy of the trace findings

The task's trace findings are **accurate**:

**Claim 1:** "EmailBison sends: `leadobserve.confirm_email_touches()` writes PUSH_MARKED, EMAIL_BOUNCED, EMAIL_DELIVERED"  
**Verified:** YES. `src/leadobserve.py:653-670` calls `events.record()` with these event types.

**Claim 2:** "HeyReach sends: `leadobserve.confirm_touches()` writes PUSH_MARKED"  
**Verified:** YES. `src/leadobserve.py:298-315` calls `events.record()`.

**Claim 3:** "Replies: `inbound.handle()` → `events.apply()` writes REPLY_RECEIVED"  
**Verified:** YES. `src/inbound.py:371` calls `events.apply()`, which calls `events.record()`.

**Claim 4:** "Bounces: same path as replies, writes EMAIL_BOUNCED"  
**Verified:** YES. Bounces are neutral events of type `EMAIL_BOUNCED` and follow the same path.

**Claim 5:** "Aggregate counters from `bison_watch_loop.py` go to heartbeat files, not records"  
**Verified:** YES. `scripts/bison_watch_loop.py` writes to `work/heartbeat/bison-<id>.json` and `work/watch-events/bison-<id>.jsonl`, not to per-lead records. This is campaign-level observability, not per-lead state.

**Claim 6:** "4 write-back paths, 1 read-and-discard path"  
**Verified:** YES. The count is accurate.

### 7. What the task did NOT do (and why that is correct)

The task did not add any production code. It added only a demo test. This is correct because the task instruction was:

> "Build only what the trace shows is missing."

The trace showed the write-back already exists, so no production code was needed. The demo test demonstrates the write-back path for verification purposes.

---

## Risks and Operational Notes

1. **Sends require manual reconciliation.** The write-back for sends exists but is not automated. If the operator does not run `python -m src.leadobserve --confirm --live`, the records are not updated. This is not a defect in TASK-387, but it is an operational characteristic worth naming. If automated send reconciliation is desired, that is a separate task.

2. **The demo test mocks the provider read.** This is appropriate for a demonstration test, but it means the test does not verify the provider API integration. The existing tests `test_the_provider_acting_alone_is_still_a_touch.py` and `test_the_send_is_recorded_once_and_by_the_provider.py` provide more comprehensive coverage of the real integration.

3. **The branch carries 86 commits from many tasks.** Merging requires cherry-picking or merging the entire branch. TASK-387 itself is clean, but the branch as a whole carries work from other tasks that may or may not be ready for merge.

---

## Reproducible Commands

All verification was performed in an isolated worktree at SHA `6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c`:

```bash
# Create worktree
git worktree add ../glm-review-task-504 6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c --detach

# Verify artifact exists
ls ../glm-review-task-504/tests/test_task387_writeback_demo.py

# Run tests
cd ../glm-review-task-504 && python -m unittest tests.test_task387_writeback_demo -v

# Check production callers
grep -rn "confirm_email_touches\|confirm_touches" ../glm-review-task-504/src/ --include="*.py"
grep -rn "inbound.ingest\|inbound.handle" ../glm-review-task-504/src/ --include="*.py"

# Check what would be deleted
git diff master...6d91146a --diff-filter=D --name-only

# Check TASK-387 specific changes
git diff 5d88cf82^..342c3211 --name-only
```

---

## Disposition

**MERGE** with the following understanding:

1. TASK-387 correctly traces the write-back paths and concludes they exist.
2. The demo test is valid and demonstrates the write-back logic.
3. The trace findings are accurate and verified.
4. No production code was added, which is correct given the task instruction.
5. The write-back for replies/bounces is automated; the write-back for sends is manual CLI only.

**Recommendation:** Accept the trace findings. If automated send reconciliation is desired, that is a separate task. TASK-387 itself is complete and correct.

---

## Evidence

- **Artifact exists:** `tests/test_task387_writeback_demo.py` at commit `f5db204e`
- **Production callers verified:**
  - Replies/bounces: `poller.run()` → `inbound.ingest()` → `events.apply()` (automated)
  - Sends: CLI `python -m src.leadobserve --confirm --live` (manual)
- **Tests pass:** 3/3 tests pass in 0.203s
- **No deletions:** Only task files would be deleted, no production code
- **No scope drift:** TASK-387 only touched its task file and added the demo test

---

**Verdict delivered:** 2026-09-29  
**Reviewer:** GLM (independent verification)  
**Target SHA:** 6d91146a9340cef5aeaad0ce28dbb3bd6e59bf3c  
**Disposition:** MERGE
