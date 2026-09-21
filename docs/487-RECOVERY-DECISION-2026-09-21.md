# 487 — recovery decision, 2026-09-21

## The recommendation is to do nothing until ~16:00Z, and here is why

487 is `active`, ten leads `in_sequence`, `emails_sent` 0, and it holds ZERO
scheduled rows. Two independent provider reads agree, taken at 09:37Z:

    bison.scheduled_emails(487)            -> 0 rows
    bison.sending_schedule(487, today)     -> SendingScheduleEmpty
    bison.sending_schedule(487, tomorrow)  -> SendingScheduleEmpty
    bison.sending_schedule(487, day_after) -> SendingScheduleEmpty

The second is the stronger read: it is the provider's own forward-looking
view of what it intends to send, not our inference from a row count. 489
answers the same call with `emails_being_sent: 3` today and 2 tomorrow, so
the endpoint is working and 487's silence is a real silence.

**THE 15:00Z DEADLINE IN THE HANDOFF IS THE WRONG CLOCK.** It reads 15:00Z -
the close of 487's Mon-Fri 07:00-15:00Z window - as the moment an empty queue
becomes a confirmed new fault. But the close of the sending day is also the
moment the DOCUMENTED rebuild trigger fires. Grok's research against
EmailBison's docs and the instance OpenAPI (`docs/GROK-EMPTY-QUEUE-2026-09-21.md`)
establishes that the scheduler runs in exactly two documented cases: on
resume, and at the end of every sending day. Reading at 15:00Z calls a fault
a minute before the scheduler is due to run.

489 is the precedent and it is ours, not a vendor claim: its window closes
21:00Z and its rebuild landed at 22:01:05Z, about an hour after close, taking
it from 5 scheduled rows to 8 and moving its first send from 09-24 to 09-21.
Nobody wrote anything to make that happen.

**So the read that matters is ~16:00Z, not 15:00Z**, and the outcomes are:

    rows appear by ~16:30Z
        -> the end-of-day cycle did its job. No write was ever needed, and
           the three days of empty queue were three days of nobody waiting
           long enough past a window close.
    still zero at 16:30Z
        -> the end-of-day trigger has now been given its chance and produced
           nothing. THAT is the new fault, and only then is the question
           below live.

`scripts/bison_watch_loop.py --campaign 487 --interval 180` is running and
prints `QUEUED` on the transition, so this needs no new machinery.

## What is NOT available, and it is worth writing down

Grok's finding closes off the obvious ideas before anyone spends a day on
them. NOT DOCUMENTED as scheduler triggers: attaching leads, attaching or
removing sender emails, `PUT /api/campaigns/{id}/schedule`, sequence updates,
`PATCH /api/campaigns/{id}/update`. There is no supported knob that rebuilds
a queue on demand.

That a resume CLEARS existing scheduled rows is also NOT DOCUMENTED - yet we
watched ten rows become zero at 09:06Z. The behaviour is real and
undocumented, which is the reason to be slow rather than fast here.

## THE CONTINGENT AUTHORIZATION REQUEST — only if zero rows at 16:30Z

Not requested yet. Written now so the decision is not drafted under time
pressure at 16:30Z.

    CAMPAIGN            487
    OPERATION           PATCH /api/campaigns/487/pause
                        then PATCH /api/campaigns/487/resume
                        ONCE, as a pair, no other call
    WHY                 the only documented way to force a scheduler run
                        before the end of a sending day
    CURRENT STATE       active, 10 leads in_sequence, sent 0, queue 0,
                        first_scheduled none
    EXPECTED EFFECT     the scheduler runs and rebuilds scheduled rows. The
                        earliest they can land is a day sender 2736 has a
                        free slot
    DUPLICATE-SEND RISK LOW and it is argued, not asserted: emails_sent is 0,
                        so there is no sent row for a rebuild to duplicate.
                        The risk is not duplication but the same clearing
                        behaviour we already saw, leaving 487 no better off
    SENDER CAPACITY     no change. 2736 is not asked for more; the rebuild
                        places rows only where it already has room
    APPROVALS           unchanged. Same ten leads, same approved control
                        copy, no membership or copy write
    ROLLBACK            none that restores rows. A pause/resume cannot be
                        undone, which is the whole reason it needs a grant.
                        If it clears the queue again 487 is where it is now
    POST-ACTION READBACK  scheduled_emails(487), sending_schedule(487) for
                        all three days, campaign status, and per-lead
                        membership - the same four reads as the 09:06Z resume

The grant this would need is NEW. The 2026-09-21 grant was ONCE, it was
spent at 09:06Z, and condition 5 forbids a second resume. This request is
deliberately narrow: one pause/resume pair on 487, nothing else, and it does
not ask for standing permission to repeat it.

## Unrelated authorized work continues regardless

487 blocks nothing else. 489 holds 8 scheduled rows and the provider reports
3 emails today, first at 13:34Z. HeyReach 605732 advanced `lastActionTime` to
09:26:26Z today, which retires the stall hypothesis in REFUTED-004.
