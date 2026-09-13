# RESONATE OS HANDOFF

Written 2026-09-13 after a session-limit interruption. Everything here was
read back from the repository or from a provider on that date. Nothing in
this file is inferred from a plan.

## Repository

- branch: `master`
- HEAD: `7ff5a01` "Say what was verified, not what was assumed"
- remote: `origin` https://github.com/KatoKhan8/resonate-group-automation.git
- remote HEAD: `7ff5a01` on `origin/master`. Identical to HEAD.
- last pushed commit: `7ff5a01`
- worktree: clean
- `work/` is gitignored. Queue and campaign state are NOT in git, by design.

## Canonical goal

Resonate OS is the internal multi-client outbound engine for Resonate Group.
Current production client: Productive. Resonate admins operate it; clients
receive reporting.

## Productive ICP

V2 is STRUCTURAL ONLY. Five criteria, and pain signals are not among them.

    geography          DEFINING
    company_type       DEFINING   agency / software agency
    services_business
    employees          20, with a 30% tolerance -> effective floor 14.0
    tracks_time

`ICP_PASS_WITH_UNCERTAINTY` is returned when both DEFINING criteria pass and
others are unknown. UNKNOWN is not IRRELEVANT and it is not a failure.

Time tracking, utilisation, profitability and resource planning are NOT ICP
gates. They belong to research and personalisation. Do not move them.

Current replay over 300 records, all Productive:

    icp_pass_with_uncertainty   113
    icp_fail                    121
    icp_review                   66

    record state: dropped 106, queued 99, verified 66, held 26, drafted 3
    contacts held across all records: 92

Fail reasons: employees 81, company_type 31, services_business 6, geography 3.

Known data-quality issues:

- `tracks_time` is unknown on 294 of 300. It is a criterion almost nothing
  can answer from a website. That is why it does not gate.
- `services_business` unknown on 165, `employees` unknown on 105.
- Headcount bands straddle the floor (11-50 against a floor of 14), and a
  band is not a headcount. These resolve to unknown rather than to a guess.
- Some records carry contradicting headcount sources, for example 23
  profiles at a company whose own site states 11 staff.
- 104 of 113 qualified accounts have ZERO contacts. This, not qualification,
  is the funnel bottleneck.

## EmailBison

Campaigns created during the build: 434, 441, 447, 449, 450, 451.

PROVIDER TRUTH as of 2026-09-13: **434, 441, 447, 449 and 450 now return
404.** The asynchronous DELETE issued earlier has landed. Only 451 exists.
Do not treat the older IDs as live; they are gone.

- canary: campaign **451**, canonical row `productive-canary-email-2026-09-13`,
  1 lead (Bison lead 203657), 1 scheduled email, sender 3948, schedule id 400
  reporting "Not Started". Scheduled to send Monday 2026-09-14 13:19Z
  (09:19 EDT, Toronto). SUBJECT and BODY variable rendering was PROVEN
  pre-send by reading `/scheduled-emails`.
- production 5-step campaign: **NOT CREATED.** This is the largest open gap.

Implemented AND live-verified verbs: `create_campaign`, `create_lead`,
`attach_leads`, `campaign_lead_ids`, `campaign_lead_count`, `set_sequence`,
`sequence_steps`, `set_limits`, `set_schedule`, `schedule`, `attach_senders`,
`campaign_senders`, `pause_campaign`, `resume_campaign`, `scheduled_emails`,
`membership`, `stop_lead`, `find_lead_by_email`, `lead`, `update_lead`,
`variables_of`, `ensure_custom_variables`, `find_campaigns_by_name`.

Per-lead stop: implemented and verified. `membership(352, [148932])` returns
`{148932: 'sequence_finished'}` against a 21,176-lead campaign.

Current live actions: one scheduled email on campaign 451. Nothing sent.

Blockers:

- `sender_id` is null on all 257 senders. This blocks account-level
  execution and is a business decision, not a code defect.
- Staging invalidates approval, so the order must be stage THEN approve.
  Undocumented provider behaviour; do not reorder.

## HeyReach

