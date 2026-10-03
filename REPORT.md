# LADDER GATE LANE - `sequencegate.role_ladder` has no production caller

Branch `task-ladder-gate-wiring`, based on `task-integration-2026-10-03`
(`b3f703cbf`). `role_ladder` does not exist on master.

---

## STEP 1 - BLAST RADIUS, MEASURED BEFORE ANY WIRING

Everything below was produced with `role_ladder` STILL UNWIRED. Nothing in
`src/` was changed to take these numbers. The gate was called directly, and
for the test-suite column `sequencegate.check` was wrapped by an observer that
recorded the ladder's verdict and returned the real verdict unchanged, so no
host test's behaviour was altered while measuring.

### 1a. The live stage path, against production state

`work/queue.jsonl` (1,584 records) and `work/campaigns.jsonl` were copied to a
scratch directory and `QUEUE`/`CAMPAIGNS` pointed at the copy. Every campaign
row was run through `bisonfactory._plan`, and for each lead the `emails` dict
was built exactly as `_refuse_sequence_gate` builds it, then handed to
`role_ladder`.

| measure | value |
|---|---|
| campaign rows walked | 221 |
| campaigns whose plan builds at all | 1 (`productive-rachele-canary-20260929`) |
| sequences that reach the gate today | **1** |
| of those, refused by `role_ladder` | **1 (100%)** |

Reasons on that one lead: `role_unreadable` x4, `bump_without_thread` x3,
`ask_does_not_descend` x1.

Every other campaign row refuses earlier, at `_require_declared_cadence` or on
the `email_sequence.steps` / `cadence_steps` key mismatch, so the live stage
path is a one-lead sample and is NOT the number that matters for tonight.

### 1b. The stored copy corpus - the number that matters for tonight

Tonight's 215 emails will be newly written, so the honest estimate of what the
gate will say is what it says about the copy this generator has already
written. Copy lives at `record["cadence"][contact_key][step_key]["body"]`.

| corpus | contacts | refused by `role_ladder` |
|---|---|---|
| carrying a COMPLETE 5-step email sequence | 48 | **48 (100%)** |
| carrying a PARTIAL sequence (3 or 4 steps) | 1,277 | **1,277 (100%)** |

Steps present -> contacts: `{3: 1272, 4: 5, 5: 48}`. The 1,272 three-step
contacts are the retired three-step cadence; a dict missing `em4`/`em5` yields
those keys with an empty body, which is `role_unreadable` by design. They are
legacy and are not what tonight stages.

Failure counts over the 48 complete sequences (a sequence can carry more than
one of each):

| refusal | occurrences | sequences affected |
|---|---|---|
| `role_unreadable` | 186 | 48 / 48 |
| `bump_without_thread` | 144 | 48 / 48 |
| `ask_unreadable` | 84 | 46 / 48 |
| `proof_reused` | 35 | 14 / 48 |
| `ask_does_not_descend` | 20 | 20 / 48 |
| `role_shared` | 9 | 6 / 48 |

Distinct failure profiles over those 48:

| n | profile |
|---|---|
| 16 | `ask_does_not_descend` + `ask_unreadable` + `bump_without_thread` + `role_unreadable` |
| 16 | `ask_unreadable` + `bump_without_thread` + `role_unreadable` |
| 7 | `ask_unreadable` + `bump_without_thread` + `proof_reused` + `role_unreadable` |
| 5 | `ask_unreadable` + `bump_without_thread` + `proof_reused` + `role_shared` + `role_unreadable` |
| 2 | `ask_does_not_descend` + `bump_without_thread` + `role_unreadable` |
| 1 | all six |
| 1 | `ask_does_not_descend` + `ask_unreadable` + `bump_without_thread` + `proof_reused` + `role_unreadable` |

Which rung each step is credited with, over the 48:

| step | credited | unreadable |
|---|---|---|
| em1 | `proof` 5 | **43** |
| em2 | `smaller_piece` 2, `proof` 4 | **42** |
| em3 | `proof` 3 | **45** |
| em4 | `proof` 5, `offer` 1, `smaller_piece` 1 | **41** |
| em5 | `breakup` 29, `proof` 4 | 15 |

