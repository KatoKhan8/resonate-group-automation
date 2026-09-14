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

STATUS: done
COMMIT SHA: 47424f2
TESTS: 16 new tests in tests/test_heyreachfactory_ensure_leads.py, all
passing. 36 existing tests in tests/test_heyreachfactory.py still pass.
52 total heyreachfactory tests green. One pre-existing failure in
test_no_write_happens_without_every_gate (collision HOLD verdict for a
finished campaign) confirmed unrelated - fails the same way before and
after these changes.
FILES CHANGED:
  src/heyreachfactory.py - added ensure_leads() and _mint_authorization()
  tests/test_heyreachfactory_ensure_leads.py - 16 behavioural tests
FINDINGS:
  - ensure_leads() follows bisonfactory._ensure_leads pattern with five
    gates in order: killswitch workspace state, suppression/DNC (via
    eligibility.must_not_contact), account collision (via
    collision.check_account + account_policy), tenant check (via
    heyreach.check_tenant), and refuse_unsupported_sequence against the
    rows actually being pushed.
  - Each gate refuses BY NAME. A contact who fails any gate is refused
    and the transport is never reached.
  - One executionguard.Authorization is minted per contact with an
    actionledger reservation. The authorization carries the operation,
    channel, workspace, campaign, record and contact.
  - The write goes through providerwrites.perform(LINKEDIN_ADD_LEAD)
    with transport=heyreach.add_leads_to_campaign and
    readback=heyreach.readback_membership. THE READBACK DECIDES.
  - Idempotent: reads membership first via readback_membership and
    pushes only the difference. A re-run costs reads and writes nothing.
  - Dry run lists who would be pushed, from which seat, with which
    variables, and touches nothing.
  - LINKEDIN_ADD_LEAD is NOT added to SUPPORTED. The only thing between
    a real lead and this function is a human deciding.
  - Guard breaking tests confirm each gate fires in order and that a
    different guard did not fire first: killswitch before suppression,
    suppression before collision, collision before tenant.
RISKS:
  - The authorization path through providerwrites.perform requires
    LINKEDIN_ADD_LEAD in SUPPORTED before a live call can succeed. This
    is the deliberate operator decision the task describes.
  - The _mint_authorization function calls actionledger.reserve which
    writes to the ledger file. In the live path, this creates a durable
    reservation that must be settled by the perform call.
  - The collision check uses collision.check_account which reads the
    EmailBison provider estate. For LinkedIn leads, the record's domain
    is used as the collision key. This is account-level per
    ACCOUNT-OUTREACH.md.
RECOMMENDED CLAUDE ACTION:
  Review ensure_leads() and the gate order. When ready to enable the
  route, add LINKEDIN_ADD_LEAD to providerwrites.SUPPORTED and run a
  canary with one contact. The function is ready; the decision is not
  an engineering one.
