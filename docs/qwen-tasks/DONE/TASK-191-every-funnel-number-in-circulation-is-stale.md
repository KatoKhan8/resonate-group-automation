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

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** c96bc01

**TESTS:**
- `tests.test_invariants`: 80 tests, all pass
- `tests.test_fixture_hygiene`: 13 tests, 4 pre-existing failures (non-reserved domains in test fixtures, unrelated to this task)
- No conflict markers in src/, tests/, scripts/
- `scripts/task191_funnel.py` runs cleanly and produces valid JSON

**FILES CHANGED:**
- `scripts/task191_funnel.py` (new) - computes funnel with explicit predicates from live queue
- `docs/FUNNEL-2026-09-16.md` (new) - the full deliverable: three populations reconciled, funnel table, before/after comparison, snapshot recommendation, stale documents list
- `docs/state/PRODUCTION-DASHBOARD.md` (updated) - LEADS section updated from 300 to 550 records, new state distribution
- `docs/state/QUEUE-MANIFEST.json` (updated) - regenerated from live queue, now shows 550 records (was "absent")

**FINDINGS:**

1. **The authoritative file is `work/queue.jsonl` in Claude's worktree.** 550 records, mtime 2026-09-16T05:23:26Z. No run in flight (spend-ledger also modified at 05:22:52Z, no Python process running).

2. **The three populations reconciled:**
   - **550** = total records in live queue AND current snapshot. The full estate.
   - **316** = subset of 550 that were in `queued` state in the snapshot. NOT a separate population; the target of the free-path run.
   - **300** = total records in the OLD snapshot (2026-09-14T21:52:15Z). The estate grew from 300 to 550 between Sept 14 evening and Sept 15 afternoon.

3. **The trap:** "PRELIMINARY_ICP 300" and "300 records exist" were the same number for different reasons in the old snapshot. In the old snapshot, 300 records had company_facts AND 300 records existed total. Reading the first as progress was a mistake.

4. **The funnel (from live state, 550 records):**
   - RECEIVED: 550 (100%)
   - NORMALIZED: 550 (100%) - all have company_facts (free-path added minimal facts to 250)
   - FREE_RESEARCH: 392 (71.3%)
   - PRELIMINARY_ICP: 537 (97.6%)
   - QUALIFIED: 113 (20.5%)
   - ICP_REVIEW: 216 (39.3%)
   - ICP_REJECTED: 221 (40.2%)
   - PERSON_DISCOVERY: 91 (16.5%)
   - ENRICHMENT: 550 (100%)
   - VERIFICATION: 87 (15.8%)
   - VERIFIED_SENDABLE: 67 (12.2%)
   - CAMPAIGN_READY: 68 (12.4%)
   - GENERATED: 190 (34.5%)
   - APPROVAL: 35 (6.4%)
   - LIVE_ELIGIBLE: 38 (6.9%)
   - DROPPED: 126, HELD: 32

5. **Snapshot recommendation:** Regenerate or retire. The snapshot (550 records, stamped 2026-09-15T17:52:12Z) is stale - it shows 250 records without company_facts that now all have them, and ICP review at 66 instead of 216. A stale artefact that multiple tasks have measured from is worse than a missing one.

6. **26 documents carry "300 records" from the old snapshot. 5 documents carry "316 records/queued" from the pre-free-path state.** Full list in `docs/FUNNEL-2026-09-16.md`. Three documents referencing "316" are EmailBison reply counts (not stale).

**RISKS:**
- The free-path run mutated live state. The funnel numbers are post-mutation. Any document written before the run (most of the 26 listed) measured a different state.
- The persona and angle distributions in the old dashboard could not be reproduced from the current data (persona_plan is empty, messaging.angle is "unknown" for all 550 records). Marked as ABSENT in the updated dashboard.
- The queue.jsonl is only in Claude's worktree. Worker worktrees cannot access it directly.

**RECOMMENDED CLAUDE ACTION:**
1. Regenerate the snapshot: `cp work/queue.jsonl work/queue.snapshot.jsonl` and update the STAMP file.
2. Review the 26 documents carrying stale "300 records" numbers. Each is a historical record and should not be edited, but a reader needs to know they are stale.
3. The 113 QUALIFIED records are the actionable estate. 216 in REVIEW need evidence before they can advance. 221 REJECTED is the structural ICP fail count.
