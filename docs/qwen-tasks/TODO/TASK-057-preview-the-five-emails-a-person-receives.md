# TASK-057 - The email side of the preview does not exist

## WHY

`scripts/render_preview.py` renders the LinkedIn campaign: every role, the
merge variable, the lead's own words, the fallback, and the RESULT a person
reads. Reading it is what found the four-questions-in-a-row defect, and it
is the reason the LinkedIn copy problem is understood at all.

The EMAIL side has no equivalent. Campaign 481 holds nine real leads carrying
`subject_1`..`subject_5` and `body_1`..`body_5` as per-lead custom variables,
and nobody can read what one of those people would actually receive without
querying the provider by hand.

The operator's requirement, verbatim: "Before meaningful scale, produce
representative FINAL RENDERED previews. For each selected prospect show
EMAIL 1, EMAIL 2, EMAIL 3, EMAIL 4, EMAIL 5 and the applicable LinkedIn
path."

## GOAL

`py -3 scripts/render_preview.py <canonical-campaign-id>` renders the EMAIL
sequence for a campaign whose channel is email, the same way it already
renders LinkedIn.

## WHAT EACH TOUCH MUST SHOW

The operator named these and they are the specification:

    DAY              from the cadence step
    CHANNEL          email
    PURPOSE          the rung's job, from the ladder
    ANGLE            the contact's angle
    VARIANT          where a variant is assigned
    EVIDENCE USED    what the draft was grounded in
    VARIABLES        {SUBJECT_1}..{BODY_5} - the provider-side names
    FALLBACKS        what EmailBison sends if a variable is not supplied
    FINAL RENDERED   subject and body, as the person reads them
    NEXT BRANCH      what happens next, and on what condition

## READ THE SAME PATH THE PROVIDER READS

This is the part that matters and the part easy to get wrong. The preview
must render from the SAME code that builds the provider payload, not from a
second implementation of it. The LinkedIn side says so in its own header -
"Rendered from cadence.expand_step - the SAME code path that builds the
provider payload via push.payloads()" - and that property is the only reason
the preview can be trusted.

For email that path runs through `bisonfactory` and the per-lead custom
variables. Find where `subject_1`..`body_5` are actually assembled and render
from there. If you find yourself formatting a subject line by hand, stop:
you are building the second representation this whole file exists to avoid.

## THE THING IT MUST MAKE VISIBLE

A person reading the output must be able to see, without cross-referencing:

  - whether the five emails make FIVE different arguments or one argument
    five times
  - whether any of them claims a conversation that never happened
  - whether the product is ever named
  - whether two of them open the same way

Those are the four defects found in this copy in the last two days. The
preview's job is to make the fifth one obvious before it reaches anybody.

## ALSO

Print a MISSING line for any step with no approved copy, the way the
LinkedIn side does. A campaign with three of five emails approved must not
render as a three-email sequence with no comment - that is how a gap gets
discovered in front of a client.

## WHAT YOU MAY NOT DO

- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`. Read only.
- No live provider call. The preview renders from canonical state; it is not
  a provider readback and must not pretend to be one.
  `scripts/heyreach_readback.py` is the readback and it is a different tool
  answering a different question.
- Do not change what is stored. This renders; it does not fix.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION. FINDINGS should say what the rendered
Productive email sequence actually reads like, because that is the first
time anybody will have seen it end to end.
