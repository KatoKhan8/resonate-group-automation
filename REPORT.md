# Merging master 2bf7b8a5 into task-copy-exemplars

LANE A, 2026-10-03. Worktree `.../0d28ed9d-.../scratchpad/wt-copy` (the one
already checked out for this branch; its path contains none of the nine
substrings that exempt a file from `test_invariants`' send guard).

No full suite was run. No provider write, no Slack post, no write to production
`work/`. No `git stash`. `__pycache__` was wiped before every measurement.

## The decision this merge rests on

Both sides changed the word contract and both arrived at ONE AUTHORITY. They
disagree about WHERE it lives and about em1's numbers.

- master (TASK-943, `975c18cc`): the authority is
  `skills.cold_email_writing.WORD_CONTRACT`; `lint` re-exports it as
  `lint.STEP_WORD_CONTRACT`; `REPLY_MIN_WORDS`, `REPLY_MAX_WORDS`,
  `REPLY_STEPS`, `reply_steps_for`, `lint.word_range` and the
  `reply_too_short` / `reply_too_long` codes are DELETED, and the 15-to-60
  thread-reply range is ABOLISHED.
- this branch: the authority is `lint.WORD_CONTRACT`, the skill card imports
  `lint`, em1 is `(90, 120, 140)`, and the 15-to-60 reply band is KEPT, moved
  into that dict.

Resolution, in the order the task set it:

1. em1 is `(90, 120, 140)`. The operator's decision of 2026-10-03, measured
   against his own 17 em1 exemplars.
2. master's STRUCTURE survives everywhere else.
   `lint.STEP_WORD_CONTRACT is skills.cold_email_writing.WORD_CONTRACT`, and
   `lint.REPLY_MIN_WORDS` / `lint.REPLY_MAX_WORDS` do not exist.
3. `tests/test_a_thread_reply_has_its_own_word_range.py` stays deleted.
4. em2 / em3 / em4 / em5 are master's values, because the branch's values for
   them ARE the abolished reply band.

### The import cycle, which decided the shape of the copystages resolution

`skills.cold_email_writing` imports `copystages` at module level to build
`SKILL.procedure`. With the authority in `skills.cold_email_writing`,
`copystages` can no longer do `from . import lint` - that closes the loop and
the contract is unbound when the module body runs. Measured, not argued. So the
branch's `render_writer_system(contract)` loses its contract parameter and
renders only `__EXEMPLARS__`; the word bands are typed into the prompt once and
held honest by
`tests.test_word_contract_enforced.TestTheProseAndTheContractAgree`, which reads
the strings actually handed to the model. That is a cross-check, not a second
authority: the prose cannot change the gate.

## The seven conflicts

**`src/skills/cold_email_writing.py` - master, then em1 edited.** Master's file
verbatim (it is the authority), with `em1` set to `(90, 120, 140)` and the
branch's exemplar measurement carried into the comment. The branch's only change
here was de-duplication via `lint.WORD_CONTRACT`, which is the same fix pointing
the other way and loses to rule 2.

**`src/lint.py` - master, all five hunks.** The branch's hunks were the 15-to-60
reply band: `WORD_CONTRACT`, `reply_band`, `is_reply_step`, `word_range`, the two
reply `EXPLAIN` entries and the reply branch of `check`. All abolished. The
branch's NON-conflicting work - `_strip_bare_name_signature` and the bare-name
branch of `countable_words` - is kept in full.

**`src/copystages.py` - master, all three hunks, then em1 edited.** Master's
typed-out prose with em1 moved to 90/140/120 in all of its renderings
(STRATEGY_SYSTEM ladder, the one-authority paragraph, the WRITER_SYSTEM headline
and bullet, the JSON schema slot, FINAL_CHECK). `from . import lint`,
`_em_schema` and the `__EM1_*` placeholders are removed - the cycle above.
`EXEMPLAR_FILES` / `exemplar_text()` / `__EXEMPLARS__`, which are what this
branch is FOR, survive.

**`tests/test_generate.py` - branch.** The fixture em1 body. Master's is ~45
words and is refused by the 90-word floor; the branch's long one is the fixture
the ruled band needs.

**`tests/test_ladder_propagation.py` - branch.** Same reason: the scripted
model's em1 body must clear 90 words.

**`tests/test_task913_writer_contract_five_plus_five.py` - master, both hunks.**
Both sides derive the mutation anchor from the contract rather than retyping it;
master's is derived from the authority that survives, and its slot format is the
one the merged `WRITER_SYSTEM` actually carries.

**`tests/test_a_thread_reply_has_its_own_word_range.py` - STAYS DELETED.**
Enumerated its 36 tests. Every one is about the abolished mechanism -
`reply_too_short` / `reply_too_long`, `lint.word_range(step, reply_steps)`,
`reply_steps_for`, `REPLY_MIN_WORDS` / `REPLY_MAX_WORDS`, an offer's rungs
overruling the contract, and the prompt stating "15 TO 60 WORDS" - except two
groups, and master already carries both verbatim in
`tests/test_word_contract_enforced.py`: `TestWhatCounts` (the opt-out and
signature exclusion, and the mid-body sign-off attack on the ceiling) and
`TestTheKeyIsRecovered` (step-key recovery, and that an ambiguous match answers
nothing). The two tests this BRANCH added to that file were new and still true -
em1's floor and ceiling enforced at the gate - and they are not lost:
`TestTheDeclaredBounds.test_every_floor_refuses_one_word_under_and_admits_itself`
and `..._every_ceiling_admits_itself_and_refuses_one_word_over` drive both bounds
of all five steps FROM the mapping, so they cover em1 at 89/90/140/141, and
`test_em1_is_90_140_em3_floor_is_60_and_em2_em4_em5_is_45` spells the triple out
once. Resurrecting the file would reintroduce the two authorities 943 removed.

## Changes beyond the seven conflicts

Each is a reader of a symbol one side deleted, or a test asserting a number the
ruling moved.

- `src/generate.py` (auto-merged, left BROKEN): `_step_refusals` still called
  `lint.explain(..., step_key=..., reply_steps=lint.reply_steps_for(
  _selected_offer(...)))` and the `draft` path still passed `step_key=day`.
  Neither name exists on master. Restored to master's `lint.explain(content,
  text)`; the branch's concern is served by master's parametrised
  `contract_code`, which carries the step, the count and both bounds.
- `src/lint.py`: removed `_LENGTH_SENTENCE` (branch-only, auto-merged in) and
  the `step_key` / `reply_steps` parameters of `explain`, which called the
  deleted `word_range`.
- `src/sequencegate.py`: `lint.WORD_CONTRACT["em1"]` ->
  `lint.STEP_WORD_CONTRACT["em1"]`.
- `prompts/exemplars/cadence-operator.md`: its rule line said em2 and em4 "are
  15 to 60 words" - the abolished band, reaching the MODEL through
  `WRITER_SYSTEM`. Corrected to 45 to 90. The operator's copy itself is
  untouched; this is the branch's own description of the cadence.
- `tests/test_word_contract_enforced.py` (master's, added by the merge): the em1
  assertions moved to the ruled band - the spelled-out triple, the declared
  range and target, the `*_contract_60_to_90` code strings, the sweep's lengths,
  `floors == {45, 60, 90}` and `ceilings == {90, 140}`, and the "a length
  MAX_WORDS admits and the contract does not" case moved from 100 (now legal) to
  150. 100 is asserted LEGAL in the same test so the move cannot hide a silent
  contract.
- `tests/test_the_em1_contract_has_one_authority.py` (branch's): rewired to
  `writer.WORD_CONTRACT` / `lint.STEP_WORD_CONTRACT`. The whole
  `TheReplyBandHasOneAuthorityToo` class asserted the abolished band and is
  replaced by `TheReplyBandIsABOLISHEDNotRelocated`, which keeps the two
  assertions still true and correct (`REPLY_MIN_WORDS` / `REPLY_MAX_WORDS`
  absent) and adds the control that the band is GONE rather than relocated. The
  derivation test that rendered the prompt against a moved contract is replaced
  by one that pins the cross-check guard instead, with the cycle written down as
  the reason.

Nothing was widened and no check was weakened. Where a test's old assertion
became false, the new assertion is at least as strict and the legal side of the
boundary is asserted too.

## Assertions

    STEP_WORD_CONTRACT is WORD_CONTRACT: True
    has REPLY_MIN_WORDS: False
    has REPLY_MAX_WORDS: False
    em1: (90, 120, 140)
    all: {'em1': (90, 120, 140), 'em2': (45, 60, 90), 'em3': (60, 75, 90),
          'em4': (45, 60, 90), 'em5': (45, 65, 90)}

Re-run under three import orders (lint first, skills first, copystages first)
after wiping `__pycache__` each time: identical, no cycle.

## Modules run

GREEN on the merged tree: `test_word_contract_enforced` (53),
`test_the_em1_contract_has_one_authority` (73),
`test_the_keyless_doors_get_the_contract` (15),
`test_task913_writer_contract_five_plus_five` (40),
`test_ladder_propagation` (25), `test_a_thread_reply_carries_no_rung_of_its_own`,
`test_em3_and_em5_can_satisfy_the_ladder_at_all`,
`test_the_ladder_is_a_ladder_of_roles`,
`test_the_ladder_is_checked_on_the_channel_it_belongs_to`,
`test_the_offer_ladder_is_enforced_as_step_objectives`,
`test_the_sequence_gate_catches_what_copylint_cannot`,
`test_a_dry_run_runs_the_sequence_gate`,
`test_the_entrypoint_actually_loads_its_skills`,
`test_the_clients_own_capability_is_not_an_invented_claim`,
`test_a_client_csv_fact_cannot_license_a_claim`,
`test_a_client_supplied_figure_licenses_no_claim_in_either_gate`,
`test_an_offer_cannot_be_invented`,
`test_a_permanent_operator_exclusion_survives_a_fact_refresh`,
`test_only_the_last_subject_may_claim_finality`,
`test_staging_a_campaign_twice_builds_one`,
`test_staging_hands_the_sequence_gate_its_inputs`,
`test_the_second_brain_returns_only_what_the_task_needs`,
`test_the_offer_cta_link_reaches_the_prospect`,
`test_a_truncated_answer_costs_one_attempt_not_the_round`.

RED on the merged tree, every one of them INHERITED - the same failing NAMES
measured on detached worktrees of my own at `2bf7b8a5` and at `68f3601b`:

- `test_generate` 2F/1E - identical 3 names on both parents
- `test_task910_writer_contract` 2F - identical on both parents
- `test_a_five_step_campaign_sends_five_different_emails` 1F - both parents
- `test_lead_variables` 2F - both parents
- `test_one_plan_decides_both_providers` 1F/5E - both parents
- `test_threaded_sequence` 3F - both parents
- `test_invariants` 3F - parents carry the SAME 3 plus an ERROR
  (`test_nothing_was_written_by_that`) that the merge does not have
- `test_fixture_hygiene` 5F - identical 5 names on both parents

Compared by NAME, never by count. **No module gained a failing name.**

## Not resolved

Nothing in the seven. Two things for the operator rather than for me:

- The inherited failures above are master's and the branch's, not this merge's.
  The gate for the merge TO master is still the named-list diff from a full run;
  this report is not that.
- The abolition means em2 and em4 are now 45 to 90 rather than 15 to 60. That is
  master's ruling of 2026-10-02 and it is what the branch's own
  `cadence-operator.md` had to be corrected to say. If the operator intends the
  shorter replies as well as the longer em1, that is a NEW ruling and it has to
  go into `skills.cold_email_writing.WORD_CONTRACT`, where
  `TestEveryRangeHasRoom` will check it has at least thirty legal lengths.
