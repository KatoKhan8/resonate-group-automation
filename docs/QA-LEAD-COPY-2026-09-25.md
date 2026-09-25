# QA Lead Copy Check — 2026-09-25

**TASK-295.** Per-lead copy quality check for the QA suite (Lane F).

**Status:** IMPLEMENTED. 26 tests green. Check script, tests, and registry
entry committed on `qwen-worker-4-r9-task295` @ `7ddbbe63`.

---

## What it checks

For every rendered lead in `work/stage/s7-copy.jsonl`:

| Rule | What it catches |
|------|----------------|
| `subject_present` | Empty subject line (ISSUE-025: 76 blank emails) |
| `body_present` | Empty body on any step |
| `not_literal_none` | The string "None" as copy |
| `no_unrendered_placeholder` | Surviving `{VAR}`, `{{VAR}}`, `[[VAR]]` |
| `no_dash` | Typographic dashes (em, en, non-breaking) |
| `no_banned_phrase` | Banned phrases and buzzwords |
| `length_in_band` | Body outside 40–180 words |
| `first_name_present_and_capitalised` | Missing or lowercase greeting name |
| `subject_matches_the_step` | Threaded step with different subject |
| `first_line_unique_in_batch` | Two leads with identical opening line |
| `persona_and_angle_consistent` | Persona/angle mismatch across channels |

## THE REAL MAPPING — measured, not remembered

The step key is NOT the variable number. Read from the client config:

    em1   position 1   body_1   subject_1   thread_reply: false
    em2   position 2   body_2   subject_1   thread_reply: true
    em4   position 3   body_4   subject_1   thread_reply: true
    em5   position 4   body_5   subject_1   thread_reply: true

Three facts:

1. **The step key is not the variable number.** em4 is at POSITION 3 and
   reads `body_4` in the s7 output (keyed by step name, not position).
2. **There is no SUBJECT_2.** All four steps carry `{SUBJECT_1}`. The
   `thread_reply_pattern` is `[false, true, true, true]`: step 1 opens the
   thread, steps 2–4 reply into it.
3. **A threaded step still carries a subject.** `bisonfactory._sequence_steps`
   puts `email_subject` on every step. The flag is the mechanism, not subject
   omission.

The check reads this mapping FROM THE CONFIG at run time and prints it in
the result document. Nothing is hardcoded.

## How it works

```
py -3 scripts/qa/check_lead_copy.py \
    --phase pre_push \
    --batch batch-2-2026-09-25 \
    --workspaces <path to work/ copy> \
    --client productive
```

The check:

1. Loads the client config and determines the step list and thread_reply
   pattern from `email_sequence.thread_reply_pattern` (or the cadence
   library default), trimmed to the campaign's own step count.
2. Reads `work/stage/s7-copy.jsonl` from the workspaces copy.
3. For each rendered row, applies the 11 rules.
4. Produces the QA contract result document (JSON).

Exit codes: 0 = PASS, 1 = FAIL, 2 = UNCONFIRMED/VACUOUS, 3 = ERROR.

## What is NOT in this check

- **Pack-fact traceability.** That is `copylint.check_batch`, which runs
  inside `bisonfactory._refuse_copylint`. This check complements it.
- **Provider readback.** That is TASK-298 (post-push).
- **Campaign-level checks.** Those are TASK-296 (EmailBison) and TASK-297
  (HeyReach).
- **Per-lead state eligibility.** That is TASK-293.
- **Per-lead research pack.** That is TASK-294.

## Disagreements between the config and committed docs

Two committed documents say em4 opens a NEW thread with `SUBJECT_2`:

- `PRODUCTION-HANDOFF-2026-09-24-LATE.md` §2
- Lane E's TASK-283

The config says otherwise:

- `config/clients/productive.yaml` lines 590–626: `thread_reply_pattern:
  [false, true, true, true]`
- Lane B's commit `1abe88ca`: *"the fourth entry is four, not five, and em4
  cannot open a second thread"*

**The config wins.** The handoff was wrong.

## Files

    scripts/qa/__init__.py                  registry entry
    scripts/qa/check_lead_copy.py           the check
    tests/test_the_step_key_is_not_the_variable_number.py   21 tests
    tests/test_a_threaded_step_still_carries_a_subject.py   5 tests

## Test names (new, 26 total)

    StepToVariableMapping.test_four_step_mapping_em4_is_position_3
    StepToVariableMapping.test_three_step_mapping_has_three_entries
    StepToVariableMapping.test_five_step_mapping
    StepToVariableMapping.test_thread_reply_pattern_from_config
    StepToVariableMapping.test_no_hardcoded_subject_2
    StepToVariableMapping.test_pattern_trimmed_to_campaign_length
    BisonfactorySequenceStepsAgrees.test_four_step_sequence_has_four_entries
    BisonfactorySequenceStepsAgrees.test_threaded_step_still_carries_subject
    CheckAgainstRenderedRows.test_clean_batch_passes
    CheckAgainstRenderedRows.test_empty_body_fires_body_present
    CheckAgainstRenderedRows.test_empty_subject_fires_subject_present
    CheckAgainstRenderedRows.test_literal_none_fires_not_literal_none
    CheckAgainstRenderedRows.test_unrendered_placeholder_fires
    CheckAgainstRenderedRows.test_dash_fires
    CheckAgainstRenderedRows.test_banned_phrase_fires
    CheckAgainstRenderedRows.test_lowercase_first_name_fires
    CheckAgainstRenderedRows.test_duplicate_first_line_fires
    CheckAgainstRenderedRows.test_vacuous_when_no_rendered_rows
    CheckAgainstRenderedRows.test_empty_vs_none_vs_unrendered_are_separate_counts
    CheckAgainstRenderedRows.test_arithmetic_closes
    CheckAgainstRenderedRows.test_rule_sentences_rendered_from_run_parameters
    ThreadedStepCarriesSubject.test_four_step_every_step_carries_subject
    ThreadedStepCarriesSubject.test_three_step_every_step_carries_subject
    ThreadedStepCarriesSubject.test_threaded_steps_are_flagged
    QACheckDoesNotExcuseEmptySubjectOnThreadedStep.test_empty_subject_fires_subject_present
    QACheckDoesNotExcuseEmptySubjectOnThreadedStep.test_nonempty_subject_passes_subject_rule

## Suite baseline vs HEAD~1

    new (26):     all test names listed above
    gone (0):     no existing tests removed
    common:       all pre-existing tests unchanged
