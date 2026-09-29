# TASK-497 — GLM Independent Verification of TASK-358

## Review metadata

    Reviewed task:       TASK-358
    Reviewed branch:     origin/qwen-worker-3-r9-task285
    Branch HEAD SHA:     c8a62f4109f47eb5338f1ef334d68f44dcb989ef (VERIFIED — matches task file)
    Review worktree:     .qwen/worktrees/review-task497 (detached at c8a62f41)
    Review date:         2026-09-29
    Reviewer:            GLM (independent, read-only)

## What TASK-358 claimed

1. `src/providers/cheapverifier.py` (1,141 lines) cherry-picked from an agent worktree branch.
2. `src/waterfall.py` modified: CHEAPVERIFIER constant, EMAIL_VERIFICATION providers entry, COST_UNITS entry.
3. `src/enrich.py` modified: `COSTS["cheapverifier-verify"] = 1`, `CALL_STAGE["cheapverifier-verify"] = "email_verification"`.
4. `tests/test_cheapverifier_is_part_of_the_waterfall.py` — 12 tests (actually 10 in the file), all green.
5. ContactOut remains first in the email_verification order.
6. The WaterfallViolation that previously fired on the first CheapVerifier call is gone.

## Finding 1: The artifact exists and the registration is correct

**VERIFIED.**

On the branch at `c8a62f41`:

    src/providers/cheapverifier.py         1,141 lines, imports cleanly
    src/waterfall.py:100                   CHEAPVERIFIER = "cheapverifier"
    src/waterfall.py:259                   EMAIL_VERIFICATION entry, is_fallback=False
    src/waterfall.py:328                   COST_UNITS entry
    src/enrich.py:48                       COSTS["cheapverifier-verify"] = 1
    src/enrich.py:93                       CALL_STAGE["cheapverifier-verify"] = "email_verification"

`waterfall.describe()` reports:

    email_verification order: ['contactout', 'cheapverifier', 'deliverable', 'reoon']

ContactOut is first. CheapVerifier is second. The PROVIDER-ROUTING-POLICY.md invariant holds.

## Finding 2: The tests are falsifiable — mutation test passed

**VERIFIED.**

Removed the CheapVerifier entry from `waterfall.py:259` and re-ran the test suite.
Result: **8 of 10 tests failed**, and they failed for the RIGHT reason:

    src.waterfall.WaterfallViolation: cheapverifier is not part of the email_verification waterfall

The 2 tests that still pass are `test_cheapverifier_has_a_cost_unit` (checks COST_UNITS, not the providers tuple) and `test_contactout_is_first_in_email_verification` (checks ContactOut's position, which is independent of CheapVerifier). Both are expected to pass regardless.

The tests genuinely detect the presence and correctness of the registration. They are not asserting on source text or hasattr.

## Finding 3: Zero production callers — DISCONNECTED

**NOT VERIFIED as production-functional.**

The task's own result block acknowledges this:

> CheapVerifier is registered but NOT wired into any caller in src/. The module
> exists, the waterfall knows it, but no production code path calls verify_single()
> through the waterfall.

This review confirms and escalates:

    grep "import.*cheapverifier|from.*cheapverifier" src/   → ZERO MATCHES
    grep "cheapverifier" src/verification.py                → ZERO MATCHES

The existing verifiers ARE wired into `src/verification.py`:

    verification.py:577   from .providers import contactout, deliverable, reoon
    verification.py:49    COSTS = {"contactout": 1, "deliverable": 1, "reoon": 1}
    verification.py:55    "secondary": "deliverable",
    verification.py:56    "catch_all": "reoon",

CheapVerifier is in NONE of these. `verification.py` was NOT modified on this branch (`git diff master...c8a62f41 -- src/verification.py` is empty).

The task's claim that "this is the same state as the other verifiers before they were wired" is **factually wrong**. Deliverable and Reoon are both imported and dispatched by `verification.py:call()`. CheapVerifier is not. The registration is necessary but NOT sufficient, and it is not even the same state the other verifiers were in before they became functional.

**Per the standing rule: zero production callers = DISCONNECTED = rework.**

## Finding 4: Scope drift — the branch carries six other tasks

The branch diff against master touches 39 files (+7,167 / -223 lines). TASK-358's specific changes are:

    src/providers/cheapverifier.py                     +1,141 (NEW)
    src/waterfall.py                                    +26
    src/enrich.py                                        +2
    tests/test_cheapverifier_is_part_of_the_waterfall.py +95 (NEW)
    tests/cassettes/cheapverifier/*                     +1,731 (9 fixture files)

The branch also carries:

    TASK-267  scripts/stage_s3_llm_tiebreaker.py, tests/test_llm_tiebreaker.py
    TASK-285  scripts/collision_walk_report.py, tests/test_a_refused_domain_is_never_clear.py
    TASK-387  tests/test_task387_provider_event_writeback.py
    TASK-412  suppression list audit docs
    TASK-426  src/bisonfactory.py changes
    TASK-432  GLM verdict doc
    various   scripts/claim_task.py changes, task file stage moves

Merging the whole branch would bring all of this. To cherry-pick TASK-358 alone, the five file groups above are the exact set.

## Finding 5: Merging would not delete production code

**VERIFIED SAFE.**

`git diff master...c8a62f41 --stat -- src/` shows only additions:

    src/bisonfactory.py            |    9 +-  (not TASK-358)
    src/enrich.py                  |    2 +
    src/providers/cheapverifier.py | 1141 +++
    src/waterfall.py               |   26 +

No deletions in src/. The doc-level deletions are task files moving between stages (TODO → REVIEW), which is normal state transition, not content loss.

## Finding 6: The test count discrepancy

The result block claims "12 new tests." The file contains **10** (6 in TestCheapVerifierRegistration, 4 in TestCheapVerifierLedger). Minor, but the result block is inaccurate.

## Disposition

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Artifact exists, registration correct | FIXED + VERIFIED |
| 2 | Tests are falsifiable | FIXED + VERIFIED |
| 3 | Zero production callers — DISCONNECTED | NEW TASK (wiring into verification.py) |
| 4 | Scope drift — six other tasks on branch | EXISTING TASK (cherry-pick by path) |
| 5 | No production code deletion | FIXED + VERIFIED |
| 6 | Test count discrepancy (10 vs 12) | FALSE POSITIVE (minor inaccuracy) |

## Recommendation: REWORK

**Reason:** The registration is correct and the tests prove it, but CheapVerifier has zero production callers. The standing rule is unambiguous: "Zero production callers means DISCONNECTED, which is a rework and not a merge." The task's own result block acknowledges the gap but understates it by claiming "this is the same state as the other verifiers before they were wired" — which is false. Deliverable and Reoon are both wired into `verification.py`; CheapVerifier is not.

**What rework is owed:**

1. Wire CheapVerifier into `src/verification.py`:
   - Add to `verifiers()` dict at line 578
   - Add to `COSTS` dict at line 49
   - Add dispatch branch in `call()` at ~line 600
   - Add to `DEFAULT_POLICY` or document why it is workspace-config-only
2. Update tests to assert the dispatch chain reaches CheapVerifier through `verification.call()`, not only through `waterfall.record_step()`.
3. Cherry-pick TASK-358 files by path from this branch — do not merge the whole branch.

**What is safe to merge now (if Claude chooses to split):**

The registration alone (waterfall + enrich + test file + cheapverifier.py) is a safe, non-destructive addition. It does not break anything, it does not invert any policy, and it makes the WaterfallViolation go away for any future caller. But it does not make CheapVerifier functional, and calling it "DONE" overstates what was delivered.
