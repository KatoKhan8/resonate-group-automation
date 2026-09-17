# The mailbox was never the problem. It had thirteen of fifteen left.

> **THIS TITLE IS WRONG AND THE CORRECTION IS AT THE BOTTOM.** Measured over
> two hours, sender 2736 had used 2 of 15. Measured over the whole day it had
> used at least 11. The conclusion below was drawn from a partial window and
> is reversed by the same sampler six hours later. Read the CORRECTION section
> before quoting anything above it.

2026-09-17, measured over 1h52m of an open sending window by
`scripts/bison_mailbox_utilisation.py`, which differences the provider's
lifetime `emails_sent_count` into a send rate.

## The claim this falsifies

`docs/PRODUCTION-HANDOFF-2026-09-17.md`, on campaign 487:

    REAL capacity    NOT 15/day. 2736 also serves ACTIVE campaigns 352, 328
                     and 327 - 173,558 emails between them. The limit is per
                     MAILBOX, so 487's share is a fraction of 15 and today
                     it is zero.

Plausible, never measured, and wrong.

## The measurement

    window                2026-09-17T10:58Z -> 12:50Z   (1h52m, window open)
    estate                225 mailboxes
    mailboxes that sent   46
    emails sent           94

    sender 2736           +2   lifetime 1742 -> 1744
    campaign 487          emails_sent 0, scheduled rows 0,
                          updated_at frozen at 2026-09-17T10:45:10Z - which
                          is OUR OWN last write, not the provider's

**Sender 2736 sent two emails during the window.** It is connected, it is
working, and it used 2 of its 15. Thirteen were left. Campaign 487 - active,
ten leads enrolled, holding that exact mailbox - received none of them, and
the provider did not touch its campaign row once in two hours while 46 of its
peers were sending.

So the mailbox is not saturated, the daily cap is not binding, and "487's
share is zero" was a description of the symptom rather than its cause. The
sharing is real. The starvation is not caused by it.

## What is left standing

One explanation survives contact with this: **the provider never picked 487
up.** It is not choosing 487 and finding no room; it is not looking. Two
independent signals agree and neither was being watched until today:

- `scheduled_emails` is a LOOKAHEAD queue. Canary 451's row appeared
  19 minutes after its window opened, carrying a future `scheduled_date`, and
  fired the next day. 487 has never had a row.
- `updated_at` moves on campaigns the provider is working - 352 and 328 move
  theirs every few minutes. 487's has not moved since we wrote to it.

The standing hypothesis is that this provider assigns a day's leads at or near
the window opening, and 487 was activated at 10:07 local on its first attempt
and restored at 12:46 local on its second - both after 09:00 Europe/Zagreb.

## The test, tomorrow morning, and its falsifier

487 is active NOW and will still be active when the window opens. So the
hypothesis makes a prediction with nothing left to explain it away:

**Between 07:00Z and 07:30Z on 2026-09-18, `bison_watch_loop` should emit
`TOUCHED` and then `QUEUED` for 487.**

If the window opens and both stay silent, the hypothesis is dead. Discard it
and investigate; do not extend it another day. A standing explanation with no
way to be wrong is how a stalled campaign gets explained away for a week.

**Do not pause, re-approve, re-attach or re-activate 487 before then.** Every
one of those resets the experiment, and the experiment is cheaper than the
next guess.

## What NOT to do about it

Attaching one of the three uncommitted mailboxes would change the variable
mid-experiment and would be attaching an inbox with ZERO lifetime sends - a
reputation risk rather than spare capacity - to ten real prospects. And it
would not test anything, because the campaign the provider is not looking at
would still be the campaign the provider is not looking at.

The estate is running at roughly 5% of its nominal 3,375/day. Capacity is not
what is wrong here.

---

## CORRECTION, 2026-09-17T17:42Z — THE TITLE IS WRONG

**Everything above was measured over 1h52m and the conclusion did not survive
the rest of the day.** It is left standing rather than deleted, because the
mistake is the useful part: a two-hour window was treated as a day.

Same sampler, same mailbox, window extended to 6h44m:

    window                2026-09-17T10:58Z -> 17:42Z
    estate                531 emails from 73 of 225 mailboxes
    sender 2736           +11   lifetime 1742 -> 1753

**Sender 2736 sent ELEVEN today, not two, against a daily_limit of 15.** And
that is a floor, not a total: sampling began at 10:58Z and whatever it sent
between the window opening at 07:00Z and then is not counted. So 2736 is at
eleven-of-fifteen or worse, and campaign 487 received none of them.

The mailbox IS close to its cap. The contention IS the constraint. The
paragraph above that says "the cap was not binding and the sharing was not the
cause" was true of the first two hours and false of the day.

**And it makes the 09-23 schedule make sense.** 487 needs ten slots on one day
from a mailbox that burns eleven or more of fifteen on campaigns 327, 328 and
352. The first day with ten free is not tomorrow. That is now the leading
explanation for the six-day gap rather than a candidate, though still not
proven: no route on this provider lists a mailbox's forward book.

### What this changes

`production_status.py` was edited at 13:00Z to stop "inferring a share from
contention", on the strength of the two-hour number. The edit is still right
in FORM - it points at the sampler instead of asserting a share - but its
worked example is wrong and is corrected in the same commit as this.

**The lesson is the one CLAUDE.md already states and this broke anyway:**
an intermittent or partial measurement is diagnosed, never generalised. A send
rate sampled across two hours of a nine-hour window is a sample, and the
sampler was built precisely because a lifetime counter says nothing about
today until it is differenced - then its first answer was read as if the
differencing were finished.

### A separate finding from the same sample

**Fifteen of the 225 mailboxes read `status: Not connected`.** Every one has
real history - 328 to 371 lifetime sends - and every one sent ZERO today. They
are not capacity and they have not been capacity for some time; nothing in
this system had noticed, because the roster reports a `daily_limit` of 15 for
all 225 regardless of whether the mailbox can send at all.

    nominal    225 x 15  = 3,375/day
    connected  210 x 15  = 3,150/day
    observed   531 in 6h44m, ~17% of the connected nominal

That gap is an operator item: fifteen inboxes in the client's estate are
disconnected and their reconnection is worth more than any sender the three
uncommitted mailboxes could offer.
