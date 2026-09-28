PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-550 — the figure gate licenses fabricated multipliers on a 4-char prefix

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

## RESULT BLOCK

**STATUS:** DONE
**COMMIT SHA:** b60328b294d659755b7634168c92691d4fabb801
**BRANCH:** task-p0b-copy-engine-pareto
**REMOTE VERIFIED:** `git rev-parse HEAD` = `git rev-parse origin/task-p0b-copy-engine-pareto` = b60328b2

**TESTS:**
- 22 new tests in `tests/test_task550_figure_gate_prefix_defect.py`: ALL PASS
- 69 existing tests in `tests/test_the_copy_engine_converges_and_still_refuses.py`: ALL PASS
- Mutation check: reverted matcher to prefix form, all 6 near-miss controls FAILED (as intended), restored byte-identical by sha256 (660c87182ead19f2bff6a9299c41cf46d9f70aa6abc75a1ea7d1a48e38716f3b)

**FILES CHANGED:**
- `src/generate.py`: replaced 4-char prefix matching with inflection family matching
- `tests/test_task550_figure_gate_prefix_defect.py`: new test module with 22 tests
- `docs/qwen-tasks/RUNNING/TASK-550-the-figure-gate-matches-a-four-character-prefix.md`: task file moved from TODO

**FINDINGS:**

CLAIM: The 4-char prefix defect licensed fabricated multipliers on 6 of 8 attack vectors.
AUTHORITY: src/generate.py line 2667 (before fix): `support_stems = {w[:4] for w in re.findall(r"[a-z]+", support.lower())}`
MEASURED AT: tests/test_task550_figure_gate_prefix_defect.py
STATE: VERIFIED - all 6 bypasses now refused

CLAIM: Literal word in pack still licenses the quantity (no over-correction).
AUTHORITY: tests/test_task550_figure_gate_prefix_defect.py::Task550LiteralWordStillLicenses
MEASURED AT: 6 tests, all pass
STATE: VERIFIED

CLAIM: Near-miss negative controls detect the prefix defect.
AUTHORITY: tests/test_task550_figure_gate_prefix_defect.py::Task550NearMissNegativeControls
MEASURED AT: mutation check - reverted to prefix form, all 6 near-miss tests FAILED
STATE: VERIFIED - mutation killed as intended

CLAIM: Idioms still pass (no over-correction).
AUTHORITY: tests/test_task550_figure_gate_prefix_defect.py::Task550IdiomsStillPass
MEASURED AT: 4 tests, all pass
STATE: VERIFIED

CLAIM: Production state unchanged.
AUTHORITY: sha256 from fresh process
MEASURED AT: work/queue.jsonl: 5542e90b39b5c43da781df8a1a98a0105fb07aad652c309096a7b83ae570c3da, work/campaigns.jsonl: b8c5158cd07b0d75e39d837453a84018178b513004a8f2c39772eac0c1cfa689
STATE: VERIFIED

**RISKS:**
- R2 defect (non-blocking, same family): `_NOT_A_QUANTITY`'s `half the`/`half of` exempts real magnitude claims like "half the cost". Not fixed in this task as it was scoped non-blocking.
- Inflection family coverage: the fix covers the inflections in `_WORDED_QUANTITY` (double/doubled/doubles/doubling, triple/tripled/triples/tripling, etc.). If new quantity words are added to the regex, their inflections must be added to `_QUANTITY_INFLECTIONS`.

**RECOMMENDED CLAUDE ACTION:**
1. Review the fix in src/generate.py (lines 2548-2600 for the helper, 2714-2730 for the call site)
2. Review the test module tests/test_task550_figure_gate_prefix_defect.py
3. Verify against the review document docs/REVIEW-P0B-142ca537.md on review-p0b-round2
4. Consider fixing R2 (non-blocking) in a follow-up task
5. Merge task-p0b-copy-engine-pareto into master after review
