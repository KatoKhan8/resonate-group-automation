#!/usr/bin/env python3
"""The permission layer for provider writes, and NOT the complete write surface.

TASK-198 (2026-09-16): this module is described elsewhere as "the single door"
and `SUPPORTED` as the answer to "what can this system write". Neither is
true. `bisonfactory` calls eight provider write functions directly, bypassing
`perform`: `set_limits`, `set_schedule`, `attach_senders`,
`ensure_custom_variables`, `create_lead`, `attach_leads`, `update_lead`, and
`pause_campaign`. Those calls carry their own gates (killswitch, collision
check, approval, pre-attach status re-read) that were added after measured
incidents, but they are not enumerated here and `SUPPORTED` does not name
them. `heyreachfactory` routes every write through `perform`; the gap is
EmailBison-only. Read `docs/TWO-DOORS-2026-09-16.md` for the full enumeration
of both doors and the recommendation.

Adding a verb to `SUPPORTED` is an operator authorization and is not this
module's alone to decide. What this module DOES enforce for every call that
passes through it: the operation is declared, the authorization is genuine,
the conditional permission holds, the idempotency check passes, and the
readback is compared. The factory's own gates are a separate layer and are
not weakened by this module's existence.

WHY THIS SHIPS WITH EVERY ALLOWLIST EMPTY.

`push.run(live=True)` raises, `tagsync.send` refuses unconditionally, and
`heyreach._read` rejects any route outside its read allowlist. Sending is
BLOCKING by construction rather than by a flag, which is the property
LIVE-READINESS.md promises and the one thing in this repository that has never
been wrong. Adding a write capability is therefore not a feature; it is the
removal of the only guarantee that has held.

So the machine was built first and given nothing to drive. `OPERATIONS`
declares what a write would need. The brakes - authorization, idempotency,
mandatory read-back, failure classification - were in place and tested before
any route was enabled, and they are still the only path through.

`SUPPORTED` IS NO LONGER EMPTY. Read the tuple, not this paragraph. As of
2026-09-15 six routes are enabled:

  heyreach.pause          bison.pause           bison.stop_lead
  heyreach.set_sequence   bison.create_campaign bison.set_sequence

This docstring said "`SUPPORTED` is empty. Every attempt refuses." for long
enough that it was quoted as current on 2026-09-15 while two sequence-write
routes were live - one of which had already written the sequence of HeyReach
campaign 599020. A document about the environment that is believed without
checking is how somebody reasons correctly to a wrong conclusion, and it cost
a whole Qwen task the night before when `QWEN.md` told a worker it had no
credentials while it held all three.

`LINKEDIN_ADD_LEAD` joined them on 2026-09-15 and is the first prospect-facing
route ever enabled here. It is enabled CONDITIONALLY: `SUPPORTED` is necessary
and not sufficient, and `perform` additionally runs the predicate in
`CONDITIONAL`, which re-reads the destination campaign from the provider and
admits only a campaign proven unable to send. Read `CONDITIONAL` for why the
tuple could not carry that on its own.

Still NOT supported, and each needs its own review before it is: adding leads
on EmailBison, creating a HeyReach campaign or list, assigning a sender,
configuring limits, and activating or unpausing anything. `LINKEDIN_ACTIVATE`
is the one to be most deliberate about: it is the verb that turns a campaign
full of staged leads into messages, and enabling add-lead is not an argument
for enabling it.

WHAT IS AND IS NOT AN ESTABLISHED CONTRACT.

An endpoint counts as established only when the provider documented it, or the
existing code already carries its confirmed shape, or a real response has been
read. Guessing a write path against a live client estate is how somebody
discovers a route by mutating production, so anything unestablished is declared
`UNSUPPORTED` with the reason, rather than attempted hopefully.

  HeyReach   /campaign/AddLeadsToCampaignV2   URL known, shape NOT validated
             create campaign                  no documented route
             create list                      no documented route
             configure sequence               no documented route
             assign sender                    no documented route
             configure limits                 no documented route
             pause / activate                 no documented route
  EmailBison /campaigns/{id}/leads            URL known, shape NOT validated
             create campaign                  no documented route
             configure sequence               no documented route
             pause / activate                 no documented route

Every one of those was probed read-only or is named in the provider modules;
none has had a successful write response read back. So `SUPPORTED` stays empty
until each is separately established, reviewed and tested - one route per
change, never a batch.

THE ONE RULE THAT MATTERS MOST.

After a write, READ BACK BEFORE DECIDING ANYTHING. Never retry because the
client did not receive a response: a timeout says nothing about whether the
provider acted, and `actionledger` refuses a retry until provider truth settles
the reservation. That rule is enforced here rather than documented here.
"""
import json
import sys

from . import actionledger, events, executionguard, store

# ------------------------------------------------------------- operations

# What each operation is, and whether it can reach a prospect. The flag is not
# decoration: `PROSPECT_FACING` operations additionally require a full
# `Authorization`, and non-prospect-facing staging does not - which is the
# distinction that lets configuration be built and verified without any risk of
# contacting somebody.
LINKEDIN_ADD_LEAD = "heyreach.add_lead"
LINKEDIN_CREATE_LIST = "heyreach.create_list"
LINKEDIN_CREATE_CAMPAIGN = "heyreach.create_campaign"
LINKEDIN_SET_SEQUENCE = "heyreach.set_sequence"
LINKEDIN_ASSIGN_SENDER = "heyreach.assign_sender"
LINKEDIN_SET_LIMITS = "heyreach.set_limits"
LINKEDIN_PAUSE = "heyreach.pause"
LINKEDIN_ACTIVATE = "heyreach.activate"
# Starting a campaign that holds NOBODY, so that it can be paused and staged
# into. Deliberately NOT `LINKEDIN_ACTIVATE`: that one starts a campaign
# holding people, and it stays sealed.
LINKEDIN_START_EMPTY_FOR_STAGING = "heyreach.start_empty_for_staging"
# Adding a lead to a LIST, not a campaign. TASK-158 proved the route works,
# TASK-165 designed the path, and neither could name the permission because
# it did not exist. Defined here with the other constants; the predicate
# lives in `liststaging` because the write layer this module owns does not
# yet carry this verb. NOT in SUPPORTED, NOT in CONDITIONAL - enabling is
# an operator decision and this task does not have it.
LINKEDIN_ADD_LEAD_TO_LIST = "heyreach.add_lead_to_list"

EMAIL_ADD_LEAD = "bison.add_lead"
EMAIL_CREATE_CAMPAIGN = "bison.create_campaign"
EMAIL_SET_SEQUENCE = "bison.set_sequence"
EMAIL_ASSIGN_SENDER = "bison.assign_sender"
EMAIL_SET_LIMITS = "bison.set_limits"
EMAIL_PAUSE = "bison.pause"
EMAIL_STOP_LEAD = "bison.stop_lead"
EMAIL_ACTIVATE = "bison.activate"

