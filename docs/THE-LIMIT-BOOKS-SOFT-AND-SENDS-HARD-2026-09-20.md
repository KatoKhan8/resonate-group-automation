# `daily_limit` is soft at booking and hard at sending

Read 2026-09-20T02:40Z from 582 utilisation samples spanning
2026-09-17T10:58Z to 2026-09-20T02:35Z, 225 mailboxes.

**This CORRECTS `docs/THE-SCHEDULER-PLACES-THE-WHOLE-COHORT-2026-09-19.md`**,
which said "`daily_limit` is not a hard provider cap" on the strength of one
forward-book reading. That statement was too broad and the correct one is
narrower, better evidenced, and has a sharper consequence.

## The two measurements disagree, and both are right

**BOOKING exceeds the limit.** The complete forward-book walk reads sender
3437 at **16 of 15** on 2026-09-21, from client campaign 352 alone.

**SENDING does not.** Per-sender counter movement, per UTC day, distribution
of how many each mailbox actually sent:

    2026-09-17   {1:15, 2:4, 3:3, 5:1, 6:5, 8:1, 9:2, 10:1, 11:1, 12:1, 15:47}
    2026-09-18   {1:13, 2:1, 3:2, 4:7, 5:1, 6:9, 7:12, 8:7, 9:4, 10:4,
                  12:1, 14:4, 15:9}
    2026-09-19   {1:17, 2:11, 3:11, 4:1, 7:1, 14:1}
    2026-09-20   {1:9}

**On the 17th, FORTY-SEVEN mailboxes sent exactly 15 and not one sent more.**
Nine more piled up at exactly 15 on the 18th. Across all four days and 225
mailboxes the maximum observed is 15, which is the limit, and there is
nothing above it.

## Why under-sampling does not explain the wall

The sampling has gaps and every daily figure above is a LOWER BOUND - the
monitor covered 10:58-23:57 on the 17th, 00:02-15:50 on the 18th (it died at
15:50 and was re-armed on the 19th), 09:52-23:59 on the 19th. **No day is
sampled midnight to midnight.**

That asymmetry runs one way, exactly as it does for the forward-book walk:
**missing samples can only push an observed count DOWN.** They cannot
manufacture a ceiling. A soft cap would scatter observations above 15 as well
as below it, and a mailbox that truly sent twenty would have to have had five
or more of its sends fall in the gaps while precisely fifteen landed in the
sampled window - forty-seven times over, on the same number.

A pile-up AT the limit with nothing above it is the signature of a cap being
applied. **The wall is evidence; the gaps only make the counts conservative.**

## The model, and it is more useful than "soft cap"

    the provider BOOKS past daily_limit      MEASURED (16 of 15, complete walk)
    the provider SENDS to daily_limit        MEASURED (47 mailboxes at exactly
                                             15, none above, 4 days, 225
                                             mailboxes)
    an overbooked day therefore sheds rows   INFERRED, and it follows directly
    WHICH row sheds                          UNKNOWN - ours or the client's
    whether a shed row slips to the next
      sending day or is dropped              UNKNOWN

Scheduling and sending are governed differently. A `scheduled_emails` row is
a booking, and the previous handoff already said a row is a lookahead rather
than a receipt - canary 451's moved overnight before it fired. This says what
the queue does when it is over-full.

## THE CONSEQUENCE, and it reinstates a concern I withdrew

`docs/THE-CLIENTS-BOOK-IS-GROWING-INTO-OUR-DAY-2026-09-19.md` warned that
sender 2736 could be oversubscribed on the 23rd. The completed walk read it
as exactly 15 of 15 and I withdrew the warning as not having materialised.

**Exactly 15 of 15 means ZERO SLACK on the day 487 sends**, and the send cap
is now known to be hard. So:

- the client's campaign 328 held ZERO rows on that mailbox-day in the
  complete walk of the 17th and holds FIVE now. The book grows.
- 487 holds the other ten.
- **the next row anybody books on 2736 for 2026-09-23 is one that cannot
  send that day**, because the mailbox will stop at fifteen.
- which of the sixteen is the one that does not go out is UNKNOWN, and
  nothing measured says the provider prefers its own campaign or ours.

That is not a prediction that 487 slips. It is a precise statement of the
exposure: **487's ten openers occupy a mailbox-day with no remaining room, on
a cap that is enforced.** The earlier withdrawal was right that nothing had
overflowed yet and wrong to treat a full day as reassuring.

The 487 watcher is armed and emits `SCHEDULE-MOVED`. That is the signal.

## What must NOT be done

**Do not test this by overbooking one of our own campaigns.** The mailboxes
are shared with a client and their deliverability is not ours to spend on an
experiment. Two free observations are already scheduled:

- **Monday 2026-09-21**: sender 3437 is booked 16 against a limit of 15 by
  the client's own campaign. Watch whether 15 or 16 send. That answers the
  shedding question at no cost to us.
- **Wednesday 2026-09-23**: 487's ten on a mailbox at exactly its limit.

## What this changes about capacity planning

`senderheadroom` calls 16-of-15 FULL, which remains the correct refusal, and
the vocabulary now has a precise meaning rather than an assumed one:

**FULL means the mailbox will not send more that day.** That is stronger than
what the module claimed for itself yesterday - it was written to mean "at or
past the number we treat as the limit" with the provider's behaviour unknown.
The measurement has now caught up with the refusal.

It also means **a booking is not capacity.** A day can hold more rows than it
will send, so counting scheduled rows against a limit is the right way to ask
"will another fit" and the wrong way to ask "what will go out". Those are
different questions and this repository now has evidence for both.
