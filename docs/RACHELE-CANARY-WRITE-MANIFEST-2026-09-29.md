PRIORITY: THE AUTHORIZATION MANIFEST — READ BEFORE AUTHORIZING

# RACHELE EMAIL CANARY — EXACT PROVIDER WRITE MANIFEST

    measured at   master 85b14520, 2026-09-29
    approved hash fba63864ca640b9e (recomputed and matched at preflight)
    recipient     Rachele Crumpler, rcrumpler@2020companies.com
    sender        Ivan / Productive, signature bytes `Ivan\nProductive`
    STATE         NOTHING EXECUTED. Provider writes 0. sending.live false.

## THE TWO FACTS THAT DECIDE HOW THIS IS SCOPED

**1. A send is not implemented in this build.**

    killswitch.global_state()
      sending: False
      why: "live sending is refused in code: push.run(live=True) raises and
            tagsync.send refuses unconditionally. This is not a flag"
      refused_in_code: True

`push.run(live=True)` raises `LiveSendNotEnabled`. **We cannot send.** The
delivery at canary time would come from EmailBison's own scheduler once a
lead sits on an ACTIVE campaign. That is what makes activation, not
attachment, the prospect-facing act.

**2. Lead creation is gated at the WORKSPACE, and nowhere narrower.**

`bisonfactory._ensure_leads` consults `killswitch.workspace_state(client)`
only. There is no campaign-scoped gate on lead creation. So the narrowest
authorization the current mechanism can express is
**"productive may have leads created"**, not **"this one campaign may"**.

**Reported as a limitation, not solved by weakening anything.** What bounds
the blast radius today:

- the global layer still refuses every send, in code, so setup cannot deliver
- no autonomous stager or sender process is running (0 python processes,
  pool watchdog stopped, no worktree locks)
- the only campaign that would be staged is the dedicated canary
- 487/489/493 are paused AT THE PROVIDER, which our killswitch does not touch
  and cannot un-pause

If a campaign-scoped lead-creation gate is wanted before authorizing, that is
a small, honest task and it is not done here.

## THE MANIFEST — EVERY MUTATION, NUMBERED

Setup, in order. **Expected prospect-facing sends during all of it: 0.**

    #  provider  action                     target              reversible  rollback
    1  bison     create_campaign            new canary campaign  yes         delete/abandon; it holds nobody
    2  bison     set_sequence               that campaign        yes         set_sequence again
    3  bison     set_limits                 that campaign        yes         set_limits again
    4  bison     set_schedule               that campaign        yes         set_schedule again
    5  bison     ensure_custom_variables    the workspace        idempotent  none needed; creates nothing
                                                                             that can reach a person
    6  bison     create_lead                Rachele              yes         stop_lead, then remove
    7  bison     attach_leads               lead -> campaign     yes         stop_lead / detach
    8  bison     update_lead                Rachele              yes         update_lead again
                 (ONLY if reconciliation finds variable drift)

**Total: 7 writes, plus 1 conditional.** Not 3 — the earlier estimate counted
only the lead operations and omitted campaign creation, which this decision
introduces.

Writes 1-5 touch no person. Writes 6-8 create and populate one lead. **None
of them sends.**

## THE SEPARATE, PROSPECT-FACING ACT

    #  provider  action     target            effect
    A  bison     activate   the canary        the provider's scheduler may
                            campaign          now deliver to Rachele at the
                                              mailbox's next free slot

**This is the authorization to withhold until everything above is verified.**
It is a different decision from the manifest and must be granted separately.
`EMAIL_ACTIVATE` is declared in `providerwrites.OPERATIONS` but is NOT in
`SUPPORTED`, so `perform` refuses it today; enabling it is itself an operator
decision recorded in code.

## READBACK, AFTER THE MANIFEST AND BEFORE ACTIVATION

    bison.campaign_lead_count(canary_id)      exactly 1
    lead lookup by rcrumpler@2020companies.com  exactly one row
    the lead's custom variables                 subject_1 plus body_1..body_5
    each body                                   byte-identical to
                                                trailingcontent.compose output
    record_id / contact_key / client            present, so a reply can be
                                                attributed back
    configdiff.approved_bison(campaign)         no lead_copy mismatch
                                                (this is the check fixed at
                                                 commit 5b3dec26)
    scripts/provider_truth.py                   rewrite PROVIDER-CAMPAIGNS.json
                                                and confirm the canary is the
                                                only campaign holding a lead

## ROLLBACK

    before activation   bison.stop_lead (SUPPORTED, goes through
                        providerwrites.perform, writes a full ledger row),
                        then detach; the campaign may be left empty
    after activation    bison.pause_campaign (SUPPORTED, authorized,
                        ledgered). The killswitch CANNOT end a campaign
                        already running - turning sending.live off is not a
                        pause and never was
    any time            suppress the address through channels.email_verdict,
                        which is what `_replied` then reads
