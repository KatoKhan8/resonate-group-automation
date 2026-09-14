# TASK-002 - What HeyReach can actually be asked, on paper

## GOAL

A precise, evidence-backed statement of which HeyReach routes in
`src/providers/heyreach.py` could answer two questions - "is this profile an
Open Profile" and "can this seat send an InMail" - and which cannot, derived
from the adapter and its fixtures WITHOUT making a live call.

## WHY IT MATTERS

`src/cadencelibrary.py` declares `CAP_OPEN_PROFILE` and `CAP_INMAIL`, and
`productive_li_heavy_v1` HOLDS any step that needs them because neither is
established. A held step is correct and it is also a cadence running ten
touches while reporting eleven. Before anybody spends a live call measuring
this, the paper answer should exist: which route, which field, what the
absence of that field would mean.

## CURRENT CONTEXT

- `src/providers/heyreach.py` is ~2300 lines. `WRITE_ROUTES` is seven routes
  and is asserted by seal tests; reads wired are listed in
  `docs/CLAUDE-HANDOFF.md`.
- Resume, StartCampaign and every `AddLeadsToCampaign` spelling are
  deliberately absent and asserted absent.
- Campaign 599020 exists at the provider in DRAFT with no sequence.

## SCOPE

Read-only analysis plus tests.

1. Enumerate every response field any wired read route is known to return,
   from the fixtures in `tests/` and from the adapter's own parsing.
2. For each of the two capabilities, answer one of:
   - SUPPORTED, naming route + field + the fixture that shows it;
   - UNSUPPORTED, naming what was looked for and where;
   - UNDETERMINED FROM FIXTURES, naming the single cheapest live read that
     would settle it and what each possible answer would mean.
