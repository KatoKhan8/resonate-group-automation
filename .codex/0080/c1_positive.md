## 2026-10-16 10:26 — TASK 0074 — section 3: the two FAIL-OPEN repairs, landed with controls

Repairs authored in tree `wt-glm-review-2026-10-14` (CRLF), branch
`task-glm-review-2026-10-14`, committed as
`5c8a4249c4fe39cb093a1e916f94f4fb88543135` ("TASK 0074: the floor that
reached operators dressed as a total", parent `40f9f3205...`, 3 files, +286
-8). Mutation proofs ran in a throwaway detached worktree
`wt-glm-mutate-0074` AT that commit, removed afterwards (`git worktree list`
read back: zero mentions). `src/providers/*`, gates, caps and
`config/model-prices.yaml` untouched; no push; no commit outside the lane
branch.

### The repairs (the shape 0073 chose, held exactly)

1. `src/simulator.py` `_credit_estimate`: `already_spent` stays numeric; it
   now carries `already_spent_is: "floor"|"total"` and the summed
   `unpriced_calls`, both read from the same `waterfall.spend()` summaries
   the number was already summed from. No new computation - the labels were
   computed one line away and dropped.
2. `src/costs.py`: `reconcile` reads the `unpriced` count
   `expected_by_provider` has computed since 0073 (and dropped here), passes
   it to `_verdict`, and carries `unpriced` + `expected_is` on each row.
   `_verdict`'s FREE_CONFIRMED now requires a fully-priced bucket: an
   expected of 0 built from `priced: False` rows with quiet counters returns
   UNPRICED with a why that names the actual condition ("could not be
   priced", "no counter moved", re-read after SETTLING_SECONDS); every
   expected>0 verdict appends the floor sentence when unpriced>0. `report()`
   appends ` FLOOR` to floor rows ONLY - a priced row's line is
   byte-identical to what it was before the marker existed, which keeps the
   first-line-prefix pin in `test_a_cost_claim_names_its_evidence` green
   unchanged.

Test module `tests/test_a_floor_is_never_a_total.py`: the classifier
(`classify_fail_open`, ground truth = the fixture's own `priced: False`
rows), the C2 fixture pair (`every_price_known` / `a_price_is_missing`), and
the per-site C1 tests. Both kill-sets are named in its docstring, per plant.

### C3 - the classifier against the UNMODIFIED module, recorded verbatim

Run BEFORE any source edit, same tree, at `40f9f3205` (log preserved:
`glm-review-2026-10-14/task0074-c3-prerepair-run.txt`, sha256
`39a0245ff476f2e6a3cd02f300a3c081ae6e02da2d5264162db961637942041d`):

- `Ran 10 tests in 0.013s` / `FAILED (failures=4, errors=5)`; the one green
  was `test_the_report_marks_nothing_when_every_price_is_known` (priced rows
  were already unmarked - the defect only ever showed on floors).
- Missing-price fixture, classifier output verbatim:
  `['costs._verdict/FREE_CONFIRMED-on-floor',
  'costs.reconcile/row-drops-unpriced', 'costs.report/floor-unmarked',
  'simulator._credit_estimate/already_spent']` - all four §2 sites, by name.
- All-priced fixture: `['costs.reconcile/row-drops-unpriced',
  'simulator._credit_estimate/already_spent']` - recorded as found: an
  unlabelled surface cannot distinguish the two fixtures, which is exactly
  why it was FAIL-OPEN. (Post-repair both fixtures print `[]`, the C2
  assertion.)
- The headline artifact, verbatim from the failure text:
  `AssertionError: 'FLOOR' not found in 'FREE_CONFIRMED     apify
  expected=0      calls=2'` - the defect's own print line, red.
- The five errors were `KeyError: 'already_spent_is'` /
  `KeyError: 'expected_is'` / `KeyError: 'unpriced'` - the absent keys are
  the finding.

Post-repair, same tree at `5c8a4249c`: `Ran 10 tests in 0.011s` / `OK`
(log: `task0074-c3-postrepair-run.txt`). With the two consumer suites:
`tests.test_a_cost_claim_names_its_evidence` + `tests.test_simulator`
together `Ran 78 tests in 37.641s` / `OK` - the 0073/earlier pins
(FREE_CONFIRMED on a priced zero, UNPRICED-on-apify-moved "not a bypass",
report first-line prefix, simulator headline keys) all held. Before/after
differ; the classifier measures something.

### C1/C4 - six plants, six kills, six hash-proven reverts

Reference in the mutation tree first: clean run at `5c8a4249c` before any
plant, `Ran 10 tests in 0.146s` / `OK`. Pre-plant sha256 in that tree:
`src/costs.py b41455b2a2a24b035d4080b2f9eaf66f5c7e70c7819d02b069d4128fe37a39ef`,
`src/simulator.py effa7db33e0bee584cd9a8b305f4da4fe546a48c0d68b93ba993e7892ad75d74`.
The tree checked out CRLF (plain `worktree add` from the env-clean lane
shell); plants were byte-pattern replacements with explicit CRLF and an
assert-count-exactly-one guard, reverts were `cp` of the pre-plant bytes,
and `src/__pycache__`+`tests/__pycache__` were deleted between plant and run
(the whole-second pyc trap). Every restore was verified sha256-equal to the
pre-plant hash above; after the last restore a final clean run gave
`Ran 10 tests` / `OK` and `git status` in the mutation tree was empty.

- **Plant A** - simulator repair deadened (the two keys removed). Killed 4:
  `test_already_spent_is_a_floor_when_a_price_is_missing`,
  `test_already_spent_is_a_total_when_every_price_is_known` (KeyError), both
  classifier tests. No costs test moved - a plant in simulator.py cannot
  kill costs teeth, so the kills are not collateral.
- **Plant B** - verdict guard deadened (`if unpriced:` -> `if False and
  unpriced:`). Killed EXACTLY 2: `test_free_is_never_confirmed_on_a_bucket_
  that_was_never_priced`, `test_the_classifier_reports_zero_when_a_price_is_
  missing`. Surgical.
- **Plant C** - reconcile rows drop `unpriced`+`expected_is`. Killed 7: the
  three named in the docstring kill-set (`test_reconcile_rows_carry_the_
  count_that_keeps_the_number_a_floor`, both classifier tests) plus the four
  other tests that read those same row keys (`free_is_never_confirmed...`,
  `free_is_confirmed_on_a_priced_zero`, `reconciled_on_a_floor_names_the_
  floor`, `the_report_marks_a_floor_as_a_floor`) - same site, same keys.
- **Plant D** - report marker dropped (`mark = ""`). Killed EXACTLY 2:
  `test_the_report_marks_a_floor_as_a_floor`,
  `test_the_classifier_reports_zero_when_a_price_is_missing`.
- **Plant E - C4, BYTE-LENGTH IDENTICAL.** `"floor"`/`"total"` swapped in
  simulator's label (both 5 bytes). File size 22334 before AND after.
  Killed 4, BOTH directions: the floor-fixture test (got "total"),
  the priced-fixture test (got "floor"), both classifier tests. The
  same-length mutation is dead.
- **Plant F - C4, BYTE-LENGTH IDENTICAL.** Same swap in costs' row
  `expected_is`. File size 19575 before AND after. Killed 8: every test
  that reads the row label in either direction, including the mirror-lie
  catches `test_free_is_confirmed_on_a_priced_zero` (priced zero marked
  floor) and `test_the_report_marks_nothing_when_every_price_is_known`
  (priced row marked FLOOR), plus both classifier tests.

Plant logs preserved: `glm-review-2026-10-14/task0074-plant{A..F}.out`.

### End-of-run figures (all in `wt-glm-review-2026-10-14` unless named)

- `md5sum scripts/run_suite.py` = `65c50c89ac0e2279fa7178cba251f256` -
  identical to the start-of-run figure in the section 1+2 entry. Quoted
  both sides; unchanged.
- `git ls-remote origin refs/heads/master` =
  `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2` - identical to start. No push
  was made from this lane; nothing merged to master.
- `git status --short`: only `?? .codex/0065/ref_suite_launch.out`, the
  pre-existing untracked measurement file named in earlier entries, not
  mine, left as found.
- Branch `task-glm-review-2026-10-14`, HEAD
  `5c8a4249c4fe39cb093a1e916f94f4fb88543135`, left in place. Worktree left
  on its branch, tree clean.

### Open items handed to the operator (decisions that are his)

- The §1 GAP stays open by design: `spendledger.report()`'s `expected_floor`
  and `unpriced_rows` still have no consumer beyond pinning tests and the
  `--json` dump, and the text CLI prints the tripwire but not the floor
  figure beside it. Fail-closed, incomplete, NOT fail-open - repairing a
  view is outside this task's mandate. RECOMMENDATION: a one-line floor
  print beside the tripwire in `main()`'s text mode, next time someone owns
  spendledger CLI polish; trivial, but it is a view change on a module
  another task may hold.
- `src/providers/glm.py` remains UNKNOWN-CLASSIFIED per §1 (three seam
  feeds); closing authority unchanged: the operator lifting the read
  prohibition, or the task that owns `src/providers/*`. Both glm models are
  priced on today's config, so no live path sees UNKNOWN through them.
- TASK 0075 (per the brief) receives: no unkillable mutation was found -
  all six plants died, both byte-identical ones included. There is no
  reportable "the suite cannot see this" result from this lane; C4's
  escape hatch was not needed.

TASK 0074 sections 1, 2 and 3 are complete. The entry is the record.
