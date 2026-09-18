# Campaign 489 is live: five approved contacts, a warm mailbox, a US window

Written 2026-09-18. Every number here was read from EmailBison, not inferred.
**ACTIVE IS NOT SENT.** At the time of writing 489 has sent nothing, because
its window has not opened.

## What exists now

    CAMPAIGN_ID       489
    CANONICAL         productive-email-us-cohort-v1
    STATUS            active
    LEADS             5   (all in_sequence)
    SENT              0
    REPLIES/BOUNCES   0 / 0
    SENDER            [3437]  rendulicbojan@gproductive.com
    CAP               5/day, 5 new leads/day
    WINDOW            09:00-17:00 America/New_York, Mon-Fri
    SEQUENCE          3 steps, thread_reply [false, true, true],
                      every step referencing {SUBJECT_1}
    SCHEDULED_EMAILS  0  - the provider has not planned them yet

    487 unchanged:    active, 10 leads, 0 sent, 10 openers still 2026-09-23

## Why a second campaign rather than moving 487

487's only mailbox, 2736, is booked to its 15/day limit on the 18th, the 21st
and the 22nd. Reproduced 2026-09-18 from the complete 183,239-row forward-book
walk, independently of the previous session's table:

    2736   09-18: 15/15    09-21: 15/15    09-22: 15/15    09-23: 10 (its own)

Pause/resume re-plans against the same full mailbox, swapping onto another of
that human's inboxes finds them booked the same days, and the step delay was
ruled out by canary 451. **The date is a consequence of a full mailbox**, so
the answer is a different mailbox - not an edit to a correct campaign.

## The sender, and the trade that was refused

    3437   rendulicbojan@gproductive.com   Bojan Rendulic
           health_of "ok", 1,784 emails sent, 6 of 15 booked today, 9 free
           readiness DEGRADED - lifetime bounce rate 2.1%, at or above the
           2% threshold. SEE THE CAVEAT BELOW; this was missed at selection.

**The same human 487 already sends as**, on a different one of his six
inboxes. His forward book is clear on every day this sequence needs: 09-22
has 11 free, 09-23 onward has 15.

The obvious alternative was rejected. Three inboxes have a completely EMPTY
forward book - 3941, 3930, 3919 - and they are empty because **they have never
sent an email**: created 2026-06-11, `emails_sent_count` 0. That is exactly
the condition `senderinventory.health_of` calls HEALTH_WARMING and
`readiness` calls **DEGRADED**. Taking one would have meant sending the first
email of a cold `.shop` mailbox, from a human none of these five has heard
from, to gain capacity the estate did not need. The system's own vocabulary
already had a word for that inbox class and the word is not "free".

## The caveat I missed when I chose this mailbox

**Sender 3437's lifetime bounce rate is 2.13% - 38 bounces on 1,784 sends -
and `senderinventory.readiness()` returns `('degraded', 'lifetime bounce rate
2.1% is at or above 2%')` for it.** Found after the campaign was already live.

I selected the mailbox on `senderinventory.health_of()`, which answers a
narrower question than I was actually asking: it checks connected, and it
checks warmup-with-zero-sends. It does not look at the bounce rate at all.
`readiness()` is the function that asks the whole question and I did not run
it. For comparison, on the same read:

    2736   487's sender, 11 bounces / 1,757 sends    0.63%
    3948   the canary's sender, 1 / 318              0.31%
    3437   489's sender, 38 / 1,784                  2.13%   DEGRADED

**What was NOT done about it, and why.** The sender was not swapped. DEGRADED
is a warning rather than a refusal - `readiness` has NOT_READY for the latter -
and the three things that make the marginal risk small here are specific:
the rate is LIFETIME over 678 leads contacted rather than anything recent, the
exposure is five addresses, and every one of those five cleared TWO
independent verifiers (ContactOut `valid` plus Reoon
`valid / deliverable / safe_to_send`). A historical bounce rate is a fact
about the lists that mailbox has been pointed at before, not about five
double-verified addresses.

Against that, swapping the sender on a LIVE campaign is a provider write with
its own failure modes, and the alternatives are worse: 2736 is booked to its
limit today, and the three inboxes with an empty forward book are the
never-sent ones rejected above.

