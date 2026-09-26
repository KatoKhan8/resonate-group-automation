PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-347 - the client file through the pipeline, in batches of 1,000, stopping before copy

**Operator instruction, 2026-09-26.** Run the client file through qualification,
MX, CheapVerifier, research packs and facts, **in batches of 1,000**, and
**STOP BEFORE COPY.**

## The input

    work/Productive/productive_ICP_safe_to_send (1).csv     35,043 rows

Columns: `Url` (LinkedIn), `First Name`, `Last Name`, `Job Title`, `Headline`,
`Company`, `Industry`, `Location`, `Work Email`, `Work Email Status`.

`work/` is gitignored and holds real people. **Nothing from it may be committed.**
Report counts, never rows.

## The order, and it is not negotiable

    qualification -> MX -> CheapVerifier -> research packs -> facts -> STOP

**Company before person.** `CLAUDE.md`: *"No paid person-level call before a
company reaches an explicit ICP verdict, and rejected, review and unknown all
mean zero person credits."* Qualification is first because it is what makes the
rest cheap. A batch that verifies emails before qualifying companies spends
credits on companies we will reject.

## SPEND. Read this before running anything.

`CLAUDE.md`: *"Costs are real: people-count is free, everything else burns
credits. Cap before you fan out."*

- **Pass an explicit `--cap` on every live run.** The pipeline already refuses a
  live run without one: *"a live run needs an explicit --cap. Unlimited is not a
  ceiling."* Do not work around that refusal - it is correct.
- **One batch of 1,000 first. Stop. Report actual spend per provider from the
  ledger.** Do not proceed to a second batch until the first batch's real cost
  is written into your result block. 35 batches at an unmeasured unit cost is
  how a credit balance disappears.
- Every paid call goes through `enrich`'s `spend()` so it lands in the ledger. A
  call that skips it is invisible to the audit.
- If a provider refuses, rate-limits, or returns an unpriced result, **stop the
  batch and report** rather than retrying into a cap.

## STOP BEFORE COPY means exactly this

No copy generation, no `copylint`, no staging, no provider campaign write, no
lead attach, no send, no activation. The deliverable is **enriched, qualified
records with packs and facts in the queue** and nothing downstream of that.

`docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md` is in force: no enrolments, no
provider attachments, no cohort pushes.

## Acceptance - RUN, paste real output

1. Batch 1 of 1,000 complete, with a count at every stage:

    rows in -> qualified / rejected / review / unknown
            -> MX pass / fail
            -> CheapVerifier valid / invalid / unknown
            -> packs built -> facts extracted

   Every number measured, none estimated.

2. **Real spend for batch 1, per provider, from the ledger** - not a projection.
   Then the projected cost of all 35 batches, labelled as a projection, so the
   operator can decide whether to continue.

3. **Nothing reached copy.** Assert it:

    py -3 -c "import json;\
    rows=[json.loads(l) for l in open('work/queue.jsonl',encoding='utf-8')];\
    staged=[r for r in rows if r.get('draft') or r.get('staged') or r.get('campaign_id')];\
    print('records carrying copy or a campaign:',len(staged));\
    assert not staged,'copy or staging reached the queue'"

   Name the real field if the schema differs - read `src/store.py`, do not guess.

4. Queue integrity: record count before and after, and **no record deleted.**
   *"Never delete a queue record. Drop it with a reason."*

5. Suppression honoured: no suppressed or DNC address enriched. Report the count
   skipped for that reason.

## What this task may NOT do

- Do not generate copy, stage, attach, activate or send.
- Do not run without `--cap`. Do not raise a cap to finish a batch.
- Do not commit anything from `work/`. Counts only.
- Do not touch `work/queue.jsonl` except through `src/store.py`.

---

## RESULT BLOCK

**STATUS: BLOCKED**

**COMMIT SHA:** (no code changes - findings only)

**ARTIFACT KIND:** finding

### FINDINGS - Five structural blockers prevent execution

