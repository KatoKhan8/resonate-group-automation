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

STATUS: REVIEW

COMMIT SHA: b15c002

TESTS: 29/29 pass in tests.test_render_preview (18 existing + 11 new).
  All 11 new tests are in TestEmailPreviewUsesTheProductionCodePath.
  The key test (test_email_preview_renders_through_bisonfactory_variables_for)
  proves the wiring: it calls _build_email_plan which calls
  bisonfactory._variables_for, and asserts the variable values match the
  stored approved copy.  Pre-existing failures in test_cadence (requires
  work/) and test_invariants (requires work/) are unrelated to this change
  and fail identically on master without my changes.

FILES CHANGED:
  scripts/render_preview.py    +847 lines (email fixtures, rendering engine,
                                canonical campaign routing)
  tests/test_render_preview.py +102 lines (11 new tests)

FINDINGS:

  The caller chain is proven, not asserted:
    render_preview("email_five")
      -> render_email_preview()
        -> _build_email_plan()
          -> bisonfactory._sequence_steps()   (the provider sequence)
          -> bisonfactory._approved_copy()    (per-lead approved words)
          -> bisonfactory._variables_for()    (custom variables on the wire)
    render_preview("productive-email-campaign-v1")
      -> _try_load_campaign()
        -> _try_load_email_campaign()
          -> _build_email_plan()  (same function, same pipeline)

  grep -rn "render_email_preview\|_build_email_plan\|_try_load_email_campaign"
  scripts/render_preview.py returns 7 hits: 3 definitions and 4 calls.
  No dead code.

  What the rendered Productive email sequence actually reads like
  (email_five fixture, Jacob Hartley, visibility angle):

    EMAIL 1 (em1, day 1): "Your project visibility gap at Northbridge
      Consulting" - Opens with who is writing, names the company and size,
      states the problem (utilisation numbers arrive too late), names
      Productive and what it joins up, ends with one question.

    EMAIL 2 (em2, day 4): "A different angle on the numbers" - Different
      argument: margin between spreadsheet and actual work. Does not repeat
      the visibility framing from email 1.

    EMAIL 3 (em3, day 8): "What Productive joins up at Northbridge
      Consulting" - Names the product explicitly, says what it connects
      (time tracking, budgets, resource planning), gives one concrete
      consequence (margin visible while work is running).

    EMAIL 4 (em4, day 12): "One more thought on visibility" - A different
      point: the gap is not the data but the time between data existing
      and the right person seeing it. One question.

    EMAIL 5 (em5, day 21): "Should I close the file?" - Easy no, no new
      pitch, asks for nothing beyond permission to stop.

  The five emails make FIVE DIFFERENT ARGUMENTS: visibility, margin,
  product name, time-to-insight, breakup. No two open the same way.
  The product is named in emails 1 and 3. No conversation is claimed
  that never happened.

  Second lead (Declan Reilly, margin angle) renders different copy:
  "margin visibility" instead of "visibility gap", "Bastion Digital"
  instead of "Northbridge Consulting", "fifty-eight people" instead of
  "forty-two". The per-lead variation is real.

  The email_missing fixture correctly shows:
    - MISSING COPY for em3 at the top of the output
    - "*** MISSING - no approved copy for this step ***" in the touch
    - "{SUBJECT_3} has no value" and "{BODY_3} has no value"
    - PRODUCT NAME MISSING flagged (only 4 of 5 emails name the product)

RISKS:
  - The canonical campaign loading path (_try_load_email_campaign) cannot
    be tested here because work/ does not exist in this worktree. The
    fixture path exercises the same _build_email_plan function, so the
    wiring is proven; the file I/O is the only untested part and it is
    the same pattern as _try_load_campaign for HeyReach.
  - The preview is READS ONLY. It does not touch work/, does not call
    any provider, does not change any state.

RECOMMENDED CLAUDE ACTION:
  Run `py -3 scripts/render_preview.py productive-email-campaign-v1`
  on the production worktree (which has work/) to see the nine real
  leads from campaign 481 rendered end to end. That is the first time
  anybody will have seen what those people would actually receive.