OPERATIONS = {
    # operation: (channel, prospect_facing, why it is not supported yet)
    LINKEDIN_ADD_LEAD: ("linkedin", True,
        "SUPPORTED as of 2026-09-15, CONDITIONALLY, and it is the first "
        "prospect-facing route this system has ever allowed. It is in "
        "SUPPORTED *and* in CONDITIONAL, and the second is the real "
        "permission: `perform` refuses unless a provider read taken at the "
        "moment of the write proves the destination campaign cannot send. "
        "Only DRAFT proves that. PAUSED does not - a human can resume it and "
        "the lead is then sent to. FINISHED does not - it describes the "
        "leads the campaign already held, not one added afterwards. An "
        "unreadable campaign, an absent status and an unrecognised status "
        "all refuse. "
        "This entry previously read 'no successful response has "
        "ever been read', and that is STILL TRUE of the response body: the "
        "shape of AddLeadsToCampaignV2's reply is unknown and is not what "
        "settles the verdict. The READBACK settles it - "
        "/campaign/GetLeadsFromCampaign, verified live against campaign "
        "565765 paging 1000 leads with leadCampaignStatus, "
        "leadConnectionStatus and errorCode per lead. A 200 is not a lead; a "
        "membership read that finds the asked-for profile is. "
        "Adding a lead to a RUNNING campaign is prospect-facing "
        "because the sequence acts on it immediately - which is precisely "
        "the state the condition exists to exclude"),
    LINKEDIN_START_EMPTY_FOR_STAGING: ("linkedin", False,
        "SUPPORTED as of 2026-09-15, and it exists because the provider "
        "leaves no other route to a stageable campaign. Measured: "
        "AddLeadsToCampaignV2 answers 400 'You cannot add new leads to a "
        "draft campaign', and /campaign/Pause answers 400 'You cannot pause "
        "an inactive campaign'. Only ongoing, paused and finished campaigns "
        "accept leads, so DRAFT -> PAUSED is not a transition this vendor "
        "has. Start then pause is the only one. "
        "NOT PROSPECT-FACING, AND THE LEAD COUNT IS WHY: this starts a "
        "campaign the provider says holds ZERO leads, read immediately "
        "before the write and refused otherwise, so there is nobody for the "
        "sequence to act on and nothing is sent. It is the argument that "
        "licensed writing a sequence onto an empty campaign, applied to the "
        "verb rather than to the copy. "
        "IT IS NOT LINKEDIN_ACTIVATE AND MUST NEVER BECOME IT. Starting a "
        "campaign that HOLDS PEOPLE is the prospect-facing moment and is a "
        "separate operation, still sealed, carrying no condition. The two are "
        "the same route told apart by a number the provider supplies. "
        "Reversible: /campaign/Pause is live-validated and SUPPORTED, so a "
        "campaign started here can be stopped by this system - which is the "
        "condition the seals set before any start verb could be added"),
    LINKEDIN_ADD_LEAD_TO_LIST: ("linkedin", False,
        "DEFINED BUT NOT ENABLED. TASK-172. Adding a lead to a LIST rather "
        "than a campaign - the route TASK-158 proved works and TASK-165 "
        "designed, for which no permission existed until this constant. "
        "Not prospect-facing: a list attached to no campaign reaches "
        "nobody, and the condition refuses the write the moment the list "
        "is attached to one. The predicate is `liststaging.assert_list_safe`: "
        "it reads the list from the provider at the moment of the write and "
        "refuses unless `campaignIds` is empty. NOT in SUPPORTED, NOT in "
        "CONDITIONAL - enabling is an operator decision and this task does "
        "not have it. "
        "Schema enforcement: `profileUrl`, `firstName` (required), "
        "`lastName` (required) are validated by `liststaging.validate_lead_row` "
        "before the transport is touched. The provider returns "
        "`addedLeadsCount: 0` with no error for a lead missing either name "
        "- a 200 that is not a success - so validation is local and "
        "pre-transport. "
        "What the condition cannot promise: a list unbound at the moment of "
        "the write can be attached to a campaign a second later by anyone "
        "with provider access. The predicate is a point-in-time check, not "
        "a lock. Detection after the fact: `liststaging.readback_list_add` "
        "re-reads the list after every write and classifies DRIFTED if "
        "`campaignIds` is no longer empty. "
        "The silent-drop response (`addedLeadsCount: 0, totalLeads: 0, "
        "duplicateLeads: 0`) is treated as failure by the readback: the "
        "lead is not found in the list, so the verdict is UNKNOWN and "
        "`stage_lead` raises `ListStagingUnverified`"),
    LINKEDIN_CREATE_LIST: ("linkedin", False,
        "no documented route; the list was created by hand in the vendor UI"),
    LINKEDIN_CREATE_CAMPAIGN: ("linkedin", False,
        "no documented route; POST /campaign/GetById already answers 405 and "
        "nothing suggests a create verb exists on the public API"),
    LINKEDIN_SET_SEQUENCE: ("linkedin", False,
        "SUPPORTED as of 2026-09-14. This said 'no documented route ... a "
        "write would be verifiable the moment a verb is established', and the "
        "verb IS established: `/campaign/UpdateSequence` is on "
        "`heyreach.WRITE_ROUTES` and campaign 599020 carries a sequence that "
        "was written through it. The condition this entry set for itself has "
        "been met.\n"
        "        Not prospect-facing, and that is what makes it safe to "
        "enable ahead of the rest: a sequence written onto a campaign holding "
        "nobody reaches nobody. 599020 has no list, no leads, and there is no "
        "wired verb that can start it - Resume and StartCampaign are "
        "deliberately absent and asserted absent by the seals.\n"
        "        `UpdateSequence` REPLACES the whole graph rather than "
        "appending, established from the adapter rather than assumed, which "
        "is the opposite of EmailBison's sequence route and is why writing "
        "this one twice is safe where writing that one twice is not."),
    LINKEDIN_ASSIGN_SENDER: ("linkedin", False,
        "STILL NOT IN SUPPORTED, AND THIS ENTRY WAS STALE. It read 'no "
        "documented route ... assignment was done by hand', and TASK-144 "
        "found that false: `/campaign/AddLinkedInAccountsToCampaign` and "
        "`/campaign/RemoveLinkedInAccountsFromCampaign` are BOTH on "
        "`heyreach.WRITE_ROUTES` and both have implementations - "
        "`heyreach.add_senders` and `heyreach.remove_senders`. The route is "
        "not the obstacle and has not been for some time.\n"
        "        This repository has been bitten twice by a paragraph about "
        "the environment that was believed without checking - once here, "
        "where this module's own docstring said SUPPORTED was empty while "
        "two sequence-write routes were live, and once in QWEN.md, where a "
        "worker was told it had no credentials while holding all three. So "
        "the correction is recorded rather than the sentence quietly "
        "deleted.\n"
        "        What keeps it out of SUPPORTED is a different question now: "
        "nothing needs it. TASK-144 measured the estate - 33 healthy seats, "
        "all 33 already carrying IN_PROGRESS campaigns, zero uncommitted - "
        "and one seat at 40 connection requests a day clears a 50-lead "
        "cohort in 1.25 working days. The cadence's own 1-3 day delays "
        "dominate the elapsed time, so a second sender does not make the "
        "first campaign faster; it adds load to a seat already serving the "
        "client's own active campaigns. Enable this when a cohort is "
        "genuinely larger than one seat's ceiling, not before, and read "
        "docs/SENDER-UTILISATION-2026-09-15.md for the arithmetic"),
    LINKEDIN_SET_LIMITS: ("linkedin", False,
        "no documented route, and no read route exposes a per-campaign limit "
        "either, so a write could not be verified even if it existed"),
    LINKEDIN_PAUSE: ("linkedin", False,
        "SUPPORTED. POST /campaign/Pause?campaignId=, established by probe on "
        "2026-09-10: an empty body answers 400 there and 404 at "
        "/campaign/PauseCampaign. Not prospect-facing - nothing is sent, and "
        "leads in progress keep their state. This was the most uncomfortable "
        "gap in this table, because until it existed the killswitch could "
        "refuse to start a campaign and could not end one"),
    LINKEDIN_ACTIVATE: ("linkedin", True,
        "the route EXISTS - POST /campaign/Resume and /campaign/StartCampaign "
        "both answer 400 to an empty body - and it is deliberately not "
        "supported yet. Activation is prospect-facing by definition, and the "
        "order matters: a system that can start an outreach campaign before "
        "it can reliably stop one has bought exposure it cannot end"),
    EMAIL_ADD_LEAD: ("email", True,
        "SUPPORTED, AND IT IS A TWO-STEP. An earlier entry here claimed "
        "campaign population was a human action in the vendor UI. That was "
        "WRONG: it probed guessed paths and read its own failure to guess as "
        "provider absence. POST /api/campaigns/{id}/leads is indeed a 405, "
        "but that is the READ route - the write is POST "
        "/api/campaigns/{id}/leads/attach-leads with {'lead_ids': [...]}, "
        "which answered 200 on 2026-09-12 and put both leads in the campaign "
        "with lead_campaign_data status `in_sequence` on readback. So a lead "
        "is CREATED by POST /api/leads and then ATTACHED. The provider is "
        "idempotent on the attach in its own words - 'Existing leads were not "
        "added' - and `bison.attach_leads` reads membership before and after "
        "rather than trusting either that sentence or the status code. "
        "Prospect-facing because attaching to a RUNNING campaign is acted on "
        "immediately. Note for the caller: the attach payload carries only "
        "ids, never words. The copy reaches the prospect through the lead's "
        "custom_variables and the sequence, so the payload that must be bound "
        "to the approval is the lead-create one"),
    EMAIL_CREATE_CAMPAIGN: ("email", False,
        "SUPPORTED. POST /api/campaigns answered 201 on 2026-09-12 and "
        "returned a DRAFT campaign, which DELETE /api/campaigns/{id} then "
        "removed. A campaign is created in `draft` and sends nothing until it "
        "is resumed, so this is not prospect-facing. It was held back on the "
        "belief that a campaign created here could never be populated; that "
        "belief was false - see EMAIL_ADD_LEAD"),
    EMAIL_SET_SEQUENCE: ("email", False,
        "SUPPORTED. POST /api/campaigns/{id}/sequence-steps answered 201 on "
        "2026-09-12. The body is the part worth writing down, because the "
        "obvious one fails: a flat step is refused, and the provider requires "
        "`title` AND a NESTED `sequence_steps` array - an empty body answers "
        "422 naming both. Not prospect-facing on its own: a sequence on a "
        "draft campaign sends nothing until that campaign is resumed"),
    EMAIL_ASSIGN_SENDER: ("email", False,
        "no documented route. /campaigns/{id}/sender-emails reads the set and "
        "pages properly, so a write would be verifiable"),
    EMAIL_SET_LIMITS: ("email", False,
        "the three limit fields are readable on the campaign object; no write "
        "verb is established"),
    EMAIL_STOP_LEAD: ("email", False,
        "SUPPORTED, AND IT IS THE ONE THIS SYSTEM'S SAFETY ARGUMENT NEEDED. "
        "POST /api/campaigns/{id}/leads/stop-future-emails with "
        "{'lead_ids': [...]}. Measured twice independently on 2026-09-13: on "
        "a campaign holding two leads this system created, stopping one moved "
        "it from `in_sequence` to `stopped` in about two seconds while the "
        "sibling stayed `in_sequence` and the campaign's own status never "
        "changed. So after a reply, an unsubscribe, a suppression or an "
        "account stop, the NEXT email to THAT person can be prevented without "
        "touching anybody else. "
        "Not prospect-facing: it can only ever reduce what somebody receives. "
        "THE STATUS CODE IS NOT THE PROOF - this route answers 200 for a lead "
        "that is not in the campaign and does nothing, so `bison.stop_lead` "
        "refuses an absent lead up front, polls the provider's own "
        "`lead_campaign_data` until the stop lands, and raises if it never "
        "does. It also fails if any OTHER member's status moved, because a "
        "per-lead stop that was not per-lead is not the verb we think we "
        "have. Two useful properties measured alongside: a stopped membership "
        "cannot be restarted by re-attaching the same campaign (422), so a "
        "stop cannot be silently undone by a routine re-stage; and a lead "
        "that is `in_sequence` anywhere cannot be attached elsewhere (422)"),
    EMAIL_PAUSE: ("email", False,
        "SUPPORTED, AT CAMPAIGN GRANULARITY - AND NO LONGER THE ONLY STOP. "
        "An earlier version of this entry said stopping one person meant "
        "pausing their whole campaign, and made campaign shard size a safety "
        "parameter on the strength of it. That was wrong: see "
        "EMAIL_STOP_LEAD, which stops exactly one person. This remains the "
        "blunt instrument for stopping EVERYBODY in a campaign at once, which "
        "is a different and still necessary thing. PATCH "
        "/api/campaigns/{id}/pause answered 200 on 2026-09-12 and the "
        "campaign read back as `paused`. `bison.pause_campaign` performs that "
        "readback and raises unless the provider itself says `paused`, so a "
        "local row can never claim PAUSED while EmailBison is still sending. "
        "Resume is symmetric and refuses an incomplete campaign in the "
        "provider's own words. "
        "PATCH /api/leads/{id}/unsubscribe remains useless as a stop - 422, "
        "'This lead has not been sent any emails yet', even for an ATTACHED "
        "lead, and irreversible besides. It was the only per-lead verb found "
        "by GUESSING at routes, and guessing is what produced two wrong "
        "conclusions in a row here. The real one was documented all along"),
    EMAIL_ACTIVATE: ("email", True,
        "THE CONTRACT IS ESTABLISHED. WHAT IS MISSING IS PERMISSION, AND "
        "THOSE ARE DIFFERENT REFUSALS. This entry read 'no documented route' "
        "until 2026-09-14, which was false and false in the expensive "
        "direction: it sent a reader looking for a route that has existed "
        "since 2026-09-13. `PATCH /api/campaigns/{id}/resume` answered 200 "
        "TWICE that day, `/campaigns/{campaign_id}/resume` is on "
        "`bison.WRITE_ROUTES`, and `bison.resume_campaign` carries the full "
        "brake set - an `expect_leads` count read from `meta.total` that "
        "refuses when the provider disagrees, `queued` polled out rather than "
        "reported as started, and `failed` classified rather than defaulted. "
        "So this module's own test of an established endpoint - 'a real "
        "response has been read' - is MET. "
        "It stays out of `SUPPORTED` for the only reason that matters: it is "
        "prospect-facing, and it is the single verb on this provider that "
        "makes a staged sequence start emailing real people. Nothing has been "
        "sent by this system yet - confirmed touches are zero - so enabling "
        "it would make the first real send a batch rather than a canary. "
        "That is an operator's decision and it is not an engineering one. "
        "WHAT ENABLING IT WOULD TAKE, stated so the decision is one line "
        "rather than an investigation: add EMAIL_ACTIVATE here, then call "
        "`bison.resume_campaign(481, expect_leads=N)` with N read from the "
        "provider first - 481 holds 23 leads of which 14 are deliberately "
        "`stopped`, and passing the wrong count is how a campaign meant for "
        "nine reaches twenty-three. A smaller first rung needs no code change "
        "at all: `bison.set_limits(481, name, emails_per_day=1)` paces it to "
        "one person a day"),
}

