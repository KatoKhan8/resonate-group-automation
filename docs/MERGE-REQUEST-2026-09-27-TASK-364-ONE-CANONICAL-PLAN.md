# Merge request — TASK-364 rework 2, one canonical SequencePlan — 2026-09-27

Claude subagent, own locked worktree. **UNREVIEWED. Not merged by me.**

    branch      worktree-agent-abf3e260cec92585d
    based on    6e72f9f0   (master, TASK-426 merged)
    files       src/sequenceplan.py                          (+617, net +617)
                src/bisonfactory.py                          (+83 -197, net -114)
                src/heyreachfactory.py                       (+76 -168, net -92)
                scripts/render_preview.py                    (key rename)
                scripts/write_heyreach_sequence.py           (key rename)
                scripts/heyreach_readback.py                 (projects the plan)
                tests/test_one_plan_decides_both_providers.py  NEW (11 tests)
                tests/test_the_linkedin_graph_follows_the_canonical_days.py
                tests/test_campaign_cannot_send.py           (fake plan key)
                tests/test_campaign_repetition_integration.py  (key)
                tests/test_bison_campaign_write.py           (fixture key)
                tests/test_no_literal_name_in_campaign_graph.py (one test rewired)
                tests/test_the_sequence_belongs_to_nobody.py (fixture keys)
                tests/test_the_copy_lint_refuses_the_real_send_path.py (key)
                tests/test_an_approval_certifies_the_words_that_ship.py (key)
                tests/test_an_approval_is_not_a_fact_check.py (key)
                tests/test_emailbison_no_empty_greeting.py   (key)
                docs/CADENCE-ROWS-2026-09-27-WHICH-CAMPAIGNS-REFUSE.md  NEW

**NO PROVIDER WRITE HAPPENED.** No EmailBison, no HeyReach, no credential read,
no live test. Both providers are faked in every test; the HeyReach fake
delegates every pure function to the real module so the graph it records was
validated by the code that validates a real one.

---

## 1. WHAT THE TASK WAS, AND WHY IT FAILED TWICE

ONE canonical SequencePlan, built FIRST from strategy and copy, with both
provider factories and every write path reading only the plan.

Attempt 1 was unwired. Attempt 2 was worse: it built each provider's sequence
first and generated a "canonical plan" FROM the result. Plan and payload could
not disagree, so a consistency test between them passed by construction, and a
mutation of the plan could not change either payload. **The direction of
derivation was the whole task.**

