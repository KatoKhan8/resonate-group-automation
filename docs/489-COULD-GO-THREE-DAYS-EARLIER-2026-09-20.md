# 489 is planned onto a mailbox-day that is full, and Monday has room

2026-09-20, Sunday evening. Read from the providers and from a census that
covers every campaign that can book a mailbox - which, until this afternoon,
no census had done since the 19th.

**Nothing in this document has been acted on.** The write it points at is not
authorized and is not performed. See "What is NOT authorized" below.

## The finding

    sender 3437, 489's only mailbox, limit 15, cohort of 5

    Mon 2026-09-21    3 of 15 booked    12 free    ROOM
    Tue 2026-09-22    0 of 15 booked    15 free    ROOM
    Wed 2026-09-23   12 of 15 booked     3 free    FULL
    Thu 2026-09-24   15 of 15 booked     0 free    FULL   <- 489 is planned here

489's first send is scheduled for **2026-09-24T13:27Z**, which is 09:27 in
`America/New_York` - the campaign's own timezone, and the first minute of its
09:00-17:00 window. The campaign is `active`, holds 5 leads `in_sequence`, and
has sent nothing.

**Monday and Tuesday both have room for the whole cohort.** The plan is three
days later than the mailbox requires.

## Why Thursday, and why it is full

Thursday reads 15 of 15 **because 489's own five rows are among them** - 10
client rows plus our 5. That is the signature of a scheduler that ran when the
book looked different: at plan time it searched forward for the first day that
could take all five, found Thursday, and booked it. The rule in
`THE-SCHEDULER-PLACES-THE-WHOLE-COHORT` held then and the placement was correct
when it was made.

What changed is the client's book. Sender 3437's Monday commitment fell from
**16 on the 19th to 3 on the 20th**, and Tuesday from 13 to 0. The client's
campaigns release and re-plan their own rows daily - the same volatility already
recorded for 327, which grew 48,759 to 49,627 rows in twenty-four hours. It
moves in both directions.

So this is not a defect in the scheduler. **It is a stale plan against a book
that has since opened up**, and nothing re-plans a campaign that is already
active and waiting.

## This was invisible until the census was fixed today

The census default walked three CLIENT campaigns and none of ours, so the walk
did not cover 489, and `senderheadroom` correctly answered REFUSED for every
mailbox on every day. REFUSED IS NOT ROOM - so before the fix in `d321c2ef`
this question could not be asked at all, in either direction. The first
version of this analysis got ROOM only by feeding `coverage` the same campaign
list as the walk, which makes the check pass vacuously. That was wrong and the
correct answer at that moment was REFUSED.

The numbers above come from a walk covering all six campaigns that can book:
327, 328, 352, 481, 487, 489. Complete, covering, and 6.8 hours old.

## What it would take, and why it is not done

EmailBison re-plans a campaign **when it is resumed** - documented, with a
source URL, in `docs/GROK-SCHEDULING-2026-09-20.md`. So a pause followed by a
resume inside Monday's window would re-plan 489 against Monday's book and the
five openers could go out that day instead of Thursday.

**That write is not authorized, and this document is not a request to
reinterpret the authorization.**

`docs/OPERATOR-AUTHORIZATION-2026-09-20-RESUME-487.md` names it explicitly
under what is NOT authorized:

    resuming 489            it is healthy and needs no intervention
    pause/resume as a
      scheduling nudge      the standing rule stands: do not blindly pause
                            or resume a campaign

Both lines were written about exactly this manoeuvre. The grant is for 487,
which is paused by an accident and whose resume undoes that accident; 489 is
healthy, and pausing a healthy live campaign to make it faster is the
definition of the thing the rule forbids.

There is also a measured risk that is not theoretical. `resume_campaign`'s
docstring records that a campaign whose next sending window is days away
**fails within seconds and moves to `failed`**. 489's next window opens Monday
07:00 New York time - fine on Monday, and a pause performed at the wrong hour
could leave a healthy campaign strictly worse than slow.

## What should happen

1. **Do nothing to 489 today.** It is healthy, enrolled and scheduled. Three
   days of latency is a cost; a failed campaign is a loss.
2. **Monday belongs to 487.** Its recovery is authorized, preflighted, and
   Monday is now provably the ONLY day its cohort of ten fits - sender 2736
   reads ROOM 15 free on Monday and FULL on both Tuesday and Wednesday. That
   write should not be crowded by a second, unauthorized one on the same
   morning.
3. **If the operator wants 489 earlier, it is a decision they take**, inside
   Monday's New York window, with the same shape as the 487 grant: provider
   truth re-read immediately before, `expect_leads=5`, and the acceptance test
   being five rows `in_sequence` on an earlier date - not the campaign reading
   `active`.
4. **The general fix is not a nudge.** A campaign that waits because the book
   was full when it was planned, on a book that empties, is a recurring
   condition rather than an incident. What is missing is a monitor that
   compares each live campaign's planned first-send date against the current
   covering census and reports a gap. That reports; it does not write. It is
   the durable version of this document and it belongs in the backlog.

## Falsifiers

- If sender 3437's Monday commitment climbs back above 10 before Monday, the
  gap closes on its own and there is nothing to decide. The book moves daily
  and this reading is 2026-09-20T12:44Z.
- If 489's five rows turn out not to be the five counted on Thursday, the
  15-of-15 reading is wrong. The per-row endpoint returns
  `scheduled_at: None` and `sender_email_id: None` on all five, so the
  Thursday date comes from the campaign-level readback and the sender
  attribution comes from the census, not from the rows themselves. **That is
  the weakest link in this analysis and it is the thing to check first.**