- **599020** RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1 - **DRAFT**,
  0 users, list 933603, seat 174892 attached, org unit 118832. Created
  2026-09-13T10:33Z. Visible in the HeyReach UI. This one is ours.
- **594061** - the earlier Productive canary, canonical row
  `productive-canary-2026-09-09`, paused.
- 50 campaigns total in the workspace; the rest are the client's own
  pre-existing work and must not be touched.

`WRITE_ROUTES` is now seven routes:

    /campaign/Pause
    /campaign/StopLeadInCampaign
    /list/CreateEmptyList
    /campaign/Create
    /campaign/UpdateSequence
    /campaign/AddLinkedInAccountsToCampaign
    /campaign/RemoveLinkedInAccountsFromCampaign

Deliberately ABSENT and asserted absent by the seals: Resume, StartCampaign,
and every AddLeadsToCampaign spelling. A campaign can be built and left in
DRAFT. It cannot be started, and no person can be put into one.

Reads wired: `/campaign/GetAll`, `/inbox/GetConversationsV2`, `/lead/GetLead`,
`/li_account/GetAll`, `/campaign/GetLeadsFromCampaign`, `/stats/GetOverallStats`,
`/list/GetAll`, `/campaign/GetCampaignsForLead`.

Blockers: Open Profile detection and InMail send are NOT established as
provider capabilities. Steps naming them are HELD by the state machine,
never silently skipped. Do not claim either works until measured.

## Live execution

- confirmed touches: 0
- scheduled actions: 1 (EmailBison 451, Monday 2026-09-14 13:19Z)
- sent actions: 0
- replies: 0
- ambiguous actions: 0
- current live rung: ONE authorized canary. `UNSTOPPABLE_CHANNEL_CAP = 1`.
- approval: the canary is approved and staged. No bulk authorization exists.
- killswitch: armed and untripped.

Campaign rows in canonical state: 9. Six are `awaiting_approval`
(three Productive, two ContactOut, one Demo Client); `productive-pilot-canary`
is draft; `productive-canary-2026-09-09` is paused; the email canary is draft.

## ABM / cadence target

`productive_li_heavy_v1` in `src/cadencelibrary.py`, selected by
`config/clients/productive.yaml` via the `cadence:` key. The shape is
asserted by test, not by hope: 5 email, 6 LinkedIn, 11 total, 21 days.

    day 1   li1 connect  + em1        day 12  em4
    day 3   li2 message               day 15  li5
    day 4   em2                       day 18  li6
    day 6   li3 message               day 21  em5
    day 8   em3
    day 10  li4

Branches: OPEN PROFILE replaces the day-1 connection request with a direct
message; CONNECTED gates every message step; CONNECTION_NOT_ACCEPTED turns
li3 into the InMail fallback. The InMail branch runs ONLY where the provider
supports it, which is currently unproven, so it is held.

Event-driven, never calendar-driven. A clock never produces evidence: time
passing is not a decline. One connection request per person per sequence,
enforced at execution time as well as at authoring time.

Account saturation, from `config/clients/productive.yaml`: contact
min_hours_between_touches 0 (a coordinated day is the point),
min_hours_between_same_channel_touches 48, max_touches_per_week 6,
max_touches_total 12; account max_active_contacts 2, max_touches_per_week 8,
min_hours_between_first_touches 72.

## Current code work

- EmailBison production hardening - **COMPLETE**. Committed `3c8cff6`.
  Paging fixed; a page is no longer read as an inventory.
- HeyReach capability/sequence - **COMPLETE**. Committed `f1fd6c0`.
  Campaign 599020 exists in DRAFT at the provider.
- cross-channel state machine - **COMPLETE**. Committed `8990225`.
  `src/linkedinstate.py`, wired into `cadence` and `nextaction`.
- LinkedIn-heavy copy and red-team - **COMPLETE**. Committed `5614f1e`.
  `step.purpose` and `already_sent` in the draft prompt.
- Productive pipeline - **COMPLETE**. Committed `4cfe0a0`. Webmail domains
  are no longer read as an employer.
