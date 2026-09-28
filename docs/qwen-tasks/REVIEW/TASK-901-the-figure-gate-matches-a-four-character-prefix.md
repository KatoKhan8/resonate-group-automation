PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-901 — the figure gate licenses fabricated multipliers on a 4-char prefix

**BLOCKING. This is the defect that stopped P0B merging.** Branch to work
from: `origin/task-p0b-copy-engine-pareto` head `142ca537`. Findings:
`docs/REVIEW-P0B-142ca537.md` on `review-p0b-round2` (`78e908e2`).

## The defect

`_invented_quantities` in **`src/generate.py`** builds its support set as
`{w[:4] for w in ...}` — a **four-character PREFIX, not a stem**. So any word
in the research pack sharing those four characters licenses a fabricated
multiplier:

    "threat" / "threshold"  ->  licenses "three times"
    "several"               ->  licenses "seven times"
    "trip"                  ->  licenses "tripled"
    "doubt"                 ->  licenses "double"
    "quadrant"              ->  licenses "quadrupled"

**Six of eight attacks bypass it.** It fires through the live path on BOTH
channels and **nothing downstream catches it**: `claims.check` returns
`is_claim` False, `copylint.untraceable`, `copylint.check_batch` and
`heyreachfactory.unsupported_claims` all report clean. That silence is the
whole premise of this gate.

**Reachability, measured against production `work/queue.jsonl`: 134 of 394
records carrying a research pack — 34.0% of the estate.**

Round 1 of this gate **over**-refused, which is safe. Round 2 **under**-refuses
on a third of the estate, which is not.

## The fix

Match on **word boundaries against each quantity word's inflection family**
(double/doubled/doubles, triple/tripled, quadruple/quadrupled, half/halved …),
not on a character prefix. The reviewer scoped it at about five lines.

**⚠ THE SAME `[:4]` TRUNCATION IS APPLIED ON *BOTH* SIDES OF THE COMPARISON.**
Reported by the author of the defect after the review was written. **Fix the
matched-phrase side as well as the support side** — repairing only the support
set leaves the same collision reachable from the other direction and will look
fixed, because the obvious tests will pass. Read both sides before you change
either.

## RESULT BLOCK

STATUS: REVIEW
COMMIT SHA: 84b74c11 (branch: task-901-figure-gate-fix)
TESTS: 27 new tests in tests/test_task901_figure_gate_prefix.py, all pass.
  69 existing tests in test_the_copy_engine_converges_and_still_refuses.py,
  all pass. 96 total, 0 failures. Ran 27 tests in 0.008s (new module).
  Ran 96 tests in 0.105s (combined). "Ran N tests" line confirmed in output.
FILES CHANGED:
  - src/generate.py: added _QUANTITY_INFLECTIONS dict (21 families),
    _quantity_licensed() helper, replaced [:4] prefix on BOTH sides of the
    comparison in _invented_quantities with inflection-family matching.
    +52 lines, -2 lines.
  - tests/test_task901_figure_gate_prefix.py: NEW test module, 27 tests
    covering all 5 acceptance criteria.
  - docs/qwen-tasks/RUNNING/TASK-901-*.md: task file moved to RUNNING.
FINDINGS:
  ARTIFACT KIND: code + test.
  CLAIM: The 4-char prefix match on BOTH sides of the comparison is replaced
    by word-boundary matching against inflection families.
  AUTHORITY: src/generate.py, _quantity_licensed() and _invented_quantities().
  MEASURED AT: 2026-09-28, against commit 142ca537 (the defect commit).
  STATE: VERIFIED.
    - Acceptance 1: All 6 bypasses REFUSED (threat→three, several→seven,
      trip→triple, doubt→double, quadrant→quadruple, threshold→three).
    - Acceptance 2: Literal words still license (double/doubled/doubles/
      doubling, triple/tripled, three, halved, quadrupled).
    - Acceptance 3: Near-miss negative controls added and passing. A pack
      containing ONLY similar words (threshold, several, quadrant, trip,
      doubt, doubtful, doubts) refuses all fabricated multipliers.
    - Acceptance 4: Idioms still pass (half an hour, double-check, half the
      team, half of the work).
    - Acceptance 5: Mutation check completed. Reverted to [:4] prefix form:
      13 tests went RED (6 bypass + 3 near-miss + 4 subTests). All failed
      for the INTENDED reason: AssertionError: [] is not true (the gate
      returned empty, no other guard fired first). Restored byte-identical:
      _quantity_licensed sha256 e13cd9c8... verified, _invented_quantities
      sha256 b4b4b122... verified.
  CALLER CHAIN VERIFIED:
    - _quantity_licensed is called by _invented_quantities (grep confirmed).
    - _invented_quantities is called by _step_refusals (existing test
      test_the_full_chain_refuses_through_step_refusals drives this path).
    - No orphan code: _QUANTITY_INFLECTIONS is consumed by _quantity_licensed.
RISKS:
  - The inflection families are hand-curated. A quantity word not in the dict
    will not be licensed by any pack. This is fail-closed (refuses rather
    than licenses), which is the safe direction.
  - The fix is on branch task-901-figure-gate-fix, based on 142ca537. The
    later commits on task-p0b-copy-engine-pareto (TASK-550, TASK-557) applied
    a similar fix independently. This branch's fix should be compared with
    theirs during integration to avoid duplication.
RECOMMENDED CLAUDE ACTION:
  Review the diff on task-901-figure-gate-fix. The fix is minimal (2 lines
  changed in the function body, plus the helper and dict). All acceptance
  criteria are met and the mutation check proves the tests are load-bearing.
  Integrate with or replace the TASK-550/TASK-557 fix on task-p0b-copy-engine-
  pareto — both arrive at the same design (inflection families).