em5 is the only rung the existing copy reliably lands. em1 - the OFFER - is
unreadable in 43 of 48. This is the operator's own finding ("the same thing
said five times") measured mechanically.

### 1c. The committed artefact fixture

`tests/fixtures/converged-copy-anonymised-2026-10-02.json`: REFUSED, 9
failures - `role_unreadable` on em1/em2/em4/em5, `ask_does_not_descend` on
em3/em5, `bump_without_thread` on em2/em3/em4. This is the expected result;
`TheArtefactDoesNotPassTomorrowsGate` already asserts it.

### 1d. The control

`TheControlPasses.GOOD` - five steps built to the ladder - is NOT refused,
`why` empty. The gate does not refuse everything.

### 1e. The real cadences under `config/`

| client | `role_ladder` verdict | reasons |
|---|---|---|
| `productive` (`Resonate CONTROL`, em1-em5) | refused | `role_unreadable`, `ask_unreadable`, `bump_without_thread` |
| `demo` | refused | `role_unreadable`, `ask_unreadable`, `bump_without_thread` |

This one is NOT a finding about the copy. `config/clients/*.yaml`
`email_sequence.steps[*].body` is `"<p>{BODY_n}</p>"` - a merge-field
template. There are no words there to read, and the ladder must never be
pointed at it. It is recorded here only to rule out that seam: the config
cadence is the WRONG place to wire this gate.

### 1f. The test suite

Every test module that drives the stage path, instrumented so the ladder's
verdict was recorded without changing the real verdict. "seqs" is the number
of sequences `_refuse_sequence_gate` hands `sequencegate.check` during that
module's run.

| module | seqs seen | would be refused |
|---|---|---|
| `test_a_client_csv_fact_cannot_license_a_claim` | 1 | 1 |
| `test_a_client_supplied_figure_licenses_no_claim_in_either_gate` | 1 | 1 |
| `test_a_dry_run_runs_the_sequence_gate` | 7 | 7 |
| `test_a_five_step_campaign_sends_five_different_emails` | 18 | 18 |
| `test_an_approval_is_not_a_fact_check` | 3 | 3 |
| `test_crash_restart_idempotency` | 36 | 36 |
| `test_lead_variables` | 5 | 5 |
| `test_lead_writes_respect_the_killswitch` | 10 | 10 |
| `test_one_plan_decides_both_providers` | 8 | 8 |
| `test_only_the_last_subject_may_claim_finality` | 17 | 17 |
| `test_staging_a_campaign_twice_builds_one` | 22 | 22 |
| `test_staging_hands_the_sequence_gate_its_inputs` | 12 | 12 |
| `test_staging_refuses_colliding_contacts` | 11 | 11 |
| `test_the_copy_lint_refuses_the_real_send_path` | 3 | 3 |
| `test_the_offer_ladder_is_enforced_as_step_objectives` | 25 | 25 |
| `test_threaded_sequence` | 2 | 2 |
| `test_two_campaigns_do_not_collide_at_the_provider` | 60 | 60 |
| TOTAL | 241 | 241 (100%) |

Seventeen modules, 241 sequences, every one refused, every one on the same
three reasons (`role_unreadable`, `ask_unreadable`, `bump_without_thread`).
The cause is that these fixtures carry placeholder bodies, not prose. That is
the fixtures being unsuitable for this gate rather than the gate being wrong -
and it is also why a blanket refusal at that seam turns seventeen modules red
at once.

### THE NUMBER, IN ONE LINE

role_ladder refuses 100% of everything production and the suite currently
produce: 48/48 complete real sequences, 1/1 on the live stage path, 241/241
test-suite sequences, and the committed artefact. The only thing it does not
refuse is the hand-built control.

This is an operator decision and it is recorded here before a line was
changed. Nothing below widens a rule or weakens a refusal to shrink it.

---

