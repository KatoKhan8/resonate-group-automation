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

---

## RESULT - CLAUDE, 2026-09-15

STATUS: DONE. Claude took this rather than a worker: QWEN.md forbids a worker
from adding an operation to `providerwrites.SUPPORTED`, which is the task.

COMMIT: 303b0fa

WHAT WAS BUILT, AND IT IS NOT WHAT THE TASK DESCRIBED

The task said "LINKEDIN_ADD_LEAD must enter SUPPORTED and four seals must be
narrowed to match". Entering SUPPORTED is necessary and is NOT the permission.
Tuple membership cannot express the rule the task itself states - "PERMITTED
only for a campaign proven DRAFT" - because that is a fact about the
DESTINATION at the moment of the write, not about the verb.

So `perform` gained a second key: a `CONDITIONAL` map of operation ->
predicate, run before the token is spent, which re-reads the destination
campaign from HeyReach and admits only one proven unable to send. Every other
route in SUPPORTED was safe by its own nature, which is why a list of names
was enough until now.

Refuses, fail-closed: IN_PROGRESS, PAUSED, FINISHED, an unrecognised status,
an absent status, an unreadable campaign, an exception of any kind, and a
caller naming no campaign at all.

THE PLACEMENT MOVED ONCE, AND THE FIRST PLACEMENT WAS WRONG TWICE

It was first written as the second thing `perform` does. That made a provider
NETWORK READ before the token was shown genuine, and it fired ahead of
`_require_approved_words` - so three tests proving unapproved copy cannot ride
an approved token failed for the wrong reason, a different guard reaching them
first. It now runs after every cheap local check and before `spend()`, so a
refusal costs nothing and the same token works once the campaign is put back
into a state that admits it.

FOUR SEALS NARROWED, SEVEN SIBLINGS FOUND

`test_supported_is_exactly_this` stays an exact-tuple comparison; the expected
value moved and the check did not loosen. The seal that said add-lead was
sealed now says ACTIVATE is - always the larger half, and it carries no
condition that could ever admit it.

Seven sibling seals in five other modules asserted the same absence and were
narrowed the same way: test_the_heyreach_write_contract (3),
test_the_factory_verbs_exist_and_are_sealed (3),
test_heyreachfactory_ensure_leads (1), test_the_write_layer_is_sealed (2),
test_the_stop_can_be_performed (2).

A DEFECT THE FIRST COHORT WOULD HAVE HIT

`ensure_leads` built its transport closure over the WHOLE batch while calling
`perform` once PER CONTACT: N contacts meant N writes each carrying all N
leads, each authorised by a token minted for one person, with a batch-wide
readback that passed on a lead a different authorization had put there. 122
leads would have been 122 writes of 122 pairs. Every test in that module
pushes a single contact, where N squared and N are the same number.

Fixed: one row per write, a readback scoped to that row, an expectation naming
that one profile. Three new tests assert what the factory HANDS the door
rather than what happened around it - that blind spot is where both defects
lived.

TESTS

    test_a_person_can_enter_a_heyreach_campaign      58  OK
    test_the_heyreach_write_contract                 23  OK (4 skipped)
    test_campaign_cannot_send                        20  OK
    test_heyreachfactory_ensure_leads                24  OK
    test_the_write_layer_is_sealed                   27  OK
    test_the_factory_verbs_exist_and_are_sealed      13  OK
    test_a_stop_beats_an_authorization               11  OK
    test_the_token_is_proof_of_one_action_only        5  OK
    test_a_confirmed_action_cannot_happen_twice      37  OK
    test_the_stop_can_be_performed                   17  OK
    test_staging_the_same_material_twice              7  OK
    test_a_campaign_intent_creates_one_campaign      34  OK

NON-INERTNESS, FOUR COUNTERFACTUALS, ALL RESTORED

    delete the guard CALL         10 of 11 condition tests fail; the
                                  admission test still passes, which is the
                                  positive control doing its job
    admit PAUSED in the predicate exactly one test fails, the intended one
    drop provider_campaign_id
      from ensure_leads           exactly one test fails, the intended one
    restore the batch closure     exactly one test fails, the intended one

LINKEDIN_ACTIVATE REMAINS SEALED, unconditionally, and is a separate decision.
