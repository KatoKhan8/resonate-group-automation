# QA Lead Copy Check — 2026-09-25

**TASK-295.** Per-lead copy validation, the check that runs before the first
provider call so what it refuses never reaches the estate.

**Script:** `scripts/qa/check_lead_copy.py`
**Tests:** `tests/test_the_step_key_is_not_the_variable_number.py`,
           `tests/test_a_threaded_step_still_carries_a_subject.py`

---

## 1. THE REAL MAPPING — MEASURED FROM THE CONFIG

The mapping is read from `config/clients/productive.yaml` at run time by
`check_lead_copy.read_step_body_mapping(config)`. It is NOT hardcoded.

### Five-step config (current, from productive.yaml lines 590-660)

```
thread_reply_pattern: [false, true, true, true, true]

em1   position 1   subject {SUBJECT_1}   body {BODY_1}   wait 3
em2   position 2   subject {SUBJECT_1}   body {BODY_2}   wait 4
em3   position 3   subject {SUBJECT_1}   body {BODY_3}   wait 4
em4   position 4   subject {SUBJECT_1}   body {BODY_4}   wait 9
em5   position 5   subject {SUBJECT_1}   body {BODY_5}   wait 1
```

### Four-step config (before 2026-09-25, eleven campaigns still run this)

```
thread_reply_pattern: [false, true, true, true]

em1   position 1   subject {SUBJECT_1}   body {BODY_1}   wait 3
em2   position 2   subject {SUBJECT_1}   body {BODY_2}   wait 4
em4   position 3   subject {SUBJECT_1}   body {BODY_3}   wait 5
em5   position 4   subject {SUBJECT_1}   body {BODY_4}   wait 1
```

### Three-step config (campaigns 485-500, Option A)

```
thread_reply_pattern: [false, true, true]

em1   position 1   subject {SUBJECT_1}   body {BODY_1}
em2   position 2   subject {SUBJECT_1}   body {BODY_2}
em4   position 3   subject {SUBJECT_1}   body {BODY_3}
```

### Three facts that break checks written from memory

1. **The step key is NOT the variable number.** em4 at position 3 reads
   `{BODY_3}`; em5 at position 4 reads `{BODY_4}`. At five steps they
   happen to agree (em5 is position 5, reads `{BODY_5}`). At four steps
   they do not. A check mapping `em5 -> BODY_5` on a four-step config
   looks for a variable that does not exist and reports every lead as blank.

2. **There is no `SUBJECT_2` and no new-thread step after position 1.**
   All steps carry `{SUBJECT_1}`. The pattern's first entry is `false` and
   the rest are `true`: step 1 opens the thread, steps 2+ reply into it.
   Two committed documents say `SUBJECT_2` exists; the config says no.

3. **A threaded step still carries `email_subject`.** The flag is the
   mechanism, not subject omission. `bisonfactory._sequence_steps` states
   this in its own docstring. An empty subject on a threaded step is NOT
   correct threading; it is an email that sends with no subject line.

---

## 2. THE RULES

Each rule is rendered from the run's parameters, not from module constants.
`copylint.RULES` has `"one of the %d steps is empty" % STEPS_EXPECTED` with
`STEPS_EXPECTED = 5`, so a three-step campaign renders "one of the 5 steps
is empty" while the check correctly ran at 3. Our check renders its own
sentences from the actual `steps_expected`.

| Rule | What it checks | Fires on |
|------|---------------|----------|
| `subject_present` | Non-empty subject after strip, per step | Empty or whitespace-only subject |
| `body_present` | Non-empty body after strip, per step | Empty body (no step has a legitimate empty body) |
| `not_literal_none` | The string "None" is not copy | `None`, `null`, `nil`, `undefined` (case-insensitive) |
| `no_unrendered_placeholder` | No surviving template variable | `{BODY_3}`, `{{FIRST_NAME}}`, `[[variable]]` |
| `no_dash` | `copylint.DASH_RE` | Em dash, en dash, spaced hyphen |
| `no_banned_phrase` | `lint.BANNED_PHRASES` + `copylint.BUZZWORDS` | "synergy", "game-changer", etc. |
| `length_in_band` | Body word count in [40, 180] | Too short or too long |
| `first_name_present_and_capitalised` | Greeting name present and capitalised | Missing, placeholder, or lowercase name |
| `subject_matches_the_step` | Subject matches threading pattern | Empty on threaded step, different from opener |
| `first_line_unique_in_batch` | No two leads share a first line | Duplicate opening sentences |
| `persona_and_angle_consistent` | Email and LinkedIn persona/angle agree | Mismatch between channels |

---

## 3. EXIT CODES

    0   PASS       every lead clean
    1   FAIL       at least one lead offends at least one rule
    2   VACUOUS    subjects == 0 (no rendered rows, or all held)
    3   ERROR      the check itself broke

`subjects == 0` exits 2 with a stated reason. A check whose subject set is
empty is never a PASS.

---

## 4. THE RESULT DOCUMENT

```json
{
  "check": "lead_copy",
  "phase": "pre_push",
  "verdict": "FAIL",
  "subjects": 128,
  "clean": 119,
  "refused": true,
  "rules": { ... rendered from this run's parameters ... },
  "counts": { ... per-rule counts ... },
  "offenders": { ... per-rule lead ids ... },
  "unverifiable": { ... },
  "steps_expected": 4,
  "thread_reply_pattern": [false, true, true, true],
  "step_mapping": [
    {"step_key": "em1", "body_variable": "BODY_1"},
    {"step_key": "em2", "body_variable": "BODY_2"},
    {"step_key": "em4", "body_variable": "BODY_3"},
    {"step_key": "em5", "body_variable": "BODY_4"}
  ],
  "empty_vs_none_vs_unrendered": {
    "empty": 3,
    "literal_none": 0,
    "unrendered": 1
  },
  "vacuous_rules": [
    "not_literal_none: zero occurrences in the estate; nothing to fire on"
  ],
  "leads_with_linkedin_copy": 0,
  "leads_with_linkedin_checked": 0
}
```