# LINKEDIN_PAUSE IS LIVE-VALIDATED. Every other operation is not.
#
# This was empty, and the note here set the exact condition for changing it:
# "one successful pause, read back as PAUSED from provider truth. Then this
# becomes `(LINKEDIN_PAUSE,)` and the stoppability cap lifts because the stop
# demonstrably exists - which is the order that makes the gate mean
# something." The condition was set deliberately high because
# `executionguard`'s `stoppability` gate reads `is_supported(pause_operation)`
# and LIFTS its one-contact cap on the answer, so this line is a promotion
# ceiling and not merely a permission.
#
# It is met, on 2026-09-12, against HeyReach campaign 594061:
#
#   POST /campaign/Pause          -> 200
#   GET  /campaign/GetById        -> status IN_PROGRESS became PAUSED
#   connectionsSent               -> 0 before and 0 after; nothing was sent
#   lead 304173736                -> request_pending before and after
#   canonical campaign state      -> recorded through `orchestrator.pause`
#   configdiff.compare_heyreach   -> PASS, 13 fields match, 1 unverifiable
#   four-way reconciliation       -> provider = canonical = ledger = touches
#
# The earlier attempt on 2026-09-10 returned a non-2xx and the write layer
# classified it UNVERIFIED, which is why this stayed empty for two days. The
# difference is a successful response that was read back, not a better
# argument about the same code.
#
# What this does NOT license: every other entry in OPERATIONS still says no
# successful response has ever been read, and each stays refused by name. A
# fixture is never a live-validated integration, and one live-validated verb
# does not validate its neighbours.
SUPPORTED = (LINKEDIN_PAUSE, EMAIL_PAUSE, EMAIL_STOP_LEAD,
             EMAIL_CREATE_CAMPAIGN, EMAIL_SET_SEQUENCE,
             # Enabled 2026-09-14. Not prospect-facing: a sequence written
             # onto a campaign holding nobody reaches nobody, and no wired
             # verb can start that campaign. See the entry above for the
             # condition it had set for itself and how it was met.
             LINKEDIN_SET_SEQUENCE,
             # Enabled 2026-09-15, TASK-137, AND IT IS THE FIRST
             # PROSPECT-FACING ROUTE THIS SYSTEM HAS EVER ALLOWED.
             # Membership of this tuple is NOT sufficient for it: see
             # CONDITIONAL below. `perform` additionally demands that the
             # destination campaign be proven, by a provider read taken at
             # the moment of the write, to be unable to send.
             LINKEDIN_ADD_LEAD,
             # Enabled 2026-09-15. NOT prospect-facing: it starts a campaign
             # the provider says holds zero leads, so it sends nothing, and
             # its condition refuses it for a campaign holding anyone at all.
             LINKEDIN_START_EMPTY_FOR_STAGING,
             # Enabled 2026-09-16 by written operator authorization - see
             # OPERATOR-AUTHORIZATION-2026-09-16.md, which records the grant
             # so it survives a context reset and need not be asked again.
             #
             # NOT prospect-facing, and the reason is a property of the LIST
             # rather than of us: a list attached to no campaign reaches
             # nobody, whatever is added to it. `assert_list_safe` reads the
             # list FROM THE PROVIDER at the moment of the write and refuses
             # unless `campaignIds` is empty. Campaign 599020 already has list
             # 933603 attached, so "a list we created" was never the safety
             # property - "attached to nothing, checked now" is.
             #
             # THIS DOES NOT UNSEAL THE CAMPAIGN ROUTE.
             # `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` stays False and
             # LINKEDIN_ADD_LEAD stays refused on the first line of its own
             # condition. Adding a lead to a HeyReach CAMPAIGN activates that
             # campaign - PAUSED and FINISHED both - and that is still the
             # prospect-facing moment. The operator's grant was specific:
             # "Do NOT interpret this as permission to bypass gates or
             # activate arbitrary campaigns."
             LINKEDIN_ADD_LEAD_TO_LIST,
             # Enabled 2026-09-16 by written operator authorization, SCOPED TO
             # ONE CAMPAIGN. See OPERATOR-AUTHORIZATION-2026-09-16.md.
             #
             # EMAIL_ACTIVATE IS PROSPECT-FACING AND IT IS THE FIRST VERB IN
             # THIS SYSTEM THAT MAKES A CAMPAIGN SEND. The grant names
             # campaign 485, sender 2736, the existing 10 approved contacts,
             # the existing approved 3-step CONTROL, and a 20/day cap - and
             # says in terms that it is not authorization to activate other
             # campaigns, change copy, add unapproved contacts or raise a cap.
             #
             # So both carry a CONDITIONAL that refuses any campaign but 485.
             # Membership of this tuple would otherwise be a channel-wide
             # licence, and the operator did not grant one.
             EMAIL_ASSIGN_SENDER,
             EMAIL_ACTIVATE)

