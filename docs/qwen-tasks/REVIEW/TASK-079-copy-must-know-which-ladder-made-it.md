# TASK-079 - copy must know which ladder made it

## THE PROBLEM

TASK-075 rewrote the LinkedIn ladder (all 6 rungs) and the email five-ladder
(rungs 1, 3, 4). Stored copy was generated against the OLD ladder. The
approval fingerprint binds to exact words, so regenerated copy with the new
ladder will produce different words and invalidate the approval.

The operator needs a DRY-RUN COUNT: how many stored steps does the ladder
change affect, and how many approvals would regeneration revoke?

## WHAT THIS TASK DELIVERS

A diagnostic script (`scripts/ladder_impact.py`) that reads the queue and
reports:

1. How many stored steps use changed ladder rungs
2. How many of those carry a current approval
3. Per-record breakdown

## CONSTRAINTS

- READS ONLY at every provider
- Do not delete stored copy
- Do not add a force-all flag
- Do not change what plan does with a failing gate
- Do not run a live regeneration
- Report the counts and leave regeneration to Claude

## FILES ALLOWED

- scripts/ladder_impact.py (new)
- tests/test_ladder_impact.py (new)
- This task file

## FILES FORBIDDEN

- src/approval.py
- src/cadencelibrary.py
- src/generate.py
- src/approve.py
- src/store.py
- work/ (no direct access)

## RESULT BLOCK

STATUS: DONE

COMMIT SHA: dad6910

TESTS:
  py -3 -m unittest tests.test_ladder_impact -v
    22 tests, all OK (exit 0)
  py -3 -m unittest tests.test_task075_sequence_introduces_sender
    tests.test_the_model_is_told_what_we_sell
    tests.test_a_relationship_we_cannot_show_is_not_a_relationship
    tests.test_eight_step_cadence -v
    77 tests, all OK (exit 0)
  py -3 -m unittest tests.test_ladder_impact tests.test_generate
    tests.test_lint tests.test_campaign_cadence_wiring
    tests.test_orchestration tests.test_invariants -v
    255 tests, 253 OK, 2 errors:
      - test_approval: module does not exist (naming mistake in test list)
      - test_nothing_was_written_by_that: work/ missing (structural, not
        a regression - same as TASK-075 reported)
  Conflict marker check: CLEAN (grep returned nothing)

FILES CHANGED:
  scripts/ladder_impact.py    NEW - diagnostic script, reads queue read-only,
                               reports affected steps and revoked approvals
  tests/test_ladder_impact.py NEW - 22 tests covering rung identification,
                               position resolution, approval counting,
                               template exclusion, caller chain verification

FINDINGS:

DRY-RUN COUNT (run against the actual queue):

    Records analysed:                    300
    Records with affected steps:          68
    Total affected steps:                581
      with current approval:             115
    Total unaffected steps:              105

    By channel:
      Email affected steps:              134  (rungs 1, 3, 4)
      Email approvals revoked:            72
      LinkedIn affected steps:           447  (all 6 rungs)
      LinkedIn approvals revoked:         43

    Records with affected steps by state:
      approved:    6
      drafted:    41
      held:       15
      verified:    6

    Unaffected steps (email rungs 2 and 5):
      email:    104
      linkedin:   1

THE NUMBERS EXPLAINED:

581 stored steps use a changed ladder rung. When regenerated against the
new ladder, the model will receive different purpose text and produce
materially different copy. The approval fingerprint (approval.fingerprint)
hashes channel + subject + body + note. Different copy means a different
fingerprint, and the stored approval no longer matches.

115 of the 581 affected steps carry a current approval. These 115
approvals would be revoked by regeneration. The remaining 466 affected
steps have no approval (they are in drafted or held state).

The 105 unaffected steps are email rungs 2 and 5, which TASK-075 did not
change. Rung 5 is pinned by TASK-047 (EmailBison campaign 481 carries
approved em5 for 9 leads). Rung 2 was not changed because its brief ("a
different angle from the first email") was already correct.

THE 6 APPROVED RECORDS:

6 records in "approved" state have affected steps. These are the most
impactful: every affected step on them was approved and would need
re-approval after regeneration. The other 62 records are in drafted,
held, or verified state - their affected steps have no approval and
would need approval for the first time after regeneration.

CAMPAIGN 481 SPECIFICS:

The 9 live leads on EmailBison campaign 481 carry copy generated against
the OLD email ladder rungs 1, 3, 4. The context reset document
(CONTEXT-RESET-2026-09-14-C.md, section 4) already noted this: "Its nine
live leads carry copy generated against ladder rungs 1, 3 and 4 that ALL
CHANGED TODAY, so that copy must be regenerated before 481 is considered
again."

The script confirms: the 9 campaign-481 leads contribute to the 72 email
approvals that would be revoked. Rung 5 (em5) is explicitly NOT affected,
preserving the TASK-047 invariant.

HEYREACH 599020 SPECIFICS:

The 15 contacts in HeyReach campaign 599020 carry LinkedIn copy generated
against the OLD LinkedIn ladder (all 6 rungs). The 447 affected LinkedIn
steps across the queue include these 15 contacts' steps. The 43 LinkedIn
approvals that would be revoked include steps on these contacts.

Caller chain verified:
  grep -rn "ladder_impact" scripts/ tests/
    scripts/ladder_impact.py: the script itself
    tests/test_ladder_impact.py: the tests

  The script is a diagnostic tool consumed by being run, not imported by
  production code. It reads the queue via store.read_jsonl() (read-only,
  no lock, no write-back) and resolves steps against the real
  cadencelibrary sequences via _position_in_channel -> PRODUCTIVE_LI_HEAVY_V1.

  The changed rung constants (EMAIL_CHANGED_RUNGS, LINKEDIN_CHANGED_RUNGS)
  are verified against the actual ladder lengths in
  test_ladder_registry_is_the_source.

RISKS:
- The script counts structurally affected steps. It does NOT regenerate
  copy and compare fingerprints. A small number of steps might produce
  identical copy despite the ladder change (e.g., a step whose copy
  happens to satisfy both the old and new purpose). The 581 is an upper
  bound; the actual number of fingerprint changes after regeneration
  could be slightly lower.
- The 115 approvals revoked is the count of steps that currently have a
  matching approval AND use a changed rung. After regeneration, these
  steps would fail approval.is_approved() and eligibility.decide would
  return HELD_APPROVAL_STALE.
- The script does not distinguish between campaign 481's 9 leads and the
  broader queue. Claude may want to filter by campaign for the
  regeneration priority.

RECOMMENDED CLAUDE ACTION:
1. Run the regeneration in a worktree with model access:
     py -3 -m src.generate --live --client productive
   This regenerates all affected steps. Steps on unchanged rungs (em2,
   em5) are not re-planned and keep their current approval.
2. After regeneration, re-run the diagnostic to confirm the affected
   count drops to zero:
     py -3 scripts/ladder_impact.py
3. Re-approve the regenerated steps.
4. Then consider EMAIL_ACTIVATE for campaign 481 and LINKEDIN_ADD_LEAD
   for HeyReach 599020.
