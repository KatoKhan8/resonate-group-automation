# TASK-062 - A failed regeneration leaves the bad copy in place

## THE FINDING, MEASURED

After a full regeneration pass completed on 2026-09-14, the stored estate
still holds copy that `lint` refuses:

    stored steps scanned                    630
    containing forbidden punctuation         13

    1gslab-com  li1, li3, li4    em dash
    25wat-com   li1              em dash
    28row-com   li1              em dash
    28row-com   li4              em dash AND curly apostrophe

`lint.SUBSTITUTED_PUNCTUATION` refuses all of those, and `generate.plan`
re-plans a note that fails lint - so these WERE re-planned. The regeneration
then failed to produce a replacement that passed the other gates, and
`linkedin_note` returns None without storing.

**The old, failing note stays exactly where it was.**

## THE QUESTION THIS TASK ANSWERS

Is that right?

There is a real argument for keeping it: a step with copy that fails lint is
blocked downstream anyway - `cadence.status_for` holds it, `eligibility`
refuses the payload - so nothing ships. Keeping it costs nothing and throwing
it away loses work that a later model run might improve on.

And a real argument against: a stored step that cannot ship looks like copy.
It inflates every "steps stored" count, it renders in previews, and the
`campaign_repetition` gate compares against it - so a bad sibling can block a
GOOD new note by colliding with copy that will never be sent.

That last one is not hypothetical. Establish whether it is happening.

## WHAT TO ESTABLISH, BEFORE CHANGING ANYTHING

1. How many stored steps currently fail `lint.check_step`? Break it down by
   failure code and by whether the step is generated or templated.
2. For each, has a regeneration been ATTEMPTED and failed? The `store.log`
   entries carry `rejected` reasons and attempt counts.
3. Does a failing stored note participate in the sibling comparisons -
   `_note_quality`, `campaign_repetition`, `repetition_across_rungs`? Read
   the code and answer from it, not from a guess.
4. If it does, find a real case where a failing sibling blocks a passing
   replacement. That is the finding that decides the fix.

## THE FIX IS CLAUDE'S CALL

Report what you find and RECOMMEND. Do not implement a removal of stored
copy without Claude's decision - deleting generated work is not reversible
and `CLAUDE.md` is explicit that a record is dropped with a reason rather
than deleted.

A patch that only EXCLUDES failing steps from the sibling comparisons, while
leaving them stored, is a much smaller change than deleting them and may be
the whole answer. Consider it.

## WHAT YOU MAY NOT DO

- Do not delete or overwrite stored copy.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not weaken the punctuation rule. TASK-055 already normalises on the way
  in; this is about copy stored BEFORE that existed.
- No provider write.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.