## STEP 2 - WHERE IT IS WIRED, AND WHY THERE

`role_ladder` now has TWO production callers and BOTH verdicts are read. The
two seams answer different questions and neither replaces the other.

### 2a. `src/generate_campaign.py`, section G of `_process_contact`

    result["role_ladder"] = sequencegate.role_ladder(seqs_for_gate["emails"])
    ...
    failures = failures + ladder_failures(result["role_ladder"])

`failures` is the retry loop's input. `_retry_reasons` puts every distinct
refusal into the next writer prompt, so a sequence that misses a rung is
REWRITTEN; after `MAX_WRITER_ATTEMPTS` the contact is held `copy_refused` and
its `sequences` are emptied, which is what makes "never stored as a send
candidate" a property of the data rather than a comment.

WHY THIS SEAM. It is where the five bodies EXIST as the writer wrote them, in
ladder order, keyed `em1..em5`, before any P.S. or CTA is appended - exactly
and only what the ladder reads. It is the ONLY seam with a remedy. And the
reviewer's consequence names it: "still accepted by production GENERATION
today".

THE DOCUMENTED OBJECTION DOES NOT REACH IT. `generate_campaign` carries a long
comment declining to fold `result["sequence_gate"]`'s failures into this list,
because `offers.py` is single-tenant and the offer the gate is handed is
Productive's whatever client is generating - so Productive's approved ladder
would refuse another client's copy. `role_ladder(steps)` TAKES NO OFFER. It
reads the five bodies, `sequencegate`'s marker tuples and
`config/copy-ask-ladder.yaml` through `copylint.ask_rank`, none of which is
client data - and that YAML's own header says why it is not in the offer
library. Asserted on the SIGNATURE in
`test_the_ladder_takes_no_offer_and_so_is_client_neutral`, not argued in prose.

The ladder goes in BEFORE the optional `validate` callback, so enforcement does
not depend on a harness remembering to ask for it - which is precisely how the
rest of `sequence_gate` came to be computed and ignored.

### 2b. `src/bisonfactory.py`, `_refuse_sequence_gate`, beside `sequencegate.check`

    ladder = sequencegate.role_ladder(emails)
    ...
    if not result.get("passed") or ladder["refused"]:

WHY HERE AS WELL. The writer seam cannot protect copy written BEFORE the ladder
existed, and section 1b measured 48 such contacts carrying a complete five-step
sequence, all 48 refused. Those words are already in canonical state and they
reach the provider through `_refuse_sequence_gate`, never through the writer.
A gate only at the writer leaves them exactly as unguarded as they are today.

It sees the same `emails` dict `sequencegate.check` already receives: the
lead's certified copy keyed by cadence step with the approved P.S. appended -
the words the prospect actually reads.

The two verdicts are reported SEPARATELY on `report["sequencegate"]["leads"]`
(each lead carries its own `role_ladder` block with `refused`, `roles`, `asks`
and `failures`) and merged only for the raise, so an operator can still tell
which gate spoke. The block is written whether it refused or not, because
"the ladder holds" and "nobody applied the ladder" must not both read as an
absent key.

### THE CHAIN, EVERY LINK PROVEN CONSUMED

    writer answer
      -> result["sequences"]            em1..em5, raw
      -> seqs_for_gate["emails"]
      -> role_ladder(...)               COMPUTED
      -> ladder_failures(...)
      -> failures                       CONSUMED: breaks or continues the retry
      -> rejected -> _retry_reasons     CONSUMED: reaches the next prompt
      -> held, sequences emptied        CONSUMED: nothing is stored

    stored approved copy
      -> _approved_copy / _contact_words_for_plan
      -> plan["leads"][n]["copy"]
      -> emails{step_key: body}
      -> role_ladder(...)               COMPUTED
      -> refused.append(...)            CONSUMED: raises FactoryRefused
      -> report["sequencegate"]         CONSUMED: parseable verdict on report

---

## STEP 3 - PROOF BY EFFECT

Two new modules. Both carry their control, and the control is not decoration:
a gate that refuses everything satisfies every negative assertion in both.

