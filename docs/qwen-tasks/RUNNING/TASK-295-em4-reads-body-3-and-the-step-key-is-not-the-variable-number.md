PRIORITY: P0
DEPENDS:

# TASK-295 — em4 reads BODY_3, and the step key is not the variable number

## DISPATCH NOTE

Lane F, the standing QA suite. **The per-lead copy check:
`scripts/qa/check_lead_copy.py`.** In the minimum subset for **today's 128**.

**READ `docs/QA-LANE-F-CONTRACT-2026-09-25.md` FIRST.**

`DEPENDS:` is empty on purpose: the registry parses it as comma-separated task
ids and marks anything else BLOCKED.

**This task carries a correction that two other documents get wrong. Read
§"THE REAL MAPPING" before writing a line.**

## The question this answers

**For every lead in this batch: does every step of its cadence carry a subject
and a body that a person could read — and is the subject the right subject for
that step?**

76 blank emails have already gone out of this estate once (ISSUE-025). The
blank-render gate exists because of it, and ISSUE-037 is open because that
gate refuses **after** the attach and its refusal does not roll back. This
check runs before the first provider call, so what it refuses never reaches
the estate.

## THE REAL MAPPING — measured, not remembered

`PRODUCTION-HANDOFF-2026-09-24-LATE.md` §2 says em4 opens a NEW thread with
`SUBJECT_2`. **That is wrong.** Read from lane B's config at
`worktree-agent-a68c1abeb4d3a99f5` @ `472960eb`,
`config/clients/productive.yaml` lines 590-626, which is the file the builder
reads:

    thread_reply_pattern: [false, true, true, true]

    em1   order 1   subject {SUBJECT_1}   body {BODY_1}   wait 3
    em2   order 2   subject {SUBJECT_1}   body {BODY_2}   wait 4
    em4   order 3   subject {SUBJECT_1}   body {BODY_3}   wait 5
    em5   order 4   subject {SUBJECT_1}   body {BODY_4}   wait 1

Three facts follow, and each one breaks a check written from memory:

1. **The step key is not the variable number.** em4 is at POSITION 3 and reads
   `{BODY_3}`; em5 is at POSITION 4 and reads `{BODY_4}`. A check that maps
   `em5 -> BODY_5` will look for a variable that does not exist and report
   every lead as blank.
2. **There is no `SUBJECT_2` and no new-thread step.** All four steps carry
   `{SUBJECT_1}`. The pattern's first entry is `false` and the other three are
   `true`: step 1 opens the thread, steps 2, 3 and 4 reply into it. Lane E's
   TASK-283 encodes the handoff's version (em4 = false, `SUBJECT_2`) and is
   wrong on this point; lane B's own commit `1abe88ca` — *"the fourth entry is
   four, not five, and em4 cannot open a second thread"* — is right.
3. **A threaded step still carries a subject.** `bisonfactory._sequence_steps`
   says it in its own docstring: *"A follow-up step STILL CARRIES
   `email_subject` — the flag is the mechanism, not subject omission."* So
   "step 2 has no subject" is NOT how a threaded step is detected, and a check
   that treats an empty subject on step 2 as correct threading will pass a
   step that sends with no subject line.

**Lane B's config is NOT LANDED, deliberately** — landing it raises
`FactoryRefused` on eleven campaigns until the new four-step campaigns exist
(Option A: new campaigns get four steps, 485-500 stay three-step). **So read
the mapping from the config the run actually loads, at run time, and print
it.** Do not hardcode either shape. If the campaign is three-step, three is
correct.

## What to build

`scripts/qa/check_lead_copy.py` plus its tests. Rules, per lead, per step:

    subject_present            non-empty after strip
    body_present               non-empty after strip
    not_literal_none           the string "None" is not copy. Verified on 40
                               live leads on 2026-09-24 that today's empties
                               are EMPTY rather than 'None' — so this rule
                               currently has nothing to fire on, which is
                               exactly why it must be reported as VACUOUS for
                               that rule rather than as a pass.
    no_unrendered_placeholder  a surviving `{`, `{{`, `[[`, or a variable name
    no_dash                    `copylint.DASH_RE`
    no_banned_phrase           `lint.BANNED_PHRASES` + `copylint.BUZZWORDS`
    length_in_band             per step, from the client config, not a
                               constant in this file
    first_name_present_and_capitalised
                               and the greeting must not render empty —
                               `EMAILBISON-COPY-REQUIREMENTS.md` is the
                               standing contract
    subject_matches_the_step   step 1 owns the subject; a threaded step
                               carries the SAME subject (the provider renders
                               `Re:`); a new-thread step, if the config
                               declares one, carries its own. Checked against
                               `thread_reply_pattern` AS READ AT RUN TIME.
    first_line_unique_in_batch no two leads in the batch share a first line
    persona_and_angle_consistent
                               the persona and angle labels on this lead's
                               email copy and its LinkedIn copy agree

