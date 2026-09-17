# The estate is not out of capacity on the 18th. 487 is.

Measured 2026-09-18 from a **COMPLETE** cursor walk of every scheduled row in
every active campaign: 327 (48,759), 328 (38,744), 352 (95,726) and 487 (10).
**183,239 rows.** No campaign partially walked, so a zero below is a real
zero rather than a row not yet reached — which is the distinction that made
every previous version of this table unsafe to act on.

Read-only GETs. Names hashed; no addresses here.

## Headroom on 2026-09-18

    151  CONNECTED + healthy + has room       2,205 emails of headroom
     59  no room on the 18th
     15  not connected
    ---
    225  inboxes

    human            inboxes   free   attested
    7cc85aecf642          45    648          0
    9e58861fb87e          32    468          0
    013d683eec7a          17    255          0
    083df9628156          17    255          0
    7798a10e783c          17    255          0
    2b4e867056bc          11    165          0
    35ecf4f32d2f           7     94          0
    6782bfbfb93f           4     56          0
    c62bbb200b21           1      9          0

Many are completely unbooked: senders 3939–3948 all read **15 of 15 free,
used 0**, connected, health `ok`.

## What this settles

**The constraint on 487 was never the estate. It is that 487 names ONE
mailbox and that mailbox is full.** 2736's owner, `c62bbb200b21`, holds ONE
inbox with room on the 18th and only 9 emails of it — so the human really is
close to full, exactly as the withdrawn 2911 recommendation eventually
implied. Everyone else has room.

2,205 emails a day of healthy connected headroom sat unreachable while ten
approved emails waited five days for one mailbox.

## Why none of it is reachable today

    ATTESTED AND USABLE: 0

All 151 are unattested, so `assignment.eligible_senders` returns `[]` and
`SAFE_FOR_PRODUCTIVE` is 0. A campaign can still name an inbox on its
canonical row — that is precisely how 487 names 2736 — but nothing can
*choose* one, and choosing is what an allocator does.

Attestation is a HUMAN statement by design and `senderownership.attest`
records who vouched and when. The provider publishes a display name on every
inbox, which is EVIDENCE and not proof; `scripts/propose_sender_attestation.py`
turns that into a proposal for a person to confirm and attests nothing itself.
It also flags the hazard that matters here: two provider names one edit apart
holding 45 and 4 inboxes, which no amount of reading the provider settles.

## One caveat that must travel with this table

**"Free now" is not "will stay free."** The documented scheduler runs on
campaign resume and at the END of every sending day, so the client's own
campaigns can book some of this headroom later today. The table is a true
statement about the queue as it stands, not a reservation.

A campaign that intends to use one of these inboxes should read the book again
immediately before it activates, not trust this file.

## What it changes

It makes the second-campaign route a capacity question that is already
answered, leaving only the two operator decisions in
`docs/GATES-BEFORE-A-SECOND-EMAIL-CAMPAIGN-2026-09-17.md`: the contact
approval, which gates staging, and the `EMAIL_ACTIVATE` scope. Nothing here
grants either, and nothing here is a reason to weaken the attestation rule to
reach the capacity faster.