### `tests/test_the_ladder_gate_is_called_on_the_real_path.py` - 7 tests, OK

Drives `bisonfactory.stage(live=False)`, the real production entrypoint, with
`providers.set_transport` booby-trapped to RAISE on any call, the real `bison`
module left in place, and the tenant killswitch deliberately ON so it cannot be
what stops the run.

The A/B is one body. `LADDER_GOOD["em2"]` opens "Following up on my note.";
`LADDER_BAD["em2"]` does not. Four of five bodies are identical, asserted by
`test_the_two_fixtures_differ_only_in_what_the_ladder_sees`, which also pins
that the ladder refuses the bad one on EXACTLY ONE check -
`bump_without_thread` at `em2` - so the refusal stays attributable.

  - `test_a_ladder_violating_sequence_is_refused_by_the_real_path`
    FactoryRefused, naming the gate, the check `bump_without_thread`, the step
    `em2` and the lead `rec-1/rec-1-c1`. Nothing reached the transport.
  - `test_the_refusal_is_the_same_one_a_live_run_would_give`
    `live=True` and `live=False` produce the identical message.
  - `test_the_ladders_verdict_is_on_the_refusals_report`
    read off `FactoryRefused.report`, not out of the prose of the message.
  - `test_a_sequence_built_to_the_ladder_reaches_the_projection`  THE CONTROL.
    Same fixture, one body different, runs all the way to the dry-run
    projection: five provider steps, no missing copy.
  - `test_the_ladders_verdict_is_on_the_passing_report_too`
    the five rungs are asserted in order and the asks asserted to descend, so
    a stub returning a bare false verdict could not pass it.
  - `test_bypassing_the_ladder_lets_the_same_bad_sequence_through`
    `role_ladder` patched to refuse nothing and the identical campaign reaches
    the projection - the refusal is the LADDER's, not another guard firing
    first.

### `tests/test_the_ladder_gate_is_read_by_the_writer_loop.py` - 7 tests, OK

Drives `generate_campaign.generate(live=False)` with the repository's own
scripted campaign model, subclassed so the ONLY thing that differs between the
two runs is the five bodies.

  - the violating draft: `role_ladder.refused` true, exactly
    `MAX_WRITER_ATTEMPTS` (10) rejections and every one of them the ladder's
    string and nothing else, `sequences` emptied, `hold_kind: copy_refused`;
  - the writer was asked again and the second prompt CONTAINS
    `bump_without_thread`, which is the remedy half;
  - THE CONTROL: the compliant draft is refused ZERO times - not "no ladder
    rejections", zero rejections of any kind - is not held, and carries all
    five bodies;
  - `ladder_failures` returns the empty list for a clean verdict and for
    `None`, so the translator cannot turn the gate into a refusal of
    everything.

---

## STEP 4 - MUTATION

`__pycache__` wiped before the mutation and again before each run.

MUTATION A, `src/bisonfactory.py`:

    -  if not result.get("passed") or ladder["refused"]:
    +  if not result.get("passed"):

MUTATION B, `src/generate_campaign.py`:

    -  failures = failures + ladder_failures(result["role_ladder"])
    +  pass

Result - the ladder-violating sequence is ACCEPTED again on both paths:

    tests.test_the_ladder_gate_is_called_on_the_real_path   FAILED (failures=3)
      FAIL test_a_ladder_violating_sequence_is_refused_by_the_real_path
           AssertionError: FactoryRefused not raised
      FAIL test_the_ladders_verdict_is_on_the_refusals_report
           AssertionError: FactoryRefused not raised
      FAIL test_the_refusal_is_the_same_one_a_live_run_would_give
           AssertionError: FactoryRefused not raised

    tests.test_the_ladder_gate_is_read_by_the_writer_loop   FAILED (failures=3)
      FAIL test_a_draft_that_misses_a_rung_is_refused_by_the_writer_loop
           AssertionError: 10 != 0
      FAIL test_a_draft_that_misses_a_rung_is_never_stored_as_a_candidate
           AssertionError: {} != {em1: Jane, your site says TestCorp is ...}
      FAIL test_the_writer_was_told_what_was_wrong_in_its_next_prompt
           AssertionError: 1 not greater than 1 : the writer was never asked
           a second time

