# Expansion is blocked by the client's own outreach, not by approval

Measured 2026-09-18 from `scripts/next_ready_cohort.py --json`, every contact
in the Productive estate, cross-tabulated by the FIRST gate that stops it and
by whether it also carries a safety refusal.

This corrects the working assumption - mine included, earlier today - that
approval is the bottleneck. Approval is the first gate on 102 contacts and it
is the ONLY thing standing in front of **seven** of them.

## The cross-tab

    EMAIL, 51 contacts
      15  ALREADY_LIVE     gate=collision    coll=in_sequence, acct=stop
      12  SAFETY_BLOCKED   gate=approval     coll=touched, acct=hold
       7  SAFETY_BLOCKED   gate=approval     coll=in_sequence, acct=stop
       6  SAFETY_BLOCKED   gate=approval     acct=stop
       4  SAFETY_BLOCKED   gate=approval     coll=touched, acct=stop
       4  SAFETY_BLOCKED   gate=approval     coll=touched
       3  SAFETY_BLOCKED   gate=approval     acct=hold

    LINKEDIN, 81 contacts
      34  SAFETY_BLOCKED   gate=approval     acct=stop
      14  SAFETY_BLOCKED   gate=approval     acct=hold
       7  SAFETY_BLOCKED   gate=copy         acct=stop
       7  NEAR_MISS        gate=approval     (nothing else)
       3  ALREADY_LIVE
       ... and a long tail, every one of which carries acct=stop or acct=hold

**Not one email contact is blocked by approval alone.** Every one of the 36
also carries an account STOP or HOLD, or a collision. Approving them converts
nobody.

**Seven LinkedIn contacts are blocked by approval alone**, and they are
exactly the seven in the regenerated near-miss packet. That is the entire
remaining convertible inventory in this estate today.

## Why the accounts are stopped

    65  stop  somebody at this account is mid-sequence right now
    33  hold  a campaign at this account ended early (stopped) and the status
              does not say whether we stopped it, they unsubscribed, or
              something else
    15  stop  1+ person(s) at this account have already replied or been marked
              interested; the account is answered
     2  hold  an address at this account bounced; the data is suspect

The 65 are the finding. **The client's own campaigns are actively emailing
these companies.** 327, 328 and 352 hold 183,239 scheduled rows between them,
and the account gate is correctly refusing to put a second conversation in
front of a company already mid-sequence with its own vendor.

The 15 are positive-reply protection, working. The 2 are a bounce, working.

## What this means for "expand the cohort"

It means sourcing, not enrichment.

The estate of 550 records is largely EXHAUSTED, and not because the pipeline
is slow or because copy is missing or because verification is incomplete. It
is exhausted because the accounts in it are already being worked by the
client. Verifying more contacts at those accounts, generating more copy for
them, or approving more of them changes nothing - the account gate refuses
after all of it, and refusing is correct.

`scripts/funnel.py` shows the same thing from the other end:

    RECEIVED          550
    QUALIFIED         113
    ICP_REVIEW        215      <- a person must look
    PERSON_DISCOVERY   91
    VERIFIED           67
    CAMPAIGN_READY     35
    LIVE_ELIGIBLE      32      <- and 18 are live

So the two real pools are **215 records awaiting a human ICP verdict** and
**new accounts nobody has sourced yet**. Neither is an enrichment problem.

## The one recoverable pool, and it is worth recovering

**33 accounts are HOLD for an UNKNOWN rather than a fact:** "a campaign at
this account ended early (stopped) and the status does not say whether we
stopped it, they unsubscribed, or something else".

That is a conservative hold on ambiguity, and it is the right default. It is
also 33 accounts - roughly a third of everything blocked - being held by a
question nobody has asked the provider.

The question is answerable. A `stopped` membership has a cause, and the
estate now has a complete forward-book walk, an events feed that normalises
100% of real events, and a reply feed. Distinguishing "we stopped it" from
"they unsubscribed" from "it finished" turns a HOLD into either a definite
STOP - which is information - or a CLEAR, which is inventory.

**It must resolve the ambiguity, never assume past it.** A HOLD that becomes
CLEAR because nobody could find evidence of a refusal is exactly the failure
this gate exists to prevent. Missing evidence is not positive evidence.

## Grok, 2026-09-18: two documented facts

Asked because they were UNKNOWN in this repository, and classified rather than
believed.

**`POST /api/leads/multiple` exists and takes up to 500 leads per request.**
DOCUMENTED - docs.emailbison.com/leads/creating-a-lead and the OpenAPI spec.
`bisonfactory._ensure_leads` creates leads one at a time. At the current
cohort sizes that costs nothing worth optimising; at 550 records it is the
difference between one request and 550. Not wired, and wiring it needs the
same care every provider write here gets - a readback that proves WHO arrived,
not a 200.

**The webhook event names are documented**, and they AGREE with what this
system already does. `lead_replied`, `email_sent`, `email_bounced`,
`email_opened`, `lead_unsubscribed`, and `untracked_reply_received` - a reply
not tied to a campaign's scheduled email.

Two things were checked rather than assumed:

- `UNTRACKED_REPLY_RECEIVED` is already mapped to `"replied"` in
  `bisonevents.TYPE_TO_KIND`. An untracked reply suppresses.
- The documented names are lowercase and the map's keys are uppercase.
  `_normalise_type` does `.strip().upper().replace(" ", "_")`, so
  `lead_replied` and `LEAD_REPLIED` both resolve. Verified directly.

So this upgrades those mappings from ASSUMED to DOCUMENTED and finds no
defect. **The two UNKNOWNs that actually block the webhook are still
UNKNOWN**: whether a real delivery POSTs the envelope or the inner payload,
and whether a RETRY repeats the envelope `uuid` - which is the dedupe key and
the whole point of the module. Polling remains the fallback.

## What should happen next, in order

1. **Approve the seven LinkedIn contacts**, or decide not to. They are the
   only convertible inventory in the estate and the packet is regenerated.
2. **Resolve the 33 ambiguous HOLDs** against provider truth. Biggest
   single pool, and it is a reading problem rather than a spending one.
3. **Source new accounts.** `new_accounts_per_day` is 5 and the constraint on
   growth is now upstream of everything this pipeline does well.
4. The 215 ICP_REVIEW records need a human verdict, and no amount of
   engineering substitutes for it.
