# TASK-019 - The caller that puts a real lead into a HeyReach campaign

Operator backlog: QWEN-09, QWEN-12.

## GOAL

Build `heyreachfactory.ensure_leads` - the caller that takes a campaign's
pushable contacts and puts them into the provider campaign through
`providerwrites.perform`, with a readback that decides the verdict. Build it
and prove it offline. DO NOT enable the route and DO NOT make a live call.

## WHY IT MATTERS - and read this before assuming it is nearly done

TASK-009 built the TRANSPORT: `heyreach.add_leads_to_campaign`,
`heyreach.readback_membership`, `heyreach.check_tenant`, all tested, 35 tests.
`/campaign/AddLeadsToCampaignV2` is on `heyreach.WRITE_ROUTES`.

**Nothing calls any of it.** `grep -rn "add_leads_to_campaign" src/` returns
the definition and nothing else. That is the recurring defect in this
repository - a thing computed correctly that nothing downstream reads - and
it is why the HeyReach campaign has held zero leads while the blocker was
recorded as "one line in `SUPPORTED`".

It was never one line. On 2026-09-14 the campaign behind that line was found
to be carrying ONE contact's personalised copy for all fourteen records; see
`docs/HEYREACH-PERSONALISATION-2026-09-14.md`. That is fixed - the graph now
carries `{connection_note}` and friends and each lead brings its own words -
which is exactly what makes this task worth doing now.

## CURRENT CONTEXT, measured 2026-09-14

- `heyreachfactory._plan` returns `pushable`: contacts scoped to the
  campaign's own `record_ids` and client, each with `custom_fields` holding
  their approved copy keyed by graph role. Dry run on
  `productive-linkedin-production-v1`: 15 contacts, 15 pushable, 0 missing.
- `heyreach.refuse_unsupported_sequence(sequence, rows)` raises unless EVERY
  row supplies EVERY variable the sequence uses. Verified end to end: a batch
  with one lead short of `connected_4` is refused by name.
- HeyReach 599020 is DRAFT, seat 174892, list 933603 bound and holding 0.
- `LINKEDIN_ADD_LEAD` is prospect-facing, so `providerwrites.perform` will
  demand a real `executionguard.Authorization`. That is correct and is the
  point; do not route around it.

## SCOPE

1. `ensure_leads(campaign_id, *, recs=None, config=None, live=False,
   by="system")`, modelled on `bisonfactory._ensure_leads`, which is the
   reference implementation for every gate below.
2. Before any write, in this order, and each one REFUSING rather than
   skipping: killswitch workspace state; suppression and DNC; account
   collision; `heyreach.check_tenant`; `refuse_unsupported_sequence` against
   the rows actually being pushed.
3. Mint one `executionguard.Authorization` per contact. Never one for the
   batch - the gates are per person.
4. Write through `providerwrites.perform(LINKEDIN_ADD_LEAD, ...)` with
   `transport=` and `readback=`. THE READBACK DECIDES. The response body of
   `AddLeadsToCampaignV2` has never been read and its shape is unknown, so
   nothing may be concluded from it; `readback_membership` is the verdict.
5. Idempotent: re-running must not create a second membership. Read
   membership first and push only the difference, as `attach_leads` does.
6. Dry run must print exactly who would be pushed, from which seat, with
   which variables, and must touch nothing.

## FILES ALLOWED

`src/heyreachfactory.py`, `tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/providerwrites.py` - the `SUPPORTED` tuple is Claude's and enabling the
route is an operator decision. `src/providers/heyreach.py` - the transport is
done; if you believe it is wrong, write that under FINDINGS instead of
changing it. `src/executionguard.py`, `src/killswitch.py`, `work/**`.

## PRODUCTION CONSTRAINTS

ZERO network. ZERO credentials. Do not call HeyReach. Do not touch campaign
599020, 594061 or any of the 48 client campaigns. Every test runs against a
fake transport.

Leave `LINKEDIN_ADD_LEAD` out of `SUPPORTED`. Your work is finished when the
only thing between it and a real lead is a human deciding.

## TESTS REQUIRED

Behavioural, against a fake transport. At minimum:

- a contact who fails suppression, DNC, collision or the killswitch is refused
  BY NAME and the transport is never reached;
- a batch where one lead cannot fill one variable refuses the WHOLE push -
  because HeyReach would send that step's fallback to that person;
- a tenant mismatch refuses before the transport;
- re-running pushes nobody twice;
- a readback that disagrees with what was asked for RAISES rather than
  reporting success;
- a transport that answers 200 with a body nobody can classify does not
  become a success.

Then break each guard deliberately and confirm the INTENDED test fails for
the INTENDED reason - and that a different guard did not fire first.

STATUS: done (rework after REVIEW 1 rejection)
COMMIT SHA: pending
TESTS: 18 tests in tests/test_heyreachfactory_ensure_leads.py, all passing.
  16 original behavioural tests + 2 new authorization gate tests.
  36 existing tests in tests/test_heyreachfactory.py still pass.
  54 total heyreachfactory tests green.