Both controls stayed GREEN under the mutation, which is what a control is for:
it must not depend on the gate being switched on.

THE FIRST MUTATION RUN CHANGED THE WORK, which is the point of running one.
Two writer-loop tests stayed green with the ladder disabled, because their
`em1` leaned on `packfixture.GROUNDING` - a fact the generation fixture's
account knows nothing about - so `copylint`'s `first_line` rule was refusing
the draft and the hold was not attributable to the ladder at all. Two tests
that could not fail. `em1` now leans on `_account()`'s own source sentence,
the compliant draft is refused zero times, and the mutation above is the
re-run against the corrected module.

RESTORE, VERIFIED BY EFFECT AND NOT BY THE FILE LOOKING RIGHT:

    git diff --stat                        -> empty
    grep -rn for the MUTATION markers in src/ -> none
    both modules re-run after wiping __pycache__ -> Ran 14 tests, OK

---

## STEP 5 - WHAT THE WIRING ACTUALLY COSTS THE SUITE, MEASURED BY NAME

NO FULL SUITE WAS RUN. The machine-wide lock is held and queued, and a
`unittest discover` belonging to another track was observed running on this
machine throughout. What follows is 48 named modules - every module that
mentions `bisonfactory.stage`, `_refuse_sequence_gate` or `generate_campaign` -
run ONE PER SUBPROCESS, twice: once in a neutral worktree detached at the base
`b3f703cbf`, once on this branch. Compared BY NAME and BY SET, never by count.

    base worktree    .../scratchpad/wt-ladderbase   detached at b3f703cbf
    branch worktree  .../scratchpad/wt-ladder       task-ladder-gate-wiring

### 102 NEW FAILING NAMES, AND THEY ARE THE STEP 1 TABLE COMING TRUE

| module | new names | seam that causes them |
|---|---|---|
| `test_two_campaigns_do_not_collide_at_the_provider` | 24 | staging |
| `test_crash_restart_idempotency` | 9 | staging |
| `test_staging_a_campaign_twice_builds_one` | 9 | staging |
| `test_a_five_step_campaign_sends_five_different_emails` | 7 | staging |
| `test_staging_hands_the_sequence_gate_its_inputs` | 6 | staging |
| `test_staging_refuses_colliding_contacts` | 6 | staging |
| `test_lead_writes_respect_the_killswitch` | 5 | staging |
| `test_a_dry_run_runs_the_sequence_gate` | 4 | staging |
| `test_lead_variables` | 4 | staging |
| `test_only_the_last_subject_may_claim_finality` | 4 | both |
| `test_task400_rework2` | 3 | generation |
| `test_the_copy_lint_refuses_the_real_send_path` | 3 | staging |
| `test_an_approval_is_not_a_fact_check` | 2 | staging |
| `test_e2e` | 2 | generation |
| `test_generate` | 2 | generation |
| `test_one_plan_decides_both_providers` | 2 | staging |
| `test_task910_writer_contract` | 2 | generation |
| `test_the_offer_ladder_is_enforced_as_step_objectives` | 2 | staging |
| `test_threaded_sequence` | 2 | staging |
| `test_a_client_csv_fact_cannot_license_a_claim` | 1 | staging |
| `test_a_client_supplied_figure_licenses_no_claim_in_either_gate` | 1 | staging |
| `test_changing_an_approved_fact_changes_the_output` | 1 | generation |
| `test_the_research_pack_has_one_shape` | 1 | generation |
| **TOTAL** | **102** | staging 87, generation 11, both 4 |

The seam column is measured, not guessed: it is which of the two call sites
that module's run actually reaches, taken from the step 1 instrumentation.

### 25 OF THE 48 MODULES ARE UNCHANGED, which is the control on the measurement

