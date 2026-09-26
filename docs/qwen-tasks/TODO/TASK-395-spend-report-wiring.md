PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-395 — does the spend report actually read what TASK-346/373 now write?

TASK-346 built the ceiling mechanism; TASK-373 threaded a real client
identity through every `model.complete()` call site in `src/`. Trace whether
whatever reporting surface exists (`scripts/glm_review.py`, a Slack spend
report, `spendledger`'s own summary functions) reads the NOW-attributed rows
correctly, or whether it was written against the old "unattributed" shape
and undercounts or misreads client-attributed spend.

## Trace first

1. `grep -rln "spendledger" scripts/ src/` — every consumer of the ledger
   that reports a number to a human (Slack, a script's stdout, a dashboard).
2. For each, does it group by client correctly now that real client ids
   land in the rows (post-TASK-373), or does it still expect everything
   under `"unattributed"` / `"_model"`?
3. Report which reporting surfaces are correct today and which need a fix,
   with file:line.

## Build only what the trace shows broken

## Acceptance

1. Run whatever spend report exists against a fixture with mixed
   client-attributed and unattributed rows; confirm it reports the client
   total correctly, not folded into unattributed.
2. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- No live model call, no provider write. Fixtures only.
- Nothing sent, nothing activated.
