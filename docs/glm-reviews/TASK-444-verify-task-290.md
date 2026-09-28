# TASK-444 — GLM Independent Verification of TASK-290

## Review metadata

    REVIEWER:           GLM (Qwen-3 session)
    TARGET TASK:        TASK-290
    TARGET BRANCH:      qwen-worker-9-r9
    BRANCH HEAD SHA:    f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    VERIFIED HEAD:      f1b9c357c17f4b557cbdb06f68339c7343ef3e83 (confirmed via git rev-parse)
    BRANCH MOVED:       No — HEAD still matches the SHA named in the task file
    START_MASTER_SHA:   master at time of review (read-only; not used as review target)
    WORKTREE:           .qwen/worktrees/review-444 (detached at f1b9c357)
    DATE:               2026-09-28

## What TASK-290 claims

TASK-290 was a second-pass task after TASK-277's copylint wiring was found to be
disconnected (wired into `src/push.py` via `push.run_with_copylint`, which is
called by nothing, in a module whose `run()` raises on `live=True`).

TASK-290's result block claims:
1. A new test file `tests/test_the_lint_refuses_the_real_push.py` with 4
   assertions driven through `bisonfactory.stage` (the REAL send path)
2. All 4 tests are GREEN
3. Breaking `_refuse_copylint` causes all 4 to fail (mutation test)
4. The copylint wiring was landed by another lane during this task
5. `outreachclaims` is NOT reachable from the send path
6. A general no-caller check is specified in `docs/COPYLINT-SECOND-PASS-2026-09-25.md`

## Finding 1: Artifacts exist — VERIFIED

    tests/test_the_lint_refuses_the_real_push.py   EXISTS (281 lines, 4 tests)
    docs/COPYLINT-SECOND-PASS-2026-09-25.md         EXISTS (202 lines)
    docs/qwen-tasks/REVIEW/TASK-277-*.md            EXISTS (appended REVIEW block)

All three files named in the result block are present on the branch at the
exact SHA `f1b9c357`. The commit that created them is `579cc624`.

## Finding 2: Existence is function — VERIFIED, THE WIRING IS REAL

The production call chain, traced by reading `src/bisonfactory.py`:

    bisonfactory.stage() [line ~60]
      → _plan()                                    # no provider call
      → _refuse_copylint(plan, recs, report)       # line 87 — THE LINT
      → _refuse_sequence_gate(plan, report)        # line ~97
      → bison.bound_workspace()                    # line ~107 — FIRST PROVIDER CALL
      → _find_or_create / _ensure_*                # provider writes follow

`_refuse_copylint` (line 581) calls `_copylint_report` which calls
`copylint.check_batch`. The lint runs at position 3 in the chain; the first
provider call is at position 5. The lint is CONSUMED.

This is NOT the same defect as TASK-277. The wiring is in the real send path,
not in a dead module.

## Finding 3: Tests pass — VERIFIED

    $ python -m unittest tests.test_the_lint_refuses_the_real_push -v
    test_a_batch_with_a_lint_violation_cannot_be_staged ... ok
    test_a_rule_added_later_is_enforced_without_touching_the_call_site ... ok
    test_the_lint_runs_before_any_provider_write ... ok
    test_the_refusal_names_the_lead_and_the_rule ... ok
    Ran 4 tests in 0.112s — OK

The companion file (`test_the_copy_lint_refuses_the_real_send_path.py`) runs
10 tests: 7 pass, 3 ERROR. The 3 errors are from the sequence gate
(`_refuse_sequence_gate`), not the lint — the test fixture lacks
`qualification` and `claims_supported` fields. This matches the result
block's claim exactly.

## Finding 4: Mutation test — VERIFIED

Replacing `_refuse_copylint` with a no-op (`lambda plan, recs, report: None`):

    Ran 4 tests in 0.110s — FAILED (failures=4)

All 4 tests fail when the wiring is broken:
- test 1: no "dash" in refusal (sequence gate refuses instead, with different text)
- test 2: no lead id in refusal (same reason)
- test 3: "copy lint" not found in refusal message (sequence gate message appears)
- test 4: invented rule name not found (same reason)

The tests test the CONNECTION between `bisonfactory.stage` and `copylint`,
not the lint logic in isolation. Breaking the wiring breaks the tests.

## Finding 5: outreachclaims reachability — VERIFIED

    $ grep -rn "outreachclaims" src/ scripts/
    src/contextpack.py:57:  from . import (account, outreachclaims, ...)
    src/web/api.py:44:      ... outreachclaims ...
    campaignqa.py:33:       from . import outreachclaims as oc

`outreachclaims` is imported by `contextpack.py` and `campaignqa.py`.
`contextpack` is NOT imported by `bisonfactory.py`, `push.py`, or
`batch1_push.py`. The chain exists but does not reach the send path.