# ------------------------------------------- conditional permission
#
# A SECOND KEY FOR THE ONE DOOR THAT REACHES A PERSON.
#
# `SUPPORTED` answers "is there a provider contract for this verb". That is
# the only question it has ever had to answer, because until now no verb in
# it could reach a prospect: a pause reduces what somebody receives, a
# sequence written onto an empty campaign reaches nobody.
#
# `LINKEDIN_ADD_LEAD` is different in kind. Adding a lead to a campaign that
# is RUNNING is a send - the sequence acts on the lead immediately - and
# adding the same lead to a campaign that is DRAFT is staging that reaches
# nobody. The verb is identical; only the destination's state decides which
# of those two things happens. A permission expressed as tuple membership
# cannot express that, so it is not expressed that way.
#
# Each entry is a predicate that must return True, and is given the PROVIDER
# campaign id. It runs inside `perform`, before the transport is touched,
# and it may not be satisfied from local state: the campaign row we planned
# against was read minutes ago and a human can press Start in the vendor UI
# in between. It re-reads the provider.
#
# It FAILS CLOSED in every direction that is not an explicit proof of
# safety: an unreadable campaign, an absent status, a status outside the
# known set, an exception of any kind, or a missing provider campaign id all
# refuse.
#
# IT USED TO ADMIT DRAFT AND ONLY DRAFT, AND THE PROVIDER REFUSES DRAFT.
#
# Measured 2026-09-15 by an actual write against campaign 599020:
#
#     POST /campaign/AddLeadsToCampaignV2 -> 400
#     "You cannot add new leads to a draft campaign."
#
# So the one state this condition admitted is the one state HeyReach will not
# accept a lead into. The condition was not strict, it was UNSATISFIABLE, and
# the route it guards could never have been used. That is recorded in
# docs/DRAFT-CANNOT-TAKE-LEADS-2026-09-15.md.
#
# WHAT REPLACED IT IS NOT "PAUSED IS FINE".
#
# The obvious repair - add PAUSED to `_STATUSES_THAT_CANNOT_SEND` - would be
# wrong and is deliberately not what happened. `campaign_cannot_send` is
# UNCHANGED and still means exactly what it says: DRAFT, and nothing else,
# cannot send. A paused campaign CAN send, the moment somebody resumes it, and
# that remains true of every paused campaign in the client's account.
#
# The permission is narrower than a status. It is:
#
#     this exact campaign, bound in OUR canonical state, declared by THIS
#     deployment as a staging campaign, and PAUSED right now at the provider
#
# A paused campaign nobody declared, or one bound to a different provider id,
# or one this deployment did not stage, is refused - which is most of the 83
# campaigns in that account, including every campaign the client runs
# themselves.
#
# The declaration is what carries ownership, and it cannot be asserted by a
# caller: this predicate READS the canonical row itself rather than taking a
# flag. `scripts/declare_campaign_shape.py` writes that declaration from a
# provider readback, refuses a campaign it cannot prove, records who ran it,
# and moves the campaign fingerprint so an approval taken before the
# declaration cannot be inherited through it.
CONDITIONAL = {}


# IS THERE A CAMPAIGN STATE THAT ACCEPTS A LEAD WITHOUT SENDING TO IT?
#
# NO, AND THE PROVIDER SAYS SO. This was False in every direction the code
# could reach and the argument for PAUSED rested on a premise that is simply
# wrong:
#
#   "Even if the campaign is paused, adding leads via API or integration
#    directly into that campaign will activate the campaign."
#   "Finished campaigns - as soon as new leads are added campaign will get
#    activated."
#   https://help.heyreach.io/en/articles/11657798-how-to-add-leads-to-campaigns
#
# So `LINKEDIN_ADD_LEAD` against a campaign is not staging. It is the
# prospect-facing moment, and the permission below - which admits a PAUSED
# campaign on the grounds that a paused campaign does not send - would cause
# the send it was written to prevent.
#
# The invariant is RESEALED rather than quietly corrected, because a
# permission whose safety argument has been falsified must stop admitting
# things before anybody decides what replaces it. Every other check below is
# left standing and still runs: when a route to safe staging is established -
# a list, or add-lead carrying the full activation evidence - this flips with
# the reason recorded beside it, and the ownership and binding proofs are
# already here.
CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False


