# TASK-045 - Render what the person actually receives

The operator: "A template passing lint is not sufficient. I want us to be able
to inspect what the PERSON ACTUALLY RECEIVES."

## GOAL

A QA artifact that shows, for several representative leads and every step of
both channels:

    RAW TEMPLATE  ->  VARIABLES  ->  FINAL RENDERED COPY

## WHY IT MATTERS

Every gate in this system checks a template or a fragment. Nothing has ever
assembled the whole thing and shown a human the message. The "hi jacob" defect
survived a green test suite, a sequence readback and a field-for-field
comparison - and would have been obvious in one rendered preview.

It also catches the class of defect no unit test reaches: a variable that
renders empty, a fallback that fires, a sentence that reads wrong once the
substitutions land, two steps that look different as templates and identical
once rendered.

## SCOPE

1. A script producing the artifact for a named campaign, defaulting to a
   handful of representative leads rather than all of them.
2. Render EVERY step of both channels, and for the LinkedIn side render EVERY
   BRANCH - an already-connected prospect and a not-yet-connected one receive
   different sequences, and both must be shown.
3. Show which variables were supplied, which were missing, and WHERE A
   FALLBACK WOULD FIRE. A fallback firing in a preview is the loudest signal
   this artifact can produce.
4. Show the same lead across all five variants of a step where they exist.
5. Output human-readable. This is for a person to read before promotion, not
   for a machine.
6. It must render from the SAME code path that builds the provider payload.
   A preview built by a second renderer previews a message nobody sends.

## PRODUCTION BOUNDARY

ZERO network, ZERO credentials - `config/.env` does not exist in this
worktree. No provider call. No write to `work/**`. Nothing staged, activated
or sent. Claude owns every live action.

## HANDOFF FORMAT

STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS / BUGS FOUND /
BUGS FIXED / RISKS / OPEN QUESTIONS / RECOMMENDED CLAUDE ACTION

Plus the grep proving each new name is CONSUMED, and confirmation that
deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- the rendered output for a fixture lead matches what `build_lead_pairs` plus
  the sequence would actually produce - assert they agree rather than
  eyeballing;
- a missing variable is reported as missing and the fallback shown;
- both LinkedIn branches appear;
- a lead with no LinkedIn URL is reported rather than skipped silently.

## DONE CONDITION

`python scripts/render_preview.py <campaign>` prints, for representative
leads, every step of every branch with its variables and final text - and a
reviewer can tell from it alone whether the campaign is fit to send.
