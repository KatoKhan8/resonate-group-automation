# TASK-061 - Drive the HeyReach regeneration to a passing dry run

## THE STATE THIS STARTS FROM

`heyreachfactory._plan` refuses the campaign whenever ANY complete contact's
LinkedIn copy repeats itself. The refusal names one contact at a time, so the
blocker MOVES as each is fixed. Observed today, in order:

    pass 1   acqcom-com/brian-price      connected_1 vs connected_4
    pass 2   adcuratio-com/ranjan-damodar connected_1 vs 2, 3, 4; 2 vs 4; 3 vs 4

That second one is worse than the first: five colliding pairs on one contact,
all sharing "across", "capacity", "projects". Four messages arguing capacity
in four different sentences is exactly the defect the operator named.

## GOAL

`py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1`
exits 0 - that is, the DRY RUN stops raising `FactoryRefused`.

## THE LOOP

    1  copy work/queue.jsonl to a scratch path OUTSIDE the repository
    2  point QUEUE at the copy. NEVER at the real file.
    3  py -3 -m src.generate --live --client productive
    4  py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1
    5  if it refuses, record WHICH contact and WHICH pairs, then repeat

It is idempotent: the planner only re-plans steps that fail a gate, so a
second pass costs far less than the first.

**STOP AFTER FIVE PASSES** even if it has not converged, and report the
sequence of blockers. Five passes that keep naming new contacts is itself the
finding - it would mean the model cannot satisfy the ladder for this cohort
and the answer is a prompt change rather than another pass.

## WHAT TO REPORT, AND IT IS THE DELIVERABLE

    the blocker at each pass: contact, colliding roles, shared words
    how many records still fail after the last pass
    model calls spent per pass
    whether the shared words are SUBJECT words (capacity, profitability,
      utilisation) or STRUCTURAL ones - that distinction decides whether the
      fix is the ladder or the gate, and Claude will make that call

## DO NOT PROMOTE THE SCRATCH QUEUE YOURSELF

You may not write `work/queue.jsonl`. When the scratch copy reaches a passing
dry run, say so and say where the scratch file is. Claude promotes it after
review. That boundary is not negotiable: the queue is the canonical record of
every prospect and `src/store.py` is its only door.

## WHAT YOU MAY NOT DO

- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- NO provider write. You hold real keys; the dry run is a dry run and
  `--live` on that script is Claude's to run, never yours.
- Do not weaken `campaign_repetition`, `repetition_across_rungs`,
  `_note_quality` or any gate to make the dry run pass. The gate refusing is
  the system working; four messages about capacity is the thing being fixed.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.
