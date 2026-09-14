# TASK-087 - the variants generate now, and they are all the same message

## WHERE THIS STANDS

TASK-084 fixed the two defects that stopped variants working:

    LinkedIn variants   ZERO -> FOUR per step   (the JSON contract)
    diversity check     now compares STRUCTURE, not word overlap

Both are on master and both work. **And the check's verdict on the real
output is: NOT materially different.** That is the check doing its job, and
it is the whole problem that remains.

Measured on `ogpartner-dk` / Jacob Faertz, li2, against the real model:

    [short_direct]   "hi jacob, this is a quick note from someone working with
                      agencies on resourcing visibility. how do y..."
                      opening=question  cta=question  words=27
    [casual]         "hi jacob, this is a quick one from me at Productive. how
                      do you currently get visibility on who's bo..."
                      opening=question  cta=question  words=27
    [professional]   "hi jacob, this is a quick note from someone working on
                      agency resourcing visibility. how do you curr..."
                      opening=question  cta=question  words=28
    [peer_to_peer]   "hi jacob, this is a quick one from me at Productive. how
                      do you currently get visibility on who's bo..."
                      opening=question  cta=question  words=32

Four approaches. One message. `casual` and `peer_to_peer` are nearly
identical strings. Every arm opens with a question and closes with a
question, and the word counts sit between 27 and 32.

**This is exactly what the operator named: "A = Hey John, B = Hi John, C =
Hello John is not an experiment."**

## THE QUESTION THIS TASK ANSWERS

Why does asking for five different approaches produce one message four times?

The check is no longer the problem - it correctly refuses these. The
GENERATION is. Investigate, in this order, and report which it is:

1. **Do the approaches reach the model at all?** Dump the ACTUAL rendered
   prompt for two different approaches and diff them. If `short_direct` and
   `casual` produce prompts that differ by one adjective, the model is
   behaving reasonably and the briefs are the defect. This is the same
   question TASK-039 asked of the ladder and the answer there was a defect.
2. **Are the approach descriptions distinguishable to a model?**
   "Professional. Full sentences, no abbreviation." is a register
   instruction, not a structural one. None of the five appears to say
   "open with a statement, not a question" or "do not ask anything".
3. **Does the rung purpose overpower the approach?** If li2's ladder brief
   says "put it as a question about how they handle it today", then EVERY
   arm is being told to ask a question and the approach cannot overrule it.
   That would explain opening=question and cta=question across all four
   exactly.

Hypothesis 3 is the most likely and the cheapest to check first. Check it
first.

## WHAT A FIX LOOKS LIKE

Approaches must vary things the ladder does not already fix. If the rung
says "ask a question", an approach that says "be conversational" can only
change the adjectives.

So either the approach must be able to override the rung's FORM while
keeping its JOB - the job is "establish the resourcing angle", the form is
free - or the approaches must vary a dimension the rung leaves open.

**Do not solve this by loosening the diversity check.** It is now correct and
it is the only thing standing between four paraphrases and a live
experiment. If the copy cannot be made different, the honest outcome is
FEWER arms, not a check that passes clones.

**Do not weaken the observation licensing.** `observation_led` is correctly
skipped when no licensed observation exists, and four honest arms beat five
manufactured ones.

## HOW YOU WILL KNOW IT WORKED

Re-run the same record and step and show the table again. The target is that
`different: True` is EARNED - at least two arms differing in opening type or
CTA type, not merely in wording. Quote the openings.

If after a real attempt the arms still collapse, say so plainly and say
which of the three causes above it is. "The rung's form instruction dominates
the approach" is a complete and useful finding, and it points at the ladder
rather than at variantgen.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** The model is yours to call.
- `work/queue.jsonl` in your worktree is NOT production state - read
  `work/queue.snapshot.jsonl` and quote its STAMP.
- Do not loosen the diversity check or its thresholds.
- Approve nothing, write no campaign.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS (the variant
table before and after, with quoted openings, and which of the three causes
it was), RISKS, RECOMMENDED CLAUDE ACTION.
