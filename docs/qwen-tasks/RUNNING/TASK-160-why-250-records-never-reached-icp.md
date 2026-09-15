PRIORITY: P0
DEPENDS:

# TASK-160 - 250 of 550 records have no ICP verdict at all

`scripts/funnel.py` measures it: `qualification.verdict.icp_status` is absent
on 250 records. Not rejected, not review - absent. They have never been
qualified, and that is the estate's real bottleneck, not intake.

## FIND THE CAUSE, DO NOT GUESS IT

Exactly one of these, with evidence:

    scheduler              nothing ever selected them
    missing research       `research.why()` blocks qualification
    provider dependency    a paid call they never got
    qualification gate     `qualify` refuses them for a stated reason
    state-transition bug   they moved past the stage without being scored
    worker capacity        the batch simply never ran that far
    deliberate backpressure

Read `src/qualify.py` and `src/run.py` for the selection predicate, then check
the 250 against it: do they MATCH the predicate and get skipped, or fail to
match at all? Those are different defects.

Group the 250 by `state`, `lane` and whether they have `company_facts` and
`research`. The shape of that table usually names the cause on its own.

## DELIVERABLE

`docs/ICP-BOTTLENECK-2026-09-15.md`: the cause with the evidence, the count
per contributing reason, and the smallest change that would move them. If it
is a defect, name the file and function.

## RULES

Read-only on `work/`. No provider writes. No model calls. Do not run `qualify`
against the real queue - that is Claude's. Quote the snapshot stamp.

---

## RESULT

- **STATUS:** DONE
- **COMMIT:** (to be committed)
- **TESTS:** Read-only analysis of snapshot and source code; no production code changed
- **FILES CHANGED:**
  - `docs/ICP-BOTTLENECK-2026-09-15.md` (new) — the deliverable
- **FINDINGS:**
  - Snapshot: `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
  - **Cause: worker capacity — the batch simply never ran that far**
  - The 250 records were ingested on 2026-09-15 at 13:37:19 UTC from `productive-intake-00000-00250.csv`
  - The snapshot was taken at 17:52:12 UTC — 4 hours 15 minutes later
  - No runner was invoked in that window; EXECUTION-LOG.md has no entry for 2026-09-15
  - All 250 records are in state `queued`, lane `domains`, with no `company_facts`, no `research`, no `stages` field
  - They match every selection predicate and are ready to be processed
  - The 300 records with verdicts were ingested on 2026-09-09 and processed through the full pipeline
  - TASK-152 already identified this: "250 of 550 are raw intake (not yet qualified)" and recommended "Run qualify on the 250 already queued (free, no credits)"
  - Not a defect in selection predicate, qualification gate, state-transition logic, or provider dependency
  - Contributing reasons: 250 records, all one reason (runner not invoked since ingestion)
- **RISKS:**
  - The 250 records are from a purchased list skewed toward micro-agencies (median 5 employees per TASK-152). The 300-record baseline showed 40% ICP rejection rate, so expect ~100 rejections and ~150 qualified/review.
  - Enrichment (next stage after qualify) costs credits: ~471 credits for 150 qualified records at 3.14/record.
  - 36 records from the 300-record baseline are held with unresolved email verification; this gap may recur.
- **RECOMMENDED CLAUDE ACTION:**
  1. Run `python -m src.run --client productive --stage qualify` to process the 250 records (free, no credits)
  2. Review ICP verdicts: expect ~150 qualified/review, ~100 rejected
  3. For the ~150 that pass, run enrichment with a cap: `python -m src.run --client productive --stage enrich --spend --cap 500`
  4. Decide on next batch size based on actual yield from the 250