def _campaign_is_a_declared_staging_campaign(provider_campaign_id,
                                             campaign_id=None):
    """True only for OUR staging campaign, PAUSED, read live, right now.

    Raises `WriteRefused` otherwise - including, and especially, when it
    cannot tell. Every branch below is a refusal except the last line.
    """
    from . import campaigns as _campaigns
    from .providers import heyreach

    if not CAMPAIGN_LEVEL_STAGING_IS_PROVEN:
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD} is RESEALED. Adding a lead to a HeyReach "
            f"campaign activates that campaign - the vendor documents it for "
            f"both PAUSED and FINISHED - so this operation is the "
            f"prospect-facing moment and not staging. The permission that "
            f"admitted a paused campaign rested on the premise that a paused "
            f"campaign does not send, and that premise is false. Nothing was "
            f"reached")

    if provider_campaign_id in (None, "", 0):
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD} requires `provider_campaign_id` so the "
            f"destination's state can be read at the moment of the write. "
            f"None was given, so nothing can be proven and this refuses. "
            f"The transport was not reached")
    if campaign_id in (None, ""):
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD} requires the CANONICAL campaign id as well "
            f"as the provider's. Without it there is no row to prove this "
            f"campaign is one this deployment staged, and 'it is paused' is "
            f"not on its own a permission. The transport was not reached")

    # 1. OURS? The canonical row is the ownership record, and it is read here
    #    rather than accepted as an argument.
    try:
        row = _campaigns.require(str(campaign_id))
    except Exception as e:
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD}: canonical campaign {campaign_id!r} could "
            f"not be read ({type(e).__name__}: {e}), so nothing proves this "
            f"provider campaign is ours. The transport was not reached"
        ) from None

    # 2. THE EXACT BINDING. A row that names a different provider campaign is
    #    a row about a different campaign, however well it matches otherwise.
    bound = str(row.get("heyreach_campaign_id") or "").strip()
    if not bound or bound != str(provider_campaign_id).strip():
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD}: canonical campaign {campaign_id!r} is "
            f"bound to HeyReach campaign {bound!r} and this write names "
            f"{str(provider_campaign_id)!r}. A mismatched binding is how a "
            f"lead reaches a campaign nobody approved. The transport was not "
            f"reached")

    # 3. DECLARED AS A STAGING CAMPAIGN BY THIS DEPLOYMENT. The declaration is
    #    `provider_status_expected == PAUSED` plus the shape fields that only
    #    `declare_campaign_shape.py` writes, from a readback. An undeclared
    #    campaign - which is every campaign the client made themselves - has
    #    none of them.
    expected = str(row.get("provider_status_expected") or "").strip()
    if expected != heyreach.PAUSED:
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD}: canonical campaign {campaign_id!r} "
            f"declares provider_status_expected={expected!r}, not "
            f"{heyreach.PAUSED}. Staging into a campaign nobody declared as a "
            f"staging campaign is not a thing this permission covers. The "
            f"transport was not reached")
    if not row.get("provider_note") or not row.get("provider_actions"):
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD}: canonical campaign {campaign_id!r} does "
            f"not declare its provider shape, so this deployment cannot show "
            f"it staged it. Run scripts/declare_campaign_shape.py against a "
            f"provider readback first. The transport was not reached")

    # 4. AND WHAT THE PROVIDER SAYS RIGHT NOW. Read live, never remembered:
    #    a human can press Start in the vendor UI between the plan and the
    #    write, and this is the read that catches it.
    try:
        live = heyreach.campaign_read(provider_campaign_id)
    except Exception as e:
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD}: the state of HeyReach campaign "
            f"{provider_campaign_id} could not be established "
            f"({type(e).__name__}: {e}). A campaign whose status is unknown "
            f"is not proven safe to stage into. The transport was not reached"
        ) from None
    if not live or str(live.get("id") or "") != str(provider_campaign_id):
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD}: HeyReach returned no campaign "
            f"{provider_campaign_id}, or one with a different id. A missing "
            f"campaign is not an empty one. The transport was not reached")
    status = str(live.get("status") or "").strip()
    if not status:
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD}: HeyReach campaign {provider_campaign_id} "
            f"returned no status field, so nothing proves it is a paused "
            f"staging campaign. An absent status is not a status. The "
            f"transport was not reached")
    if status != heyreach.PAUSED:
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD}: HeyReach campaign {provider_campaign_id} "
            f"is {status!r}, not {heyreach.PAUSED}. A DRAFT "
            f"campaign refuses leads outright; an IN_PROGRESS one sends to "
            f"them immediately; a FINISHED or unrecognised one is not proven "
            f"anything. The transport was not reached")
    return True


def _campaign_is_ours_and_holds_nobody(provider_campaign_id,
                                       campaign_id=None):
    """True only for OUR declared campaign that the provider says is EMPTY.

    THE LEAD COUNT IS THE WHOLE PERMISSION. Starting a campaign holding zero
    leads sends nothing; starting one holding a single person is the
    prospect-facing moment this system has never performed. The provider
    supplies that number and it is read here, immediately before the write,
    from the route that enumerates actual rows - not from `progressStats`,
    which is a residual that goes negative on live campaigns.

    Ownership is proven the same way as for a staged lead: the canonical row
    is READ, never accepted as an argument.
    """
    from . import campaigns as _campaigns
    from .providers import heyreach

    if provider_campaign_id in (None, "", 0) or campaign_id in (None, ""):
        raise WriteRefused(
            f"{LINKEDIN_START_EMPTY_FOR_STAGING} requires both the provider "
            f"campaign id and the canonical one: one to read the provider's "
            f"lead count, one to prove the campaign is ours. The transport "
            f"was not reached")
    try:
        row = _campaigns.require(str(campaign_id))
    except Exception as e:
        raise WriteRefused(
            f"{LINKEDIN_START_EMPTY_FOR_STAGING}: canonical campaign "
            f"{campaign_id!r} could not be read ({type(e).__name__}: {e}), so "
            f"nothing proves this campaign is ours. The transport was not "
            f"reached") from None
    bound = str(row.get("heyreach_campaign_id") or "").strip()
    if not bound or bound != str(provider_campaign_id).strip():
        raise WriteRefused(
            f"{LINKEDIN_START_EMPTY_FOR_STAGING}: canonical campaign "
            f"{campaign_id!r} is bound to {bound!r} and this names "
            f"{str(provider_campaign_id)!r}. Starting somebody else's "
            f"campaign is the worst possible version of this mistake. The "
            f"transport was not reached")

    try:
        _rows, total = heyreach.campaign_leads(provider_campaign_id, offset=0)
    except Exception as e:
        raise WriteRefused(
            f"{LINKEDIN_START_EMPTY_FOR_STAGING}: the lead count of HeyReach "
            f"campaign {provider_campaign_id} could not be read "
            f"({type(e).__name__}: {e}). A campaign whose population is "
            f"unknown is not proven empty. The transport was not reached"
        ) from None
    if total is None:
        raise WriteRefused(
            f"{LINKEDIN_START_EMPTY_FOR_STAGING}: HeyReach returned no lead "
            f"total for campaign {provider_campaign_id}. A missing count is "
            f"not a zero. The transport was not reached")
    if int(total) != 0:
        raise WriteRefused(
            f"{LINKEDIN_START_EMPTY_FOR_STAGING}: HeyReach campaign "
            f"{provider_campaign_id} holds {total} lead(s). Starting a "
            f"campaign that holds people is prospect-facing, is "
            f"{LINKEDIN_ACTIVATE}, and is sealed. The transport was not "
            f"reached")
    return True


CONDITIONAL[LINKEDIN_ADD_LEAD] = _campaign_is_a_declared_staging_campaign
CONDITIONAL[LINKEDIN_START_EMPTY_FOR_STAGING] = (
    _campaign_is_ours_and_holds_nobody)


