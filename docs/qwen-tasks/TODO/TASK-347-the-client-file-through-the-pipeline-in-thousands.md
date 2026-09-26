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
