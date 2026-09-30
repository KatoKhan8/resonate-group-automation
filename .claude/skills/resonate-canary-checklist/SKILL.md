---
name: resonate-canary-checklist
description: Pre-flight checklist before any Resonate OS canary, first live send, provider write, lead attachment, campaign activation or ramp step. Use when selecting or clearing a canary contact, preparing a provider write, or asked whether a contact is ready to send. Enforces a positive ICP verdict, operator exclusion, suppression, the collision check against provider truth, email-only first canary, AUTONOMOUS_PRODUCTION wording, execution scope, readback and the operator GO.
---

# Canary checklist

Canonical: `docs/RACHELE-CANARY-AND-RAMP-PLAN-2026-09-29.md` (execution and
readback plan, and the ramp), `docs/OPERATING-MODE.md` PRODUCTION FREEZE +
decision 19 (launch gate order) + §0a, `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md`,
`docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md`.

**Nothing on this list is inferred from the line above it. Every item is
measured, and an unreadable authority is UNKNOWN — which is never PASS, zero,
clear or safe.**

## 0. The freeze, and who may say yes

No launch, activation, enrolment, provider attachment, prospect-facing send,
resume or provider-changing live test without the operator's explicit
`APPROVED`. The killswitch, the freeze and review approval are **three
independent protections** — none is the others' backup. The killswitch refuses
to START an action and **cannot END one already running**: turning `sending.live`
off is not a pause and is never reported as one. Authority for its value is
`killswitch.workspace_state('<client>')`, never a line in a document.

## 1. Qualification — a POSITIVE verdict, never "not rejected"

    authority   qualify.state_of
    NOT         qualification.verdict.icp_status read alone, a score, a tier,
                a confidence, `not_processed`, or the absence of a rejection

`not_processed` means no verdict exists. **Absence of an ICP verdict is not a
pass.** Company first: no paid person-level call before the company reaches an
explicit ICP verdict, and rejected / review / unknown all mean zero person
credits.

## 2. Operator exclusion

Permanent operator exclusion is its own canonical state — not fingerprint-bound,
never clearing the classifier's verdict, reversible only by a recorded operator
action. Its store is `config/operator-exclusions.jsonl`.

**Check whether it is on master before relying on it:**

    git fetch origin && git merge-base --is-ancestor <sha> origin/master

If the exclusion path is not integrated, the exclusion is **UNKNOWN**, not clear.
A human review is discarded when the facts move — correct for a review that
permits, backwards for one that forbids.

## 3. Suppression, DNC and channel verdict

`channels.email_verdict` asked under the **CLIENT's** policy, not the defaults;
`hygiene` / `agencydnc` for account-level DNC; positive-reply protection. All 76
recipients of the two incidents are suppressed through `channels.email_verdict`.
Verification must read `verified / sendable` under the client's verification
policy — a set address is not a verified one.

## 4. Collision check against provider truth — ours AND the client's

`src/collision.py`, read-only, against the provider's own lead list. This answers
the one question the confirmed-touch model structurally cannot: **what has
somebody else already done from this account.** Our canonical state said zero
touches for two canary contacts and was right about what *this* system had done;
the client's own estate had been working the same list for months.

    search by DOMAIN, walk every page, compare addresses locally
    a broad match (> BROAD_MATCH rows) is a REFUSAL TO ANSWER, never a clean sheet
    verdicts: ALLOW / HOLD / STOP  over  TOUCHED / IN_SEQUENCE / CLEAR

`sending_paused` is membership without contact and flips back to `in_sequence`
the moment somebody resumes — it is not `sequence_finished`. A membership status
nobody has verified the meaning of is reported as unknown, not as harmless. A
reply is a reply even when the counter says zero.

Also check `_refuse_colliding_leads` against the workspace, `_known_lead_ids` for
this campaign, and the 90-day rule (`src/reengagement.py`: REENGAGE needs no
reply ever AND sequence finished AND last touch > 90 days). 27k of the HeyReach
inbox is the client's own, so "we have spoken to them" is not ours by default.

Refresh provider truth with `py -3 scripts/provider_truth.py`, fully paginated —
a partial read is not estate truth, and `docs/state/PROVIDER-CAMPAIGNS.json` is a
**cached read**, not the authority.

## 5. Copy and approval

    approval hash recomputed from the record == the approved hash; a mismatch
      REFUSES rather than approves
    approval.is_approved true for every step, fingerprints unchanged
    approval.is_accountable_approver accepts the stamp (an address, or an
      `approval.OPERATOR_ARMS` value) — a friendly name is refused, and the
      refusal points at the copy while the cause is the signature on it
    configdiff.approved_bison(campaign) vs the provider: lead_copy must match
    copylint and sequencegate both ran on the real path

Approved or sent drafts are **never** overwritten; an unapproved one may be
regenerated. Never widen a gate to make a draft pass — regenerate. A dry run
executes the real decision and safety path with zero provider writes; it never
means "skip the safety path because `live=False`".

## 6. Email only for the first canary

**ONE contact. ONE channel.** LinkedIn is a separate authorization: a second
provider and a second class of write. HeyReach target at canary: **none**.

## 7. AUTONOMOUS_PRODUCTION wording

Where the approval authority is autonomous rather than the operator in person,
the approver string is `approval.AUTONOMOUS_PRODUCTION` (`autonomous-production`)
carrying its expiry, and the grant is **bound to the campaign**. It records who
approved a step; it is never a substitute for the operator's `APPROVED` on a
first send.

## 8. Execution scope

The grant names the contact, the hash and the campaign. Canarying a **different**
prospect, or a different campaign target, is outside it and needs a new decision.
Campaign target is itself an operator decision: attach to an existing approved
campaign, create a dedicated canary campaign (recommended — blast radius one
person), or reuse a paused one. **Reuse is REFUSED**: 487/489/493 are paused by
operator decision and 487's resume grant is spent.

## 9. Two decisions, never collapsed

    decision A   create and attach the lead     writes 1-3, sends 0
    decision B   activate / resume the campaign THE SEND

**The send is the provider's scheduler, not ours.** Attaching a lead to an ACTIVE
campaign causes a send at the mailbox's next free slot, and the day a cohort goes
out is a property of the MAILBOX. Confirm the attested mailbox is not already
15/15 booked on the intended day, and that it has a stored signature — an empty
signature BLOCKS.

## 10. Readback — the only evidence

    bison.campaign_lead_count(provider_id)   +1 exactly
    lead lookup by email                     returns the person, one row
    custom variables                         each body byte-identical to
                                             trailingcontent.compose output
    record_id / contact_key / client         present, so a reply attributes
    after any send                           provider sent-events == 1, and the
                                             sent copy read by eye against the
                                             approved hash

A local dry run, a generated sequence, an adapter test or a "write passed" line
is not evidence. Then rewrite `docs/state/PROVIDER-CAMPAIGNS.json`.

## 11. Operator GO, then stop

Post the pre-flight result to `#resonate-os` in the decision format and **stop**.
Do not proceed on silence — there is no veto window. Rollback before activation
is `bison.stop_lead` plus removal from the campaign; after activation,
`bison.pause_campaign`; at any point, suppress the address through
`channels.email_verdict`. Both stop verbs go through `providerwrites.perform` on
purpose, so each writes a ledger row.

**Record-specific failure → HELD with the exact reason, and continue. Systemic
failure → stop the controller immediately** (wrong-company copy, wrong-person
personalisation, unsupported claim escaping the gates, hash mismatch, wrong
sender, duplicate enrolment, unexpected write, unexpected send, provider readback
contradicting canonical state).
