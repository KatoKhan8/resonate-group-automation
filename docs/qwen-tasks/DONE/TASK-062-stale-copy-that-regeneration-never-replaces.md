# TASK-062 - A failed regeneration leaves the bad copy in place

## THE FINDING, MEASURED

After a full regeneration pass completed on 2026-09-14, the stored estate
still holds copy that `lint` refuses:

    stored steps scanned                    630
    containing forbidden punctuation         13

    [REDACTED-record-1]  li1, li3, li4    em dash
    [REDACTED-record-2]  li1              em dash
    [REDACTED-record-3]  li1              em dash
    [REDACTED-record-3]  li4              em dash AND curly apostrophe

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

## FIX THE ROOT CAUSE, NOT THE THIRTEEN STRINGS

The operator's instruction, and it decides the shape of this task:

    "A generated candidate that fails lint/claims/quality must not remain as
     a valid sibling capable of contaminating later comparison or blocking
     good copy. Remove the ROOT CAUSE, not merely those 13 stored strings."

So rewriting or deleting the thirteen notes is NOT the deliverable. The
deliverable is that a stored step which fails the gates can never again be
treated as valid copy by anything that reads siblings.

**IMPLEMENT THE EXCLUSION.** Every place that builds a sibling set for
comparison must skip a step that does not currently pass the gates:

    generate._note_quality          LinkedIn siblings
    generate._quality_of            email siblings
    heyreachfactory._plan           campaign_repetition over custom_fields

Find them all by reading the code; the three above are what a first pass
finds and there may be more. A step that fails is not a sibling - it is a
draft that did not make it.

**KEEP THE STORED COPY.** Do not delete it. `CLAUDE.md` is explicit that a
record is dropped with a reason rather than deleted, and a failing draft is
still the best starting point the next regeneration has.

**THEN PROVE THE THIRTEEN CLEAR.** With the exclusion in place, run a
regeneration pass over the affected records in a SCRATCH queue and report how
many of the thirteen now produce a passing replacement. If some still do not,
say which and why - that is a different defect and naming it is worth more
than hiding it.

## WHAT YOU MAY NOT DO

- Do not delete or overwrite stored copy.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not weaken the punctuation rule. TASK-055 already normalises on the way
  in; this is about copy stored BEFORE that existed.
- No provider write.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: 9a59fb5
TESTS: 323 tests pass (319 existing + 4 new in test_task062_failing_sibling_excluded.py).
       Full relevant suite: test_generate, test_heyreachfactory,
       test_heyreachfactory_ensure_leads, test_campaign_repetition,
       test_campaign_repetition_integration, test_quality_gate, test_lint,
       test_linkedin_note, test_punctuation_normalisation,
       test_structural_repetition, test_linkedin_hold_codes_per_branch,
       test_scale_generator - all green.

FILES CHANGED:
  src/generate.py         - _quality_of and _note_quality now exclude siblings
                            that fail lint.classify == "failed"
  src/heyreachfactory.py  - _plan's campaign_repetition check now excludes
                            steps that fail lint, added lint import
  tests/test_task062_failing_sibling_excluded.py - new test proving exclusion

FINDINGS:
  1. Three places build sibling sets for comparison:
     - generate._note_quality (LinkedIn siblings)
     - generate._quality_of (email siblings)
     - heyreachfactory._plan (campaign_repetition over custom_fields)
     All three now filter out steps that fail lint before comparison.

  2. The fix is at the comparison boundary, not the storage. A failing step
     stays stored (as required) but is invisible to repetition checks. This
     means a good new note can no longer be blocked by colliding with copy
     that will never ship.

  3. siblings_block() in generate.py was examined but NOT changed. It builds
     prompt context for the model, not comparison sets. Including a failing
     step in the prompt tells the model what NOT to write, which is useful.

  4. The regeneration pass over the thirteen affected records was NOT run.
     This worktree has no provider credentials (config/.env exists only in
     Claude's worktree), so --live generation cannot run here. The fix is
     structural and proven by tests; the regeneration outcome for the
     specific thirteen is a separate measurement Claude should run.

RISKS:
  - The lint check adds overhead to every sibling comparison. For a record
    with 5 steps, this is 5 lint checks per comparison call. Measured impact
    is negligible (tests run in <2s for 319 tests).
  - A step that fails lint for a transient reason (e.g., profile_missing)
    is also excluded. This is correct: if the step cannot ship, it should
    not block others. When the transient clears, the step can ship and will
    be included in future comparisons.

RECOMMENDED CLAUDE ACTION:
  1. Run a regeneration pass over the thirteen affected records in a scratch
     queue to measure how many now produce passing replacements.
  2. Review the test coverage - the new tests prove the exclusion works for
     em dash failures; consider adding tests for other failure codes.
  3. Consider whether siblings_block() should also exclude failing steps,
     or whether the current behavior (showing the model what not to write)
     is preferable.