### The five invariants the runner enforces

1. `offenders` and `unverifiable` hold IDS, never counts.
2. `clean + |union(offenders) ∪ union(unverifiable)| == subjects`.
3. `subjects == 0` is VACUOUS, exit 2, never PASS.
4. Every key in `counts`, `offenders` and `unverifiable` exists in `rules`.
5. `rules` sentences are rendered from THIS RUN's parameters.

---

## 5. EMPTY vs 'None' vs UNRENDERED — THREE SEPARATE COUNTS

These have different causes and a report that merges them reports one as
another:

- **EMPTY** (`body_present` / `subject_present`): the variable resolved to
  nothing. The lead carried no value for that position. Cause: the render
  had nothing to substitute. 76 blank emails (ISSUE-025) were this shape.

- **LITERAL 'None'** (`not_literal_none`): the variable resolved to the
  four-character string `None`. Cause: the factory wrote `str(None)` into a
  variable slot. Currently zero occurrences in the estate (verified
  2026-09-24), which is exactly why this rule is reported as VACUOUS rather
  than as a pass.

- **UNRENDERED** (`no_unrendered_placeholder`): a surviving `{BODY_3}` or
  `{{FIRST_NAME}}` in the rendered output. Cause: the template referenced a
  variable the lead did not supply. A prospect reading `{BODY_3}` is worse
  than one reading nothing, because it also shows how the sausage is made.

---

## 6. VACUOUS RULES

A rule with nothing to fire on is reported as VACUOUS, not as PASS.

- `not_literal_none` currently has zero occurrences. Reporting it as PASS
  and reporting it as "0 subjects carried a value this rule could judge"
  are different statements, and only the second is honest.

- `persona_and_angle_consistent` requires LinkedIn copy to compare against.
  If no leads carry LinkedIn copy, the rule is VACUOUS, not PASS. A check
  that passes because the thing it checks is absent is the ISSUE-041 shape.

---

## 7. CONSTRUCTED FAILURES

One constructed failure per rule, shown firing in the test suite:

| Rule | Constructed failure | Test |
|------|-------------------|------|
| `subject_present` | Empty subject on a threaded step | `ThreadedStepWithoutSubjectFails` |
| `not_literal_none` | Subject = "None" | `check_not_literal_none({"subject": "None", ...})` |
| `no_unrendered_placeholder` | Body contains `{BODY_3}` | `check_no_unrendered_placeholder({"body": "{BODY_3}"})` |
| `no_dash` | Body contains " - " | `check_no_dash("word - word")` |
| `no_banned_phrase` | Body contains "synergy" | `check_no_banned_phrase("great synergy")` |
| `first_name_present_and_capitalised` | Name = "jane" (lowercase) | `check_first_name("jane")` |
| `subject_matches_the_step` | Threaded step with empty subject | `ThreadedStepWithoutSubjectFails` |
| `first_line_unique_in_batch` | Two leads with same first line | `check_first_line_unique` with shared `seen_first_lines` |
| `persona_and_angle_consistent` | Email persona "founder", LinkedIn "finance" | Compared in `run()` |

---

## 8. USAGE

```bash
py -3 scripts/qa/check_lead_copy.py \
    --phase pre_push \
    --workspaces work-copy-2026-09-25T06-00Z \
    --campaign 502 --campaign 503 \
    --json work/qa/2026-09-25T06-00Z/lead_copy.json
```

The `--workspaces` path is a copy of production's `work/` directory. The
check reads `stage/s7-copy.jsonl` from it. No default; a worktree has its
own stale `work/` and most worker worktrees have none at all.

---

## 9. DISAGREEMENTS BETWEEN THE CONFIG AND COMMITTED DOCS

| Document | Says | Config says | Who is right |
|----------|------|-------------|-------------|
| `PRODUCTION-HANDOFF-2026-09-24-LATE.md` §2 | em4 opens NEW thread with `SUBJECT_2` | em4 is thread reply on `SUBJECT_1` | Config (commit `1abe88ca`) |
| Lane E's TASK-283 | em4 = false, `SUBJECT_2` | em4 = true, `SUBJECT_1` | Config |
| `stage_s7_copy.py` comment | "step 2 no subject" | Step 2 carries `{SUBJECT_1}` | Config |

The config is the file the builder reads. Lane B's commit `1abe88ca` —
*"the fourth entry is four, not five, and em4 cannot open a second thread"*
— is right.

---

## 10. BOUNDARIES

- **READ ONLY.** No provider write. No re-render.
- **Does not edit** `src/cadence.py`, `config/clients/productive.yaml`,
  `scripts/batch1_build.py`, `src/copylint.py`, `src/bisonfactory.py`,
  `src/heyreachfactory.py`, or any provider module.
- **No prospect PII** in committed files. Ids and excerpts under `work/qa/`.
- Production `work/` is not this check's; `--workspaces` a named copy.

---

## 11. THE SUITE BASELINE

Run `scripts/suite_baseline.py --diff` against `HEAD~1` to report new and
gone tests by name, both directions. A one-directional diff hides the case
that matters.

New tests in this task:
- `tests/test_the_step_key_is_not_the_variable_number.py` — 14 tests
- `tests/test_a_threaded_step_still_carries_a_subject.py` — 13 tests
