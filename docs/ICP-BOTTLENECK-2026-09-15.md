# ICP Bottleneck Analysis — 2026-09-15

**Snapshot:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

## The number

250 of 550 Productive records have no ICP verdict. Not rejected, not review — absent. They have never been qualified.

## The cause, with evidence

**Worker capacity: the batch simply never ran that far.**

The 250 records were ingested on 2026-09-15 at 13:37:19 UTC from `productive-intake-00000-00250.csv`. The snapshot was taken at 17:52:12 UTC — 4 hours 15 minutes later. In that window, no runner processed them.

### Evidence

**Shape of the 250 records:**

| Field | Value | Count |
|---|---|---|
| state | queued | 250/250 |
| lane | domains | 250/250 |
| company_facts | absent | 250/250 |
| research | absent | 250/250 |
| stages | absent | 250/250 |
| log | ingested from productive-intake-00000-00250.csv | 250/250 |

**Comparison with the 300 records that WERE processed:**

| Field | 250 (no verdict) | 300 (has verdict) |
|---|---|---|
| Ingested | 2026-09-15 13:37:19 | 2026-09-09 13:23:58–13:24:24 |
| Source file | productive-intake-00000-00250.csv | productive-live-pilot-0250.csv (200), productive-live-pilot-0050.csv (50) |
| Has company_facts | 0/250 | 300/300 |
| Has research | 0/250 | 207/300 |
| Has stages | 0/250 | 298/300 |
| States | queued (250) | drafted (44), held (36), dropped (125), approved (3), queued (66), verified (26) |

The 300 records were ingested 6 days earlier and processed through the full pipeline. The 250 records arrived on the same day the snapshot was taken and were never processed.

### Why they were not processed

The runner (`src/run.py`) walks the queue in stages: `enrich -> qualify -> personas -> generate -> render -> push`. Each stage checks `needs(rec, stage)` before processing. The 250 records have no `stages` field, so `needs(rec, "enrich")` returns True for all of them — they are eligible for processing.

The enrich stage (`stage_enrich` in `src/run.py`) iterates over target records and calls `enrich.enrich_record` for each. The selection logic in `enrich.run()` filters by state: `states=("queued", "enriched")` by default. All 250 records are in state `queued`, so they match the predicate.

**The runner was never called on these records.** There is no execution log entry for 2026-09-15 in `EXECUTION-LOG.md`. The last recorded run is 2026-09-12, which processed the original 300 records. The 250 new records were ingested but no subsequent run was executed to process them.

This is not a defect in the selection predicate, qualification gate, or state-transition logic. The records match every predicate and are ready to be processed. The cause is simply that no runner has been invoked since they arrived.

### TASK-152 confirms this

TASK-152 (`docs/qwen-tasks/DONE/TASK-152-the-intake-backlog-is-20944-domains.md`) measured the same snapshot and reported:

> "250 of 550 are raw intake (not yet qualified) from `productive-intake-00000-00250.csv`"

The recommended action was:

> "Run qualify on the 250 already queued (free, no credits)"

The task identified the bottleneck but did not run the processing, because TASK-152's rules forbade running the runner against the real queue ("Do not run `src.ingest` against the real queue. Production state is Claude's.").

## The smallest change that would move them

**Run the runner on the 250 records.** This is free for the qualify stage (no provider calls, no model calls):

```bash
python -m src.run --client productive --stage qualify --limit 250
```

This will:
1. Classify each company against the client's ICP config
2. Score each company and assign an ICP verdict (qualified, review, rejected)
3. Write the verdict to `qualification.verdict.icp_status`
4. Mark `stages.qualify.status = "done"`

Expected outcome (derived from the 300-record baseline):
- ~60% qualified or review (150 records)
- ~40% rejected (100 records)
- 0 credits spent (qualify is deterministic, no provider calls)

After qualification, the enriched records can proceed to enrichment (person discovery, email verification), which DOES cost credits and requires `--spend --cap N`.

## Contributing reasons, counted

| Reason | Count | Notes |
|---|---|---|
| Runner not invoked since ingestion | 250 | No defect; operational gap |
| Selection predicate failure | 0 | All 250 match the predicate |
| Qualification gate refusal | 0 | No record reached the gate |
| Provider dependency | 0 | Qualify spends nothing |
| State-transition bug | 0 | All 250 are in valid state `queued` |
| Deliberate backpressure | 0 | No hold or pause reason recorded |

## File and function references

- **Selection predicate:** `src/run.py:stage_enrich()` line ~180, iterates records and checks `needs(rec, "enrich")`
- **Enrichment runner:** `src/enrich.py:run()` line 1292, filters by `states=("queued", "enriched")`
- **Qualification runner:** `src/run.py:stage_qualify()` line ~240, calls `qualify.company(rec, config)`
- **Qualification logic:** `src/qualify.py:company()` line ~120, writes `rec["qualification"]` with verdict
- **Funnel measurement:** `scripts/funnel.py:classify()` line ~70, counts records by stage

## Risks

- The 250 records are from a purchased list (`productive-intake-00000-00250.csv`) that TASK-152 found skewed toward micro-agencies (median 5 employees). The 300-record baseline showed a 40% ICP rejection rate driven by size <20 employees. The same rate may apply to the 250, yielding ~100 rejections and ~150 qualified/review.
- Enrichment (the next stage after qualify) costs credits: 1,725 credits for the 300-record baseline (3.14/record). Processing 150 qualified records from the 250 would cost ~471 credits.
- 36 records from the 300-record baseline are held with unresolved email verification (accept_all domains). This gap has no resolution path and may recur in the 250.

## Recommended Claude action

1. Run `python -m src.run --client productive --stage qualify` to process the 250 records (free, no credits)
2. Review the ICP verdicts: expect ~150 qualified/review, ~100 rejected
3. For the ~150 that pass, run enrichment with a cap: `python -m src.run --client productive --stage enrich --spend --cap 500`
4. Decide on next batch size based on actual yield from the 250

---

**Analysis performed by:** TASK-160  
**Date:** 2026-09-15  
**Method:** Read-only analysis of `work/queue.snapshot.jsonl` and source code. No provider calls, no model calls, no writes to `work/`.
