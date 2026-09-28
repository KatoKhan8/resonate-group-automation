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