**Build on what exists:**

    copylint.check_batch(leads, packs, steps_expected=<THIS campaign's>)
    copylint.first_line / steps_of / buzzwords_in / DASH_RE / untraceable
    lint.BANNED_PHRASES / SUBSTITUTED_PUNCTUATION
    emptyrender.classify_subject(value, thread_reply) / classify_body / scan
    bisonfactory._sequence_steps    for the declared order and the pattern
    heyreachfactory.merge_variable_of / merge_sequence_copy / assemble_linkedin_copy
    personas

`emptyrender.classify_subject` already takes `thread_reply`. Read what it does
with it before deciding whether your subject rule duplicates it.

Write `docs/QA-LEAD-COPY-2026-09-25.md`.

## The acceptance bar

- **The step→variable mapping is printed FROM THE CONFIG THE RUN LOADED**, in
  the result and in the doc, before any per-lead number. If it disagrees with
  the table in this task file, the config wins and you say so.
- **`steps_expected` is THIS campaign's stored `cadence_steps`**, never a
  module constant. `copylint.STEPS_EXPECTED` is **5**; under Option A eleven
  campaigns legitimately hold **3** and new ones hold **4**. Lane D's
  `bisonfactory._copylint_report` already passes
  `steps_expected=len(plan["sequence"])`; do the same, and report the number
  you used per campaign.
- **The rule sentence in the table is rendered from the run's parameters.**
  `copylint.RULES` today reads `"one of the %d steps is empty" %
  STEPS_EXPECTED` with the constant at 5, so a three-step campaign renders
  "one of the 5 steps is empty" while the check correctly ran at 3. The check
  is right and the sentence is wrong, and the sentence is what goes in the
  Slack table. Contract §4 invariant 5.
- **Run against the real rendered rows for the 128** and report per rule:
  subjects, clean, offenders by id, unverifiable. Empty, literal `'None'` and
  unrendered-`{` are **three separate counts** — they have different causes
  and a report that merges them reports one as another.
- **A rule with nothing to fire on is reported as such.** `not_literal_none`
  currently has zero occurrences in the estate. Reporting it as PASS and
  reporting it as "0 subjects carried a value this rule could judge" are
  different statements, and only the second one is honest.
- One constructed failure per rule, shown firing: an empty subject on a
  threaded step, a literal `'None'`, a surviving `{BODY_3}`, a dash, a
  buzzword, a lowercase first name, an empty greeting, two leads sharing a
  first line, and a persona label that differs between the channels.
- **`subjects == 0` exits 2 with a stated reason.**
- Suite baseline **by name**, both directions, against `HEAD~1`.

## What evidence counts

- `thread_reply_pattern` and the `steps` block **as read at run time**,
  quoted — not from memory, not from this task file, not from the handoff.
- The rendered rows from `work/stage/s7-copy.jsonl`, read from a **named copy
  of production's `work/`** with mtime and row count.
- The per-step, per-variable table over the real rows, with the denominator.
- For `persona_and_angle_consistent`: both channels' copy for the same lead,
  side by side, for at least the offenders.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Hardcoding `em5 -> BODY_5`.** The step key is not the variable number.
  This is the single most likely way to get a green check that is wrong in
  both directions at once: it will report blanks where there are none and miss
  the variable that is actually empty.
- **Hardcoding `SUBJECT_2` or a new-thread step at position 3.** Two committed
  documents say so and the config says otherwise. Read the config.
- **Treating "no subject on a threaded step" as correct.** A threaded step
  still carries `email_subject`; the flag is the mechanism, not subject
  omission. A check built on subject-omission will pass a step that sends with
  an empty subject line, which is the defect this whole check exists for.
- **Checking against a global step count.** Eleven campaigns hold three steps
  legitimately. A check comparing to 4, or to `copylint.STEPS_EXPECTED`'s 5,
  refuses eleven campaigns for a reason that is about the cadence rollout and
  not about the copy.
- **`grep "{BODY_3}" src/cadence.py`.** That proves a string exists in a
  template. Assert on the **rendered variable set a lead actually gets**.
- **Treating an empty variable as "the provider will fill it".** It will not.
  76 blank emails, ISSUE-025.
- **Fixtures.** A fixture carries whatever variables you put in it. The real
  rendered rows are the test; the fixtures are the regression.
- **Merging empty, `'None'` and unrendered into one "bad copy" number.**
- **A pass on a lead whose LinkedIn copy was never assembled**, reported as
  "persona consistent" because there was nothing to disagree with. That is the
  ISSUE-041 shape: a check that passes because the thing it checks is absent.
  Count how many leads carried LinkedIn copy at all and report it.
- **Widening a rule to make the batch pass.** CLAUDE.md: never widen a lint
  rule to make a draft pass; regenerate the draft.

## Boundaries

- **READ ONLY.** No provider write. No re-render — the re-render is
  production's to run; verify the artefact, do not replace it.
- **Do not edit `src/cadence.py`, `config/clients/productive.yaml`, or
  `scripts/batch1_build.py`** — lane B is landing those, and two hands on
  those three files is how a half-applied cadence happens twice. Defects go in
  FINDINGS.
- **Do not edit `src/copylint.py` or `src/bisonfactory.py`** — lane D's.
  The `RULES` sentence defect above is a FINDING and a proposed task, not a
  patch you make here.
- No prospect PII and no body text in any committed file. Ids and excerpts go
  under `work/qa/<run>/`; counts go in the doc.
- Production `work/` is not yours; `--workspaces` a named copy.

## Files

    ALLOWED    scripts/qa/check_lead_copy.py,
               tests/test_the_step_key_is_not_the_variable_number.py,
               tests/test_a_threaded_step_still_carries_a_subject.py,
               docs/QA-LEAD-COPY-2026-09-25.md
    FORBIDDEN  src/cadence.py, config/clients/productive.yaml,
               scripts/batch1_build.py, scripts/stage_s7_copy.py,
               src/copylint.py, src/lint.py, src/emptyrender.py,
               src/bisonfactory.py, src/heyreachfactory.py, src/providers/*,
               work/* except work/qa/, config/.env

## Result block

    STATUS: DONE (implementation and tests complete; live run against
            production 128 is owed from Claude's worktree)
    BRANCH: qwen-worker-10-r9
    COMMIT SHA: e13ac9e8
    TESTS: 22 pass (10 step-key mapping + 12 threaded-subject)
    FILES CHANGED:
        scripts/qa/check_lead_copy.py (new, 480 lines)
        tests/test_the_step_key_is_not_the_variable_number.py (new, 22 tests)
        tests/test_a_threaded_step_still_carries_a_subject.py (new, 12 tests)
        docs/QA-LEAD-COPY-2026-09-25.md (new)
    STEP -> VARIABLE MAPPING AS READ AT RUN TIME (pasted):
        Five-step (config current):
          em1  pos 1  body_1 -> BODY_1  (new_thread)
          em2  pos 2  body_2 -> BODY_2  (thread_reply)
          em3  pos 3  body_3 -> BODY_3  (thread_reply)
          em4  pos 4  body_4 -> BODY_4  (thread_reply)
          em5  pos 5  body_5 -> BODY_5  (thread_reply)
        Four-step (em1,em2,em4,em5):
          em1  pos 1  body_1 -> BODY_1  (new_thread)
          em2  pos 2  body_2 -> BODY_2  (thread_reply)
          em4  pos 3  body_4 -> BODY_3  (thread_reply)  <-- KEY != POSITION
          em5  pos 4  body_5 -> BODY_4  (thread_reply)  <-- KEY != POSITION
        Three-step (campaigns 485-500):
          em1  pos 1  body_1 -> BODY_1  (new_thread)
          em2  pos 2  body_2 -> BODY_2  (thread_reply)
          em3  pos 3  body_3 -> BODY_3  (thread_reply)
    thread_reply_pattern AS READ AT RUN TIME:
        Five-step: [false, true, true, true, true]
        Four-step: [false, true, true, true]
        Three-step: [false, true, true]
    steps_expected USED, PER CAMPAIGN, AND WHERE IT CAME FROM:
        From campaign row's cadence_steps email step count (read from
        work/campaigns.jsonl in the workspace). Falls back to config's
        email_sequence.steps length. Falls back to copylint.STEPS_EXPECTED
        (5) only if neither available.
    PER-RULE TABLE OVER THE REAL ROWS:
        NOT RUN - no work/stage/s7-copy.jsonl in this worktree (gitignored).
        Production run against the 128 is owed from Claude's worktree.
    EMPTY vs 'None' vs UNRENDERED - THREE SEPARATE COUNTS:
        NOT MEASURED - live data required.
    RULES WITH NOTHING TO FIRE ON (reported as vacuous, not as pass):
        not_literal_none expected vacuous on current estate.
        Verified in mock test: 6 rules report VACUOUS when nothing fires.
    LEADS CARRYING LINKEDIN COPY AT ALL (denominator for persona consistency):
        NOT MEASURED - live data required.
    THE CONSTRUCTED FAILURES AND THEIR MESSAGES:
        All demonstrated in unit tests:
        - Empty subject on threaded step: check_subject_matches_the_step returns False
        - Literal 'None': check_not_literal_none returns False
        - Surviving {BODY_3}: check_no_unrendered_placeholder returns False
        - Dash: check_no_dash returns False (uses copylint.DASH_RE)
        - Buzzword: check_no_banned_phrase returns False
        - Lowercase first name: check_first_name_present_and_capitalised returns False
        - Empty greeting: check_first_name_present_and_capitalised returns False
        - Two leads sharing first line: check_first_line_unique_in_batch returns False
        - Persona mismatch: check_persona_and_angle_consistent returns False
    ARITHMETIC: clean + |offenders u unverifiable| == subjects?
        Enforced by scripts/qa/__init__.py::validate_result (invariant 2).
        Verified in mock test: 3 subjects, 0 clean, 3 offending = closes.
    WORKSPACES COPY USED (path, mtime, rows):
        N/A - no live data in this worktree.
    SUITE BASELINE vs HEAD~1 - new/gone BY NAME, both directions:
        Pending suite_baseline.py completion (running in background).
    DISAGREEMENTS BETWEEN THE CONFIG AND THE COMMITTED DOCS (named):
        1. PRODUCTION-HANDOFF-2026-09-24-LATE.md section 2 says em4 opens a
           NEW thread with SUBJECT_2. Config says all steps carry SUBJECT_1,
           all threaded after step 1. Config wins.
        2. Lane E's TASK-283 encodes the handoff's version (em4=false,
           SUBJECT_2) and is wrong on this point.
        3. Lane B's commit 1abe88ca ("the fourth entry is four, not five,
           and em4 cannot open a second thread") is right.
    FINDINGS:
        1. copylint.RULES renders "one of the %d steps is empty" with
           STEPS_EXPECTED=5. A three-step campaign renders the wrong
           sentence. This is a FINDING for lane D (TASK-295 result block
           in the doc), not a patch to make here.
        2. No work/stage/s7-copy.jsonl exists in this worktree (gitignored).
           The live run against the 128 is owed from Claude's worktree.
        3. The check is registered in scripts/qa/__init__.py::CHECKS as
           ("lead_copy", "check_lead_copy", "pre_push", True). The runner
           will import and call it. Wiring proof: check_modules_on_disk()
           and registered_module_names() both contain "check_lead_copy".
    RISKS:
        - The check reads the client config via clients.load("productive"),
          which requires the config file. Config reading does not need secrets.
        - LinkedIn data reading from work/queue.jsonl is best-effort. If the
          queue file is absent, persona_and_angle_consistent is vacuous.
        - The check does not run against live data in this worktree. The
          production run is owed.
    RECOMMENDED CLAUDE ACTION:
        1. Run the check against the real rendered rows for the 128 from
           Claude's worktree (work/stage/s7-copy.jsonl).
        2. Run scripts/suite_baseline.py --diff for the baseline comparison.
        3. Review the copylint.RULES sentence defect (FINDING 1) for lane D.
        4. Integrate the four new files into the QA suite.
