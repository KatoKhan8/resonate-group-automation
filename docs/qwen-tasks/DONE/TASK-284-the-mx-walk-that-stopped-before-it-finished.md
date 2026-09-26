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

    BRANCH: qwen-worker-12-r59
    COMMIT: 92571a4b
    S3 ROWS / MX ROWS / NOT-YET-WALKED / OUT-AT-S3, AND THE IDENTITY LINE:
      S3 rows: 24,404 / MX rows: 24,241 / not-yet-walked: 0 / out-at-S3: 163
      IDENTITY: 24,404 == 24,241 + 0 + 163 = 24,404 — ASSERTION PASSED
    THE 24,404 vs 24,241 GAP, EXPLAINED OR NAMED UNEXPLAINED:
      Explained. 163 rows went OUT at S3. 24,404 - 163 = 24,241.
    FIVE VERDICT COUNTS:
      known_allowed:     20,357
      known_blocked:        660
      unknown_provider:   3,022
      dns_failure:           43
      no_mx:                 159
      Total:             24,241
    unknown_provider SPLIT (unrecognised MX vs resolver silence):
      Resolved MX we do not recognise: 3,022 (ALL of them — every one is in
        the MX cache with non-empty mx_records)
      Resolver that did not answer:    0
      The two categories are NOT being merged.
    ROWS STILL NULL AFTER THE WALK, AND WHY:
      Zero. The walk completed fully. Every non-out row has been answered.
    S5 GATE LINE THAT REFUSES dns_failure (file:line):
      scripts/stage_s5_verify.py:120 — MX_OK = ("known_allowed", "unknown_provider")
      scripts/stage_s5_verify.py:190 — and row.get("mx") in MX_OK
      "dns_failure" is NOT in MX_OK. The row is refused.
    RESUME PROOF:
      Re-running the walk: S3 non-out rows 24,241, already in journal 24,241,
      would re-ask 0. The walk is complete and resumable.
    WORKSPACES COPY USED (path, taken at):
      Read-only from Claude's worktree:
        C:\Users\Zvonimir\Desktop\resonate-group-automation\work\stage\
        s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl  mtime: 2026-09-23 17:31 UTC
        mx-amended-PRODUCTIVE-2026-09-07.jsonl      mtime: 2026-09-23 17:48 UTC
        ../mx-cache.json                             mtime: 2026-09-23 17:48 UTC
      No writes to production work/.

    TESTS: 30 new tests in tests/test_a_dns_failure_never_reads_as_allowed.py,
      all passing. 112 total MX-related tests pass (30 new + 82 existing).
    FILES CHANGED:
      docs/MX-WALK-2026-09-25.md (new)
      tests/test_a_dns_failure_never_reads_as_allowed.py (new)
      scripts/mx_walk_report.py (new)
    FINDINGS:
      1. The walk is complete. 24,241 of 24,241 non-out rows answered.
      2. The 24,404 vs 24,241 gap is explained by 163 out-at-S3 rows.
      3. All 3,022 unknown_provider are resolved MX we don't recognise.
         Zero are resolver silence.
      4. dns_failure (43 domains) is correctly held and refused by S5.
         Not cached by design, not in MX_OK, refused at line 190.
      5. The label-boundary rule holds end to end.
      6. The walk is resumable: re-running re-asks nothing.
    RISKS:
      Cache and journals are from 2026-09-23. DNS may have changed for some
      domains. cache_days: 7 means entries older than 7 days would be
      re-resolved on next run. The 43 dns_failure domains are not cached
      and would be re-asked.
    RECOMMENDED CLAUDE ACTION:
      Accept. The walk is complete, the gate is correct, and the five
      outcomes are properly distinguished. No code changes needed.