def _list_is_unbound_right_now(provider_list_id, campaign_id=None):
    """True only for a list the provider says is attached to NO campaign.

    Enabled 2026-09-16 under written operator authorization; see
    OPERATOR-AUTHORIZATION-2026-09-16.md.

    THE FIRST ARGUMENT IS A LIST ID, NOT A CAMPAIGN ID. Every other condition
    in this map is handed a campaign, because until now every conditional verb
    wrote to one. `perform` passes whatever the caller put in
    `provider_campaign_id`, so this verb's callers put the list there - and
    `liststaging.stage_lead` is the only intended caller.

    WHY THE SAFETY PROPERTY IS A FACT ABOUT THE LIST. A list attached to no
    campaign reaches nobody, whatever is added to it. That is not a claim about
    our intentions; it is the provider's own behaviour. `assert_list_safe`
    reads the list at the moment of the write and raises unless `campaignIds`
    is empty.

    "A LIST WE CREATED" WAS NEVER THE PROPERTY. Campaign 599020 already has
    list 933603 attached, and that list is ours. Ownership is checked too, but
    unboundness is what makes the write non-prospect-facing.

    WHAT THIS CANNOT PROMISE. A list unbound at the moment of the write can be
    attached a second later by anyone with provider access. This is a
    point-in-time check, not a lock, and `liststaging.readback_list_add`
    classifies DRIFTED if the list is no longer unbound afterwards. That is
    detection, not prevention, and it is the honest limit of this permission.
    """
    from . import liststaging

    # TRANSLATED AT THE BOUNDARY, and not merely for tidiness.
    #
    # `perform` documents one refusal type: a write that did not happen raises
    # `WriteRefused`. `assert_list_safe` raises `ListStagingRefused`, which is
    # not a subclass of it, so a caller correctly catching `WriteRefused`
    # around `perform` would not catch this one - the refusal would escape as
    # an unexpected exception type and read as a crash rather than as the gate
    # working. Measured 2026-09-16 while enabling the verb.
    #
    # The message is preserved verbatim, because it already names the list,
    # the campaigns it is attached to, and that the transport was not reached.
    try:
        liststaging.assert_list_safe(provider_list_id)
    except liststaging.ListStagingRefused as e:
        raise WriteRefused(
            f"{LINKEDIN_ADD_LEAD_TO_LIST}: {e}") from None
    return True


CONDITIONAL[LINKEDIN_ADD_LEAD_TO_LIST] = _list_is_unbound_right_now


# THE ONE CAMPAIGN THE 2026-09-16 GRANT NAMES. Both values, because the
# provider id says which campaign at EmailBison and the canonical id says
# which row this deployment believes it is - and a mismatch between them is
# how a lead reaches a campaign nobody approved.
_AUTHORIZED_EMAIL_CAMPAIGN = ("485", "productive-email-control-v2")


def _is_the_authorized_email_campaign(provider_campaign_id, campaign_id=None):
    """True only for EmailBison campaign 485, the one the operator named.

    Enabled 2026-09-16 under written operator authorization, which was
    explicit about its own scope: campaign 485, sender 2736, the existing 10
    approved contacts, the existing approved 3-step CONTROL, a 20/day cap, and
    "NOT authorization to ... activate other campaigns, change copy, add
    unapproved contacts, or increase caps".

    WHY A CONDITION RATHER THAN PLAIN MEMBERSHIP. `EMAIL_ACTIVATE` is the
    first verb in this system that makes a campaign send. Membership of
    `SUPPORTED` alone is a channel-wide licence: it would admit activating 481,
    which holds 23 people with 6 to 40 historical touches each under a
    non-CONTROL sequence. The operator granted one campaign, so the permission
    is one campaign.

    Widening this is a new operator decision. Editing the tuple above to add a
    campaign is not a refactor.
    """
    want_provider, want_canonical = _AUTHORIZED_EMAIL_CAMPAIGN
    if str(provider_campaign_id or "").strip() != want_provider:
        raise WriteRefused(
            f"this authorization covers EmailBison campaign {want_provider} "
            f"only, and this write names {provider_campaign_id!r}. The "
            f"2026-09-16 grant is scoped to one campaign; activating another "
            f"is a new operator decision. The transport was not reached")
    if str(campaign_id or "").strip() != want_canonical:
        raise WriteRefused(
            f"provider campaign {want_provider} is authorized, but the "
            f"canonical row offered is {campaign_id!r} rather than "
            f"{want_canonical!r}. A mismatched binding is how a send reaches a "
            f"campaign nobody approved. The transport was not reached")
    return True


CONDITIONAL[EMAIL_ASSIGN_SENDER] = _is_the_authorized_email_campaign
CONDITIONAL[EMAIL_ACTIVATE] = _is_the_authorized_email_campaign

# `perform` runs the condition at ONE call site, inside the prospect-facing
# branch. That is correct only while every conditional operation is
# prospect-facing, so the assumption is asserted here rather than left to be
# discovered by the first non-facing operation that quietly skips its own
# condition. If this ever fires, add the second call site; do not delete it.
# `perform` runs conditions in BOTH branches now, and this assertion changed
# with it. It used to require every conditional operation to be
# prospect-facing, because conditions ran only in that branch and an
# operation whose condition never ran would be an operation with no
# permission at all - the right guard while the only conditional verb reached
# a person.
#
# `LINKEDIN_START_EMPTY_FOR_STAGING` is conditional and NOT facing: it starts
# a campaign holding nobody, and its condition is precisely what establishes
# "holding nobody". So the guard is inverted rather than dropped - what must
# hold is that a declared condition is reachable, and `perform` now runs them
# on both paths.
for _op in CONDITIONAL:
    if _op not in OPERATIONS:
        raise AssertionError(
            f"{_op} has a condition and is not a declared operation, so "
            f"nothing describes what it does or whether it reaches anybody")
del _op


def is_conditional(operation):
    """Whether this operation needs more than tuple membership."""
    describe(operation)
    return operation in CONDITIONAL


def require_conditional_permission(operation, provider_campaign_id,
                                   campaign_id=None):
    """Run the operation's condition, or pass through if it has none.

    `campaign_id` is the CANONICAL campaign, not the provider's. A condition
    that has to prove a campaign is ours needs the row that says so, and
    taking it as an argument here rather than letting the predicate be handed
    an `owned=True` flag is the difference between proving ownership and
    being told about it.
    """
    check = CONDITIONAL.get(operation)
    if check is None:
        return True
    return check(provider_campaign_id, campaign_id)

PROSPECT_FACING = tuple(op for op, (_c, facing, _w) in OPERATIONS.items()
                        if facing)


# ------------------------------------------------------- failure classes

ACCEPTED = "accepted"        # provider confirmed and read-back agreed
REFUSED = "refused"          # provider declined before acting. Retryable
UNKNOWN = "unknown"          # we cannot say whether it acted. NEVER retryable
DRIFTED = "drifted"          # it acted, and read-back disagrees with what we
                             # asked for. Never retryable; needs a human

CLASSES = (ACCEPTED, REFUSED, UNKNOWN, DRIFTED)


class WriteRefused(RuntimeError):
    """The write did not happen and nothing changed at the provider."""


class WriteUnsupported(WriteRefused):
    """This operation has no established provider contract.

    A distinct type because it is not a safety refusal that a future
    authorization could satisfy - it is an absence of knowledge about the
    provider, and the fix is to establish the contract, not to try harder.
    """


class WriteUnverified(RuntimeError):
    """It may have happened and we cannot prove what. Never retry on this.

    Raised after a call, so unlike `WriteRefused` the provider may have acted.
    The ledger row is left UNRESOLVED, which blocks the key permanently until a
    person reconciles it by hand.
    """


def describe(operation):
    """`(channel, prospect_facing, why_unsupported)` or raise."""
    if operation not in OPERATIONS:
        raise WriteUnsupported(
            f"{operation!r} is not a declared provider operation. Add it to "
            f"OPERATIONS with its channel and whether it can reach a prospect "
            f"before writing code that performs it.")
    return OPERATIONS[operation]


def is_supported(operation):
    describe(operation)
    return operation in SUPPORTED


def require_supported(operation):
    channel, facing, why = describe(operation)
    if operation not in SUPPORTED:
        raise WriteUnsupported(
            f"{operation} is not supported in this build: {why}. "
            f"Nothing was sent to {channel}.")
    return True


