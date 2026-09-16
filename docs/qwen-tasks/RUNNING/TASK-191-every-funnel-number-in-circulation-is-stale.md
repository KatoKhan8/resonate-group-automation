PRIORITY: P1
DEPENDS:

# TASK-191 - every funnel number in circulation is from a stale file

## WHERE THIS SITS

The handoff Claude recovered this morning carried this funnel:

    RECEIVED 550  PRELIMINARY_ICP 300  QUALIFIED 113  ICP_REVIEW 66
    PERSON_DISCOVERY 91  ENRICHED 91  VERIFIED 67  CAMPAIGN_READY 32
    LIVE_ELIGIBLE 28  DROPPED 125  HELD 36

Then TASK-171 established that `work/queue.snapshot.jsonl` is **stale**: it
holds 550 records against live state's 300, and reports `icp_status` NONE for
every one of them. Several tasks have since measured from it, including some
whose numbers are now in committed documents, and a free-path run over the
estate has been writing to live state throughout the morning.

So there are three populations in circulation - 550, 316 and 300 - and no
document says which is which. `docs/state/PRODUCTION-DASHBOARD.md` and
`docs/state/LEDGER.json` are the artefacts a fresh session reads first.

## THE QUESTION

1. **Name the authoritative file** for live pipeline state, with its record
   count and its stamp. TASK-171 says `work/queue.jsonl`, 300 records. Confirm
   it, and explain the 550 - is the snapshot a superset including records live
   state has dropped, a different client, an older ingest, or simply wrong?
   The three populations must be reconciled, not just labelled.
2. **Recompute the funnel from live state.** Every stage in the objective:
   RECEIVED, NORMALIZED, FREE_RESEARCH, PRELIMINARY_ICP, QUALIFIED,
   PERSON_DISCOVERY, ENRICHMENT, VERIFICATION, CAMPAIGN_READY, APPROVAL,
   LIVE_ELIGIBLE, plus DROPPED and HELD. State the predicate you used for each
   stage - a stage counted by a different predicate than last time is a
   different number, not a change.
3. **Regenerate the snapshot, or retire it.** If `queue.snapshot.jsonl` has a
   purpose, say what writes it and regenerate it so it agrees with live state.
   If nothing needs it, say so and recommend its removal - a stale artefact
   that eleven tasks have measured from is worse than a missing one.
4. **Update the durable state files.** `PRODUCTION-DASHBOARD.md`,
   `LEDGER.json`, `QUEUE-MANIFEST.json` - whatever `scripts/durable_state.py`
   generates - so a fresh session reads today's numbers. Stamp each with the
   source file and record count it came from.
5. **List the documents carrying superseded numbers.** Do not edit them. A
   document is a record of what was measured when; a list of which ones are now
   wrong is what a reader needs.

## THE TRAP

A free-path run has been mutating live state all morning, so a funnel computed
mid-run is a snapshot of a moving target. Check whether a run is still writing
before you count, say so in the stamp, and if one is in flight either wait or
record the count as provisional and say which. Do not present a mid-run number
as the funnel.

Second trap: `PRELIMINARY_ICP 300` and `QUALIFIED 113` came from a 550-record
file. If live state has 300 records total, then "300 reached PRELIMINARY_ICP"
and "300 records exist" are the same number for different reasons, and reading
the first as progress is a mistake somebody will make. Say it plainly.

## WHAT YOU MAY NOT DO

- No provider writes, no paid provider calls.
- Do not move any record between states, and do not run a live stage.
- Do not edit documents that carry superseded numbers - list them.
- Do not delete `queue.snapshot.jsonl` in this task; recommend it.
- Never commit PII. The manifest must stay PII-safe - check what
  `durable_state.py` already does about that before adding to it.

## FILES ALLOWED

    docs/state/PRODUCTION-DASHBOARD.md
    docs/state/   (the generated files)
    scripts/durable_state.py
    docs/FUNNEL-2026-09-16.md   (new)
    scripts/task191_*.py

## FILES FORBIDDEN

    src/   config/   work/queue.jsonl (read only)

## DELIVERABLE

The authoritative file with its count and stamp, the three populations
reconciled, the funnel recomputed with the predicate for every stage, the
snapshot regenerated or a recommendation to retire it, the durable state files
updated and stamped, and the list of documents now carrying superseded numbers.