So the honest position is: the trade was made on an incomplete check, the
check has now been completed, the answer did not change the decision, and an
operator who disagrees should say so - `bison.detach_senders` and
`attach_senders` are both supported. **If any of the five bounces, this is the
first thing to read.**

## The window, and exactly how far it is from perfect

    monday-friday  09:00-17:00  America/New_York

`bisonfactory._plan` reads `sending_window` off the CAMPAIGN before the
client's, and its own comment says why: EmailBison schedules one window per
campaign, so the window belongs to the cohort. The client default is
Europe/Zagreb - 03:00 Eastern for these people.

Evidence, from `company_facts.offices`, which is what is actually recorded:

    New York NY        Eastern         09:00-17:00 local
    Chicago IL         Central         08:00-16:00 local
    Greensboro NC      Eastern         09:00-17:00 local
    Scottsdale AZ      Arizona, no DST 06:00-14:00 local   <- the deviation
    US, no city        country only    timezone UNKNOWN, not guessed

**Four of five sit in local business hours and the fifth opens at 06:00.**
This is not a resolved cohort and the document does not claim it is:
`geo.propose_cohort_window`, landed today by TASK-227, would correctly return
NO PROPOSAL for a cohort spanning three zones. The narrower claim is the
checkable one - every recipient is in the United States, America/New_York is
the best-supported single window for them, and Europe/Zagreb is the worst.

## The approval, and how it is bound

The operator approved five email contacts on 2026-09-18, conditional on their
being the same five from the approval packet with all evidence unchanged.

**Proven rather than assumed.** The packet was regenerated from live state and
diffed against the copy the operator read: identical except the generation
timestamp line. Fifteen steps, byte for byte.

The approvals themselves are the durable binding, because
`approval.fingerprint` covers channel, subject, body and note - change a word
and the approval stops applying. Recorded here with identifiers hashed,
because `work/` is gitignored for the reason that it names real people:

    record        contact       step  fingerprint        current
    e3cb63532ad5  b3db105bae4c  em1   0c494ccab214d000   True
    e3cb63532ad5  b3db105bae4c  em2   3a59adadc5bd3e56   True
    e3cb63532ad5  b3db105bae4c  em3   5ee3541f802e7fe4   True
    9d2802e5f931  7d22234d9236  em1   8546d2874bb4710a   True
    9d2802e5f931  7d22234d9236  em2   e96400376815826d   True
    9d2802e5f931  7d22234d9236  em3   b8c1c19d9d8cfe52   True
    361967c27122  071bab9229e4  em1   eb65cdb603184034   True
    361967c27122  071bab9229e4  em2   83cc48af986fda44   True
    361967c27122  071bab9229e4  em3   8ff49695c808771e   True
    2c416dea559e  e1bfefed4a7e  em1   dc592ba81d92aead   True
    2c416dea559e  e1bfefed4a7e  em2   605007df12805ba2   True
    2c416dea559e  e1bfefed4a7e  em3   53a7ff65facb86f7   True
    1facb2457f55  b453289bf239  em1   cf2d24e326f73511   True
    1facb2457f55  b453289bf239  em2   98a86d2a6600f0f9   True
    1facb2457f55  b453289bf239  em3   084bc15a242989b8   True

    by        zvonimir@resonategroup.co (operator authorisation 2026-09-18 US cohort)
    at        2026-09-18T05:17:19Z

`approval.is_accountable_approver` refuses a bare token, so `claude`, `qwen`
and `system` could not have signed these.

Double verification holds for all five: ContactOut `valid` plus Reoon
`valid / deliverable: true / safe_to_send: true`, two independent vendors.
Deliverable reads `error` on every one - the unset `DELIVERABLE_RESULT_SHAPE`,
an unmade spending decision - and does not count either way. Evidence ages
2 to 8 days. **There is still no freshness RULE in this build**
(`verification.age_of` says so, and MANUAL-REVIEW.md 9b is where the decision
is asked for), so the ages are reported rather than passed against a
threshold nobody has set.

## The collision that had to be read rather than assumed

