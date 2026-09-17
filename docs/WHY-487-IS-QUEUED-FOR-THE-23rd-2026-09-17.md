# Why 487's ten emails are queued for 23 September

2026-09-17. Every number below is a provider readback. Where our code's
prediction and the provider disagree, the provider wins; where a claim is not
in the provider's documentation, it says UNKNOWN.

## The facts

    CAMPAIGN_ID              487
    CAMPAIGN_STATUS          active
    QUEUED_EMAILS            10   (one per lead, all step 4742 = the opener)
    SCHEDULED_AT             2026-09-23  07:12 08:24 08:55 09:46 10:00
                                         11:13 12:35 12:42 13:22 14:00  (UTC)
    CAMPAIGN_TIMEZONE        Europe/Zagreb
    SENDING_DAYS             Mon-Fri (saturday false, sunday false)
    SEND_WINDOW_START        09:00:00
    SEND_WINDOW_END          17:00:00
    STEP_DELAY               step1 wait_in_days 3, step2 4, step3 1
    SENDER_IDS               [2736]
    SENDER_AVAILABILITY      daily_limit 15, Connected, warmup on,
                             1,756 lifetime, 11 bounced
    PROVIDER_SCHEDULER_STATE queued at 2026-09-17T15:02:48Z, two minutes after
                             the campaign's window closed

In Europe/Zagreb those ten UTC instants are 09:12 to 16:00 - **every one
inside the campaign's own 09:00-17:00 window**, spread across the day rather
than bunched. The schedule is being honoured exactly.

(`scheduled_date_local` on each row reads six hours ahead of `scheduled_date`
while Zagreb is UTC+2, and six of the ten "local" values fall outside the
campaign's window while all ten UTC values fall inside it. `scheduled_date` is
the field that means something. Nothing here reads the other one.)

## The cause: the mailbox's forward book is full until the 23rd

Not the step delay. Not the timezone. Not the sending days. Not activation.
**Sender availability**, and it is measured rather than inferred.

`/campaigns/{id}/scheduled-emails` carries a full `sender_email` object per
row, so the sibling campaigns' queues can be read for what mailbox 2736 is
already committed to. Sampling 3,600 rows across campaigns 327, 328 and 352:

    sender   09-18  09-19  09-21  09-22  09-23     daily_limit
      2736      15      0      15      15      0            15
      2903      15      0      15      15      0            15
      2904      15      0      15      15      0            15
      2906      15      0      15      15      0            15
      2911       0      0      10      15      0            15
      3437       6     14      15       4      0            15

**Sender 2736 is booked to exactly its daily limit of 15 on 18, 21 and 22
September.** The first day with any free capacity is the 23rd, which is where
all ten of 487's openers landed.

Two independent cross-checks that the sample is not lying:

- **Four of the six inboxes show exactly 15 on three separate days.** Landing
  on a mailbox's precise configured limit, repeatedly, is not a sampling
  coincidence.
- `scripts/bison_mailbox_utilisation.py` measured 2736 actually sending **+11
  today**, and this sample shows **11 rows scheduled for today**. Two different
  routes, the same number.

### The chain, stated causally

    CONFIG        487 names exactly one sender, 2736, whose daily_limit is 15
                  and which also serves three ACTIVE campaigns
    PROVIDER RULE the limit is per MAILBOX and shared across every campaign
                  holding it; the scheduler books forward, day by day
    DECISION      at end-of-day on the 17th it looked for a day with free
                  capacity on 2736 - the 18th, 21st and 22nd were each at
                  15/15, so the 23rd was the first available
    RESULT        ten openers at 2026-09-23, 07:12Z-14:00Z, all inside the
                  campaign's window

The end-of-day timing is itself documented: "it schedules on campaign resume
and at the end of each sending day"
(docs.emailbison.com/campaigns/overview.md), which is why the rows appeared at
15:02:48Z rather than at the window's opening. That disposed of the earlier
window-opening hypothesis; this disposes of the remaining question it left.

### Not the step delay, and here is the control

