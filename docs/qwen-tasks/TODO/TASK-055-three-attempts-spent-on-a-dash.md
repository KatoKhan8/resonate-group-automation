# TASK-055 - Three attempts spent on a punctuation character

## THE FINDING, MEASURED

`lint` refuses an em dash, en dash, curly apostrophe or non-breaking hyphen.
The rule is right: those characters arrive as mojibake in some clients, and
`SUBSTITUTED_PUNCTUATION` has been in this repository for a long time.

What is wrong is what happens next. Regenerating `ogpartner-dk` and
`acqcom-com` live on 2026-09-14, the six `em4` refusals broke down as:

    em dash / curly punctuation   4
    structural repetition          3
    repetition across rungs        1
    the body is under 40 words     1
    the subject is 60 characters   1

Four of six. And `generate.draft` allows THREE attempts, so a step whose
first two drafts carry a dash has one attempt left for everything else -
which is how `em4` ends up never written at all. The record log shows runs
where all three attempts died on punctuation.

`generate.linkedin_note` now has the same loop and the same exposure: two of
six notes in an earlier run carried an em dash.

## THE QUESTION THIS TASK HAS TO ANSWER FIRST

**Is a dash a CONTENT failure at all?**

Every other thing lint refuses is about what the message SAYS. A dash is
about how a character is encoded. Regenerating a whole draft because of one
character throws away a message that may have been good, spends a model call,
and - four times in six - spends the last one.

There are three defensible answers and they are not the same:

  A  keep regenerating. The model should write plain ASCII and a draft that
     does not is a draft that ignored its brief.
  B  normalise the character and keep the draft. An em dash becomes " - ",
     a curly apostrophe becomes "'". The words are untouched.
  C  normalise, and do not count the attempt.

**B and C are the ones to think hardest about**, because normalising is
EDITING A DRAFT, and `CLAUDE.md` says a failing draft is regenerated, never
patched. Read that rule and decide whether it applies to a character
substitution that changes no word - and if you conclude it does not apply,
say precisely why, because that argument is the whole deliverable.

Do NOT widen `SUBSTITUTED_PUNCTUATION` or remove the check under any of the
three answers. What reaches the provider must still be plain ASCII.

## MEASURE BEFORE DECIDING

1. Across the estate's stored `rejected` log entries, how often is
   punctuation the reason? Break it down by step key.
2. When a draft fails on punctuation alone, does the NEXT attempt pass? If
   the retry reliably fixes it, answer A costs one call and nothing else.
   If the model repeats the dash, A is a loop that never terminates.
3. Does the prompt already forbid it clearly? Both prompts carry a plain
   ASCII rule. If the model is being told and ignoring it, that is evidence
   about A.

Report the numbers. The recommendation follows from them, not from taste.

## IF THE ANSWER IS B OR C

Normalisation belongs in ONE place, with one implementation, applied before
lint - not in `draft`, again in `linkedin_note`, and again anywhere else a
model answer arrives. Find where model output is first turned into a step
and put it there. Two copies of a character map is how they drift.

The mapping is exactly `lint.SUBSTITUTED_PUNCTUATION` and nothing else. Do
not "tidy" any other character.

## PROVE IT

Behavioural. A model whose first answer carries an em dash and whose second
is clean: assert what gets stored, how many attempts were spent, and that the
stored text contains no character from `SUBSTITUTED_PUNCTUATION`. Then break
it deliberately and confirm the intended test fails for the intended reason.

## WHAT YOU MAY NOT DO

- Do not widen or remove the punctuation rule.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- No live provider call, no campaign mutation.
- Do not change `EMAIL_FIVE_LADDER` rung 5.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
