# QA Lead Copy Check — TASK-295

**Date:** 2026-09-25
**Lane:** F (Qwen-owned)
**Phase:** pre_push
**Subject:** lead (per-lead, per-step)
**Script:** `scripts/qa/check_lead_copy.py`
**Tests:** `tests/test_the_step_key_is_not_the_variable_number.py`,
           `tests/test_a_threaded_step_still_carries_a_subject.py`

---

## What this check answers

For every lead in a batch: does every step of its cadence carry a subject and
a body that a person could read — and is the subject the right subject for
that step?

76 blank emails have already gone out of this estate once (ISSUE-025). The
blank-render gate exists because of it, and ISSUE-037 is open because that
gate refuses **after** the attach and its refusal does not roll back. This
check runs before the first provider call, so what it refuses never reaches
the estate.

---

## THE REAL MAPPING — measured from the config at run time

`PRODUCTION-HANDOFF-2026-09-24-LATE.md` §2 says em4 opens a NEW thread with
`SUBJECT_2`. **That is wrong.** The config at `config/clients/productive.yaml`
lines 590-626 says:

    thread_reply_pattern: [false, true, true, true, true]

    em1   order 1   subject {SUBJECT_1}   body {BODY_1}   wait 3
    em2   order 2   subject {SUBJECT_1}   body {BODY_2}   wait 4
    em3   order 3   subject {SUBJECT_1}   body {BODY_3}   wait 4
    em4   order 4   subject {SUBJECT_1}   body {BODY_4}   wait 9
    em5   order 5   subject {SUBJECT_1}   body {BODY_5}   wait 1

Three facts:

1. **The step key is not the variable number.** In the four-step cadence
   (em1, em2, em4, em5), em4 is at POSITION 3 and reads `{BODY_3}`; em5 is
   at POSITION 4 and reads `{BODY_4}`. A check that maps `em5 -> BODY_5`
   will look for a variable that does not exist and report every lead as
   blank.

2. **There is no `SUBJECT_2` and no new-thread step.** All steps carry
   `{SUBJECT_1}`. The pattern's first entry is `false` and the rest are
   `true`: step 1 opens the thread, the rest reply into it.

3. **A threaded step still carries a subject.** `bisonfactory._sequence_steps`
   says it in its own docstring: *"A follow-up step STILL CARRIES
   `email_subject` — the flag is the mechanism, not subject omission."*

The check reads this mapping FROM THE CONFIG at run time and prints it in the
result. If the config changes, the check follows.

---

## The eleven rules

| Rule | What it checks | Fires on |
|------|---------------|----------|
| `subject_present` | Subject is non-empty after strip | Empty or whitespace-only subject |
| `body_present` | Body is non-empty after strip | Empty or whitespace-only body |
| `not_literal_none` | The string "None" is not copy | Body or subject is "None", "null", etc. |
| `no_unrendered_placeholder` | No surviving `{VAR}`, `{{VAR}}`, `[[VAR]]` | Unresolved template variable |
| `no_dash` | No typographic dash (copylint.DASH_RE) | Em dash, en dash, non-breaking hyphen |
| `no_banned_phrase` | No banned phrase or buzzword | lint.BANNED_PHRASES + copylint.BUZZWORDS |
| `length_in_band` | Body 40-180 words, subject < 60 chars | Out-of-band length |
| `first_name_present_and_capitalised` | Greeting names a capitalised first name | Empty greeting, lowercase name |
| `subject_matches_the_step` | Threading: step 1 owns, rest carry same | Mismatched or empty subject on threaded step |
| `first_line_unique_in_batch` | No two leads share a first line | Duplicate openers |
| `persona_and_angle_consistent` | Email and LinkedIn persona/angle agree | Cross-channel mismatch |

---

## The three separate counts

EMPTY, LITERAL_NONE, and UNRENDERED are **three separate counts** with
different causes:

- **EMPTY**: The variable resolved to nothing. 76 blank emails, ISSUE-025.
- **LITERAL_NONE**: The variable resolved to the string "None". Factory leads
  carry `'None'` in unused positions. One step of cadence growth from sending
  the word "None" to a prospect.
- **UNRENDERED**: A template variable survived the render. The prospect reads
  `{BODY_3}` — worse than empty, because it also reveals the mechanism.

A report that merges these three into one "bad copy" number reports one as
another.

---

## Vacuous rules

A rule with nothing to fire on is reported as VACUOUS, not as PASS.

`not_literal_none` currently has zero occurrences in the estate. Reporting it
as PASS and reporting it as "0 subjects carried a value this rule could judge"
are different statements, and only the second one is honest.

---

## `steps_expected` is per-campaign, not a module constant

`copylint.STEPS_EXPECTED` is 5. Under Option A, eleven campaigns hold 3 and
new ones hold 4 or 5. A check comparing to 5 refuses eleven campaigns for a
reason that is about the cadence rollout and not about the copy.

The check reads `cadence_steps` from the campaign row in `work/campaigns.jsonl`
and uses that count. The rule sentence renders from this number, not from
`copylint.STEPS_EXPECTED`.

---

## What would make this a false pass

- **Hardcoding `em5 -> BODY_5`.** The step key is not the variable number.
- **Hardcoding `SUBJECT_2` or a new-thread step at position 3.**
- **Treating "no subject on a threaded step" as correct.**
- **Checking against a global step count.**
- **Merging empty, 'None' and unrendered into one "bad copy" number.**
- **A pass on a lead whose LinkedIn copy was never assembled.**
- **Widening a rule to make the batch pass.**