`wait_in_days: 3` on step 1 is the tempting answer and it is wrong. Canary
campaign 451 carried the identical `wait_in_days: 3` on its only step, was
created on 2026-09-13, and its first `scheduled_date` was **the same day**.
The same field produced a same-day schedule there and a six-day one here, so
it is not what differs. What differs is the mailbox: 451 sent from 3948, which
was not carrying three other campaigns.

## Can these ten send tomorrow? YES - but not from 2736

487 needs ten free slots on 2026-09-18. Mailbox 2736 has **zero**: its fifteen
are already committed to the client's own campaigns. No configuration change
to 487 can conjure capacity out of a full mailbox, and
`PRODUCTION-SCALE-POLICY.md` forbids the one that looks like it could -
"a sender estate that is never made to carry more by raising a limit".

**Sender 2911 has all fifteen of its slots free on 2026-09-18**, and it is the
same human:

                            2736                     2911
    name hash               c62bbb200b21             c62bbb200b21   SAME
    email signature         9d5ab0201ca9             9d5ab0201ca9   IDENTICAL
    status                  Connected                Connected
    daily_limit             15                       15
    lifetime sends          1,756                    1,793
    bounced                 11  (0.63%)              9  (0.50%)     BETTER
    free on 09-18           0 of 15                  15 of 15
    domain                  dontgoproductive.com     gettryproductive.com

The signature is byte-identical, so a prospect reads the same person and the
same sign-off. 3437 is rejected despite having free capacity: its lifetime
bounce rate is 2.1%, above the 2% DEGRADED threshold `senderinventory`
already applies.

### The smallest documented, reversible change

    POST   /campaigns/487/attach-sender-emails   {"sender_email_ids": [2911]}
    DELETE /campaigns/487/remove-sender-emails   {"sender_email_ids": [2736]}

Both are documented, both are already in `bison.WRITE_ROUTES`, and the detach
route has been exercised successfully once. Arity stays at ONE sender
throughout if the attach and detach are ordered detach-then-attach; done the
other way round the campaign passes through a two-sender state that
`executionguard` would refuse to authorise anything against.

### What it would and would not change

Provable from canonical state and provider truth:

    approved copy            UNCHANGED. The body is a per-lead {BODY_1}
                             variable; the sender contributes only the
                             signature, which is byte-identical
    sequence / threading     UNCHANGED. No sequence-step write is involved
    lead membership          UNCHANGED. No lead verb is called
    HumanSenderIdentity      UNCHANGED. Same human, same name, same signature
    reply suppression        UNCHANGED. Keyed on the lead, not the mailbox
    verification             UNCHANGED. A property of the address
    collision / history      UNCHANGED. Account-level, mailbox-independent
    approval fingerprint     CHANGES, EXPECTEDLY. `campaigns.fingerprint`
                             covers the sender, so the canonical row must be
                             updated and RE-APPROVED. That is the documented
                             path and the operator has authorised this exact
                             shape once before, for a different sender

### The one thing that is UNKNOWN, and it is the reason to stop here

**What happens to the ten already-scheduled rows when a campaign's senders
change is NOT DOCUMENTED.** The vendor does not say whether they are
rescheduled, reassigned, dropped, or left pointing at a detached mailbox.

That matters more than usual, because those ten rows are the first real
artefact this campaign has ever produced: one per lead, fully rendered copy,
zero unresolved placeholders. Losing them to find out costs the thing we spent
the day getting.

`scripts/grok_provider_research.py` and a follow-up query are asking the
vendor's documentation exactly this. **Until that comes back, the change is
specified and not made.** The 23rd is not a good outcome; re-rolling a working
queue into an undocumented state is a worse one, and the difference between
them is one documentation answer away.

## What this does NOT license

- Raising 2736's daily limit. Forbidden by policy and it would push the
  client's own campaigns onto a mailbox already at its ceiling.
- Attaching 2911 **in addition** to 2736. Two senders on the canonical row is
  refused by `executionguard`, and while EmailBison's per-lead stickiness is
  now documented, the FIRST send's picker is not - so which of the two a given
  prospect got would be observed after the fact rather than chosen.
- Touching the sibling campaigns. They are the client's production and their
  claim on the estate is theirs.
