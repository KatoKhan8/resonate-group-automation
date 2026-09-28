# TASK-467 — Independent verification of TASK-221

## Review metadata

| Field | Value |
|-------|-------|
| Task reviewed | TASK-221 |
| Branch | `origin/qwen-worker-2-r50` |
| Branch HEAD SHA | `e3d60bdee84470dddaf5a01c2fd88b84e21101d4` |
| Verified at SHA | `e3d60bdee84470dddaf5a01c2fd88b84e21101d4` (confirmed via `git rev-parse`) |
| Merge base with master | `23a95720da44bcaccbef2eefcae610e3ffbf5d01` |
| Review worktree | `.qwen/worktrees/task467-verify` (detached at target SHA) |
| Master HEAD at review time | `caa7c513` |
| Disposition | **CLOSE — work already integrated and superseded on master** |

---

## 1. Does the artifact exist on this ref?

**YES.** The test file `tests/test_no_activation_without_an_exact_match.py` exists at the target SHA and runs green:

```
Ran 47 tests in 1.354s
OK (expected failures=4)
Exit code: 0
```

This matches the result block's claim of "47 tests ran, 0 failures, 0 errors, 4 expected failures. Exit code 0." **VERIFIED.**

The task file `docs/qwen-tasks/DONE/TASK-221-the-exact-match-gate-still-pins-yesterdays-shape.md` (131 lines) also exists on the branch.

---

## 2. Existence is not function — is every link consumed?

**YES, within the branch's own scope.** The test module is consumed by the standard test runner (`python -m unittest tests.test_no_activation_without_an_exact_match`). The tests exercise real production code through real entry points:

- `configdiff.compare_heyreach` and `configdiff.compare_bison` — the real comparison functions
- `configdiff.approved_heyreach` and `configdiff.approved_bison` — the real approved-side builders
- `executionguard.authorize` — the real authorization entry point
- `providerwrites.require_conditional_permission` — the real permission gate

The provider mocks patch real transport functions (`src.providers.heyreach.campaign_read`, `src.providers.bison.base`, etc.) and the test asserts on real diff verdicts, not on source text or `hasattr`. **Not disconnected.**

---

## 3. Falsification of the result's own claims

### 3.1 `STANDING_EMAIL_DEFECT = frozenset()`

**VERIFIED.** The diff shows the change from `{"actions"}` to `frozenset()`, and the test run confirms no standing email defect remains. Master has the same change at line 113.

### 3.2 Threaded email fixture

**VERIFIED.** The branch defines `THREADED_EMAIL_SEQUENCE` with three steps (em1/em2/em3), all referencing `{SUBJECT_1}`, with `thread_reply_pattern: [False, True, True]` and final `wait_in_days: 1`. The `_install_threaded_config` and `_write_email_copy` helpers wire it through the real cadence and approval paths.

### 3.3 Permission scope assertions (the four assertions)

**VERIFIED.** The test `test_email_activation_is_scoped_to_one_campaign` makes four real calls:
1. `is_supported(EMAIL_ACTIVATE)` → `True` ✓
2. `EMAIL_ACTIVATE in CONDITIONAL` ✓
3. `require_conditional_permission(EMAIL_ACTIVATE, "481", ...)` raises `WriteRefused` ✓
4. `require_conditional_permission(EMAIL_ACTIVATE, "485", "wrong-row")` raises `WriteRefused` ✓
5. `require_conditional_permission(EMAIL_ACTIVATE, "485", "productive-email-control-v2")` passes ✓

These are real function calls with real exception assertions, not `hasattr` or source-text checks.

### 3.4 `test_compare_bison_can_now_pass`

**VERIFIED.** The `@unittest.expectedFailure` was removed and the test asserts `configdiff.PASS`. The test run confirms it passes.

### 3.5 Every mutation still caught

**VERIFIED** by the test run. All 43 non-expectedFailure tests pass, and the 4 expectedFailures are the documented gaps (no-approved-copy, per-domain cap, daily limit, schedule).

### 3.6 `src/` was not modified

**VERIFIED.** `git diff master...origin/qwen-worker-2-r50 -- src/` returns empty.

---

## 4. Are the tests falsifiable?

**YES.** The mutation tests assert exact failing-field sets through the real comparison functions. A mutation test cannot pass unless the comparison genuinely fails to detect the change. The permission tests call real functions and assert real exceptions. The fingerprint tests mutate real campaign fields and assert real hash changes.

How could these pass while the implementation is wrong? Only if the production comparison functions were broken in a way that matched the fixture's exact mutation pattern — which would require a coincidental breakage across multiple independent fields simultaneously.