`test_a_described_capability_traces_to_its_licensed_text`,
`test_a_question_says_which_kind_of_nothing_it_has`,
`test_a_truncated_answer_costs_one_attempt_not_the_round`,
`test_activation_refuses_without_the_operators_approval`, `test_audit`,
`test_list_staging_rehearsal`, `test_no_activation_without_an_exact_match`,
`test_no_model_is_not_a_bad_record`, `test_pilotpath`, `test_qwen_cli_model`,
`test_run`, `test_sending_live_off_blocks_only_our_new_writes`,
`test_task565_incident_regression_fixtures`, `test_task907_ps_producer_hop`,
`test_task911_second_brain_canonical_status`,
`test_task913_writer_contract_five_plus_five`,
`test_the_entrypoint_actually_loads_its_skills`,
`test_the_entrypoint_is_the_only_generation_path`,
`test_the_entrypoint_refuses_at_a_client_ceiling`,
`test_the_ladder_is_checked_on_the_channel_it_belongs_to`,
`test_the_writer_is_told_how_long_its_answer_may_be` - all OK on both sides.
`test_only_the_selected_offer_is_validated`, `test_preproduction`,
`test_set_regeneration`, `test_task400_rework3` - RED on both sides with the
SAME name sets, so they are not this branch's.

A handful of names appear in both the NEW and the GONE column of the same
module (`test_lead_variables`, `test_threaded_sequence`,
`test_one_plan_decides_both_providers`, `test_task910_writer_contract`,
`test_a_five_step_campaign_sends_five_different_emails`): those modules were
already RED on the base and the failure moved from FAIL to ERROR or back. They
are counted as new above, which is the conservative reading.

### `test_fixture_hygiene` and `test_invariants`, run on both sides

8 failing names on the base, the SAME 8 on the branch, ZERO new. Neither
`REPORT.md` nor either new test module is named by any hygiene failure, and
nothing in this branch's diff adds an `os.environ.get` state lookup, so the
barrier checklist is untouched.

---

## WHAT THIS LEAVES FOR THE OPERATOR, AND IT IS A DECISION, NOT AN EDIT

No rule was widened and no refusal was weakened to shrink any of the numbers
above. The gate is correct and the copy is bad, and I checked that directly
rather than assuming it: the stored five-step sequences are PLAIN PROSE, not
HTML and not placeholders, and reading one shows exactly what the operator
described - em1 that never says what the reader gets, no step that references
the thread it is continuing, no named client with a number, and an em4 that
explains the prospect's own company back to them. The refusals are true
positives. This is not a shape error at the call site.

Three facts the decision rests on:

1. **Nothing merged and nothing deployed.** This is a local branch.
2. **Generation is where the defect lives and where it can be fixed.** Wiring
   the writer seam alone costs 11 new names (15 counting the shared module)
   and gives the writer the ladder's refusals as feedback, which is the
   mechanism by which 215 emails get written TO the ladder instead of around
   it. With the current corpus as the guide, the first drafts will be refused
   and rewritten; drafts that still miss a rung after ten attempts are HELD,
   not shipped.
3. **The staging seam costs 87 of the 102 names and protects a narrower
   thing**: the 48 already-stored sequences. Those are additionally behind
   three barriers CLAUDE.md already records - the killswitch refuses in code,
   `sending.live` is false, and 0 of 3,005 stored approvals are still valid.
   It is the right guard and it is the expensive one.

If the operator wants generation enforced tonight and the staging seam
deferred, the whole of the staging change is one condition in
`src/bisonfactory.py`:

    if not result.get("passed") or ladder["refused"]:   <- as committed
    if not result.get("passed"):                        <- staging seam off

That is MUTATION A from step 4, so its exact effect is already measured: the
three staging tests in `test_the_ladder_gate_is_called_on_the_real_path` go
red and say so by name, which is the honest record of a gate switched off
rather than a gate quietly never called. The 87 names return to green.

I have not made that change. It is the operator's call, and it is recorded
here rather than taken.