**1. No CheapVerifier provider module on this branch.**
The task names "CheapVerifier" as a pipeline stage. The module `src/providers/cheapverifier.py` (1,141 lines, fully implemented against the live API) exists only on branch `worktree-agent-a9fe2f7a7ad9343aa` (commits `a5d50144` and `01c45d9d`). It was never merged to master or this worker branch. Even if cherry-picked, `src/waterfall.py` line 236 declares EMAIL_VERIFICATION providers as `(CONTACTOUT, DELIVERABLE, REOON)` - CheapVerifier is absent, so `waterfall.record_step` would raise `WaterfallViolation: cheapverifier is not part of the email_verification waterfall` on the first paid call. The commit message of `01c45d9d` records exactly this failure.

**2. CSV format does not match the ingest pipeline.**
The CSV has 33,887 data rows (not 35,042 - the task counted lines including header), 21,455 unique companies, columns: `Url, First Name, Last Name, Job Title, Headline, Company, Industry, Location, Work Email, Work Email Status`. `src/ingest.py` expects columns `company, domain` and deduplicates by domain - importing this CSV would drop ~12,432 rows as "duplicate domain". The queue record model is company-centric (one record per domain, contacts in an array); the CSV is person-centric. No import path exists that groups by domain and attaches multiple contacts per record from this CSV format.

**3. The queue is empty.**
`work/queue.jsonl` does not exist in this worktree. No records to process.

**4. The stage intermediate files do not exist.**
`work/stage/` directory is absent. `scripts/batch1_build.py` and the stage scripts (`stage_s3_icp.py`, `stage_s5_verify.py`, `stage_s7_copy.py`) depend on `s3-icp.jsonl`, `s5-verify.jsonl`, `mx-cache.json`, `s7-copy.jsonl` - none present. The 24k track's intermediate state was not carried to this worktree.

**5. Pipeline order mismatch.**
The task specifies: `qualification -> MX -> CheapVerifier -> research packs -> facts -> STOP`. The actual pipeline in `src/run.py` runs `enrich -> qualify -> personas -> generate -> render -> push`. Enrichment (which includes MX, verification, research, facts population) runs BEFORE qualification, with internal gates (`person_level_allowed`) that check for ICP verdict before person-level spend. The code comment states: "It is a fixed point rather than a single pass - enrichment gathers free company facts, qualification reads them, and the *next* pass is the one allowed to buy people." The task's requested order cannot be executed by the existing pipeline orchestration.

### What the CSV data looks like

```
Total rows: 33887
Unique companies: 21455
Rows without email: 0
Rows with extractable domain: 33887
```

All rows have valid work emails from which domains can be extracted.

### What exists and what it costs

- `CHEAPVERIFIER_API_KEY` is present in `config/.env` (credential exists, no code to use it)
- `config/clients/productive.yaml` declares CheapVerifier budget: `total: 100000, per_day: 95000, per_run: 10000`
- Productive verification config: `primary: deliverable, secondary: reoon, catch_all: reoon`
- ContactOut is removed from verification for Productive (still used for enrichment)

### What would be needed to proceed

1. **Integrate CheapVerifier:** Cherry-pick or re-implement `src/providers/cheapverifier.py` and add it to `waterfall.py` EMAIL_VERIFICATION providers tuple.
2. **Build a person-centric import:** Write a script that reads the CSV, groups by domain, creates one queue record per domain with all people at that company as contacts.
3. **Decide pipeline order:** Either run the existing `enrich -> qualify` fixed-point loop, or build a new orchestration that qualifies companies first (using only free company-level data) before any paid person-level calls.
4. **Populate the queue:** Import the 33,887 rows (grouped into ~21,455 domain records) before any pipeline stage can run.

### TESTS

Not run - no code changes, no pipeline execution.

### FILES CHANGED

- `docs/qwen-tasks/REVIEW/TASK-347-the-client-file-through-the-pipeline-in-thousands.md` (moved from TODO, findings added)

### RISKS

- Attempting to force execution without these prerequisites would spend credits on a broken pipeline, produce incorrect counts, or drop records silently.
- The CheapVerifier module on the other branch was written against a live API that may have changed since 2026-09-25.

### RECOMMENDED CLAUDE ACTION

1. Decide whether CheapVerifier integration is the next priority and assign it.
2. Decide whether a person-centric CSV import script should be built (it would also serve future client file imports).
3. Re-dispatch this task after blockers 1-4 are resolved, or split it into sub-tasks addressing each blocker.
