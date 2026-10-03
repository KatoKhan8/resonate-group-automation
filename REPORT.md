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