---

## 5. Would merging it DELETE anything?

**YES — and this is the critical finding.** Master has moved significantly ahead of the branch.

### Master vs branch comparison

| Metric | Branch | Master |
|--------|--------|--------|
| Test file lines | 941 | 1167 |
| Test count | 47 | 54 |
| Expected failures | 4 | 3 |
| `src/` changes | 0 | Multiple commits |

### What master has that the branch does not

Master has **7 additional tests** the branch lacks:

1. `test_a_follow_up_that_stopped_being_a_thread_reply` — mutation test for the threaded shape
2. `test_a_lead_holding_copy_nobody_approved` — per-lead copy mutation
3. `test_only_the_opener_carries_a_subject_variable` — subject variable invariant
4. `test_the_email_sequence_is_not_covered_and_it_defines_side_a` — fingerprint gap finding
5. `test_activation_names_exactly_one_campaign_on_each_channel` — unified permission assertion
6. `test_email_activation_refuses_every_campaign_but_the_authorized_one` — more thorough than branch's version, includes rebound/resize scenarios
7. `test_linkedin_activation_refuses_every_campaign_but_the_canary` — more thorough than branch's version, includes the 604869 refusal
8. `test_the_campaign_under_test_here_could_never_be_activated` — property preservation

### What master has CLOSED that the branch still has as expectedFailure

- **No-approved-copy gap**: Master has `test_an_email_campaign_with_no_approved_copy_is_refused` (line 722) which asserts the gap is CLOSED. The branch still has `test_an_email_campaign_with_no_approved_copy_should_not_pass` as `@unittest.expectedFailure`.

### Merge impact

Merging the branch would REPLACE master's 1167-line, 54-test file with the branch's 941-line, 47-test file. This would:

1. **DELETE 7 tests** that master has added
2. **RE-OPEN** the "no approved copy" gap (back to `@unittest.expectedFailure`)
3. **REPLACE** master's more thorough permission assertions (which test rebound/resize scenarios and the LinkedIn canary) with the branch's weaker ones
4. **LOSE** the `test_the_email_sequence_is_not_covered_and_it_defines_side_a` fingerprint finding

This is the exact merge damage the protocol warns about.

---

## 6. Scope drift

The branch carries **two files unrelated to TASK-221**:

1. `scripts/task183_results.json` — Modified by the top commit (`e3d60bde UNREVIEWED CHECKPOINT: TASK-183's run extended from 4 records to 10`). Extends results from 4 to 12 entries (10 processed + 2 timeouts). This is TASK-183 work.
2. `docs/qwen-tasks/DONE/TASK-221-the-exact-match-gate-still-pins-yesterdays-shape.md` — The task file itself. Not on master. Could be cherry-picked as a historical record.

The TASK-183 results JSON is scope drift and must not be merged as part of TASK-221.

---

## Findings

### Finding 1: Work fully superseded (CRITICAL)

**Severity**: Critical (merge would regress master)
**Evidence**: Master has 54 tests vs branch's 47; master has closed the no-approved-copy gap; master has more thorough permission assertions including rebound/resize scenarios.
**Detail**: Every change the branch made has been incorporated into master through subsequent commits (`9b022770`, `2e3eacc2`, `5982599e`, `b7e1622d`, `d0b2bf9e`), and master has gone further.

### Finding 2: Scope drift — TASK-183 results JSON

**Severity**: Suggestion
**Evidence**: `scripts/task183_results.json` modified by commit `e3d60bde`, which is TASK-183 work, not TASK-221.
**Detail**: The file extends from 4 to 12 results. This is legitimate TASK-183 output but does not belong in a TASK-221 merge.

### Finding 3: Task file not on master

**Severity**: Nice to have
**Evidence**: `docs/qwen-tasks/DONE/TASK-221-the-exact-match-gate-still-pins-yesterdays-shape.md` exists only on the branch.
**Detail**: The task file records the work done and could be cherry-picked as a historical record, but the code changes it describes must not be merged.

---

## Recommendation

**CLOSE.** The branch's work was correct and valuable at the time it was done. All 47 tests pass, the fixture updates are sound, and the permission scope assertions are real. However, master has since received all of these changes plus additional improvements through five subsequent commits. Merging the branch would actively regress the test suite from 54 tests to 47, re-open a closed safety gap, and replace more thorough assertions with weaker ones.

**No merge. No cherry-pick of the test file.** The task file could be cherry-picked separately if historical record is desired, but the code changes are already on master in a more advanced form.
