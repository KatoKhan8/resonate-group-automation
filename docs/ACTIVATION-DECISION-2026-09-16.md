# The narrow activation decision, and why it is not the global killswitch

Prepared 2026-09-16 at the operator's instruction: "Prepare the exact narrow
operator decision required to transition the Productive canary from staged to
LIVE/SENDING... Do not create a broad 'disable safety' mechanism."

## FIRST: the global killswitch is the wrong lever, and must not be touched

`killswitch.global_state()` reports `sending: false, refused_in_code: true`.
That reads like the safety interlock standing between this system and a send.
It is not.

    push.run(live=True) raises LiveSendNotEnabled:
      "live push is not implemented in this build. Phase 7 ships preparation
       only: payloads, eligibility, pause and idempotency. No code here can
       reach EmailBison or HeyReach."

**That is an unimplemented feature, not a disabled one.** `push.run` builds
payloads and checks eligibility; there is no send code behind it to enable.
`killswitch.global_state()` derives its verdict from the presence of that
exception class, which is why it is described in its own docstring as "derived
from the refusal rather than from a flag... a review, not a toggle".

And it is irrelevant to reaching LIVE/SENDING, because **the provider does the
sending.** A HeyReach campaign holding leads and running sends by itself. An
EmailBison campaign that is active sends by itself. Nothing in `push.py` is on
that path.

So: leave `push.run`'s refusal exactly as it is. Removing it would enable an
unbuilt code path and would change nothing about the canary. The narrow
decision is two permissions, below.

## WHAT IS ACTUALLY REQUIRED

Two verbs, each prospect-facing, each currently in neither `SUPPORTED` nor
`CONDITIONAL`:

    heyreach.activate    route EXISTS (POST /campaign/Resume,
                         /campaign/StartCampaign). Withheld on a stated
                         condition: "a system that can start an outreach
                         campaign before it can reliably stop one has bought"
                         trouble. `heyreach.pause` IS supported, so the stop
                         side exists and that condition is MET.

    bison.activate       contract established since 2026-09-13
                         (PATCH /api/campaigns/{id}). Its own entry says "WHAT
                         IS MISSING IS PERMISSION, AND THOSE ARE DIFFERENT
                         REFUSALS". `bison.pause` and `bison.stop_lead` are
                         both supported, so the stop side exists here too.

Each should be granted **scoped to one named campaign**, not as a channel-wide
capability. The existing `CONDITIONAL` mechanism is how that is expressed: a
predicate that reads the provider at the moment of the write and refuses
anything but the declared campaign. `_campaign_is_ours_and_holds_nobody` and
`_list_is_unbound_right_now` are the two precedents.

## PROVIDER STATE, READ 2026-09-16

    HEYREACH
      workspace          Resonate's HeyReach account
      campaign 599020    "RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1"
                         status FINISHED  <- CHANGED OVERNIGHT, was DRAFT
                         0 leads, sender 174892 attached
      list 940797        "RESONATE - STAGING PROBE - DO NOT USE"
                         campaignIds [] - UNBOUND. 1 lead (TASK-158 probe)
      list 933603        attached to 599020. NOT a staging destination.

    EMAILBISON
      workspace          id 10, "PRODUCTIVE"
      campaign 481       paused, 23 leads, 20 emails/day. NOT the destination -
                         TASK-174: all 23 carry 6-40 historical touches under a
                         non-CONTROL sequence, and set_sequence APPENDS.
      campaign 451       completed, 1 lead, 1 sent.
      CONTROL campaign   DOES NOT EXIST YET. The write is prepared and
                         rehearsed; see scripts/stage_canary_lead.py's sibling
                         path and docs/BISON-WRITE-REHEARSAL-2026-09-16.md.

**599020 being FINISHED matters.** Provider truth: adding a lead to a FINISHED
campaign ACTIVATES it. So the campaign route is send-capable right now, which
is exactly why `LINKEDIN_ADD_LEAD` stays sealed and the canary goes through the
unbound LIST instead.

## THE TWO CANARIES

    LINKEDIN
      cohort           1 contact (record hash 699952d14554)
      copy             li1-li5, all approved by operator-control-arm, with
                       fingerprints. Profile resolves at /lead/GetLead.
      sender           174892, attached to 599020, resolves and is active
      max exposure     5 messages to 1 person
      path             unbound list 940797 -> readback -> bind to campaign ->
                       activate

    EMAIL
      cohort           10 contacts (was 17; 16 survived collision; 11 have a
                       resolved persona; 10 have an em2 step at all)
      copy             CONTROL em1-em3, all 30 renderings pass lint AND the
                       claims gate, approval pending one command
      sender           NONE on the new campaign. `_ensure_senders` refuses to
                       choose: "picking an inbox would be choosing which human
                       a prospect hears from". A campaign with no sender sends
                       nothing, so assigning one is part of this decision.
      max exposure     30 messages to 10 people, capped at 20 emails/day
      path             create campaign -> set CONTROL sequence -> readback ->
                       add leads -> activate

## WHAT MUST BE PRESERVED, AND IS

Listed because the operator required it, with where each lives:

    workspace killswitch   killswitch.workspace_state - "sending.live is on
                           for productive". UNCHANGED by this decision.
    tenancy                bison.bound_workspace() checked before any write;
                           heyreach tenancy in assert_list_safe
    collision              collision.check_account, account-level, run per
                           contact by TASK-177 and again at write time
    prior contact          checked against the provider, not local state -
                           it found a real 13-email history on one domain
    approval fingerprint   approval.is_approved compares the fingerprint to
                           the copy; a stamp on replaced text is detected
    verification           no email is generated for an unverified address
    fatigue                src/fatigue.py, consulted in the gate ladder
    sender caps            20/day on the email campaign; HeyReach seat limits
    provider readback      providerwrites.perform refuses a write with no
                           readback
    audit ledger           actionledger + the waterfall spend ledger
    idempotency            staged_already refuses the same material twice

None of these is weakened by granting the two verbs. Each activation is a
single provider call against one named campaign, and every gate above runs
before it.

## WHAT IS STILL BLOCKED, AND BY WHAT

Neither canary is staged yet, and not for want of a decision:

- **Claude Code's auto-mode classifier denies every write from this session** -
  provider calls and local state mutations alike. Two commands are packaged and
  waiting: `scripts/apply_control_approval.py --live` (10 contacts, 30 steps,
  dry run passes with zero refusals) and `scripts/stage_canary_lead.py --live`.
  This is a harness control, not a Resonate OS gate, and it must not be worked
  around.
- **The HeyReach list add returns `0/0/0`** on this canary - three attempts,
  two through the campaign route yesterday and one through the list route
  today. The URL was a bare vanity slug and is now canonicalised; the profile
  resolves; the remaining difference is that the transport was sending
  `companyName` and `position` on top of the three fields TASK-158 proved, and
  the default is now the proven three. That correction is untested against the
  provider because of the classifier.
