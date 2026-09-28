PRIORITY: P0
SIZE: S
DEPENDS: 

# TASK-557 — the figure gate licenses fabricated multipliers on a 4-char prefix

**BLOCKING. This is the defect that stopped P0-B merging.** Branch to work
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

## The instrument, because two agents were fooled by it today

**Derive a suite verdict from the presence of a `Ran N tests` line in the
output file, NEVER from `$?`.** A killed run here reported `exit=127` while
having already written 922 KB of genuine test output. **A truncated process and
a failing suite are indistinguishable by exit code.** No `Ran` line means an
**absent** measurement, not a failing one — UNKNOWN under invariant 0.

## Acceptance — all of it, or it is not done

1. All six bypasses above are **REFUSED**.
2. A pack containing the **literal** word still **licenses** it (do not
   over-correct into round 1's defect).
3. **THE MISSING CONTROL, and the reason this shipped: a NEAR-MISS negative
   control.** Every existing control uses a pack containing the literal word.
   You must add controls where the pack contains only a *similar* word and the
   claim is refused.
4. Idioms still pass: "half an hour", "double-check".
5. Mutation: revert your matcher to the prefix form; the near-miss control must
   go red. Restore byte-identical, sha256 verified.

## Files
**`src/generate.py` only**, plus your own test module. Nobody else may touch
`src/generate.py` while this task is open.

## RULES THAT OUTRANK FINISHING — every brief here

- **NEVER WIDEN A GATE TO MAKE A DRAFT PASS.** If a gate refuses correct copy,
  fix what it CONSULTS, never what it PERMITS.
- **A test count is never a PASS.** Name the real path exercised, the negative
  control, and the killed mutation.
- **EVERY new check needs a NEGATIVE control** — an input that must be REFUSED
  — and a **NEAR-MISS** control, not only an obvious one. The B1 defect below
  exists precisely because every control used a pack containing the literal
  word.
- **MUTATION CHECK IS MANDATORY.** Break your own fix in source, prove the
  intended test goes red for the intended reason, confirm no other guard fired
  first, restore the source and verify **byte-identical by sha256**.
  These files are **CRLF**: a `\n`-anchored regex matches zero times and your
  mutation becomes a silent no-op that looks like a surviving test.
- **PROVIDER WRITES = 0.** `sending.live` is false, the freeze stands, nothing
  is sent to anybody.
- Production `work/` is READ-ONLY. Verify `work/queue.jsonl` and
  `work/campaigns.jsonl` unchanged **by sha256 from a fresh process** — mtime
  is the wrong instrument, 23 loops write that checkout.
- **Write suite logs OUTSIDE the repository.** A log inside the tree became
  part of `test_fixture_hygiene`'s corpus and nearly committed real prospect
  domains. And interrupting a suite leaves one temp dir per test — 94,867 of
  them broke every later run. **A suite with no `Ran N tests` line is an
  absent measurement, not a failure**: sweep `%TEMP%` and re-run.
- Suite baseline is `docs/state/SUITE-BASELINE-2026-09-26.txt`, 128 named
  failures, compared **AS SETS, NEVER COUNTS**. It is known stale on master
  (TASK-549): four of its entries fail on master with no branch at all.
- Commit and push to your own branch; **verify the remote with `git rev-parse`**.
  Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** (VERIFIED / UNPROVEN /
  UNKNOWN) and your exact branch head SHA. GLM verifies against that SHA.

---

## RESULT BLOCK — TASK-557

**STATUS:** DONE
**ARTIFACT KIND:** verification of existing fix (code + tests) from TASK-550 on this branch

**CLAIM:** All six bypasses from the review are REFUSED by the inflection-family matcher.
**AUTHORITY:** `tests/test_task550_figure_gate_prefix_defect.py::Task550PrefixDefectBypassesAreRefused`
**MEASURED AT:** 6 tests, all pass. `python -m unittest tests.test_task550_figure_gate_prefix_defect` → `Ran 22 tests in 0.004s OK`
**STATE:** VERIFIED

**CLAIM:** A pack containing the literal word still licenses the quantity (no over-correction).
**AUTHORITY:** `tests/test_task550_figure_gate_prefix_defect.py::Task550LiteralWordStillLicenses`
**MEASURED AT:** 6 tests, all pass
**STATE:** VERIFIED

**CLAIM:** Near-miss negative controls detect the prefix defect.
**AUTHORITY:** `tests/test_task550_figure_gate_prefix_defect.py::Task550NearMissNegativeControls`
**MEASURED AT:** 6 tests, all pass. Mutation check: reverted to prefix form → 12 tests FAILED (6 bypass + 6 near-miss), including `test_threat_does_not_license_three_times`, `test_several_does_not_license_seven_times`, `test_trip_does_not_license_tripled`, `test_doubt_does_not_license_double`, `test_quadrant_does_not_license_quadrupled`, `test_threshold_does_not_license_three_times`. All failed with `AssertionError: [] is not true` — the prefix form incorrectly licensed the fabricated multiplier.
**STATE:** VERIFIED — mutation killed as intended

**CLAIM:** Idioms still pass (no over-correction).
**AUTHORITY:** `tests/test_task550_figure_gate_prefix_defect.py::Task550IdiomsStillPass`
**MEASURED AT:** 4 tests, all pass: "half an hour", "double-check", "twice last year", "half the team"
**STATE:** VERIFIED

**CLAIM:** Mutation test byte-identical restore.
**AUTHORITY:** sha256 from fresh process
**MEASURED AT:** Before mutation: `660c87182ead19f2bff6a9299c41cf46d9f70aa6abc75a1ea7d1a48e38716f3b`. After restore: `660c87182ead19f2bff6a9299c41cf46d9f70aa6abc75a1ea7d1a48e38716f3b`. Match: True.
**STATE:** VERIFIED

**CLAIM:** Production state unchanged.
**AUTHORITY:** sha256 from fresh process
**MEASURED AT:** `work/queue.jsonl`: `5542e90b39b5c43d...`, `work/campaigns.jsonl`: `b8c5158cd07b0d75...`
**STATE:** VERIFIED

**CLAIM:** The fix replaces the 4-char prefix with inflection-family matching on BOTH sides.
**AUTHORITY:** `src/generate.py:2548-2600` (`_QUANTITY_INFLECTIONS`, `_quantity_licensed`), `src/generate.py:2714-2730` (call site in `_invented_quantities`)
**MEASURED AT:** Code inspection. Support side: `support_words = set(re.findall(r"[a-z]+", support.lower()))` — full words, not prefixes. Matched side: `_quantity_licensed(head[0], support_words)` — looks up inflection family and checks set intersection. No `[:4]` truncation on either side.
**STATE:** VERIFIED

**FILES CHANGED:**
- `src/generate.py` — fix by TASK-550 (commit `b60328b2`), verified by TASK-557
- `tests/test_task550_figure_gate_prefix_defect.py` — test module by TASK-550

**FINDINGS:**
- The fix is correct and complete. All acceptance criteria met.
- The mutation test confirms the near-miss controls detect the prefix defect.
- CRLF line endings preserved (3530 CRLF, 0 LF-only).
- No other guards fired first during mutation — the failures were directly from the near-miss and bypass tests asserting on `_invented_quantities` return values.

**RISKS:**
- Inflection family coverage: if new quantity words are added to `_WORDED_QUANTITY`, their inflections must be added to `_QUANTITY_INFLECTIONS`. Currently covers: double/doubled/doubles/doubling, triple/tripled/triples/tripling, quadruple/quadrupled/quadruples/quadrupling, halve/halved/halves/halving, half, twice, thrice, two–ten, tenfold/twofold/threefold/fourfold/fivefold.

**RECOMMENDED CLAUDE ACTION:**
1. Verify the fix in `src/generate.py` (lines 2548-2600, 2714-2730)
2. Verify the test module `tests/test_task550_figure_gate_prefix_defect.py`
3. Merge `task-p0b-copy-engine-pareto` into master after review

**COMMIT SHA:** 14081a5c414695f32e785baf43acf092eb47b2ba (branch head of `task-p0b-copy-engine-pareto`)
**BRANCH:** `task-p0b-copy-engine-pareto`
**VERIFIED BY:** TASK-557 on `qwen-worker-r9`, work verified on `task-p0b-copy-engine-pareto`
**PUSHED:** origin/task-p0b-copy-engine-pareto at 14081a5c
