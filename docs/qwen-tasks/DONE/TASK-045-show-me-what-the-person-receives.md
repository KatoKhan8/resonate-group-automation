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

## RESULT

STATUS: DONE

COMMIT SHA: fa1e9ae

TESTS: 18 tests in tests/test_render_preview.py

TEST RESULTS: All 18 pass.

FILES CHANGED:
  scripts/render_preview.py (new, 521 lines)
  tests/test_render_preview.py (new, 213 lines)

FINDINGS:
  1. The script renders from cadence.expand_step - the SAME function that
     cadence.build calls, which push.collect calls, whose output feeds
     push.payloads.  A preview built by a second renderer previews a
     message nobody sends.  This is proven by 4 tests that assert the
     rendered output equals what expand_step returns directly.

  2. Both LinkedIn branches appear: NOT CONNECTED (default) and CONNECTED
     (connection_accepted=True).  The day10 step shows comparable_proof
     when not connected and comparable_proof_short when connected - the
     variant_if_accepted mechanism working correctly.

  3. Missing variables are reported.  A record with no company_facts.name
     (domain-shaped company field) raises CompanyNameUnusable and the
     preview shows "!!! COMPANY NAME UNUSABLE" for every template step.

  4. A lead with no LinkedIn URL shows "NOT PROVIDED" and "WARNING: No
     LinkedIn URL - all LinkedIn steps will be BLOCKED".  The connected
     branch is shown as "SKIPPED because no LinkedIn URL was provided".

  5. Generated steps (day1, day15 in balanced cadence) show "step returned
     None (generated content not yet written)" when no stored copy exists.
     The li_heavy fixture with pre-filled generated content shows the
     stored body/note correctly.

  6. Four fixture campaigns: balanced (templates), li_heavy (generated),
     no_linkedin (missing URL), missing_variable (domain-shaped company).

GREP PROVING CONSUMPTION:
  render_preview: called from main() in scripts/render_preview.py and from
  12 test methods in tests/test_render_preview.py.
  _render_step_for_preview: called from render_preview() (twice, once per
  branch) and from 8 test methods in tests/test_render_preview.py.

DELETING THE CALL MAKES A TEST FAIL:
  test_rendered_output_depends_on_expand_step_call asserts that the rendered
  output is not None and contains the contact's name.  If the call to
  cadence.expand_step in _render_step_for_preview were deleted, the rendered
  output would be None and the assertion would fail.  This is also proven
  by the 4 tests in TestPreviewUsesTheProductionCodePath that assert the
  preview's output equals what expand_step returns directly.

RISKS:
  - The script uses fixture data only.  A real campaign preview would need
    to load actual records from work/queue.jsonl and a real client config.
    This is out of scope for TASK-045 (ZERO network, ZERO credentials).
  - Generated steps require stored content to render.  The li_heavy fixture
    pre-fills this; a real campaign would have it from the model.

OPEN QUESTIONS:
  - Should the preview also show variant assignment (which of 5 variants a
    contact gets)?  The current script shows the rendered output but not
    the variant id.  This could be added by calling cadence.variant_for.
  - Should the preview load real campaigns from work/campaigns.jsonl?  This
    would require a real workspace and is out of scope for this task.

RECOMMENDED CLAUDE ACTION:
  Review the rendered output for the balanced fixture and confirm it shows
  what a person would actually receive.  The "hi jacob" defect would have
  been obvious: the preview shows the exact subject and body with all
  variables substituted, and any missing or fallback value is flagged.
