# Operator authorization — 2026-09-21 — first-wave push, batch 1

Recorded verbatim. Nothing in this file is a paraphrase, and nothing below the
grant reinterprets it.

---

OPERATOR AUTHORIZATION, 2026-09-21, Zvonimir. First-wave push.

AUTHORIZED: enroll the first 500 READY leads from today's S5 run into
production campaigns, ONCE, as batch 1, under every condition below.

CONDITIONS, all binding:
1. READY means: two independent fresh verifications passed (pair
   recorded per lead), MX known_allowed or unknown_provider, collision
   and suppression cleared fail-closed, copy rendered from approved
   Productive templates with the threading invariant, ICP verdict IN.
   Nothing HELD or flagged enters the batch.
2. Campaigns: one EmailBison campaign per attested human, 8 max. If
   arity 8f4406e1 is merged, each campaign names ALL of that human's
   attested connected mailboxes; if not, its single healthiest mailbox by
   lifetime bounce. Cap 15 first-step sends per mailbox per day. No
   Casey Wright, Morgan Ellis or Riley Parker mailbox anywhere.
3. Sequence: threaded 3-step, step 1 subject only, steps 2+
   thread_reply=true, recipient-local sending windows, timezone cohorts
   grouped, no inferred timezone where the country spans several.
4. LinkedIn: only for leads with a LinkedIn URL, on fresh unbound lists,
   one HeyReach campaign per attested seat, cross-channel human match not
   required, conservative allocation on seats shared with the client.
5. Write-back campaign ids and channel status per lead; never
   double-enroll; the 306 store-overlap domains stay out of batch 1.
6. Before the provider write, post the batch stats to
   #resonate-notifications and the terminal: READY count, per-campaign
   counts, per-human mailbox count, total first-step capacity per day,
   verification pairs, HELD by reason, credits spent. Then wait 15
   minutes. If I do not veto in that window, push.
7. After the push: report enrolled per campaign, provider-confirmed
   scheduled rows per campaign, first scheduled send per campaign, and
   state explicitly that enrolled is not sent.
8. Hard stops apply before and after: bounce > 2% on any mailbox over
   7 days, any spam complaint, a reply not stopping the other channel
   within 15 min, unsubscribe not propagated, verification weakened,
   credit cap reached. Any one halts the push or pauses the batch and
   posts CRITICAL.

NOT AUTHORIZED: a second batch, any write to 487 or 489, any pause or
resume, changing approved live copy, any push if READY < 500 without a
separate line from me. If READY is between 300 and 499 by 21:00 Zagreb,
send me the stats and ask; do not push.

---

## Status of this grant

    STATE        RECORDED, NOT YET EXERCISED, as of 2026-09-21T14:0xZ
    SPENDS       once, on batch 1, and then it is spent
    PRECONDITION S5 has not started. READY is 0. Nothing may be pushed.

## What this session must check before exercising it

Each of these is a condition above, restated as the check that proves it.
None may be assumed from an earlier run.

    cond 1  every lead carries TWO verification provider names, from the
            recorded order (ContactOut, Reoon, Deliverable), both fresh.
            A supplier's "Verified" column is not one of them - the input
            file's own column is the vendor's word and was rejected.
    cond 1  MX is known_allowed or unknown_provider. known_blocked, no_mx
            and dns_failure are all excluded - dns_failure is HELD because
            we could not ask, which is not the same fact as no mail.
    cond 2  the mailbox set is drawn from the 159 attested. Casey Wright,
            Morgan Ellis and Riley Parker are EXCLUDED by the register and
            their 51 mailboxes may not appear even as a fallback.
    cond 2  whether arity 8f4406e1 is MERGED decides one mailbox or all of
            a human's. Check the merge, do not assume it.
    cond 5  the 306 domains already in the store are out. They are the
            overlap S1 found and they are the double-enrolment risk.
    cond 6  stats posted AND fifteen minutes elapsed. The veto window is
            not a formality and the clock starts at the post, not at the
            decision to post.
    cond 8  the hard stops are checked BEFORE the write as well as after.

## The two numbers that decide whether it can be exercised at all

    READY >= 500                 push, after cond 6
    READY 300-499 at 21:00 Zagreb  send stats and ASK. Do not push.
    READY < 300                  no push, no question, report only.

## What it does not authorize, restated because it is the expensive half

A second batch. Any write to 487 or 489 - both are live and 489 sent its
first email today at 13:34:48Z. Any pause or resume of anything. Any change
to approved live copy. And no push at all below 500 READY without a separate
line from the operator.