3. Write a test asserting the capability constants are consumed by the state
   machine - that a step naming an unproven capability is HELD and not
   silently dropped. Assert on behaviour (what the planner returns), never by
   grepping source text. CLAUDE.md is explicit about this and it has bitten
   this repo before.

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`, a new markdown report under `docs/`.

## FILES FORBIDDEN

`src/providers/heyreach.py` and every other `src/**` file. This task changes
no adapter. `work/**`.

## PRODUCTION CONSTRAINTS

Zero network. Zero credentials. Do not call HeyReach. Do not touch campaign
599020 or 594061, and do not touch the other 48 campaigns in that workspace -
they are the client's own live work.

## TESTS REQUIRED

At least one behavioural test for the hold path described above. It must fail
if the hold is removed - prove that by removing it temporarily, confirming
the intended test failed for the intended reason, and restoring.

## EXPECTED OUTPUT

`docs/HEYREACH-CAPABILITY-CONTRACT.md` with one classification per
capability, plus the test.

## DONE CONDITION

Claude can read that document and know exactly which one live call to spend
next, or that no live call is needed because the fixtures already answer it.

## RESULT

STATUS: done

COMMIT SHA: ab048e2

TESTS:
  17 tests in tests/test_task002_capability_contract.py - all pass.
  Four classes:
    CapabilityTableContract (7 tests) - CAP_CONNECT/MESSAGE proven True,
      CAP_OPEN_PROFILE/INMAIL proven False, unknown capability refused,
      empty capability satisfied, every shipped sequence capability
      classified in the table.
    OpenProfileCapabilityHeld (4 tests) - the li1 open-profile
      alternative is chosen when OPEN_PROFILE state is observed, held
      with HELD_CAPABILITY_UNPROVEN, names its node as the alternative,
      and the counterfactual (flipping the table) makes it GO.
    InMailCapabilityHeld (4 tests) - the li3 InMail fallback is chosen
      after unaccepted connection, held at step 4 (capability gate)
      before step 8 (eligibility), held even when provider says
      eligible, and the counterfactual makes it GO.
    CapabilityGateIsTheGatekeeper (2 tests) - capability gate fires
      before prospect-state checks; proven capabilities pass through.
  Break-the-wiring verified: removing the capability check from
    plan_step (src/linkedinstate.py lines 787-791) causes 4 tests to
    FAIL for the intended reason (go instead of wait, None instead of
    HELD_CAPABILITY_UNPROVEN). Restored, all 17 pass.

FILES CHANGED:
  tests/test_task002_capability_contract.py   (new) 17 behavioural tests
  docs/HEYREACH-CAPABILITY-CONTRACT.md        (new) the capability contract
  docs/qwen-tasks/RUNNING/TASK-002-heyreach-capability-contract.md
    -> docs/qwen-tasks/DONE/TASK-002-heyreach-capability-contract.md

FINDINGS:

  CAPABILITY VERDICTS:

  1. CAP_OPEN_PROFILE (linkedin.open_profile_message): UNSUPPORTED
     Route checked: every wired read route.
     Field sought: openProfile, isOpenProfile, premium, connectionDegree,
       or any boolean/enum indicating Open Profile status.
     Found in: NOWHERE. /lead/GetLead returns 23 keys, none indicate
       Open Profile. /campaign/GetLeadsFromCampaign's linkedInUserProfile
       has 16 keys, none indicate it. /inbox/GetConversationsV2's
       correspondentProfile.connections is an integer count, not a status.
     CHECK_IS_OPEN_PROFILE is a documented branching node type but was
       NOT observed in any of 82 campaigns (1194 nodes). It works inside
       a running graph and is not externally readable.
     Cheapest live read: NONE. No route exposes this as a queryable field.
     What would change it: vendor adds a field to an existing read route.

  2. CAP_INMAIL (linkedin.inmail): UNSUPPORTED
     Route checked: every wired read route.
     Field sought: lead-level InMail eligibility or reachability.
     Found in: /li_account/GetAll carries inMailLimit, inMailLimitMax,
       inMailCooldown at SEAT level. These describe OUR capacity, not
       prospect reachability. No lead-level field exists.
     INMAIL is a real node type (15 occurrences across 82 sequences).
       The payload shape is objects with subject+message, not strings.
       The adapter handles this correctly.
     Cheapest live read: NONE. No route exposes prospect-level InMail
       eligibility.
     What would change it: vendor adds a lead-level field, or a
       CONNECTION_REQUEST_ACCEPTED webhook / /MyNetwork/IsConnection is
       wired into the allowlist.

  WHAT TASK-025 ALREADY SETTLED:
  - CAP_OPEN_PROFILE and CAP_INMAIL are both False in CAPABILITIES.
  - leadobserve.observe() has no caller in src/ (wiring gap, not
    capability gap).
  - Steps naming unproven capabilities are HELD by plan_step.
  - 9 behavioural tests in test_task025_funnel_unproven_held.py assert
    the hold path (on qwen-worker-2; not synced to this worktree).
  This task extends TASK-025 with:
  - Enumeration of every response field from every wired read route.
  - The counterfactual test (flipping the table is the ONLY change).
  - The ordering test (capability gate fires before prospect-state).
  - The completeness test (every shipped sequence capability classified).

  CALLER VERIFICATION (QWEN.md rule):
  grep -rn "capability(" src/ -> 2 hits:
    src/linkedinstate.py:244  (definition)
    src/linkedinstate.py:788  (called by plan_step - the real entry point)
  grep -rn "HELD_CAPABILITY_UNPROVEN" src/ -> 4 hits:
    src/linkedinstate.py:205  (definition)
    src/linkedinstate.py:790  (returned by plan_step)
    src/linkedinstate.py:861-863  (comments)
    src/nextaction.py:137  (consumed - mapped to WAIT_LINKEDIN_CAPABILITY)
  Chain: plan_step -> capability() -> CAPABILITIES -> HELD_CAPABILITY_UNPROVEN
    -> nextaction.py. Fully consumed.

RISKS:
  - Both verdicts are UNSUPPORTED, not UNDETERMINED. The adapter's own
    constants (OPEN_PROFILE_DETECTABLE = False, INMAIL_ELIGIBILITY_DETECTABLE
    = False) agree. If the vendor adds a field tomorrow, the verdicts
    change by adding a read route and flipping a CAPABILITIES entry.
  - The break-the-wiring verification temporarily modified src/linkedinstate.py
    and restored it. git diff src/ is clean. The verification proved 4 tests
    fail for the intended reason when the capability check is removed.

RECOMMENDED CLAUDE ACTION:
  1. No live call is needed. The fixtures already answer both questions:
     neither capability is readable from any wired route, and no single
     live call would change that verdict.
  2. If the vendor adds Open Profile or InMail eligibility fields, the
     path to validation is: add the read route to READ_ROUTES_ALL, parse
     the field in the adapter, flip the CAPABILITIES entry to True, and
     the 17 tests (including the counterfactuals) will validate the change.
  3. The CHECK_IS_OPEN_PROFILE node type exists in the vendor's vocabulary
     but was not observed in this workspace's 82 campaigns. If a future
     campaign uses it, the adapter already recognises it as a LinkedIn-only
     node (LINKEDIN_ONLY_NODES) and a branching node (BRANCHING_NODES).