- outcomes / provenance fix - **COMPLETE**. Committed `fb1557d`.
- safety-test failures: **none found.** Verified by running the 225 tests
  that cover every file touched in this session - `test_audit`,
  `test_invariants`, `test_the_stop_can_be_performed`,
  `test_the_factory_verbs_exist_and_are_sealed`,
  `test_a_refusal_is_not_a_purchase`,
  `test_two_campaigns_do_not_collide_at_the_provider`,
  `test_transport_audit` - all OK.

  The WHOLE suite was NOT observed to completion. It runs longer than the
  900-second watchdog and was killed at the limit (exit 124) on the one run
  that captured its exit code honestly. Treat "full suite green" as
  UNVERIFIED until somebody runs it without a timeout.

## P0

1. No EmailBison 5-step production campaign exists. The mission requires one
   readable in the provider UI. Nothing blocks building it.
2. `sender_id` null on all 257 EmailBison senders blocks account-level
   execution. Needs an operator decision, not code.

## P1

0. The full test suite exceeds 900 seconds and no run in this session
   observed its verdict. Three earlier runs appeared to exit 0; that was the
   exit code of `tail` at the end of the pipeline, not of unittest. Pipe
   unittest through nothing, or the verdict line is lost and the exit code
   is the filter's. Either split the suite or raise the watchdog.
1. HeyReach 599020 has no sequence and no leads. It is an empty DRAFT shell.
2. Open Profile and InMail capability unmeasured on HeyReach.
3. 104 of 113 qualified accounts have no contacts; contact discovery is the
   funnel bottleneck, not qualification.
4. Of the 9 qualified accounts WITH contacts: 6 STOP (already mid-sequence in
   the client's own campaigns 327 and 352), 1 HOLD, 2 ALLOW but only with
   catch-all or unverified addresses.

## Provider truth to re-check before ANY retry

- EmailBison 434/441/447/449/450 are **404**. Deleted. Do not retry against
  them and do not read their absence as an adapter fault.
- Campaign 451 is production evidence. Do NOT cancel, duplicate, restage or
  otherwise mutate it to test something. Re-staging pauses it.
- `per_page` is ignored; every list route returns 15 rows. Count from
  `meta.total` via `campaign_lead_count`, never from a returned list.
- `POST /campaigns` discards every field except `name`.
- The sequence route APPENDS; it does not replace.
- `GET .../schedule` and `attach-sender-emails` can answer HTTP 200 with
  `success: false`. The status code is not the verdict.
- `?email=` is not a filter; it returns an unfiltered page.
- DELETE is asynchronous.
- `custom_variables` must be a LIST of name/value objects, with the names
  declared in advance.
- HeyReach Resume and StartCampaign are DIFFERENT verbs, neither wired.
  StopLeadInCampaign is per-lead. No campaign or list DELETE exists.
- Spend to date: 699 provider calls, 962 credits against a 50,000 ceiling.

## Next 10 actions

1. Observe the Monday 2026-09-14 13:19Z canary send on campaign 451 and
   record the outcome. Do not mutate the campaign in order to observe it.
2. Build the EmailBison 5-step production campaign through `bisonfactory`,
   named on the RESONATE - PRODUCTIVE - EMAIL - GEO - PERSONA - LIHEAVY-V1
   pattern, and leave it PAUSED.
3. Read that campaign back from the provider and compare against the
   canonical expected shape: 5 steps, delays, sender pool, schedule,
   custom variables.
4. Write the HeyReach sequence onto campaign 599020 via UpdateSequence.
5. Read 599020 back and confirm the sequence matches the LinkedIn half of
   `productive_li_heavy_v1`.
6. Measure HeyReach Open Profile detection and InMail send. Report the exact
   limitation if unsupported, and build the strongest supported fallback
   rather than pretending it works.
7. Resolve `sender_id` null with the operator. Nothing at account scale runs
   until this is answered.
8. Attack the contact bottleneck: 104 qualified accounts with no contacts.
9. Stage accounts against both production campaigns, stage THEN approve.
10. Only then propose widening the live rung past one action.

## Next single best action

Build the EmailBison 5-step production campaign and read it back from the
provider. It is the largest open gap, nothing blocks it, and it does not
touch the scheduled canary.
