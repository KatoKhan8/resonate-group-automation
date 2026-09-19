# The rule is the whole cohort, and it predicts both campaigns exactly

Read 2026-09-19T11:35Z from a **COMPLETE** forward-book walk: 327, 328, 352,
487 and 489, 184,284 rows, every campaign `complete: true`, oldest walk 1.5h
old and covering every active campaign.

**This settles 489's cause and CORRECTS two things written earlier today.**

## The complete book

    sender 2736 (limit 15)      09-21   09-22   09-23   09-24
      client 327                  15       0       0       0
      client 328                   0      15       5       0
      our    487                   0       0      10       0
      ----------------------------------------------------------
      total                     15/15   15/15   15/15    0/15

    sender 3437 (limit 15)      09-21   09-22   09-23   09-24
      client 352                  16      13      14       8
      our    489                   0       0       0       5
      ----------------------------------------------------------
      total                     16/15   13/15   14/15   13/15

## CORRECTION 1: the rule is not "first day with a free slot"

`docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md` said 487 landed on "the
first day its mailbox had a single free slot" and expected 489 to have landed
on the 22nd. **That rule is refuted by the complete data.** Sender 3437 had
two free slots on the 22nd and one on the 23rd, and 489 went to the 24th
anyway.

The rule that fits is **the first sending day with room for the WHOLE
COHORT**. Tested as a counterfactual - each campaign's own rows removed from
the book, then asked where a cohort of that size would first fit:

    campaign 487   cohort of 10   sender 2736
      09-21 free  0    09-22 free  0    09-23 free 10    09-24 free 15
      PREDICTED 2026-09-23      ACTUAL 2026-09-23      MATCH

    campaign 489   cohort of 5    sender 3437
      09-21 free -1    09-22 free  2    09-23 free  1    09-24 free  7
      PREDICTED 2026-09-24      ACTUAL 2026-09-24      MATCH

**Two campaigns, different senders, different cohort sizes, different
windows, both predicted exactly.** The old rule gets 487 right by coincidence
- ten needed and ten free is the same answer either way - and gets 489
plainly wrong.

### How strong this is, stated honestly

It is a RETRODICTION against a snapshot taken after the fact. The book is
walked today; 489 was planned at 2026-09-18T21:03Z and 487 on the 17th, and
the client's campaigns have inserted rows since. Campaign 352 held 4 rows on
the 22nd in the walk of the 17th and holds 13 now, so the book at planning
time is not recoverable.

So the match cannot rule out "the book simply looked different then". What
makes it more than a coincidence is that it is an EXACT hit on two different
cohort sizes where the sizes are what discriminate the two rules.

    the whole-cohort rule fits both campaigns exactly    MEASURED, retrodicted
    the single-slot rule is refuted by 489               MEASURED
    the book at planning time                            UNKNOWN, unrecoverable
    the rule is causal rather than coincidental          INFERRED, two points

`senderheadroom.earliest_day` already takes `need` and already implements
these semantics, which was designed before the rule was known and turns out
to be the right shape. `verdict(..., need=N)` is the whole-cohort question.

## CORRECTION 2: the contention warning was overstated

`docs/THE-CLIENTS-BOOK-IS-GROWING-INTO-OUR-DAY-2026-09-19.md` was written
from a 14%-complete walk of campaign 328. It reported sender 2736 at ">=15 of
15" on the 23rd with 86% of the book unread, and warned the day could be
OVERSUBSCRIBED.

**It is not. The complete walk reads exactly 15 of 15**: 328's five and
487's ten, and nothing further. The lower bound was correct and the worry
that it would keep climbing did not materialise.

The better reading is the opposite of alarming: **the scheduler packed 487's
ten into exactly the ten slots 328 had left**, which is what the whole-cohort
rule predicts and is evidence the limit is being respected rather than
strained.

What stands from that document is narrower and still true: 328 held ZERO rows
on that mailbox-day in the complete walk of the 17th and holds five now, so
the client's book does grow into days our campaigns already occupy. **The
mailbox now has zero slack on the 23rd**, so any further row the client books
there is the one that creates real contention. That is worth the armed
watcher, and it is not a prediction that 487 will slip.

## THE NEW FACT, and it is the important one

**Sender 3437 is booked 16 of 15 on 2026-09-21. Campaign 352 alone exceeds
the mailbox's own `daily_limit`.**

That is a single client campaign booking past the cap this system treats as
the ceiling on a mailbox. So:

- `daily_limit` is **not a hard provider cap**, or not one enforced at
  planning time. Something can overbook a mailbox.
- Our model of FULL is therefore SOFTER than assumed. `senderheadroom` calls
  16-of-15 FULL, which stays the right refusal - it will not add an
  eleventh - but "FULL" means "at or past the number we treat as the limit",
  NOT "the provider will refuse more".
- Whether the overbooked 16th actually sends on the 21st is **UNKNOWN**, and
  it is cheaply observable on Monday.

This matters more than either correction above, because every capacity number
in this system rests on `daily_limit` meaning something. One campaign is
already past it.

    352 books 16 on a mailbox whose limit is 15       MEASURED
    daily_limit is not enforced at planning time      INFERRED, one case
    whether all 16 send on the 21st                   UNKNOWN - watch Monday
    whether our campaigns could also overbook         UNKNOWN - NOT to be
                                                      tested deliberately

**Do not test this by overbooking one of our own campaigns.** The mailboxes
are shared with a client and their deliverability is not ours to spend on an
experiment. Monday's observation of 352 is free.

## What follows

1. **489's date is explained and no longer needs the stale-walk story.** The
   earlier account - that the client's book grew between the walk and the
   planning - is still probably true (352 went 4 -> 13 on the 22nd) but it is
   no longer load-bearing. The whole-cohort rule explains the 24th directly.
2. **A cohort's SIZE is a scheduling input, not just a safety cap.** Five
   leads fit three days earlier than ten do on a contended mailbox. Splitting
   a cohort across mailboxes buys latency, and that is a real lever the
   allocator does not currently pull.
3. **`daily_limit` needs re-examining before it is trusted as capacity.**