## 2. THE SHAPE NOW

    strategy (this campaign's declared cadence_steps)
      + copy (the client's email templates and LinkedIn fallbacks)
              |
              v
      sequenceplan.for_campaign()   ONE plan. No leads, no provider call.
              |                                  |
              v                                  v
      derive_bison_sequence()          derive_heyreach_sequence()
      (EmailBison steps + title)       (the HeyReach graph)
              |                                  |
      bisonfactory._plan                 heyreachfactory._plan
      plan["provider_sequence"]          plan["provider_sequence"]
              |                                  |
      _ensure_sequence / _ensure_leads    stage / ensure_leads

Both factories build the plan from the same two inputs through the same
function, so the plan each reports is the same object for the same campaign -
asserted, not claimed: the acceptance module builds the plan itself and
compares it to `report["plan"]["sequence_plan"]` from both factories.

## 3. WHAT WAS DELETED, AND WHY THAT IS THE POINT

Three independent builders are gone:

- `bisonfactory._sequence_steps` no longer assembles anything. It keeps its
  signature - `configdiff` and the preview renderer reach the plan through it -
  and projects. `_resolve_thread_pattern` and `_order_of` moved with the
  construction they served.
- `heyreachfactory._li_message_delays` and `_build_sequence_no_inmail` are
  deleted. With them went this module's last read of the cadence library:
  **the graph's message delays came off `PRODUCTIVE_LI_HEAVY_V1` whatever the
  campaign declared.** `cadencelibrary` is no longer imported there at all.
- `heyreachfactory.merge_sequence_copy` is gone; the per-role copy block is
  part of the plan. `REQUIRED_ROLES` and `FALLBACK_CONFIG_KEY` are now bound to
  the plan's own constants rather than being second copies of them.

`plan["sequence"]` is RETIRED everywhere - both factory plans, the preview's
own plan-shaped dict, and `scripts/write_heyreach_sequence.py`. While a key of
that name exists, a write path can read a sequence that nothing derived from
the plan, which is the defect this task is about. A grep for it across `src/`,
`scripts/` and `tools/` returns nothing.

## 4. ACCEPTANCE — BY EFFECT, THROUGH THE FACTORIES

`tests/test_one_plan_decides_both_providers.py`, 11 tests, all green. Every
assertion goes through `bisonfactory.stage` or `heyreachfactory.stage`.

**The falsifier.** The fixture cadence declares five LinkedIn steps on days
1/5/11/18/26, so its inter-message gaps are 6/7/8. No ladder, client file or
default carries those numbers. A factory building its own graph produces
3/4/5 and cannot pass.

**Attacked three times, each time confirming the intended test failed for the
intended reason:**

    projection reads message_delays=None    test_the_graph_carries_this_
    (the old library constant)              campaigns_own_message_gaps
                                            FAILED: [3, 4, 5] != [6, 7, 8]

    derive_bison_sequence hardcodes         test_the_sequence_that_reaches_
    wait_in_days                            emailbison_is_the_projection FAILED

    _ensure_sequence hardcodes the title    the same test, and only that test

The second attack is the one that taught something: comparing a payload to
`derive_bison_sequence` puts the same bug on both sides of the equality, so
the email test ALSO asserts the provider-held waits against this cadence's own
gaps, written out in the test file.

**The mutation.** One edit to the canonical plan - the fourth step of each
channel moves - and both payloads move with it, each equal to its channel's new
projection. That is the assertion attempt 2 could not make.

## 5. THE TWO QUESTIONS I WAS ASKED TO ANSWER

### 5.1 A dry run does not run the sequence gate

Unchanged by this work and confirmed by probe: a dry-run report carries
`copylint` and **no** `sequencegate` key, because `stage()` still returns before
both gates when `live=False`. `docs/BRIEF-dry-run-executes-the-safety-path.md`
owns the fix.

**This wiring makes that fix EASIER, in four measurable ways.**

1. The early return and both gate functions are untouched here. The edits in
   `bisonfactory` are in `_plan`, in the plan dict, in `_ensure_sequence`'s
   title and at seven read sites - none of them in `stage()` between lines 72
   and 100 where the fix lands.
2. Both gates already read state the plan builds identically in both modes:
   `_copylint_batch` takes its expected step count from
   `plan["provider_sequence"]`, and the per-lead gate inputs TASK-426 added sit
   on `plan["leads"]`. The fix moves a CALL, not data.
3. The plan-level refusals already fire on the dry-run path - measured: a
   declared wait that does not reproduce the cadence refuses a dry run today.
   So the dry run is already the real decision path for the plan half; the two
   gates are what is left.
4. The acceptance module's dry-run tests use a fixture that passes both gates
   LIVE, so they stay green when the gates start running on dry runs.

One thing the fix must know: it should not re-derive the gate's inputs. The
qualification and capability come off the plan's leads and the projection off
`plan["provider_sequence"]`; a second derivation beside them is the same defect
in a new place.

### 5.2 The 64 campaigns and the canonical cadence

`docs/CADENCE-ROWS-2026-09-27-WHICH-CAMPAIGNS-REFUSE.md`, measured on the
production file and reconciled with `OPERATING-MODE` entry 9. In one line:
**five emails on days 1/4/8/12/21 is canonical and not in doubt** - it is
agreed independently by OPERATING-MODE, the shipped productive config and the
09-25 five-step merge request - and the twelve three-step rows are pre-09-24
declarations. **Three of those twelve are the ACTIVE campaigns** (487, 489,
493), whose sequences exist at a provider where `set_sequence` APPENDS, so
re-declaring them is not a row edit. Nothing was written to any row, no cadence
was changed, no fourth cadence was invented and no gate was widened.

## 5.3 THE MISTAKE THIS TASK MADE, AND WHAT CAUGHT IT

I checked for callers of the three functions this change deletes with a grep
piped through `head -30`. The output was truncated at exactly the line where
`tests/` began, so it reported `src/` hits only and I read that as "no test
callers". **A completeness check whose output is truncated is not a
completeness check.** The full suite found eleven names:

    6  test_the_linkedin_graph_follows_the_canonical_days   TASK-343's proof
    4  test_campaign_cannot_send                            fake _plan's key
    1  test_campaign_repetition_integration                 assertIn("sequence")

and three more fixtures that were passing the retired key into `_ensure_leads`,
`_refuse_unsupported` and the greeting guard **while staying green** - the key
was ignored, so the sequence they believed they supplied was empty. That half
is the more dangerous one, and a suite is what found it rather than a grep.

One production script called a deleted function: `scripts/heyreach_readback.py`
built its expected graph with `merge_sequence_copy`. It now projects the plan
and takes the CAMPAIGN ROW, which is a fix rather than a port - it was
comparing the provider's graph against one whose delays came off the library
ladder whatever the campaign declared, so a campaign running its own LinkedIn
days would have been reported DRIFTED against somebody else's clock.

TASK-343's module was repointed at the moved seam with every assertion
unchanged, because its subject - the ladder answer - is still exactly the
ladder answer, and its docstring now says where the campaign-cadence half is
proved.

## 6. WHAT THIS DOES NOT DO

- **Brief item 5 is not done, and colliding would have been worse.** Preview,
  XLSX and the approval hash deriving from the same plan is about the
  GENERATION-time half of the plan - `sequenceplan.new` plus its contacts,
  produced by `src/generate_campaign.py`, where TASK-400 is active and which
  this task is told not to edit. `derive_xlsx_data` does not exist on master
  at all; it was attempt 2's, on the abandoned branch. What this change does
  give the preview is a sequence that is a projection of the canonical plan
  rather than a second assembly.
- `plan["sequence_config"]` is left on the bison report and now has no reader
  in `src/`. Named as a follow-up candidate rather than removed on the same
  commit as the wiring.
- `_sequence_steps` builds a plan from a config fragment with `campaign=None`,
  which is a second CONSTRUCTION SITE of the same builder - not a second
  builder. It exists so `configdiff` and the preview keep their entry point.

## 7. SUITE — TWO RUNS, AND THE SECOND IS THE ONE THAT COUNTS

Both through `py -3 scripts/run_suite.py`, waiting for `scripts/suite_verdict.txt`
rather than grepping a running log, and diffed as a SET against
`docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names). The 228-failure 09-27
file is not a baseline and was not used.

    run 1   the wiring commit          2051s   136 names   15 new vs baseline
    run 2   this branch's head         1985s   125 names    4 new vs baseline

Run 1 is what found the eleven hidden callers of §5.3. Run 2 is the tree being
offered for merge.

**The four remaining new names are master's, not this branch's, and that is
shown by import graph rather than asserted:**

    test_an_offer_cannot_be_invented …test_approval_status_is_not_defaulted_to_approved
    test_fixture_hygiene …test_every_email_address_is_on_a_reserved_domain
    test_fixture_hygiene …test_no_real_client_prospect_or_roster_domain
    test_the_cadence_reacts_to_what_the_prospect_did …test_the_meeting_reaches_the_send_gate_too

None of those three modules imports `sequenceplan`, `bisonfactory` or
`heyreachfactory` - checked by importing each in a clean interpreter and
listing which of this branch's modules loaded: none did. The offers one is the
`approved` status now in `config/clients/productive-offers.yaml`; the hygiene
two name case-study, handoff and config files, and none of the files they name
is touched by this branch; the fourth is `eligibility.must_not_contact`
returning None where `blocked:company_paused` is expected, and `eligibility`
imports nothing from here either.

**One of those four is in a safety module** (`eligibility`), which is why it was
checked by import graph and not by judgement. It is a real problem and it is
somebody's - it is not this change's, and it was already failing before this
branch existed.

Seven baseline failures now PASS: the five `test_a_resume_leaves_a_ledger_row`
names the baseline itself flagged as pre-existing red,
`test_nothing_writes_to_a_provider`'s declared-write check, and the
`test_secrets` variable-example check that master's integration-queue run
already recorded as fixed. None of those is this branch's work either.

**Every module this branch touches or repoints is green**, run together: 170
tests, the only two failures being `test_campaign_cannot_send`'s
`test_add_lead_is_refused_for_finished` and `test_finished_is_not_proven_safe`,
both named in the 09-26 baseline.

The three protected proofs are whole at this head: `test_lead_writes_respect_
the_killswitch` 5/5, `test_staging_hands_the_sequence_gate_its_inputs` 12/12,
`test_sending_live_off_blocks_only_our_new_writes` 6/6.
