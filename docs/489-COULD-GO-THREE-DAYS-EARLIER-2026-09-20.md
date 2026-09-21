# 489 is planned onto a mailbox-day that is full, and Monday has room

> **RESOLVED 2026-09-21T06:54Z. THE FALSIFIER FIRED IN THE PREDICTED
> DIRECTION AND NO WRITE WAS EVER NEEDED.**
>
>     first_scheduled   2026-09-24T13:27Z  ->  2026-09-21T13:34Z
>     scheduled rows    5 (ids 223361xx)   ->  8 (ids 223411xx, all new)
>     provider says     today 3 emails, tomorrow 2, day after none
>
> The end-of-day scheduler run re-planned 489 **three days earlier, on its
> own**, exactly as the update below predicted. The row ids are entirely new,
> so the old plan was discarded and rebuilt rather than amended.
>
> **The pause/resume this document describes was correctly refused and was
> genuinely unnecessary.** Had it been performed on Sunday it would have been
> an unauthorized write that took credit for something the provider did by
> itself - and `resume_campaign` fails a campaign whose window is days away,
> so it could have left 489 worse than slow.
>
> It was surfaced by `bison.sending_schedule`, integrated from TASK-236
> minutes earlier. Nothing in this repository could previously ask the
> provider what it would actually send; the first time it did, the answer had
> already changed.
>
> 489's first real emails are due **today, 13:34Z (09:34 America/New_York)**,
> inside its own window. That is a provider statement, not an inference, and
> it is not a send until the provider confirms one.

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

## UPDATE, same evening: it may re-plan itself, and no write may be needed

Two things found after the above was written, both of which narrow the
recommendation rather than change the measurement.

**1. The scheduler does not only run on resume.** `docs/GROK-SCHEDULING-2026-09-20.md`
records it as DOCUMENTED, with a source URL: the campaign scheduler runs
**"every time the campaign is resumed, and at the end of every sending
day"** - the pause/resume trick is described there only as the way to force a
run *before* the end of the sending day.
<https://docs.emailbison.com/campaigns/overview>

489's schedule is Mon-Fri 09:00-17:00 America/New_York, so **its next
scheduler run happens on its own at the end of Monday's sending day**, with
no write from us. If the placement rule is "first day that fits the whole
cohort" and Monday's book is still open when it runs, 489 re-plans earlier by
itself.

That makes the unauthorized pause/resume not merely forbidden but very likely
unnecessary. **Wait for Monday's end-of-day run before proposing any write.**

**2. There is a documented read for what will actually send**, which this
repository was not using:

    GET /api/campaigns/{id}/sending-schedule?day=today|tomorrow|day_after_tomorrow
    GET /api/campaigns/sending-schedules

Asked of both campaigns on 2026-09-20T20:0xZ, all three days:

    487  today / tomorrow / day_after_tomorrow   400 "No emails scheduled for this period"
    489  today / tomorrow / day_after_tomorrow   400 "No emails scheduled for this period"

Read it carefully, because it is weaker evidence than it looks. Today is
Sunday; 487 is PAUSED so it has no built volume by construction; and the
window only reaches Tuesday the 22nd while 489's first send is planned for
Thursday the 24th. So **all six answers are consistent with the picture above
and none of them contradicts it.** What they establish is narrow and still
worth having: as of tonight, the provider has no built sending volume for
either campaign on Sunday, Monday or Tuesday.

This endpoint is the authoritative answer to "what will actually send", which
is a different question from `first_scheduled` on the campaign row, and
nothing here reads it yet. Wiring it into the 487 and 489 watchers is the
cheapest observability win available and is queued as engineering work.

## The falsifier this creates

**At the end of Monday's sending day, 489's scheduler runs.** Re-read
`first_scheduled` on Tuesday morning:

- moved earlier -> the end-of-day run re-plans against the current book, the
  latency is self-correcting, and no write should ever have been considered.
- unchanged at 09-24 -> the plan is sticky once made, the end-of-day run only
  places NEW leads, and the question of an authorized re-plan becomes real.

Either way it is answered by reading, on Tuesday, for free.

## What should happen

1. **Do nothing to 489 today, and probably nothing at all.** It is healthy,
   enrolled and scheduled, its scheduler runs on its own at the end of
   Monday's sending day, and the falsifier above resolves on Tuesday by
   reading. Three days of latency is a cost; a failed campaign is a loss.
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
