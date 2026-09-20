# The client's book is growing into the day 487 is due

> **CORRECTED 2026-09-19T11:35Z by
> `docs/THE-SCHEDULER-PLACES-THE-WHOLE-COHORT-2026-09-19.md`.** This was
> written from a 14%-complete walk of campaign 328 and warned the 23rd could
> be OVERSUBSCRIBED. The completed walk reads it as exactly 15 of 15 - 328's
> five and 487's ten and nothing more. The lower bound was right; the worry
> that it would keep climbing was not. What stands: 328 held ZERO there in
> the complete walk of the 17th and holds five now, so the mailbox has zero
> slack on the day 487 sends. That justifies the watcher. It is NOT a
> prediction that 487 will slip.
>
> **PARTLY REINSTATED 2026-09-20 by
> `docs/THE-LIMIT-BOOKS-SOFT-AND-SENDS-HARD-2026-09-20.md`.** Withdrawing the
> warning was right that nothing had overflowed and WRONG to read a full day
> as reassuring. The send cap is now measured as hard, so exactly 15 of 15
> means the next row booked on that mailbox-day cannot send that day - and
> which of the sixteen sheds is UNKNOWN. Still not a prediction that 487
> slips; a precise statement of the exposure.

Read 2026-09-19T10:15Z, from a fresh forward-book walk started at 09:28Z.
**Addendum to `docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md`**, which
proved the send date is a property of the mailbox. This is the part that
proved not to be static.

## What changed in two days

Sender 2736 carries campaign 487. Daily limit 15. Same sender, same days,
two walks:

                          09-21    09-22    09-23
    WALK OF 2026-09-17    (all three campaigns COMPLETE)
      client 327            15        0        0
      client 328             0       15        0
      our    487             0        0       10
      -------------------------------------------
      total                15/15    15/15    10/15   <- 5 free

    WALK OF 2026-09-19    (327 complete; 328 only 14% walked)
      client 327            15        0        0
      client 328             0       15        5    <- NEW
      our    487                        (not yet re-walked; 10 by direct read)
      -------------------------------------------
      total              >=15/15  >=15/15  >=15/15  <- NONE free

**In the complete walk of the 17th, campaign 328 held ZERO rows on sender
2736 for the 23rd. It now holds at least five**, and that is a lower bound
read from fourteen percent of its book.

## Sender 2736 has no proven headroom left on the day 487 sends

    487's own rows on 2026-09-23, from a direct provider read   10
    client 328's rows on the same mailbox and day, lower bound   5
    ----------------------------------------------------------------
    committed, lower bound                                      15
    sender 2736 daily limit                                     15

A lower bound that already reaches the limit is a full mailbox - that
asymmetry is the whole basis of `senderheadroom`, and it holds here. **2736
is committed to its limit on 2026-09-23 with 86% of campaign 328's book still
unread.**

`senderheadroom` itself still answers REFUSED for that day, correctly: the
fresh walk has not re-walked campaign 487, so the module can only see 328's
five and will not call five-of-fifteen free on an incomplete walk. The
fifteen above is a synthesis of the module's number with a direct provider
read, not the module's own verdict. It will say FULL on its own once the
walk reaches 487.

## What this does and does not predict

**It does not predict that 487 will fail to send.** What the provider's
scheduler does with an oversubscribed mailbox-day is UNKNOWN and nothing here
measures it. Three behaviours all fit what is known: it moves our rows to a
later day, it moves the client's, or it exceeds the nominal limit.

One precedent, and it is weak: 487's earliest row moved from
`2026-09-23T07:12Z` to `2026-09-23T08:41Z` between the 17th and the 18th.
**The day held and the times shifted.** So a same-day reshuffle is OBSERVED.
A day-slip is not, and must not be reported as expected.

    the 17th walk had 328 at zero on the 23rd            MEASURED
    the 19th walk has 328 at >=5 on the 23rd             MEASURED (14% walk)
    487 holds 10 rows on 2736 on the 23rd                MEASURED (provider)
    2736 is committed to >=15 of 15 on the 23rd          DERIVED, sound
    487's rows move to a later day                       UNKNOWN - not predicted
    the scheduler's oversubscription behaviour           UNKNOWN

## Why it matters more than three days of latency

The previous document treated the client's book as a fixed obstacle that puts
our cohorts at the back of a queue. It is not fixed. **It is growing into the
days our campaigns already occupy**, on the same mailboxes, between one walk
and the next.

That changes the shape of the problem. A sender allocator that picks the
soonest free day from a snapshot is choosing against a book that will have
moved by the time the provider plans - which is exactly why
`senderheadroom`'s freshness gate refuses to prove ROOM from a walk older
than twenty-four hours, and why that gate is not conservatism for its own
sake.

It also means the fix is not "pick a better day". **It is a mailbox the
client's campaigns cannot book at all.**

## The test, and it is cheap

Wednesday 2026-09-23 from 08:41Z is 487's ten openers, and it is the first
real batch this system will have sent. Watch it rather than assume it:

- ten rows send on the 23rd -> the mailbox absorbed the contention and the
  limit is softer than 15, or 328's rows went elsewhere.
- the rows move to a later day -> the client's book displaces ours, which is
  a much more serious finding than latency and changes what a sender is for.
- some send and some do not -> the limit is hard and the day is shared
  first-come.

`py -3 scripts/bison_watch_loop.py --campaign 487 --interval 180` was armed
at 2026-09-19T10:20Z for exactly this, alongside the 489 watcher. It emits
`SCHEDULE-MOVED` when the earliest scheduled date changes, which is the
signal that distinguishes the three outcomes above. Monitors are
session-scoped: **check the process list before trusting its silence.**
