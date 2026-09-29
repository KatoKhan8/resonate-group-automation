# GLM Verdict: TASK-349 — provider sends and replies write-back to the action ledger

**Reviewing branch:** `origin/qwen-worker-6-r68`
**Branch HEAD SHA:** `c92175e7a15f820f173e1cf466587ba602ec6f03`
**Verified SHA:** `git rev-parse origin/qwen-worker-6-r68` → `c92175e7a15f820f173e1cf466587ba602ec6f03` ✅ MATCH
**Worktree:** `.qwen/worktrees/task491-review` (detached HEAD at target SHA)
**Date:** 2026-09-29

---

## 1. Does the artifact exist, and does it do what the result block claims?

**VERIFIED.** Three production files changed, one test file added:

| File | Change |
|------|--------|
| `src/actionledger.py` | +57 lines: `PROVIDER_SENT`, `PROVIDER_REPLIED` states; `record_provider_event()` function |
| `src/inbound.py` | +51/-1 lines: `actionledger` import; `_LEDGER_KINDS` map; `_write_back_to_ledger()` helper; call from `handle()` |
| `tests/test_a_send_and_a_reply_both_leave_a_row.py` | +265 lines: NEW, 10 tests |

The task file moved from `docs/qwen-tasks/TODO/` to `docs/qwen-tasks/REVIEW/` (the 73 deletions in the diff stat). No production code was deleted.

**Claims verified:**
- ✅ `record_provider_event` is idempotent on `provider_event_id` (key = `obs:{provider_event_id}`, checked before append)
- ✅ Two timestamps recorded: `provider_timestamp` (from event) and `observed_at` (from `store.now()`), stored as distinct fields
- ✅ Returns `None` on replay, row dict on first write
- ✅ Raises `ActionRefused` when `provider_event_id` is empty/missing
- ✅ New states NOT in default `count_on` states — observations never inflate daily cap

## 2. Existence is not function — is every link consumed?

**VERIFIED.** Full caller chain traced on the branch:

```
poller.py:471  →  inbound.ingest()
inbound.py:601  →  inbound.handle()  (inside list comprehension over neutral events)
inbound.py:484  →  _write_back_to_ledger()
inbound.py:391  →  actionledger.record_provider_event()
actionledger.py:478  →  definition
```

`_write_back_to_ledger` has exactly TWO references in `src/`: its definition (line 376) and its call (line 484). `record_provider_event` has exactly TWO references: its definition (line 478) and its call from `_write_back_to_ledger` (line 391). No orphan code.

The chain enters from `poller.run()` which is the production entry point for provider event polling. **The wiring is real and complete.**

## 3. Falsification — mutation test

**REPRODUCED INDEPENDENTLY.** Removed the `_write_back_to_ledger` call from `handle()` (replaced with `pass`):

```
Ran 10 tests — FAILED (failures=6)
```

All 6 failures are `0 != N` assertions on ledger row counts — exactly the expected "missing row" failures:
- `test_send_writes_exactly_one_row`: `0 != 1`
- `test_replay_writes_no_additional_row`: `0 != 1`
- `test_two_different_sends_write_two_rows`: `0 != 2`
- `test_reply_row_carries_contact_key_and_both_timestamps`: `0 != 1`
- `test_reply_replay_writes_no_additional_row`: `0 != 1`
- `test_two_different_replies_write_two_rows`: `0 != 2`

The 4 tests that still pass are those that don't depend on the write-back actually firing (guard mock test, missing-ID test, two daily-count tests). **No different guard fired first.** The failures are specifically and correctly about missing ledger rows.

Restored the call: 10/10 green. ✅

## 4. Are the tests falsifiable?

