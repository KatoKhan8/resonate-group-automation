PRIORITY: P0
DEPENDS: 

# TASK-137 - narrow four seals, then the control arm can ship

## EVERYTHING IS READY EXCEPT THIS

The operator approved shipping the validated fallback copy as the CONTROL arm.
Every other piece is established and verified:

    cohort        122 LinkedIn-reachable contacts with NO prior outreach
                  (151 reachable, 29 carry a prior EmailBison lead id and are
                  held out of the first campaign)
    campaign      599020, DRAFT, startedAt null, list 933603 attached
    sequence      ALREADY CORRECT. Pure merge variables - {connection_note},
                  {connected_1..4}, {message_2..4} - 27/27 readback PASS.
                  The words arrive per lead in customUserFields, so NO
                  sequence write is needed.
    copy          the operator's own fallbacks, the benchmark all three human
                  reads measured against
    lead builder  build_lead_pairs already supports arbitrary custom fields:
                  "Whatever this campaign's own copy asks for"
    connection    the sequence root is CHECK_IS_CONNECTION, so the provider
                  branches at runtime and a connection request never reaches
                  an existing connection
    predicate     campaign_cannot_send, fail-closed, DRAFT only, checked
                  immediately before the write. 20 tests, proven non-inert
    readback      VERIFIED on campaign 565765: 1000 leads paged with
                  leadCampaignStatus, leadConnectionStatus, errorCode

## THE ONE REMAINING STEP

`LINKEDIN_ADD_LEAD` must enter `providerwrites.SUPPORTED`, and **four seals
must be narrowed to match** - they currently assert it is never supported:

    tests/test_a_person_can_enter_a_heyreach_campaign.py, TheSealStillHolds
      test_linkedin_add_lead_is_not_supported
      test_supported_is_exactly_this
      test_the_add_lead_operation_is_still_not_supported
      test_the_write_layer_still_refuses_prospect_facing_ops

Claude enabled the route, saw these four fail, and **reverted rather than
narrow four seals hastily at the end of a long session**. They exist precisely
to make this deliberate.

## WHAT NARROWING MEANS - AND WHAT IT MUST NOT MEAN

Each seal should assert the CONDITIONAL permission, not the absence of one:

    add_lead is REFUSED for a campaign that can send        (IN_PROGRESS, PAUSED,
                                                             FINISHED, unknown)
    add_lead is REFUSED when the status read FAILS          (fail closed)
    add_lead is PERMITTED only for a campaign proven DRAFT
    LINKEDIN_ACTIVATE is STILL refused, unconditionally

**Do not delete a seal. Do not loosen `test_supported_is_exactly_this` into a
subset check** - its whole value is that it pins the exact tuple, so any future
addition has to be deliberate too. Update the expected tuple.

**Every replacement must be proven non-inert**: break the guard, confirm the
intended test fails for the intended reason, and confirm a different guard did
not fire first.

## WHAT YOU MAY NOT DO

- Do not add leads. Do not write to any provider. This task ends at green
  tests.
- Do not enable `LINKEDIN_ACTIVATE`. Activation is the prospect-facing moment
  and is a separate decision with its own evidence.
- Do not touch `campaign_cannot_send` or its 20 tests. They are correct.
- Read every test exit code OFF THE PROCESS, never through a pipe.

## DELIVERABLE

The four narrowed seals, the enablement in `SUPPORTED`, counterfactual
evidence per seal, and the full HeyReach neighbour suite green. Then Claude
performs the write: 122 leads with fallback copy in custom fields, provider
readback, and activation as a separate decision afterwards.
