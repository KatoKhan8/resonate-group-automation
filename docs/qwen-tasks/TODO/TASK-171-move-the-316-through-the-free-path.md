PRIORITY: P0
DEPENDS:

# TASK-171 - run the free path over all 316, and report what it produced

## WHERE THIS SITS

TASK-163 answered the question that was holding the batch still, and the
answer was A:

    python -m src.run --spend --cap 0 --stage enrich --stage qualify

An evidence-free record cannot reach `dropped`. `icpstructural.verdict_of`
needs at least one FAIL to produce ICP_FAIL; absent evidence every structural
criterion returns UNKNOWN; UNKNOWN with no FAIL is ICP_REVIEW. Five records
measured, nought dropped.

Claude then ran it with `--limit 20` and got this:

    enrich   records=9, spent=0, refused=['2ton-com:apify-research']
    states   queued 316, verified 35, held 35, dropped 125, drafted 37, approved 2

Two things in that output need explaining before the full run is worth doing.

1. `--limit 20` processed NINE records, not twenty.
2. `queued` did not move at all, while `drafted` fell from 44 to 37 and
   `verified` rose from 26 to 35 - records in a state the run was not aimed at.

And `work/queue.snapshot.jsonl` reports `icp_status` NONE for all 550 with
`lane` domains for all 550, which disagrees with the run's own state counts.
So the artefact Claude measured from is not the live state, and anything
measured from it today is not trustworthy.

## THE QUESTION

1. **Where is live state, and what is the snapshot?** Name the module and the
   path that `src.run` reads and writes. Say when `work/queue.snapshot.jsonl`
   is written, what writes it, and why it reports `icp_status` NONE for records
   the runner says are verified. If it is a stale artefact, say what regenerates
   it and regenerate it.
2. **Why nine and not twenty?** Find the predicate that selected nine. Read
   `qualify.needs_work` and the `--limit` handling in `src/run.py`. A limit that
   silently means something other than "this many records" makes every bounded
   run a guess.
3. **Why did `drafted` and `verified` move?** Claude passed `--lane domains`.
   Determine whether `--lane` scopes the enrich stage at all, and whether those
   transitions were correct work or an unscoped side effect. `drafted` falling
   is the one to be sure about - say which records moved and why.
4. **Then run it over all 316** and report the real distribution: `icp_status`
   per record, counted, plus how many got research from webfetch, how many
   webfetch failed on, and the credit spend, which must be zero.

## THE TRAP

`spent=0` in a summary line is the runner's claim about itself. Read the
durable spend ledger and confirm zero independently - that is what it is for.
`refused=['2ton-com:apify-research']` proves the cap refused one paid call; it
does not prove no other paid call happened.

Second trap: this task runs a LIVE stage over the whole batch, and `dropped` is
terminal. Before the full run, assert from the code - not from TASK-163's
sample - that no record in this batch can reach `dropped` by this path. If any
can, run nothing and report which.

## WHAT YOU MAY NOT DO

- No provider writes. No HeyReach or EmailBison write of any kind.
- Zero credits. If the run reports any spend above zero, stop it and report.
- Do not weaken ICP or a gate to move records forward.
- Do not move a record to `dropped`, and do not clear one that is.
- Never commit PII. Hash record ids and domains.

## FILES ALLOWED

    docs/FREE-PATH-RUN-2026-09-16.md   (new)
    scripts/task171_*.py
    work/queue.snapshot.jsonl   (only if you establish that regenerating it is
                                 correct, and say what regenerates it)

## FILES FORBIDDEN

    src/   config/

## DELIVERABLE

The live-state answer with module and path, the snapshot's provenance and
staleness verdict, why nine, whether `--lane` scopes enrich and what moved, the
full 316 `icp_status` distribution, the webfetch success and failure counts,
and the spend read off the ledger.
