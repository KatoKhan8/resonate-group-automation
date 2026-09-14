# TASK-047 - Four emails, different words, one formula

## THE FINDING, MEASURED

Four of the five staged Productive emails open with the same SHAPE:

    [the company's own self-description]
    -> [why I am writing, stated by role]
    -> [the ask]

Regenerated live on `ogpartner-dk` 2026-09-14, after the prompt gained a
product block, em1 and em2 still read:

    em1  "Your agency describes itself as creating custom-made solutions
          that adapt to the ever-changing market. I am reaching out to you
          as the founder because..."
    em2  "Your agency highlights work on diverse campaigns like Bestseller
          and Nilfisk, showing a strong focus on creative execution. I am
          reaching out to you as the founder because..."

Different words. One formula. And "I am reaching out to you as the founder"
appears in both, which reads as if the SENDER holds that title.

`quality.repetition_across_rungs` passed all of it, correctly by its own
rule: it counts shared distinctive WORDS, and a formula that varies its
nouns shares almost none.

## GOAL

A check that catches structural repetition - the same message SHAPE reused
across rungs - and reports which rungs collide and on what.

## WHAT "SHAPE" MEANS HERE, CONCRETELY

You are not writing a general-purpose essay grader. The shape of a cold
email as this system generates it is a short sequence of moves, and the
detectable ones are:

    opening move      does sentence one describe THEM, describe US, ask a
                      question, or state an observation?
    self-reference    does a sentence introduce the sender by role
                      ("I am reaching out to you as the founder")?
    closing move      does the last sentence ask a question, propose a
                      call, or offer an out?
    question count    how many questions the message asks

Two rungs collide when their opening move AND closing move are the same.
That is a starting definition, not a requirement - if you find a better one
while measuring, say so under FINDINGS and defend it with numbers.

## WHERE IT GOES

`src/quality.py` already owns this question and already has the right shape
of API: `gate(text, config, steps=..., channel=..., ignore=...)` returns
`{verdict, reasons, detail}` and `repetition_across_rungs` is its
cross-step half. Add beside it, do not build a parallel module.

## THE TRAP THIS TASK IS MOST LIKELY TO FALL INTO

A structural check that is too eager fails good copy. Measured precedent in
this repository, and read it before you tune anything: `quality.gate`'s own
docstring records that applying the LinkedIn angle rule to email failed 51 of
70 staged steps AND the human-approved canary on campaign 451. A gate that
fails good copy is worse than none.

So: measure your check against the real estate BEFORE wiring it into
anything. Report how many of the currently stored steps it would refuse. If
it refuses the 451 canary copy, it is wrong.

## PROVE IT IS CONSUMED

A function in `quality.py` that nothing calls is the recurring defect here.
Trace and prove: the check runs at the point copy is STORED (see
`generate.draft`, which runs lint, claims and the quality gate inside the
attempt loop and regenerates rather than patching), the reason reaches the
model on retry through `lint.explain`, and a colliding draft is not stored.

## WHAT YOU MAY NOT DO

- Do not widen or weaken `repetition_across_rungs`. Add beside it.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- No live provider call, no live model call, no campaign mutation.
- Do not change `EMAIL_FIVE_LADDER` rung 5. EmailBison 481 holds nine real
  leads carrying approved copy generated against it.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