FILES CHANGED:
  src/heyreachfactory.py - _mint_authorization now calls
    executionguard.authorize() instead of constructing Authorization directly.
    Removed actionledger import (no longer needed). Added configdiff import.
  tests/test_heyreachfactory_ensure_leads.py - added configdiff and
    executionguard imports. Updated _patch_external to mock
    configdiff.compare_heyreach and executionguard.authorize. Added
    AuthorizationGateRefuses class with two tests.
FINDINGS:
  REWORK: _mint_authorization CONSTRUCTED Authorization(...) directly.
    providerwrites.perform checks with isinstance, so a hand-built object
    passed while having passed NO gate. executionguard.authorize() is now
    the ONLY construction site in src/ (grep confirms: one match at
    executionguard.py:658). The five pre-filter gates remain as a cheap
    pre-filter that refuses by name before the expensive path.
  _mint_authorization now calls executionguard.authorize() with:
    operation=LINKEDIN_ADD_LEAD, channel="linkedin", campaign, rec, contact,
    step_key="day3" (a LinkedIn step in cadence.STEPS), workspace=client,
    config, readback (from configdiff.compare_heyreach), by.
  Each contact gets its own Readback from configdiff.compare_heyreach()
    because authorize() spends it. This is expensive but correct: each
    authorization gets its own sealed, timestamped provider comparison.
  NEW TEST: test_authorize_refuses_on_approval_gate_write_never_happens
    drives ensure_leads through a contact that passes all five pre-filters
    but fails the "approval" gate (which the five do not check). Mocks
    authorize() to raise NotAuthorized("approval", ...). Asserts the
    transport is never reached. If the implementation constructed
    Authorization directly (bypassing authorize()), this test FAILS.
  NEW TEST: test_authorize_must_be_called_not_constructed asserts that
    authorize() is actually called. If the implementation constructs
    Authorization directly, the mock is never called and the assertion
    fails. This is the test the review demands.
  LINKEDIN_ADD_LEAD remains NOT in SUPPORTED. The only thing between a
    real lead and this function is a human deciding.
RISKS:
  configdiff.compare_heyreach() is called once per contact in the live
    path. This is expensive (provider reads) but correct: each authorization
    needs its own sealed Readback. If this becomes a bottleneck, the
    Readback TTL could be leveraged to reuse within the 15-minute window,
    but that would require changes to authorize() to accept pre-spent
    Readbacks, which is out of scope.
  The step_key="day3" is a LinkedIn step from cadence.STEPS. The
    authorize() copy gate checks if the step renders for this contact.
    For LinkedIn lead addition, we are not sending a specific message but
    adding a person to a campaign sequence. The copy gate may refuse if
    the contact does not have a "day3" step in their cadence. This is
    correct behaviour: if the step does not render, the contact should
    not be added.
RECOMMENDED CLAUDE ACTION:
  Review the rework. The authorization now goes through the canonical
  gate. When ready to enable the route, add LINKEDIN_ADD_LEAD to
  providerwrites.SUPPORTED and run a canary with one contact.

---

## REVIEW 1 - REJECTED 2026-09-14. Rework, do not start over.

The first attempt (`qwen-worker-2`, 47424f2) built the right shape - five
gates in order, per-contact refusals, idempotent membership read, readback
deciding the verdict, `LINKEDIN_ADD_LEAD` correctly left out of `SUPPORTED`,
16 behavioural tests. Keep all of that.

**One thing is rejected, and it is the thing the whole door rests on.**

`_mint_authorization` CONSTRUCTS the object:

    return executionguard.Authorization(
        key=key, operation=providerwrites.LINKEDIN_ADD_LEAD, ...)

`providerwrites.perform` says, in its own words, that a prospect-facing
operation "needs a real Authorization - the object, not something shaped like
one. `executionguard` is the only thing that mints one and it does so only
after every gate passes." The check it performs is `isinstance`, so a directly
constructed object passes it while having passed NO gate.

`grep -rn "Authorization(" src/` returns exactly one construction site:
`executionguard.py:658`, at the end of `authorize()`. Yours would be the
second, and the moment there are two the `isinstance` check stops meaning
anything for anybody.

Re-implementing the gates inside `ensure_leads` does not substitute for it.
Even where the two sets agree today they will drift - CLAUDE.md's "prefer
canonical state to a second representation of it" is exactly this case - and
`authorize()` runs gates your five do not, starting with `copy`, which asks
whether the step actually RENDERS for this contact before anybody is written
anywhere.

### What to do

Call it:

    executionguard.authorize(
        operation=providerwrites.LINKEDIN_ADD_LEAD, channel="linkedin",
        campaign=..., rec=..., contact=..., step_key=..., workspace=...,
        config=..., readback=..., by=...)

and use what it returns. Note `readback` is REQUIRED and is the
`(diff_result, verified_at)` pair from a provider comparison the CALLER has
already performed - read its docstring, which explains why a gate that fetches
its own evidence can be satisfied by calling it twice.

Your own gates may stay as a cheap pre-filter that refuses by name before the
expensive path, which is genuinely useful. They may not stand in for the
Authorization.

### The test that decides the rework

A test that `ensure_leads` cannot obtain an Authorization for a contact that
`executionguard.authorize` would refuse - drive it through a contact that
fails an executionguard gate your five do not check, and prove the write never
happens. If that test passes with your five gates and no `authorize()` call,
it is not testing the right thing.
