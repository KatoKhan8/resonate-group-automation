PRIORITY: P1
DEPENDS:

# TASK-284 — the MX walk that stopped before it finished

## The question this answers

**Is the MX verdict for the 09-07 estate complete, current, and fail-closed —
and how many of the 3,022 `unknown_provider` rows are actually a resolver that
did not answer?**

The funnel as of 2026-09-24:

    S3 ICP  24,404  ->  in 19,612 · flagged 4,629 · out 163
    MX      24,241  ->  allowed 20,357 · unknown 3,022 · blocked 660

**24,241 is not 24,404.** 163 rows went OUT at S3, which accounts for some of
it, and the rest is unexplained. S5 gates on `row["mx"] in MX_OK`, and the
offline re-judge carried `mx` forward as **null because it never asked** —
which is the exact reason `scripts/stage_mx_amended.py` exists. A row with a
null `mx` is not an allowed row and it is not a blocked row; it is a row the
gate will refuse for a reason nobody reads.

`src/mx.py` has five outcomes deliberately, not four:

    known_allowed / known_blocked / unknown_provider / dns_failure / no_mx

**`dns_failure` HOLDS the channel; it is never "no gateway found".** That is
the one failure mode that would quietly send into the thing the module exists
to avoid. This task checks that the distinction survives the walk, the
journal, and the gate — not just the function.

## What to do

DNS only. **No credits, no provider API, no writes.**

1. Run `py -3 scripts/stage_mx_amended.py --report` and reconcile its journal
   against the amended S3 journal. Account for **every** row: in the S3
   journal, in the MX journal, verdict per row. Print the identity
   `S3 rows == MX rows + not-yet-walked + out-at-S3` and make it an assertion.
2. Resume the walk to completion for the rows the amended judge did not put
   OUT. It is resumable and incremental by design; say how many it had already
   answered and how many it added.
3. **Split the 3,022 `unknown_provider`.** How many are a resolved MX we do
   not recognise (legitimate unknown, policy decides) versus how many are a
   resolver that did not answer? If those are being merged anywhere, that is
   the finding.
4. Check the label-boundary rule holds end to end: `pphosted.com` matches
   `mx1.pphosted.com` and does not match `notpphosted.com.evil.test`. Assert
   it through the walk's verdict, not by reading `src/mx.py`.
5. Trace the verdict into the gate: show that S5 refuses a `dns_failure` row
   and a null-`mx` row, and name the line that does it.

Write `docs/MX-WALK-2026-09-25.md` with the full per-verdict census.

## The acceptance bar

- **Every** S3 row is accounted for by exactly one outcome, and the identity
  above is printed and asserted. The 163-row gap between 24,404 and 24,241 is
  explained by name, or reported as unexplained with the count.
- The five outcomes are reported separately. Four buckets is a fail.
- `dns_failure` count is stated, and a test proves a `dns_failure` row cannot
  reach an allowed state through the journal or the gate.
- Rows still carrying a **null** `mx` after the walk are counted and named as
  a class, with why they were never asked.
- The walk is resumable: kill it and restart it, and it re-asks nothing.
  Demonstrate.

## What evidence counts

- The reconciliation table with the printed identity line.
- The per-verdict counts from the real journal, with the journal's path and
  mtime.
- For the `dns_failure` claim: the S5 gate line (file:line) that refuses it,
  and a run showing the refusal.
- Three real domains, one per interesting verdict (blocked, unknown, no_mx),
  with the MX hostnames that produced the verdict. Domains are companies, not
  people, so they may be named; **no addresses, no personal names.**

## WHAT WOULD MAKE THIS A FALSE PASS

- **A count with no names.** "3,022 unknown" is the number we already have.
  The deliverable is the SET, split by cause, diffable against the next run.
- **Unit tests on `src/mx.py`.** The function is not the risk; the journal and
  the gate are. A green `test_mx` proves nothing about whether S5 reads the
  verdict. Drive it through the walk.
- **A resolver failure counted as `unknown_provider`** — or silently retried
  until it answers something. If the walk retries, say how many times and what
  it does when the retries run out.
- **Reporting the walk complete because the script exited 0.** Exit 0 on a run
  that walked 0 rows is the shape of a halt that alerted nothing. Print rows
  walked.
- **Reading a stale journal from your worktree's `work/`.** Point `WORKSPACES`
  at a named copy of production's and say when it was taken.

## Boundaries

- DNS only. No EmailBison, HeyReach, Apify, ContactOut or Reoon calls.
- Do not write to production `work/`.
- Do not change `src/mx.py`'s policy. If the policy is wrong, that is a
  FINDING with a reproduction, and the operator decides.

## Files

    ALLOWED    docs/MX-WALK-2026-09-25.md,
               tests/test_a_dns_failure_never_reads_as_allowed.py,
               scripts/mx_walk_report.py (if a reconciler is needed)
    FORBIDDEN  src/mx.py, src/providers/*, work/* (production),
               config/.env, scripts/*_watch_loop.py

## Result block

    BRANCH:
    COMMIT:
    S3 ROWS / MX ROWS / NOT-YET-WALKED / OUT-AT-S3, AND THE IDENTITY LINE:
    THE 24,404 vs 24,241 GAP, EXPLAINED OR NAMED UNEXPLAINED:
    FIVE VERDICT COUNTS:
    unknown_provider SPLIT (unrecognised MX vs resolver silence):
    ROWS STILL NULL AFTER THE WALK, AND WHY:
    S5 GATE LINE THAT REFUSES dns_failure (file:line):
    RESUME PROOF:
    WORKSPACES COPY USED (path, taken at):
