# Why 493, 496, 497 and 498 first send on the 24th

Read-only. Asked by the operator on 2026-09-22: is it mailbox daily capacity
consumed by the client's campaigns, the window, or the provider's planner?

**It is the mailboxes, and the forward book says so without ambiguity.**

## The measurement

`work/forward-book-census.json`, walked 2026-09-21T18:50Z, complete, covering
every campaign that can book a mailbox: 327, 328, 352, 481, 487, 489. Cells
are the campaign's own named mailboxes that still have room that day.

    camp  human       mailboxes   09-22  09-23  09-24  09-25   first send
    491   kresimir           63      48     48     48     48   TODAY 13:03Z
    492   bernarda           47      30     29     29     29   TODAY 13:55Z
    494   fran               12      11     11     11     11   TODAY 14:13Z
    495   tomislav           11       7      7      7      7   TODAY 13:02Z
    493   ivan               13       2      0      0      0   09-24 13:20Z
    496   bojan               5       0      0      0      0   09-24 08:10Z
    497   jakov               2       0      0      0      0   09-24 08:33Z
    498   luka                1       0      0      0      0   09-24 07:09Z

The split is exact. Every campaign sending today has mailboxes with room
today. Every campaign waiting has none, or nearly none.

**Not the window.** 498's window is Europe/Zagreb, which opened at 07:00Z
this morning — the earliest of the three cohorts. It is still the one
waiting longest. 493 shares America/New_York with 491, 492 and 494, which
all send today.

**Not the planner.** The planner placed each campaign on the first day its
mailboxes could carry it; that is the behaviour
`docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md` already records, and this
is another instance of it rather than a new fact.

**It is the client's own campaigns.** 327, 328 and 352 have those inboxes
booked to their 15/day limit. jakov has two attested mailboxes and luka has
one; neither has any slack at all.

## What this does NOT prove, stated because the number matters

Our book shows **zero** room for those four on the 24th as well, and the
provider scheduled them there anyway. Two honest readings and this walk
cannot separate them: the census is fourteen hours old and the client's
campaigns may have finished rows since, or a booking counted on a later day
is one that will have been spent by the time that day arrives. The census
does not carry 491-498's own new bookings either, because they did not exist
when it ran.

So: **why they wait is settled. The exact day the provider chose is the
provider's, and our book does not independently confirm room on it.** A
fresh census after today's sends would.

## The consequence for sizing, which is the useful half

**2,310 a day is a cap, not a throughput.** It is 154 attested mailboxes ×
15, and it assumes every mailbox is free every day. Today the free ones are:

    48 + 30 + 11 + 7 + 2 + 0 + 0 + 0  =  98 mailboxes with room
    98 × 15                           =  1,470 first steps actually available

Batch 3 should be sized against the second number. Enrolling against the cap
would put leads on jakov and luka, whose three mailboxes between them are
fully booked by the client for the next four days, and those leads would sit
enrolled-but-unsent while the pacing rule reported them as fine.

**The pacing rule needs the forward book, not the mailbox count.** That is
one line in the batch builder and it is the difference between a backlog we
chose and one we did not notice.
