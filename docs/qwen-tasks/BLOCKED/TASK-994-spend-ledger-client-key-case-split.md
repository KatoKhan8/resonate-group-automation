# TASK-994 — spend is split across two spellings of one client

STAGE: BLOCKED
PRIORITY: P1

## DISPATCH CONFLICT — REPORTED 2026-10-13

This task was assigned to this branch (qwen-worker-5-r9) but is already
completed by qwen-worker-10-r9 and sitting in REVIEW on that branch.

**Evidence:**

1. The task file does not exist in `docs/qwen-tasks/TODO/` on master — it was
   claimed by qwen-worker-10-r9 (commit b0f042aca) and moved to REVIEW
   (commit 8eaec62f0).
2. `git log --all --grep="TASK-994"` shows the implementation commits on
   qwen-worker-10-r9:
   - `faad44e5c TASK-994: normalise spend ledger client key to lowercase on write`
   - `8eaec62f0 TASK-994: move to REVIEW after implementing client key normalisation`
3. The implementation on qwen-worker-10-r9 was verified by checking out the
   files and running the test suite: 11 new tests in
   `tests/test_spend_ledger_client_key_is_normalised.py` all pass, and all 28
   existing spend ledger tests still pass (39 total, 0 failures).
4. Master does not yet have this work integrated (`git log master --grep="TASK-994"`
   returns nothing), so the task appears "open" from master's perspective, but
   the work is done and waiting for review.

**What qwen-worker-10-r9 did (verified):**

- Normalised client key to lowercase in `src/spendledger.py`: `record()`,
  `spent()`, `reserved()`, and `Hold.__init__()`.
- Added coverage reporting to `src/web/api.py` `spend_ledger()`: reports how
  many rows had a known client vs unknown/unattributed.
- Created `tests/test_spend_ledger_client_key_is_normalised.py` with 11 tests
  proving two spellings cannot both exist in the ledger.
- Documented the 111 "unattributed" rows as the operator's decision gate per
  the task acceptance criteria.

**This branch's action:** STOP. Do not duplicate the work. Claude will integrate
qwen-worker-10-r9's branch after review.

## Measured 2026-10-12 over all 20,446 rows of `work/spend-ledger.jsonl`

    productive       18,128 rows       19,242 micro-USD
    Productive        2,087 rows            0 micro-USD
    unattributed        111 rows      716,699 micro-USD
    TOTAL            20,446 rows    3,352,099 micro-USD   (~$3.35)

Two findings.

**1. The client key is case-split.** 2,087 rows are filed under `Productive`. A
spend reader filtering on `productive` does not see them. This is the same class
of defect the standing rule already names — *a spend reader that filters a
retired tenant reports a clean zero while watching nothing* — arriving through
capitalisation rather than through tenancy.

**2. 111 rows are literally `unattributed`, carrying 716,699 micro-USD** — about
21% of all recorded spend, and the largest single bucket after the
task-attributed model calls. The standing rule is that model spend is attributed
to a client or a task and is never left unattributed.

This is one of the operator's named decision gates, so the disposition of the
111 rows is the operator's call, not this task's.

## Acceptance

- Normalise the client key on write, plus a test proving two spellings cannot
  both exist.
- Attribute the 111 rows, or record why they cannot be and what was lost.
- A reader that reports its own COVERAGE: how many rows it matched and how many
  it did not, so a filter that watches nothing says so out loud.

## RESULT BLOCK

STATUS: BLOCKED (dispatch conflict — task already completed by qwen-worker-10-r9)
COMMIT: N/A (this branch did no implementation work)
TESTS: N/A (implementation verified on qwen-worker-10-r9: 11 new tests + 28
       existing spend tests = 39 total, all passing)
FILES CHANGED: None (this branch only created this task file with the conflict report)

FINDINGS:
  1. TASK-994 is already implemented on qwen-worker-10-r9 (commits faad44e5c,
     8eaec62f0) and is in REVIEW. The implementation normalises the client key
     to lowercase on write in `src/spendledger.py` (record, spent, reserved,
     Hold.__init__) and adds coverage reporting to `src/web/api.py` spend_ledger().
  2. The implementation was verified by checking out the files from qwen-worker-10-r9
     and running the full spend test suite: 11 new tests in
     `tests/test_spend_ledger_client_key_is_normalised.py` all pass, and all 28
     existing spend ledger tests still pass (39 total, 0 failures).
  3. Master does not yet have this work integrated, so the task appears "open"
     from master's perspective, but the work is done and waiting for review.
  4. This is a dispatch conflict: the task was assigned to multiple workers
     (qwen-worker-10-r9 and qwen-worker-5-r9), but qwen-worker-10-r9 claimed it
     first (commit b0f042aca) and completed it. The task queue may have a race
     condition or stale state that caused the duplicate assignment.

RISKS:
  - If this branch proceeds with duplicate implementation, it will create merge
    conflicts with qwen-worker-10-r9's work.
  - The dispatch conflict suggests the task queue may not be tracking claims
    accurately across branches.

RECOMMENDED CLAUDE ACTION:
  1. Review and integrate qwen-worker-10-r9's TASK-994 work (it is verified correct).
  2. Investigate why multiple workers were assigned the same task — the task file
     was claimed on qwen-worker-10-r9 but still appeared in TODO for other workers.
  3. Close this task as BLOCKED (dispatch conflict) on qwen-worker-5-r9.