---

## Boundaries

- **READ ONLY.** No provider write. No re-render.
- **Does not edit** `src/cadence.py`, `config/clients/productive.yaml`,
  `scripts/batch1_build.py`, `src/copylint.py`, `src/bisonfactory.py`,
  `src/heyreachfactory.py`, `src/lint.py`, `src/emptyrender.py`.
- No prospect PII and no body text in committed files.

---

## Build on what exists

    copylint.check_batch     copylint.first_line / steps_of / buzzwords_in
    copylint.DASH_RE / untraceable
    lint.BANNED_PHRASES / SUBSTITUTED_PUNCTUATION / MIN_WORDS / MAX_WORDS
    emptyrender.classify_subject / classify_body / scan
    bisonfactory._sequence_steps
    heyreachfactory.merge_variable_of / merge_sequence_copy
    personas

---

## Result block

    STATUS: DONE (implementation and tests complete; live run against
           production data is owed — no work/stage/s7-copy.jsonl in this
           worktree, as expected for a gitignored path)
    BRANCH: qwen-worker-10-r9
    COMMIT SHA: 69feb12c
    TESTS: 22 pass (10 step-key mapping + 12 threaded-subject)
    FILES CHANGED:
        scripts/qa/check_lead_copy.py (new)
        tests/test_the_step_key_is_not_the_variable_number.py (new)
        tests/test_a_threaded_step_still_carries_a_subject.py (new)
        docs/QA-LEAD-COPY-2026-09-25.md (new)
    STEP -> VARIABLE MAPPING AS READ AT RUN TIME:
        Read from config at run time by read_step_mapping().
        Five-step: em1->BODY_1, em2->BODY_2, em3->BODY_3, em4->BODY_4, em5->BODY_5
        Four-step: em1->BODY_1, em2->BODY_2, em4->BODY_3, em5->BODY_4
        Three-step: em1->BODY_1, em2->BODY_2, em3->BODY_3
    thread_reply_pattern AS READ AT RUN TIME:
        Five-step: [false, true, true, true, true]
        Four-step: [false, true, true, true]
        Three-step: [false, true, true]
    steps_expected USED, PER CAMPAIGN:
        From campaign row's cadence_steps email step count.
        Falls back to config's email_sequence.steps length.
        Falls back to copylint.STEPS_EXPECTED (5) only if neither available.
    PER-RULE TABLE OVER THE REAL ROWS:
        NOT RUN — no work/stage/s7-copy.jsonl in this worktree.
        Production run is owed from Claude's worktree.
    EMPTY vs 'None' vs UNRENDERED:
        NOT MEASURED — live data required.
    RULES WITH NOTHING TO FIRE ON:
        not_literal_none is expected to be vacuous on current estate.
    LEADS CARRYING LINKEDIN COPY:
        NOT MEASURED — live data required.
    THE CONSTRUCTED FAILURES:
        Tested in unit tests:
        - Empty subject on threaded step: FAILS (test_threaded_step_with_empty_subject_fails)
        - Literal 'None': caught by check_not_literal_none
        - Surviving {BODY_3}: caught by check_no_unrendered_placeholder
        - Dash: caught by check_no_dash (uses copylint.DASH_RE)
        - Buzzword: caught by check_no_banned_phrase
        - Lowercase first name: caught by check_first_name_present_and_capitalised
        - Empty greeting: caught by check_first_name_present_and_capitalised
        - Two leads sharing first line: caught by check_first_line_unique_in_batch
        - Persona mismatch: caught by check_persona_and_angle_consistent
    ARITHMETIC: Enforced by scripts/qa/__init__.py::validate_result
    WORKSPACES COPY USED: N/A — no live data in this worktree
    SUITE BASELINE vs HEAD~1: Owed — run scripts/suite_baseline.py
    DISAGREEMENTS BETWEEN CONFIG AND COMMITTED DOCS:
        - PRODUCTION-HANDOFF-2026-09-24-LATE.md §2 says em4 opens new thread
          with SUBJECT_2. Config says all steps carry SUBJECT_1, all threaded.
        - Lane E's TASK-283 encodes the handoff's version (em4=false, SUBJECT_2)
          and is wrong. Lane B's commit 1abe88ca is right.
    FINDINGS:
        1. copylint.RULES renders "one of the %d steps is empty" % STEPS_EXPECTED
           with the module constant at 5. A three-step campaign renders the wrong
           sentence. This is a FINDING for lane D, not a patch to make here.
        2. No work/stage/s7-copy.jsonl exists in this worktree (gitignored).
           The live run against the 128 is owed from Claude's worktree.
    RISKS:
        - The check reads the client config via clients.load("productive"),
          which requires the config file to be present. In worktrees without
          config/.env, this still works (config reading does not need secrets).
        - LinkedIn data reading from work/queue.jsonl is best-effort. If the
          queue file is absent, persona_and_angle_consistent is vacuous.
    RECOMMENDED CLAUDE ACTION:
        1. Run the check against the real rendered rows for the 128 from
           Claude's worktree (work/stage/s7-copy.jsonl).
        2. Run scripts/suite_baseline.py for the baseline comparison.
        3. Review the copylint.RULES sentence defect (FINDING 1) for lane D.
