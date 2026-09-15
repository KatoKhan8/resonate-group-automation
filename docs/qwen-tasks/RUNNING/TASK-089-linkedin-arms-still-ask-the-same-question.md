# TASK-089 - LinkedIn still collapses to four question-openers

## WHERE THIS CAME FROM

TASK-084 fixed the JSON contract and LinkedIn variants went ZERO -> FOUR.
TASK-087 found the cause of their sameness - the ladder rungs carried FORM
instructions ("asks a question"), which no approach description can overrule -
and replaced them with CONTENT jobs. Measured after that fix:

    em3   diversity_collisions FALSE   genuinely different, one arm opens
                                       with a statement where others ask
    em2   collision                    problem_led vs value_led, both
                                       statement/statement
    li3   collision x3                 concise_direct, conversational and
                                       problem_led ALL still question/question

**Email differentiates on at least one step. LinkedIn does not differentiate
at all.** That is the open half and this task closes it.

## WHAT IS ALREADY TRUE - DO NOT REDO IT

- `variantgen.APPROACHES` has FIVE approaches, not four. The fifth,
  `observation_led`, is withheld unless the record holds a licensed
  observation. Four arms on a record with no evidence is CORRECT, not a bug.
- The structural diversity check compares opening type, CTA type, tone,
  length and when the product is introduced. It is NOT word overlap any
  more. It is currently REFUSING the LinkedIn sets, which is it working.
- `LINKEDIN_APPROACH_ORDER` and `APPROACH_TO_STYLE['linkedin_message']` map
  the five approaches onto style keys.

## THE QUESTION

Why does email differentiate and LinkedIn not, when both went through the
same TASK-087 rung rewrite?

Investigate in this order and REPORT WHICH IT IS rather than fixing blind:

1. **Diff the rendered prompts.** Dump the ACTUAL rendered prompt for
   `concise_direct` and `problem_led` at li3, write both to files, and diff
   them. TASK-087 did exactly this at li2 and found four differing lines, all
   of them the approach heading. If the LinkedIn rungs STILL carry a form
   instruction that the email rungs lost, that is the answer and it is a
   one-place fix.
2. **Check the LinkedIn rung text specifically.** TASK-087 rewrote rungs. Did
   it rewrite the LinkedIn ladder, the email ladder, or a shared one? If
   LinkedIn has its own rung text, it may never have received the fix.
3. **Check the length ceiling.** A LinkedIn message has a much shorter budget
   than an email. If every arm is squeezed to ~30 words, structural variety
   may be impossible at that length and the honest answer is "LinkedIn
   supports fewer genuinely different arms than email" - which is a FINDING,
   not a failure. Say so with the measurement if that is what you find.

## WHAT NOT TO DO

- **Do not raise or weaken the diversity threshold.** The check refusing
  clones is the property worth protecting. Widening it passes more clones.
- **Do not add a form instruction back** to make arms differ. That is what
  caused this. The approach controls STRUCTURE; the rung controls CONTENT.
- **Do not break `test_rung_four_references_previous_questions`.** TASK-087
  regressed it once by stripping rung 4's reference to earlier steps. Rung 4
  must still say what previous rungs ESTABLISHED without saying what SHAPE
  this one takes.
- **Do not report a predicted table.** TASK-087's worker wrote what the model
  "should now produce" instead of running it. You have model access - all
  three `LLM_*` variables are in `config/.env` in YOUR worktree. Run it.

## DELIVERABLE

The diagnosis (which of 1/2/3 it is, with the evidence), the fix if it is 1
or 2, and a MEASURED table of opening type / CTA type / word count per arm
for li1, li2 and li3 against the real model on a real record. Plus the
`diversity_collisions` verdict per step, before and after.

Run the neighbours: variantgen, generate, ladder, prompt, claims, lint,
task075, propagation. Read every exit code off the process, never a pipe.
