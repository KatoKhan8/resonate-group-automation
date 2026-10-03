# LANE B — the LinkedIn character contract is one measured authority

Branch `task-981-li-char-contract`, off master `2bf7b8a5`.
Worktree `.../scratchpad/wt-lic` — the path contains none of the nine
substrings that would exempt every file from `test_invariants`' send guard.

No full suite was run. No provider call, no Slack post, no production `work/`
write, no model spend. `git push` not attempted.

---

## 1. The contract, as implemented

Declared in **`src/skills/linkedin_writing.py`**, mirroring
`skills.cold_email_writing.WORD_CONTRACT` in shape and in how it is wired.

```python
LINKEDIN_CHAR_CONTRACT = {
    "li1":  (UNKNOWN, UNKNOWN, 300),
    "li2":  (100, 125, 299),
    "li3+": (100, 173, 299),
}
LI1_MEASURED_CEILING = 179
```

| role | floor | target | ceiling |
|---|---|---|---|
| li1 connection note | UNKNOWN | UNKNOWN | 300 hard (LinkedIn's), 179 measured, recorded not enforced |
| li2 first message | 100 | 125 | 299 |
| li3+ every follow-up | 100 | 173 | 299 |

Helpers, all rendered from the mapping and never from a retyped number:
`contract_role` (li3/li4/li5/li9 to `li3+`), `char_bounds`, `char_target`,
`strictest_message_bounds`, `bound_phrase`, `chars_rule`.

`LI1_MEASURED_CEILING = 179` is deliberately OUTSIDE the mapping: it rests on
one campaign, so it is a number the writer is told and the gate does not
refuse on. The gate's only hard cap on a note stays LinkedIn's own 300.

## 2. How UNKNOWN is represented

A singleton sentinel `linkedin_writing.UNKNOWN`, instance of a private
`_Unknown` class, re-exported as `lint.LINKEDIN_UNKNOWN`. It is NOT `None`,
NOT `0`, NOT "no limit". It actively refuses to become a number:

- `__bool__` raises `TypeError` — `if floor:` cannot silently mean either
  "there is a floor" or "there is not".
- `__int__` / `__index__` raise `TypeError`.
- it defines no ordering, so `len(text) < UNKNOWN` raises rather than
  evaluating to something.
- `repr` is `"UNKNOWN"`, and `bound_phrase` renders it as the word, so no
  prompt, explanation or report can print a number that was never measured.

The only legal test is `is UNKNOWN`, and that is what the gate does. The
branch is live, not dead: `TestOneAuthority.test_giving_li1_a_floor_starts_refusing_short_notes`
gives li1 a floor at runtime and the gate starts refusing, with no other line
changing.

## 3. Every reader, rewired

Grepped for `NOTE_MIN_CHARS`, `MESSAGE_MIN_CHARS`, `MESSAGE_MAX_CHARS` and
`NOTE_MAX_CHARS` across the repo. All of them:

| file | what it was | what it is |
|---|---|---|
| `src/lint.py:775-778` | the four flat constants | three DELETED; `NOTE_MAX_CHARS` now `= LINKEDIN_CHAR_CONTRACT["li1"][2]` |
| `src/lint.py` (module head) | — | `LINKEDIN_CHAR_CONTRACT` alias beside `STEP_WORD_CONTRACT`, plus `LINKEDIN_UNKNOWN` and `NOTE_MEASURED_CEILING` |
| `src/lint.py` `EXPLAIN` | "the note is too long", "too short to say anything", and NO entry at all for the two message codes | all four interpolated from the contract; the two message codes added, naming the band and both targets |
| `src/lint.py` `check_linkedin` | `len > NOTE_MAX / < NOTE_MIN`, `len > MESSAGE_MAX / < MESSAGE_MIN` | resolves the contract row, skips a bound that `is UNKNOWN`; now takes `step_key` |
| `src/lint.py` `check_step` | dropped `step_key` on the LinkedIn branch | threads it through |
| `src/copystages.py:583` | "each under 280 characters" | li1 under 280 under a 300 cap; EVERY MESSAGE AFTER IT 100 TO 299 CHARACTERS, aiming 125 / 173 |
| `src/copystages.py:622-635` | "`NOTE_MAX_CHARS` (300) and `MESSAGE_MAX_CHARS` (1900)" | the contract as a three-row table plus where each number came from; the `requires` mismatch paragraph is kept, it is still true |
| `src/copystages.py:654` | li5 "STILL AT LEAST 60 CHARACTERS ... `NOTE_MIN_CHARS` (40)" | "STILL AT LEAST 100 CHARACTERS, and aim for 173" |
| `src/cadencelibrary.py:191` | `NOTE_MAX_CHARS` comment | same, plus "the note has no floor" and the 179 measured ceiling |
| `src/cadencelibrary.py:255` + rung 5 brief | "78 characters against a `MESSAGE_MIN_CHARS` of 60 ... clears the gate with room to spare", brief says "One line is the right length" | the claim is withdrawn as measured-false and the BRIEF ITSELF is changed to "AT LEAST 100 CHARACTERS, aiming for about 173" — a prompt that asks for copy the gate refuses is the defect this repo keeps paying for |
| `scripts/task176_linkedin_canary_payload.py:42-45,106-114,513` | four retyped constants under "(from src/lint.py)" | imports the contract; the report line renders `chars_rule()` |
| `scripts/task179_approval_analysis.py:112-121` | four bare literals 300/40/1900/60 under "mirror the lint checks" | reads the contract |
| `tools/mutation_audit.py:386-390` | mutated the literal `"NOTE_MAX_CHARS = 300"` in `src/lint.py` | that string no longer exists — the entry now mutates the contract, and TWO MORE mutations are added (drop the li2 floor, invent a li1 floor) |
| `tools/mutation_audit.py:382-383` | `return check_linkedin(rec, key, step)` | updated for the new signature, or it would have become a silent no-op |
| `src/generate_campaign.py:130` | `lint.NOTE_MAX_CHARS` in the token budget | unchanged, still works, now reads the contract transitively |

No module anywhere assigns one of the three deleted names. Asserted, not
claimed: `TestOneAuthority.test_no_module_anywhere_declares_one_of_them_again`
walks `src/`, `scripts/`, `tools/` and `tests/` and parses each file with
`ast`, so prose naming the refuted constants (which is how the refutation
stays readable) is allowed and an assignment is not. It has a POSITIVE
CONTROL that plants a real `MESSAGE_MIN_CHARS = 60` in a `.py` under the
scanned tree, requires the scan to find it, deletes it, and requires the scan
to come back clean — because a search that can never fire is green for the
wrong reason, and that has happened in this repository before.

## 4. Tests

New: `tests/test_the_linkedin_char_contract_is_measured.py`, 46 tests.
Rewritten: `tests/test_linkedin_lint.py` (+5), `tests/test_a_linkedin_message_is_not_a_connection_request.py` (+1).
Fixture premise repaired: `tests/test_set_regeneration.py`.

ON THIS BRANCH: 46/46, 24/24, 14/14 — OK.

ON A CLEAN `2bf7b8a5` WORKTREE with these same three files copied in:
`FAILED (failures=12, errors=26)` on the new module and
`FAILED (failures=6, errors=2)` on the two rewritten ones.

The twelve that FAIL on master do so with a verdict mismatch, each for the
intended reason:

| test | master says |
|---|---|
| `test_the_19_character_note_the_corpus_measured_best_is_clean` | `['note_too_short']` |
| `test_no_note_however_short_is_refused_for_length` | `['note_too_short']` at 1, 5, 19, 39 |
| `test_a_99_character_message_is_refused_under_the_measured_floor` | `[]` |
| `test_the_floor_binds_on_every_follow_up_key_too` | `[]` at li3/li4/li5 |
| `test_a_300_character_message_is_refused_over_the_measured_ceiling` | `[]` |
| `test_a_message_whose_step_key_is_unknown_gets_the_strictest_bounds` | `[]` |
| `test_the_door_every_step_goes_through_threads_the_key` | `[]` |
| `test_the_three_refuted_constants_are_gone_from_lint` | `NOTE_MIN_CHARS` still exists |
| `test_no_module_anywhere_declares_one_of_them_again` | 6 assignments found |
| `test_the_positive_control_for_that_scan` | the real constants are still there |
| `test_the_writer_prompt_carries_the_contract_as_a_table` | `'li3+'` not in `WRITER_SYSTEM` |
| `test_the_note_explanation_names_the_cap_and_the_measured_ceiling` | "the note is too long for a connection request" |

plus, in the two rewritten files: the 19-character note, the two-word note,
the 99-character message, the 300-character message, the 301-character
message's code, and `lint.MESSAGE_MAX_CHARS` still being 1900.

The 26 that ERROR on master error because the contract does not exist there.
They are feature tests and carry no weight on their own — the twelve above
are the discriminators.

CONTROLS — pass identically before and after. Deliberately labelled, so a
blanket "stop enforcing length" change could not be credited to this suite:

- `test_CONTROL_a_301_character_note_is_still_refused`
- `test_CONTROL_a_300_character_note_is_still_allowed`
- `test_CONTROL_a_1901_character_message_is_still_refused`
- `test_CONTROL_every_linkedin_step_in_the_demo_lints_clean` — measured, 18
  steps, 129 to 176 characters, clean under both the old constants and the
  contract
- `test_a_100_character_message_is_in_band`, `test_a_299_character_message_is_in_band`,
  `test_a_too_long_message_is_not_also_reported_as_too_short`,
  `test_an_empty_note_is_still_missing_rather_than_short`

MUTATION PROBE. The four mutation-audit entries that touch this change were
applied, run, restored and re-run, with `__pycache__` wiped on both sides and
the restore VERIFIED BY EFFECT, never by the file looking right:

```
li1 ceiling 300 -> 3000                       mutated: FAILED (failures=3)   restored: OK
li2 floor 100 -> 1                            mutated: FAILED (failures=2)   restored: OK
li1 floor UNKNOWN -> 40                       mutated: FAILED (failures=2)   restored: OK
check_step stops routing to the LinkedIn door mutated: FAILED (failures=1)   restored: OK
```

Separately, every one of the 551 mutation-audit entries was checked to still
match its target exactly once. Four are no-ops; all four are pre-existing on
master (`generate`, `notify`, `events`, `assignment`). This branch adds none.

## 5. Modules run, with results

Individual modules only — no `scripts/run_suite.py`, no `tests.offline`, no
discovery. `(= master)` means the identical failure reproduces on a clean
`2bf7b8a5` worktree and is not this change's.

| module | result |
|---|---|
| test_lint | OK (43) |
| test_linkedin_lint | OK (24) |
| test_a_linkedin_message_is_not_a_connection_request | OK (14) |
| test_the_linkedin_char_contract_is_measured | OK (46) |
| test_linkedinstate_redteam | OK (25) |
| test_a_linkedin_note_is_claim_checked_too | OK (7) |
| test_linkedin_hold_codes_per_branch | OK (23) |
| test_the_angle_guard_holds_on_linkedin | OK (5) |
| test_a_linkedin_approval_certifies_the_words_that_ship | OK (7) |
| test_word_contract_enforced | OK (53) |
| test_the_keyless_doors_get_the_contract | OK (15) |
| test_task913_writer_contract_five_plus_five | OK (40) |
| test_ladder_propagation | OK (25) |
| test_the_writer_is_told_how_long_its_answer_may_be | OK (38) |
| test_the_entrypoint_actually_loads_its_skills | OK (6) |
| test_a_skill_is_loaded_by_the_stage_that_uses_it | OK (6) |
| test_the_model_is_told_what_we_sell | OK (15) |
| test_copylint | OK (45) |
| test_cadence | OK (38) |
| test_eight_step_cadence | OK (25) |
| test_the_linkedin_graph_follows_the_canonical_days | OK (9) |
| test_heyreachfactory | OK (39) |
| test_failure_injection | OK (35) |
| test_a_note_that_fits_as_a_template_and_not_rendered | OK (11) |
| test_a_campaign_is_provably_linkedin_only | OK (24) |
| test_simulator | OK (45) |
| test_task565_incident_regression_fixtures | OK (30) |
| test_approve | OK (43) |
| test_the_copy_lint_refuses_the_real_send_path | OK (10) |
| test_demo_outreach | OK (87) |
| test_import_hardening | OK (47) |
| test_quality_gate | OK (39) |
| test_structural_repetition | OK (28) |
| test_no_branch_repeats_a_message | OK (6) |
| test_the_linkedin_lane_could_collide | OK (23) |
| test_campaign_qa | OK (27) |
| test_render | OK (22) |
| test_push | OK (37) |
| test_preview | OK (37) |
| test_a_dry_run_runs_the_sequence_gate | OK (8) |
| test_the_sequence_gate_catches_what_copylint_cannot | OK (19) |
| test_set_regeneration | 1 failure, `test_generate_record_replaces_colliding_set` (= master) |
| test_invariants | 3 failures (= master) |
| test_threaded_sequence | 3 failures (= master) |
| test_linkedin_note | 1 failure, em-dash normaliser (= master) |
| test_task910_writer_contract | 2 failures, em-dash normaliser (= master) |
| test_ladder_impact | 3 failures, li6 retirement (= master) |
| test_the_linkedin_lane_is_not_gated_on_email | 1 failure (= master) |
| test_variantgen | 1 failure, li6 retirement (= master) |
| test_an_approval_certifies_the_words_that_ship | 1 failure (= master) |
| test_generate | not run — refuses without a configured model (environment) |

No module regressed.

## 6. One behavioural change worth stating plainly

`test_set_regeneration.test_failed_regeneration_preserves_originals` fed the
regenerator `{"note": "no"}` twenty times and relied on `NOTE_MIN_CHARS` to
refuse it. Under the contract a two-character note is clean, so the test
stopped exercising the rollback path at all — it went green for the wrong
reason, not red. The fixture now fails on a banned phrase instead; an
over-length note is caught one layer earlier, by the schema, which raises
rather than returning. This is the one place where the ruling silently
disarmed an existing test, and it is named here because the next such fixture
will not announce itself either.

## 7. Left undone

1. THE `requires` MISMATCH IS UNTOUCHED AND IS STILL A LIVE DEFECT. The
   campaign writer's output carries no `requires`, so a step it emits is
   linted as a connection request — which now means NO FLOOR and a 300
   ceiling where the cadence intends 100-299. It was already wrong before
   (1900 vs 300); it is still wrong, in a different direction. Out of scope
   for this ruling, and the paragraph describing it is kept in
   `copystages.WRITER_SYSTEM`.
2. THE 280 CONVENTION IS LEFT ALONE. "connect is under 280 characters"
   appears in `copyprompts`, `copystages`, both writing skills and a QA
   script. 280 is the merge-field margin under the 300 cap, not one of the
   three refuted numbers, and consolidating it is a separate task.
3. li2's 100 FLOOR IS CARRIED, NOT MEASURED. Section 14.4.2: li2 under 100
   characters is n = 128 and the corpus never did it. The floor comes from
   li3+, where it is measured. That carry is in the docstring; it is an
   assumption and is labelled as one.
4. A PER-STEP FOLLOW-UP CONTRACT STAYS UNKNOWN. Section 14.4.5: step 2 alone
   shows the longer band winning. li3+ is pooled on purpose.
5. NO SECOND-BRAIN OR DOCS FILE WAS WRITTEN. The measurements live on
   `task-981-li-contract` section 14; this branch cites them and adds no
   fourth artefact of the same numbers.
6. THE SUITE WAS NOT RUN END TO END, by instruction. Forty-nine modules were,
   individually, and are tabulated above.