**YES.** The tests assert on:
- Exact row counts in the ledger (not `hasattr` or source text)
- Specific field values (`state`, `provider`, `channel`, `contact_key`, `provider_event_id`, `provider_timestamp`, `observed_at`)
- Inequality of the two timestamps (not just presence)
- Idempotency (replay writes nothing)
- Daily count isolation (observations don't inflate `count_on`)

The mutation test above proves the tests detect the absence of the wiring. A fake implementation that returned canned data would fail the field-value assertions. **These tests prove function, not existence.**

## 5. Would merging delete anything?

**NO.** `git diff master...c92175e7 --stat -- src/ tests/` shows:

```
src/actionledger.py                               |  57 +++++
src/inbound.py                                    |  51 +-
tests/test_a_send_and_a_reply_both_leave_a_row.py | 265 ++++++
3 files changed, 372 insertions(+), 1 deletion(-)
```

The single deletion in `src/inbound.py` is the import line being reformatted (adding `actionledger` to the import block). **Zero production lines deleted. Zero files removed.**

The 73 deletions in the full diff stat are the task file moving from `TODO/` to `REVIEW/`.

## 6. Scope drift

**CLEAN.** The branch carries exactly three commits beyond its merge base:

```
9773039c TASK-349 to RUNNING
cbccbc8e TASK-349: provider sends and replies write back
c92175e7 TASK-349 to REVIEW
```

All three are TASK-349 housekeeping and implementation. No unrelated changes, no scratch files, no accidental edits. Cherry-pick would be straightforward — the three src/test files are self-contained.

---

## Additional findings

### Pre-existing test failures on the branch (NOT caused by TASK-349)

Two failures in `test_a_resume_leaves_a_ledger_row` appear when running on this branch but NOT on current master:
- `test_email_resume_is_supported_but_linkedin_is_not`: `'refused' != 'unverified'`
- `test_neither_is_supported`: `'bison.resume' unexpectedly found in SUPPORTED`

Both `providerwrites.py` and the test file are byte-identical between master and this branch. The failures arise because the branch was forked from an older master (`2e1e55a5`) and some transitive dependency has changed on master since. **These are branch-age artifacts, not TASK-349 defects.** They will resolve on rebase.

### Acceptance 4 (live reconciliation) is honestly OWED

The result block correctly reports that reconciling provider send/reply counts against ledger rows requires Claude's worktree with live queue access. This is not a defect — it's a scope limitation that was correctly flagged.

### Design quality

The design is sound:
- `obs:` key prefix cleanly separates observation rows from reservation rows
- `_write_back_to_ledger` never raises — a ledger failure cannot break the reply path
- Only `EMAIL_DELIVERED` and `REPLY_RECEIVED` trigger write-back, via an explicit mapping (`_LEDGER_KINDS`)
- The `kind` parameter to `record_provider_event` uses the module constants, not raw strings
- The bare `except` in `_write_back_to_ledger` is intentional and documented (ledger failure must not stop classification/pause/notification)

---

## Disposition

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | Artifact exists and matches claims | VERIFIED | Tests pass, code matches result block |
| 2 | Full caller chain is connected | VERIFIED | poller → ingest → handle → _write_back_to_ledger → record_provider_event |
| 3 | Mutation test falsifies correctly | VERIFIED | 6 tests fail with `0 != N` when write-back removed |
| 4 | Tests are falsifiable | VERIFIED | Assert on row counts, field values, timestamp inequality |
| 5 | Merge deletes nothing | VERIFIED | +372/-1 in src/tests; 73 deletions are task file move |
| 6 | No scope drift | VERIFIED | 3 commits, all TASK-349 |
| 7 | Acceptance 4 (live reconciliation) | OWED | Correctly flagged by worker; needs Claude's worktree |

---

## Recommendation: **MERGE**

TASK-349 is clean, well-tested, correctly wired, and honestly reported. The one owed item (acceptance 4) is correctly flagged and does not block integration. The design respects every rule the task named: idempotency, two timestamps, nothing subtracts, no provider writes, no second ledger.

The branch has two pre-existing test failures from branch age that will resolve on rebase and are not caused by this task's changes.