def _record_confirmed_touch(authorization):
    """Write the canonical confirmed touch for an action the provider took.

    THE DUPLICATION LAW HAD NO DURABLE HALF. `touch.CONFIRMING_EVENTS` maps
    `events.PUSH_MARKED` to SENT, and `push.mark_pushed` was its only writer -
    but `push.run(live=True)` raises, so no live send could ever reach it. A
    real send therefore settled the ledger and left `push.already_pushed`,
    `eligibility._separation` and `fatigue.contact_check` with nothing to see.
    The ledger key is per STEP (`rec:contact:step:channel`), so it refuses a
    repeat of the same step and nothing else: a different step to the same
    person passed every check.

    `push.mark_pushed` is called rather than reimplemented. Two writers of one
    canonical fact is how the live path and the dry path come to disagree, and
    this module exists because that disagreement is expensive.

    `events.record` is already idempotent on the event id, and the id is
    derived from the action key, so recording twice appends once. That is what
    makes this safe to call again during reconciliation.
    """
    from . import push

    with store.transaction() as recs:
        rec = store.get(authorization.rec_id, recs)
        if rec is None:
            raise WriteUnverified(
                f"the provider acted on {authorization.rec_id!r} and that "
                f"record is no longer in the queue, so the touch cannot be "
                f"recorded. Reconcile by hand before anything else runs")
        step = push.stored_step(rec, authorization.contact_key,
                               authorization.step_key)
        push.mark_pushed(rec, authorization.contact_key,
                         authorization.step_key, authorization.key,
                         at=store.now(), day=step.get("day"))


