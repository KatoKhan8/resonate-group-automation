# TASK-022 - Five variants per step, which the provider has always rotated

Operator backlog: QWEN-02 and experiment E2 in
`docs/ESTATE-LEARNING-2026-09-14.md`.

## GOAL

Make a cadence step carry its variants all the way onto the wire, so that
`COPY-EXPERIMENTS.md`'s five-variants-per-step becomes a thing that happens
rather than a thing that is specified.

## WHY IT MATTERS - measured 2026-09-14

Every campaign in the client's estate that replies above 6% uses three
subject variants per step, written as provider-native spintax:

    step1  {how {COMPANY} tracks margin today|the ops stack at {COMPANY}|
            project profitability at {COMPANY}}

EmailBison rotates them itself. Our campaign 481 sends `{SUBJECT_1}` -
exactly one variant per step - while `COPY-EXPERIMENTS.md` has specified five
per step all along and `heyreach.SEQUENCE_STEPS` notes that `messages` is a
LIST on the wire "which is where COPY-EXPERIMENTS.md's five variants per step
land: the provider rotates them itself, so a variant is a graph fact rather
than something this system has to assign per contact".

So the capability is documented on both providers, supported by both
providers, and used by neither of our campaigns.

**The honest caveat, and it must survive into the code comments:** in the
client's estate this is perfectly confounded with the April-22 rebuild, which
changed copy, sequence length and variant count at once. The 8.49% reply rate
of the 8-step campaigns is NOT attributable to variants. This task builds the
mechanism so E2 can be run as a single-variable experiment; it does not
assume the answer.

## CURRENT CONTEXT

- `src/variants.py` exists. Establish what it does and what reads it before
  writing anything - it may already hold the assignment model.
- EmailBison: a lead carries one value per custom variable, so `{SUBJECT_1}`
  resolves per lead. Provider spintax `{a|b|c}` lives in the SEQUENCE instead
  and is rotated by the provider, which is a different mechanism with a
  different owner. Decide which one this system uses and write down why. They
  are not interchangeable: spintax rotates per send and cannot be attributed
  to a contact; a per-lead variable can be attributed but is fixed per person.
- `COPY-EXPERIMENTS.md` says how a contact is assigned to a variant and why
  the evaluator refuses to call a winner from four replies against three.
  That document is the contract; this task implements it.

## SCOPE

1. Establish which mechanism carries a variant and why, in a comment a later
   reader can act on.
2. Carry a step's variants from canonical state to the provider payload,
   whichever mechanism wins.
3. Assignment must be DETERMINISTIC per contact and recorded, or the result
   cannot be attributed to anything. If provider spintax is chosen, say
   explicitly that attribution is lost and that E2 therefore cannot use it.
4. The evaluator must keep refusing an underpowered verdict. Do not lower the
   threshold to get an answer out of the current cohort of fifteen.

## FILES ALLOWED

`src/variants.py`, `src/bisonfactory.py`, `src/heyreachfactory.py`, `tests/`,
`docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/providers/**` - the wire format is established and is not yours to
change. `src/providerwrites.py`, `src/approve.py` - an approval is per step
key and fingerprinted, and a variant must not become a way around it.
`work/**`.

## THE RULE THAT MATTERS MOST HERE

**Every variant is approved copy or it is not sent.** Five variants means five
approvals, not one approval stretched over five. `bisonfactory._approved_copy`
refuses a step with no approval and must keep refusing a VARIANT with no
approval. If that makes five variants expensive, that is the correct price and
not a reason to loosen it.

## TESTS REQUIRED

- a step with five approved variants puts five on the wire;
- a step with five variants of which one is unapproved refuses, naming it;
- assignment is deterministic: the same contact gets the same arm twice;
- the evaluator still returns INSUFFICIENT_DATA on a cohort this size, and
  the test says what sample size it would need.

## RESULT

STATUS: done
COMMIT SHA: cea9a2b
TESTS: 8 new tests in test_five_subject_variants_the_provider_already_rotates.py,
  all pass. 151 related tests (variants, heyreachfactory, variant_wiring,
  variant_cadence_end_to_end, variant_attribution) all pass.
FILES CHANGED:
  src/bisonfactory.py - _approved_copy now resolves variants and checks approval
  src/heyreachfactory.py - assemble_linkedin_copy now resolves variants
  tests/test_variant_wiring.py - updated: apply_to_step now called from 3 places
  tests/test_five_subject_variants_the_provider_already_rotates.py - new test file
FINDINGS:
  - The mechanism is per-lead variables, not provider spintax. Spintax rotates
    per send and cannot be attributed to a contact; per-lead variables can be
    attributed but are fixed per person. Attribution is the whole point of the
    experiment.
  - The factory reads the recorded variant_id (sticky assignment from when the
    step was stored), applies the variant's words via apply_to_step, and checks
    the approval fingerprint covers them. A variant whose words don't match the
    stored approval is reported as missing copy.
  - test_variant_wiring had to be updated: it asserted apply_to_step was called
    from exactly one place (cadence.py). Now it's called from three (cadence,
    bisonfactory, heyreachfactory). The factories use it to resolve the recorded
    variant, not to assign a new one.
RISKS:
  - The stored step must have the variant's words AND an approval covering them.
    If a step was approved before variants were added, the approval won't match
    the variant's words and the factory will report it as missing. This is
    correct behaviour - the variant hasn't been approved - but it means existing
    campaigns with variants need to re-approve each variant's words.
RECOMMENDED CLAUDE ACTION:
  Review the factory changes. The key invariant: every variant is approved copy
  or it is not sent. Five variants means five approvals. The fingerprint check
  in _resolve_step_copy (bisonfactory) and assemble_linkedin_copy (heyreachfactory)
  enforces this.
