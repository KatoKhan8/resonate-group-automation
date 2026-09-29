PRIORITY: READ BEFORE THE FIRST PROVIDER WRITE

# RACHELE LIVE CANARY — EXECUTION AND READBACK PLAN, AND THE RAMP

    MEASURED AT  master 5b3dec26, 2026-09-29
    STATE        PLAN ONLY. Nothing executed. Provider writes 0.
                 sending.live false. NOT AUTHORIZED TO SEND.

---

## 1. THE APPROVED ARTIFACT

    approval hash   fba63864ca640b9e
    approved by     Zvonimir (operator), 2026-09-29
    recorded        10 step approvals on the record, record state `approved`
    recipient       Rachele Crumpler, CFO, rcrumpler@2020companies.com
                    linkedin.com/in/rachele-crumpler-cpa-6a2a973a
    account         2020 Companies / 2020companies.com (2020companies-com)
    sender          Ivan, founder, Productive - signature bytes
                    `Ivan\nProductive`, verified in the EmailBison projection
    verification    verified / sendable, 3 of 2 confirmations
                    (contactout, deliverable, reoon)

The hash was RECOMPUTED and asserted equal to `fba63864ca640b9e` before any
approval stamp was written; a mismatch refuses rather than approves.

## 2. WHAT THE CANARY IS

**ONE contact. ONE channel first.** Email only. LinkedIn is a separate
authorization, because a LinkedIn enrolment is a second provider and a second
class of write.

    expected provider writes at canary time
      1  bison.create_lead            the lead for Rachele
      2  bison.attach_leads           attach it to the canary campaign
      3  bison.update_lead            only if reconciliation finds drift

    expected prospect-facing sends at canary time
      0  at the moment of the write

**The send is the provider's scheduler, not ours.** Attaching a lead to an
ACTIVE campaign is what causes a send, at the mailbox's next free slot. So
the canary is two operator decisions, not one:

    decision A   create and attach the lead        (writes 1-3)
    decision B   activate / resume the campaign    (the send)

Do not collapse them. `docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md`: the
day a cohort goes out is a property of the MAILBOX.

## 3. CAMPAIGN TARGET — UNRESOLVED, NEEDS AN OPERATOR DECISION

`work/campaigns.jsonl` holds 64 productive campaigns, 31 non-LinkedIn. None
is a Rachele canary campaign. Three routes:

    A. attach to an existing approved campaign   no create_campaign write,
                                                 but the campaign's sequence
                                                 must match the 5-step ladder
    B. create a dedicated canary campaign        one extra provider write
                                                 (bison.create_campaign +
                                                 set_sequence + set_limits)
    C. reuse a paused campaign                   REFUSED: 487/489/493 are
                                                 paused by operator decision
                                                 and 487's resume grant is
                                                 SPENT

**Recommended: B**, a dedicated canary campaign with a schedule whose window
is known, so the send time is predictable and the blast radius is one person.
**This is an operator decision and is not taken here.**

HeyReach target: **none at canary**. LinkedIn stays unenrolled until email is
proven.

## 4. PRE-FLIGHT, IN ORDER

    1. killswitch.workspace_state('productive')['sending'] must be TRUE
       It is FALSE today. Turning it on is an operator action and is the
       switch that lets `_ensure_leads` create a lead at all.
    2. approval hash recomputed from the record == fba63864ca640b9e
    3. approval.is_approved true for all 10 steps, fingerprints unchanged
    4. configdiff.approved_bison(campaign) vs the provider: lead_copy must
       match. THIS IS THE CHECK THAT WAS BROKEN AND IS NOW FIXED - see
       commit 5b3dec26.
    5. suppression: Rachele not on the suppression list, not operator-excluded
    6. duplicate check: `_refuse_colliding_leads` against the workspace, plus
       `_known_lead_ids` for this campaign; 27k of the HeyReach inbox is the
       client's own, so a "we have spoken to them" signal is not ours by
       default
    7. sender: the attested mailbox for Ivan; confirm it is not already 15/15
       booked on the intended day

