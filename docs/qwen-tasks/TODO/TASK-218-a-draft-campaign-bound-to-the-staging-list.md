PRIORITY: P0
DEPENDS:

# TASK-218 - a DRAFT campaign bound to the staging list, and the start verb

## WHERE THIS SITS

TASK-216 settled the architecture. The list-to-campaign bind is a FIELD on the
campaign - `linkedInUserListId` on `POST /campaign/Create` - and there is no
separate attach route. `heyreach.create_campaign(name, list_id, account_ids)`
already implements it and creates in DRAFT, and its own docstring is the safety
argument: "A DRAFT SENDS NOTHING. Activation is `/campaign/StartCampaign`,
which is not on `WRITE_ROUTES` and is not implemented here."

So binding at creation is NOT activation, and the `LINKEDIN_ADD_LEAD` reseal
never has to be touched: we never add to campaign 599020 at all.

What exists right now:

    list 940797      UNBOUND, holds ONE operator-approved contact whose
                     li1-li5 carry `operator-control-arm` approval with
                     fingerprints, profile resolves at /lead/GetLead
    campaign 599020  FINISHED, 0 leads, seat 174892. NOT to be reused.
    seat 174892      resolves, active
    LINKEDIN_SET_SEQUENCE   already in SUPPORTED
    LINKEDIN_CREATE_CAMPAIGN  NOT in SUPPORTED
    /campaign/StartCampaign   NOT on WRITE_ROUTES, NOT implemented

## THE QUESTION

Two deliverables, and the second one must not be reachable.

### 1. The DRAFT canary campaign path, wired but NOT enabled

1. **Define the permission for creation.** `LINKEDIN_CREATE_CAMPAIGN` exists as
   a constant and is not in `SUPPORTED`. Write its `CONDITIONAL` predicate in
   the style of `_list_is_unbound_right_now` and
   `_campaign_is_ours_and_holds_nobody`: it must assert, from a provider read
   at the moment of the write, that the list it is about to bind is OURS, in
   OUR tenant, and currently holds only approved leads. **Leave it OUT of
   `SUPPORTED`** - enabling is the operator's, and say so in the entry.
2. **Is creation prospect-facing?** Argue it from the provider rather than
   asserting it. A DRAFT cannot send, so the answer is probably no - but
   binding a list to a campaign is the moment the list stops being unbound,
   which ends the safety property every staged lead depends on. Say what that
   costs and what would detect it.
3. **The readback.** After creation, what proves the campaign is DRAFT, bound
   to the intended list, carrying the intended seat, and holding exactly the
   leads that list holds? Write it. `addedLeadsCount`-style self-reports are
   not readbacks on this provider - TASK-158 measured twelve shapes returning
   0/0/0 with HTTP 200.
4. **The sequence.** 599020 carries 17 nodes with merge variables and the words
   arrive per lead. The new campaign needs the same sequence via the already
   supported `LINKEDIN_SET_SEQUENCE`. Establish whether the 17-node shape can
   be read off 599020 and written to a new campaign, and whether its readback
   hash (`32f8dde79bfa0f27` for 599020) is reproducible.

### 2. The start verb, implemented and sealed

5. **Implement `/campaign/StartCampaign`** in `src/providers/heyreach.py` in
   the shape `resume_campaign` has on the Bison side: it must take an
   `expect_leads` containment argument and refuse if the provider disagrees,
   and it must CLASSIFY the provider's answer rather than trust a 200 - a
   status that is still unknown when polling runs out raises rather than
   reporting success. Add the route to `WRITE_ROUTES`.
6. **`LINKEDIN_ACTIVATE` stays OUT of `SUPPORTED`.** Wire it so that calling it
   fails closed, loudly, naming the missing permission, and add the test that
   proves the OFF switch refuses. That test is the deliverable that matters
   most in this half.

## THE TRAP

You are implementing the verb that makes a LinkedIn campaign send. The whole
value of doing it now is that it is ready and refused, so the operator's
decision is one line rather than a day of engineering. **A start verb that is
reachable without a permission is worse than no start verb**, because
everything else in the path looks finished.

Second trap: `heyreach.pause` is already supported, so the stop side exists -
the stated condition for ever enabling activation ("a system that can start an
outreach campaign before it can reliably stop one has bought trouble") is met.
Do not treat that as permission. It removes an objection; it does not grant.

## WHAT YOU MAY NOT DO

- **No provider writes.** No campaign creation, no bind, no sequence write, no
  start, no lead add. Reads are expected. Test against fakes.
- Do not add `LINKEDIN_CREATE_CAMPAIGN` or `LINKEDIN_ACTIVATE` to `SUPPORTED`.
- Do not change `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` or
  `_campaign_is_a_declared_staging_campaign`.
- Do not touch list 940797, list 933603 or campaign 599020.
- Never commit a profile URL, a prospect name or a domain.

## FILES ALLOWED

    src/providers/heyreach.py   (StartCampaign + WRITE_ROUTES)
    src/providerwrites.py   (the CONDITIONAL predicates only - NOT SUPPORTED)
    src/heyreachfactory.py
    tests/test_heyreach_start_is_sealed.py   (new)
    tests/test_draft_campaign_bind.py   (new)
    docs/HEYREACH-DRAFT-CANARY-2026-09-16.md   (new)

## FILES FORBIDDEN

    work/   config/

## DELIVERABLE

The creation permission defined with its condition and left OFF; the
prospect-facing argument made from the provider; the creation readback; the
sequence-reproduction answer; `StartCampaign` implemented with containment and
answer classification; and the test proving activation refuses while
`LINKEDIN_ACTIVATE` is not in `SUPPORTED`.