def material_fingerprint(payload):
    """A stable digest of what is being staged.

    Sorted keys, because a payload that round-trips through JSON comes back
    in a different order and an ordering difference is not a different
    campaign.
    """
    import hashlib

    return hashlib.sha256(
        json.dumps(payload or {}, sort_keys=True, default=str,
                   ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def staged_already(campaign_id, operation, payload):
    """Has this exact material already been staged for this campaign?

    WHY NOT THE ACTION LEDGER. It refuses a reservation that cannot name a
    record, a contact, a sender and a step - "an action nobody can attribute
    is an action nobody can reconcile" - and a staging write has none of
    those. It is a fact about a CAMPAIGN, not about a person, so it is
    recorded where campaign facts live. Bending the ledger's attribution rule
    to fit would weaken the guard that makes it worth having.

    Returns the recorded entry, or None.
    """
    from . import campaigns

    row = campaigns.get(str(campaign_id))
    if row is None:
        return None
    entry = (row.get("provider_staged") or {}).get(operation)
    if not entry:
        return None
    if entry.get("fingerprint") != material_fingerprint(payload):
        return None            # different material, so a different write
    return entry


def record_staged(campaign_id, operation, payload, observed):
    """Write down that this material reached the provider, and what came back."""
    from . import campaigns, store

    with campaigns.transaction() as rows:
        row = campaigns.get(str(campaign_id), rows)
        if row is None:
            return None
        entry = {"operation": operation,
                 "fingerprint": material_fingerprint(payload),
                 "at": store.now(),
                 "observed": observed if isinstance(observed, dict) else None}
        row.setdefault("provider_staged", {})[operation] = entry
    return entry


def _require_approved_words(operation, authorization, step, payload):
    """The words that were approved must be the words that are transported.

    `authorization.fingerprint` records what `approval.is_approved` blessed.
    Nothing compared it to what was actually sent, so the two could differ:
    with a token minted for approved copy, a payload carrying "BUY MY THING,
    unapproved text" was transported and settled as `sent`. Approval gated the
    rendered step and a different string reached the prospect.

    Two things are checked, because either alone is bypassable:

      1. the step handed to this function fingerprints to the approved value -
         so the caller cannot approve one step and declare another;
      2. every non-empty line of that step's copy literally appears in the
         serialised payload - so the caller cannot present the approved step
         and transport something else.

    Only prospect-facing writes reach here. A staging write sends no words.
    """
    from . import approval

    if not isinstance(step, dict):
        raise WriteRefused(
            f"{operation} is prospect-facing and was given no `step`, so the "
            f"words being sent cannot be compared to the words that were "
            f"approved. Pass the same step `authorize` was given")
    actual = approval.fingerprint(step)
    if actual != authorization.fingerprint:
        raise WriteRefused(
            f"{operation}: this step fingerprints to {actual!r} and the "
            f"authorization approved {authorization.fingerprint!r}. The copy "
            f"changed after it was approved")
    body = json.dumps(payload, default=str, ensure_ascii=False)
    for field in ("subject", "body", "note"):
        text = str(step.get(field) or "").strip()
        if text and text not in body:
            raise WriteRefused(
                f"{operation}: the approved {field} does not appear in the "
                f"payload being transported. The approved words and the sent "
                f"words must be the same words")


def perform(operation, *, authorization=None, tenant=None, campaign=None,
            payload=None, transport=None, readback=None, expected=None,
            step=None, by="system", provider_campaign_id=None):
    """The single door. Refuses, in this order, before any transport is touched.

    `transport` and `readback` are injected so the contract can be developed
    and tested against fixtures without a live provider, which is the only
    responsible way to build a write path. Neither is optional at call time:
    a write with no read-back is a write nobody can classify.
    """
    channel, facing, _why = describe(operation)

    # 1. Is there a contract at all? Cheapest and most decisive refusal.
    require_supported(operation)

    # 2. A prospect-facing operation needs a real Authorization - the object,
    #    not something shaped like one. `executionguard` is the only thing that
    #    mints one and it does so only after every gate passes.
    if facing:
        if not isinstance(authorization, executionguard.Authorization):
            raise WriteRefused(
                f"{operation} is prospect-facing and requires an "
                f"Authorization from executionguard.authorize(); a dict "
                f"claiming the gates passed is not proof they did")
        if authorization.channel != channel:
            raise WriteRefused(
                f"the authorization is for {authorization.channel} and "
                f"{operation} writes to {channel}")
        # THE CHANNEL IS NOT THE ACTION.
        #
        # Until this check existed, the only question asked was which channel
        # the token was for - so an authorization minted for `add_lead` would
        # drive `activate`, because both are linkedin and both are facing. One
        # approval to add a lead was therefore an approval to start the
        # campaign, which is the precise escalation the gate ladder exists to
        # prevent. Every gate in `authorize` is evaluated for a NAMED
        # operation, and a token is only proof of the action it names.
        if authorization.operation != operation:
            raise WriteRefused(
                f"the authorization is for {authorization.operation!r} and "
                f"this is {operation!r}. Every gate was evaluated against the "
                f"operation the token names; it is not proof for a different "
                f"one, even on the same channel")
        _require_approved_words(operation, authorization, step, payload)

        # AND IS THE DESTINATION IN A STATE THAT ADMITS THIS AT ALL?
        #
        # For every operation but one this is a no-op. For
        # `LINKEDIN_ADD_LEAD` it is the whole permission: the verb is allowed
        # only against a campaign the provider says, at this moment, cannot
        # send. Read `CONDITIONAL` above for why membership of `SUPPORTED`
        # could not carry that.
        #
        # THE PLACEMENT IS DELIBERATE AND IT MOVED ONCE. It was first written
        # above, as the second thing `perform` did, and that was wrong twice
        # over. It made a PROVIDER NETWORK READ before the token had been
        # shown to be genuine, for this operation, carrying the approved
        # words - so a caller with a bogus authorization could drive HeyReach
        # traffic. And it fired ahead of `_require_approved_words`, so three
        # tests that prove unapproved copy cannot ride an approved token
        # started failing for the wrong reason: a different guard reached
        # them first, which is the exact failure mode CLAUDE.md names.
        #
        # So: every cheap local check first, then this one read, then spend.
        # It sits BEFORE `spend()` on purpose - a refusal here costs nothing
        # and the same token works once the campaign is put back into a state
        # that admits it. The race it closes is the window between this read
        # and the POST, and that window is now `spend`, one ledger read and
        # `revalidate` - all local.
        require_conditional_permission(operation, provider_campaign_id,
                                       campaign)

        authorization.spend()
        key = authorization.key
        # A RESERVATION MUST ALREADY EXIST. `executionguard.authorize` writes
        # one before it mints an Authorization, so in the real path this always
        # holds - but `Authorization` is a plain Python object and can be
        # constructed directly, which is exactly how this check came to be
        # needed: a hand-built one drove a write and `settle` then had nothing
        # to settle. A prospect-facing write with no durable row before it is
        # unreconcilable after it, so it is refused here rather than discovered
        # later.
        if actionledger.state_of(key) != actionledger.ATTEMPTED:
            raise WriteRefused(
                f"{operation} has no open reservation for {key!r} "
                f"(ledger says {actionledger.state_of(key)!r}). A "
                f"prospect-facing write must be reserved before it is "
                f"attempted, or nothing can reconcile it afterwards")
    else:
        # A STAGING WRITE IS NOT PROSPECT-FACING AND IS STILL NOT REPEATABLE.
        #
        # `key` is None here because the action ledger is for actions that
        # reach a person, and this does not. But nothing else was refusing a
        # repeat either, so create-campaign, create-list, set-sequence,
        # assign-sender and set-limits could each be performed twice and build
        # a second provider campaign. A crash between the POST and the
        # response leaves a campaign nobody can find and a retry that makes
        # another.
        #
        # So the campaign row remembers what has been staged onto it, keyed by
        # the fingerprint of the material. Restage the same material and this
        # refuses; change the material and the fingerprint moves and it is a
        # different write, which is what a spec fingerprint is for.
        key = None
        # A STAGING WRITE CAN CARRY A CONDITION TOO, and until
        # `LINKEDIN_START_EMPTY_FOR_STAGING` none did - conditions ran only in
        # the facing branch above, and an assertion at import time kept that
        # honest by refusing a non-facing conditional operation.
        #
        # Starting a campaign is safe exactly when the campaign holds nobody,
        # which is a fact about the provider rather than about the verb. That
        # is a condition by definition, and it belongs on the operation that
        # needs it rather than buried in a factory - so it runs here, before
        # the staging-repeat check and before the transport.
        require_conditional_permission(operation, provider_campaign_id,
                                       campaign)
        done = staged_already(campaign, operation, payload)
        if done is not None:
            raise WriteRefused(
                f"{operation} was already staged for campaign {campaign!r} at "
                f"{done.get('at')} with the same material "
                f"(fingerprint {done.get('fingerprint')}). Staging it again "
                f"builds a second provider campaign; read provider truth and "
                f"reuse what is there, or change the material so this is a "
                f"different write")

    if not callable(transport):
        raise WriteRefused("no transport supplied; refusing to guess one")
    if not callable(readback):
        raise WriteRefused(
            "no read-back supplied. A provider write whose effect is never "
            "read cannot be classified, and an unclassified write is one "
            "nobody can safely retry or abandon")

    # 2b. THE STOPS, AGAIN, AGAINST DISK.
    #
    # Everything above this line asks whether the TOKEN is good: genuine,
    # unspent, right channel, reserved. None of it asks whether the PERSON
    # still wants to hear from us, and that is a different question with a
    # different answer - `authorize` asked it against whatever record the
    # caller was holding, which may have been loaded before the reply arrived.
    #
    # On 2026-09-11 that gap was demonstrated end to end: an unsubscribe was
    # persisted after the mint, `eligibility.decide` answered
    # `blocked:unsubscribed`, and this function called the transport anyway and
    # settled the ledger to `sent`.
    #
    # A refusal here costs nothing. A sent message cannot be recalled.
    if facing:
        executionguard.revalidate(authorization)

    # 3. Perform, then READ BACK BEFORE DECIDING ANYTHING.
    try:
        response = transport(payload)
    except Exception as e:
        # The provider may or may not have acted. This is the branch that must
        # never become a retry loop.
        if key:
            actionledger.settle(key, actionledger.UNRESOLVED,
                                why=f"{type(e).__name__} during {operation}")
        raise WriteUnverified(
            f"{operation} raised {type(e).__name__}: the provider may have "
            f"acted. Read provider truth and settle {key!r} by hand; do NOT "
            f"retry") from None

    try:
        observed = readback()
    except Exception as e:
        if key:
            actionledger.settle(key, actionledger.UNRESOLVED,
                                why=f"read-back failed: {type(e).__name__}")
        raise WriteUnverified(
            f"{operation} returned a response but the read-back failed "
            f"({type(e).__name__}). The provider's state is unknown; do NOT "
            f"retry") from None

    verdict = _classify(observed, expected)

    # Recorded only on an accepted staging write. An UNVERIFIED one must stay
    # re-attemptable after a human has read provider truth, and recording it
    # here would refuse that retry on the strength of a write nobody could
    # confirm.
    if not facing and verdict == ACCEPTED:
        record_staged(campaign, operation, payload, observed)

    # THE TOUCH IS WRITTEN BEFORE THE LEDGER SETTLES, and the order is the
    # whole safety argument. Dying between these two writes must fail closed:
    #
    #   touch first  -> touch recorded, ledger still ATTEMPTED. The next
    #                   attempt is refused by fatigue and by the reservation.
    #   ledger first -> ledger SENT, no touch. Person-level rules see nothing,
    #                   which is precisely the defect being closed here.
    #
    # A touch recorded for an action that did not happen costs one refusal. A
    # missing touch costs a second message to a real person.
    if facing and verdict == ACCEPTED:
        try:
            _record_confirmed_touch(authorization)
        except Exception as e:
            actionledger.settle(
                key, actionledger.UNRESOLVED,
                why=f"touch not recorded: {type(e).__name__}",
                provider_response=_trim(response), readback=_trim(observed))
            raise WriteUnverified(
                f"{operation} reached the provider and was accepted, but the "
                f"confirmed touch could not be recorded ({type(e).__name__}). "
                f"The action is NOT safe to retry - reconcile it by hand"
            ) from None

    if key:
        actionledger.settle(
            key,
            actionledger.SENT if verdict == ACCEPTED else actionledger.UNRESOLVED,
            why=verdict, provider_response=_trim(response),
            readback=_trim(observed))
    if verdict != ACCEPTED:
        raise WriteUnverified(
            f"{operation}: read-back says {verdict}. Expected {expected!r}, "
            f"observed {_trim(observed)!r}. Not retryable")
    return {"operation": operation, "class": verdict, "key": key,
            "response": _trim(response), "readback": _trim(observed),
            "at": store.now()}


def _classify(observed, expected):
    """Did the provider end up in the state we asked for?"""
    if expected is None:
        return UNKNOWN
    # AN EMPTY EXPECTATION VERIFIES NOTHING. `{}` used to fall through to the
    # dict branch, whose loop then had nothing to check, and returned ACCEPTED
    # - so a caller that forgot to say what it wanted got a read-back that
    # agreed with it and a ledger row settled to SENT. Asking for nothing is
    # not the same as getting what you asked for. `0` and `False` stay real
    # expectations; only an empty container is the absence of one.
    if isinstance(expected, (dict, list, tuple, set, str)) and not expected:
        return UNKNOWN
    if isinstance(expected, dict) and isinstance(observed, dict):
        for name, want in expected.items():
            if observed.get(name) != want:
                return DRIFTED
        return ACCEPTED
    return ACCEPTED if observed == expected else DRIFTED


def _trim(value, limit=2000):
    try:
        text = json.dumps(value, default=str)
    except Exception:
        text = str(value)
    return text[:limit]


def report():
    rows = []
    for operation in sorted(OPERATIONS):
        channel, facing, why = OPERATIONS[operation]
        rows.append({"operation": operation, "channel": channel,
                     "prospect_facing": facing,
                     "supported": operation in SUPPORTED, "why": why})
    return {"supported": list(SUPPORTED), "operations": rows,
            "sealed": not SUPPORTED}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="python -m src.providerwrites",
                                description=__doc__)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    found = report()
    if a.json:
        print(json.dumps(found, indent=1))
        return 0
    print(f"provider write layer: "
          f"{'SEALED - no operation is supported' if found['sealed'] else 'OPEN'}")
    for row in found["operations"]:
        mark = "ENABLED " if row["supported"] else "unsupported"
        facing = " PROSPECT-FACING" if row["prospect_facing"] else ""
        print(f"  {mark} {row['operation']:28}{facing}")
        if not row["supported"]:
            print(f"      {row['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
