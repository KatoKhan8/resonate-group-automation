# TASK-436 — GLM Independent Verification of TASK-264

## Review metadata

| Field | Value |
|-------|-------|
| Target task | TASK-264 — every test module runs in isolation |
| Target branch | origin/qwen-worker-4-r9 |
| Target SHA (per task file) | e05f401e6b3126bd248a7a54c14b3ba86828c73a |
| Actual HEAD at fetch time | 2cb8755afc8ad069ccab24a6d80819d779c57e54 |
| Branch movement | **YES — branch moved.** Per task instructions, reviewed e05f401e anyway. |
| Review worktree | .qwen/worktrees/task436-review (detached at e05f401e, now removed) |
| Reviewer | GLM (Qwen session, TASK-436) |
| Date | 2026-09-28 |

---

## 1. Does the artifact exist on this ref?

**YES — artifact verified at e05f401e.**

Three files carry TASK-264's changes:

| File | Change | Verified |
|------|--------|----------|
| `tests/base.py` | Added `ISOLATE_VARS` tuple, `save_env()`, `restore_env()` helpers; expanded `QueueTest.setUp/tearDown` and `ProviderTest.setUp` to use them | YES |
| `tests/test_invariants.py` | Replaced `PinsTheRealStatePaths` mixin with `_ClearsStateOverrides` using shared helpers | YES |
| `tests/test_no_test_leaves_the_environment_changed.py` | Added `PerTestIsolationWorks` class with 4 proof tests | YES |

`PinsTheRealStatePaths` no longer exists as a live class — only referenced in historical comments. `grep -rn "PinsTheRealStatePaths" tests/ src/` returns only comment hits.

---

## 2. Existence is function — is the mechanism consumed?

**YES — heavily consumed.**

225 test classes inherit from `QueueTest` or `ProviderTest`. Every one of them now gets per-test environment isolation through the shared `save_env()`/`restore_env()` mechanism. The chain is:

```
QueueTest.setUp() → save_env() → [test runs] → tearDown() → restore_env()
ProviderTest.setUp() → save_env() → [test runs] → addCleanup(restore_env)
```

`_ClearsStateOverrides` in `test_invariants.py` also consumes `save_env()`/`restore_env()` from `tests/base.py`, replacing its own inline implementation.

This is not a function without callers. It is the default path for the majority of the test suite.

---

## 3. Falsification of the result's own claims

### Claim: "per-test isolation restores env vars after each test"

**VERIFIED by direct mutation test.** I constructed a `LeakyQueueTest` subclass that sets `CAMPAIGNS` and `QUEUE_BACKEND` during a test, ran it through `unittest.TestSuite`, and confirmed both variables were `None` afterwards:

```
CAMPAIGNS after: None (should be None)
QUEUE_BACKEND after: None (should be None)
Result errors: []
Result failures: []
PASS: isolation actually works
```

### Claim: "15/15 pass in test_no_test_leaves_the_environment_changed"

**VERIFIED.** Ran the full module at e05f401e:

```
Ran 15 tests in 21.418s
OK
```

### Claim: "test_invariants: 83/85 pass (2 pre-existing failures)"

**PARTIALLY VERIFIED — with a caveat.**

On master (main worktree, which has `work/`): 85 tests, 2 failures (reviewapproval checklist, emailbison route). Matches the result block.

On the review worktree (detached at e05f401e, no `work/` dir): 85 tests, 2 failures + 1 error. The error is `test_nothing_was_written_by_that` in `TestTheBarrierCoversEveryWriter`, which fails with `FileNotFoundError` because `store.PRODUCTION_WORK` does not exist in the worktree. This is a **worktree artifact**, not a TASK-264 regression — the same test passes on master in a tree with `work/`.

### Claim: "No test deleted, skipped or weakened"

**VERIFIED.** The diff for `tests/test_invariants.py` shows only the mixin replacement (`PinsTheRealStatePaths` → `_ClearsStateOverrides`). No test method was removed, no assertion changed, no skip added.

### Claim: "PinsTheRealStatePaths folded in"

**VERIFIED.** The class is gone. `_ClearsStateOverrides` uses `save_env()`/`restore_env()` from `tests/base.py`. One mechanism serves both use cases.

---

## 4. Are the tests falsifiable?

**YES.** The proof tests in `PerTestIsolationWorks` and `TheIsolationItselfWorks`:

- Construct real `QueueTest` subclasses that mutate real env vars
- Run them through `unittest.TestSuite.run()`
- Assert the env vars are restored to their pre-test state (including absence)
- Test both directions: new var created → restored to absent; existing var changed → restored to old value

These are NOT:
- `hasattr` checks
- Assertions on source text
- Token-in-file checks
- Fake cassettes

If `restore_env` were a no-op, or `save_env` missed a variable, the tests would fail. The mechanism is proved by observation of behaviour, not by inspection of code.

---

## 5. Would merging DELETE anything?

**No production code or test deletions.** The branch deletes 5 task files from `docs/qwen-tasks/TODO/`:

```
TASK-264-every-test-module-runs-in-isolation.md  (→ REVIEW)
TASK-279-the-19612-packs-arrive-in-chunks-or-not-at-all.md  (→ REVIEW)
TASK-408-glm-verify-task-319.md  (→ REVIEW)
TASK-414-spend-report-wiring-check.md  (→ REVIEW)
TASK-422-heyreach-seat-cap-check.md  (→ BLOCKED)
```

These are queue-progress moves (TODO → REVIEW/BLOCKED), not content deletions. No source, test, or documentation files are deleted.

---

## 6. Scope drift

**SIGNIFICANT.** The branch carries 40+ commits from many tasks beyond TASK-264:

- TASK-245, TASK-246, TASK-264, TASK-285, TASK-326
- TASK-408, TASK-414, TASK-422, TASK-423, TASK-426, TASK-427, TASK-429
- Handoff documents, safety commits, suite triage, collision walk reports
- New scripts: `pack_fetch.py`, `collision_walk_report.py`, `qa/check_readback.py`, `stage_work_to_host.sh`
- New source modules: `enrollmenttags.py`, `secondbrain.py` additions
- Config changes: `productive-offers.yaml`
- State files: `LEDGER.json` (8219 lines changed), `QUEUE-MANIFEST.json`, `TASK-REGISTRY.json`

TASK-264's own changes are isolated to 3 commits (`fc6dcaee`, `1417eac1`, `d945ef7e`) touching 3 files. **Cherry-pick is required** — merging the whole branch to get TASK-264 would bring the entire workforce report, the offers validation, the enrollment tags, and the ledger changes along with it.

---

## Findings

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | Artifact exists and is consumed by 225 test classes | — | VERIFIED |
| 2 | save_env/restore_env correctly isolates per-test | — | VERIFIED by mutation |
| 3 | 15/15 proof tests pass at e05f401e | — | VERIFIED |
| 4 | PinsTheRealStatePaths fully replaced, one mechanism remains | — | VERIFIED |
| 5 | No test deleted, skipped or weakened | — | VERIFIED |
| 6 | Branch carries 40+ commits from 12+ other tasks | Scope | Cherry-pick required |
| 7 | test_invariants error in worktree is environmental, not a regression | — | NOT A DEFECT |

---

## Disposition

**MERGE (cherry-pick).**

TASK-264 is correct, well-tested, and consumed. The isolation mechanism is the real article: it saves and restores the full `ISOLATE_VARS + store.STATE_OVERRIDES` set (34+ variables) around every test in `QueueTest` and `ProviderTest`, and the proof tests genuinely falsify the claim rather than asserting on source text.

The branch has significant scope drift and must not be merged wholesale for this task. The three TASK-264 commits (`fc6dcaee`, `1417eac1`, `d945ef7e`) touching `tests/base.py`, `tests/test_invariants.py`, and `tests/test_no_test_leaves_the_environment_changed.py` are clean and self-contained.

### What to cherry-pick

```
fc6dcaee TASK-264: claim and move to RUNNING
1417eac1 TASK-264: per-test environment isolation in QueueTest and ProviderTest
d945ef7e TASK-264: result block and move to REVIEW
```

Files:
- `tests/base.py`
- `tests/test_invariants.py`
- `tests/test_no_test_leaves_the_environment_changed.py`
- `docs/qwen-tasks/REVIEW/TASK-264-every-test-module-runs-in-isolation.md` (task file move)

### Residual risk

The result block acknowledges the full suite could not be run to completion (timeout in `test_demo_smoke`). The per-test isolation is conservative (save/restore, not clear) and should not break any previously-passing test. If a test depended on a leak from a previous `QueueTest`, it will now see a clean environment — which is the intended behaviour, but may surface new order-dependent failures in modules that were not individually verified.