**Four of the five were already leads in campaign 481**, the paused historical
campaign. Each read `status: "stopped"`, `emails_sent: 0`. `stopped` is not
`in_sequence`, so they were attachable; zero sent means nobody had ever been
written to. Had any read `in_sequence` the provider would have refused the
whole batch with one unattributed 422 and this campaign would not exist.

See `docs/THE-LOADED-GUN-IS-SMALLER-THAN-IT-LOOKED-2026-09-18.md`: 485 is
already 10 of 10 stopped, and 481's real exposure is 9 `sending_paused` rows
belonging to 487.

## Three defects found on the way, all by gates doing their job

**1. An authorization that is minted and never used leaves a reservation
nothing settles.** CORRECTED on the day it was written: the first reading of
this blamed the killswitch, and that was wrong. `actionledger.reserve` runs
AFTER the killswitch, so a killswitch refusal writes nothing - and the
session's own record proves it, because run A refused all five at the
killswitch and run B then authorized all five, which gate 6 would have refused
as an unsettled retry had run A left anything.

What actually happened: run B authorized all five and each correctly reserved,
then `providerwrites.perform` raised before the transport - `no transport
supplied`, my own caller bug - so nothing reached the provider and nothing
settled the keys. On run C those five `attempted` rows broke the ledger arm of
`collision.staging_artifact_evidence`, the campaign stopped proving itself our
own silent staging, and all five contacts read TOUCHED against the campaign
that had just loaded them.

The all-or-nothing activation shape makes this routine: one authorization per
contact, abort if any refuses, and every one minted before the refusal has
already reserved. HeyReach 605487 hit the same thing - three of four
authorized, the fourth refused - which is why
`settle_abandoned_linkedin_attempts.py` already existed. Settled ABANDONED
against provider truth by `scripts/settle_abandoned_email_attempts.py`, never
FAILED: nobody asked the provider. **Not fixed**; PRODUCT-GAPS 44.

**2. `provider_status_expected` must read `paused` until the campaign runs.**
The readback `executionguard.authorize` requires is taken BEFORE activation.
A row claiming `active` fails `configdiff` on `status` alone - 14 checks, one
failure - refusing the activation it was written to permit.

**3. `perform(expected=None)` reports `WriteUnverified` on a write that
SUCCEEDED.** 489 went `active` and the script reported failure. v3's script
has the same shape. Ambiguity is the worst possible result here, because the
safe response is to READ and the tempting one is to retry.

## The permission, and why it is two tables

    providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS   which provider campaign a
                                                 canonical row may reach
    providerwrites._NEVER_ACTIVATE               481 and 485, refused whatever
                                                 row names them
    executionguard.LIVE_ACTIVATION_GRANTS        whether the ACT was granted

Each names the US cohort and nothing else changed. Neither is sufficient
alone, which is what stops one edit from being enough. `_NEVER_ACTIVATE` is
the new one and it is not redundant: the allowlist resolves a provider id FROM
a row, so it is only as safe as that row's `bison_campaign_id`.

## What has NOT happened

- **No email has been sent by this system, on any campaign, ever.** 489 is
  active with an unopened window; 487 is queued for the 23rd.
- 489's openers are not scheduled. `scheduled_emails` reads 0. Campaign 451's
  row appeared 19 minutes after its window opened and then MOVED overnight
  before firing, so a row is a lookahead and not a receipt - and no row at all
  is a more specific fact than "nothing sent".
- The watcher is armed: `py -3 -u scripts/bison_watch_loop.py --campaign 489
  --interval 180`. It emits QUEUED when the provider first plans this
  campaign, which is the first observable sign it has looked at it.

## Cohort, after

    EMAIL     ALREADY_LIVE 15   READY_NOW 0   NEAR_MISS 0   blocked 36 (approval)
    LINKEDIN  ALREADY_LIVE  3   READY_NOW 0   NEAR_MISS 7   blocked 71

LIVE moved 13 -> 18. The next operator decision is the 7 LinkedIn contacts in
the regenerated near-miss packet. LinkedIn NEAR_MISS fell 12 -> 7 in the same
pass and that part is correct: five of those twelve are people at accounts
the email cohort just went live to, and the account is the unit of outreach.