Claim verified: outreachclaims is NOT on the send path.

## Finding 6: Deletion risk — NONE

    $ git diff master...f1b9c357 --stat --diff-filter=D
    ...TASK-392-signature-per-attested-mailbox-verification.md | 37 ----
    ...TASK-399-docs-hygiene-pass.md                           | 39 ----

Both "deleted" files are task queue files that moved from TODO/ to REVIEW/ —
normal queue progression, not data loss. Verified both exist in REVIEW/ on
the branch.

No production code, configuration, or data files would be deleted by merge.

## Finding 7: Scope drift — SIGNIFICANT but TASK-290 is CLEAN

The branch carries 64 changed files / 6,818 insertions across ~30 commits
from many tasks (TASK-290, 305, 313, 318, 364, 391, 397, 399, 400, 402,
403, 404, 416, 423, 424, 425, and others).

TASK-290's own commit (`579cc624`) is clean:

    docs/COPYLINT-SECOND-PASS-2026-09-25.md            | 202 +++
    docs/qwen-tasks/REVIEW/TASK-277-copylint-wiring-tests.md | 41 ++
    tests/test_the_lint_refuses_the_real_push.py       | 281 +++
    3 files changed, 524 insertions(+)

All additive, no deletions, no edits to production code. Cherry-pickable
in isolation from the rest of the branch.

## Finding 8: Test falsifiability — STRONG

The tests are well-designed against the repository's recurring defect
(guard module with no production caller):

- They drive through `bisonfactory.stage`, not the lint directly
- They use a `_CountingBison` fake that tracks every provider operation
- They assert on the REFUSAL MESSAGE content (rule name, lead id, lint source)
- They assert on PROVIDER COUNTERS being zero (lint ran before any write)
- They monkey-patch `copylint.RULES` to prove the wiring reads the rule SET

The one weakness: the positive control tests (clean batch staged successfully)
are blocked by the sequence gate, not the lint. This is acknowledged in the
result block and is a fixture enrichment issue, not a wiring defect.

## Disposition

| # | Claim | Verdict |
|---|-------|---------|
| 1 | Artifacts exist | VERIFIED — all 3 files present at f1b9c357 |
| 2 | Wiring is real | VERIFIED — `_refuse_copylint` at bisonfactory.py:87, before first provider call |
| 3 | Tests pass | VERIFIED — 4/4 in new file, 7/10 in companion (3 RED due to sequence gate, as claimed) |
| 4 | Mutation test holds | VERIFIED — breaking wiring causes 4/4 fail |
| 5 | outreachclaims not on send path | VERIFIED — contextpack imports it, but contextpack is not on send path |
| 6 | No dangerous deletions | VERIFIED — only task queue files moved (TODO→REVIEW) |
| 7 | Scope drift | SIGNIFICANT — branch carries ~60 other files; TASK-290's commit is clean and cherry-pickable |
| 8 | Tests are falsifiable | STRONG — drive through real entry point, assert on refusal + provider counters |

## Recommendation: MERGE (cherry-pick)

TASK-290's deliverable is correct, well-tested, and addresses a real defect
from TASK-277. The wiring is genuine, the tests are falsifiable, and the
artifacts are purely additive.

The branch carries significant scope drift from other tasks, but TASK-290's
commit (`579cc624`) is isolated and cherry-pickable. Recommend cherry-picking
that single commit rather than merging the full branch.

The 3 RED tests in the companion file are a known fixture issue (sequence
gate requires `qualification` and `claims_supported` fields) and are not a
blocker for this task's integration.

## Evidence commands

    # Verify branch HEAD
    git rev-parse origin/qwen-worker-9-r9
    # → f1b9c357c17f4b557cbdb06f68339c7343ef3e83

    # Check artifacts exist
    git show f1b9c357:tests/test_the_lint_refuses_the_real_push.py | head -5
    git show f1b9c357:docs/COPYLINT-SECOND-PASS-2026-09-25.md | head -5

    # Verify wiring
    grep -n "_refuse_copylint" src/bisonfactory.py
    # → 87:    _refuse_copylint(plan, recs, report)
    # → 581:def _refuse_copylint(plan, recs, report):

    # Run tests
    python -m unittest tests.test_the_lint_refuses_the_real_push -v

    # Mutation test
    python -c "
    import src.bisonfactory as bf
    bf._refuse_copylint = lambda plan, recs, report: None
    import unittest
    suite = unittest.TestLoader().loadTestsFromName('tests.test_the_lint_refuses_the_real_push')
    unittest.TextTestRunner(verbosity=2).run(suite)
    "

    # Check deletions
    git diff master...f1b9c357 --stat --diff-filter=D

    # TASK-290's own commit
    git show 579cc624 --stat