## 5. READBACK — WHAT PROVES IT WORKED

Only a provider readback against a real id is evidence. A local dry run, a
generated sequence and a "write passed" line are not.

    after the write
      bison.campaign_lead_count(provider_id)   +1 exactly
      bison lead lookup by email               returns Rachele, one row
      the lead's custom variables              subject_1 + body_1..body_5,
                                               each body byte-identical to
                                               trailingcontent.compose output
      record_id / contact_key / client         present, so a reply can be
                                               attributed
      scripts/provider_truth.py                rewrite docs/state/
                                               PROVIDER-CAMPAIGNS.json

    after any send decision
      provider sent-events for that lead       exactly 1
      the send ledger                          1 confirmed touch
      the mailbox                              the sent copy read by eye and
                                               compared to the approved hash

## 6. ROLLBACK AND STOP

    before activation   bison.stop_lead (in SUPPORTED, goes through
                        providerwrites.perform, writes a full ledger row)
                        and remove the lead from the campaign
    after activation    bison.pause_campaign (SUPPORTED, authorized,
                        ledgered). NOTE: the killswitch refuses to START an
                        action and CANNOT END one already running - turning
                        sending.live off is NOT a pause.
    at any point        suppress the address through channels.email_verdict

**The stop verbs are the two that go through the central door.** That is not
a coincidence and it is the reason they are the ones to reach for.

## 7. THE RAMP — DESIGN ONLY, NOT BUILT

    canary(1) -> 5 -> 10 -> 15 -> 20 -> 25 -> 50 -> 50 -> 50 -> ...

COMPANIES, not leads and not contacts. No jump to 50.

**Advance only when the preceding checkpoint shows:** zero systemic failures,
no unexpected writes, no duplicate enrolments, correct sender, correct
company/contact mapping, approved copy and hash matching the projection, and
a provider readback consistent with canonical state. Individual HELD records
do not block advancement.

### Checkpoint record, per batch

    batch size · companies attempted · researched · Apify runs · qualified ·
    HELD (with exact reasons) · contacts discovered / qualified / verified /
    sendable / enrolled · emails projected · LinkedIn steps projected ·
    provider writes · messages actually sent · duplicate-prevention result ·
    sender identity result · approval hashes · provider readback result ·
    errors

### Record-specific failure -> HELD / NOT_QUALIFIED, reason recorded, CONTINUE

no admissible research fact · fails ICP · no relevant contact · verification
fails · operator-excluded · copy cannot clear gates for one contact

### Systemic failure -> STOP THE CONTROLLER IMMEDIATELY

wrong-company copy · wrong-person personalisation · unsupported claim escaping
the gates · approval/hash mismatch · approved artifact differing from the
provider projection · wrong sender · duplicate enrolment · unexpected provider
write · unexpected prospect-facing send · campaign/sequence mapping mismatch ·
provider projection mismatch · canonical state corruption · evidence or
provenance bypass · operator-exclusion bypass · verification-policy bypass ·
provider readback contradicting canonical state · a repeated identical
infrastructure error suggesting a shared cause

### Durability

The ramp must run under a durable, checkpointed, resumable controller - NOT
an interactive session. Restart must not cause duplicate processing,
duplicate enrolment, duplicate sends, skipped companies, or loss of HOLD
reasons or approval hashes. State belongs in canonical storage and the
controller resumes from it.

### Research policy, decided 2026-09-29

`step1_without_pack_fact` REMAINS REFUSING. The expired demotion is NOT
renewed. Reuse admissible research; otherwise run the canonical Apify path;
admit only sourced and provenanced evidence; if research still yields no
admissible personalisation fact, HELD that record with the exact reason and
continue. Never invent or pad an icebreaker. Missing research is a RESEARCH
TRIGGER, not permission to lower personalisation quality.
